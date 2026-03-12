"""Deterministic tests for the scheduler module.

No APScheduler instance is started in any test. Tests exercise:
- schedule config correctness (instruments, intervals, families, windows)
- job isolation (failure in one instrument does not propagate)
- failure logging (structured log on error)
- success logging (structured log on success)
- last-known-good preservation (artifacts untouched on failure)
- no-overlap config (max_instances=1 set on every job)
- build_scheduler produces correct job configuration
- market-hours-aware skip/proceed decisions (PR 1)
- structured log fields include market state + freshness (PR 1)
"""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import logging
import pytest

from market_data_officer.market_hours import MarketState
from market_data_officer.scheduler import (
    SCHEDULE_CONFIG,
    build_scheduler,
    refresh_instrument,
)


# ── Schedule config tests ────────────────────────────────────────────


class TestScheduleConfig:
    """Verify SCHEDULE_CONFIG is correct and complete."""

    TRUSTED_INSTRUMENTS = {"EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "XPTUSD"}

    def test_all_trusted_instruments_present(self):
        """Every trusted instrument has a schedule config entry."""
        assert set(SCHEDULE_CONFIG.keys()) == self.TRUSTED_INSTRUMENTS

    def test_fx_instruments_cadence(self):
        """FX instruments (EURUSD, GBPUSD) use 1h interval."""
        for sym in ("EURUSD", "GBPUSD"):
            assert SCHEDULE_CONFIG[sym]["interval_hours"] == 1
            assert SCHEDULE_CONFIG[sym]["family"] == "FX"

    def test_metals_instruments_cadence(self):
        """Metals instruments (XAUUSD, XAGUSD, XPTUSD) use 4h interval."""
        for sym in ("XAUUSD", "XAGUSD", "XPTUSD"):
            assert SCHEDULE_CONFIG[sym]["interval_hours"] == 4
            assert SCHEDULE_CONFIG[sym]["family"] == "Metals"

    def test_window_hours_present(self):
        """Every instrument config includes a window_hours key."""
        for sym, cfg in SCHEDULE_CONFIG.items():
            assert "window_hours" in cfg, f"{sym} missing window_hours"
            assert cfg["window_hours"] > 0

    def test_fx_window_hours(self):
        """FX window is 24h."""
        for sym in ("EURUSD", "GBPUSD"):
            assert SCHEDULE_CONFIG[sym]["window_hours"] == 24

    def test_metals_window_hours(self):
        """Metals window is 48h."""
        for sym in ("XAUUSD", "XAGUSD", "XPTUSD"):
            assert SCHEDULE_CONFIG[sym]["window_hours"] == 48

    def test_config_keys_complete(self):
        """Every config entry has all required keys."""
        required_keys = {"interval_hours", "window_hours", "family"}
        for sym, cfg in SCHEDULE_CONFIG.items():
            assert required_keys.issubset(cfg.keys()), (
                f"{sym} missing keys: {required_keys - cfg.keys()}"
            )


# ── Job isolation tests ──────────────────────────────────────────────


class TestJobIsolation:
    """Prove that refresh_instrument catches all exceptions."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_success_returns_success_outcome(self, mock_pipeline):
        """A successful pipeline run returns outcome='success'."""
        mock_pipeline.return_value = None
        result = refresh_instrument("EURUSD")
        assert result["outcome"] == "success"
        assert result["instrument"] == "EURUSD"
        assert "duration" in result

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_pipeline_called_with_correct_symbol(self, mock_pipeline):
        """The pipeline is called with the correct instrument symbol."""
        mock_pipeline.return_value = None
        refresh_instrument("GBPUSD")
        call_args = mock_pipeline.call_args
        assert call_args.kwargs["symbol"] == "GBPUSD"

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_pipeline_called_with_date_range(self, mock_pipeline):
        """The pipeline is called with start_date and end_date."""
        mock_pipeline.return_value = None
        refresh_instrument("EURUSD")
        call_args = mock_pipeline.call_args
        assert call_args.kwargs["start_date"] is not None
        assert call_args.kwargs["end_date"] is not None
        # end_date should be after start_date
        assert call_args.kwargs["end_date"] > call_args.kwargs["start_date"]

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_window_hours_from_config(self, mock_pipeline):
        """The date window matches the config window_hours."""
        from datetime import timedelta
        mock_pipeline.return_value = None
        config = {"interval_hours": 1, "window_hours": 12, "family": "FX"}
        refresh_instrument("EURUSD", config=config)
        call_args = mock_pipeline.call_args
        delta = call_args.kwargs["end_date"] - call_args.kwargs["start_date"]
        # Allow small timing tolerance (< 1 second)
        assert abs(delta.total_seconds() - 12 * 3600) < 1.0

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_value_error_caught(self, mock_pipeline):
        """ValueError (unknown instrument) is caught at the job boundary."""
        mock_pipeline.side_effect = ValueError("Unknown instrument: FAKE")
        result = refresh_instrument("FAKE")
        assert result["outcome"] == "failure"
        assert "Unknown instrument" in result["error"]

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_runtime_error_caught(self, mock_pipeline):
        """RuntimeError is caught at the job boundary."""
        mock_pipeline.side_effect = RuntimeError("decode failed")
        result = refresh_instrument("EURUSD")
        assert result["outcome"] == "failure"
        assert "decode failed" in result["error"]

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_connection_error_caught(self, mock_pipeline):
        """ConnectionError (network failure) is caught at the job boundary."""
        mock_pipeline.side_effect = ConnectionError("timeout")
        result = refresh_instrument("XAUUSD")
        assert result["outcome"] == "failure"
        assert "timeout" in result["error"]

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_generic_exception_caught(self, mock_pipeline):
        """Any Exception subclass is caught at the job boundary."""
        mock_pipeline.side_effect = Exception("unexpected")
        result = refresh_instrument("XAGUSD")
        assert result["outcome"] == "failure"
        assert "unexpected" in result["error"]

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_does_not_raise(self, mock_pipeline):
        """A failed job must not raise — it returns a failure dict."""
        mock_pipeline.side_effect = Exception("boom")
        # This must not raise
        result = refresh_instrument("XPTUSD")
        assert result["outcome"] == "failure"


# ── Logging tests ────────────────────────────────────────────────────


class TestScheduleLogging:
    """Prove structured log entries are emitted."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_success_log_emitted(self, mock_pipeline, caplog):
        """A successful run emits an INFO log with instrument and SUCCESS."""
        mock_pipeline.return_value = None
        import logging
        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            refresh_instrument("EURUSD")
        assert any("EURUSD" in r.message and "SUCCESS" in r.message for r in caplog.records)

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_log_emitted(self, mock_pipeline, caplog):
        """A failed run emits an ERROR log with instrument and FAILURE."""
        mock_pipeline.side_effect = RuntimeError("test error")
        import logging
        with caplog.at_level(logging.ERROR, logger="market_data_officer.scheduler"):
            refresh_instrument("EURUSD")
        assert any("EURUSD" in r.message and "FAILURE" in r.message for r in caplog.records)

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_log_includes_error_message(self, mock_pipeline, caplog):
        """Failure log includes the error string."""
        mock_pipeline.side_effect = ValueError("bad symbol")
        import logging
        with caplog.at_level(logging.ERROR, logger="market_data_officer.scheduler"):
            refresh_instrument("EURUSD")
        assert any("bad symbol" in r.message for r in caplog.records)


# ── Last-known-good preservation tests ───────────────────────────────


class TestLastKnownGood:
    """Prove artifacts are untouched on failure."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_pipeline_not_called_after_failure(self, mock_pipeline):
        """On failure, run_pipeline is called exactly once (no retry in same job)."""
        mock_pipeline.side_effect = Exception("fail")
        refresh_instrument("EURUSD")
        assert mock_pipeline.call_count == 1

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_no_artifact_deletion_on_failure(self, mock_pipeline):
        """The job function does not delete or overwrite anything on failure.

        Since the job only calls run_pipeline and catches the exception,
        and run_pipeline only writes on success, artifacts are preserved.
        This test proves the job boundary does not introduce any cleanup/delete.
        """
        mock_pipeline.side_effect = Exception("fail")
        result = refresh_instrument("EURUSD")
        # Job returned cleanly with failure — no side effects
        assert result["outcome"] == "failure"
        # Pipeline was the only thing called
        assert mock_pipeline.call_count == 1


# ── build_scheduler config tests ─────────────────────────────────────


class TestBuildScheduler:
    """Verify build_scheduler produces correct job configuration.

    NOTE: We do NOT start the scheduler. We only inspect the job list.
    """

    def test_one_job_per_instrument(self):
        """Each trusted instrument gets exactly one job."""
        scheduler = build_scheduler()
        jobs = scheduler.get_jobs()
        job_ids = {j.id for j in jobs}
        expected = {f"refresh_{sym}" for sym in SCHEDULE_CONFIG}
        assert job_ids == expected
        # No shutdown needed — scheduler was never started

    def test_max_instances_is_one(self):
        """Every job has max_instances=1 (no-overlap policy)."""
        scheduler = build_scheduler()
        for job in scheduler.get_jobs():
            assert job.max_instances == 1, f"{job.id} has max_instances={job.max_instances}"
        # No shutdown needed — scheduler was never started

    def test_coalesce_enabled(self):
        """Every job has coalesce=True."""
        scheduler = build_scheduler()
        for job in scheduler.get_jobs():
            assert job.coalesce is True, f"{job.id} has coalesce={job.coalesce}"
        # No shutdown needed — scheduler was never started

    def test_interval_matches_config(self):
        """Each job's interval matches its SCHEDULE_CONFIG entry."""
        scheduler = build_scheduler()
        for job in scheduler.get_jobs():
            sym = job.id.replace("refresh_", "")
            expected_hours = SCHEDULE_CONFIG[sym]["interval_hours"]
            # APScheduler IntervalTrigger stores interval as timedelta
            from datetime import timedelta
            assert job.trigger.interval == timedelta(hours=expected_hours), (
                f"{sym}: expected {expected_hours}h, got {job.trigger.interval}"
            )
        # No shutdown needed — scheduler was never started

    def test_custom_config_override(self):
        """build_scheduler accepts a custom config dict."""
        custom = {
            "TEST_SYM": {"interval_hours": 2, "window_hours": 6, "family": "Test"},
        }
        scheduler = build_scheduler(schedule_config=custom)
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "refresh_TEST_SYM"
        # No shutdown needed — scheduler was never started


# ── Market-hours-aware scheduler integration tests (PR 1) ────────────


# Deterministic timestamps — no real clock dependency
_TUESDAY_14 = datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc)
_SATURDAY_03 = datetime(2026, 3, 14, 3, 0, tzinfo=timezone.utc)
_FRIDAY_22 = datetime(2026, 3, 13, 22, 0, tzinfo=timezone.utc)
_SUNDAY_20 = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)


