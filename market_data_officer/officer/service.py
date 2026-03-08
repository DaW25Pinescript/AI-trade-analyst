"""Officer service — top-level orchestrator for building market packets.

Orchestrates: loader -> quality -> features -> summarizer -> packet assembly.
Does not implement any of the above directly — delegates to each module.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

from .contracts import (
    ActiveFVGZone,
    FeatureBlock,
    LiquidityNearest,
    LiquidityTimeframeSummary,
    MarketPacket,
    MarketPacketV2,
    QualityBlock,
    StructureBlock,
    StructureRecentEvent,
    StructureRegime,
)
from .features import compute_core_features
from .loader import EXPECTED_TIMEFRAMES, PACKAGES_DIR, load_all_timeframes, load_manifest
from .quality import check_package_quality
from .summarizer import build_state_summary
from structure.reader import load_structure_summary, structure_is_available
from instrument_registry import INSTRUMENT_REGISTRY

# Derive trust sets from the central registry
TRUSTED_INSTRUMENTS = {
    sym for sym, meta in INSTRUMENT_REGISTRY.items()
    if meta.trust_level == "trusted"
}
PROVISIONAL_INSTRUMENTS = {
    sym for sym, meta in INSTRUMENT_REGISTRY.items()
    if meta.trust_level == "provisional"
}


@dataclass
class ValidationResult:
    """Result of manifest validation."""

    valid: bool
    instrument: str
    flags: list[str]
    manifest: dict | None = None


def validate_package_manifest(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
) -> ValidationResult:
    """Validate a hot package manifest without building a full packet.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        ValidationResult with validity status and any flags.
    """
    flags: list[str] = []
    try:
        manifest = load_manifest(instrument, packages_dir)
    except FileNotFoundError as e:
        return ValidationResult(
            valid=False,
            instrument=instrument,
            flags=["manifest_not_found"],
            manifest=None,
        )

    if manifest.get("instrument") != instrument:
        flags.append("instrument_mismatch")
    if "as_of_utc" not in manifest:
        flags.append("missing_as_of_utc")
    if "windows" not in manifest:
        flags.append("missing_windows")

    return ValidationResult(
        valid=len(flags) == 0,
        instrument=instrument,
        flags=flags,
        manifest=manifest,
    )


def _build_timeframe_rows(df: pd.DataFrame) -> list:
    """Convert a DataFrame to list-of-dicts row format for the packet.

    Args:
        df: OHLCV DataFrame with DatetimeIndex.

    Returns:
        List of row dicts with timestamp_utc, open, high, low, close, volume.
    """
    rows = []
    for ts, row in df.iterrows():
        ts_str = ts.isoformat().replace("+00:00", "Z")
        rows.append({
            "timestamp_utc": ts_str,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return rows


def _assemble_regime(packets: dict[str, dict]) -> StructureRegime | None:
    """Assemble regime from structure packets with 4h -> 1h -> 15m preference."""
    for preferred_tf in ("4h", "1h", "15m"):
        if preferred_tf in packets and packets[preferred_tf]:
            regime_data = packets[preferred_tf].get("regime")
            if regime_data:
                return StructureRegime(
                    bias=regime_data.get("bias", "neutral"),
                    last_bos_direction=regime_data.get("last_bos_direction"),
                    last_mss_direction=regime_data.get("last_mss_direction"),
                    trend_state=regime_data.get("trend_state", "unknown"),
                    structure_quality=regime_data.get("structure_quality", "unknown"),
                    source_timeframe=preferred_tf,
                )
    return None


def _assemble_recent_events(
    packets: dict[str, dict],
    max_events: int = 5,
) -> list[StructureRecentEvent]:
    """Collect last N BOS/MSS events across all timeframes, sorted by time desc."""
    all_events = []
    valid_types = {"bos_bull", "bos_bear", "mss_bull", "mss_bear"}
    for tf, packet in packets.items():
        for event in packet.get("events", []):
            event_type = event.get("type", "")
            if event_type in valid_types:
                all_events.append(StructureRecentEvent(
                    type=event_type,
                    time=event.get("time", ""),
                    timeframe=tf,
                    reference_price=event.get("reference_price", 0.0),
                ))
    all_events.sort(key=lambda e: e.time, reverse=True)
    return all_events[:max_events]


def _to_liquidity_nearest(level: dict | None) -> LiquidityNearest | None:
    """Convert a raw liquidity level dict to LiquidityNearest."""
    if level is None:
        return None
    return LiquidityNearest(
        type=level.get("type", "unknown"),
        price=level.get("price", 0.0),
        scope=level.get("liquidity_scope", "unclassified"),
        status=level.get("status", "active"),
    )


def _assemble_liquidity_summary(
    packets: dict[str, dict],
    current_price: float,
) -> dict[str, LiquidityTimeframeSummary]:
    """Build per-timeframe liquidity summary with nearest above/below."""
    summary = {}
    for tf, packet in packets.items():
        active_levels = [
            level for level in packet.get("liquidity", [])
            if level.get("status") == "active"
        ]
        above = [l for l in active_levels if l.get("price", 0) > current_price]
        below = [l for l in active_levels if l.get("price", 0) < current_price]

        nearest_above = (
            min(above, key=lambda l: l["price"] - current_price) if above else None
        )
        nearest_below = (
            max(below, key=lambda l: l["price"]) if below else None
        )

        summary[tf] = LiquidityTimeframeSummary(
            active_count=len(active_levels),
            nearest_above=_to_liquidity_nearest(nearest_above),
            nearest_below=_to_liquidity_nearest(nearest_below),
        )
    return summary


def _assemble_active_fvg_zones(
    packets: dict[str, dict],
    current_price: float,
) -> list[ActiveFVGZone]:
    """Collect open and partially_filled FVG zones, sorted by proximity to price."""
    zones = []
    valid_statuses = {"open", "partially_filled"}

    for tf, packet in packets.items():
        # FVGs may be in imbalance list or active_zones
        fvg_list = packet.get("imbalance", [])
        for fvg in fvg_list:
            if fvg.get("status") in valid_statuses:
                zones.append(ActiveFVGZone(
                    id=fvg.get("id", ""),
                    fvg_type=fvg.get("fvg_type", ""),
                    zone_high=fvg.get("zone_high", 0.0),
                    zone_low=fvg.get("zone_low", 0.0),
                    zone_size=fvg.get("zone_size", 0.0),
                    status=fvg.get("status", ""),
                    timeframe=tf,
                    origin_time=fvg.get("origin_time", ""),
                ))

    # Sort by proximity to current price (midpoint distance)
    zones.sort(key=lambda z: abs(current_price - (z.zone_high + z.zone_low) / 2))
    return zones


def assemble_structure_block(
    instrument: str,
    structure_output_dir: Path | None = None,
    current_price: float = 0.0,
    available_timeframes: tuple[str, ...] | None = None,
) -> StructureBlock:
    """Assemble a StructureBlock from structure engine outputs.

    Args:
        instrument: Instrument symbol.
        structure_output_dir: Optional custom structure output directory.
        current_price: Current price for proximity-based sorting.
        available_timeframes: Timeframes to load. Defaults to (15m, 1h, 4h).

    Returns:
        Populated StructureBlock.
    """
    tfs = available_timeframes or ("15m", "1h", "4h")

    kwargs = {}
    if structure_output_dir is not None:
        kwargs["output_dir"] = structure_output_dir

    packets = load_structure_summary(instrument, timeframes=tfs, **kwargs)

    if not packets:
        return StructureBlock.unavailable()

    # Find the most recent as_of across all packets
    as_of_values = []
    engine_version = None
    for p in packets.values():
        as_of_val = p.get("as_of", "")
        if as_of_val:
            as_of_values.append(as_of_val if isinstance(as_of_val, str) else str(as_of_val))
        build_info = p.get("build", {})
        if build_info.get("engine_version"):
            engine_version = build_info["engine_version"]

    latest_as_of = max(as_of_values) if as_of_values else None

    regime = _assemble_regime(packets)
    recent_events = _assemble_recent_events(packets)
    liquidity = _assemble_liquidity_summary(packets, current_price)
    active_fvg_zones = _assemble_active_fvg_zones(packets, current_price)

    return StructureBlock(
        available=True,
        source_engine_version=engine_version,
        as_of=latest_as_of,
        regime=regime,
        recent_events=recent_events,
        liquidity=liquidity,
        active_fvg_zones=active_fvg_zones,
    )


def build_market_packet(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
    structure_output_dir: Path | None = None,
) -> MarketPacketV2:
    """Build a complete Market Packet v2 for the given instrument.

    Orchestrates the full pipeline: load -> quality check -> features -> summary
    -> structure assembly -> packet.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.
        structure_output_dir: Optional custom structure output directory.

    Returns:
        MarketPacketV2 instance ready for serialization.
    """
    now_utc = datetime.now(timezone.utc)
    as_of_utc = now_utc.isoformat().replace("+00:00", "Z")

    # Determine instrument trust level
    is_trusted = instrument in TRUSTED_INSTRUMENTS
    is_provisional = instrument in PROVISIONAL_INSTRUMENTS
    instrument_verified = is_trusted

    # For unverified/provisional instruments, check if data exists
    # If no data, return a minimal packet with appropriate quality flags
    if not instrument_verified:
        quality_label = "unverified"
        quality_flags = ["instrument_not_verified"]

        # Try to load data anyway — it may exist even if unverified
        try:
            manifest = load_manifest(instrument, packages_dir)
            quality_block = check_package_quality(instrument, packages_dir, now_utc)
            quality_block.flags.insert(0, "instrument_not_verified")
        except FileNotFoundError:
            # No data at all — return minimal packet
            from .contracts import CoreFeatures, StateSummary

            return MarketPacketV2(
                instrument=instrument,
                as_of_utc=as_of_utc,
                source={
                    "vendor": "dukascopy",
                    "canonical_tf": "1m",
                    "quality": "unverified",
                },
                timeframes={},
                features=FeatureBlock(
                    core=CoreFeatures(
                        atr_14=0.0,
                        volatility_regime="normal",
                        momentum=0.0,
                        ma_50=0.0,
                        ma_200=0.0,
                        swing_high=0.0,
                        swing_low=0.0,
                        rolling_range=0.0,
                        session_context="asian",
                    ),
                ),
                state_summary=StateSummary(
                    trend_1h="neutral",
                    trend_4h="neutral",
                    trend_1d="neutral",
                    volatility_regime="normal",
                    momentum_state="flat",
                    session_context="asian",
                    data_quality="unverified",
                ),
                quality=QualityBlock(
                    manifest_valid=False,
                    all_timeframes_present=False,
                    staleness_minutes=0,
                    stale=False,
                    partial=True,
                    flags=["instrument_not_verified", "no_data_available"],
                ),
                structure=StructureBlock.unavailable(),
            )
    else:
        quality_block = check_package_quality(instrument, packages_dir, now_utc)

    # Determine overall data quality
    if not instrument_verified:
        data_quality = "unverified"
        source_quality = "unverified"
    elif quality_block.stale:
        data_quality = "stale"
        source_quality = "stale"
    elif quality_block.partial:
        data_quality = "partial"
        source_quality = "partial"
    else:
        data_quality = "validated"
        source_quality = "validated"

    # Load all timeframes
    timeframes_data = load_all_timeframes(instrument, packages_dir)

    # Build timeframe section for packet
    timeframes_packet: Dict[str, dict] = {}
    for tf in EXPECTED_TIMEFRAMES:
        if tf in timeframes_data:
            df = timeframes_data[tf]
            timeframes_packet[tf] = {
                "count": len(df),
                "rows": _build_timeframe_rows(df),
            }

    # Compute core features from 1h bars
    df_1h = timeframes_data.get("1h", pd.DataFrame())
    core_features = compute_core_features(df_1h, as_of_utc=now_utc)

    # Build state summary
    state_summary = build_state_summary(
        core_features, timeframes_data, data_quality=data_quality
    )

    # Log quality issues
    for flag in quality_block.flags:
        print(f"[officer] WARNING: quality flag: {flag}")

    # Assemble structure block
    struct_kwargs = {}
    if structure_output_dir is not None:
        struct_kwargs["structure_output_dir"] = structure_output_dir

    # Get current price for proximity sorting
    current_price = 0.0
    if not df_1h.empty:
        current_price = float(df_1h["close"].iloc[-1])

    if structure_is_available(instrument, **({"output_dir": structure_output_dir} if structure_output_dir else {})):
        structure_block = assemble_structure_block(
            instrument,
            structure_output_dir=structure_output_dir,
            current_price=current_price,
        )
    else:
        structure_block = StructureBlock.unavailable()

    return MarketPacketV2(
        instrument=instrument,
        as_of_utc=as_of_utc,
        source={
            "vendor": "dukascopy",
            "canonical_tf": "1m",
            "quality": source_quality,
        },
        timeframes=timeframes_packet,
        features=FeatureBlock(core=core_features),
        state_summary=state_summary,
        quality=quality_block,
        structure=structure_block,
    )


def refresh_from_latest_exports(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
) -> MarketPacketV2:
    """Re-read latest exports and build a fresh market packet.

    Equivalent to build_market_packet but named for clarity when used
    after a feed pipeline run.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        Freshly built MarketPacketV2.
    """
    return build_market_packet(instrument, packages_dir)


def write_packet(packet: MarketPacket | MarketPacketV2, output_dir: Path) -> Path:
    """Write a market packet to JSON file.

    Args:
        packet: MarketPacket or MarketPacketV2 to serialize.
        output_dir: Directory to write the JSON file.

    Returns:
        Path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{packet.instrument}_market_packet.json"
    output_path.write_text(json.dumps(packet.to_dict(), indent=2))
    return output_path
