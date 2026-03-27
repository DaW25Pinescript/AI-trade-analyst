"""Phase 5 — PriceStore loader integration tests.

All tests mock PriceStoreAdapter. No network, no real Parquet reads.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from market_data_officer.officer.loader import (
    _get_pricestore_adapter,
    get_expected_timeframes,
    load_all_timeframes,
    load_from_pricestore,
)
from market_data_officer.officer.quality import _compute_staleness


def _make_ohlcv_df(rows: int = 10, base_ts: datetime = None) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame with UTC DatetimeIndex."""
    if base_ts is None:
        base_ts = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    idx = pd.DatetimeIndex(
        [base_ts + timedelta(hours=i) for i in range(rows)], tz="UTC"
    )
    return pd.DataFrame(
        {
            "open": [1.1 + i * 0.001 for i in range(rows)],
            "high": [1.11 + i * 0.001 for i in range(rows)],
            "low": [1.09 + i * 0.001 for i in range(rows)],
            "close": [1.105 + i * 0.001 for i in range(rows)],
            "volume": [100.0 + i for i in range(rows)],
        },
        index=idx,
    )


# -- Test 1: get_expected_timeframes for FX excludes 1m --


def test_expected_timeframes_fx_excludes_1m():
    """FX instruments get 5m, 15m, 1h, 4h, 1d — no 1m."""
    tfs = get_expected_timeframes("EURUSD")
    assert "1m" not in tfs
    assert "5m" in tfs
    assert "1h" in tfs
    assert "1d" in tfs


# -- Test 2: get_expected_timeframes for metals excludes 1m and 5m --


def test_expected_timeframes_metals():
    """Metals get 15m, 1h, 4h, 1d — no 1m or 5m."""
    tfs = get_expected_timeframes("XAUUSD")
    assert "1m" not in tfs
    assert "5m" not in tfs
    assert "15m" in tfs
    assert "1d" in tfs


# -- Test 3: _get_pricestore_adapter returns None when TDP not available --


def test_adapter_returns_none_when_tdp_unavailable():
    """If TDP import fails and TDP_SRC_DIR not set, returns None."""
    with patch.dict(os.environ, {"TDP_SRC_DIR": "", "TDP_DATA_DIR": ""}, clear=False):
        with patch("builtins.__import__", side_effect=ImportError("no pipeline")):
            result = _get_pricestore_adapter()
    assert result is None


# -- Test 4: load_from_pricestore calls adapter correctly --


def test_load_from_pricestore_calls_adapter():
    """load_from_pricestore delegates to PriceStoreAdapter.get_timeframes."""
    mock_adapter = MagicMock()
    mock_adapter.get_timeframes.return_value = {
        "5m": _make_ohlcv_df(20),
        "15m": _make_ohlcv_df(10),
        "1h": _make_ohlcv_df(5),
        "4h": _make_ohlcv_df(3),
        "1d": _make_ohlcv_df(1),
    }

    with patch("market_data_officer.officer.loader._get_pricestore_adapter", return_value=mock_adapter):
        result = load_from_pricestore("EURUSD")

    assert len(result) == 5
    assert "5m" in result
    assert "1h" in result
    mock_adapter.get_timeframes.assert_called_once()


# -- Test 5: load_all_timeframes uses PriceStore when configured --


def test_load_all_timeframes_uses_pricestore():
    """Default use_pricestore=True path calls load_from_pricestore."""
    mock_adapter = MagicMock()
    mock_adapter.get_timeframes.return_value = {
        "5m": _make_ohlcv_df(20),
        "15m": _make_ohlcv_df(10),
        "1h": _make_ohlcv_df(5),
        "4h": _make_ohlcv_df(3),
        "1d": _make_ohlcv_df(1),
    }

    with patch("market_data_officer.officer.loader._get_pricestore_adapter", return_value=mock_adapter):
        result = load_all_timeframes("EURUSD")

    assert "5m" in result
    assert "1m" not in result  # 1m not requested from PriceStore


# -- Test 6: load_all_timeframes falls back to CSV when PriceStore unavailable --


def test_load_all_timeframes_fallback_to_csv(hot_packages_dir):
    """When PriceStore is unavailable, falls back to CSV hot packages."""
    with patch("market_data_officer.officer.loader._get_pricestore_adapter", return_value=None):
        result = load_all_timeframes("EURUSD", packages_dir=hot_packages_dir)

    # CSV fallback should load from hot packages
    assert isinstance(result, dict)
    # hot_packages_dir fixture has CSV data
    assert len(result) > 0


# -- Test 7: load_all_timeframes with use_pricestore=False skips PriceStore --


def test_load_all_timeframes_explicit_csv(hot_packages_dir):
    """use_pricestore=False bypasses PriceStore entirely."""
    with patch("market_data_officer.officer.loader._get_pricestore_adapter") as mock_get:
        result = load_all_timeframes(
            "EURUSD", packages_dir=hot_packages_dir, use_pricestore=False,
        )
        mock_get.assert_not_called()

    assert isinstance(result, dict)


# -- Test 8: empty PriceStore data does NOT trigger fallback --


def test_empty_pricestore_does_not_fallback():
    """Empty DataFrames from PriceStore are a data gap, not a fallback trigger."""
    mock_adapter = MagicMock()
    # Return all empty DataFrames
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    empty.index = pd.DatetimeIndex([], tz="UTC")
    mock_adapter.get_timeframes.return_value = {
        "5m": empty, "15m": empty, "1h": empty, "4h": empty, "1d": empty,
    }

    with patch("market_data_officer.officer.loader._get_pricestore_adapter", return_value=mock_adapter):
        result = load_all_timeframes("EURUSD")

    # Empty DFs are filtered out, but we used PriceStore (no fallback)
    assert len(result) == 0
    mock_adapter.get_timeframes.assert_called_once()


# -- Test 9: _compute_staleness uses highest-res TF --


def test_compute_staleness_uses_highest_res():
    """Staleness computed from 5m (highest-res), not 1m."""
    now = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    # 5m has recent data, 1h has old data
    data = {
        "5m": _make_ohlcv_df(10, base_ts=now - timedelta(minutes=30)),
        "1h": _make_ohlcv_df(5, base_ts=now - timedelta(hours=10)),
    }
    minutes, is_stale = _compute_staleness("EURUSD", data, now)
    # Should use 5m (most recent bar ~30 min ago + 9 hours = recent)
    assert minutes < 120  # Not using the old 1h data


# -- Test 10: _compute_staleness falls through when 5m empty --


def test_compute_staleness_fallthrough():
    """When 5m is empty, staleness falls through to 15m, then 1h, etc."""
    now = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    empty.index = pd.DatetimeIndex([], tz="UTC")
    data = {
        "5m": empty,
        "15m": empty,
        "1h": _make_ohlcv_df(5, base_ts=now - timedelta(hours=5)),
    }
    minutes, is_stale = _compute_staleness("EURUSD", data, now)
    # Uses 1h — last bar is ~1h ago (5 bars * 1h, base at now-5h, last at now-1h)
    assert minutes > 0
