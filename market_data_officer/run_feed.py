"""CLI entry point for the market data feed pipeline."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _seed_fixture(instrument: str) -> None:
    """Write a minimal valid hot package fixture for dev/test use.

    Uses the same manifest/CSV shape as conftest.hot_packages_dir so the
    officer's standard loader path works unchanged.
    """
    from feed.config import PACKAGES_DIR, HOT_WINDOW_SIZES

    PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Instrument-keyed fixture parameters
    _FIXTURE_PARAMS = {
        "EURUSD": {"base_price": 1.0850, "volatility": 0.0005, "volume_range": (100, 5000)},
        "XAUUSD": {"base_price": 2700.0, "volatility": 2.0, "volume_range": (0.1, 10.0)},
    }
    # XAUUSD uses only the 4 analyst-target timeframes
    _XAUUSD_TIMEFRAMES = {"15m", "1h", "4h", "1d"}

    params = _FIXTURE_PARAMS.get(instrument, _FIXTURE_PARAMS["EURUSD"])
    base_price = params["base_price"]
    volatility = params["volatility"]
    vol_lo, vol_hi = params["volume_range"]

    rng = np.random.RandomState(42)
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    all_tf_configs = {
        "1m": ("1min", HOT_WINDOW_SIZES["1m"]),
        "5m": ("5min", HOT_WINDOW_SIZES["5m"]),
        "15m": ("15min", HOT_WINDOW_SIZES["15m"]),
        "1h": ("1h", HOT_WINDOW_SIZES["1h"]),
        "4h": ("4h", HOT_WINDOW_SIZES["4h"]),
        "1d": ("1D", HOT_WINDOW_SIZES["1d"]),
    }
    # Filter to target timeframes for this instrument
    tf_configs = {
        k: v for k, v in all_tf_configs.items()
        if instrument != "XAUUSD" or k in _XAUUSD_TIMEFRAMES
    }

    windows_manifest: dict = {}
    for tf_label, (freq, count) in tf_configs.items():
        index = pd.date_range(end=now_utc, periods=count, freq=freq, tz="UTC")
        returns = rng.normal(0, volatility, count)
        close = base_price + np.cumsum(returns)
        high = close + rng.uniform(0, volatility * 2, count)
        low = close - rng.uniform(0, volatility * 2, count)
        open_ = close + rng.normal(0, volatility * 0.5, count)
        volume = rng.uniform(vol_lo, vol_hi, count)

        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=index,
        )
        df.index.name = "timestamp_utc"

        filename = f"{instrument}_{tf_label}_latest.csv"
        df.to_csv(PACKAGES_DIR / filename)
        windows_manifest[tf_label] = {"count": count, "file": filename}

    manifest = {
        "instrument": instrument,
        "as_of_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema": "timestamp_utc,open,high,low,close,volume",
        "windows": windows_manifest,
    }
    (PACKAGES_DIR / f"{instrument}_hot.json").write_text(json.dumps(manifest, indent=2))
    print(f"[fixture] Wrote {instrument} hot package to {PACKAGES_DIR}")


def main() -> None:
    """Run the market data feed pipeline from the command line."""
    parser = argparse.ArgumentParser(
        description="Market Data Officer Feed — ingestion spine (EURUSD, XAUUSD)",
    )
    parser.add_argument(
        "--instrument",
        type=str,
        required=True,
        help="Instrument symbol (e.g. EURUSD)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--save-raw",
        action="store_true",
        default=False,
        help="Cache raw bi5 files to disk",
    )
    parser.add_argument(
        "--gap-report",
        action="store_true",
        default=False,
        help="Generate gap detection report after ingestion",
    )
    parser.add_argument(
        "--hot-only",
        action="store_true",
        default=False,
        help="Skip fetching — rebuild derived timeframes and hot packages from existing canonical",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        default=False,
        help="Generate cache diagnostics report (per-hour fetch/decode audit trail)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        default=False,
        help="Seed a synthetic hot package fixture for dev/test (no network required)",
    )

    args = parser.parse_args()

    if args.fixture:
        _seed_fixture(args.instrument)
        return

    if not args.start_date or not args.end_date:
        parser.error("--start-date and --end-date are required (unless using --fixture)")

    try:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        print(f"Error parsing dates: {exc}")
        sys.exit(1)

    if end < start:
        print("Error: end-date must be >= start-date")
        sys.exit(1)

    # Import here to avoid import errors when just running --help
    from feed.pipeline import run_pipeline

    run_pipeline(
        symbol=args.instrument,
        start_date=start,
        end_date=end,
        save_raw=args.save_raw,
        gap_report=args.gap_report,
        hot_only=args.hot_only,
        diagnostics=args.diagnostics,
    )


if __name__ == "__main__":
    main()
