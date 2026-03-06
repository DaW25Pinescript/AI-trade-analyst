"""Prior period liquidity levels, EQH/EQL detection, and sweep events.

Computes:
- Prior day high/low from completed sessions
- Prior week high/low from completed weeks
- Equal highs/equal lows from confirmed swing clusters
- Sweep events when price trades through liquidity levels
"""

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

import pandas as pd

from .config import StructureConfig
from .schemas import LiquidityLevel, SweepEvent, SwingPoint


def _get_session_boundaries(
    bars: pd.DataFrame,
    config: StructureConfig,
) -> List[Tuple[datetime, datetime]]:
    """Compute daily session boundaries from bar timestamps.

    Each session runs from day_session_open_utc on one day to the same
    hour the next day.

    Args:
        bars: DataFrame with DatetimeIndex.
        config: Structure engine configuration.

    Returns:
        List of (session_start, session_end) tuples for completed sessions.
    """
    if bars.empty:
        return []

    start = bars.index[0].to_pydatetime()
    end = bars.index[-1].to_pydatetime()
    open_hour = config.day_session_open_utc

    # Find the first session start at or before the first bar
    current = start.replace(hour=open_hour, minute=0, second=0, microsecond=0)
    if current > start:
        current -= timedelta(days=1)

    sessions = []
    while current + timedelta(days=1) <= end:
        session_start = current
        session_end = current + timedelta(days=1)
        sessions.append((session_start, session_end))
        current += timedelta(days=1)

    return sessions


def _get_week_boundaries(
    bars: pd.DataFrame,
    config: StructureConfig,
) -> List[Tuple[datetime, datetime]]:
    """Compute weekly session boundaries.

    Each week runs from week_session_open_day at day_session_open_utc
    to the same time the following week.

    Args:
        bars: DataFrame with DatetimeIndex.
        config: Structure engine configuration.

    Returns:
        List of (week_start, week_end) tuples for completed weeks.
    """
    if bars.empty:
        return []

    start = bars.index[0].to_pydatetime()
    end = bars.index[-1].to_pydatetime()
    open_hour = config.day_session_open_utc
    open_day = config.week_session_open_day  # Sunday = 6

    # Find the first week start at or before the first bar
    current = start.replace(hour=open_hour, minute=0, second=0, microsecond=0)
    # Walk back to the right weekday
    while current.isoweekday() != open_day:
        current -= timedelta(days=1)
    if current > start:
        current -= timedelta(weeks=1)

    weeks = []
    while current + timedelta(weeks=1) <= end:
        week_start = current
        week_end = current + timedelta(weeks=1)
        weeks.append((week_start, week_end))
        current += timedelta(weeks=1)

    return weeks


def _detect_prior_period_levels(
    bars: pd.DataFrame,
    config: StructureConfig,
    timeframe: str,
) -> List[LiquidityLevel]:
    """Detect prior day and prior week high/low levels.

    Args:
        bars: DataFrame with DatetimeIndex and OHLCV columns.
        config: Structure engine configuration.
        timeframe: Timeframe label for ID generation.

    Returns:
        List of LiquidityLevel objects for prior period highs and lows.
    """
    levels: List[LiquidityLevel] = []

    # Prior day highs and lows
    sessions = _get_session_boundaries(bars, config)
    for i in range(len(sessions) - 1):
        # The "prior" session for the next session
        sess_start, sess_end = sessions[i]
        # Get bars within this session
        mask = (bars.index >= sess_start) & (bars.index < sess_end)
        session_bars = bars[mask]
        if session_bars.empty:
            continue

        day_high = float(session_bars["high"].max())
        day_low = float(session_bars["low"].min())
        origin = sess_start

        compact_origin = origin.strftime("%Y%m%dT%H%M")

        levels.append(LiquidityLevel(
            id=f"liq_{timeframe}_pdh_{compact_origin}",
            type="prior_day_high",
            price=day_high,
            origin_time=origin,
            timeframe=timeframe,
            status="active",
        ))
        levels.append(LiquidityLevel(
            id=f"liq_{timeframe}_pdl_{compact_origin}",
            type="prior_day_low",
            price=day_low,
            origin_time=origin,
            timeframe=timeframe,
            status="active",
        ))

    # Prior week highs and lows
    weeks = _get_week_boundaries(bars, config)
    for i in range(len(weeks) - 1):
        week_start, week_end = weeks[i]
        mask = (bars.index >= week_start) & (bars.index < week_end)
        week_bars = bars[mask]
        if week_bars.empty:
            continue

        week_high = float(week_bars["high"].max())
        week_low = float(week_bars["low"].min())
        origin = week_start

        compact_origin = origin.strftime("%Y%m%dT%H%M")

        levels.append(LiquidityLevel(
            id=f"liq_{timeframe}_pwh_{compact_origin}",
            type="prior_week_high",
            price=week_high,
            origin_time=origin,
            timeframe=timeframe,
            status="active",
        ))
        levels.append(LiquidityLevel(
            id=f"liq_{timeframe}_pwl_{compact_origin}",
            type="prior_week_low",
            price=week_low,
            origin_time=origin,
            timeframe=timeframe,
            status="active",
        ))

    return levels


