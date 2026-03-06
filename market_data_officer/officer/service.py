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

from .contracts import FeatureBlock, MarketPacket, QualityBlock
from .features import compute_core_features
from .loader import EXPECTED_TIMEFRAMES, PACKAGES_DIR, load_all_timeframes, load_manifest
from .quality import check_package_quality
from .summarizer import build_state_summary

# Instruments verified through Phase 1A (EURUSD) and Phase 1B (XAUUSD)
TRUSTED_INSTRUMENTS = {"EURUSD", "XAUUSD"}
PROVISIONAL_INSTRUMENTS: set[str] = set()


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


def build_market_packet(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
) -> MarketPacket:
    """Build a complete Market Packet v1 for the given instrument.

    Orchestrates the full pipeline: load -> quality check -> features -> summary -> packet.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        MarketPacket instance ready for serialization.
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

            return MarketPacket(
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

    return MarketPacket(
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
    )


def refresh_from_latest_exports(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
) -> MarketPacket:
    """Re-read latest exports and build a fresh market packet.

    Equivalent to build_market_packet but named for clarity when used
    after a feed pipeline run.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        Freshly built MarketPacket.
    """
    return build_market_packet(instrument, packages_dir)


def write_packet(packet: MarketPacket, output_dir: Path) -> Path:
    """Write a market packet to JSON file.

    Args:
        packet: MarketPacket to serialize.
        output_dir: Directory to write the JSON file.

    Returns:
        Path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{packet.instrument}_market_packet.json"
    output_path.write_text(json.dumps(packet.to_dict(), indent=2))
    return output_path
