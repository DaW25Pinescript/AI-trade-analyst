"""Package loader — reads hot package CSVs and manifests from the feed's export layer.

The Officer reads exclusively from market_data/packages/latest/.
It never reads raw Parquet or calls any feed pipeline functions.
"""

import json
from pathlib import Path
from typing import Dict

import pandas as pd

# Default hot package directory (matches feed config)
PACKAGES_DIR = Path("market_data/packages/latest")

EXPECTED_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]


def load_manifest(instrument: str, packages_dir: Path = PACKAGES_DIR) -> dict:
    """Load and parse the JSON manifest for an instrument's hot package.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        Parsed manifest dict with keys: instrument, as_of_utc, schema, windows.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
    """
    manifest_path = packages_dir / f"{instrument}_hot.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Hot package manifest not found for {instrument}. "
            f"Has the feed pipeline run? Expected: {manifest_path}"
        )
    return json.loads(manifest_path.read_text())


def load_timeframe(
    instrument: str,
    tf: str,
    packages_dir: Path = PACKAGES_DIR,
) -> pd.DataFrame:
    """Load a single timeframe CSV from the hot package.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        tf: Timeframe label, e.g. '1h'.
        packages_dir: Path to the hot packages directory.

    Returns:
        UTC-aware DataFrame with DatetimeIndex and OHLCV columns.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
    csv_path = packages_dir / f"{instrument}_{tf}_latest.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Hot package CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)

    # Ensure UTC-aware index
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")

    df.index.name = "timestamp_utc"
    return df


def load_all_timeframes(
    instrument: str,
    packages_dir: Path = PACKAGES_DIR,
) -> Dict[str, pd.DataFrame]:
    """Load all available timeframe DataFrames for an instrument.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        packages_dir: Path to the hot packages directory.

    Returns:
        Dict mapping timeframe label to DataFrame. Missing timeframes are omitted.
    """
    result = {}
    for tf in EXPECTED_TIMEFRAMES:
        try:
            result[tf] = load_timeframe(instrument, tf, packages_dir)
        except FileNotFoundError:
            continue
    return result
