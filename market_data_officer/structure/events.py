"""BOS and MSS detection from confirmed swings.

BOS (Break of Structure): confirmed when a candle closes beyond a prior
confirmed swing's price. Close-confirmation only — wick breaches do not
trigger BOS in 3A.

MSS (Market Structure Shift): confirmed when a BOS fires in the opposite
direction of the established structural bias.
"""

from typing import List, Optional

import pandas as pd

from .config import StructureConfig
from .schemas import StructureEvent, SwingPoint


def detect_events(
    bars: pd.DataFrame,
    swings: List[SwingPoint],
    config: StructureConfig,
    timeframe: str = "1h",
) -> List[StructureEvent]:
    """Detect BOS and MSS events from confirmed swings and bar data.

    Args:
        bars: DataFrame with DatetimeIndex and OHLCV columns.
        swings: List of confirmed SwingPoint objects (from detect_swings).
        config: Structure engine configuration.
        timeframe: Timeframe label for ID generation.

    Returns:
        List of StructureEvent objects (BOS and MSS), ordered by time.

    Raises:
        ValueError: If bars DataFrame is missing required columns.
    """
    if bars.empty or not swings:
        return []

    required_cols = {"open", "high", "low", "close"}
    missing = required_cols - set(bars.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    events: List[StructureEvent] = []

    # Track the most recent confirmed swing high and swing low
    # that are eligible for BOS (confirmed before the current bar)
    swing_highs = sorted(
        [s for s in swings if s.type == "swing_high"],
        key=lambda s: s.confirm_time,
    )
    swing_lows = sorted(
        [s for s in swings if s.type == "swing_low"],
        key=lambda s: s.confirm_time,
    )

    # Track current structural bias for MSS detection
    current_bias: Optional[str] = None
    # Track which swings have already been broken to avoid duplicate BOS
    broken_swing_ids: set = set()

    closes = bars["close"].values
    timestamps = bars.index

    for bar_idx in range(len(bars)):
        bar_time = timestamps[bar_idx].to_pydatetime()
        bar_close = float(closes[bar_idx])

        # Find the most recent confirmed swing high before this bar
        active_sh = None
        for sh in reversed(swing_highs):
            if sh.confirm_time < bar_time and sh.id not in broken_swing_ids:
                active_sh = sh
                break

        # Find the most recent confirmed swing low before this bar
        active_sl = None
        for sl in reversed(swing_lows):
            if sl.confirm_time < bar_time and sl.id not in broken_swing_ids:
                active_sl = sl
                break

        # Check for bullish BOS: close above prior swing high
        if active_sh and bar_close > active_sh.price:
            compact_time = bar_time.strftime("%Y%m%dT%H%M")
            event_type = "bos_bull"
            prior_bias_val = None

            # Check if this is an MSS (direction change)
            if current_bias == "bearish":
                event_type = "mss_bull"
                prior_bias_val = "bearish"

            event_id = f"ev_{timeframe}_{compact_time}_{event_type}"
            events.append(StructureEvent(
                id=event_id,
                type=event_type,
                time=bar_time,
                timeframe=timeframe,
                reference_swing_id=active_sh.id,
                reference_price=active_sh.price,
                break_close=bar_close,
                prior_bias=prior_bias_val,
                status="confirmed",
            ))
            broken_swing_ids.add(active_sh.id)
            current_bias = "bullish"

        # Check for bearish BOS: close below prior swing low
        if active_sl and bar_close < active_sl.price:
            compact_time = bar_time.strftime("%Y%m%dT%H%M")
            event_type = "bos_bear"
            prior_bias_val = None

            # Check if this is an MSS (direction change)
            if current_bias == "bullish":
                event_type = "mss_bear"
                prior_bias_val = "bullish"

            event_id = f"ev_{timeframe}_{compact_time}_{event_type}"
            events.append(StructureEvent(
                id=event_id,
                type=event_type,
                time=bar_time,
                timeframe=timeframe,
                reference_swing_id=active_sl.id,
                reference_price=active_sl.price,
                break_close=bar_close,
                prior_bias=prior_bias_val,
                status="confirmed",
            ))
            broken_swing_ids.add(active_sl.id)
            current_bias = "bearish"

    # Sort by time for deterministic ordering
    events.sort(key=lambda e: e.time)
    return events


def update_swing_statuses(
    swings: List[SwingPoint],
    events: List[StructureEvent],
) -> None:
    """Update swing statuses based on BOS events.

    Swings whose levels have been broken get status='broken'.
    This is a status transition only — no mutation of price/time/id.

    Args:
        swings: List of SwingPoint objects to update in place.
        events: List of StructureEvent objects (BOS/MSS).
    """
    broken_ids = {e.reference_swing_id for e in events}
    for swing in swings:
        if swing.id in broken_ids and swing.status == "confirmed":
            swing.status = "broken"
