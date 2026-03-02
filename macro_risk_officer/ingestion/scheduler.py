"""
TTL-cached macro context scheduler.

Fetches a fresh MacroContext at most once per TTL window (default 30 min).
Pipeline nodes read from the cache — zero added latency to /analyse.

TTL and instrument exposure defaults are loaded from config YAML (MRO-P3).

Usage:
    scheduler = MacroScheduler()
    context = scheduler.get_context(instrument="XAUUSD")
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from macro_risk_officer.config.loader import load_thresholds, load_weights
from macro_risk_officer.core.models import MacroContext
from macro_risk_officer.core.reasoning_engine import ReasoningEngine
from macro_risk_officer.ingestion.clients.finnhub_client import FinnhubClient
from macro_risk_officer.ingestion.clients.fred_client import FredClient
from macro_risk_officer.ingestion.clients.gdelt_client import GdeltClient
from macro_risk_officer.ingestion.normalizer import normalise_events


class MacroScheduler:
    def __init__(self, ttl_seconds: Optional[int] = None) -> None:
        cfg_ttl: int = load_thresholds()["scheduler"]["ttl_seconds"]
        self.ttl: int = ttl_seconds if ttl_seconds is not None else cfg_ttl

        # Instrument exposure map — loaded from weights.yaml so adding a new
        # instrument only requires a YAML edit, no code change.
        raw_exposures: dict = load_weights().get("instrument_exposures", {})
        self._instrument_exposures: Dict[str, Dict[str, float]] = {
            symbol: dict(assets) for symbol, assets in raw_exposures.items()
        }

        self._cache: Optional[MacroContext] = None
        self._last_fetch: float = 0.0
        self._engine = ReasoningEngine()

    def get_context(self, instrument: str = "XAUUSD") -> Optional[MacroContext]:
        """
        Return a cached MacroContext, refreshing if TTL has expired.
        Returns None if data sources are unavailable (fails silently so the
        main pipeline is never blocked).
        """
        now = time.monotonic()
        if self._cache is not None and (now - self._last_fetch) < self.ttl:
            return self._cache

        try:
            self._cache = self._refresh(instrument)
            self._last_fetch = now
        except Exception:
            pass  # Stale cache or None — Arbiter continues without macro context

        return self._cache

    def _refresh(self, instrument: str) -> MacroContext:
        raw_events = []

        # Finnhub: scheduled event calendar (actual vs forecast surprises)
        try:
            finnhub = FinnhubClient()
            raw_events.extend(finnhub.fetch_calendar(lookback_days=14, lookahead_days=2))
        except Exception:
            pass  # Continue with FRED-only context if Finnhub unavailable

        # FRED: macro series momentum (current vs prior reading)
        try:
            fred = FredClient()
            raw_events.extend(fred.to_macro_events())
        except Exception:
            pass  # Continue with Finnhub-only context if FRED unavailable

        # GDELT: geopolitical sentiment (no API key required)
        try:
            gdelt = GdeltClient()
            raw_events.extend(gdelt.fetch_geopolitical_events(lookback_days=3))
        except Exception:
            pass  # Non-critical — continue without geopolitical signal

        if not raw_events:
            raise RuntimeError("No events retrieved from any data source.")

        events = normalise_events(raw_events)
        exposures = self._instrument_exposures.get(instrument, {})
        return self._engine.generate_context(events, exposures)

    def invalidate(self) -> None:
        """Force a refresh on next get_context() call."""
        self._last_fetch = 0.0
