"""
TTL-cached macro context scheduler.

Fetches a fresh MacroContext at most once per TTL window (default 30 min).
Pipeline nodes read from the cache — zero added latency to /analyse.

TTL and instrument exposure defaults are loaded from config YAML (MRO-P3).

Phase-4 addition: every refresh attempt is counted in SchedulerMetrics (in-process)
and logged to FetchLog (persistent SQLite) so the `kpi` CLI command can report
macro availability % and context freshness across restarts.

Usage:
    scheduler = MacroScheduler()
    context = scheduler.get_context(instrument="XAUUSD")
    print(scheduler.metrics.cache_hit_ratio)
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from macro_risk_officer.config.loader import load_thresholds, load_weights
from macro_risk_officer.core.models import MacroContext
from macro_risk_officer.core.reasoning_engine import ReasoningEngine
from macro_risk_officer.history.metrics import FetchLog, SchedulerMetrics
from macro_risk_officer.ingestion.clients.finnhub_client import FinnhubClient
from macro_risk_officer.ingestion.clients.fred_client import FredClient
from macro_risk_officer.ingestion.clients.gdelt_client import GdeltClient
from macro_risk_officer.ingestion.normalizer import normalise_events


class MacroScheduler:
    def __init__(self, ttl_seconds: Optional[int] = None, enable_fetch_log: bool = True) -> None:
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
        self._refresh_lock = threading.Lock()  # HIGH-4: prevents thundering herd on cache miss

        # Phase-4 KPI telemetry
        self._metrics = SchedulerMetrics()
        self._fetch_log: Optional[FetchLog] = FetchLog() if enable_fetch_log else None

    @property
    def metrics(self) -> SchedulerMetrics:
        """Live in-process KPI counters for this scheduler instance."""
        return self._metrics

    def get_context(self, instrument: str = "XAUUSD") -> Optional[MacroContext]:
        """
        Return a cached MacroContext, refreshing if TTL has expired.
        Returns None if data sources are unavailable (fails silently so the
        main pipeline is never blocked).
        """
        now = time.monotonic()
        # Fast path: cache valid — no lock needed for reads
        if self._cache is not None and (now - self._last_fetch) < self.ttl:
            self._metrics.cache_hits += 1
            return self._cache

        # Slow path: acquire lock then re-check to prevent thundering herd (HIGH-4).
        # Only one thread runs _refresh(); others wait and then use the fresh cache.
        self._metrics.cache_misses += 1
        with self._refresh_lock:
            # Re-check inside lock — another thread may have already refreshed
            now = time.monotonic()
            if self._cache is not None and (now - self._last_fetch) < self.ttl:
                return self._cache

            try:
                self._cache, source_mask, event_count = self._refresh(instrument)
                self._last_fetch = time.monotonic()
                self._metrics.fetch_successes += 1
                self._metrics.last_fetch_epoch = self._last_fetch
                if self._fetch_log is not None:
                    self._fetch_log.record_success(source_mask, event_count)
            except Exception as exc:
                self._metrics.fetch_failures += 1
                if self._fetch_log is not None:
                    self._fetch_log.record_failure(type(exc).__name__)
                # Stale cache or None — Arbiter continues without macro context

        return self._cache

    def _refresh(self, instrument: str) -> Tuple[MacroContext, str, int]:
        """
        Fetch fresh events from all available sources and compute MacroContext.

        Phase 4: data source fetches run in parallel (ThreadPoolExecutor) to
        reduce cold-start latency from ~3× slowest source to ~1× slowest source.

        Returns (context, source_mask, event_count) where source_mask is a
        comma-separated list of sources that contributed events (e.g. "fred,gdelt").
        """

        def _fetch_finnhub() -> Tuple[str, list]:
            events = FinnhubClient().fetch_calendar(lookback_days=14, lookahead_days=2)
            return "finnhub", events or []

        def _fetch_fred() -> Tuple[str, list]:
            events = FredClient().to_macro_events()
            return "fred", events or []

        def _fetch_gdelt() -> Tuple[str, list]:
            events = GdeltClient().fetch_geopolitical_events(lookback_days=3)
            return "gdelt", events or []

        raw_events: list = []
        active_sources: List[str] = []

        # Fan out all three data-source fetches concurrently; each is I/O-bound
        # so a thread pool is appropriate. Failures are silently swallowed so
        # that any live source still produces a valid MacroContext.
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(_fetch_finnhub),
                executor.submit(_fetch_fred),
                executor.submit(_fetch_gdelt),
            ]
            for future in as_completed(futures):
                try:
                    source, events = future.result()
                    if events:
                        raw_events.extend(events)
                        active_sources.append(source)
                except Exception:
                    pass  # Individual source failure is non-blocking

        if not raw_events:
            raise RuntimeError("No events retrieved from any data source.")

        events = normalise_events(raw_events)
        exposures = self._instrument_exposures.get(instrument, {})
        context = self._engine.generate_context(events, exposures)
        return context, ",".join(sorted(active_sources)), len(events)

    def invalidate(self) -> None:
        """Force a refresh on next get_context() call."""
        self._cache = None
        self._last_fetch = 0.0
