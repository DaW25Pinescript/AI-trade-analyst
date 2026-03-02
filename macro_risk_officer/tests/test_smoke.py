"""
MRO Phase 4 — live-source smoke tests.

These tests hit real external APIs (Finnhub, FRED, GDELT).
They are SKIPPED by default and must be opted in explicitly:

    MRO_SMOKE_TESTS=1 pytest macro_risk_officer/tests/test_smoke.py -v

Prerequisites:
  - FINNHUB_API_KEY env var set (for Finnhub tests)
  - FRED_API_KEY env var set (for FRED tests)
  - Internet connectivity

GDELT requires no API key and is always included when smoke tests are enabled.

Design principles:
  - Non-blocking: failures are warnings, not hard errors, so CI never breaks
  - Non-flaky: each test checks structural contracts (types, field names) rather
    than specific values, which vary with live market data
  - Each client is tested in isolation so a single API outage doesn't mask others
"""

from __future__ import annotations

import os

import pytest

# ── Guard — skip the entire module unless opt-in flag is set ──────────────────

_SMOKE = os.getenv("MRO_SMOKE_TESTS", "").strip().lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(
    not _SMOKE,
    reason=(
        "Live-source smoke tests are opt-in. "
        "Set MRO_SMOKE_TESTS=1 to run (requires API keys + internet)."
    ),
)

# ── GDELT smoke (no API key required) ────────────────────────────────────────


class TestGdeltSmoke:
    """GDELT DOC 2.0 — no key required, always runnable when smoke is enabled."""

    def test_fetch_returns_list(self):
        from macro_risk_officer.ingestion.clients.gdelt_client import GdeltClient

        client = GdeltClient()
        events = client.fetch_geopolitical_events(lookback_days=3)
        # May be empty if tone is within noise floor — that is valid
        assert isinstance(events, list)

    def test_event_fields_present_when_returned(self):
        from macro_risk_officer.ingestion.clients.gdelt_client import GdeltClient
        from macro_risk_officer.core.models import MacroEvent

        client = GdeltClient()
        events = client.fetch_geopolitical_events(lookback_days=7)
        for evt in events:
            assert isinstance(evt, MacroEvent)
            assert evt.category == "geopolitical"
            assert evt.tier == 2
            assert evt.source == "gdelt"
            assert evt.actual in (1.0, -1.0)

    def test_no_exception_on_repeated_calls(self):
        from macro_risk_officer.ingestion.clients.gdelt_client import GdeltClient

        client = GdeltClient()
        # Two calls in succession — verifies no state leaks / silent auth issues
        client.fetch_geopolitical_events(lookback_days=1)
        client.fetch_geopolitical_events(lookback_days=3)


# ── Finnhub smoke (FINNHUB_API_KEY required) ──────────────────────────────────


_FINNHUB_KEY = os.getenv("FINNHUB_API_KEY", "")
_skip_finnhub = pytest.mark.skipif(
    not _FINNHUB_KEY,
    reason="FINNHUB_API_KEY not set — Finnhub smoke tests skipped",
)


@_skip_finnhub
class TestFinnhubSmoke:
    def test_calendar_returns_list(self):
        from macro_risk_officer.ingestion.clients.finnhub_client import FinnhubClient

        client = FinnhubClient(api_key=_FINNHUB_KEY)
        events = client.fetch_calendar(lookback_days=7, lookahead_days=2)
        assert isinstance(events, list)

    def test_event_structure_when_returned(self):
        from macro_risk_officer.ingestion.clients.finnhub_client import FinnhubClient
        from macro_risk_officer.core.models import MacroEvent

        client = FinnhubClient(api_key=_FINNHUB_KEY)
        events = client.fetch_calendar(lookback_days=14, lookahead_days=2)
        for evt in events:
            assert isinstance(evt, MacroEvent)
            assert evt.source == "finnhub"
            assert evt.event_id.startswith("finnhub-")
            assert evt.tier in (1, 2, 3)
            assert evt.category in (
                "monetary_policy", "inflation", "employment", "growth"
            )

    def test_no_duplicate_event_ids(self):
        from macro_risk_officer.ingestion.clients.finnhub_client import FinnhubClient

        client = FinnhubClient(api_key=_FINNHUB_KEY)
        events = client.fetch_calendar(lookback_days=14, lookahead_days=2)
        ids = [e.event_id for e in events]
        assert len(ids) == len(set(ids)), "Duplicate event_ids returned by Finnhub client"


