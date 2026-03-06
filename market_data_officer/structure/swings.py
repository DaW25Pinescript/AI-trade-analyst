"""Confirmed swing detection using fixed left/right pivot confirmation.

A swing high is confirmed when the anchor bar's high exceeds the highs of
`left_bars` bars to the left AND `right_bars` bars to the right, all on
already-closed bars. Swing lows are symmetric using lows.

No provisional swings in 3A — a swing either meets confirmation criteria
or does not exist yet.
"""

from typing import List

import pandas as pd

from .config import StructureConfig
from .schemas import SwingPoint


def detect_swings(
    bars: pd.DataFrame,
    config: StructureConfig,
    timeframe: str = "1h",
) -> List[SwingPoint]:
    """Detect confirmed swing highs and lows from OHLCV bars.

    Args:
        bars: DataFrame with DatetimeIndex and columns: open, high, low, close, volume.
        config: Structure engine configuration.
        timeframe: Timeframe label for ID generation.

    Returns:
        List of confirmed SwingPoint objects, ordered by anchor_time.

    Raises:
        ValueError: If bars DataFrame is missing required columns.
    """
    if bars.empty:
        return []

    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(bars.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    left = config.pivot_left_bars
    right = config.pivot_right_bars
    min_bars = left + 1 + right

    if len(bars) < min_bars:
        return []

    swings: List[SwingPoint] = []
    highs = bars["high"].values
    lows = bars["low"].values
    timestamps = bars.index

    for i in range(left, len(bars) - right):
        # Check swing high: anchor high > all left highs AND all right highs
        is_swing_high = True
        for j in range(i - left, i):
            if highs[i] <= highs[j]:
                is_swing_high = False
                break
        if is_swing_high:
            for j in range(i + 1, i + right + 1):
                if highs[i] <= highs[j]:
                    is_swing_high = False
                    break

        if is_swing_high:
            anchor_time = timestamps[i].to_pydatetime()
            confirm_time = timestamps[i + right].to_pydatetime()
            compact_time = anchor_time.strftime("%Y%m%dT%H%M")
            swing_id = f"sw_{timeframe}_{compact_time}_sh"

            swings.append(SwingPoint(
                id=swing_id,
                type="swing_high",
                price=float(highs[i]),
                anchor_time=anchor_time,
                confirm_time=confirm_time,
                timeframe=timeframe,
                left_bars=left,
                right_bars=right,
                strength=right,
                status="confirmed",
            ))

        # Check swing low: anchor low < all left lows AND all right lows
        is_swing_low = True
        for j in range(i - left, i):
            if lows[i] >= lows[j]:
                is_swing_low = False
                break
        if is_swing_low:
            for j in range(i + 1, i + right + 1):
                if lows[i] >= lows[j]:
                    is_swing_low = False
                    break

        if is_swing_low:
            anchor_time = timestamps[i].to_pydatetime()
            confirm_time = timestamps[i + right].to_pydatetime()
            compact_time = anchor_time.strftime("%Y%m%dT%H%M")
            swing_id = f"sw_{timeframe}_{compact_time}_sl"

            swings.append(SwingPoint(
                id=swing_id,
                type="swing_low",
                price=float(lows[i]),
                anchor_time=anchor_time,
                confirm_time=confirm_time,
                timeframe=timeframe,
                left_bars=left,
                right_bars=right,
                strength=right,
                status="confirmed",
            ))

    # Sort by anchor_time for deterministic ordering
    swings.sort(key=lambda s: s.anchor_time)
    return swings
