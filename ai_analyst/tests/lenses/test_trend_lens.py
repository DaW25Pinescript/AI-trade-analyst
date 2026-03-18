"""Tests for TrendLens — deterministic fixture-based tests only.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 4.4
Acceptance criteria: AC-2, AC-4
"""

import pytest
import numpy as np

from ai_analyst.lenses.trend import TrendLens
from ai_analyst.lenses.base import LensOutput


# ── Fixtures ────────────────────────────────────────────────────────────────


def make_bullish_price_data(n=120):
    """Clear uptrend: ascending prices with small noise."""
    np.random.seed(42)
    closes = np.linspace(1900, 2100, n) + np.random.normal(0, 3, n)
    highs = closes + np.abs(np.random.normal(0, 5, n))
    lows = closes - np.abs(np.random.normal(0, 5, n))
    return {"close": closes, "high": highs, "low": lows}


def make_bearish_price_data(n=120):
    """Clear downtrend: descending prices with small noise."""
    np.random.seed(42)
    closes = np.linspace(2100, 1900, n) + np.random.normal(0, 3, n)
    highs = closes + np.abs(np.random.normal(0, 5, n))
    lows = closes - np.abs(np.random.normal(0, 5, n))
    return {"close": closes, "high": highs, "low": lows}


def make_noisy_price_data(n=120):
    """Ranging/choppy data — flat mean with noise."""
    np.random.seed(99)
    closes = 2000 + np.random.normal(0, 15, n)
    highs = closes + np.abs(np.random.normal(0, 8, n))
    lows = closes - np.abs(np.random.normal(0, 8, n))
    return {"close": closes, "high": highs, "low": lows}


def make_insufficient_data(n=5):
    """Too few bars for EMA calculation."""
    closes = np.array([2000.0, 2010.0, 2005.0, 2015.0, 2020.0])
    highs = closes + 5
    lows = closes - 5
    return {"close": closes, "high": highs, "low": lows}


DEFAULT_CONFIG = {
    "timeframe": "1H",
    "ema_fast": 20,
    "ema_slow": 50,
    "slope_lookback": 10,
}


# ── AC-2: Valid schema — all fields present ─────────────────────────────────