# ── FRED smoke (FRED_API_KEY required) ────────────────────────────────────────


_FRED_KEY = os.getenv("FRED_API_KEY", "")
_skip_fred = pytest.mark.skipif(
    not _FRED_KEY,
    reason="FRED_API_KEY not set — FRED smoke tests skipped",
)


@_skip_fred
class TestFredSmoke:
    def test_to_macro_events_returns_list(self):
        from macro_risk_officer.ingestion.clients.fred_client import FredClient

        client = FredClient(api_key=_FRED_KEY)
        events = client.to_macro_events()
        assert isinstance(events, list)

    def test_event_series_ids_present(self):
        from macro_risk_officer.ingestion.clients.fred_client import FredClient

        client = FredClient(api_key=_FRED_KEY)
        events = client.to_macro_events()
        expected_series = {"DFF", "CPIAUCSL", "T10Y2Y", "UNRATE", "DCOILWTICO"}
        returned_series = {e.event_id.split("-")[0] for e in events}
        # At least some series should return — a complete blackout would be
        # a FRED API outage.  Allow partial availability.
        assert len(returned_series) > 0, "FRED returned zero macro series"

    def test_event_structure_when_returned(self):
        from macro_risk_officer.ingestion.clients.fred_client import FredClient
        from macro_risk_officer.core.models import MacroEvent

        client = FredClient(api_key=_FRED_KEY)
        events = client.to_macro_events()
        for evt in events:
            assert isinstance(evt, MacroEvent)
            assert evt.source == "fred"
            assert evt.surprise is not None


# ── Full-scheduler smoke ───────────────────────────────────────────────────────


class TestSchedulerSmoke:
    """
    End-to-end: MacroScheduler._refresh() with whatever keys are available.
    Uses whatever combination of Finnhub/FRED/GDELT succeeds.
    """

    def test_get_context_returns_context_or_none(self):
        """
        Scheduler must never raise — it must return MacroContext or None.
        A None result is acceptable when all upstream sources fail.
        """
        from macro_risk_officer.ingestion.scheduler import MacroScheduler
        from macro_risk_officer.core.models import MacroContext

        scheduler = MacroScheduler(enable_fetch_log=False)
        result = scheduler.get_context(instrument="XAUUSD")
        assert result is None or isinstance(result, MacroContext)

    def test_metrics_incremented_after_get_context(self):
        """Metrics counters must be non-zero after at least one get_context() call."""
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        scheduler.get_context(instrument="XAUUSD")
        m = scheduler.metrics
        assert m.cache_hits + m.cache_misses >= 1
        assert m.fetch_successes + m.fetch_failures >= 1

    def test_cache_hit_on_second_call(self):
        """Second call within TTL must be a cache hit, not a re-fetch."""
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        scheduler.get_context(instrument="XAUUSD")  # first call → miss or failure
        scheduler.get_context(instrument="XAUUSD")  # second call → cache hit if first succeeded
        m = scheduler.metrics
        # If the first call produced a context, the second must be a hit
        if m.fetch_successes >= 1:
            assert m.cache_hits >= 1, "Expected cache hit on second call"

    def test_context_structure_when_returned(self):
        """When a context is produced it must satisfy the Pydantic model."""
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        ctx = scheduler.get_context(instrument="XAUUSD")
        if ctx is None:
            pytest.skip("No data sources available — structural check skipped")

        assert ctx.regime in ("risk_off", "neutral", "risk_on")
        assert ctx.vol_bias in ("expanding", "neutral", "contracting")
        assert 0.0 <= ctx.confidence <= 1.0
        assert ctx.time_horizon_days > 0
        assert len(ctx.explanation) > 0