class TestMarketHoursIntegration:
    """Prove scheduler correctly skips/proceeds based on market state."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_open_market_calls_pipeline(self, mock_pipeline):
        """When market is OPEN, run_pipeline is called."""
        mock_pipeline.return_value = None
        result = refresh_instrument("EURUSD", _now=_TUESDAY_14)
        assert result["outcome"] == "success"
        assert mock_pipeline.call_count == 1

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_closed_market_skips_pipeline(self, mock_pipeline):
        """When market is CLOSED_EXPECTED, run_pipeline is NOT called.

        This is the negative test proving refresh is skipped, not assumed.
        """
        result = refresh_instrument("EURUSD", _now=_FRIDAY_22)
        assert result["outcome"] == "skipped"
        assert result["market_state"] == "CLOSED_EXPECTED"
        mock_pipeline.assert_not_called()

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_off_session_skips_pipeline(self, mock_pipeline):
        """When market is OFF_SESSION_EXPECTED (Saturday), pipeline is skipped."""
        result = refresh_instrument("EURUSD", _now=_SATURDAY_03)
        assert result["outcome"] == "skipped"
        assert result["market_state"] == "OFF_SESSION_EXPECTED"
        mock_pipeline.assert_not_called()

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_sunday_pre_open_skips(self, mock_pipeline):
        """Sunday before session open → CLOSED_EXPECTED, pipeline skipped."""
        result = refresh_instrument("GBPUSD", _now=_SUNDAY_20)
        assert result["outcome"] == "skipped"
        assert result["market_state"] == "CLOSED_EXPECTED"
        mock_pipeline.assert_not_called()

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_skip_preserves_artifacts(self, mock_pipeline):
        """Skipped refresh never calls pipeline — artifacts untouched."""
        result = refresh_instrument("XAUUSD", _now=_SATURDAY_03)
        assert result["outcome"] == "skipped"
        mock_pipeline.assert_not_called()

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_preserves_artifacts_with_market_state(self, mock_pipeline):
        """On OPEN failure, artifacts preserved and market state in result."""
        mock_pipeline.side_effect = RuntimeError("provider down")
        result = refresh_instrument("EURUSD", _now=_TUESDAY_14)
        assert result["outcome"] == "failure"
        assert result["market_state"] == "OPEN"
        assert mock_pipeline.call_count == 1


class TestStructuredLogFields:
    """Prove structured log fields include market state and freshness."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_success_result_has_structured_fields(self, mock_pipeline):
        """Success result includes market_state, freshness, reason_code."""
        mock_pipeline.return_value = None
        result = refresh_instrument("EURUSD", _now=_TUESDAY_14)
        assert "market_state" in result
        assert "freshness" in result
        assert "reason_code" in result
        assert "evaluation_ts" in result
        assert result["market_state"] == "OPEN"
        assert result["freshness"] == "FRESH"

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_result_has_structured_fields(self, mock_pipeline):
        """Failure result includes market_state, freshness, reason_code."""
        mock_pipeline.side_effect = Exception("boom")
        result = refresh_instrument("EURUSD", _now=_TUESDAY_14)
        assert "market_state" in result
        assert "freshness" in result
        assert "reason_code" in result
        assert result["market_state"] == "OPEN"

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_skip_result_has_market_state(self, mock_pipeline):
        """Skipped result includes market_state and evaluation_ts."""
        result = refresh_instrument("EURUSD", _now=_SATURDAY_03)
        assert result["market_state"] == "OFF_SESSION_EXPECTED"
        assert "evaluation_ts" in result

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_success_log_includes_market_fields(self, mock_pipeline, caplog):
        """Success log message contains market_state and freshness."""
        mock_pipeline.return_value = None
        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            refresh_instrument("EURUSD", _now=_TUESDAY_14)
        log_text = " ".join(r.message for r in caplog.records)
        assert "market_state=OPEN" in log_text
        assert "freshness=FRESH" in log_text

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_skip_log_includes_market_state(self, mock_pipeline, caplog):
        """Skip log message contains market_state."""
        with caplog.at_level(logging.INFO, logger="market_data_officer.scheduler"):
            refresh_instrument("EURUSD", _now=_SATURDAY_03)
        log_text = " ".join(r.message for r in caplog.records)
        assert "SKIPPED" in log_text
        assert "market_state=OFF_SESSION_EXPECTED" in log_text

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_log_includes_market_fields(self, mock_pipeline, caplog):
        """Failure log message contains market_state and freshness."""
        mock_pipeline.side_effect = Exception("fail")
        with caplog.at_level(logging.ERROR, logger="market_data_officer.scheduler"):
            refresh_instrument("EURUSD", _now=_TUESDAY_14)
        log_text = " ".join(r.message for r in caplog.records)
        assert "market_state=OPEN" in log_text


