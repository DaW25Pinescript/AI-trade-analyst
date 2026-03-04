import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_analyst.api import main as api_main
from ai_analyst.models.arbiter_output import FinalVerdict


class _StubGraph:
    def __init__(self, verdict: FinalVerdict):
        self._verdict = verdict

    async def ainvoke(self, state):
        out = dict(state)
        out["final_verdict"] = self._verdict
        return out


def _sample_verdict() -> FinalVerdict:
    fixture = Path(__file__).parent / "fixtures" / "sample_final_verdict.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    payload.pop("_comment", None)
    return FinalVerdict.model_validate(payload)


def _multipart_payload():
    data = {
        "instrument": "XAUUSD",
        "session": "NY",
        "timeframes": json.dumps(["H4", "M15"]),
        "account_balance": "10000",
        "min_rr": "2.0",
        "max_risk_per_trade": "0.5",
        "max_daily_risk": "2.0",
        "no_trade_windows": json.dumps(["FOMC"]),
        "market_regime": "trending",
        "news_risk": "none_noted",
        "open_positions": json.dumps([]),
        "overlay_indicator_claims": json.dumps(["FVG"]),
    }
    files = {
        "chart_h4": ("chart.png", b"fake-image-bytes", "image/png"),
    }
    return data, files


def test_analyse_includes_run_usage_summary(monkeypatch):
    verdict = _sample_verdict()
    stub = _StubGraph(verdict)
    # HIGH-8: graph is now set via lifespan startup — patch build_analysis_graph so
    # the lifespan sets app.state.graph to our stub instead of the real pipeline.
    monkeypatch.setattr(api_main, "build_analysis_graph", lambda: stub)
    monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "draft-1"})

    calls = []

    def _fake_summarize(run_dir):
        calls.append(str(run_dir))
        return {
            "total_calls": 3,
            "successful_calls": 3,
            "failed_calls": 0,
            "calls_by_stage": {"phase1_analyst": 2, "arbiter": 1},
            "calls_by_node": {"default": 2, "arbiter_node": 1},
            "calls_by_model": {"gpt-4o": 2, "claude": 1},
            "calls_by_provider": {"openai": 2, "anthropic": 1},
            "tokens": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "calls_with_token_usage": 3,
            "calls_without_token_usage": 0,
            "total_cost_usd": 0.12,
        }

    monkeypatch.setattr(api_main, "summarize_usage", _fake_summarize)

    with TestClient(api_main.app) as client:
        data, files = _multipart_payload()
        resp = client.post("/analyse", data=data, files=files)

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"]
    assert body["ticket_draft"]["id"] == "draft-1"
    assert body["usage_summary"]["total_calls"] == 3
    assert body["usage_summary"]["tokens"]["total_tokens"] == 150
    assert calls and body["run_id"] in calls[0]


def test_analyse_usage_summary_fail_safe(monkeypatch):
    verdict = _sample_verdict()
    stub = _StubGraph(verdict)
    monkeypatch.setattr(api_main, "build_analysis_graph", lambda: stub)
    monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "draft-2"})

    def _raise(_run_dir):
        raise RuntimeError("meter read failed")

    monkeypatch.setattr(api_main, "summarize_usage", _raise)

    with TestClient(api_main.app) as client:
        data, files = _multipart_payload()
        resp = client.post("/analyse", data=data, files=files)

    assert resp.status_code == 200
    body = resp.json()
    assert body["usage_summary"]["total_calls"] == 0
    assert body["usage_summary"]["tokens"]["total_tokens"] == 0


def test_get_run_usage_returns_summary(monkeypatch):
    calls = []

    def _fake_summarize(run_dir):
        calls.append(str(run_dir))
        return {
            "total_calls": 2,
            "successful_calls": 2,
            "failed_calls": 0,
            "calls_by_stage": {"arbiter": 2},
            "calls_by_node": {"arbiter_node": 2},
            "calls_by_model": {"gpt-4o": 2},
            "calls_by_provider": {"openai": 2},
            "tokens": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            "calls_with_token_usage": 2,
            "calls_without_token_usage": 0,
            "total_cost_usd": 0.03,
        }

    monkeypatch.setattr(api_main, "summarize_usage", _fake_summarize)

    with TestClient(api_main.app) as client:
        resp = client.get("/runs/run-abc/usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-abc"
    assert body["usage_summary"]["total_calls"] == 2
    assert calls and "run-abc" in calls[0]


def test_get_run_usage_fail_safe(monkeypatch):
    def _raise(_run_dir):
        raise RuntimeError("meter read failed")

    monkeypatch.setattr(api_main, "summarize_usage", _raise)

    with TestClient(api_main.app) as client:
        resp = client.get("/runs/run-def/usage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "run-def"
    assert body["usage_summary"]["total_calls"] == 0
    assert body["usage_summary"]["tokens"]["total_tokens"] == 0
