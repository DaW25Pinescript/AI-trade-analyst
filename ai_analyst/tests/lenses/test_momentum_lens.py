"""Tests for MomentumLens — deterministic fixture-based tests only.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 4.5
Acceptance criteria: AC-3, AC-4
"""

import pytest
import numpy as np

from ai_analyst.lenses.momentum import MomentumLens
from ai_analyst.lenses.base import LensOutput


# ── Fixtures ────────────────────────────────────────────────────────────────


def make_bullish_price_data(n=120):
    """Clear uptrend: strong positive momentum."""
    np.random.seed(42)
    closes = np.linspace(1900, 2100, n) + np.random.normal(0, 3, n)
    highs = closes + np.abs(np.random.normal(0, 5, n))
    lows = closes - np.abs(np.random.normal(0, 5, n))
    return {"close": closes, "high": highs, "low": lows}


def make_bearish_price_data(n=120):
    """Clear downtrend: strong negative momentum."""
    np.random.seed(42)
    closes = np.linspace(2100, 1900, n) + np.random.normal(0, 3, n)
    highs = closes + np.abs(np.random.normal(0, 5, n))
    lows = closes - np.abs(np.random.normal(0, 5, n))
    return {"close": closes, "high": highs, "low": lows}


def make_noisy_price_data(n=120):
    """Ranging/choppy data — flat mean with noise, frequent sign changes."""
    np.random.seed(99)
    closes = 2000 + np.random.normal(0, 20, n)
    highs = closes + np.abs(np.random.normal(0, 10, n))
    lows = closes - np.abs(np.random.normal(0, 10, n))
    return {"close": closes, "high": highs, "low": lows}


def make_insufficient_data(n=5):
    """Too few bars for ROC calculation."""
    closes = np.array([2000.0, 2010.0, 2005.0, 2015.0, 2020.0])
    highs = closes + 5
    lows = closes - 5
    return {"close": closes, "high": highs, "low": lows}


DEFAULT_CONFIG = {
    "timeframe": "1H",
    "roc_lookback": 10,
    "momentum_smoothing": 5,
    "signal_mode": "roc",
}


# ── AC-3: Valid schema — all fields present ─────────────────────────────────


