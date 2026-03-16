"""Market data read service — read-side OHLCV projection (PR-CHART-1).

Reads stored OHLCV CSV data from MDO's hot package layer and projects it
into frontend-ready Candle format. No writes, no fetches, no scheduler.

Import boundary:
  ALLOWED: loader (load_timeframe, load_manifest), instrument_registry, feed.config
  FORBIDDEN: structural engine, scheduler, pipeline, fetch code

Spec: docs/specs/PR_CHART_1_SPEC.md §6.3
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from market_data_officer.feed.config import PACKAGES_DIR
from market_data_officer.instrument_registry import INSTRUMENT_REGISTRY
from market_data_officer.officer.loader import load_manifest, load_timeframe

from ai_analyst.api.models.market_data import Candle, OHLCVResponse

logger = logging.getLogger(__name__)

DataState = Literal["live", "stale", "unavailable"]

# Timeframes the loader knows about
KNOWN_TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")
DEFAULT_TIMEFRAME = "4h"
API_VERSION = "2026.03"


class InstrumentNotFound(Exception):
    pass


class TimeframeNotFound(Exception):
    pass


class MarketDataReadError(Exception):
    pass


def _is_valid_candle_row(row: dict) -> bool:
    """Check if a row dict has valid OHLCV numeric values."""
    for field in ("open", "high", "low", "close", "volume"):
        val = row.get(field)
        if val is None:
            return False
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _derive_data_state(
    total_source_rows: int,
    valid_rows: int,
    manifest_found: bool,
) -> DataState:
    """Derive data_state per §6.5 / §6.2.3."""
    if total_source_rows == 0 or valid_rows == 0:
        return "unavailable"
    dropped = total_source_rows - valid_rows
    drop_ratio = dropped / total_source_rows
    if not manifest_found:
        return "stale"
    if drop_ratio >= 0.10:
        return "stale"
    return "live"


def read_ohlcv(
    instrument: str,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = 100,
    packages_dir: Path | None = None,
) -> OHLCVResponse:
    """Read OHLCV candles for an instrument/timeframe from hot packages.

    Args:
        instrument: Instrument symbol (e.g. "XAUUSD").
        timeframe: Candle timeframe (e.g. "4h"). Defaults to "4h".
        limit: Max candles to return (1–500). Already validated by caller.
        packages_dir: Override for testing.

    Returns:
        OHLCVResponse with candles in ascending time order.

    Raises:
        InstrumentNotFound: Instrument not in registry.
        TimeframeNotFound: No hot package CSV for this timeframe.
        MarketDataReadError: I/O failure during read.
    """
    pkg_dir = packages_dir if packages_dir is not None else PACKAGES_DIR

    # Validate instrument against registry
    if instrument not in INSTRUMENT_REGISTRY:
        raise InstrumentNotFound(f"Instrument not found: {instrument}")

    # Load the CSV
    try:
        df = load_timeframe(instrument, timeframe, pkg_dir)
    except FileNotFoundError:
        raise TimeframeNotFound(
            f"No data for {instrument} timeframe {timeframe}"
        )
    except Exception as exc:
        # Empty CSV files cause pandas/loader errors — treat as empty store
        csv_path = pkg_dir / f"{instrument}_{timeframe}_latest.csv"
        if csv_path.exists():
            import pandas as pd
            try:
                raw = pd.read_csv(csv_path)
                if raw.empty:
                    df = raw
                else:
                    raise MarketDataReadError(
                        f"Failed to read market data for {instrument}/{timeframe}: {exc}"
                    ) from exc
            except pd.errors.EmptyDataError:
                df = pd.DataFrame()
            except MarketDataReadError:
                raise
            except Exception:
                raise MarketDataReadError(
                    f"Failed to read market data for {instrument}/{timeframe}: {exc}"
                ) from exc
        else:
            raise MarketDataReadError(
                f"Failed to read market data for {instrument}/{timeframe}: {exc}"
            ) from exc

    total_source_rows = len(df)

    # Check manifest for freshness
    manifest_found = True
    try:
        load_manifest(instrument, pkg_dir)
    except FileNotFoundError:
        manifest_found = False

    # Project DataFrame rows to Candle shape, dropping malformed rows
    candles: list[Candle] = []
    for ts, row in df.iterrows():
        row_dict = row.to_dict()
        if not _is_valid_candle_row(row_dict):
            continue
        try:
            epoch = int(ts.timestamp())
        except (AttributeError, OSError, ValueError):
            continue
        candles.append(Candle(
            timestamp=epoch,
            open=float(row_dict["open"]),
            high=float(row_dict["high"]),
            low=float(row_dict["low"]),
            close=float(row_dict["close"]),
            volume=float(row_dict["volume"]),
        ))

    valid_rows = len(candles)
    data_state = _derive_data_state(total_source_rows, valid_rows, manifest_found)

    # Sort ascending by timestamp (oldest first) and take tail N
    candles.sort(key=lambda c: c.timestamp)
    candles = candles[-limit:]

    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return OHLCVResponse(
        version=API_VERSION,
        generated_at=now_utc,
        data_state=data_state,
        instrument=instrument,
        timeframe=timeframe,
        candles=candles,
        candle_count=len(candles),
    )