# ── PR 2: Alert wiring integration tests ─────────────────────────────

from market_data_officer.scheduler import _alert_state, _get_alert_state
from market_data_officer.alert_policy import AlertLevel, RefreshOutcome


@pytest.fixture(autouse=False)
def clear_alert_state():
    """Clear module-level alert state before and after each test."""
    _alert_state.clear()
    yield
    _alert_state.clear()


class TestAlertWiringStaleEscalation:
    """Live + stale-live sequence emits WARN then CRITICAL at thresholds."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_warn_at_threshold(self, mock_pipeline, caplog, clear_alert_state):
        """Repeated stale-live emits WARN at threshold."""
        # Simulate stale results — pipeline succeeds but freshness is STALE_BAD
        # by mocking classify_freshness to return STALE_BAD
        mock_pipeline.return_value = None

        from market_data_officer.market_hours import FreshnessClassification, FreshnessResult, ReasonCode
        stale_result = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result):
            with caplog.at_level(logging.WARNING, logger="market_data_officer.scheduler"):
                # Run 1: consecutive_stale_live goes to 1 (below threshold)
                r1 = refresh_instrument("EURUSD", _now=_TUESDAY_14)
                # Run 2: consecutive_stale_live goes to 2 (at WARN threshold)
                r2 = refresh_instrument("EURUSD", _now=_TUESDAY_14)

        assert r2.get("alert_level") == "warn"
        assert r2.get("alert_emitted") is True
        alert_logs = [r for r in caplog.records if "ALERT" in r.message
                      and "ALERT_EVAL_ERROR" not in r.message]
        assert len(alert_logs) >= 1

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_critical_at_threshold(self, mock_pipeline, caplog, clear_alert_state):
        """Repeated stale-live emits CRITICAL at higher threshold."""
        mock_pipeline.return_value = None

        from market_data_officer.market_hours import FreshnessClassification, FreshnessResult, ReasonCode
        stale_result = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result):
            with caplog.at_level(logging.WARNING, logger="market_data_officer.scheduler"):
                for _ in range(4):
                    result = refresh_instrument("EURUSD", _now=_TUESDAY_14)

        assert result.get("alert_level") == "critical"
        assert result.get("alert_emitted") is True


class TestAlertWiringFailureEscalation:
    """Live + repeated refresh failures emit CRITICAL."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_repeated_failures_escalate(self, mock_pipeline, caplog, clear_alert_state):
        mock_pipeline.side_effect = RuntimeError("provider down")

        with caplog.at_level(logging.WARNING, logger="market_data_officer.scheduler"):
            for _ in range(2):
                result = refresh_instrument("EURUSD", _now=_TUESDAY_14)

        assert result.get("alert_level") == "critical"
        assert "failure" in result.get("alert_reason", "")


