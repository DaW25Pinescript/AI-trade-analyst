"""
YFinance price client — MRO Phase 4.

Fetches historical OHLCV data for MRO-tracked instruments to enable
post-hoc regime accuracy scoring.

No API key required. yfinance wraps the Yahoo Finance API.

Design rules:
  - Soft dependency: if yfinance is not installed, all methods return None / {}.
  - All exceptions are caught; callers should treat None as "data unavailable".
  - Uses hourly granularity throughout (good for 1h, 24h, 5d lookbacks;
    avoids 1-minute data rate limits that apply for >30-day lookbacks).

Instrument → Yahoo Finance symbol mapping:
  MRO uses short-hand instrument names (XAUUSD, US500, etc.).
  Yahoo Finance requires specific ticker symbols (GC=F, ^GSPC, etc.).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# MRO instrument name → Yahoo Finance ticker symbol
_SYMBOL_MAP: Dict[str, str] = {
    "XAUUSD": "GC=F",      # Gold Futures
    "XAGUSD": "SI=F",      # Silver Futures
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "US500":  "^GSPC",     # S&P 500
    "NAS100": "^NDX",      # Nasdaq 100
    "USOIL":  "CL=F",      # Crude Oil Futures (WTI)
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "DXY":    "DX-Y.NYB",  # US Dollar Index
}

# Offsets at which we record price snapshots (hours)
PRICE_OFFSETS_HOURS: Dict[str, int] = {
    "price_at_record": 0,
    "price_at_1h":     1,
    "price_at_24h":    24,
    "price_at_5d":     24 * 5,
}


class YFinanceClient:
    """
    Fetches hourly close prices around a given timestamp for a single instrument.
    Returns empty dict when yfinance is unavailable or data cannot be fetched.
    """

    def instrument_to_symbol(self, instrument: str) -> Optional[str]:
        """Map an MRO instrument name to a Yahoo Finance ticker symbol."""
        return _SYMBOL_MAP.get(instrument.upper())

    def fetch_prices_around(
        self, instrument: str, recorded_at: datetime
    ) -> Dict[str, Optional[float]]:
        """
        Fetch close prices at T+0h, T+1h, T+24h, T+5d for the given instrument.

        Args:
            instrument  : MRO instrument string (e.g. "XAUUSD").
            recorded_at : UTC timestamp of the run that was recorded.

        Returns:
            Dict with keys matching PRICE_OFFSETS_HOURS — values are floats
            (close price in instrument's quote currency) or None if unavailable.
        """
        symbol = self.instrument_to_symbol(instrument)
        if symbol is None:
            logger.debug("No yfinance symbol for instrument=%s", instrument)
            return {k: None for k in PRICE_OFFSETS_HOURS}

        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed — price outcomes disabled.")
            return {k: None for k in PRICE_OFFSETS_HOURS}

        # Ensure recorded_at is timezone-aware UTC
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        else:
            recorded_at = recorded_at.astimezone(timezone.utc)

        max_offset_hours = max(PRICE_OFFSETS_HOURS.values())
        fetch_start = recorded_at - timedelta(hours=2)
        fetch_end = recorded_at + timedelta(hours=max_offset_hours + 24)

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(
                start=fetch_start.strftime("%Y-%m-%d"),
                end=fetch_end.strftime("%Y-%m-%d"),
                interval="1h",
                auto_adjust=True,
            )
        except Exception as exc:
            logger.warning("yfinance fetch failed for %s: %s", symbol, exc)
            return {k: None for k in PRICE_OFFSETS_HOURS}

        if hist is None or hist.empty:
            logger.debug("yfinance returned empty data for %s", symbol)
            return {k: None for k in PRICE_OFFSETS_HOURS}

        # Normalise index to UTC
        if hist.index.tz is None:
            hist.index = hist.index.tz_localize("UTC")
        else:
            import pandas as pd
            hist.index = hist.index.tz_convert("UTC")

        closes = hist["Close"]

        def _closest_close(target: datetime) -> Optional[float]:
            """Return the close price of the hourly bar closest to target."""
            target_ns = pd.Timestamp(target)
            try:
                pos = closes.index.searchsorted(target_ns, side="left")
                if pos >= len(closes):
                    pos = len(closes) - 1
                return float(closes.iloc[pos])
            except Exception:
                return None

        import pandas as pd

        result: Dict[str, Optional[float]] = {}
        for col, offset_h in PRICE_OFFSETS_HOURS.items():
            target = recorded_at + timedelta(hours=offset_h)
            result[col] = _closest_close(target)

        return result
