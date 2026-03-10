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
