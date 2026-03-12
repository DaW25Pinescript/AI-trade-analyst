"""Tests for officer.summarizer — Group 5 acceptance criteria."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone

from market_data_officer.officer.contracts import CoreFeatures
from market_data_officer.officer.features import compute_core_features
from market_data_officer.officer.loader import load_all_timeframes
from market_data_officer.officer.summarizer import build_state_summary, derive_trend


class TestStateSummary:
    """T5.1 — All state summary fields present."""

    def test_all_fields_present(self, hot_packages_dir):
        timeframes = load_all_timeframes("EURUSD", hot_packages_dir)
        df_1h = timeframes["1h"]
        features = compute_core_features(df_1h)
        summary = build_state_summary(features, timeframes)

        assert summary.trend_1h in ("bullish", "bearish", "neutral")
        assert summary.trend_4h in ("bullish", "bearish", "neutral")
        assert summary.trend_1d in ("bullish", "bearish", "neutral")
        assert summary.volatility_regime in ("low", "normal", "expanding")
        assert summary.momentum_state in ("expanding", "contracting", "flat")
        assert summary.session_context in ("asian", "london", "new_york", "overlap")
        assert summary.data_quality in ("validated", "partial", "stale", "unverified")


class TestTrendDerivation:
    """T5.2 — Trend derivation is consistent with MA relationship."""

    def test_bullish_trend(self):
        """If close > ma_50 > ma_200, trend must be bullish."""
        rng = np.random.RandomState(100)
        # Create a clearly bullish dataset: uptrend so close > ma50 > ma200
        n = 250
        close = 1.0 + np.linspace(0, 0.05, n) + rng.normal(0, 0.001, n)
        df = pd.DataFrame({
            "open": close - 0.0001,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": rng.uniform(100, 1000, n),
        })
        trend = derive_trend(df)
        # With a consistent uptrend, close > ma50 > ma200
        assert trend == "bullish"

    def test_bearish_trend(self):
        """If close < ma_50 < ma_200, trend must be bearish."""
        rng = np.random.RandomState(101)
        n = 250
        close = 1.1 - np.linspace(0, 0.05, n) + rng.normal(0, 0.001, n)
        df = pd.DataFrame({
            "open": close + 0.0001,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "volume": rng.uniform(100, 1000, n),
        })
        trend = derive_trend(df)
        assert trend == "bearish"

    def test_neutral_insufficient_data(self):
        """Less than 200 bars should return neutral."""
        df = pd.DataFrame({
            "close": [1.0] * 50,
            "open": [1.0] * 50,
            "high": [1.001] * 50,
            "low": [0.999] * 50,
            "volume": [100] * 50,
        })
        assert derive_trend(df) == "neutral"
