"""
Phase 3 — Monitoring & Observability test suite.

Tests correlation IDs, pipeline metrics collection, metrics store,
and operator dashboard endpoint availability.
"""
import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from ai_analyst.core.correlation import (
    CorrelationFilter,
    correlation_ctx,
    get_correlation_id,
    setup_structured_logging,
)
from ai_analyst.core.pipeline_metrics import (
    MetricsSnapshot,
    MetricsStore,
    RunMetrics,
    metrics_store,
)


# ── Correlation ID tests ─────────────────────────────────────────────────────

class TestCorrelationContext:
    def test_default_is_empty(self):
        """Correlation ID defaults to empty string when not set."""
        # Reset to default in case a previous test set it
        token = correlation_ctx.set("")
        try:
            assert get_correlation_id() == ""
        finally:
            correlation_ctx.reset(token)

    def test_set_and_get(self):
        """Correlation ID can be set and retrieved."""
        token = correlation_ctx.set("run-abc-123")
        try:
            assert get_correlation_id() == "run-abc-123"
        finally:
            correlation_ctx.reset(token)

    def test_reset_restores_previous(self):
        """Resetting a token restores the previous correlation ID."""
        outer_token = correlation_ctx.set("outer")
        inner_token = correlation_ctx.set("inner")
        assert get_correlation_id() == "inner"
        correlation_ctx.reset(inner_token)
        assert get_correlation_id() == "outer"
        correlation_ctx.reset(outer_token)

    def test_filter_injects_run_id(self):
        """CorrelationFilter injects run_id into log records."""
        token = correlation_ctx.set("test-run-456")
        try:
            f = CorrelationFilter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="hello", args=(), exc_info=None,
            )
            result = f.filter(record)
            assert result is True
            assert record.run_id == "test-run-456"  # type: ignore[attr-defined]
        finally:
            correlation_ctx.reset(token)

    def test_filter_empty_when_not_set(self):
        """CorrelationFilter returns empty string when no context is set."""
        token = correlation_ctx.set("")
        try:
            f = CorrelationFilter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="hello", args=(), exc_info=None,
            )
            f.filter(record)
            assert record.run_id == ""  # type: ignore[attr-defined]
        finally:
            correlation_ctx.reset(token)

    def test_setup_structured_logging_idempotent(self):
        """setup_structured_logging can be called multiple times safely."""
        setup_structured_logging()
        setup_structured_logging()  # should not add duplicate handlers
        root = logging.getLogger()
        phase3_handlers = [
            h for h in root.handlers if getattr(h, "_phase3_tag", None) == "_phase3_structured"
        ]
        assert len(phase3_handlers) == 1


# ── RunMetrics dataclass tests ───────────────────────────────────────────────

def _make_run_metrics(
    run_id="run-001",
    instrument="XAUUSD",
    session="NY",
    total_latency_ms=5000,
    llm_cost_usd=0.05,
    llm_calls=5,
    llm_calls_failed=0,
    analyst_count=4,
    analyst_agreement_pct=75,
    decision="ENTER_LONG",
    overall_confidence=0.82,
    overlay_provided=False,
    deliberation_enabled=False,
    macro_context_available=True,
    timestamp=None,
) -> RunMetrics:
    return RunMetrics(
        run_id=run_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        instrument=instrument,
        session=session,
        total_latency_ms=total_latency_ms,
        llm_cost_usd=llm_cost_usd,
        llm_calls=llm_calls,
        llm_calls_failed=llm_calls_failed,
        analyst_count=analyst_count,
        analyst_agreement_pct=analyst_agreement_pct,
        decision=decision,
        overall_confidence=overall_confidence,
        overlay_provided=overlay_provided,
        deliberation_enabled=deliberation_enabled,
        macro_context_available=macro_context_available,
    )


class TestRunMetrics:
    def test_dataclass_fields(self):
        """RunMetrics has all required fields."""
        m = _make_run_metrics()
        assert m.run_id == "run-001"
        assert m.instrument == "XAUUSD"
        assert m.total_latency_ms == 5000
        assert m.llm_cost_usd == 0.05
        assert m.analyst_agreement_pct == 75

    def test_asdict_roundtrip(self):
        """RunMetrics can be serialized to dict and back."""
        m = _make_run_metrics()
        d = asdict(m)
        assert d["run_id"] == "run-001"
        assert d["decision"] == "ENTER_LONG"
        assert isinstance(d["node_timings"], dict)

    def test_json_serializable(self):
        """RunMetrics asdict is JSON-serializable."""
        m = _make_run_metrics()
        s = json.dumps(asdict(m))
        assert "run-001" in s


