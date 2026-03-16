import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_analyst.api.routers.reflect import router as reflect_router


def _mk_run(run_id: str, ts: str, instrument: str = "XAUUSD", session: str = "NY", verdict: str = "NO_TRADE"):
    return {
        "run_id": run_id,
        "timestamp": ts,
        "request": {"instrument": instrument, "session": session},
        "analysts": [
            {"persona": "default_analyst", "status": "success"},
            {"persona": "ict_purist", "status": "success"},
        ],
        "analysts_skipped": [{"persona": "prosecutor", "status": "skipped", "reason": "test"}],
        "analysts_failed": [{"persona": "skeptical_quant", "status": "failed", "reason": "test"}],
        "arbiter": {"ran": True, "verdict": verdict},
        "usage_summary": {"total_calls": 2, "total_cost_usd": 0.01},
        "errors": [],
    }


def _mk_audit(run_id: str, decision: str = "NO_TRADE", risk_override: bool = True):
    return {
        "run_id": run_id,
        "analyst_outputs": [
            {"htf_bias": "bullish", "confidence": 0.8, "recommended_action": "BUY"},
            {"htf_bias": "bearish", "confidence": 0.6, "recommended_action": "SELL"},
        ],
        "final_verdict": {"risk_override_applied": risk_override, "decision": decision},
    }


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def app_client(tmp_path):
    runs_dir = tmp_path / "runs"
    audit_dir = tmp_path / "logs" / "runs"
    runs_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)

    app = FastAPI()
    app.include_router(reflect_router)

    with (
        patch("ai_analyst.api.services.reflect_aggregation._RUNS_DIR", runs_dir),
        patch("ai_analyst.api.services.reflect_aggregation._AUDIT_DIR", audit_dir),
        patch("ai_analyst.api.services.reflect_bundle._RUNS_DIR", runs_dir),
    ):
        yield TestClient(app), runs_dir, audit_dir


def test_persona_performance_below_threshold_empty(app_client):
    client, runs_dir, _ = app_client
    for i in range(9):
        _write_json(runs_dir / f"run_{i}" / "run_record.json", _mk_run(f"run_{i}", f"2026-03-14T11:0{i}:00Z"))
    data = client.get("/reflect/persona-performance?max_runs=50").json()
    assert data["threshold_met"] is False
    assert data["stats"] == []


def test_persona_performance_with_audit_enrichment(app_client):
    client, runs_dir, audit_dir = app_client
    for i in range(10):
        run_id = f"run_{i}"
        _write_json(runs_dir / run_id / "run_record.json", _mk_run(run_id, f"2026-03-14T10:{i:02d}:00Z", verdict="BUY"))
        _write_json(audit_dir / f"{run_id}.jsonl", _mk_audit(run_id, decision="NO_TRADE", risk_override=True))

    data = client.get("/reflect/persona-performance?max_runs=50").json()
    assert data["threshold_met"] is True
    stats = {s["persona"]: s for s in data["stats"]}
    da = stats["default_analyst"]
    assert da["participation_count"] == 10
    assert da["skip_count"] == 0
    assert da["fail_count"] == 0
    assert da["participation_rate"] == 1.0
    assert da["override_rate"] == 1.0
    assert da["flagged"] is True
    assert da["stance_alignment"] == 1.0
    assert da["avg_confidence"] == pytest.approx(0.8)


def test_persona_performance_without_audit_yields_null_provisional_metrics(app_client):
    client, runs_dir, _ = app_client
    for i in range(10):
        _write_json(runs_dir / f"run_{i}" / "run_record.json", _mk_run(f"run_{i}", f"2026-03-14T09:{i:02d}:00Z", verdict="BUY"))

    data = client.get("/reflect/persona-performance").json()
    stats = {s["persona"]: s for s in data["stats"]}
    da = stats["default_analyst"]
    assert da["override_rate"] is None
    assert da["avg_confidence"] is None
    assert data["data_state"] == "stale"


def test_persona_performance_invalid_params(app_client):
    client, *_ = app_client
    r = client.get("/reflect/persona-performance?max_runs=9")
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "INVALID_PARAMS"


