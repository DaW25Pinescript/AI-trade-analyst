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
from .decode import decode_dukascopy_ticks, decode_with_diagnostics
from .diagnostics import DiagnosticsCollector, save_cache_inventory, verify_decode_assumptions
from .export import export_hot_packages
from .fetch import build_bi5_url, fetch_bi5, fetch_bi5_detailed
from .gaps import generate_gap_report, save_gap_report
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


def _load_existing_derived(symbol: str, tf_label: str) -> Optional[pd.DataFrame]:
    """Load existing derived parquet if it exists."""
    path = DERIVED_DIR / f"{symbol}_{tf_label}.parquet"
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


def _derive_affected_window(
    canonical_ohlcv: pd.DataFrame,
    symbol: str,
    rule: str,
    tf_label: str,
    new_data_start: Optional[pd.Timestamp],
) -> Optional[pd.DataFrame]:
    """Derive a single higher timeframe, regenerating only the affected window.

    If new_data_start is provided and existing derived data exists, only
    resample the canonical slice from the affected boundary onwards, then
    merge with the unaffected prefix of existing derived data.

    Returns the full derived DataFrame or None if empty.
    """
    if canonical_ohlcv.empty:
        return None

    existing_derived = _load_existing_derived(symbol, tf_label)

    # If no new data or no existing derived, do a full resample
    if new_data_start is None or existing_derived is None or existing_derived.empty:
        derived = resample_from_1m(canonical_ohlcv, rule)
        return derived if not derived.empty else None

    # Find the derived bar boundary that contains new_data_start.
    # Resample a tiny slice to find where the boundary falls.
    boundary = _find_resample_boundary(new_data_start, rule)

    # Split existing derived into unaffected prefix and affected suffix
    unaffected = existing_derived[existing_derived.index < boundary]

    # Resample only the canonical data from the boundary onwards
    affected_canonical = canonical_ohlcv[canonical_ohlcv.index >= boundary]
    if affected_canonical.empty:
        return existing_derived

    new_derived = resample_from_1m(affected_canonical, rule)
    if new_derived.empty:
        return existing_derived if not existing_derived.empty else None

    # Merge: unaffected prefix + newly resampled suffix
    if unaffected.empty:
        derived = new_derived
    else:
        derived = pd.concat([unaffected, new_derived])
        derived = derived[~derived.index.duplicated(keep="last")]
        derived = derived.sort_index()

    return derived if not derived.empty else None


