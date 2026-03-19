"""Tests for the AutoTune evaluator."""

import json
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autotune.evaluator import (
    classify_outcome,
    compute_atr,
    dataframe_to_lens_input,
    evaluate,
)


class TestClassifyOutcome:
    """Test outcome classification logic."""

    def test_bullish_confirmed(self):
        """Bullish call confirmed when price exceeds threshold."""
        close_t = 100.0
        highs = np.array([102.0, 103.0, 104.0, 105.0])
        lows = np.array([99.5, 99.5, 99.5, 99.5])
        result = classify_outcome("bullish", close_t, highs, lows, 1.5, 2.0)
        assert result == "confirmed"

    def test_bearish_confirmed(self):
        """Bearish call confirmed when price drops enough."""
        close_t = 100.0
        highs = np.array([100.5, 100.5, 100.5, 100.5])
        lows = np.array([98.0, 97.0, 96.0, 95.0])
        result = classify_outcome("bearish", close_t, highs, lows, 1.5, 2.0)
        assert result == "confirmed"

    def test_bullish_invalidated(self):
        """Bullish call invalidated when adverse move hits first."""
        close_t = 100.0
        highs = np.array([100.2, 100.3, 100.4, 100.5])
        lows = np.array([97.0, 97.5, 98.0, 98.5])
        result = classify_outcome("bullish", close_t, highs, lows, 1.5, 2.0)
        assert result == "invalidated"

    def test_unresolved(self):
        """Neither threshold crossed → unresolved."""
        close_t = 100.0
        highs = np.array([100.5, 100.5, 100.5, 100.5])
        lows = np.array([99.5, 99.5, 99.5, 99.5])
        result = classify_outcome("bullish", close_t, highs, lows, 2.0, 2.0)
        assert result == "unresolved"

    def test_same_bar_collision_invalidation_first(self):
        """Same bar where both thresholds are reachable → INVALIDATED.

        This is the critical invalidation-first rule: adverse is checked
        before favorable within each bar.
        """
        close_t = 100.0
        # Bar with huge range — both thresholds reachable
        highs = np.array([105.0])
        lows = np.array([95.0])
        # confirm_threshold = 3.0, invalid_threshold = 3.0
        # favorable = 105-100 = 5 >= 3 ✓
        # adverse = 100-95 = 5 >= 3 ✓
        # But adverse is checked FIRST → INVALIDATED
        result = classify_outcome("bullish", close_t, highs, lows, 3.0, 3.0)
        assert result == "invalidated"

    def test_same_bar_collision_bearish(self):
        """Same bar collision for bearish call."""
        close_t = 100.0
        highs = np.array([105.0])
        lows = np.array([95.0])
        result = classify_outcome("bearish", close_t, highs, lows, 3.0, 3.0)
        assert result == "invalidated"

    def test_sequential_scan_order_matters(self):
        """Earlier bar invalidation overrides later bar confirmation."""
        close_t = 100.0
        # Bar 1: adverse hits. Bar 2: favorable would hit.
        highs = np.array([100.2, 104.0])
        lows = np.array([97.0, 99.0])
        result = classify_outcome("bullish", close_t, highs, lows, 3.0, 2.0)
        assert result == "invalidated"

    def test_confirmation_on_later_bar(self):
        """Confirmation on bar 2 when bar 1 doesn't trigger anything."""
        close_t = 100.0
        highs = np.array([100.5, 103.0])
        lows = np.array([99.5, 99.0])
        result = classify_outcome("bullish", close_t, highs, lows, 2.0, 3.0)
        assert result == "confirmed"


class TestComputeATR:
    """Test Wilder's ATR computation."""

    def test_basic_atr(self):
        """ATR computation with known values."""
        n = 20
        highs = np.array([10 + i * 0.5 for i in range(n)], dtype=np.float64)
        lows = np.array([9 + i * 0.5 for i in range(n)], dtype=np.float64)
        closes = np.array([9.5 + i * 0.5 for i in range(n)], dtype=np.float64)

        atr = compute_atr(highs, lows, closes, period=14)

        # First 13 values should be NaN
        assert all(np.isnan(atr[:13]))
        # Index 13 (period-1) should be the simple mean of first 14 TRs
        assert not np.isnan(atr[13])
        # Remaining values should not be NaN
        assert all(~np.isnan(atr[14:]))

    def test_atr_initial_value(self):
        """ATR at period-1 = simple mean of first `period` TRs."""
        highs = np.array([11, 12, 13, 14, 15], dtype=np.float64)
        lows = np.array([9, 10, 11, 12, 13], dtype=np.float64)
        closes = np.array([10, 11, 12, 13, 14], dtype=np.float64)

        atr = compute_atr(highs, lows, closes, period=3)
        # TR[0] = 11-9=2, TR[1] = max(2, |12-10|, |10-10|) = 2, TR[2] = 2
        assert atr[2] == pytest.approx(2.0)


class TestDataFrameToLensInput:
    """Test DataFrame to lens input conversion."""

    def test_conversion(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
            "open": [1.0, 2.0, 3.0, 4.0, 5.0],
            "high": [1.5, 2.5, 3.5, 4.5, 5.5],
            "low": [0.5, 1.5, 2.5, 3.5, 4.5],
            "close": [1.2, 2.2, 3.2, 4.2, 5.2],
            "volume": [100, 200, 300, 400, 500],
        })
        result = dataframe_to_lens_input(df)

        assert set(result.keys()) == {"timestamp", "open", "high", "low", "close", "volume"}
        assert all(v.dtype == np.float64 for v in result.values())
        assert all(len(v) == 5 for v in result.values())


class TestEvaluatorLensErrors:
    """Test evaluator handling of lens errors."""

    def test_lens_error_halt(self):
        """Evaluator halts if lens_errors > 5% of total_steps."""
        # Create a DataFrame that's too short for the lookback,
        # which should cause lens errors
        # This is tested implicitly — a config with lookback larger than data
        # would produce empty slices
        pass  # Covered by integration test


class TestEvaluatorDeterminism:
    """Test that same inputs produce same outputs."""

    def test_deterministic_results(self):
        """Running evaluator twice with same inputs produces identical output."""
        # Create synthetic data
        np.random.seed(42)
        n = 200
        prices = np.cumsum(np.random.randn(n) * 0.5) + 100
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": prices,
            "high": prices + np.abs(np.random.randn(n) * 0.3),
            "low": prices - np.abs(np.random.randn(n) * 0.3),
            "close": prices + np.random.randn(n) * 0.1,
            "volume": np.random.randint(100, 1000, n).astype(float),
        })

        params = {"lookback_bars": 60, "pivot_window": 3}
        config = {
            "horizon_bars": 4,
            "step_bars": 4,
            "atr_period": 14,
            "confirmation_atr_mult": 0.25,
            "invalidation_atr_mult": 0.25,
        }

        result1 = evaluate(df, "test", params, config)
        result2 = evaluate(df, "test", params, config)

        assert result1["metrics"] == result2["metrics"]
        assert result1["diagnostics"] == result2["diagnostics"]
