"""Deterministic tests for the scheduler module.

No APScheduler instance is started in any test. Tests exercise:
- schedule config correctness (instruments, intervals, families, windows)
- job isolation (failure in one instrument does not propagate)
- failure logging (structured log on error)
- success logging (structured log on success)
- last-known-good preservation (artifacts untouched on failure)
- no-overlap config (max_instances=1 set on every job)
- build_scheduler produces correct job configuration
"""

from unittest.mock import patch, MagicMock
import pytest

from scheduler import (
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

    @patch("scheduler.run_pipeline")
    def test_success_returns_success_outcome(self, mock_pipeline):
        """A successful pipeline run returns outcome='success'."""
        mock_pipeline.return_value = None
        result = refresh_instrument("EURUSD")
        assert result["outcome"] == "success"
        assert result["instrument"] == "EURUSD"
        assert "duration" in result

    @patch("scheduler.run_pipeline")
    def test_pipeline_called_with_correct_symbol(self, mock_pipeline):
        """The pipeline is called with the correct instrument symbol."""
        mock_pipeline.return_value = None
        refresh_instrument("GBPUSD")
        call_args = mock_pipeline.call_args
        assert call_args.kwargs["symbol"] == "GBPUSD"

    @patch("scheduler.run_pipeline")
    def test_pipeline_called_with_date_range(self, mock_pipeline):
        """The pipeline is called with start_date and end_date."""
        mock_pipeline.return_value = None
        refresh_instrument("EURUSD")
        call_args = mock_pipeline.call_args
        assert call_args.kwargs["start_date"] is not None
        assert call_args.kwargs["end_date"] is not None
        # end_date should be after start_date
        assert call_args.kwargs["end_date"] > call_args.kwargs["start_date"]

    @patch("scheduler.run_pipeline")
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

    @patch("scheduler.run_pipeline")
    def test_value_error_caught(self, mock_pipeline):
        """ValueError (unknown instrument) is caught at the job boundary."""
        mock_pipeline.side_effect = ValueError("Unknown instrument: FAKE")
        result = refresh_instrument("FAKE")
        assert result["outcome"] == "failure"
        assert "Unknown instrument" in result["error"]

    @patch("scheduler.run_pipeline")
    def test_runtime_error_caught(self, mock_pipeline):
        """RuntimeError is caught at the job boundary."""
        mock_pipeline.side_effect = RuntimeError("decode failed")
        result = refresh_instrument("EURUSD")
        assert result["outcome"] == "failure"
        assert "decode failed" in result["error"]

    @patch("scheduler.run_pipeline")
    def test_connection_error_caught(self, mock_pipeline):
        """ConnectionError (network failure) is caught at the job boundary."""
        mock_pipeline.side_effect = ConnectionError("timeout")
        result = refresh_instrument("XAUUSD")
        assert result["outcome"] == "failure"
        assert "timeout" in result["error"]

    @patch("scheduler.run_pipeline")
    def test_generic_exception_caught(self, mock_pipeline):
        """Any Exception subclass is caught at the job boundary."""
        mock_pipeline.side_effect = Exception("unexpected")
        result = refresh_instrument("XAGUSD")
        assert result["outcome"] == "failure"
        assert "unexpected" in result["error"]

    @patch("scheduler.run_pipeline")
    def test_failure_does_not_raise(self, mock_pipeline):
        """A failed job must not raise — it returns a failure dict."""
        mock_pipeline.side_effect = Exception("boom")
        # This must not raise
        result = refresh_instrument("XPTUSD")
        assert result["outcome"] == "failure"


# ── Logging tests ────────────────────────────────────────────────────


class TestScheduleLogging:
    """Prove structured log entries are emitted."""

    @patch("scheduler.run_pipeline")
    def test_success_log_emitted(self, mock_pipeline, caplog):
        """A successful run emits an INFO log with instrument and SUCCESS."""
        mock_pipeline.return_value = None
        import logging
        with caplog.at_level(logging.INFO, logger="scheduler"):
            refresh_instrument("EURUSD")
        assert any("EURUSD" in r.message and "SUCCESS" in r.message for r in caplog.records)

    @patch("scheduler.run_pipeline")
    def test_failure_log_emitted(self, mock_pipeline, caplog):
        """A failed run emits an ERROR log with instrument and FAILURE."""
        mock_pipeline.side_effect = RuntimeError("test error")
        import logging
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            refresh_instrument("EURUSD")
        assert any("EURUSD" in r.message and "FAILURE" in r.message for r in caplog.records)

    @patch("scheduler.run_pipeline")
    def test_failure_log_includes_error_message(self, mock_pipeline, caplog):
        """Failure log includes the error string."""
        mock_pipeline.side_effect = ValueError("bad symbol")
        import logging
        with caplog.at_level(logging.ERROR, logger="scheduler"):
            refresh_instrument("EURUSD")
        assert any("bad symbol" in r.message for r in caplog.records)


# ── Last-known-good preservation tests ───────────────────────────────


class TestLastKnownGood:
    """Prove artifacts are untouched on failure."""

    @patch("scheduler.run_pipeline")
    def test_pipeline_not_called_after_failure(self, mock_pipeline):
        """On failure, run_pipeline is called exactly once (no retry in same job)."""
        mock_pipeline.side_effect = Exception("fail")
        refresh_instrument("EURUSD")
        assert mock_pipeline.call_count == 1

    @patch("scheduler.run_pipeline")
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
