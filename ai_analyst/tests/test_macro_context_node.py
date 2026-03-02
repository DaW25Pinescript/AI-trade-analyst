"""
Unit tests for the macro_context_node graph node.

These tests verify:
  1. The node populates state["macro_context"] when the scheduler returns a context.
  2. The node sets macro_context=None without raising when the scheduler returns None.
  3. The node sets macro_context=None without raising when the scheduler throws.
  4. The node passes the correct instrument to the scheduler.
  5. The node handles the case where macro_risk_officer is not importable.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from macro_risk_officer.core.models import AssetPressure, MacroContext
from ai_analyst.models.ground_truth import (
    GroundTruthPacket,
    MarketContext,
    RiskConstraints,
    ScreenshotMetadata,
)
from ai_analyst.models.lens_config import LensConfig


pytestmark = pytest.mark.asyncio


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_state(instrument: str = "XAUUSD") -> dict:
    gt = GroundTruthPacket(
        instrument=instrument,
        session="NY",
        timeframes=["H4"],
        charts={"H4": "base64"},
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")
        ],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000.0),
    )
    return {
        "ground_truth": gt,
        "lens_config": LensConfig(),
        "analyst_outputs": [],
        "overlay_delta_reports": [],
        "macro_context": None,
        "final_verdict": None,
        "error": None,
    }


def _sample_macro_context() -> MacroContext:
    return MacroContext(
        regime="risk_off",
        vol_bias="expanding",
        asset_pressure=AssetPressure(USD=0.7, GOLD=0.5, SPX=-0.6),
        conflict_score=-0.45,
        confidence=0.72,
        time_horizon_days=45,
        explanation=["Hawkish Fed surprise → USD supported, GOLD pressured."],
        active_event_ids=["finnhub-fed-2026-03"],
    )


# ── Tests ──────────────────────────────────────────────────────────────────


class TestMacroContextNode:
    async def test_populates_state_when_scheduler_returns_context(self):
        """Node stores the returned MacroContext in state["macro_context"]."""
        from ai_analyst.graph import macro_context_node as module
        ctx = _sample_macro_context()
        mock_scheduler = MagicMock()
        mock_scheduler.get_context.return_value = ctx

        with patch.object(module, "_scheduler", mock_scheduler):
            state = _make_state()
            result = await module.macro_context_node(state)

        assert result["macro_context"] is ctx
        mock_scheduler.get_context.assert_called_once_with(instrument="XAUUSD")

    async def test_passes_instrument_to_scheduler(self):
        """Node extracts instrument from ground_truth and passes it to get_context."""
        from ai_analyst.graph import macro_context_node as module
        mock_scheduler = MagicMock()
        mock_scheduler.get_context.return_value = None

        with patch.object(module, "_scheduler", mock_scheduler):
            state = _make_state(instrument="NAS100")
            await module.macro_context_node(state)

        mock_scheduler.get_context.assert_called_once_with(instrument="NAS100")

    async def test_sets_none_when_scheduler_returns_none(self):
        """Node sets macro_context=None (without raising) when scheduler returns None."""
        from ai_analyst.graph import macro_context_node as module
        mock_scheduler = MagicMock()
        mock_scheduler.get_context.return_value = None

        with patch.object(module, "_scheduler", mock_scheduler):
            state = _make_state()
            result = await module.macro_context_node(state)

        assert result["macro_context"] is None

    async def test_does_not_raise_when_scheduler_throws(self):
        """Node catches scheduler exceptions and sets macro_context=None."""
        from ai_analyst.graph import macro_context_node as module
        mock_scheduler = MagicMock()
        mock_scheduler.get_context.side_effect = RuntimeError("network failure")

        with patch.object(module, "_scheduler", mock_scheduler):
            state = _make_state()
            result = await module.macro_context_node(state)

        assert result["macro_context"] is None

    async def test_does_not_raise_when_scheduler_is_none(self):
        """Node handles _scheduler=None (import failure) without raising."""
        from ai_analyst.graph import macro_context_node as module

        with patch.object(module, "_scheduler", None):
            # Also patch _get_scheduler to return None (simulating import failure)
            with patch.object(module, "_get_scheduler", return_value=None):
                state = _make_state()
                result = await module.macro_context_node(state)

        assert result["macro_context"] is None

    async def test_other_state_keys_unchanged(self):
        """Node must not mutate any state keys other than macro_context."""
        from ai_analyst.graph import macro_context_node as module
        ctx = _sample_macro_context()
        mock_scheduler = MagicMock()
        mock_scheduler.get_context.return_value = ctx

        with patch.object(module, "_scheduler", mock_scheduler):
            state = _make_state()
            original_gt = state["ground_truth"]
            result = await module.macro_context_node(state)

        assert result["ground_truth"] is original_gt
        assert result["analyst_outputs"] == []
        assert result["final_verdict"] is None
