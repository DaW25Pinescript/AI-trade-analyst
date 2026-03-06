"""Top-level orchestration for the Phase 3A Structure Engine.

Orchestrates all structure modules in sequence:
swings → events → liquidity/sweeps → regime → packet assembly.

Does not implement any module's logic directly.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import StructureConfig
from .events import detect_events, update_swing_statuses
from .io import get_output_path, load_bars, write_packet_atomic
from .liquidity import detect_liquidity
from .regime import compute_regime
from .schemas import StructurePacket
from .swings import detect_swings


def compute_structure_packet(
    instrument: str,
    timeframe: str,
    config: StructureConfig,
    bars: Optional[pd.DataFrame] = None,
    packages_dir: Optional[Path] = None,
) -> StructurePacket:
    """Compute a complete structure packet for one instrument and timeframe.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        timeframe: Timeframe label, e.g. '1h'.
        config: Structure engine configuration.
        bars: Optional pre-loaded bars DataFrame. If None, loads from packages.
        packages_dir: Optional custom packages directory.

    Returns:
        A fully populated StructurePacket.

    Raises:
        FileNotFoundError: If bars cannot be loaded.
        ValueError: If bar data is invalid.
    """
    # Load bars if not provided
    if bars is None:
        kwargs = {}
        if packages_dir is not None:
            kwargs["packages_dir"] = packages_dir
        bars = load_bars(instrument, timeframe, **kwargs)

    # Step 1: Detect confirmed swings
    swings = detect_swings(bars, config, timeframe=timeframe)

    # Step 2: Detect BOS and MSS events
    events = detect_events(bars, swings, config, timeframe=timeframe)

    # Step 3: Update swing statuses based on events
    update_swing_statuses(swings, events)

    # Step 4: Detect liquidity levels and sweeps
    liquidity_levels, sweep_events = detect_liquidity(
        bars, swings, config,
        timeframe=timeframe,
        instrument=instrument,
    )

    # Step 5: Compute regime summary
    regime = compute_regime(swings, events)

    # Step 6: Assemble packet
    tolerance = config.eqh_eql_tolerance.get(instrument, 0.00010)
    build_info = {
        "engine_version": "phase_3a",
        "source": f"hot_package_{timeframe}_csv",
        "quality_flag": "trusted",
        "pivot_left_bars": config.pivot_left_bars,
        "pivot_right_bars": config.pivot_right_bars,
        "bos_confirmation": config.bos_confirmation,
        "eqh_eql_tolerance": tolerance,
    }

    # Count events by type
    bos_count = sum(1 for e in events if "bos" in e.type)
    mss_count = sum(1 for e in events if "mss" in e.type)

    diagnostics = {
        "bars_processed": len(bars),
        "swings_confirmed": len(swings),
        "bos_events": bos_count,
        "mss_events": mss_count,
        "liquidity_levels": len(liquidity_levels),
        "sweep_events": len(sweep_events),
    }

    packet = StructurePacket(
        schema_version="structure_packet_v1",
        instrument=instrument,
        timeframe=timeframe,
        as_of=datetime.now(timezone.utc),
        build=build_info,
        swings=swings,
        events=events,
        liquidity=liquidity_levels,
        sweep_events=sweep_events,
        regime=regime,
        diagnostics=diagnostics,
    )

    return packet


def run_engine(
    instruments: list,
    config: StructureConfig,
    packages_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> dict:
    """Run the Structure Engine for all instruments and timeframes.

    Args:
        instruments: List of instrument symbols to process.
        config: Structure engine configuration.
        packages_dir: Optional custom packages directory.
        output_dir: Optional custom output directory.

    Returns:
        Dict mapping '{instrument}_{tf}' to the computed StructurePacket.
    """
    results = {}

    for instrument in instruments:
        for tf in config.timeframes:
            key = f"{instrument}_{tf}"
            print(f"  Computing structure: {key}...")

            try:
                kwargs = {}
                if packages_dir is not None:
                    kwargs["packages_dir"] = packages_dir
                packet = compute_structure_packet(
                    instrument, tf, config, **kwargs,
                )

                # Write JSON packet
                out_dir = output_dir if output_dir else None
                path_kwargs = {}
                if out_dir:
                    path_kwargs["output_dir"] = out_dir
                out_path = get_output_path(instrument, tf, **path_kwargs)
                write_packet_atomic(packet.to_dict(), out_path)

                results[key] = packet
                print(f"    -> {len(packet.swings)} swings, "
                      f"{len(packet.events)} events, "
                      f"{len(packet.liquidity)} levels, "
                      f"{len(packet.sweep_events)} sweeps")

            except FileNotFoundError as e:
                print(f"    -> SKIPPED: {e}")
            except ValueError as e:
                print(f"    -> ERROR: {e}")

    return results
