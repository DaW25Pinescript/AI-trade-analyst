"""Tests for the resample layer."""

import pandas as pd
import pytest

from feed.resample import resample_from_1m


def _make_canonical(n: int = 60) -> pd.DataFrame:
    """Create a canonical 1m OHLCV DataFrame for testing."""
    idx = pd.date_range("2025-01-15 09:00", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "open": [1.0900 + i * 0.0001 for i in range(n)],
            "high": [1.0905 + i * 0.0001 for i in range(n)],
            "low": [1.0895 + i * 0.0001 for i in range(n)],
            "close": [1.0902 + i * 0.0001 for i in range(n)],
            "volume": [100.0] * n,
        },
        index=idx,
    )


def test_resample_5m_schema():
    """T5.1 — Derived 5m has correct schema and metadata."""
    df = _make_canonical()
    df_5m = resample_from_1m(df, "5min")

    assert not df_5m.empty
    assert set(df_5m.columns) >= {"open", "high", "low", "close", "volume", "vendor", "build_method", "quality_flag"}
    assert df_5m.index.tzinfo is not None
    assert df_5m["vendor"].iloc[0] == "derived"
    assert df_5m["build_method"].iloc[0] == "resample_from_1m"


def test_resample_bar_correctness():
    """T5.3 — 5m bar values are correct aggregations of 1m bars."""
    df = _make_canonical(10)
    df_5m = resample_from_1m(df, "5min")

    first_5 = df.iloc[:5]
    bar = df_5m.iloc[0]

    assert bar["open"] == first_5["open"].iloc[0]
    assert bar["high"] == first_5["high"].max()
    assert bar["low"] == first_5["low"].min()
    assert bar["close"] == first_5["close"].iloc[-1]
    assert bar["volume"] == first_5["volume"].sum()


def test_resample_empty_input():
    """Empty input returns empty DataFrame."""
    result = resample_from_1m(pd.DataFrame(), "5min")
    assert result.empty


def test_resample_1h():
    """1h resample works correctly."""
    df = _make_canonical(120)
    df_1h = resample_from_1m(df, "1h")
    assert not df_1h.empty
    assert df_1h.index.tzinfo is not None


def test_no_mid_column_in_resample():
    """T5.2 — No mid column in resample output."""
    df = _make_canonical()
    df_5m = resample_from_1m(df, "5min")
    assert "mid" not in df_5m.columns