class TestAlertWiringClosedSuppression:
    """Closed/off-session path emits no alert even after many evaluations."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_no_alerts_during_closure(self, mock_pipeline, caplog, clear_alert_state):
        with caplog.at_level(logging.WARNING, logger="market_data_officer.scheduler"):
            for _ in range(10):
                result = refresh_instrument("EURUSD", _now=_SATURDAY_03)

        assert result.get("alert_level") == "none"
        alert_logs = [r for r in caplog.records if "ALERT" in r.message
                      and "ALERT_EVAL_ERROR" not in r.message]
        assert len(alert_logs) == 0


class TestAlertWiringRecovery:
    """Recovery emits one structured recovery log."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_recovery_log_emitted(self, mock_pipeline, caplog, clear_alert_state):
        """After escalation, a successful refresh emits recovery."""
        from market_data_officer.market_hours import FreshnessClassification, FreshnessResult, ReasonCode

        stale_result = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        fresh_result = FreshnessResult(
            classification=FreshnessClassification.FRESH,
            reason_code=ReasonCode.OPEN_AND_FRESH,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=30.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        mock_pipeline.return_value = None

        # Escalate to WARN
        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result):
            for _ in range(2):
                refresh_instrument("EURUSD", _now=_TUESDAY_14)

        # Recovery
        with patch("market_data_officer.scheduler.classify_freshness", return_value=fresh_result):
            with caplog.at_level(logging.WARNING, logger="market_data_officer.scheduler"):
                caplog.clear()
                result = refresh_instrument("EURUSD", _now=_TUESDAY_14)

        assert result.get("alert_level") == "none"
        assert result.get("alert_emitted") is True
        # Check recovery log has recovered_from fields
        alert_logs = [r for r in caplog.records if "ALERT" in r.message
                      and "ALERT_EVAL_ERROR" not in r.message]
        assert len(alert_logs) == 1
        assert "recovered_from_level" in alert_logs[0].message
        assert "recovered_from_reason" in alert_logs[0].message


