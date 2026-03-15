"""Deterministic tests for Run Browser endpoint (PR-RUN-1).

Covers AC-1 through AC-20 from docs/specs/PR_RUN_1_SPEC.md §7.

All tests use temp directories with fixture copies — no live pipeline dependency.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_analyst.api.services.ops_run_browser import (
    RunScanError,
    project_run_browser,
)

# ── Paths ────────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_RUN_RECORD = FIXTURES_DIR / "sample_run_record.json"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_sample() -> dict:
    return json.loads(SAMPLE_RUN_RECORD.read_text(encoding="utf-8"))


def _write_run(runs_dir: Path, run_id: str, record: dict) -> Path:
    """Write a run_record.json to a temp run directory."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record_path = run_dir / "run_record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    return run_dir


def _make_run(
    run_id: str,
    timestamp: str = "2026-03-14T11:00:00Z",
    instrument: str = "XAUUSD",
    session: str = "NY",
    arbiter_ran: bool = True,
    verdict: str = "NO_TRADE",
    errors: list | None = None,
    stages: list | None = None,
    analysts_failed: list | None = None,
) -> dict:
    """Build a minimal run_record dict for testing."""
    record = _load_sample()
    record["run_id"] = run_id
    record["timestamp"] = timestamp
    record["request"]["instrument"] = instrument
    record["request"]["session"] = session
    record["arbiter"]["ran"] = arbiter_ran
    record["arbiter"]["verdict"] = verdict
    if errors is not None:
        record["errors"] = errors
    if stages is not None:
        record["stages"] = stages
    if analysts_failed is not None:
        record["analysts_failed"] = analysts_failed
    return record


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def runs_dir(tmp_path):
    """Provide a temp runs directory."""
    d = tmp_path / "runs"
    d.mkdir()
    return d


@pytest.fixture()
def populated_runs_dir(runs_dir):
    """Runs dir with 5 varied runs for testing."""
    _write_run(runs_dir, "run_001", _make_run(
        "run_001", "2026-03-14T11:00:00Z", "XAUUSD", "NY",
    ))
    _write_run(runs_dir, "run_002", _make_run(
        "run_002", "2026-03-14T10:00:00Z", "EURUSD", "LDN",
    ))
    _write_run(runs_dir, "run_003", _make_run(
        "run_003", "2026-03-14T09:00:00Z", "XAUUSD", "ASIA",
    ))
    _write_run(runs_dir, "run_004", _make_run(
        "run_004", "2026-03-14T08:00:00Z", "EURUSD", "NY",
    ))
    _write_run(runs_dir, "run_005", _make_run(
        "run_005", "2026-03-14T07:00:00Z", "XAUUSD", "NY",
        arbiter_ran=False, verdict="",
    ))
    return runs_dir


@pytest.fixture()
def client(populated_runs_dir):
    """TestClient with the runs router mounted, pointing at temp dir."""
    from unittest.mock import patch
    from ai_analyst.api.routers.runs import router as runs_router

    app = FastAPI()
    app.include_router(runs_router)

    with patch(
        "ai_analyst.api.services.ops_run_browser._RUNS_DIR",
        populated_runs_dir,
    ):
        yield TestClient(app)


# ── AC-1: Endpoint exists ────────────────────────────────────────────────────


class TestEndpointExists:
    def test_returns_200(self, client):
        resp = client.get("/runs/")
        assert resp.status_code == 200

    def test_response_has_items(self, client):
        data = client.get("/runs/").json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_response_has_pagination(self, client):
        data = client.get("/runs/").json()
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert "has_next" in data


# ── AC-2: ResponseMeta present ───────────────────────────────────────────────


class TestResponseMeta:
    def test_version_present(self, client):
        data = client.get("/runs/").json()
        assert data["version"] == "2026.03"

    def test_generated_at_present(self, client):
        data = client.get("/runs/").json()
        assert "generated_at" in data
        # Should be ISO 8601 parseable
        datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))

    def test_data_state_present(self, client):
        data = client.get("/runs/").json()
        assert data["data_state"] in ("live", "stale", "unavailable")


# ── AC-3: Pagination works ───────────────────────────────────────────────────


class TestPagination:
    def test_page_size_limits_results(self, client):
        data = client.get("/runs/?page=1&page_size=2").json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 5
        assert data["has_next"] is True

    def test_page_2(self, client):
        data = client.get("/runs/?page=2&page_size=2").json()
        assert len(data["items"]) == 2
        assert data["page"] == 2
        assert data["has_next"] is True

    def test_last_page(self, client):
        data = client.get("/runs/?page=3&page_size=2").json()
        assert len(data["items"]) == 1
        assert data["has_next"] is False

    def test_beyond_last_page(self, client):
        data = client.get("/runs/?page=10&page_size=2").json()
        assert len(data["items"]) == 0
        assert data["has_next"] is False


# ── AC-4: Page bounds enforced ───────────────────────────────────────────────


