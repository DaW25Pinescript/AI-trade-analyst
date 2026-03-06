"""Imbalance / liquidity sweep detection — Phase 4 stub.

This module will detect order flow imbalances and liquidity sweep events.
"""

import pandas as pd


def detect_imbalance(df: pd.DataFrame) -> None:
    """Detect order flow imbalance events in the given OHLCV data.

    Phase 4 will implement: volume-weighted imbalance scoring, liquidity sweep
    detection at key levels, stop-hunt pattern recognition, institutional
    order flow inference.
    Not implemented in Phase 2.

    Args:
        df: OHLCV DataFrame with standard columns.

    Returns:
        None — stub only. Phase 4 will return imbalance bias and events.
    """
    return None
