"""Phase 3C — FVG detection, fill tracking, and active zone registry.

Detects Fair Value Gaps using body-only logic, tracks fill progression
through partial and full states, and maintains an active zone registry.
"""

import pandas as pd

from .config import StructureConfig
from .schemas import FairValueGap
from market_data_officer.instrument_registry import INSTRUMENT_REGISTRY


def _compact_ts(ts) -> str:
    """Create a compact timestamp string for deterministic IDs."""
    return ts.strftime("%Y%m%d%H%M")


def detect_fvg(
    bars: pd.DataFrame,
    config: StructureConfig,
    instrument: str,
    timeframe: str,
) -> list:
    """Detect Fair Value Gaps using body-only logic.

    A zone is not emitted until candle 3 closes (no lookahead).
    Minimum gap size filtered per instrument config.
    """
    # Look up per-instrument FVG min size from the registry; fall back to EURUSD
    registry_meta = INSTRUMENT_REGISTRY.get(instrument)
    if registry_meta is not None and registry_meta.fvg_min_size > 0:
        min_size = registry_meta.fvg_min_size
    else:
        min_size = config.fvg_min_size_eurusd

    zones = []
    for i in range(2, len(bars)):
        c1 = bars.iloc[i - 2]
        c3 = bars.iloc[i]

        # Body boundaries
        c1_body_high = max(c1["open"], c1["close"])
        c1_body_low = min(c1["open"], c1["close"])
        c3_body_high = max(c3["open"], c3["close"])
        c3_body_low = min(c3["open"], c3["close"])

        # Bullish FVG: gap between c1 body top and c3 body bottom
        if c3_body_low > c1_body_high:
            gap_size = c3_body_low - c1_body_high
            if gap_size >= min_size:
                origin_ts = bars.index[i - 1]
                confirm_ts = bars.index[i]
                fvg_id = f"fvg_{timeframe}_{_compact_ts(origin_ts)}_bull"
                zones.append(FairValueGap(
                    id=fvg_id,
                    fvg_type="bullish_fvg",
                    zone_high=c3_body_low,
                    zone_low=c1_body_high,
                    zone_size=gap_size,
                    origin_time=origin_ts,
                    confirm_time=confirm_ts,
                    timeframe=timeframe,
                    status="open",
                ))

        # Bearish FVG: gap between c3 body top and c1 body bottom
        elif c3_body_high < c1_body_low:
            gap_size = c1_body_low - c3_body_high
            if gap_size >= min_size:
                origin_ts = bars.index[i - 1]
                confirm_ts = bars.index[i]
                fvg_id = f"fvg_{timeframe}_{_compact_ts(origin_ts)}_bear"
                zones.append(FairValueGap(
                    id=fvg_id,
                    fvg_type="bearish_fvg",
                    zone_high=c1_body_low,
                    zone_low=c3_body_high,
                    zone_size=gap_size,
                    origin_time=origin_ts,
                    confirm_time=confirm_ts,
                    timeframe=timeframe,
                    status="open",
                ))

    return zones


def update_fvg_fills(zone: FairValueGap, bars: pd.DataFrame) -> FairValueGap:
    """Process subsequent bars after zone confirmation.

    Tracks partial and full fill transitions in order.
    A zone cannot skip from open to fully_filled without partial_fill.
    If price blows through, both transitions fire in sequence on the same bar.
    """
    if zone.status == "invalidated":
        return zone  # terminal state — do not reprocess

    subsequent = bars[bars.index > zone.confirm_time]

    for ts, bar in subsequent.iterrows():
        close = bar["close"]

        if zone.fvg_type == "bullish_fvg":
            # Check for entry into zone: close below zone_high
            if zone.status == "open" and close < zone.zone_high:
                zone.status = "partially_filled"
                zone.first_touch_time = ts
                zone.partial_fill_time = ts
                zone.fill_low = close

            # Check for full fill: close at or below zone_low
            if zone.status == "partially_filled":
                zone.fill_low = min(zone.fill_low if zone.fill_low is not None else close, close)
                if close <= zone.zone_low:
                    zone.status = "invalidated"
                    zone.full_fill_time = ts
                    return zone

        elif zone.fvg_type == "bearish_fvg":
            # Check for entry into zone: close above zone_low
            if zone.status == "open" and close > zone.zone_low:
                zone.status = "partially_filled"
                zone.first_touch_time = ts
                zone.partial_fill_time = ts
                zone.fill_high = close

            # Check for full fill: close at or above zone_high
            if zone.status == "partially_filled":
                zone.fill_high = max(zone.fill_high if zone.fill_high is not None else close, close)
                if close >= zone.zone_high:
                    zone.status = "invalidated"
                    zone.full_fill_time = ts
                    return zone

    return zone


def build_active_zone_registry(zones: list) -> dict:
    """Build the active zone registry from a list of FVG zones.

    Only zones with status 'open' or 'partially_filled' are included.
    """
    active = [z for z in zones if z.status in ("open", "partially_filled")]
    return {
        "count": len(active),
        "zones": active,
    }


def process_imbalance(
    bars: pd.DataFrame,
    config: StructureConfig,
    instrument: str,
    timeframe: str,
) -> tuple:
    """Full imbalance pipeline: detect FVGs, update fills, build registry.

    Returns:
        Tuple of (all_zones, active_zones_dict).
    """
    # Step 1: Detect FVGs
    zones = detect_fvg(bars, config, instrument, timeframe)

    # Step 2: Update fill tracking for each zone
    for i, zone in enumerate(zones):
        zones[i] = update_fvg_fills(zone, bars)

    # Step 3: Build active zone registry
    active_zones = build_active_zone_registry(zones)

    return zones, active_zones
