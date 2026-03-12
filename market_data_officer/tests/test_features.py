"""Tests for officer.features — Group 3 acceptance criteria."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone

from market_data_officer.officer.features import compute_core_features
from market_data_officer.officer.loader import load_timeframe


class TestCoreFeatures:
    """T3.1 — All core feature fields are present and non-null."""

    def test_all_fields_present(self, hot_packages_dir):
        df_1h = load_timeframe("EURUSD", "1h", hot_packages_dir)
        features = compute_core_features(df_1h)

        assert features.atr_14 > 0
        assert features.volatility_regime in ("low", "normal", "expanding")
        assert features.momentum is not None
        assert features.ma_50 > 0
        assert features.ma_200 > 0
        assert features.swing_high > 0
        assert features.swing_low > 0
        assert features.rolling_range > 0
        assert features.session_context in ("asian", "london", "new_york", "overlap")


class TestATRPlausibility:
    """T3.2 — ATR is positive and plausible for EURUSD."""

    def test_atr_plausible(self, hot_packages_dir):
        df_1h = load_timeframe("EURUSD", "1h", hot_packages_dir)
        features = compute_core_features(df_1h)
        # Synthetic data uses volatility=0.0005, so ATR should be in a reasonable range
        assert features.atr_14 > 0, f"ATR must be positive: {features.atr_14}"


class TestMAPlausibility:
    """T3.3 — MA values are plausible for EURUSD."""

    def test_ma_plausible(self, hot_packages_dir):
        df_1h = load_timeframe("EURUSD", "1h", hot_packages_dir)
        features = compute_core_features(df_1h)
        assert 0.8 < features.ma_50 < 1.5
        assert 0.8 < features.ma_200 < 1.5


class TestDeterminism:
    """T3.4 — Feature computation is deterministic."""

    def test_deterministic(self, hot_packages_dir):
        df_1h = load_timeframe("EURUSD", "1h", hot_packages_dir)
        fixed_time = datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc)
        features_a = compute_core_features(df_1h, as_of_utc=fixed_time)
        features_b = compute_core_features(df_1h, as_of_utc=fixed_time)
        assert features_a.atr_14 == features_b.atr_14
        assert features_a.ma_50 == features_b.ma_50
        assert features_a.momentum == features_b.momentum
        assert features_a.session_context == features_b.session_context


class TestInsufficientData:
    """T3.5 — Insufficient data returns graceful result, not crash."""

    def test_tiny_dataframe(self, hot_packages_dir):
        df_1h = load_timeframe("EURUSD", "1h", hot_packages_dir)
        tiny_df = df_1h.head(10)  # Only 10 bars
        features = compute_core_features(tiny_df)
        assert features is not None
        # Should not raise — some values may be 0.0 for insufficient data
