"""Compression detection — Phase 4 stub.

This module will detect price compression zones indicating potential expansion.
"""

import pandas as pd


def detect_compression(df: pd.DataFrame) -> None:
    """Detect compression zones in the given OHLCV data.

    Phase 4 will implement: range contraction detection, Bollinger Band squeeze,
    ATR compression percentile, historical range comparison, breakout probability.
    Not implemented in Phase 2.

    Args:
        df: OHLCV DataFrame with standard columns.

    Returns:
        None — stub only. Phase 4 will return compression state and metrics.
    """
    return None