# ── MetricsStore tests ───────────────────────────────────────────────────────

class TestMetricsStore:
    def test_empty_snapshot(self):
        """Empty store returns zero-valued snapshot."""
        store = MetricsStore()
        snap = store.snapshot()
        assert snap.total_runs == 0
        assert snap.total_cost_usd == 0.0
        assert snap.avg_latency_ms == 0.0
        assert snap.decision_distribution == {}
        assert snap.recent_runs == []

    def test_record_and_snapshot(self):
        """Recording a run updates the snapshot."""
        store = MetricsStore()
        store.record_run(_make_run_metrics())
        snap = store.snapshot()
        assert snap.total_runs == 1
        assert snap.total_cost_usd == 0.05
        assert snap.avg_latency_ms == 5000.0
        assert snap.decision_distribution == {"ENTER_LONG": 1}
        assert len(snap.recent_runs) == 1

    def test_multiple_runs_aggregation(self):
        """Multiple runs are properly aggregated."""
        store = MetricsStore()
        store.record_run(_make_run_metrics(run_id="r1", llm_cost_usd=0.10, decision="ENTER_LONG"))
        store.record_run(_make_run_metrics(run_id="r2", llm_cost_usd=0.20, decision="NO_TRADE"))
        store.record_run(_make_run_metrics(run_id="r3", llm_cost_usd=0.30, decision="ENTER_LONG"))

        snap = store.snapshot()
        assert snap.total_runs == 3
        assert snap.total_cost_usd == pytest.approx(0.60, abs=0.001)
        assert snap.avg_cost_per_run_usd == pytest.approx(0.20, abs=0.001)
        assert snap.decision_distribution["ENTER_LONG"] == 2
        assert snap.decision_distribution["NO_TRADE"] == 1

    def test_bounded_history(self):
        """MetricsStore respects max_entries bound."""
        store = MetricsStore(max_entries=3)
        for i in range(5):
            store.record_run(_make_run_metrics(run_id=f"r{i}"))
        assert store.run_count == 3
        snap = store.snapshot()
        assert snap.total_runs == 3
        # Oldest runs (r0, r1) should be evicted
        run_ids = [r["run_id"] for r in snap.recent_runs]
        assert "r0" not in run_ids
        assert "r1" not in run_ids

    def test_error_rate_calculation(self):
        """Error rate is correctly computed from failed/total calls."""
        store = MetricsStore()
        store.record_run(_make_run_metrics(
            run_id="r1", llm_calls=10, llm_calls_failed=2,
        ))
        snap = store.snapshot()
        assert snap.error_rate == pytest.approx(0.2, abs=0.01)

    def test_instrument_distribution(self):
        """Instrument distribution tracks run counts per instrument."""
        store = MetricsStore()
        store.record_run(_make_run_metrics(run_id="r1", instrument="XAUUSD"))
        store.record_run(_make_run_metrics(run_id="r2", instrument="EURUSD"))
        store.record_run(_make_run_metrics(run_id="r3", instrument="XAUUSD"))
        snap = store.snapshot()
        assert snap.instrument_distribution == {"XAUUSD": 2, "EURUSD": 1}

    def test_started_at(self):
        """MetricsStore records server start time."""
        store = MetricsStore()
        assert store.started_at is not None
        # Should be a valid ISO timestamp
        dt = datetime.fromisoformat(store.started_at)
        assert dt.year >= 2026

    def test_thread_safety(self):
        """MetricsStore is safe under concurrent writes."""
        import threading
        store = MetricsStore(max_entries=100)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    store.record_run(_make_run_metrics(run_id=f"t{thread_id}-r{i}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert store.run_count == 100  # 5 threads × 20 runs = 100

    def test_snapshot_recent_runs_limit(self):
        """Snapshot limits recent_runs to last 10."""
        store = MetricsStore(max_entries=50)
        for i in range(20):
            store.record_run(_make_run_metrics(run_id=f"r{i:03d}"))
        snap = store.snapshot()
        assert len(snap.recent_runs) == 10
        # Should be the last 10
        assert snap.recent_runs[0]["run_id"] == "r010"
        assert snap.recent_runs[9]["run_id"] == "r019"


# ── Global metrics_store singleton test ──────────────────────────────────────

class TestGlobalMetricsStore:
    def test_singleton_accessible(self):
        """Global metrics_store singleton is importable and functional."""
        assert metrics_store is not None
        assert isinstance(metrics_store.started_at, str)

    def test_singleton_records(self):
        """Global metrics_store can record and snapshot."""
        initial = metrics_store.run_count
        metrics_store.record_run(_make_run_metrics(run_id="global-test"))
        assert metrics_store.run_count >= initial + 1


# ── Audit logger correlation ID test ─────────────────────────────────────────

class TestAuditLogCorrelation:
    def test_log_run_includes_correlation_id(self, tmp_path):
        """log_run includes correlation_id in the audit log entry."""
        from ai_analyst.core import logger as audit_logger

        # Temporarily override LOG_DIR
        original_log_dir = audit_logger.LOG_DIR
        audit_logger.LOG_DIR = tmp_path

        token = correlation_ctx.set("corr-test-789")
        try:
            from ai_analyst.models.ground_truth import (
                GroundTruthPacket,
                RiskConstraints,
                MarketContext,
                ScreenshotMetadata,
            )
            from ai_analyst.models.analyst_output import AnalystOutput, KeyLevels
            from ai_analyst.models.arbiter_output import (
                FinalVerdict,
                AuditLog,
            )

            gt = GroundTruthPacket(
                instrument="XAUUSD",
                session="NY",
                timeframes=["H4"],
                charts={"H4": "dGVzdA=="},
                screenshot_metadata=[ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")],
                risk_constraints=RiskConstraints(min_rr=2.0),
                context=MarketContext(account_balance=10000),
            )

            analyst = AnalystOutput(
                htf_bias="bullish",
                structure_state="continuation",
                key_levels=KeyLevels(premium=["2050"], discount=["2000"]),
                setup_valid=True,
                confidence=0.8,
                recommended_action="LONG",
                notes="test note",
                disqualifiers=[],
            )

            verdict = FinalVerdict(
                final_bias="bullish",
                decision="ENTER_LONG",
                approved_setups=[],
                no_trade_conditions=[],
                overall_confidence=0.8,
                analyst_agreement_pct=75,
                risk_override_applied=False,
                arbiter_notes="test",
                audit_log=AuditLog(
                    run_id=gt.run_id,
                    analysts_received=1,
                    analysts_valid=1,
                    htf_consensus=True,
                    setup_consensus=True,
                    risk_override=False,
                ),
            )

            log_path = audit_logger.log_run(gt, [analyst], verdict)
            log_content = log_path.read_text()
            entry = json.loads(log_content.strip())
            assert entry["correlation_id"] == "corr-test-789"
            assert entry["run_id"] == gt.run_id

        finally:
            correlation_ctx.reset(token)
            audit_logger.LOG_DIR = original_log_dir


# ── MetricsSnapshot dataclass tests ──────────────────────────────────────────

class TestMetricsSnapshot:
    def test_empty_snapshot_serializable(self):
        """Empty MetricsSnapshot is JSON-serializable."""
        snap = MetricsSnapshot(
            total_runs=0,
            total_cost_usd=0.0,
            avg_cost_per_run_usd=0.0,
            avg_latency_ms=0.0,
            avg_analyst_agreement_pct=0.0,
            decision_distribution={},
            instrument_distribution={},
            runs_last_hour=0,
            runs_last_24h=0,
            last_run_at=None,
            error_rate=0.0,
            recent_runs=[],
        )
        s = json.dumps(asdict(snap))
        assert '"total_runs": 0' in s

    def test_snapshot_with_data(self):
        """MetricsSnapshot with data is JSON-serializable."""
        snap = MetricsSnapshot(
            total_runs=5,
            total_cost_usd=1.23,
            avg_cost_per_run_usd=0.246,
            avg_latency_ms=3500.0,
            avg_analyst_agreement_pct=80.0,
            decision_distribution={"ENTER_LONG": 3, "NO_TRADE": 2},
            instrument_distribution={"XAUUSD": 5},
            runs_last_hour=2,
            runs_last_24h=5,
            last_run_at="2026-03-05T12:00:00+00:00",
            error_rate=0.05,
            recent_runs=[{"run_id": "r1"}],
        )
        d = asdict(snap)
        assert d["total_runs"] == 5
        assert d["decision_distribution"]["ENTER_LONG"] == 3
