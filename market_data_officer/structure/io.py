"""I/O utilities — load derived bars and write JSON structure packets.

The Structure Engine reads from hot package CSVs (same source as the Officer)
in market_data/packages/latest/. It writes JSON packets to structure/output/.
"""

import json
import os
from pathlib import Path

import pandas as pd

# Default paths relative to repo root
PACKAGES_DIR = Path("market_data/packages/latest")
OUTPUT_DIR = Path("market_data_officer/structure/output")


def load_bars(
    instrument: str,
    timeframe: str,
    packages_dir: Path = PACKAGES_DIR,
) -> pd.DataFrame:
    """Load OHLCV bars for an instrument and timeframe from hot packages.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        timeframe: Timeframe label, e.g. '1h'.
        packages_dir: Path to the hot packages directory.

    Returns:
        UTC-aware DataFrame with DatetimeIndex and OHLCV columns.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If data is empty or malformed.
    """
    csv_path = packages_dir / f"{instrument}_{timeframe}_latest.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Hot package CSV not found: {csv_path}. "
            f"Has the feed pipeline run?"
        )

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)

    if df.empty:
        raise ValueError(f"Empty data file: {csv_path}")

    # Ensure UTC-aware index
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")

    df.index.name = "timestamp_utc"

    required_cols = {"open", "high", "low", "close", "volume"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {csv_path}: {missing}")

    return df


def write_packet_atomic(packet: dict, path: str) -> None:
    """Write a structure packet to JSON atomically.

    Writes to a temp file first, then renames to avoid partial writes.

    Args:
        packet: Serialized structure packet dictionary.
        path: Target file path.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, default=str)
    os.replace(tmp, path)


def get_output_path(
    instrument: str,
    timeframe: str,
    output_dir: Path = OUTPUT_DIR,
) -> str:
    """Get the output file path for a structure packet.

    Args:
        instrument: Instrument symbol, e.g. 'EURUSD'.
        timeframe: Timeframe label, e.g. '1h'.
        output_dir: Directory for output files.

    Returns:
        Full file path string.
    """
    filename = f"{instrument.lower()}_{timeframe}_structure.json"
    return str(output_dir / filename)