class TestPageBounds:
    def test_page_size_zero(self, client):
        resp = client.get("/runs/?page_size=0")
        assert resp.status_code == 422

    def test_page_size_too_large(self, client):
        resp = client.get("/runs/?page_size=100")
        assert resp.status_code == 422

    def test_page_zero(self, client):
        resp = client.get("/runs/?page=0")
        assert resp.status_code == 422


# ── AC-5: Newest-first sort ──────────────────────────────────────────────────


class TestSort:
    def test_newest_first(self, client):
        data = client.get("/runs/").json()
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True)


# ── AC-6: Instrument filter ──────────────────────────────────────────────────


class TestInstrumentFilter:
    def test_filter_xauusd(self, client):
        data = client.get("/runs/?instrument=XAUUSD").json()
        assert all(item["instrument"] == "XAUUSD" for item in data["items"])
        assert data["total"] == 3  # run_001, run_003, run_005

    def test_filter_eurusd(self, client):
        data = client.get("/runs/?instrument=EURUSD").json()
        assert all(item["instrument"] == "EURUSD" for item in data["items"])
        assert data["total"] == 2  # run_002, run_004


# ── AC-7: Session filter ─────────────────────────────────────────────────────


class TestSessionFilter:
    def test_filter_ny(self, client):
        data = client.get("/runs/?session=NY").json()
        assert all(item["session"] == "NY" for item in data["items"])
        assert data["total"] == 3  # run_001, run_004, run_005

    def test_filter_ldn(self, client):
        data = client.get("/runs/?session=LDN").json()
        assert data["total"] == 1


# ── AC-8: Combined filter ────────────────────────────────────────────────────


class TestCombinedFilter:
    def test_xauusd_ny(self, client):
        data = client.get("/runs/?instrument=XAUUSD&session=NY").json()
        assert data["total"] == 2  # run_001, run_005
        assert all(
            item["instrument"] == "XAUUSD" and item["session"] == "NY"
            for item in data["items"]
        )


# ── AC-9: No-match filter ────────────────────────────────────────────────────


class TestNoMatchFilter:
    def test_nonexistent_instrument(self, client):
        resp = client.get("/runs/?instrument=GBPJPY")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# ── AC-10: Malformed artifact tolerance ───────────────────────────────────────


