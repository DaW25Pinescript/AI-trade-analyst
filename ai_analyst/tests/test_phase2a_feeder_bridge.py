"""
Phase 2a — feeder bridge + float fix tests.

Tests:
  1. POST /feeder/ingest accepts a valid feeder contract and returns MacroContext
  2. POST /feeder/ingest rejects invalid contract_version
  3. POST /feeder/ingest rejects non-JSON body
  4. GET /feeder/health returns no_data before any ingestion
  5. GET /feeder/health returns fresh after successful ingestion
  6. macro_context_node prefers live feeder context over scheduler
  7. macro_context_node falls back to scheduler when feeder is stale
  8. macro_context_node falls back to scheduler when no feeder context
  9. ticket_draft includes aiEdgeScorePct alongside aiEdgeScore
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_analyst.api import main as api_main
from ai_analyst.graph.macro_context_node import (
    _try_feeder_context,
    macro_context_node,
    _FEEDER_STALE_SECONDS,
)
from ai_analyst.output.ticket_draft import build_ticket_draft
from ai_analyst.models.arbiter_output import FinalVerdict


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _sample_feeder_payload():
    """Minimal valid feeder contract for testing."""
    return {
        "contract_version": "1.0.0",
        "generated_at": "2026-03-04T12:00:00Z",
        "instrument_context": "XAUUSD",
        "sources_queried": ["finnhub", "fred", "gdelt"],
        "status": "ok",
        "warnings": [],
        "events": [
            {
                "event_id": "test-nfp-001",
                "source": "finnhub",
                "title": "Non-Farm Payrolls",
                "category": "employment",
                "region": "US",
                "timestamp": "2026-03-01T12:30:00Z",
                "importance": "high",
                "actual": 250000.0,
                "forecast": 245000.0,
                "previous": 240000.0,
                "surprise_direction": "positive",
                "pressure_direction": None,
                "raw_reference": None,
                "tags": ["economic_release", "labour"],
            },
        ],
        "source_health": {
            "finnhub": {"status": "ok", "record_count": 1, "latency_ms": 100},
            "fred": {"status": "failed", "error": "FRED_API_KEY not set"},
            "gdelt": {"status": "ok", "record_count": 0, "latency_ms": 50},
        },
    }


def _sample_verdict_dict():
    """Minimal FinalVerdict dict for testing."""
    return {
        "final_bias": "bullish",
        "decision": "ENTER_LONG",
        "approved_setups": [{
            "type": "Pullback",
            "entry_zone": "1932.5–1934.0",
            "stop": "1929.8",
            "targets": ["TP1: 1937.2"],
            "rr_estimate": 2.1,
            "confidence": 0.78,
        }],
        "no_trade_conditions": [],
        "overall_confidence": 0.78,
        "analyst_agreement_pct": 75,
        "risk_override_applied": False,
        "arbiter_notes": "Test note",
        "audit_log": {
            "run_id": "test-run-001",
            "analysts_received": 4,
            "analysts_valid": 3,
            "htf_consensus": True,
            "setup_consensus": True,
            "risk_override": False,
        },
    }


# ── /feeder/ingest endpoint tests ─────────────────────────────────────────────

def test_feeder_ingest_accepts_valid_payload():
    """POST /feeder/ingest with valid contract returns 200 + MacroContext."""
    with TestClient(api_main.app) as client:
        payload = _sample_feeder_payload()
        response = client.post("/feeder/ingest", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "macro_context" in body
    ctx = body["macro_context"]
    assert ctx["regime"] in ("risk_on", "risk_off", "neutral")
    assert 0.0 <= ctx["confidence"] <= 1.0
    assert "ingested_at" in body


def test_feeder_ingest_rejects_bad_contract_version():
    """POST /feeder/ingest rejects unsupported contract_version."""
    with TestClient(api_main.app) as client:
        payload = _sample_feeder_payload()
        payload["contract_version"] = "99.0.0"
        response = client.post("/feeder/ingest", json=payload)

    assert response.status_code == 422
    assert "contract_version" in response.json()["detail"].lower()


def test_feeder_ingest_rejects_non_json():
    """POST /feeder/ingest rejects non-JSON body."""
    with TestClient(api_main.app) as client:
        response = client.post(
            "/feeder/ingest",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422


def test_feeder_ingest_rejects_invalid_schema_with_safe_error():
    """POST /feeder/ingest rejects invalid schema with safe error details."""
    with TestClient(api_main.app) as client:
        payload = {"instrument_context": "XAUUSD"}  # missing required contract fields
        response = client.post("/feeder/ingest", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "FEEDER_PAYLOAD_INVALID"
    assert "traceback" not in json.dumps(detail).lower()
    assert "instrument_context" not in json.dumps(detail)


# ── /feeder/health endpoint tests ─────────────────────────────────────────────

def test_feeder_health_returns_no_data_initially():
    """GET /feeder/health before any ingestion returns no_data."""
    with TestClient(api_main.app) as client:
        response = client.get("/feeder/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_data"
    assert body["stale"] is True


def test_feeder_health_returns_fresh_after_ingest():
    """GET /feeder/health after successful ingest returns fresh."""
    with TestClient(api_main.app) as client:
        # First ingest
        payload = _sample_feeder_payload()
        ingest_resp = client.post("/feeder/ingest", json=payload)
        assert ingest_resp.status_code == 200

        # Then health check
        response = client.get("/feeder/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fresh"
    assert body["stale"] is False
    assert body["age_seconds"] < 5  # should be nearly instant
    assert body["event_count"] == 1
    assert body["regime"] in ("risk_on", "risk_off", "neutral")


# ── macro_context_node feeder preference tests ────────────────────────────────

def test_try_feeder_context_returns_fresh_context():
    """_try_feeder_context returns context when fresh."""
    from macro_risk_officer.core.models import MacroContext, AssetPressure

    ctx = MacroContext(
        regime="risk_on",
        vol_bias="contracting",
        asset_pressure=AssetPressure(),
        conflict_score=0.2,
        confidence=0.65,
        time_horizon_days=14,
        explanation=["Test"],
        active_event_ids=["e1"],
    )
    state = {
        "_feeder_context": ctx,
        "_feeder_ingested_at": datetime.now(timezone.utc),
    }

    result = _try_feeder_context(state)
    assert result is not None
    assert result.regime == "risk_on"


def test_try_feeder_context_returns_none_when_stale():
    """_try_feeder_context returns None when context is stale."""
    from macro_risk_officer.core.models import MacroContext, AssetPressure

    ctx = MacroContext(
        regime="risk_on",
        vol_bias="contracting",
        asset_pressure=AssetPressure(),
        conflict_score=0.2,
        confidence=0.65,
        time_horizon_days=14,
        explanation=["Test"],
        active_event_ids=["e1"],
    )
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=_FEEDER_STALE_SECONDS + 100)
    state = {
        "_feeder_context": ctx,
        "_feeder_ingested_at": stale_time,
    }

    result = _try_feeder_context(state)
    assert result is None


def test_try_feeder_context_returns_none_when_absent():
    """_try_feeder_context returns None when no feeder context in state."""
    state = {}
    result = _try_feeder_context(state)
    assert result is None


def test_macro_context_node_prefers_feeder():
    """macro_context_node uses feeder context when fresh, skipping scheduler."""
    from macro_risk_officer.core.models import MacroContext, AssetPressure

    ctx = MacroContext(
        regime="risk_off",
        vol_bias="expanding",
        asset_pressure=AssetPressure(VIX=0.5),
        conflict_score=-0.3,
        confidence=0.7,
        time_horizon_days=45,
        explanation=["FOMC hawkish surprise"],
        active_event_ids=["fomc-001"],
    )

    from ai_analyst.models.ground_truth import (
        GroundTruthPacket, RiskConstraints, MarketContext, ScreenshotMetadata,
    )

    gt = GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4"],
        charts={"H4": "fake-b64"},
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")
        ],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000),
    )

    state = {
        "ground_truth": gt,
        "lens_config": None,
        "analyst_outputs": [],
        "overlay_delta_reports": [],
        "macro_context": None,
        "final_verdict": None,
        "error": None,
        "enable_deliberation": False,
        "deliberation_outputs": [],
        "_feeder_context": ctx,
        "_feeder_ingested_at": datetime.now(timezone.utc),
    }

    result = asyncio.run(macro_context_node(state))
    assert result["macro_context"] is not None
    assert result["macro_context"].regime == "risk_off"
    assert result["macro_context"].conflict_score == -0.3


# ── ticket_draft float fix test ───────────────────────────────────────────────

def test_ticket_draft_includes_pct_score():
    """build_ticket_draft includes aiEdgeScorePct alongside aiEdgeScore."""
    verdict = FinalVerdict.model_validate(_sample_verdict_dict())

    from ai_analyst.models.ground_truth import (
        GroundTruthPacket, RiskConstraints, MarketContext, ScreenshotMetadata,
    )

    gt = GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4"],
        charts={"H4": "fake-b64"},
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")
        ],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000),
    )

    draft = build_ticket_draft(verdict, gt)
    assert draft["aiEdgeScore"] == 0.78
    assert draft["aiEdgeScorePct"] == 78.0
