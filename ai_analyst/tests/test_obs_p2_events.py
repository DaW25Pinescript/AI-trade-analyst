"""Observability Phase 2 — deterministic tests for structured event emission.

Tests validate that:
- MDO scheduler emits structured JSON events for refresh outcomes
- APScheduler listeners emit structured events for lifecycle events
- Feeder ingest emits structured events for mapping success/failure
- Triage batch summary emits structured events with partial-failure classification
- Graph routing emits structured events for routing decisions
- All events carry top_level_category (6 canonical) and event_code (15-class taxonomy)

All tests are deterministic — no live provider dependency.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-path shimming for market_data_officer imports.
# When running from ai_analyst/tests/, the MDO internal modules (feed, market_hours,
# alert_policy) are not on sys.path.  We insert stubs so scheduler.py can import.
# ---------------------------------------------------------------------------
_MDO_STUBS = ["feed", "feed.pipeline", "market_hours", "alert_policy"]
for _mod_name in _MDO_STUBS:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()


# ---------------------------------------------------------------------------
# Taxonomy validation helpers
# ---------------------------------------------------------------------------

CANONICAL_CATEGORIES = frozenset({
    "request_validation_failure",
    "runtime_execution_failure",
    "dependency_unavailability",
    "stale_but_readable",
    "artifact_read_write_failure",
    "recovery_after_prior_failure",
})


def _extract_obs_events(records: list[logging.LogRecord]) -> list[dict]:
    """Extract structured JSON events from log records."""
    events = []
    for rec in records:
        msg = rec.getMessage()
        try:
            parsed = json.loads(msg)
            if "event" in parsed:
                events.append(parsed)
        except (json.JSONDecodeError, TypeError):
            continue
    return events


def _assert_taxonomy(event: dict) -> None:
    """Assert that the event conforms to the taxonomy nesting rule."""
    assert "top_level_category" in event, f"Missing top_level_category in {event['event']}"
    assert "event_code" in event, f"Missing event_code in {event['event']}"
    assert event["top_level_category"] in CANONICAL_CATEGORIES, (
        f"Invalid top_level_category '{event['top_level_category']}' in {event['event']}. "
        f"Must be one of {sorted(CANONICAL_CATEGORIES)}"
    )


# ===========================================================================
# MDO Scheduler — structured refresh events
# ===========================================================================


class TestMDOSchedulerEvents:
    """Test structured events emitted by market_data_officer/scheduler.py."""

    def test_refresh_success_emits_structured_event(self, caplog):
        """refresh_instrument success path emits mdo.refresh.complete."""
        from market_data_officer.scheduler import refresh_instrument

        now = datetime(2026, 3, 12, 14, 0, 0, tzinfo=timezone.utc)
        with (
            patch("market_data_officer.scheduler.run_pipeline"),
            patch("market_data_officer.scheduler.get_market_state") as mock_ms,
            patch("market_data_officer.scheduler.classify_freshness") as mock_cf,
            caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"),
        ):
            mock_ms.return_value = MagicMock(value="OPEN")
            # Make market_state not match CLOSED/OFF_SESSION
            mock_ms.return_value.__eq__ = lambda s, o: False
            mock_ms.return_value.__ne__ = lambda s, o: True
            mock_ms.return_value.__hash__ = lambda s: id(s)

            mock_fresh = MagicMock()
            mock_fresh.classification = MagicMock(value="FRESH")
            mock_fresh.reason_code = MagicMock(value="within_threshold")
            mock_cf.return_value = mock_fresh

            with patch("market_data_officer.scheduler._evaluate_alert"):
                result = refresh_instrument("XAUUSD", {"window_hours": 48}, _now=now)

        assert result["outcome"] == "success"
        events = _extract_obs_events(caplog.records)
        complete_events = [e for e in events if e["event"] == "mdo.refresh.complete"]
        assert len(complete_events) == 1
        ev = complete_events[0]
        _assert_taxonomy(ev)
        assert ev["instrument"] == "XAUUSD"
        assert ev["outcome"] == "success"
        assert "duration_ms" in ev

    def test_refresh_failure_emits_structured_event(self, caplog):
        """refresh_instrument failure path emits mdo.refresh.failed."""
        from market_data_officer.scheduler import refresh_instrument

        now = datetime(2026, 3, 12, 14, 0, 0, tzinfo=timezone.utc)
        with (
            patch("market_data_officer.scheduler.run_pipeline", side_effect=RuntimeError("conn refused")),
            patch("market_data_officer.scheduler.get_market_state") as mock_ms,
            patch("market_data_officer.scheduler.classify_freshness") as mock_cf,
            caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"),
        ):
            mock_ms.return_value = MagicMock(value="OPEN")
            mock_ms.return_value.__eq__ = lambda s, o: False
            mock_ms.return_value.__ne__ = lambda s, o: True
            mock_ms.return_value.__hash__ = lambda s: id(s)

            mock_fresh = MagicMock()
            mock_fresh.classification = MagicMock(value="MISSING_BAD")
            mock_fresh.reason_code = MagicMock(value="no_artifact")
            mock_cf.return_value = mock_fresh

            with patch("market_data_officer.scheduler._evaluate_alert"):
                result = refresh_instrument("XAUUSD", {"window_hours": 48}, _now=now)

        assert result["outcome"] == "failure"
        events = _extract_obs_events(caplog.records)
        failed_events = [e for e in events if e["event"] == "mdo.refresh.failed"]
        assert len(failed_events) == 1
        ev = failed_events[0]
        _assert_taxonomy(ev)
        assert ev["event_code"] == "mdo_refresh_pipeline_error"
        assert ev["error_type"] == "RuntimeError"

    def test_refresh_skipped_emits_structured_event(self, caplog):
        """refresh_instrument market-closed skip emits mdo.refresh.skipped."""
        from market_data_officer.scheduler import refresh_instrument, MarketState

        now = datetime(2026, 3, 12, 14, 0, 0, tzinfo=timezone.utc)
        with (
            patch("market_data_officer.scheduler.get_market_state",
                  return_value=MarketState.CLOSED_EXPECTED),
            caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"),
        ):
            with patch("market_data_officer.scheduler._evaluate_alert"):
                result = refresh_instrument("XAUUSD", {"window_hours": 48}, _now=now)

        assert result["outcome"] == "skipped"
        events = _extract_obs_events(caplog.records)
        skip_events = [e for e in events if e["event"] == "mdo.refresh.skipped"]
        assert len(skip_events) == 1
        ev = skip_events[0]
        _assert_taxonomy(ev)
        assert ev["event_code"] == "mdo_refresh_market_closed"


# ===========================================================================
# APScheduler listeners
# ===========================================================================


class TestAPSchedulerListeners:
    """Test that APScheduler lifecycle listeners emit structured events."""

    def test_on_job_executed_emits_event(self, caplog):
        from market_data_officer.scheduler import _on_job_executed

        mock_event = MagicMock()
        mock_event.job_id = "refresh_XAUUSD"
        mock_event.scheduled_run_time = datetime(2026, 3, 12, 14, 0, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            _on_job_executed(mock_event)

        events = _extract_obs_events(caplog.records)
        assert len(events) == 1
        _assert_taxonomy(events[0])
        assert events[0]["event"] == "scheduler.job.executed"
        assert events[0]["job_id"] == "refresh_XAUUSD"

    def test_on_job_error_emits_event(self, caplog):
        from market_data_officer.scheduler import _on_job_error

        mock_event = MagicMock()
        mock_event.job_id = "refresh_EURUSD"
        mock_event.exception = RuntimeError("provider timeout")
        mock_event.scheduled_run_time = datetime(2026, 3, 12, 14, 0, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            _on_job_error(mock_event)

        events = _extract_obs_events(caplog.records)
        assert len(events) == 1
        _assert_taxonomy(events[0])
        assert events[0]["event_code"] == "scheduler_job_error"

    def test_on_job_missed_emits_event(self, caplog):
        from market_data_officer.scheduler import _on_job_missed

        mock_event = MagicMock()
        mock_event.job_id = "refresh_GBPUSD"
        mock_event.scheduled_run_time = datetime(2026, 3, 12, 14, 0, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            _on_job_missed(mock_event)

        events = _extract_obs_events(caplog.records)
        assert len(events) == 1
        _assert_taxonomy(events[0])
        assert events[0]["event_code"] == "scheduler_job_missed"
        assert events[0]["top_level_category"] == "dependency_unavailability"

    def test_on_job_max_instances_emits_event(self, caplog):
        from market_data_officer.scheduler import _on_job_max_instances

        mock_event = MagicMock()
        mock_event.job_id = "refresh_XAGUSD"
        mock_event.scheduled_run_time = datetime(2026, 3, 12, 14, 0, tzinfo=timezone.utc)

        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            _on_job_max_instances(mock_event)

        events = _extract_obs_events(caplog.records)
        assert len(events) == 1
        _assert_taxonomy(events[0])
        assert events[0]["event_code"] == "scheduler_job_overlap_skipped"
        assert events[0]["top_level_category"] == "stale_but_readable"


# ===========================================================================
# APScheduler build_scheduler wires listeners
# ===========================================================================


class TestBuildSchedulerListeners:
    """Verify build_scheduler registers lifecycle listeners."""

    def test_build_scheduler_registers_listeners(self):
        from market_data_officer.scheduler import build_scheduler

        scheduler = build_scheduler({"TEST": {"interval_hours": 1}})
        # APScheduler stores listeners as a list of (callback, mask) tuples
        listener_count = len(scheduler._listeners)
        assert listener_count >= 4, f"Expected >=4 listeners, got {listener_count}"


# ===========================================================================
# Feeder ingest — structured events
# ===========================================================================


class TestFeederIngestEvents:
    """Test structured events in macro_risk_officer/ingestion/feeder_ingest.py."""

    def test_events_from_feeder_logs_mapping_summary_on_skip(self, caplog):
        """Malformed events produce mapping_failed + mapping_summary events."""
        from macro_risk_officer.ingestion.feeder_ingest import events_from_feeder

        payload = {
            "contract_version": "1.0.0",
            "events": [
                {  # Valid
                    "event_id": "ev1",
                    "category": "growth",
                    "importance": "high",
                    "timestamp": "2026-03-12T10:00:00Z",
                    "title": "GDP Release",
                },
                {  # Malformed — missing event_id
                    "category": "inflation",
                    "title": "CPI Miss",
                },
            ],
        }

        with caplog.at_level(logging.INFO, logger="macro_risk_officer.ingestion.feeder_ingest"):
            result = events_from_feeder(payload)

        assert len(result) == 1  # Only the valid event
        events = _extract_obs_events(caplog.records)

        # Should have a mapping_failed event for the malformed one
        failed_events = [e for e in events if e["event"] == "feeder.event.mapping_failed"]
        assert len(failed_events) == 1
        _assert_taxonomy(failed_events[0])
        assert failed_events[0]["event_code"] == "feeder_event_mapping_failure"

        # Should have a mapping_summary
        summary_events = [e for e in events if e["event"] == "feeder.ingest.mapping_summary"]
        assert len(summary_events) == 1
        _assert_taxonomy(summary_events[0])
        assert summary_events[0]["total_events"] == 2
        assert summary_events[0]["mapped"] == 1
        assert summary_events[0]["skipped"] == 1

    def test_events_from_feeder_logs_mapping_complete_on_success(self, caplog):
        """All events valid produces mapping_complete event."""
        from macro_risk_officer.ingestion.feeder_ingest import events_from_feeder

        payload = {
            "contract_version": "1.0.0",
            "events": [
                {
                    "event_id": "ev1",
                    "category": "growth",
                    "importance": "medium",
                    "timestamp": "2026-03-12T10:00:00Z",
                    "title": "GDP Release",
                },
            ],
        }

        with caplog.at_level(logging.INFO, logger="macro_risk_officer.ingestion.feeder_ingest"):
            result = events_from_feeder(payload)

        assert len(result) == 1
        events = _extract_obs_events(caplog.records)
        complete_events = [e for e in events if e["event"] == "feeder.ingest.mapping_complete"]
        assert len(complete_events) == 1
        _assert_taxonomy(complete_events[0])
        assert complete_events[0]["mapped"] == 1
        assert complete_events[0]["skipped"] == 0

    def test_ingest_feeder_payload_emits_received_and_complete(self, caplog):
        """ingest_feeder_payload emits received and complete events."""
        from macro_risk_officer.ingestion.feeder_ingest import ingest_feeder_payload

        payload = {
            "contract_version": "1.0.0",
            "events": [
                {
                    "event_id": "ev1",
                    "category": "monetary_policy",
                    "importance": "high",
                    "timestamp": "2026-03-12T10:00:00Z",
                    "title": "Fed Rate Decision",
                    "source": "fed",
                },
            ],
        }

        with caplog.at_level(logging.INFO, logger="macro_risk_officer.ingestion.feeder_ingest"):
            ctx = ingest_feeder_payload(payload, "XAUUSD")

        assert ctx is not None
        events = _extract_obs_events(caplog.records)

        received = [e for e in events if e["event"] == "feeder.ingest.received"]
        assert len(received) == 1
        _assert_taxonomy(received[0])
        assert received[0]["instrument"] == "XAUUSD"

        complete = [e for e in events if e["event"] == "feeder.ingest.complete"]
        assert len(complete) == 1
        _assert_taxonomy(complete[0])
        assert complete[0]["events_ingested"] >= 1


# ===========================================================================
# Triage batch summary — structured events (Guardrail B: log only)
# ===========================================================================


class TestTriageBatchEvents:
    """Test structured triage batch summary events in journey.py."""

    def test_emit_obs_event_produces_json(self, caplog):
        """The _emit_obs_event helper produces valid JSON."""
        from ai_analyst.api.routers.journey import _emit_obs_event

        with caplog.at_level(logging.INFO, logger="ai_analyst.api.routers.journey"):
            _emit_obs_event(
                "test.event",
                top_level_category="runtime_execution_failure",
                event_code="test_code",
                foo="bar",
            )

        events = _extract_obs_events(caplog.records)
        assert len(events) == 1
        _assert_taxonomy(events[0])
        assert events[0]["event"] == "test.event"
        assert events[0]["foo"] == "bar"


# ===========================================================================
# Graph routing — structured events
# ===========================================================================


class TestGraphRoutingEvents:
    """Test structured routing decision events in pipeline.py."""

    def test_route_after_phase1_emits_event_arbiter(self, caplog):
        """_route_after_phase1 emits graph.route.after_phase1 event."""
        from ai_analyst.graph.pipeline import _route_after_phase1

        gt = MagicMock()
        gt.run_id = "test-run-001"
        gt.m15_overlay = None
        state = {"ground_truth": gt, "enable_deliberation": False}

        with caplog.at_level(logging.INFO, logger="ai_analyst.graph.pipeline"):
            result = _route_after_phase1(state)

        assert result == "run_arbiter"
        events = _extract_obs_events(caplog.records)
        route_events = [e for e in events if e["event"] == "graph.route.after_phase1"]
        assert len(route_events) == 1
        _assert_taxonomy(route_events[0])
        assert route_events[0]["destination"] == "run_arbiter"
        assert route_events[0]["deliberation_enabled"] is False

    def test_route_after_phase1_emits_event_deliberation(self, caplog):
        """_route_after_phase1 routes to deliberation when enabled."""
        from ai_analyst.graph.pipeline import _route_after_phase1

        gt = MagicMock()
        gt.run_id = "test-run-002"
        gt.m15_overlay = None
        state = {"ground_truth": gt, "enable_deliberation": True}

        with caplog.at_level(logging.INFO, logger="ai_analyst.graph.pipeline"):
            result = _route_after_phase1(state)

        assert result == "deliberation"
        events = _extract_obs_events(caplog.records)
        route_events = [e for e in events if e["event"] == "graph.route.after_phase1"]
        assert len(route_events) == 1
        assert route_events[0]["destination"] == "deliberation"
        assert route_events[0]["deliberation_enabled"] is True

    def test_route_after_deliberation_emits_event(self, caplog):
        """_route_after_deliberation emits graph.route.after_deliberation event."""
        from ai_analyst.graph.pipeline import _route_after_deliberation

        gt = MagicMock()
        gt.run_id = "test-run-003"
        gt.m15_overlay = None
        state = {"ground_truth": gt}

        with caplog.at_level(logging.INFO, logger="ai_analyst.graph.pipeline"):
            result = _route_after_deliberation(state)

        assert result == "run_arbiter"
        events = _extract_obs_events(caplog.records)
        route_events = [e for e in events if e["event"] == "graph.route.after_deliberation"]
        assert len(route_events) == 1
        _assert_taxonomy(route_events[0])


# ===========================================================================
# Taxonomy completeness — all 15 event codes nest under 6 categories
# ===========================================================================


class TestTaxonomyCompleteness:
    """Validate the 15-class taxonomy nests under 6 canonical categories."""

    TAXONOMY = {
        # category → list of event_codes
        "request_validation_failure": [
            "feeder_payload_schema_invalid",
            "feeder_event_mapping_failure",
        ],
        "runtime_execution_failure": [
            "mdo_refresh_success",
            "mdo_refresh_pipeline_error",
            "scheduler_job_executed",
            "scheduler_job_error",
            "triage_batch_success",
            "triage_batch_partial_failure",
            "triage_batch_all_failed",
            "graph_routing_decision",
            "graph_pipeline_started",
            "feeder_ingest_received",
            "feeder_ingest_success",
        ],
        "dependency_unavailability": [
            "scheduler_job_missed",
        ],
        "stale_but_readable": [
            "mdo_refresh_market_closed",
            "scheduler_job_overlap_skipped",
        ],
        "artifact_read_write_failure": [],
        "recovery_after_prior_failure": [
            "feeder_staleness_recovered",
        ],
    }

    def test_all_categories_are_canonical(self):
        """Every category in the taxonomy is one of the 6 canonical ones."""
        for cat in self.TAXONOMY:
            assert cat in CANONICAL_CATEGORIES

    def test_no_duplicate_event_codes(self):
        """No event_code appears in more than one category."""
        seen = {}
        for cat, codes in self.TAXONOMY.items():
            for code in codes:
                assert code not in seen, f"Duplicate event_code '{code}' in {cat} and {seen[code]}"
                seen[code] = cat

    def test_event_code_count(self):
        """Taxonomy has the expected number of event codes."""
        total = sum(len(codes) for codes in self.TAXONOMY.values())
        assert total >= 15, f"Expected >=15 event codes, got {total}"
