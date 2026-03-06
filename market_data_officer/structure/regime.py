"""Objective regime summary derived from confirmed structure events.

Regime is derivative and non-authoritative. It summarises confirmed
events — it does not predict.
"""

from typing import List

from .schemas import RegimeSummary, StructureEvent, SwingPoint

# Minimum BOS events needed for trend determination
MIN_BOS_FOR_TREND = 3
# Swing cycles to look back for structure quality assessment
QUALITY_LOOKBACK_CYCLES = 5


def compute_regime(
    swings: List[SwingPoint],
    events: List[StructureEvent],
) -> RegimeSummary:
    """Derive objective structural regime from confirmed swings and events.

    Derivation rules:
    - bias: direction of the most recent confirmed BOS
    - last_bos_direction: direction field of the most recent BOS event
    - last_mss_direction: direction of the most recent MSS event, else None
    - trend_state: 'trending' if last 3 BOS are same direction,
                   'ranging' if alternating, 'unknown' if insufficient
    - structure_quality: 'clean' if no opposing BOS in last 5 swing cycles,
                         'choppy' if opposing BOS present,
                         'unknown' if insufficient history

    Args:
        swings: List of confirmed SwingPoint objects.
        events: List of StructureEvent objects (BOS and MSS).

    Returns:
        RegimeSummary object.
    """
    # Extract BOS and MSS events separately
    bos_events = [e for e in events if e.type in ("bos_bull", "bos_bear")]
    mss_events = [e for e in events if e.type in ("mss_bull", "mss_bear")]

    # Sort by time
    bos_events.sort(key=lambda e: e.time)
    mss_events.sort(key=lambda e: e.time)

    # Bias: direction of the most recent BOS
    bias = "neutral"
    last_bos_direction = None
    if bos_events:
        last_bos = bos_events[-1]
        if "bull" in last_bos.type:
            bias = "bullish"
            last_bos_direction = "bullish"
        elif "bear" in last_bos.type:
            bias = "bearish"
            last_bos_direction = "bearish"

    # Also check MSS events for bias (MSS is also a BOS in the opposite direction)
    all_directional = sorted(
        [e for e in events if e.type in ("bos_bull", "bos_bear", "mss_bull", "mss_bear")],
        key=lambda e: e.time,
    )
    if all_directional:
        last_dir = all_directional[-1]
        if "bull" in last_dir.type:
            bias = "bullish"
            last_bos_direction = "bullish"
        elif "bear" in last_dir.type:
            bias = "bearish"
            last_bos_direction = "bearish"

    # Last MSS direction
    last_mss_direction = None
    if mss_events:
        last_mss = mss_events[-1]
        if "bull" in last_mss.type:
            last_mss_direction = "bullish"
        elif "bear" in last_mss.type:
            last_mss_direction = "bearish"

    # Trend state: last 3 directional events same direction → trending
    trend_state = "unknown"
    if len(all_directional) >= MIN_BOS_FOR_TREND:
        last_n = all_directional[-MIN_BOS_FOR_TREND:]
        directions = []
        for e in last_n:
            if "bull" in e.type:
                directions.append("bullish")
            else:
                directions.append("bearish")

        if len(set(directions)) == 1:
            trend_state = "trending"
        else:
            trend_state = "ranging"

    # Structure quality: no opposing BOS in last 5 swing cycles → clean
    structure_quality = "unknown"
    sorted_swings = sorted(swings, key=lambda s: s.anchor_time)
    if len(sorted_swings) >= QUALITY_LOOKBACK_CYCLES and len(all_directional) >= 2:
        # Look at BOS events within the last N swing cycles
        cutoff_swing = sorted_swings[-QUALITY_LOOKBACK_CYCLES]
        recent_directional = [
            e for e in all_directional if e.time >= cutoff_swing.anchor_time
        ]

        if recent_directional:
            recent_dirs = set()
            for e in recent_directional:
                if "bull" in e.type:
                    recent_dirs.add("bullish")
                else:
                    recent_dirs.add("bearish")

            if len(recent_dirs) == 1:
                structure_quality = "clean"
            else:
                structure_quality = "choppy"

    return RegimeSummary(
        bias=bias,
        last_bos_direction=last_bos_direction,
        last_mss_direction=last_mss_direction,
        trend_state=trend_state,
        structure_quality=structure_quality,
    )