def _find_resample_boundary(ts: pd.Timestamp, rule: str) -> pd.Timestamp:
    """Find the start of the resample period containing ts.

    For example, if ts is 14:23 and rule is "1h", returns 14:00.
    """
    # Strip tzinfo to avoid pandas "Cannot pass datetime with tzinfo with tz param"
    dt = ts.to_pydatetime().replace(tzinfo=None)

    if rule == "5min":
        minute = (dt.minute // 5) * 5
        result = dt.replace(minute=minute, second=0, microsecond=0)
    elif rule == "15min":
        minute = (dt.minute // 15) * 15
        result = dt.replace(minute=minute, second=0, microsecond=0)
    elif rule == "1h":
        result = dt.replace(minute=0, second=0, microsecond=0)
    elif rule == "4h":
        hour = (dt.hour // 4) * 4
        result = dt.replace(hour=hour, minute=0, second=0, microsecond=0)
    elif rule == "1D":
        result = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        return ts

    return pd.Timestamp(result, tz="UTC")


def run_pipeline(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    save_raw: bool = False,
    gap_report: bool = False,
    hot_only: bool = False,
    diagnostics: bool = False,
) -> None:
    """Run the full ingestion pipeline for one instrument over a date range.

    1. Load existing canonical data (if any) for incremental append
    2. Fetch + decode + aggregate new hourly data
    3. Merge with existing, deduplicate, validate, save canonical
    4. Derive higher timeframes (selective: only affected windows)
    5. Export hot packages
    6. Optionally generate gap report
    7. Optionally generate diagnostics report (Phase 1D)

    If hot_only=True, skip fetching and just regenerate derived + hot packages
    from existing canonical data.
    """
    if symbol not in INSTRUMENTS:
        raise ValueError(f"Unknown instrument: {symbol}. Available: {list(INSTRUMENTS.keys())}")

    meta = INSTRUMENTS[symbol]

    # Load existing canonical
    existing = _load_existing_canonical(symbol)

    # Hot-only mode: skip fetching, just rebuild derived + hot packages
    if hot_only:
        if existing is None or existing.empty:
            print("[pipeline] no existing canonical data — nothing to refresh")
            return
        canonical = existing
        print(f"[pipeline] hot-only mode: refreshing from {len(canonical)} canonical bars")
        _rebuild_derived_and_export(canonical, symbol, new_data_start=None)
        if gap_report:
            _run_gap_report(canonical, symbol)
        if diagnostics:
            save_cache_inventory(symbol)
        print(f"[pipeline] hot-only refresh complete for {symbol}")
        return

    # Initialize diagnostics collector if enabled
    collector: Optional[DiagnosticsCollector] = None
    if diagnostics:
        collector = DiagnosticsCollector(symbol)

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
                if collector:
                    collector.record_skipped(current)
                current += timedelta(hours=1)
                continue

        if collector:
            # Diagnostics-enabled path: use detailed fetch + decode
            try:
                result = fetch_bi5_detailed(symbol, current, save_raw=save_raw)
                fetch_count += 1

                collector.record_fetch(
                    hour_utc=current,
                    url=result.url,
                    http_status=result.http_status,
                    payload=result.data,
                    cached_path=result.cached_path,
                    error=result.error,
                )

                if result.data:
                    ticks, stats = decode_with_diagnostics(result.data, current, meta)
                    bars_produced = 0
                    if not ticks.empty:
                        bars = ticks_to_1m_ohlcv(ticks)
                        if not bars.empty:
                            all_bars.append(bars)
                            bars_produced = len(bars)

                    collector.record_decode(
                        hour_utc=current,
                        tick_count=stats.tick_count,
                        bars_produced=bars_produced,
                        price_min=stats.price_min,
                        price_max=stats.price_max,
                        volume_total=stats.volume_total,
                        decode_error=stats.error,
                    )
                else:
                    collector.record_decode(
                        hour_utc=current,
                        tick_count=0,
                        bars_produced=0,
                        decode_error=result.error or "no_payload",
                    )
            except Exception as exc:
                print(f"[pipeline] error at {current}: {exc}")
                collector.record_fetch(
                    hour_utc=current,
                    url=build_bi5_url(symbol, current),
                    http_status=0,
                    payload=b"",
                    error=f"pipeline_error:{exc}",
                )
        else:
            # Standard path: original fetch + decode (no diagnostics overhead)
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

    # Track the earliest new bar for selective derived regeneration
    new_data_start: Optional[pd.Timestamp] = None

    # Merge new bars
    if all_bars:
        new_df = pd.concat(all_bars)
        new_df = new_df.sort_index()
        new_df = new_df[~new_df.index.duplicated(keep="first")]

        new_data_start = new_df.index[0]

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

        print(f"[pipeline] new data from {new_data_start} ({len(new_df)} new bars)")
    else:
        canonical = existing
        print("[pipeline] no new data fetched — regenerating derived from existing canonical")

    # Save canonical
    _save_canonical(canonical, symbol)

    # Rebuild derived timeframes and hot packages
    _rebuild_derived_and_export(canonical, symbol, new_data_start)

    # Gap report
    if gap_report:
        _run_gap_report(canonical, symbol)

    # Diagnostics report (Phase 1D)
    if collector:
        report_path = collector.save_report()
        diag_report = collector.build_report()

        # Run decode assumption verification
        anomaly_report = verify_decode_assumptions(symbol, diag_report)
        n_anomalies = anomaly_report.get("anomalies_found", 0)
        if n_anomalies > 0:
            print(f"[diagnostics] {n_anomalies} decode anomaly(ies) detected — see report")

        # Save cache inventory if raw cache was enabled
        if save_raw:
            save_cache_inventory(symbol)

        summary = diag_report.get("summary", {})
        print(f"[diagnostics] {summary.get('total_ticks_decoded', 0)} ticks → "
              f"{summary.get('total_bars_produced', 0)} bars across "
              f"{summary.get('fetched', 0)} fetched hours")

    print(f"[pipeline] pipeline complete for {symbol}")


def _rebuild_derived_and_export(
    canonical: pd.DataFrame,
    symbol: str,
    new_data_start: Optional[pd.Timestamp],
) -> None:
    """Rebuild derived timeframes (selectively if possible) and export hot packages."""
    canonical_ohlcv = canonical[["open", "high", "low", "close", "volume"]]

    hot_dfs = {"1m": canonical_ohlcv}

    for rule in DERIVED_TIMEFRAMES:
        tf_label = TIMEFRAME_LABELS[rule]
        derived = _derive_affected_window(
            canonical_ohlcv, symbol, rule, tf_label, new_data_start
        )
        if derived is not None and not derived.empty:
            _save_derived(derived, symbol, tf_label)
            hot_dfs[tf_label] = derived[["open", "high", "low", "close", "volume"]]

    export_hot_packages(hot_dfs, symbol)


def _run_gap_report(canonical: pd.DataFrame, symbol: str) -> None:
    """Generate and save gap report for the canonical data."""
    report = generate_gap_report(symbol, canonical)
    save_gap_report(symbol, report)

    summary = report.get("summary", {})
    trading_gaps = summary.get("trading_hour_gaps", 0)
    trading_missing = summary.get("trading_hour_missing_minutes", 0)
    print(f"[pipeline] gap report: {trading_gaps} trading-hour gap(s), "
          f"{trading_missing} missing minute(s)")