class TestAlertWiringStructuredFields:
    """Alert logs include all required context fields from §6.8."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_alert_log_has_required_fields(self, mock_pipeline, caplog, clear_alert_state):
        from market_data_officer.market_hours import FreshnessClassification, FreshnessResult, ReasonCode

        stale_result = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        mock_pipeline.return_value = None

        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result):
            with caplog.at_level(logging.WARNING, logger="market_data_officer.scheduler"):
                for _ in range(2):
                    refresh_instrument("EURUSD", _now=_TUESDAY_14)

        alert_logs = [r for r in caplog.records if "ALERT" in r.message
                      and "ALERT_EVAL_ERROR" not in r.message]
        assert len(alert_logs) >= 1
        log_msg = alert_logs[-1].message
        for field in [
            "alert_level=", "reason_code=", "market_state=",
            "freshness=", "refresh_outcome=", "consecutive_stale_live=",
            "consecutive_failures=", "last_success_ts=", "eval_ts=",
        ]:
            assert field in log_msg, f"Missing field: {field}"


class TestAlertWiringStateReset:
    """Scheduler state resets correctly after success."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_state_resets_after_recovery(self, mock_pipeline, caplog, clear_alert_state):
        from market_data_officer.market_hours import FreshnessClassification, FreshnessResult, ReasonCode

        stale_result = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        mock_pipeline.return_value = None

        # Escalate
        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result):
            for _ in range(2):
                refresh_instrument("EURUSD", _now=_TUESDAY_14)

        # Verify escalated state
        state = _get_alert_state("EURUSD")
        assert state["last_alert_level"] == AlertLevel.WARN

        # Recover (default classify_freshness will return FRESH for just-refreshed)
        refresh_instrument("EURUSD", _now=_TUESDAY_14)

        # State should be reset
        state = _get_alert_state("EURUSD")
        assert state["last_alert_level"] == AlertLevel.NONE
        assert state["consecutive_stale_live"] == 0
        assert state["consecutive_failures"] == 0