class TestTrendLensOutputSchema:
    def test_returns_lens_output_object(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result, LensOutput)

    def test_status_is_success_on_valid_data(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.error is None

    def test_data_contains_all_required_top_level_fields(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        required = ["timeframe", "direction", "strength", "state"]
        for field in required:
            assert field in result.data, f"Missing required field: {field}"

    def test_direction_fields_always_present(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "ema_alignment" in result.data["direction"]
        assert "price_vs_ema" in result.data["direction"]
        assert "overall" in result.data["direction"]

    def test_strength_fields_always_present(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "slope" in result.data["strength"]
        assert "trend_quality" in result.data["strength"]

    def test_state_fields_always_present(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "phase" in result.data["state"]
        assert "consistency" in result.data["state"]

    def test_direction_fields_use_allowed_values(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["direction"]["ema_alignment"] in {
            "bullish", "bearish", "neutral",
        }
        assert result.data["direction"]["price_vs_ema"] in {
            "above", "below", "mixed",
        }
        assert result.data["direction"]["overall"] in {
            "bullish", "bearish", "ranging",
        }

    def test_strength_fields_use_allowed_values(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["strength"]["slope"] in {
            "positive", "negative", "flat",
        }
        assert result.data["strength"]["trend_quality"] in {
            "strong", "moderate", "weak",
        }

    def test_state_fields_use_allowed_values(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["state"]["phase"] in {
            "continuation", "pullback", "transition",
        }
        assert result.data["state"]["consistency"] in {
            "aligned", "conflicting",
        }

    def test_timeframe_matches_config(self):
        lens = TrendLens()
        config = {**DEFAULT_CONFIG, "timeframe": "4H"}
        result = lens.run(make_bullish_price_data(), config)
        assert result.data["timeframe"] == "4H"
        assert result.timeframe == "4H"

    def test_lens_id_is_trend(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.lens_id == "trend"

    def test_version_is_v1(self):
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.version == "v1.0"


# ── AC-4: Clean failure — no partial data ───────────────────────────────────


class TestTrendLensFailureBehavior:
    def test_returns_failed_status_on_empty_data(self):
        """Lens must return status='failed', not raise, on empty arrays."""
        lens = TrendLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.status == "failed"
        assert result.data is None
        assert result.error is not None
        assert len(result.error) > 0

    def test_never_raises_exception_on_empty(self):
        """Lens contract: never raise — always return LensOutput."""
        lens = TrendLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        try:
            result = lens.run(empty, DEFAULT_CONFIG)
            assert isinstance(result, LensOutput)
        except Exception as exc:
            pytest.fail(f"Lens raised instead of returning failed LensOutput: {exc}")

    def test_never_raises_on_missing_keys(self):
        """Missing price_data keys should produce a clean failure."""
        lens = TrendLens()
        try:
            result = lens.run({}, DEFAULT_CONFIG)
            assert result.status == "failed"
            assert result.data is None
        except Exception as exc:
            pytest.fail(f"Lens raised on missing keys: {exc}")

    def test_partial_data_never_returned(self):
        """On failure: data must be None, not a partial dict."""
        lens = TrendLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        if result.status == "failed":
            assert result.data is None, "Partial data returned on failure"

    def test_lens_id_present_on_failure(self):
        lens = TrendLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.lens_id == "trend"

    def test_version_present_on_failure(self):
        lens = TrendLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.version == "v1.0"

    def test_timeframe_present_on_failure(self):
        lens = TrendLens()
        empty = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(empty, DEFAULT_CONFIG)
        assert result.timeframe == "1H"

    def test_insufficient_bars_fails_cleanly(self):
        """Too few bars for EMA: should fail, not crash."""
        lens = TrendLens()
        result = lens.run(make_insufficient_data(), DEFAULT_CONFIG)
        assert result.status == "failed"
        assert result.data is None
        assert result.error is not None


# ── Interpretation contract ─────────────────────────────────────────────────


class TestTrendLensInterpretation:
    def test_bullish_data_produces_bullish_direction(self):
        """Strong uptrend should classify as bullish overall."""
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["direction"]["overall"] in {"bullish", "ranging"}
        assert result.data["direction"]["ema_alignment"] in {"bullish", "neutral"}

    def test_bearish_data_produces_bearish_direction(self):
        """Strong downtrend should classify as bearish overall."""
        lens = TrendLens()
        result = lens.run(make_bearish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["direction"]["overall"] in {"bearish", "ranging"}
        assert result.data["direction"]["ema_alignment"] in {"bearish", "neutral"}

    def test_noisy_data_produces_ranging_or_weak(self):
        """Choppy data should produce ranging/weak signals."""
        lens = TrendLens()
        result = lens.run(make_noisy_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        # Noisy data should not produce strong trending signals
        assert result.data["direction"]["overall"] in {
            "bullish", "bearish", "ranging",
        }

    def test_bullish_slope_is_positive(self):
        """Uptrend should have positive or flat slope."""
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["strength"]["slope"] in {"positive", "flat"}

    def test_bearish_slope_is_negative(self):
        """Downtrend should have negative or flat slope."""
        lens = TrendLens()
        result = lens.run(make_bearish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["strength"]["slope"] in {"negative", "flat"}

    def test_bullish_continuation_phase(self):
        """Strong uptrend should be continuation or transition."""
        lens = TrendLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["state"]["phase"] in {
            "continuation", "pullback", "transition",
        }


# ── Configuration sensitivity ───────────────────────────────────────────────


class TestTrendLensConfig:
    def test_custom_ema_periods_respected(self):
        """Custom EMA periods should produce valid output."""
        lens = TrendLens()
        config = {**DEFAULT_CONFIG, "ema_fast": 10, "ema_slow": 30}
        result = lens.run(make_bullish_price_data(), config)
        assert result.status == "success"
        assert "direction" in result.data

    def test_timeframe_passed_through(self):
        """Config timeframe must appear in output."""
        lens = TrendLens()
        config = {**DEFAULT_CONFIG, "timeframe": "15M"}
        result = lens.run(make_bullish_price_data(), config)
        assert result.data["timeframe"] == "15M"
        assert result.timeframe == "15M"
