"""Validation layer — enforces data integrity before every write."""

import pandas as pd


REQUIRED_OHLCV_COLUMNS = {"open", "high", "low", "close", "volume"}


def validate_ohlcv(df: pd.DataFrame, label: str) -> None:
    """Validate an OHLCV DataFrame. Raises ValueError on any integrity failure.

    Checks:
    1. Required columns present
    2. Monotonically increasing timestamps
    3. No duplicate timestamps
    4. No null OHLC values
    5. High/low envelope validity
    """
    if df.empty:
        return

    # 1. Required columns
    missing = REQUIRED_OHLCV_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"[{label}] missing required columns: {missing}")

    # 2. Monotonic timestamps
    if not df.index.is_monotonic_increasing:
        raise ValueError(f"[{label}] index is not monotonic increasing")

    # 3. No duplicate timestamps
    dupes = df.index.duplicated()
    if dupes.any():
        n_dupes = dupes.sum()
        raise ValueError(f"[{label}] {n_dupes} duplicate timestamp(s) found")

    # 4. No null OHLC
    for col in ("open", "high", "low", "close"):
        if df[col].isnull().any():
            n_null = df[col].isnull().sum()
            raise ValueError(f"[{label}] {n_null} null value(s) in {col}")

    # 5. High/low envelope
    bad_high = df["high"] < df[["open", "close"]].max(axis=1)
    if bad_high.any():
        n_bad = bad_high.sum()
        raise ValueError(f"[{label}] {n_bad} row(s) with invalid high (high < max(open, close))")

    bad_low = df["low"] > df[["open", "close"]].min(axis=1)
    if bad_low.any():
        n_bad = bad_low.sum()
        raise ValueError(f"[{label}] {n_bad} row(s) with invalid low (low > min(open, close))")