class TestMalformedTolerance:
    def test_malformed_json_skipped(self, populated_runs_dir):
        bad_dir = populated_runs_dir / "run_bad"
        bad_dir.mkdir()
        (bad_dir / "run_record.json").write_text("{invalid json", encoding="utf-8")

        result = project_run_browser(runs_dir=populated_runs_dir)
        # Should still return the 5 valid runs, skipping the malformed one
        assert result.total == 5
        assert result.data_state == "stale"  # skipped > 0

    def test_missing_required_fields_skipped(self, populated_runs_dir):
        bad_dir = populated_runs_dir / "run_no_id"
        bad_dir.mkdir()
        (bad_dir / "run_record.json").write_text(
            json.dumps({"timestamp": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

        result = project_run_browser(runs_dir=populated_runs_dir)
        assert result.total == 5  # 5 valid, 1 skipped

    def test_no_run_record_skipped(self, populated_runs_dir):
        junk_dir = populated_runs_dir / "junk_folder"
        junk_dir.mkdir()

        result = project_run_browser(runs_dir=populated_runs_dir)
        assert result.total == 5


# ── AC-11: Empty runs directory ───────────────────────────────────────────────


class TestEmptyDirectory:
    def test_empty_dir(self, runs_dir):
        result = project_run_browser(runs_dir=runs_dir)
        assert result.total == 0
        assert result.items == []
        assert result.data_state == "live"

    def test_nonexistent_dir(self, tmp_path):
        result = project_run_browser(runs_dir=tmp_path / "nonexistent")
        assert result.total == 0
        assert result.items == []


# ── AC-12: Scan bound respected ──────────────────────────────────────────────


class TestScanBound:
    def test_max_scan_limits_dirs(self, runs_dir):
        # Create 10 runs but scan max 3
        for i in range(10):
            _write_run(runs_dir, f"run_{i:03d}", _make_run(
                f"run_{i:03d}", f"2026-03-14T{i:02d}:00:00Z",
            ))

        result = project_run_browser(runs_dir=runs_dir, max_scan=3)
        # Should scan at most 3, so total <= 3
        assert result.total <= 3


# ── AC-13: run_status: completed ─────────────────────────────────────────────


class TestRunStatusCompleted:
    def test_clean_run_is_completed(self, runs_dir):
        _write_run(runs_dir, "run_clean", _make_run(
            "run_clean",
            arbiter_ran=True,
            verdict="BUY",
            errors=[],
            stages=[
                {"stage": "validate_input", "status": "ok", "duration_ms": 100},
                {"stage": "arbiter", "status": "ok", "duration_ms": 200},
            ],
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].run_status == "completed"


# ── AC-14: run_status: partial ───────────────────────────────────────────────


class TestRunStatusPartial:
    def test_no_arbiter_is_partial(self, runs_dir):
        _write_run(runs_dir, "run_partial", _make_run(
            "run_partial",
            arbiter_ran=False,
            verdict="",
            errors=[],
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].run_status == "partial"

    def test_arbiter_ran_no_verdict_is_partial(self, runs_dir):
        record = _make_run("run_partial2", errors=[])
        record["arbiter"] = {"ran": True}  # no verdict key
        _write_run(runs_dir, "run_partial2", record)
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].run_status == "partial"


# ── AC-15: run_status: failed ────────────────────────────────────────────────


class TestRunStatusFailed:
    def test_errors_means_failed(self, runs_dir):
        _write_run(runs_dir, "run_err", _make_run(
            "run_err",
            errors=[{"error": "something broke"}],
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].run_status == "failed"

    def test_stage_failure_means_failed(self, runs_dir):
        _write_run(runs_dir, "run_stage_fail", _make_run(
            "run_stage_fail",
            errors=[],
            stages=[
                {"stage": "validate_input", "status": "ok", "duration_ms": 100},
                {"stage": "analyst_execution", "status": "failed", "duration_ms": 0},
            ],
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].run_status == "failed"

    def test_analysts_failed_no_verdict(self, runs_dir):
        _write_run(runs_dir, "run_af", _make_run(
            "run_af",
            arbiter_ran=False,
            verdict="",
            errors=[],
            analysts_failed=[{"persona": "test", "reason": "crash"}],
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].run_status == "failed"


# ── AC-17: final_decision gated ──────────────────────────────────────────────


class TestFinalDecisionGated:
    def test_arbiter_ran_true_has_decision(self, runs_dir):
        _write_run(runs_dir, "run_v", _make_run(
            "run_v", arbiter_ran=True, verdict="BUY",
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].final_decision == "BUY"

    def test_arbiter_ran_false_null_decision(self, runs_dir):
        _write_run(runs_dir, "run_nv", _make_run(
            "run_nv", arbiter_ran=False, verdict="BUY",
        ))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].final_decision is None


# ── AC-18: trace_available field ──────────────────────────────────────────────


class TestTraceAvailable:
    def test_readable_run_trace_available(self, runs_dir):
        _write_run(runs_dir, "run_ok", _make_run("run_ok"))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].trace_available is True

    def test_malformed_run_not_in_results(self, runs_dir):
        """Malformed runs are skipped entirely (not returned with trace_available=false)."""
        bad_dir = runs_dir / "run_bad"
        bad_dir.mkdir()
        (bad_dir / "run_record.json").write_text("{bad", encoding="utf-8")

        result = project_run_browser(runs_dir=runs_dir)
        assert all(item.trace_available for item in result.items)


# ── AC-19: No trace data leakage ─────────────────────────────────────────────


class TestNoTraceLeakage:
    def test_no_analyst_results(self, populated_runs_dir):
        result = project_run_browser(runs_dir=populated_runs_dir)
        for item in result.items:
            item_dict = item.model_dump()
            assert "analysts" not in item_dict
            assert "stages" not in item_dict
            assert "arbiter" not in item_dict or isinstance(item_dict.get("arbiter"), type(None))
            # Only expected fields
            expected_keys = {
                "run_id", "timestamp", "instrument", "session",
                "final_decision", "run_status", "trace_available",
            }
            assert set(item_dict.keys()) == expected_keys


# ── AC-20: Error envelope ────────────────────────────────────────────────────


class TestErrorEnvelope:
    def test_scan_failure_returns_error(self):
        from unittest.mock import patch
        from ai_analyst.api.routers.runs import router as runs_router

        app = FastAPI()
        app.include_router(runs_router)

        with patch(
            "ai_analyst.api.routers.runs.project_run_browser",
            side_effect=RunScanError("Cannot scan runs directory: boom"),
        ):
            client = TestClient(app)
            resp = client.get("/runs/")
            assert resp.status_code == 500
            data = resp.json()
            assert data["detail"]["error"] == "RUN_SCAN_FAILED"


# ── Projection service unit tests ────────────────────────────────────────────


class TestProjectionService:
    def test_basic_projection(self, runs_dir):
        _write_run(runs_dir, "run_a", _make_run("run_a"))
        result = project_run_browser(runs_dir=runs_dir)
        assert len(result.items) == 1
        item = result.items[0]
        assert item.run_id == "run_a"
        assert item.instrument == "XAUUSD"
        assert item.session == "NY"

    def test_missing_request_block(self, runs_dir):
        record = _make_run("run_nr")
        del record["request"]
        _write_run(runs_dir, "run_nr", record)
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].instrument is None
        assert result.items[0].session is None

    def test_missing_arbiter_block(self, runs_dir):
        record = _make_run("run_na")
        del record["arbiter"]
        _write_run(runs_dir, "run_na", record)
        result = project_run_browser(runs_dir=runs_dir)
        assert result.items[0].final_decision is None
        assert result.items[0].run_status == "partial"

    def test_data_state_live_when_all_clean(self, runs_dir):
        _write_run(runs_dir, "run_clean", _make_run("run_clean"))
        result = project_run_browser(runs_dir=runs_dir)
        assert result.data_state == "live"
