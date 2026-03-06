"""Gap detection and reporting for canonical 1m data."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .config import CANONICAL_DIR, DATA_ROOT


# FX market hours: Sunday 22:00 UTC → Friday 22:00 UTC
# Hours outside this window are expected gaps (weekend closure).
_FX_WEEK_OPEN_DOW = 6   # Sunday
_FX_WEEK_OPEN_HOUR = 22
_FX_WEEK_CLOSE_DOW = 4  # Friday
_FX_WEEK_CLOSE_HOUR = 22

GAP_REPORT_DIR = DATA_ROOT / "reports"


def is_fx_trading_hour(dt: datetime) -> bool:
    """Return True if dt falls within expected FX trading hours."""
    dow = dt.weekday()  # Mon=0 … Sun=6
    hour = dt.hour

    # Saturday: always closed
    if dow == 5:
        return False

    # Sunday: only open from 22:00 onwards
    if dow == 6:
        return hour >= _FX_WEEK_OPEN_HOUR

    # Friday: only open until 22:00
    if dow == 4:
        return hour < _FX_WEEK_CLOSE_HOUR

    # Mon–Thu: fully open
    return True


def detect_gaps(
    canonical_df: pd.DataFrame,
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Dict]:
    """Detect missing 1m bars during expected FX trading hours.

    Returns a list of gap records, each with:
      - gap_start: first missing minute (ISO string)
      - gap_end: last missing minute (ISO string)
      - missing_minutes: count of missing bars in this gap
      - classification: 'weekend' | 'trading_hours'

    Gaps are contiguous runs of missing minutes. Weekend gaps are classified
    separately from unexpected trading-hour gaps.
    """
    if canonical_df.empty:
        return []

    if start is None:
        start = canonical_df.index[0].to_pydatetime()
    if end is None:
        end = canonical_df.index[-1].to_pydatetime()

    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    # Build the full expected minute range
    expected = pd.date_range(start=start, end=end, freq="1min", tz="UTC")
    present = set(canonical_df.index)
    missing = sorted(set(expected) - present)

    if not missing:
        return []

    # Group contiguous missing minutes into gap runs
    gaps: List[Dict] = []
    run_start = missing[0]
    prev = missing[0]

    for ts in missing[1:]:
        if ts - prev > timedelta(minutes=1):
            # Close current run
            gaps.append(_make_gap_record(run_start, prev))
            run_start = ts
        prev = ts

    # Close final run
    gaps.append(_make_gap_record(run_start, prev))

    return gaps


def _make_gap_record(gap_start: pd.Timestamp, gap_end: pd.Timestamp) -> Dict:
    """Build a single gap record with classification."""
    minutes = int((gap_end - gap_start).total_seconds() / 60) + 1

    # Classify: if the entire gap falls outside FX trading hours → weekend
    # Otherwise → trading_hours (unexpected)
    all_weekend = True
    current = gap_start.to_pydatetime()
    end_dt = gap_end.to_pydatetime()
    while current <= end_dt:
        if is_fx_trading_hour(current):
            all_weekend = False
            break
        current += timedelta(minutes=1)

    return {
        "gap_start": gap_start.isoformat(),
        "gap_end": gap_end.isoformat(),
        "missing_minutes": minutes,
        "classification": "weekend" if all_weekend else "trading_hours",
    }


def generate_gap_report(
    symbol: str,
    canonical_df: Optional[pd.DataFrame] = None,
) -> Dict:
    """Generate a full gap report for an instrument.

    Loads canonical data if not provided. Returns a JSON-serializable dict
    with summary statistics and gap details.
    """
    if canonical_df is None:
        path = CANONICAL_DIR / f"{symbol}_1m.parquet"
        if not path.exists():
            return {"symbol": symbol, "error": "no canonical data found"}
        canonical_df = pd.read_parquet(path)
        canonical_df.index = pd.to_datetime(canonical_df.index, utc=True)

    if canonical_df.empty:
        return {"symbol": symbol, "error": "canonical data is empty"}

    gaps = detect_gaps(canonical_df, symbol)

    weekend_gaps = [g for g in gaps if g["classification"] == "weekend"]
    trading_gaps = [g for g in gaps if g["classification"] == "trading_hours"]

    report = {
        "symbol": symbol,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "canonical_range": {
            "first": canonical_df.index[0].isoformat(),
            "last": canonical_df.index[-1].isoformat(),
            "total_bars": len(canonical_df),
        },
        "summary": {
            "total_gaps": len(gaps),
            "weekend_gaps": len(weekend_gaps),
            "trading_hour_gaps": len(trading_gaps),
            "total_missing_minutes": sum(g["missing_minutes"] for g in gaps),
            "trading_hour_missing_minutes": sum(g["missing_minutes"] for g in trading_gaps),
        },
        "trading_hour_gaps": trading_gaps,
        "weekend_gaps": weekend_gaps,
    }

    return report


def save_gap_report(symbol: str, report: Dict) -> Path:
    """Save a gap report to disk as JSON."""
    GAP_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = GAP_REPORT_DIR / f"{symbol}_gap_report.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"[gaps] saved report: {path}")
    return path
