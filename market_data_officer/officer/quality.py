"""Read-side quality checks for hot package data.

Validates manifest integrity, timeframe completeness, staleness,
and data sanity before the Officer builds any market packet.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .contracts import QualityBlock
from .loader import EXPECTED_TIMEFRAMES, PACKAGES_DIR, load_manifest, load_timeframe

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


def check_package_quality(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
    now_utc: Optional[datetime] = None,
) -> QualityBlock:
    """Run all read-side quality checks on a hot package.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.
        now_utc: Override current time for testing. Defaults to now.

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

    # Check manifest
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
    for tf in EXPECTED_TIMEFRAMES:
        csv_path = packages_dir / f"{instrument}_{tf}_latest.csv"
        if not csv_path.exists():
            all_present = False
            partial = True
            flags.append(f"{tf}_missing")
            continue

        try:
            df = load_timeframe(instrument, tf, packages_dir)
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

    # Staleness check — based on 1m file's last bar
    try:
        df_1m = load_timeframe(instrument, "1m", packages_dir)
        if not df_1m.empty:
            last_bar_utc = df_1m.index[-1].to_pydatetime()
            if last_bar_utc.tzinfo is None:
                last_bar_utc = last_bar_utc.replace(tzinfo=timezone.utc)
            staleness_minutes = int(
                (now_utc - last_bar_utc).total_seconds() / 60
            )
            if staleness_minutes > STALENESS_THRESHOLD_MINUTES:
                stale = True
                flags.append("stale")
    except FileNotFoundError:
        pass  # Already flagged as missing above

    return QualityBlock(
        manifest_valid=manifest_valid,
        all_timeframes_present=all_present,
        staleness_minutes=staleness_minutes,
        stale=stale,
        partial=partial,
        flags=flags,
    )
