"""Aggregation layer — converts tick-level data to 1-minute OHLCV bars."""

import pandas as pd


def ticks_to_1m_ohlcv(tick_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate a tick DataFrame (with mid and volume columns) into 1-minute OHLCV.

    Input: DataFrame indexed by timestamp_utc with columns [mid, volume].
    Output: DataFrame indexed by timestamp_utc with columns [open, high, low, close, volume].

    Returns empty DataFrame if input is empty.
    """
    if tick_df.empty:
        return pd.DataFrame()

    ohlcv = tick_df["mid"].resample("1min").agg(
        open="first",
        high="max",
        low="min",
        close="last",
    )

    ohlcv["volume"] = tick_df["volume"].resample("1min").sum()

    # Drop minutes with no ticks
    ohlcv = ohlcv.dropna(subset=["open"])

    return ohlcv
