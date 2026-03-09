"""yFinance fallback provider — fetches 1m OHLCV when Dukascopy is unavailable.

AC-3 implementation: provider-level fallback that activates only when the
primary Dukascopy fetch fails at the transport layer (network error, HTTP
error, SSL error after retries are exhausted).  Does NOT activate on
downstream failures (decode, validation, business logic).

Soft dependency: returns empty DataFrame if yfinance is not installed.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from instrument_registry import INSTRUMENT_REGISTRY

logger = logging.getLogger(__name__)


def fetch_1m_ohlcv_yfinance(
    symbol: str,
    hour_dt: datetime,
) -> pd.DataFrame:
    """Fetch 1-minute OHLCV bars for a single hour via yfinance.

    Args:
        symbol: Canonical instrument symbol (e.g. "EURUSD").
        hour_dt: Timezone-aware UTC datetime for the target hour.

    Returns:
        DataFrame with columns [open, high, low, close, volume] indexed by
        UTC timestamp, matching ``ticks_to_1m_ohlcv`` output format.
        Returns empty DataFrame if yfinance is unavailable or fetch fails.
    """
    meta = INSTRUMENT_REGISTRY.get(symbol)
    if meta is None or not meta.yfinance_alias:
        logger.debug("No yfinance alias for %s — fallback skipped", symbol)
        return pd.DataFrame()

    try:
        import yfinance as yf  # noqa: F811 — soft dependency
    except ImportError:
        logger.debug("yfinance not installed — fallback unavailable")
        return pd.DataFrame()

    yf_symbol = meta.yfinance_alias

    # Target window: the exact hour, plus a small buffer for edge bars
    start = hour_dt.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1, minutes=5)

    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(
            start=start.strftime("%Y-%m-%d %H:%M:%S"),
            end=end.strftime("%Y-%m-%d %H:%M:%S"),
            interval="1m",
            auto_adjust=True,
        )
    except Exception as exc:
        logger.warning("yfinance fallback failed for %s (%s): %s", symbol, yf_symbol, exc)
        return pd.DataFrame()

    if hist is None or hist.empty:
        return pd.DataFrame()

    # Normalise index to UTC
    if hist.index.tz is None:
        hist.index = hist.index.tz_localize("UTC")
    else:
        hist.index = hist.index.tz_convert("UTC")

    # Filter to the target hour only
    hour_start = pd.Timestamp(start, tz="UTC")
    hour_end = hour_start + timedelta(hours=1)
    hist = hist[(hist.index >= hour_start) & (hist.index < hour_end)]

    if hist.empty:
        return pd.DataFrame()

    # Normalise column names to lowercase OHLCV
    result = pd.DataFrame(
        {
            "open": hist["Open"].values,
            "high": hist["High"].values,
            "low": hist["Low"].values,
            "close": hist["Close"].values,
            "volume": hist["Volume"].values.astype(float),
        },
        index=hist.index,
    )
    result.index.name = "timestamp_utc"

    return result