def _detect_equal_levels(
    swings: List[SwingPoint],
    tolerance: float,
    timeframe: str,
) -> List[LiquidityLevel]:
    """Detect EQH (equal highs) and EQL (equal lows) from confirmed swings.

    Two or more confirmed swing highs (or lows) within tolerance produce
    an EQH (or EQL) level. Uses greedy clustering: iterate sorted swings,
    group consecutive swings within tolerance.

    Args:
        swings: List of confirmed SwingPoint objects.
        tolerance: Fixed pip/point tolerance for equality comparison.
        timeframe: Timeframe label for ID generation.

    Returns:
        List of LiquidityLevel objects for equal highs/lows.
    """
    levels: List[LiquidityLevel] = []

    # Process swing highs and lows separately
    for swing_type, level_type in [("swing_high", "equal_highs"), ("swing_low", "equal_lows")]:
        typed_swings = sorted(
            [s for s in swings if s.type == swing_type],
            key=lambda s: s.price,
        )

        if len(typed_swings) < 2:
            continue

        # Greedy clustering: group swings with prices within tolerance
        used = set()
        for i, anchor in enumerate(typed_swings):
            if i in used:
                continue
            cluster = [anchor]
            cluster_indices = [i]
            for j in range(i + 1, len(typed_swings)):
                if j in used:
                    continue
                if abs(typed_swings[j].price - anchor.price) <= tolerance:
                    cluster.append(typed_swings[j])
                    cluster_indices.append(j)

            if len(cluster) >= 2:
                for idx in cluster_indices:
                    used.add(idx)

                member_ids = [s.id for s in cluster]
                avg_price = sum(s.price for s in cluster) / len(cluster)
                # Origin time is the earliest swing in the cluster
                earliest = min(cluster, key=lambda s: s.anchor_time)
                compact_origin = earliest.anchor_time.strftime("%Y%m%dT%H%M")
                abbrev = "eqh" if level_type == "equal_highs" else "eql"

                levels.append(LiquidityLevel(
                    id=f"liq_{timeframe}_{abbrev}_{compact_origin}",
                    type=level_type,
                    price=avg_price,
                    origin_time=earliest.anchor_time,
                    timeframe=timeframe,
                    status="active",
                    member_swing_ids=member_ids,
                    tolerance_used=tolerance,
                ))

    return levels


