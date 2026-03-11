"""Deterministic tests for Security/API Hardening phase.

Covers AC-1 (auth), AC-2 (body limit), AC-3 (graph timeout),
AC-4 (error contract), AC-5 (stream error contract).
All tests are deterministic — no live LLM calls or provider dependency.
"""

import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_analyst.api import main as api_main


# ── Helpers ──────────────────────────────────────────────────────────────────

_PNG_HEADER = b"\x89PNG\r\n\x1a\n"

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
        "chart_h4": ("chart.png", _PNG_HEADER + b"\x00" * 64, "image/png"),
    }
    return data, files


# ── AC-1: Auth policy tests ─────────────────────────────────────────────────

class TestAuthPolicy:
    """AC-1: /analyse and /analyse/stream have explicit deterministic access policy."""

    def test_analyse_rejects_missing_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "secret-key")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post("/analyse", data=data, files=files)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "unauthorized"

    def test_analyse_rejects_wrong_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "secret-key")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "wrong-key"},
            )
        assert resp.status_code == 401

    def test_analyse_rejects_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("AI_ANALYST_API_KEY", raising=False)
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "any-key"},
            )
        assert resp.status_code == 401

    def test_analyse_accepts_correct_api_key(self, monkeypatch):
        """With correct key, request proceeds past auth (may fail on graph, that's fine)."""
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        # Stub graph to avoid needing full pipeline
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        # Should get past auth — 200 or pipeline error, but NOT 401
        assert resp.status_code != 401

    def test_analyse_stream_rejects_missing_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "secret-key")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post("/analyse/stream", data=data, files=files)
        assert resp.status_code == 401

    def test_analyse_stream_rejects_wrong_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "secret-key")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "wrong-key"},
            )
        assert resp.status_code == 401

    def test_health_does_not_require_api_key(self, monkeypatch):
        """Health endpoint should not require auth."""
        monkeypatch.setenv("AI_ANALYST_API_KEY", "secret-key")
        with TestClient(api_main.app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200


# ── AC-2: Body-size limit tests ─────────────────────────────────────────────

class TestBodySizeLimit:
    """AC-2: Global body-size cap rejects oversized requests."""

    def test_rejects_oversized_content_length(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        with TestClient(api_main.app) as client:
            # Claim a content-length far exceeding 10 MB
            resp = client.post(
                "/analyse",
                headers={
                    "X-API-Key": "test-key",
                    "Content-Length": str(20 * 1024 * 1024),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                content=b"x=1",
            )
        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"].lower()

    def test_accepts_normal_size_request(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        # Should not be 413
        assert resp.status_code != 413


# ── AC-3: Graph execution timeout tests ─────────────────────────────────────

class TestGraphTimeout:
    """AC-3: Analysis execution has explicit server-side timeout boundary."""

    def test_analyse_returns_504_on_graph_timeout(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")

        class _SlowGraph:
            async def ainvoke(self, state):
                await asyncio.sleep(999)

        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _SlowGraph())
        monkeypatch.setattr(api_main, "GRAPH_TIMEOUT_SECONDS", 0.1)

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 504
        body = resp.json()
        assert "timed out" in body["detail"].lower()
        # AC-4: Must not leak internal details
        assert "asyncio" not in body["detail"].lower()
        assert "Traceback" not in body["detail"]

    def test_analyse_stream_emits_timeout_error_event(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")

        class _SlowGraph:
            async def ainvoke(self, state):
                await asyncio.sleep(999)

        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _SlowGraph())
        monkeypatch.setattr(api_main, "GRAPH_TIMEOUT_SECONDS", 0.1)

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        # Stream returns 200 with SSE events
        assert resp.status_code == 200
        events = [
            line.removeprefix("data: ")
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        error_events = [json.loads(e) for e in events if '"error"' in e]
        assert len(error_events) >= 1
        assert "timed out" in error_events[-1]["detail"].lower()


# ── AC-4: Error contract tests ──────────────────────────────────────────────

class TestErrorContract:
    """AC-4: Client-facing errors are sanitised — no internal detail leaks."""

    def test_analyse_runtime_error_no_detail_leak(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")

        class _FailGraph:
            async def ainvoke(self, state):
                raise RuntimeError("Provider sk-abc123secret returned 500: internal server error at /v1/chat")

        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _FailGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        # Must not contain the secret or provider error detail
        assert "sk-abc" not in detail
        assert "internal server error" not in detail.lower()
        assert "/v1/chat" not in detail
        # Should be the generic safe message
        assert "check server logs" in detail.lower()

    def test_analyse_generic_error_no_detail_leak(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")

        class _FailGraph:
            async def ainvoke(self, state):
                raise ValueError("unexpected internal state at line 42")

        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _FailGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "line 42" not in detail
        assert "check server logs" in detail.lower()


# ── AC-5: Stream error contract tests ────────────────────────────────────────

class TestStreamErrorContract:
    """AC-5: /analyse/stream error events use safe contract — no raw str(exc)."""

    def test_stream_runtime_error_no_detail_leak(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")

        class _FailGraph:
            async def ainvoke(self, state):
                raise RuntimeError("Provider OPENAI_API_KEY=sk-secret returned 502")

        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _FailGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 200
        events = [
            line.removeprefix("data: ")
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        error_events = [json.loads(e) for e in events if '"error"' in e]
        assert len(error_events) >= 1
        error_detail = error_events[-1]["detail"]
        # Must not contain the raw exception text or secrets
        assert "sk-secret" not in error_detail
        assert "OPENAI_API_KEY" not in error_detail
        assert "502" not in error_detail
        assert "check server logs" in error_detail.lower()

    def test_stream_generic_error_safe(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")

        class _FailGraph:
            async def ainvoke(self, state):
                raise Exception("database connection pool exhausted")

        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _FailGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        events = [
            line.removeprefix("data: ")
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        error_events = [json.loads(e) for e in events if '"error"' in e]
        assert len(error_events) >= 1
        assert "database" not in error_events[-1]["detail"].lower()


# ── JSON form validation detail tests ───────────────────────────────────────

class TestJsonFormValidationDetail:
    """String-array multipart fields accept JSON arrays and Swagger-style CSV."""

    def test_analyse_accepts_timeframes_json_array(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["timeframes"] = '["H4","M15","M5"]'
            resp = client.post("/analyse", data=data, files=files, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_analyse_accepts_timeframes_csv(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["timeframes"] = "H4,M15,M5"
            resp = client.post("/analyse", data=data, files=files, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_analyse_accepts_no_trade_windows_json_array(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["no_trade_windows"] = '["FOMC","NFP"]'
            resp = client.post("/analyse", data=data, files=files, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_analyse_accepts_no_trade_windows_csv(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["no_trade_windows"] = "FOMC,NFP"
            resp = client.post("/analyse", data=data, files=files, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_analyse_accepts_csv_with_whitespace_trimming(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["timeframes"] = " H4 , M15 , M5 "
            resp = client.post("/analyse", data=data, files=files, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_malformed_json_array_still_returns_structured_422(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["timeframes"] = '["H4",'
            resp = client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["field"] == "timeframes"
        assert "form field 'timeframes'" in detail["message"]
        assert detail["raw_value"] == '\'["H4",\''
        assert detail["request_id"] is not None

    def test_optional_empty_open_positions_remains_accepted(self, monkeypatch):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())
        monkeypatch.setattr(api_main, "build_ticket_draft", lambda _v, _g: {"id": "t1"})
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["open_positions"] = ""
            resp = client.post("/analyse", data=data, files=files, headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_dev_parse_logging_includes_raw_field_and_mode(self, monkeypatch, caplog):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setenv("AI_ANALYST_DEV_DIAGNOSTICS", "true")
        caplog.set_level("INFO")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["timeframes"] = "H4,M15"
            client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key", "X-Request-ID": "req-parse-log"},
            )
        assert "[dev-parse] request_id=req-parse-log field=timeframes raw='H4,M15' mode=csv_fallback" in caplog.text


class TestDevDiagnosticsPersistence:
    def test_parse_failure_writes_fallback_diagnostics_jsonl(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setenv("AI_ANALYST_DEV_DIAGNOSTICS", "true")
        monkeypatch.setattr(api_main, "_DEV_DIAGNOSTICS_FALLBACK_PATH", tmp_path / "diag.jsonl")
        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            data["timeframes"] = '["H4",'
            client.post(
                "/analyse", data=data, files=files,
                headers={"X-API-Key": "test-key", "X-Request-ID": "req-diag-1"},
            )

        content = (tmp_path / "diag.jsonl").read_text(encoding="utf-8")
        assert "\"request_id\": \"req-diag-1\"" in content
        assert "\"final_status\": \"failed\"" in content


# ── Stub graph for happy-path tests ──────────────────────────────────────────

from pathlib import Path
from ai_analyst.models.arbiter_output import FinalVerdict


class _StubGraph:
    def __init__(self):
        fixture = Path(__file__).parent / "fixtures" / "sample_final_verdict.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        payload.pop("_comment", None)
        self._verdict = FinalVerdict.model_validate(payload)

    async def ainvoke(self, state):
        out = dict(state)
        out["final_verdict"] = self._verdict
        return out


class _SlowStubGraph(_StubGraph):
    """Stub graph with a small delay so the SSE loop emits at least one heartbeat."""

    async def ainvoke(self, state):
        await asyncio.sleep(0.4)  # > 0.2s heartbeat interval
        return await super().ainvoke(state)


class _ProgressStubGraph(_StubGraph):
    """Stub graph that pushes an analyst_done event before returning."""

    async def ainvoke(self, state):
        from ai_analyst.core import progress_store
        run_id = state["ground_truth"].run_id
        await progress_store.push_event(run_id, {
            "type": "analyst_done",
            "stage": "phase1",
            "persona": "test_persona",
            "model": "stub-model",
            "action": "long",
            "confidence": 0.85,
        })
        return await super().ainvoke(state)


# ── Stream event semantics tests ─────────────────────────────────────────────

def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE data lines into a list of JSON event dicts."""
    events = []
    for line in response_text.split("\n"):
        if line.startswith("data: "):
            try:
                events.append(json.loads(line.removeprefix("data: ")))
            except json.JSONDecodeError:
                pass
    return events


class TestStreamEventSemantics:
    """Stream happy-path event semantics: heartbeat, analyst_done shape, verdict."""

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self, monkeypatch):
        monkeypatch.setattr(api_main, "_check_rate_limit", lambda _ip: None)

    def test_stream_emits_verdict_event_with_expected_shape(self, monkeypatch):
        """Verdict event is emitted at stream completion with FinalVerdict payload."""
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _StubGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        verdict_events = [e for e in events if e.get("type") == "verdict"]
        assert len(verdict_events) == 1, f"Expected exactly 1 verdict event, got {len(verdict_events)}"
        verdict_payload = verdict_events[0]["verdict"]
        # Verify FinalVerdict shape — required fields present
        for field in ("final_bias", "decision", "overall_confidence",
                      "analyst_agreement_pct", "arbiter_notes"):
            assert field in verdict_payload, f"Missing field: {field}"

    def test_stream_emits_heartbeat_during_processing(self, monkeypatch):
        """At least one heartbeat event is emitted while the pipeline runs."""
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _SlowStubGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        heartbeats = [e for e in events if e.get("type") == "heartbeat"]
        assert len(heartbeats) >= 1, "Expected at least one heartbeat event"

    def test_stream_relays_analyst_done_event_shape(self, monkeypatch):
        """analyst_done events are relayed via SSE with required fields."""
        monkeypatch.setenv("AI_ANALYST_API_KEY", "test-key")
        monkeypatch.setattr(api_main, "build_analysis_graph", lambda: _ProgressStubGraph())

        with TestClient(api_main.app) as client:
            data, files = _multipart_payload()
            resp = client.post(
                "/analyse/stream", data=data, files=files,
                headers={"X-API-Key": "test-key"},
            )
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        analyst_events = [e for e in events if e.get("type") == "analyst_done"]
        assert len(analyst_events) >= 1, "Expected at least one analyst_done event"
        evt = analyst_events[0]
        # Verify analyst_done event shape
        for field in ("stage", "persona", "model", "action", "confidence"):
            assert field in evt, f"Missing field in analyst_done: {field}"
        assert evt["stage"] == "phase1"
        assert isinstance(evt["confidence"], (int, float))