def test_pattern_summary_bucket_threshold_and_flag(app_client):
    client, runs_dir, _ = app_client
    # one bucket above threshold and flagged no-trade
    for i in range(10):
        _write_json(runs_dir / f"xau_ny_{i}" / "run_record.json", _mk_run(f"xau_ny_{i}", f"2026-03-14T08:{i:02d}:00Z", "XAUUSD", "NY", "NO_TRADE"))
    # one sparse bucket
    for i in range(9):
        _write_json(runs_dir / f"eur_ldn_{i}" / "run_record.json", _mk_run(f"eur_ldn_{i}", f"2026-03-14T07:{i:02d}:00Z", "EURUSD", "LDN", "BUY"))

    data = client.get("/reflect/pattern-summary").json()
    buckets = {(b["instrument"], b["session"]): b for b in data["buckets"]}
    rich = buckets[("XAUUSD", "NY")]
    sparse = buckets[("EURUSD", "LDN")]
    assert rich["threshold_met"] is True
    assert rich["no_trade_rate"] == 1.0
    assert rich["flagged"] is True
    assert sparse["threshold_met"] is False
    assert sparse["verdict_distribution"] == []


def test_malformed_and_missing_required_runs_are_skipped(app_client):
    client, runs_dir, _ = app_client
    for i in range(10):
        _write_json(runs_dir / f"good_{i}" / "run_record.json", _mk_run(f"good_{i}", f"2026-03-14T06:{i:02d}:00Z"))
    # malformed
    bad = runs_dir / "bad1"
    bad.mkdir()
    (bad / "run_record.json").write_text("{bad", encoding="utf-8")
    # missing timestamp
    _write_json(runs_dir / "bad2" / "run_record.json", {"run_id": "bad2", "request": {"instrument": "XAUUSD", "session": "NY"}})

    data = client.get("/reflect/pattern-summary?max_runs=50").json()
    assert data["scan_bounds"]["skipped_runs"] == 2
    assert data["data_state"] == "stale"


def test_bundle_404_when_run_record_missing(app_client):
    client, *_ = app_client
    r = client.get("/reflect/run/does_not_exist")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "RUN_NOT_FOUND"


def test_bundle_usage_summary_precedence_usage_json_over_embedded(app_client):
    client, runs_dir, _ = app_client
    run_id = "run_bundle_1"
    _write_json(runs_dir / run_id / "run_record.json", _mk_run(run_id, "2026-03-14T06:00:00Z"))
    _write_json(runs_dir / run_id / "usage.json", {"total_calls": 999})
    (runs_dir / run_id / "usage.jsonl").write_text('{"x":1}\n', encoding="utf-8")

    data = client.get(f"/reflect/run/{run_id}").json()
    assert data["artifact_status"]["run_record"] == "present"
    assert data["artifact_status"]["usage_json"] == "present"
    assert data["artifact_status"]["usage_jsonl"] == "present"
    assert data["usage_summary"]["total_calls"] == 999


def test_bundle_embedded_usage_summary_fallback(app_client):
    client, runs_dir, _ = app_client
    run_id = "run_bundle_2"
    _write_json(runs_dir / run_id / "run_record.json", _mk_run(run_id, "2026-03-14T06:01:00Z"))
    data = client.get(f"/reflect/run/{run_id}").json()
    assert data["artifact_status"]["usage_json"] == "missing"
    assert data["usage_summary"]["total_calls"] == 2


def test_bundle_malformed_usage_degrades_not_500(app_client):
    client, runs_dir, _ = app_client
    run_id = "run_bundle_3"
    _write_json(runs_dir / run_id / "run_record.json", _mk_run(run_id, "2026-03-14T06:02:00Z"))
    (runs_dir / run_id / "usage.jsonl").write_text("{bad", encoding="utf-8")

    r = client.get(f"/reflect/run/{run_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["artifact_status"]["usage_jsonl"] == "malformed"


def test_bundle_malformed_run_record_is_404(app_client):
    client, runs_dir, _ = app_client
    run_id = "bad_rr"
    d = runs_dir / run_id
    d.mkdir(parents=True)
    (d / "run_record.json").write_text("{bad", encoding="utf-8")

    r = client.get(f"/reflect/run/{run_id}")
    assert r.status_code == 404