def _detect_sweeps(
    bars: pd.DataFrame,
    levels: List[LiquidityLevel],
    timeframe: str,
) -> List[SweepEvent]:
    """Detect sweep events where price trades through liquidity levels.

    Sweeps can be triggered by wick or close — price merely needs to
    trade through the level. This is distinct from BOS which requires
    close confirmation.

    Args:
        bars: DataFrame with DatetimeIndex and OHLCV columns.
        levels: List of LiquidityLevel objects to check for sweeps.
        timeframe: Timeframe label for ID generation.

    Returns:
        List of SweepEvent objects for detected sweeps.
    """
    sweep_events: List[SweepEvent] = []

    highs = bars["high"].values
    lows = bars["low"].values
    closes = bars["close"].values
    timestamps = bars.index

    for level in levels:
        if level.status != "active":
            continue

        # Determine sweep direction based on level type
        is_high_level = level.type in ("prior_day_high", "prior_week_high", "equal_highs")
        is_low_level = level.type in ("prior_day_low", "prior_week_low", "equal_lows")

        if not (is_high_level or is_low_level):
            continue

        for bar_idx in range(len(bars)):
            bar_time = timestamps[bar_idx].to_pydatetime()

            # Only check bars after the level's origin time
            if bar_time <= level.origin_time:
                continue

            swept = False
            sweep_price = 0.0
            sweep_type_str = ""

            if is_high_level:
                # Sweep high: price trades above the level
                if float(closes[bar_idx]) > level.price:
                    swept = True
                    sweep_price = float(closes[bar_idx])
                    sweep_type_str = "close_sweep"
                elif float(highs[bar_idx]) > level.price:
                    swept = True
                    sweep_price = float(highs[bar_idx])
                    sweep_type_str = "wick_sweep"

            elif is_low_level:
                # Sweep low: price trades below the level
                if float(closes[bar_idx]) < level.price:
                    swept = True
                    sweep_price = float(closes[bar_idx])
                    sweep_type_str = "close_sweep"
                elif float(lows[bar_idx]) < level.price:
                    swept = True
                    sweep_price = float(lows[bar_idx])
                    sweep_type_str = "wick_sweep"

            if swept:
                level.status = "swept"
                level.swept_time = bar_time
                level.sweep_type = sweep_type_str

                compact_time = bar_time.strftime("%Y%m%dT%H%M")
                # Extract abbreviation from level id for sweep id
                level_abbrev = level.id.split("_")[2]  # e.g. "pdh", "eqh"
                sweep_side = "sweep_high" if is_high_level else "sweep_low"

                sweep_events.append(SweepEvent(
                    id=f"swp_{timeframe}_{compact_time}_{level_abbrev}",
                    type=sweep_side,
                    time=bar_time,
                    timeframe=timeframe,
                    liquidity_level_id=level.id,
                    sweep_price=sweep_price,
                    sweep_type=sweep_type_str,
                    status="confirmed",
                ))
                break  # Level is swept, move to next level

    return sweep_events


def detect_liquidity(
    bars: pd.DataFrame,
    swings: List[SwingPoint],
    config: StructureConfig,
    timeframe: str = "1h",
    instrument: str = "EURUSD",
) -> Tuple[List[LiquidityLevel], List[SweepEvent]]:
    """Detect all liquidity levels and sweep events.

    Args:
        bars: DataFrame with DatetimeIndex and OHLCV columns.
        swings: List of confirmed SwingPoint objects.
        config: Structure engine configuration.
        timeframe: Timeframe label for ID generation.
        instrument: Instrument symbol for tolerance lookup.

    Returns:
        Tuple of (liquidity_levels, sweep_events).

    Raises:
        ValueError: If bars DataFrame is missing required columns.
    """
    if bars.empty:
        return [], []

    required_cols = {"open", "high", "low", "close"}
    missing = required_cols - set(bars.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Detect prior period levels
    levels = _detect_prior_period_levels(bars, config, timeframe)

    # Detect EQH/EQL
    tolerance = config.eqh_eql_tolerance.get(instrument, 0.00010)
    eq_levels = _detect_equal_levels(swings, tolerance, timeframe)
    levels.extend(eq_levels)

    # Detect sweeps against all levels
    sweep_events = _detect_sweeps(bars, levels, timeframe)

    return levels, sweep_events
