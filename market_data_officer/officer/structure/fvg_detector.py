"""Fair Value Gap (FVG) detection — Phase 3 stub.

This module will identify fair value gaps (imbalance zones) in price action.
"""

import pandas as pd


def detect_fvg(df: pd.DataFrame) -> None:
    """Detect Fair Value Gap zones in the given OHLCV data.

    Phase 3 will implement: three-candle gap detection, gap fill tracking,
    zone classification (bullish/bearish), multi-timeframe confluence.
    Not implemented in Phase 2.

    Args:
        df: OHLCV DataFrame with standard columns.

    Returns:
        None — stub only. Phase 3 will return structured FVG zones.
    """
    return None
