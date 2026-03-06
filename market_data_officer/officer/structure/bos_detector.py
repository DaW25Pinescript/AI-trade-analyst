"""Break of Structure (BOS) detection — Phase 3 stub.

This module will detect structural breaks in price action across timeframes.
"""

import pandas as pd


def detect_bos(df: pd.DataFrame) -> None:
    """Detect Break of Structure events in the given OHLCV data.

    Phase 3 will implement: pivot detection rules, break confirmation logic,
    close vs wick interpretation, timeframe interaction model.
    Not implemented in Phase 2.

    Args:
        df: OHLCV DataFrame with standard columns.

    Returns:
        None — stub only. Phase 3 will return structured BOS events.
    """
    return None
