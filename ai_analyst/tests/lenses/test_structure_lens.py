"""Tests for StructureLens — deterministic fixture-based tests only.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Sections 4.2, 4.3
Acceptance criteria: AC-1, AC-4
"""

import pytest
import numpy as np

from ai_analyst.lenses.structure import StructureLens
from ai_analyst.lenses.base import LensOutput


# ── Fixtures ────────────────────────────────────────────────────────────────


def make_bullish_price_data(n=120):
    """Clean uptrend: HH/HL structure, breakout above resistance."""
    np.random.seed(42)
    closes = np.linspace(1900, 2100, n) + np.random.normal(0, 5, n)
    highs = closes + np.abs(np.random.normal(0, 8, n))
    lows = closes - np.abs(np.random.normal(0, 8, n))
    return {"close": closes, "high": highs, "low": lows}


def make_bearish_price_data(n=120):
    """Clean downtrend: LH/LL structure."""
    np.random.seed(42)
    closes = np.linspace(2100, 1900, n) + np.random.normal(0, 5, n)
    highs = closes + np.abs(np.random.normal(0, 8, n))
    lows = closes - np.abs(np.random.normal(0, 8, n))
    return {"close": closes, "high": highs, "low": lows}


def make_noisy_price_data(n=120):
    """Choppy/ranging data — should produce mixed structure."""
    np.random.seed(99)
    closes = 2000 + np.random.normal(0, 20, n)
    highs = closes + np.abs(np.random.normal(0, 10, n))
    lows = closes - np.abs(np.random.normal(0, 10, n))
    return {"close": closes, "high": highs, "low": lows}


def make_insufficient_data(n=5):
    """Too few bars for swing detection."""
    closes = np.array([2000.0, 2010.0, 2005.0, 2015.0, 2020.0])
    highs = closes + 5
    lows = closes - 5
    return {"close": closes, "high": highs, "low": lows}


DEFAULT_CONFIG = {
    "timeframe": "1H",
    "lookback_bars": 100,
    "swing_sensitivity": "medium",
    "level_method": "pivot",
    "breakout_rule": "close",
}


# ── AC-1: Valid schema — all fields present ─────────────────────────────────