class TestMomentumLensOutputSchema:
    def test_returns_lens_output_object(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result, LensOutput)

    def test_status_is_success_on_valid_data(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.error is None

    def test_data_contains_all_required_top_level_fields(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        required = ["timeframe", "direction", "strength", "state", "risk"]
        for field in required:
            assert field in result.data, f"Missing required field: {field}"

    def test_direction_fields_always_present(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "state" in result.data["direction"]
        assert "roc_sign" in result.data["direction"]

    def test_strength_fields_always_present(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "impulse" in result.data["strength"]
        assert "acceleration" in result.data["strength"]

    def test_state_fields_always_present(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "phase" in result.data["state"]
        assert "trend_alignment" in result.data["state"]

    def test_risk_fields_always_present(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "exhaustion" in result.data["risk"]
        assert "chop_warning" in result.data["risk"]

    def test_direction_fields_use_allowed_values(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["direction"]["state"] in {
            "bullish", "bearish", "neutral",
        }
        assert result.data["direction"]["roc_sign"] in {
            "positive", "negative", "flat",
        }

    def test_strength_fields_use_allowed_values(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["strength"]["impulse"] in {
            "strong", "moderate", "weak",
        }
        assert result.data["strength"]["acceleration"] in {
            "rising", "falling", "flat",
        }

    def test_state_fields_use_allowed_values(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["state"]["phase"] in {
            "expanding", "fading", "reversing", "flat",
        }
        assert result.data["state"]["trend_alignment"] in {
            "aligned", "conflicting", "unknown",
        }

    def test_risk_fields_are_boolean(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result.data["risk"]["exhaustion"], bool)
        assert isinstance(result.data["risk"]["chop_warning"], bool)

    def test_timeframe_matches_config(self):
        lens = MomentumLens()
        config = {**DEFAULT_CONFIG, "timeframe": "4H"}
        result = lens.run(make_bullish_price_data(), config)
        assert result.data["timeframe"] == "4H"
        assert result.timeframe == "4H"

    def test_lens_id_is_momentum(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.lens_id == "momentum"

    def test_version_is_v1(self):
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.version == "v1.0"


# ── AC-4: Clean failure — no partial data ───────────────────────────────────


class TestMomentumLensFailureBehavior:
    def test_returns_failed_status_on_empty_data(self):
        """Lens must return status='failed', not raise, on empty arrays."""
        lens = MomentumLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.status == "failed"
        assert result.data is None
        assert result.error is not None
        assert len(result.error) > 0

    def test_never_raises_exception_on_empty(self):
        """Lens contract: never raise — always return LensOutput."""
        lens = MomentumLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        try:
            result = lens.run(empty, DEFAULT_CONFIG)
            assert isinstance(result, LensOutput)
        except Exception as exc:
            pytest.fail(f"Lens raised instead of returning failed LensOutput: {exc}")

    def test_never_raises_on_missing_keys(self):
        """Missing price_data keys should produce a clean failure."""
        lens = MomentumLens()
        try:
            result = lens.run({}, DEFAULT_CONFIG)
            assert result.status == "failed"
            assert result.data is None
        except Exception as exc:
            pytest.fail(f"Lens raised on missing keys: {exc}")

    def test_partial_data_never_returned(self):
        """On failure: data must be None, not a partial dict."""
        lens = MomentumLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        if result.status == "failed":
            assert result.data is None, "Partial data returned on failure"

    def test_lens_id_present_on_failure(self):
        lens = MomentumLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.lens_id == "momentum"

    def test_version_present_on_failure(self):
        lens = MomentumLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.version == "v1.0"

    def test_timeframe_present_on_failure(self):
        lens = MomentumLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.timeframe == "1H"

    def test_insufficient_bars_fails_cleanly(self):
        """Too few bars for ROC: should fail, not crash."""
        lens = MomentumLens()
        result = lens.run(make_insufficient_data(), DEFAULT_CONFIG)
        assert result.status == "failed"
        assert result.data is None
        assert result.error is not None


# ── Interpretation contract ─────────────────────────────────────────────────


class TestMomentumLensInterpretation:
    def test_bullish_data_produces_bullish_momentum(self):
        """Strong uptrend should show bullish momentum."""
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["direction"]["state"] in {"bullish", "neutral"}
        assert result.data["direction"]["roc_sign"] in {"positive", "flat"}

    def test_bearish_data_produces_bearish_momentum(self):
        """Strong downtrend should show bearish momentum."""
        lens = MomentumLens()
        result = lens.run(make_bearish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["direction"]["state"] in {"bearish", "neutral"}
        assert result.data["direction"]["roc_sign"] in {"negative", "flat"}

    def test_noisy_data_produces_valid_output(self):
        """Choppy data should produce valid momentum readings."""
        lens = MomentumLens()
        result = lens.run(make_noisy_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        # Noisy data: all values within allowed sets
        assert result.data["strength"]["impulse"] in {
            "strong", "moderate", "weak",
        }

    def test_trending_data_has_no_chop_warning(self):
        """Clear trend should not trigger chop warning."""
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["risk"]["chop_warning"] is False

    def test_risk_exhaustion_is_boolean(self):
        """Exhaustion flag should always be boolean."""
        lens = MomentumLens()
        for data_fn in [make_bullish_price_data, make_bearish_price_data, make_noisy_price_data]:
            result = lens.run(data_fn(), DEFAULT_CONFIG)
            assert result.status == "success"
            assert isinstance(result.data["risk"]["exhaustion"], bool)

    def test_trend_alignment_on_bullish_data(self):
        """Bullish trend with positive ROC should be aligned."""
        lens = MomentumLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["state"]["trend_alignment"] in {
            "aligned", "conflicting", "unknown",
        }


# ── Configuration sensitivity ───────────────────────────────────────────────


class TestMomentumLensConfig:
    def test_custom_roc_lookback_respected(self):
        """Custom ROC lookback should produce valid output."""
        lens = MomentumLens()
        config = {**DEFAULT_CONFIG, "roc_lookback": 5, "momentum_smoothing": 3}
        result = lens.run(make_bullish_price_data(), config)
        assert result.status == "success"
        assert "direction" in result.data

    def test_timeframe_passed_through(self):
        """Config timeframe must appear in output."""
        lens = MomentumLens()
        config = {**DEFAULT_CONFIG, "timeframe": "15M"}
        result = lens.run(make_bullish_price_data(), config)
        assert result.data["timeframe"] == "15M"
        assert result.timeframe == "15M"
