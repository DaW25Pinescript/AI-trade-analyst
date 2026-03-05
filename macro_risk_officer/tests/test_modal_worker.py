"""
Tests for the Modal macro feeder worker and feeder_ingest integration.

No live network calls — all external fetches are patched with fixtures.

Coverage:
  1. Feeder output shape matches contract schema
  2. Normalizer behaviour for each source adapter (_macro_event_to_feeder_event)
  3. Duplicate event handling (_dedup_events)
  4. Partial source failure — partial results returned, not an exception
  5. Local MRO acceptance of feeder payload — correct MacroEvent mapping
  6. No regression in existing reasoning path via feeder ingest
  7. contract_version mismatch is rejected
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from macro_risk_officer.core.models import MacroEvent
from macro_risk_officer.ingestion.feeder_ingest import (
    SUPPORTED_CONTRACT_VERSION,
    _feeder_event_to_macro_event,
    _importance_to_tier,
    events_from_feeder,
    ingest_feeder_payload,
)
from macro_risk_officer.modal_macro_worker import (
    CONTRACT_VERSION,
    _category_tags,
    _dedup_events,
    _importance_from_tier,
    _macro_event_to_feeder_event,
    _surprise_direction,
    build_feeder_payload,
)


# ─── Shared fixtures ───────────────────────────────────────────────────────────


def _make_macro_event(
    event_id: str = "finnhub-test-001",
    category: str = "inflation",
    tier: int = 1,
    actual: float | None = 0.4,
    forecast: float | None = 0.3,
    previous: float | None = 0.2,
    description: str = "US CPI m/m",
    source: str = "finnhub",
    timestamp: datetime | None = None,
) -> MacroEvent:
    if timestamp is None:
        timestamp = datetime(2026, 3, 4, 14, 0, tzinfo=timezone.utc)
    return MacroEvent(
        event_id=event_id,
        category=category,
        tier=tier,
        timestamp=timestamp,
        actual=actual,
        forecast=forecast,
        previous=previous,
        description=description,
        source=source,
    )


def _make_feeder_event(
    event_id: str = "finnhub-test-001",
    source: str = "finnhub",
    title: str = "US CPI m/m",
    category: str = "inflation",
    region: str = "US",
    timestamp: str = "2026-03-04T14:00:00+00:00",
    importance: str = "high",
    actual: float | None = 0.4,
    forecast: float | None = 0.3,
    previous: float | None = 0.2,
    surprise_direction: str | None = "positive",
    pressure_direction: None = None,
    raw_reference: None = None,
    tags: list[str] | None = None,
) -> dict:
    return {
        "event_id": event_id,
        "source": source,
        "title": title,
        "category": category,
        "region": region,
        "timestamp": timestamp,
        "importance": importance,
        "actual": actual,
        "forecast": forecast,
        "previous": previous,
        "surprise_direction": surprise_direction,
        "pressure_direction": pressure_direction,
        "raw_reference": raw_reference,
        "tags": tags or ["economic_release", "inflation"],
    }


def _make_minimal_payload(
    events: list[dict] | None = None,
    status: str = "ok",
    warnings: list[str] | None = None,
) -> dict:
    """Build a minimal valid feeder payload for ingestion tests."""
    return {
        "contract_version": SUPPORTED_CONTRACT_VERSION,
        "generated_at": "2026-03-04T00:00:00Z",
        "instrument_context": "XAUUSD",
        "sources_queried": ["finnhub", "fred", "gdelt"],
        "status": status,
        "warnings": warnings or [],
        "events": events if events is not None else [_make_feeder_event()],
        "source_health": {
            "finnhub": {"status": "ok", "record_count": 1, "latency_ms": 200},
            "fred": {"status": "ok", "record_count": 0, "latency_ms": 300},
            "gdelt": {"status": "ok", "record_count": 0, "latency_ms": 100},
        },
    }


# ─── 1. Helper function unit tests ────────────────────────────────────────────


class TestHelpers:
    def test_importance_from_tier_mapping(self):
        assert _importance_from_tier(1) == "high"
        assert _importance_from_tier(2) == "medium"
        assert _importance_from_tier(3) == "low"
        assert _importance_from_tier(99) == "low"  # unknown → low

    def test_surprise_direction_positive(self):
        assert _surprise_direction(0.4, 0.3) == "positive"

    def test_surprise_direction_negative(self):
        assert _surprise_direction(0.2, 0.3) == "negative"

    def test_surprise_direction_none_when_equal(self):
        assert _surprise_direction(0.3, 0.3) is None

    def test_surprise_direction_none_when_missing(self):
        assert _surprise_direction(None, 0.3) is None
        assert _surprise_direction(0.4, None) is None
        assert _surprise_direction(None, None) is None

    def test_category_tags_known(self):
        tags = _category_tags("monetary_policy")
        assert "central_bank" in tags
        assert "rate_decision" in tags

    def test_category_tags_unknown_defaults(self):
        tags = _category_tags("unknown_category")
        assert tags == ["economic_release"]


# ─── 2. Normalizer: _macro_event_to_feeder_event ──────────────────────────────


class TestMacroEventToFeederEvent:
    def test_title_maps_from_description(self):
        ev = _make_macro_event(description="US CPI m/m")
        result = _macro_event_to_feeder_event(ev)
        assert result["title"] == "US CPI m/m"

    def test_importance_maps_from_tier(self):
        ev = _make_macro_event(tier=1)
        assert _macro_event_to_feeder_event(ev)["importance"] == "high"

        ev2 = _make_macro_event(tier=2)
        assert _macro_event_to_feeder_event(ev2)["importance"] == "medium"

        ev3 = _make_macro_event(tier=3)
        assert _macro_event_to_feeder_event(ev3)["importance"] == "low"

    def test_surprise_direction_positive(self):
        ev = _make_macro_event(actual=0.4, forecast=0.3)
        assert _macro_event_to_feeder_event(ev)["surprise_direction"] == "positive"

    def test_surprise_direction_negative(self):
        ev = _make_macro_event(actual=0.2, forecast=0.3)
        assert _macro_event_to_feeder_event(ev)["surprise_direction"] == "negative"

    def test_pressure_direction_always_null(self):
        ev = _make_macro_event()
        assert _macro_event_to_feeder_event(ev)["pressure_direction"] is None

    def test_region_us_for_finnhub(self):
        ev = _make_macro_event(source="finnhub")
        assert _macro_event_to_feeder_event(ev)["region"] == "US"

    def test_region_us_for_fred(self):
        ev = _make_macro_event(source="fred")
        assert _macro_event_to_feeder_event(ev)["region"] == "US"

    def test_region_global_for_gdelt(self):
        ev = _make_macro_event(source="gdelt")
        assert _macro_event_to_feeder_event(ev)["region"] == "global"

    def test_all_required_fields_present(self):
        ev = _make_macro_event()
        result = _macro_event_to_feeder_event(ev)
        required = {
            "event_id", "source", "title", "category", "region",
            "timestamp", "importance", "actual", "forecast", "previous",
            "surprise_direction", "pressure_direction", "raw_reference", "tags",
        }
        assert required.issubset(result.keys())

    def test_event_id_preserved(self):
        ev = _make_macro_event(event_id="fred-DFF-20260301")
        assert _macro_event_to_feeder_event(ev)["event_id"] == "fred-DFF-20260301"

    def test_timestamp_is_iso_string(self):
        ev = _make_macro_event()
        ts = _macro_event_to_feeder_event(ev)["timestamp"]
        # Must be parseable as ISO datetime
        parsed = datetime.fromisoformat(ts)
        assert parsed.year == 2026

    def test_geopolitical_source_has_geopolitical_tag(self):
        ev = _make_macro_event(category="geopolitical", source="gdelt")
        tags = _macro_event_to_feeder_event(ev)["tags"]
        assert "geopolitical" in tags

    def test_none_actual_preserved(self):
        ev = _make_macro_event(actual=None, forecast=None)
        result = _macro_event_to_feeder_event(ev)
        assert result["actual"] is None
        assert result["forecast"] is None


# ─── 3. Deduplication ─────────────────────────────────────────────────────────


class TestDedupEvents:
    def test_removes_exact_duplicates(self):
        ev = _make_feeder_event(event_id="abc-001")
        result = _dedup_events([ev, ev, ev])
        assert len(result) == 1
        assert result[0]["event_id"] == "abc-001"

    def test_preserves_distinct_events(self):
        events = [
            _make_feeder_event(event_id="a"),
            _make_feeder_event(event_id="b"),
            _make_feeder_event(event_id="c"),
        ]
        result = _dedup_events(events)
        assert len(result) == 3

    def test_preserves_first_occurrence(self):
        ev1 = _make_feeder_event(event_id="dup", title="First")
        ev2 = _make_feeder_event(event_id="dup", title="Second")
        result = _dedup_events([ev1, ev2])
        assert len(result) == 1
        assert result[0]["title"] == "First"

    def test_empty_input(self):
        assert _dedup_events([]) == []

    def test_cross_source_dedup(self):
        # Same event_id from two sources (shouldn't happen in practice, but
        # dedup must handle it defensively)
        ev1 = _make_feeder_event(event_id="same-id", source="finnhub")
        ev2 = _make_feeder_event(event_id="same-id", source="fred")
        result = _dedup_events([ev1, ev2])
        assert len(result) == 1


# ─── 4. build_feeder_payload — partial source failure ─────────────────────────


class TestBuildFeederPayload:
    def _fred_event_list(self) -> list[dict]:
        return [
            _make_feeder_event(
                event_id="fred-DFF-20260301",
                source="fred",
                title="Effective Federal Funds Rate",
                category="monetary_policy",
                importance="high",
            )
        ]

    def test_partial_failure_returns_partial_status(self):
        """A single failing source produces status='partial', not an exception."""
        with (
            patch(
                "macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                return_value=([], {"status": "failed", "error": "timeout"}),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_fred_adapter",
                return_value=(
                    self._fred_event_list(),
                    {"status": "ok", "record_count": 1, "latency_ms": 200},
                ),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50}),
            ),
        ):
            result = build_feeder_payload(
                finnhub_key="dummy", fred_key="dummy"
            )

        assert result["status"] == "partial"
        assert len(result["events"]) == 1
        assert result["source_health"]["finnhub"]["status"] == "failed"
        assert result["source_health"]["fred"]["status"] == "ok"

    def test_partial_failure_warning_recorded(self):
        with (
            patch(
                "macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                return_value=(
                    [],
                    {"status": "failed", "error": "HTTP 403 Forbidden"},
                ),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_fred_adapter",
                return_value=(
                    self._fred_event_list(),
                    {"status": "ok", "record_count": 1, "latency_ms": 300},
                ),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50}),
            ),
        ):
            result = build_feeder_payload(
                finnhub_key="dummy", fred_key="dummy"
            )

        assert any("finnhub" in w for w in result["warnings"])
        assert any("HTTP 403" in w for w in result["warnings"])

    def test_all_sources_failed_produces_failed_status(self):
        with (
            patch(
                "macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                return_value=([], {"status": "failed", "error": "timeout"}),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_fred_adapter",
                return_value=([], {"status": "failed", "error": "timeout"}),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                return_value=([], {"status": "failed", "error": "timeout"}),
            ),
        ):
            result = build_feeder_payload(
                finnhub_key="dummy", fred_key="dummy"
            )

        assert result["status"] == "failed"
        assert result["events"] == []

    def test_all_sources_ok_produces_ok_status(self):
        with (
            patch(
                "macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                return_value=(
                    [_make_feeder_event(event_id="fin-001", source="finnhub")],
                    {"status": "ok", "record_count": 1, "latency_ms": 100},
                ),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_fred_adapter",
                return_value=(
                    self._fred_event_list(),
                    {"status": "ok", "record_count": 1, "latency_ms": 200},
                ),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50}),
            ),
        ):
            result = build_feeder_payload(
                finnhub_key="dummy", fred_key="dummy"
            )

        assert result["status"] == "ok"
        assert len(result["events"]) == 2

    def test_missing_api_key_treated_as_source_failure(self):
        """Missing FINNHUB_API_KEY produces a failed source, not an exception."""
        with (
            patch(
                "macro_risk_officer.modal_macro_worker._run_fred_adapter",
                return_value=(
                    self._fred_event_list(),
                    {"status": "ok", "record_count": 1, "latency_ms": 200},
                ),
            ),
            patch(
                "macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50}),
            ),
        ):
            # No finnhub_key provided — should not call _run_finnhub_adapter
            result = build_feeder_payload(
                finnhub_key=None, fred_key="dummy"
            )

        assert result["source_health"]["finnhub"]["status"] == "failed"
        assert "FINNHUB_API_KEY not set" in result["source_health"]["finnhub"]["error"]
        # fred events are still returned
        assert len(result["events"]) == 1

    def test_contract_version_is_set(self):
        with (
            patch("macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
            patch("macro_risk_officer.modal_macro_worker._run_fred_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
        ):
            result = build_feeder_payload(finnhub_key="k", fred_key="k")

        assert result["contract_version"] == CONTRACT_VERSION

    def test_sources_queried_always_present(self):
        with (
            patch("macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                  return_value=([], {"status": "failed", "error": "x"})),
            patch("macro_risk_officer.modal_macro_worker._run_fred_adapter",
                  return_value=([], {"status": "failed", "error": "x"})),
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "failed", "error": "x"})),
        ):
            result = build_feeder_payload(finnhub_key="k", fred_key="k")

        assert set(result["sources_queried"]) == {"finnhub", "fred", "gdelt"}

    def test_dedup_applied_across_sources(self):
        """Events with the same event_id from multiple adapters are deduplicated."""
        shared_id = "shared-event-001"
        ev_fin = _make_feeder_event(event_id=shared_id, source="finnhub")
        ev_fred = _make_feeder_event(event_id=shared_id, source="fred")

        with (
            patch("macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                  return_value=([ev_fin], {"status": "ok", "record_count": 1, "latency_ms": 0})),
            patch("macro_risk_officer.modal_macro_worker._run_fred_adapter",
                  return_value=([ev_fred], {"status": "ok", "record_count": 1, "latency_ms": 0})),
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
        ):
            result = build_feeder_payload(finnhub_key="k", fred_key="k")

        assert len(result["events"]) == 1

    def test_generated_at_is_iso_timestamp(self):
        with (
            patch("macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
            patch("macro_risk_officer.modal_macro_worker._run_fred_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 0})),
        ):
            result = build_feeder_payload(finnhub_key="k", fred_key="k")

        # Must be a valid ISO-like timestamp string
        ts = result["generated_at"]
        assert "T" in ts
        assert "Z" in ts or "+" in ts or len(ts) >= 19


# ─── 5. feeder_ingest — contract validation ───────────────────────────────────


class TestFeederIngestContractVersion:
    def test_correct_version_accepted(self):
        payload = _make_minimal_payload()
        events = events_from_feeder(payload)
        assert isinstance(events, list)

    def test_wrong_version_raises_value_error(self):
        payload = _make_minimal_payload()
        payload["contract_version"] = "0.9.0"
        with pytest.raises(ValueError, match="contract_version"):
            events_from_feeder(payload)

    def test_missing_version_raises_value_error(self):
        payload = _make_minimal_payload()
        del payload["contract_version"]
        with pytest.raises(ValueError, match="contract_version"):
            events_from_feeder(payload)


# ─── 6. feeder_ingest — feeder event → MacroEvent mapping ─────────────────────


class TestFeederEventToMacroEvent:
    def test_title_becomes_description(self):
        ev = _make_feeder_event(title="US CPI m/m")
        macro = _feeder_event_to_macro_event(ev)
        assert macro.description == "US CPI m/m"

    def test_importance_high_becomes_tier_1(self):
        ev = _make_feeder_event(importance="high")
        assert _feeder_event_to_macro_event(ev).tier == 1

    def test_importance_medium_becomes_tier_2(self):
        ev = _make_feeder_event(importance="medium")
        assert _feeder_event_to_macro_event(ev).tier == 2

    def test_importance_low_becomes_tier_3(self):
        ev = _make_feeder_event(importance="low")
        assert _feeder_event_to_macro_event(ev).tier == 3

    def test_importance_to_tier_mapping(self):
        assert _importance_to_tier("high") == 1
        assert _importance_to_tier("medium") == 2
        assert _importance_to_tier("low") == 3
        assert _importance_to_tier("unknown") == 3  # default

    def test_actual_forecast_previous_preserved(self):
        ev = _make_feeder_event(actual=0.4, forecast=0.3, previous=0.2)
        macro = _feeder_event_to_macro_event(ev)
        assert macro.actual == 0.4
        assert macro.forecast == 0.3
        assert macro.previous == 0.2

    def test_source_preserved(self):
        ev = _make_feeder_event(source="fred")
        assert _feeder_event_to_macro_event(ev).source == "fred"

    def test_event_id_preserved(self):
        ev = _make_feeder_event(event_id="fred-DFF-20260301")
        assert _feeder_event_to_macro_event(ev).event_id == "fred-DFF-20260301"

    def test_timestamp_parsed_from_iso_string(self):
        ev = _make_feeder_event(timestamp="2026-03-04T14:00:00+00:00")
        macro = _feeder_event_to_macro_event(ev)
        assert macro.timestamp.year == 2026
        assert macro.timestamp.month == 3
        assert macro.timestamp.day == 4

    def test_invalid_category_raises_value_error(self):
        ev = _make_feeder_event(category="unknown_category")
        with pytest.raises(ValueError, match="category"):
            _feeder_event_to_macro_event(ev)

    def test_all_valid_categories_accepted(self):
        valid_categories = [
            "monetary_policy", "inflation", "employment",
            "growth", "geopolitical", "systemic_risk",
        ]
        for cat in valid_categories:
            ev = _make_feeder_event(category=cat)
            macro = _feeder_event_to_macro_event(ev)
            assert macro.category == cat


# ─── 7. feeder_ingest — events_from_feeder (normalisation + dedup) ────────────


class TestEventsFromFeeder:
    def test_empty_events_returns_empty_list(self):
        payload = _make_minimal_payload(events=[])
        events = events_from_feeder(payload)
        assert events == []

    def test_duplicate_events_deduplicated(self):
        ev = _make_feeder_event(event_id="dup-001")
        payload = _make_minimal_payload(events=[ev, ev])
        events = events_from_feeder(payload)
        ids = [e.event_id for e in events]
        assert len(ids) == len(set(ids))
        assert "dup-001" in ids

    def test_single_valid_event_returned(self):
        payload = _make_minimal_payload(events=[_make_feeder_event()])
        events = events_from_feeder(payload)
        assert len(events) == 1
        assert isinstance(events[0], MacroEvent)

    def test_malformed_event_skipped_gracefully(self):
        """An event with an invalid category is skipped — not a fatal error."""
        good = _make_feeder_event(event_id="good-001")
        bad = {**_make_feeder_event(event_id="bad-001"), "category": "INVALID"}
        payload = _make_minimal_payload(events=[bad, good])
        events = events_from_feeder(payload)
        assert len(events) == 1
        assert events[0].event_id == "good-001"

    def test_events_sorted_by_tier_then_age(self):
        """normalise_events must sort: tier 1 before tier 2."""
        tier1 = _make_feeder_event(
            event_id="tier1-001", importance="high",
            timestamp="2026-03-01T10:00:00+00:00",
        )
        tier2 = _make_feeder_event(
            event_id="tier2-001", importance="medium",
            timestamp="2026-03-01T12:00:00+00:00",
        )
        payload = _make_minimal_payload(events=[tier2, tier1])
        events = events_from_feeder(payload)
        assert events[0].tier <= events[-1].tier


# ─── 8. ingest_feeder_payload — end-to-end MacroContext production ────────────


class TestIngestFeederPayload:
    def _hawkish_payload(self) -> dict:
        """Payload with a hawkish Fed event that should drive risk_off regime."""
        return _make_minimal_payload(
            events=[
                _make_feeder_event(
                    event_id="fed-hawkish-feeder",
                    category="monetary_policy",
                    title="Fed rate decision (hawkish)",
                    importance="high",
                    actual=5.5,
                    forecast=5.25,
                    previous=5.25,
                )
            ]
        )

    def test_returns_macro_context(self):
        from macro_risk_officer.core.models import MacroContext
        ctx = ingest_feeder_payload(self._hawkish_payload())
        assert isinstance(ctx, MacroContext)

    def test_hawkish_fed_produces_risk_off_or_neutral(self):
        ctx = ingest_feeder_payload(self._hawkish_payload())
        assert ctx.regime in ("risk_off", "neutral")

    def test_hawkish_fed_pressures_nq(self):
        ctx = ingest_feeder_payload(self._hawkish_payload())
        assert ctx.asset_pressure.NQ < 0

    def test_hawkish_fed_supports_usd(self):
        ctx = ingest_feeder_payload(self._hawkish_payload())
        assert ctx.asset_pressure.USD > 0

    def test_empty_events_returns_neutral_context(self):
        payload = _make_minimal_payload(events=[])
        ctx = ingest_feeder_payload(payload)
        assert ctx.regime == "neutral"
        assert ctx.confidence == 0.0

    def test_instrument_exposures_affect_conflict_score(self):
        """XAUUSD (long GOLD) should have negative conflict with hawkish macro."""
        ctx = ingest_feeder_payload(
            self._hawkish_payload(), instrument="XAUUSD"
        )
        # Hawkish → GOLD pressured. XAUUSD has long GOLD exposure → conflict
        assert ctx.conflict_score < 0

    def test_version_mismatch_raises_before_engine(self):
        payload = self._hawkish_payload()
        payload["contract_version"] = "2.0.0"
        with pytest.raises(ValueError, match="contract_version"):
            ingest_feeder_payload(payload)

    def test_active_event_ids_populated(self):
        ctx = ingest_feeder_payload(self._hawkish_payload())
        assert "fed-hawkish-feeder" in ctx.active_event_ids

    def test_explanation_generated(self):
        ctx = ingest_feeder_payload(self._hawkish_payload())
        assert len(ctx.explanation) > 0


# ─── 9. Regression: existing reasoning path via scheduler unaffected ──────────


class TestExistingReasoningPathUnaffected:
    """Verify the pre-existing scheduler + reasoning_engine path still works."""

    def test_reasoning_engine_accepts_direct_macro_events(self):
        """ReasoningEngine.generate_context still works with direct MacroEvent input."""
        from macro_risk_officer.core.reasoning_engine import ReasoningEngine

        events = [
            _make_macro_event(
                event_id="direct-test-001",
                category="monetary_policy",
                tier=1,
                actual=5.5,
                forecast=5.25,
            )
        ]
        engine = ReasoningEngine()
        ctx = engine.generate_context(events)
        assert ctx.regime in ("risk_off", "neutral")

    def test_normalise_events_still_deduplicates(self):
        """normalise_events API unchanged."""
        from macro_risk_officer.ingestion.normalizer import normalise_events

        ev = _make_macro_event(event_id="norm-test-001")
        result = normalise_events([ev, ev])
        assert len(result) == 1


# ─── 10. CLI: feeder-run and feeder-ingest commands ──────────────────────────


class TestFeederRunCLI:
    """Test the feeder-run CLI command (calls build_feeder_payload directly)."""

    def test_feeder_run_prints_json(self, capsys):
        from macro_risk_officer.main import cmd_feeder_run

        with (
            patch("macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                  return_value=([_make_feeder_event()],
                                {"status": "ok", "record_count": 1, "latency_ms": 100})),
            patch("macro_risk_officer.modal_macro_worker._run_fred_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50})),
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50})),
            patch.dict("os.environ", {"FINNHUB_API_KEY": "test", "FRED_API_KEY": "test"}),
        ):
            cmd_feeder_run(instrument="XAUUSD")

        import json
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["contract_version"] == CONTRACT_VERSION
        assert data["instrument_context"] == "XAUUSD"
        assert len(data["events"]) == 1

    def test_feeder_run_missing_keys_produces_partial(self, capsys):
        from macro_risk_officer.main import cmd_feeder_run

        with (
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50})),
            patch.dict("os.environ", {}, clear=True),
        ):
            # Remove env vars so keys are None
            import os
            os.environ.pop("FINNHUB_API_KEY", None)
            os.environ.pop("FRED_API_KEY", None)
            cmd_feeder_run(instrument="XAUUSD")

        import json
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["source_health"]["finnhub"]["status"] == "failed"
        assert data["source_health"]["fred"]["status"] == "failed"


class TestFeederIngestCLI:
    """Test the feeder-ingest CLI command."""

    def test_feeder_ingest_from_file(self, capsys, tmp_path):
        import json
        from macro_risk_officer.main import cmd_feeder_ingest

        payload = _make_minimal_payload(
            events=[
                _make_feeder_event(
                    event_id="cli-test-001",
                    category="monetary_policy",
                    importance="high",
                    actual=5.5,
                    forecast=5.25,
                    previous=5.25,
                )
            ]
        )
        fpath = tmp_path / "feeder.json"
        fpath.write_text(json.dumps(payload))

        cmd_feeder_ingest(instrument="XAUUSD", file_path=str(fpath))
        captured = capsys.readouterr()
        assert "MACRO RISK CONTEXT" in captured.out
        assert "cli-test-001" in captured.out

    def test_feeder_ingest_bad_version_exits(self, capsys, tmp_path):
        import json
        from macro_risk_officer.main import cmd_feeder_ingest

        payload = _make_minimal_payload()
        payload["contract_version"] = "99.0.0"
        fpath = tmp_path / "bad.json"
        fpath.write_text(json.dumps(payload))

        with pytest.raises(SystemExit) as exc:
            cmd_feeder_ingest(instrument="XAUUSD", file_path=str(fpath))
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.out


class TestCLIHelpIncludesFeeder:
    """Verify --help lists the new feeder commands."""

    def test_help_mentions_feeder_run(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "macro_risk_officer", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "feeder-run" in result.stdout

    def test_help_mentions_feeder_ingest(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "macro_risk_officer", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "feeder-ingest" in result.stdout


# ─── 11. Round-trip determinism ──────────────────────────────────────────────


class TestRoundTripDeterminism:
    """Verify that the same inputs produce the same feeder output."""

    def _fixed_events(self):
        return [
            _make_feeder_event(event_id="det-001", actual=0.4, forecast=0.3),
            _make_feeder_event(event_id="det-002", category="monetary_policy",
                               actual=5.5, forecast=5.25, importance="high"),
        ]

    def test_build_feeder_payload_is_deterministic(self):
        events = self._fixed_events()
        with (
            patch("macro_risk_officer.modal_macro_worker._run_finnhub_adapter",
                  return_value=(events, {"status": "ok", "record_count": 2, "latency_ms": 100})),
            patch("macro_risk_officer.modal_macro_worker._run_fred_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50})),
            patch("macro_risk_officer.modal_macro_worker._run_gdelt_adapter",
                  return_value=([], {"status": "ok", "record_count": 0, "latency_ms": 50})),
        ):
            result1 = build_feeder_payload(
                finnhub_key="k", fred_key="k",
                generated_at="2026-03-04T00:00:00Z",
            )
            result2 = build_feeder_payload(
                finnhub_key="k", fred_key="k",
                generated_at="2026-03-04T00:00:00Z",
            )

        assert result1 == result2

    def test_macro_event_to_feeder_event_is_deterministic(self):
        ev = _make_macro_event(event_id="det-macro-001")
        r1 = _macro_event_to_feeder_event(ev)
        r2 = _macro_event_to_feeder_event(ev)
        assert r1 == r2

    def test_ingest_produces_same_context_for_same_payload(self):
        payload = _make_minimal_payload(
            events=[
                _make_feeder_event(
                    event_id="det-ingest-001",
                    category="inflation",
                    importance="high",
                    actual=3.8,
                    forecast=3.2,
                )
            ]
        )
        ctx1 = ingest_feeder_payload(payload)
        ctx2 = ingest_feeder_payload(payload)
        assert ctx1.regime == ctx2.regime
        assert ctx1.vol_bias == ctx2.vol_bias
        assert ctx1.conflict_score == ctx2.conflict_score
        assert ctx1.confidence == ctx2.confidence
        assert ctx1.time_horizon_days == ctx2.time_horizon_days
        assert ctx1.active_event_ids == ctx2.active_event_ids
        assert ctx1.explanation == ctx2.explanation
        assert ctx1.asset_pressure.model_dump() == pytest.approx(
            ctx2.asset_pressure.model_dump(),
            abs=1e-9,
        )


# ─── 12. Adapter edge cases ─────────────────────────────────────────────────


class TestAdapterEdgeCases:
    """Edge cases for source adapter conversion."""

    def test_none_actual_and_forecast_no_surprise(self):
        ev = _make_macro_event(actual=None, forecast=None)
        result = _macro_event_to_feeder_event(ev)
        assert result["surprise_direction"] is None
        assert result["actual"] is None
        assert result["forecast"] is None

    def test_zero_actual_zero_forecast(self):
        ev = _make_macro_event(actual=0.0, forecast=0.0)
        result = _macro_event_to_feeder_event(ev)
        assert result["surprise_direction"] is None  # no directional surprise
        assert result["actual"] == 0.0

    def test_negative_surprise(self):
        ev = _make_macro_event(actual=-0.5, forecast=0.3)
        result = _macro_event_to_feeder_event(ev)
        assert result["surprise_direction"] == "negative"

    def test_geopolitical_gdelt_event_mapping(self):
        ev = _make_macro_event(
            event_id="gdelt-geo-20260304-abc",
            category="geopolitical",
            tier=2,
            actual=0.7,
            forecast=0.0,
            description="GDELT geopolitical escalation signal (avg tone -5.2)",
            source="gdelt",
        )
        result = _macro_event_to_feeder_event(ev)
        assert result["region"] == "global"
        assert result["importance"] == "medium"
        assert result["source"] == "gdelt"
        assert "geopolitical" in result["tags"]

    def test_fred_systemic_risk_event_mapping(self):
        ev = _make_macro_event(
            event_id="fred-T10Y2Y-20260301",
            category="systemic_risk",
            tier=2,
            actual=-0.3,
            forecast=-0.1,
            description="10Y-2Y Treasury Yield Spread (inversion signal)",
            source="fred",
        )
        result = _macro_event_to_feeder_event(ev)
        assert result["category"] == "systemic_risk"
        assert result["surprise_direction"] == "negative"
        assert "systemic_risk" in result["tags"]

    def test_feeder_event_with_missing_optional_fields(self):
        """Feeder events with None actual/forecast still map to valid MacroEvent."""
        ev = _make_feeder_event(
            event_id="partial-001",
            actual=None,
            forecast=None,
            previous=None,
            surprise_direction=None,
        )
        macro = _feeder_event_to_macro_event(ev)
        assert macro.actual is None
        assert macro.forecast is None
        assert macro.surprise is None

    def test_feeder_event_with_naive_timestamp(self):
        """Naive timestamp (no TZ) gets UTC assumed."""
        ev = _make_feeder_event(timestamp="2026-03-04T14:00:00")
        macro = _feeder_event_to_macro_event(ev)
        assert macro.timestamp.tzinfo is not None

    def test_multiple_sources_mixed_in_payload(self):
        """Payload with events from all 3 sources maps correctly."""
        events = [
            _make_feeder_event(event_id="fin-001", source="finnhub",
                               category="inflation"),
            _make_feeder_event(event_id="fred-001", source="fred",
                               category="monetary_policy"),
            _make_feeder_event(event_id="gdelt-001", source="gdelt",
                               category="geopolitical"),
        ]
        payload = _make_minimal_payload(events=events)
        macro_events = events_from_feeder(payload)
        assert len(macro_events) == 3
        sources = {e.source for e in macro_events}
        assert sources == {"finnhub", "fred", "gdelt"}
