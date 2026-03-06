"""Resample layer — derives higher timeframes from canonical 1m OHLCV."""

import pandas as pd

from .validate import validate_ohlcv


def resample_from_1m(canonical_df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample canonical 1m OHLCV to a higher timeframe.

    Resamples from open/high/low/close/volume columns only.
    Adds vendor, build_method, and quality_flag metadata columns.
    """
    if canonical_df.empty:
        return pd.DataFrame()

    resampled = canonical_df.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })

    # Drop bars with no data
    resampled = resampled.dropna(subset=["open"])

    # Add metadata columns
    resampled["vendor"] = "derived"
    resampled["build_method"] = "resample_from_1m"
    resampled["quality_flag"] = "ok"

    return resampled
