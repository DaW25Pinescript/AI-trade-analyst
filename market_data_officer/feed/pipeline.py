"""Pipeline orchestration — ties fetch, decode, aggregate, validate, resample, export."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .aggregate import ticks_to_1m_ohlcv
from .config import (
    CANONICAL_DIR,
    DERIVED_DIR,
    DERIVED_TIMEFRAMES,
    INSTRUMENTS,
    PACKAGES_DIR,
    TIMEFRAME_LABELS,
    InstrumentMeta,
)
from .decode import decode_dukascopy_ticks
from .export import export_hot_packages
from .fetch import fetch_bi5
from .resample import resample_from_1m
from .validate import validate_ohlcv


def _load_existing_canonical(symbol: str) -> Optional[pd.DataFrame]:
    """Load existing canonical parquet if it exists."""
    path = CANONICAL_DIR / f"{symbol}_1m.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index, utc=True)
        return df
    return None


def _save_canonical(df: pd.DataFrame, symbol: str) -> None:
    """Save canonical 1m OHLCV to parquet with validation."""
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    validate_ohlcv(df, f"canonical_{symbol}_1m")
    path = CANONICAL_DIR / f"{symbol}_1m.parquet"
    df.to_parquet(path, compression="zstd")
    print(f"[pipeline] saved canonical: {path} ({len(df)} bars)")


def _save_derived(df: pd.DataFrame, symbol: str, tf_label: str) -> None:
    """Save a derived timeframe as both parquet and CSV."""
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    validate_ohlcv(df[["open", "high", "low", "close", "volume"]], f"derived_{symbol}_{tf_label}")

    parquet_path = DERIVED_DIR / f"{symbol}_{tf_label}.parquet"
    csv_path = DERIVED_DIR / f"{symbol}_{tf_label}.csv"

    df.to_parquet(parquet_path, compression="zstd")
    df.to_csv(csv_path)
    print(f"[pipeline] saved derived {tf_label}: {parquet_path} ({len(df)} bars)")


def run_pipeline(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    save_raw: bool = False,
) -> None:
    """Run the full ingestion pipeline for one instrument over a date range.

    1. Load existing canonical data (if any) for incremental append
    2. Fetch + decode + aggregate new hourly data
    3. Merge with existing, deduplicate, validate, save canonical
    4. Derive higher timeframes
    5. Export hot packages
    """
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unknown instrument: {symbol}. Available: {list(INSTRUMENTS.keys())}")

    meta = INSTRUMENTS[symbol]

    # Load existing canonical for incremental logic
    existing = _load_existing_canonical(symbol)
    last_ts: Optional[pd.Timestamp] = None
    if existing is not None and not existing.empty:
        last_ts = existing.index[-1]
        print(f"[pipeline] existing canonical ends at {last_ts} ({len(existing)} bars)")

    # Generate all hours in range
    all_bars: list[pd.DataFrame] = []
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    end = end_date.replace(hour=23, minute=0, second=0, microsecond=0)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    fetch_count = 0
    skip_count = 0

    while current <= end:
        # Incremental: skip hours already covered
        if last_ts is not None:
            hour_end = current + timedelta(minutes=59)
            if hour_end <= last_ts:
                skip_count += 1
                current += timedelta(hours=1)
                continue

        try:
            raw = fetch_bi5(symbol, current, save_raw=save_raw)
            fetch_count += 1

            if raw:
                ticks = decode_dukascopy_ticks(raw, current, meta)
                if not ticks.empty:
                    bars = ticks_to_1m_ohlcv(ticks)
                    if not bars.empty:
                        all_bars.append(bars)
        except Exception as exc:
            print(f"[pipeline] error at {current}: {exc}")

        current += timedelta(hours=1)

    print(f"[pipeline] fetched {fetch_count} hours, skipped {skip_count} already-ingested")

    if not all_bars and existing is None:
        print("[pipeline] no data fetched and no existing canonical — nothing to do")
        return

    # Merge new bars
    if all_bars:
        new_df = pd.concat(all_bars)
        new_df = new_df.sort_index()
        new_df = new_df[~new_df.index.duplicated(keep="first")]

        # Add metadata columns
        new_df["vendor"] = "dukascopy"
        new_df["build_method"] = "tick_to_1m"
        new_df["quality_flag"] = "ok"

        if existing is not None and not existing.empty:
            combined = pd.concat([existing, new_df])
            combined = combined[~combined.index.duplicated(keep="first")]
            combined = combined.sort_index()
            canonical = combined
        else:
            canonical = new_df
    else:
        canonical = existing

    # Save canonical
    _save_canonical(canonical, symbol)

    # Strip metadata for OHLCV-only operations
    canonical_ohlcv = canonical[["open", "high", "low", "close", "volume"]]

    # Derive higher timeframes
    hot_dfs = {"1m": canonical_ohlcv}

    for rule in DERIVED_TIMEFRAMES:
        tf_label = TIMEFRAME_LABELS[rule]
        derived = resample_from_1m(canonical_ohlcv, rule)
        if not derived.empty:
            _save_derived(derived, symbol, tf_label)
            hot_dfs[tf_label] = derived[["open", "high", "low", "close", "volume"]]

    # Export hot packages
    export_hot_packages(hot_dfs, symbol)

    print(f"[pipeline] pipeline complete for {symbol}")
