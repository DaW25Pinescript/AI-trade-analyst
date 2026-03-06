"""Export layer — writes hot package CSVs and JSON manifest."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

from .config import HOT_WINDOW_SIZES, PACKAGES_DIR
from .validate import validate_ohlcv


def export_hot_packages(
    dataframes: Dict[str, pd.DataFrame],
    symbol: str,
    output_dir: Path = PACKAGES_DIR,
) -> None:
    """Export rolling tail CSVs and a JSON manifest for agent consumption.

    dataframes: mapping from timeframe label (e.g. "1m", "5m") to DataFrame.
    Only OHLCV columns are exported in the CSVs (no metadata columns).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    ohlcv_cols = ["open", "high", "low", "close", "volume"]
    windows_manifest: Dict[str, dict] = {}

    for tf_label, df in dataframes.items():
        if df.empty:
            continue

        max_rows = HOT_WINDOW_SIZES.get(tf_label, len(df))
        tail = df.tail(max_rows)

        # Export only OHLCV columns
        export_df = tail[ohlcv_cols] if all(c in tail.columns for c in ohlcv_cols) else tail

        filename = f"{symbol}_{tf_label}_latest.csv"
        filepath = output_dir / filename

        validate_ohlcv(export_df, f"hot_{tf_label}")
        export_df.to_csv(filepath)

        windows_manifest[tf_label] = {
            "count": len(export_df),
            "file": filename,
        }

    # Write JSON manifest
    manifest = {
        "instrument": symbol,
        "as_of_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": "timestamp_utc,open,high,low,close,volume",
        "windows": windows_manifest,
    }

    manifest_path = output_dir / f"{symbol}_hot.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[export] wrote manifest: {manifest_path}")
