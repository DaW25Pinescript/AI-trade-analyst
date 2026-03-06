"""Tests for the validation layer."""

import pandas as pd
import pytest

from feed.validate import validate_ohlcv


def _make_ohlcv(n: int = 5, start: str = "2025-01-15 09:00") -> pd.DataFrame:
    """Create a valid OHLCV DataFrame for testing."""
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "open": [1.09] * n,
            "high": [1.095] * n,
            "low": [1.085] * n,
            "close": [1.092] * n,
            "volume": [100.0] * n,
        },
        index=idx,
    )


def test_valid_df_passes():
    """T4.1 — Valid DataFrame passes silently."""
    df = _make_ohlcv()
    validate_ohlcv(df, "test")  # should not raise


def test_empty_df_passes():
    """Empty DataFrame passes validation."""
    validate_ohlcv(pd.DataFrame(), "test")


def test_non_monotonic_raises():
    """T4.2 — Non-monotonic index raises."""
    df = _make_ohlcv()
    df = df.iloc[::-1]  # reverse order
    with pytest.raises(ValueError, match="monotonic"):
        validate_ohlcv(df, "test")


def test_duplicate_timestamps_raise():
    """T4.3 — Duplicate timestamps raise."""
    df = _make_ohlcv(3)
    df = pd.concat([df, df.iloc[[1]]])
    df = df.sort_index()
    with pytest.raises(ValueError, match="duplicate"):
        validate_ohlcv(df, "test")


def test_null_ohlc_raises():
    """T4.4 — Null OHLC raises."""
    df = _make_ohlcv()
    df.loc[df.index[2], "close"] = None
    with pytest.raises(ValueError, match="null"):
        validate_ohlcv(df, "test")


def test_invalid_high_raises():
    """T4.5 — Invalid high/low envelope raises."""
    df = _make_ohlcv()
    # Set high below open — impossible candle
    df.loc[df.index[0], "high"] = 1.08
    with pytest.raises(ValueError, match="invalid high"):
        validate_ohlcv(df, "test")


def test_invalid_low_raises():
    """Invalid low above close raises."""
    df = _make_ohlcv()
    df.loc[df.index[0], "low"] = 1.10
    with pytest.raises(ValueError, match="invalid low"):
        validate_ohlcv(df, "test")


def test_missing_columns_raises():
    """Missing required columns raises."""
    df = _make_ohlcv()
    df = df.drop(columns=["volume"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_ohlcv(df, "test")