class TestAlertIsolation:
    """Alert evaluation failure does not crash the scheduler."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_alert_eval_exception_does_not_crash(self, mock_pipeline, caplog, clear_alert_state):
        """If derive_alert_decision raises, scheduler still returns result."""
        mock_pipeline.return_value = None

        with patch("market_data_officer.scheduler.derive_alert_decision", side_effect=RuntimeError("policy bug")):
            with caplog.at_level(logging.ERROR, logger="market_data_officer.scheduler"):
                result = refresh_instrument("EURUSD", _now=_TUESDAY_14)

        # Refresh succeeded — result still returned
        assert result["outcome"] == "success"
        assert result["instrument"] == "EURUSD"
        # Alert error was logged
        alert_error_logs = [r for r in caplog.records if "ALERT_EVAL_ERROR" in r.message]
        assert len(alert_error_logs) >= 1


class TestAlertPerInstrumentIsolation:
    """Instrument A's failures do not affect instrument B's counters."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_counters_per_instrument(self, mock_pipeline, caplog, clear_alert_state):
        mock_pipeline.side_effect = RuntimeError("down")

        refresh_instrument("EURUSD", _now=_TUESDAY_14)
        refresh_instrument("EURUSD", _now=_TUESDAY_14)

        state_eur = _get_alert_state("EURUSD")
        state_gbp = _get_alert_state("GBPUSD")

        assert state_eur["consecutive_failures"] == 2
        assert state_gbp["consecutive_failures"] == 0


class TestHoldThroughClosure:
    """Counter at 2 before weekend, resumes at 3 on Monday STALE_BAD."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_counter_hold_and_resume(self, mock_pipeline, caplog, clear_alert_state):
        from market_data_officer.market_hours import FreshnessClassification, FreshnessResult, ReasonCode

        stale_result = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_TUESDAY_14,
        )

        mock_pipeline.return_value = None

        # Tuesday: 2 stale evals → counter at 2 (WARN threshold)
        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result):
            for _ in range(2):
                refresh_instrument("EURUSD", _now=_TUESDAY_14)

        state = _get_alert_state("EURUSD")
        assert state["consecutive_stale_live"] == 2

        # Saturday: many closed evals — counter should hold at 2
        for _ in range(5):
            refresh_instrument("EURUSD", _now=_SATURDAY_03)

        state = _get_alert_state("EURUSD")
        assert state["consecutive_stale_live"] == 2  # held, not reset

        # Monday: one more stale eval → counter resumes at 3
        _MONDAY_10 = datetime(2026, 3, 16, 10, 0, tzinfo=timezone.utc)
        stale_result_monday = FreshnessResult(
            classification=FreshnessClassification.STALE_BAD,
            reason_code=ReasonCode.OPEN_AND_OVERDUE,
            market_state=MarketState.OPEN,
            instrument="EURUSD",
            age_minutes=120.0,
            threshold_minutes=90.0,
            evaluation_ts=_MONDAY_10,
        )
        with patch("market_data_officer.scheduler.classify_freshness", return_value=stale_result_monday):
            refresh_instrument("EURUSD", _now=_MONDAY_10)

        state = _get_alert_state("EURUSD")
        assert state["consecutive_stale_live"] == 3  # resumed, not 1


class TestExistingPR1BehaviorIntact:
    """Existing PR 1 runtime behavior remains intact after alert wiring."""

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_success_still_returns_expected_shape(self, mock_pipeline, clear_alert_state):
        mock_pipeline.return_value = None
        result = refresh_instrument("EURUSD", _now=_TUESDAY_14)
        assert result["outcome"] == "success"
        assert result["instrument"] == "EURUSD"
        assert "market_state" in result
        assert "freshness" in result

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_failure_still_returns_expected_shape(self, mock_pipeline, clear_alert_state):
        mock_pipeline.side_effect = RuntimeError("boom")
        result = refresh_instrument("EURUSD", _now=_TUESDAY_14)
        assert result["outcome"] == "failure"
        assert "error" in result

    @patch("market_data_officer.scheduler.run_pipeline")
    def test_skip_still_returns_expected_shape(self, mock_pipeline, clear_alert_state):
        result = refresh_instrument("EURUSD", _now=_SATURDAY_03)
        assert result["outcome"] == "skipped"
        assert result["market_state"] == "OFF_SESSION_EXPECTED"