class TestStructureLensOutputSchema:
    def test_returns_lens_output_object(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result, LensOutput)

    def test_status_is_success_on_valid_data(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.error is None

    def test_data_contains_all_required_top_level_fields(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        required = [
            "timeframe", "levels", "distance", "swings",
            "trend", "breakout", "rejection",
        ]
        for field in required:
            assert field in result.data, f"Missing required field: {field}"

    def test_levels_always_present_even_if_null(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "support" in result.data["levels"]
        assert "resistance" in result.data["levels"]

    def test_distance_fields_always_present(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "to_support" in result.data["distance"]
        assert "to_resistance" in result.data["distance"]

    def test_swings_fields_always_present(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "recent_high" in result.data["swings"]
        assert "recent_low" in result.data["swings"]

    def test_trend_fields_use_allowed_values(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["trend"]["local_direction"] in {
            "bullish", "bearish", "ranging",
        }
        assert result.data["trend"]["structure_state"] in {
            "HH_HL", "LH_LL", "mixed",
        }

    def test_breakout_status_uses_allowed_values(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["breakout"]["status"] in {
            "none", "breakout_up", "breakout_down", "holding", "failed",
        }

    def test_breakout_level_broken_uses_allowed_values(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["breakout"]["level_broken"] in {
            "support", "resistance", None,
        }

    def test_rejection_fields_are_boolean(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result.data["rejection"]["at_support"], bool)
        assert isinstance(result.data["rejection"]["at_resistance"], bool)

    def test_timeframe_matches_config(self):
        lens = StructureLens()
        config = {**DEFAULT_CONFIG, "timeframe": "4H"}
        result = lens.run(make_bullish_price_data(), config)
        assert result.data["timeframe"] == "4H"
        assert result.timeframe == "4H"

    def test_lens_id_is_structure(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.lens_id == "structure"

    def test_version_is_v1(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.version == "v1.0"


# ── AC-4: Clean failure — no partial data ───────────────────────────────────


class TestStructureLensFailureBehavior:
    def test_returns_failed_status_on_empty_data(self):
        """Lens must return status='failed', not raise, on empty arrays."""
        lens = StructureLens()
        empty = {
            "close": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
        }
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.status == "failed"
        assert result.data is None
        assert result.error is not None
        assert len(result.error) > 0

    def test_never_raises_exception_on_empty(self):
        """Lens contract: never raise — always return LensOutput."""
        lens = StructureLens()
        empty = {
            "close": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
        }
        try:
            result = lens.run(empty, DEFAULT_CONFIG)
            assert isinstance(result, LensOutput)
        except Exception as exc:
            pytest.fail(f"Lens raised instead of returning failed LensOutput: {exc}")

    def test_never_raises_on_missing_keys(self):
        """Missing price_data keys should produce a clean failure."""
        lens = StructureLens()
        try:
            result = lens.run({}, DEFAULT_CONFIG)
            assert result.status == "failed"
            assert result.data is None
        except Exception as exc:
            pytest.fail(f"Lens raised on missing keys: {exc}")

    def test_partial_data_never_returned(self):
        """On failure: data must be None, not a partial dict."""
        lens = StructureLens()
        empty = {
            "close": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
        }
        result = lens.run(empty, DEFAULT_CONFIG)
        if result.status == "failed":
            assert result.data is None, "Partial data returned on failure"

    def test_lens_id_present_on_failure(self):
        """lens_id must be correct even on failure."""
        lens = StructureLens()
        empty = {
            "close": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
        }
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.lens_id == "structure"

    def test_version_present_on_failure(self):
        lens = StructureLens()
        empty = {
            "close": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
        }
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.version == "v1.0"

    def test_timeframe_present_on_failure(self):
        lens = StructureLens()
        empty = {
            "close": np.array([]),
            "high": np.array([]),
            "low": np.array([]),
        }
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.timeframe == "1H"

    def test_insufficient_bars_does_not_crash(self):
        """Very few bars: either succeed with nulls or fail cleanly."""
        lens = StructureLens()
        result = lens.run(make_insufficient_data(), DEFAULT_CONFIG)
        assert result.status in {"success", "failed"}
        if result.status == "failed":
            assert result.data is None
            assert result.error is not None


# ── AC-1 extended: Interpretation contract ──────────────────────────────────


class TestStructureLensInterpretation:
    def test_bullish_data_produces_bullish_or_ranging_direction(self):
        """Strong uptrend should classify as bullish or ranging — not bearish."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["trend"]["local_direction"] in {"bullish", "ranging"}

    def test_bearish_data_produces_bearish_or_ranging_direction(self):
        """Strong downtrend should classify as bearish or ranging — not bullish."""
        lens = StructureLens()
        result = lens.run(make_bearish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["trend"]["local_direction"] in {"bearish", "ranging"}

    def test_noisy_data_produces_valid_structure_state(self):
        """Choppy data should produce a valid structure_state."""
        lens = StructureLens()
        result = lens.run(make_noisy_price_data(), DEFAULT_CONFIG)
        if result.status == "success":
            assert result.data["trend"]["structure_state"] in {
                "HH_HL", "LH_LL", "mixed",
            }

    def test_support_is_below_current_price(self):
        """Support must always be below current price when present."""
        lens = StructureLens()
        data = make_bullish_price_data()
        result = lens.run(data, DEFAULT_CONFIG)
        if result.status == "success" and result.data["levels"]["support"] is not None:
            current = float(data["close"][-1])
            assert result.data["levels"]["support"] <= current

    def test_resistance_is_above_current_price(self):
        """Resistance must always be above current price when present."""
        lens = StructureLens()
        data = make_bullish_price_data()
        result = lens.run(data, DEFAULT_CONFIG)
        if result.status == "success" and result.data["levels"]["resistance"] is not None:
            current = float(data["close"][-1])
            assert result.data["levels"]["resistance"] >= current

    def test_distance_to_support_is_non_negative(self):
        """Distance to support must be non-negative (price above support)."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        if result.status == "success" and result.data["distance"]["to_support"] is not None:
            assert result.data["distance"]["to_support"] >= 0

    def test_distance_to_resistance_is_non_negative(self):
        """Distance to resistance must be non-negative (price below resistance)."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        if result.status == "success" and result.data["distance"]["to_resistance"] is not None:
            assert result.data["distance"]["to_resistance"] >= 0


# ── Configuration sensitivity ───────────────────────────────────────────────


class TestStructureLensConfiguration:
    def test_different_sensitivity_produces_valid_output(self):
        """All sensitivity settings must produce valid output."""
        lens = StructureLens()
        for sensitivity in ["low", "medium", "high"]:
            config = {**DEFAULT_CONFIG, "swing_sensitivity": sensitivity}
            result = lens.run(make_bullish_price_data(), config)
            assert result.status == "success", (
                f"Failed on sensitivity={sensitivity}: {result.error}"
            )

    def test_small_lookback_produces_valid_output(self):
        """Even minimal lookback must produce valid or clean failure."""
        lens = StructureLens()
        config = {**DEFAULT_CONFIG, "lookback_bars": 20}
        result = lens.run(make_bullish_price_data(), config)
        assert result.status in {"success", "failed"}
        if result.status == "success":
            assert "timeframe" in result.data
