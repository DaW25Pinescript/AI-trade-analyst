"""Read-side quality checks for hot package data.

Validates manifest integrity, timeframe completeness, staleness,
and data sanity before the Officer builds any market packet.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .contracts import QualityBlock
from .loader import EXPECTED_TIMEFRAMES, PACKAGES_DIR, get_expected_timeframes, load_manifest, load_timeframe

# Staleness threshold in minutes during assumed market hours
STALENESS_THRESHOLD_MINUTES = 60

# Minimum row counts per timeframe for a package to be considered valid
MIN_ROW_COUNTS = {
    "1m": 100,
    "5m": 20,
    "15m": 10,
    "1h": 5,
    "4h": 2,
    "1d": 1,
}


def _compute_staleness(
    instrument: str,
    timeframes_data: Dict[str, pd.DataFrame],
    now_utc: datetime,
) -> tuple[int, bool]:
    """Compute staleness from highest-resolution available timeframe.

    Preference order: 5m > 15m > 1h > 4h > 1d
    Returns (staleness_minutes, is_stale).
    """
    for tf in ("5m", "15m", "1h", "4h", "1d"):
        if tf in timeframes_data and not timeframes_data[tf].empty:
            last_bar = timeframes_data[tf].index[-1].to_pydatetime()
            if last_bar.tzinfo is None:
                last_bar = last_bar.replace(tzinfo=timezone.utc)
            minutes = int((now_utc - last_bar).total_seconds() / 60)
            return minutes, minutes > STALENESS_THRESHOLD_MINUTES
    return 0, False


def check_package_quality(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
    now_utc: Optional[datetime] = None,
    timeframes_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> QualityBlock:
    """Run all read-side quality checks on a hot package.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.
        now_utc: Override current time for testing. Defaults to now.
        timeframes_data: Pre-loaded timeframes dict (from PriceStore path).
            If provided, skips CSV file checks and uses this data directly.

    Returns:
        QualityBlock with all check results populated.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    flags: list[str] = []
    manifest_valid = False
    all_present = True
    staleness_minutes = 0
    stale = False
    partial = False

    expected_tfs = get_expected_timeframes(instrument)

    # PriceStore path: timeframes_data already loaded
    if timeframes_data is not None:
        manifest_valid = True  # No manifest in PriceStore path

        for tf in expected_tfs:
            if tf not in timeframes_data or timeframes_data[tf].empty:
                all_present = False
                partial = True
                flags.append(f"{tf}_missing")
                continue

            df = timeframes_data[tf]

            # Row count check
            min_rows = MIN_ROW_COUNTS.get(tf, 1)
            if len(df) < min_rows:
                flags.append(f"{tf}_insufficient_rows")

            # Monotonic timestamp check
            if not df.index.is_monotonic_increasing:
                flags.append(f"{tf}_not_monotonic")

            # Duplicate timestamp check
            if df.index.duplicated().any():
                flags.append(f"{tf}_duplicate_timestamps")

        # Staleness from highest-resolution available TF
        staleness_minutes, stale = _compute_staleness(instrument, timeframes_data, now_utc)
        if stale:
            flags.append("stale")

        return QualityBlock(
            manifest_valid=manifest_valid,
            all_timeframes_present=all_present,
            staleness_minutes=staleness_minutes,
            stale=stale,
            partial=partial,
            flags=flags,
        )

    # Legacy CSV path: check manifest and files
    try:
        manifest = load_manifest(instrument, packages_dir)
        manifest_valid = True
    except FileNotFoundError:
        raise  # Hard failure per CONSTRAINTS.md

    # Check manifest fields
    if "instrument" not in manifest or "as_of_utc" not in manifest:
        manifest_valid = False
        flags.append("manifest_missing_fields")

    # Check all timeframe CSVs exist and load
    csv_timeframes_data: Dict[str, pd.DataFrame] = {}
    for tf in EXPECTED_TIMEFRAMES:
        csv_path = packages_dir / f"{instrument}_{tf}_latest.csv"
        if not csv_path.exists():
            all_present = False
            partial = True
            flags.append(f"{tf}_missing")
            continue

        try:
            df = load_timeframe(instrument, tf, packages_dir)
            csv_timeframes_data[tf] = df
        except Exception as e:
            all_present = False
            partial = True
            flags.append(f"{tf}_corrupt")
            print(f"[quality] WARNING: {tf} failed to load: {e}")
            continue

        # Row count check
        min_rows = MIN_ROW_COUNTS.get(tf, 1)
        if len(df) < min_rows:
            flags.append(f"{tf}_insufficient_rows")

        # Monotonic timestamp check
        if not df.index.is_monotonic_increasing:
            flags.append(f"{tf}_not_monotonic")

        # Duplicate timestamp check
        if df.index.duplicated().any():
            flags.append(f"{tf}_duplicate_timestamps")

    # Staleness check — use highest-resolution available TF
    staleness_minutes, stale = _compute_staleness(instrument, csv_timeframes_data, now_utc)
    if stale:
        flags.append("stale")

    return QualityBlock(
        manifest_valid=manifest_valid,
        all_timeframes_present=all_present,
        staleness_minutes=staleness_minutes,
        stale=stale,
        partial=partial,
        flags=flags,
    )
