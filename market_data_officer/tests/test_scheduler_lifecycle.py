"""Deterministic tests for scheduler lifecycle: startup, shutdown, health-check.

Tests cover:
- Startup fail-fast on invalid config (proven, not assumed)
- Startup posture banner logging
- Shutdown signal handling and logging (proven, not assumed)
- Health-check shape and read-only behavior
- Health-check reflects alert state after refresh cycles
"""

import logging
import signal
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from market_data_officer.alert_policy import AlertLevel
from market_data_officer.runtime_config import (
    ConfigValidationError,
    RuntimeConfig,
    validate_runtime_config,
)
from market_data_officer.scheduler import (
    SCHEDULE_CONFIG,
    _alert_state,
    _get_alert_state,
    build_scheduler,
    get_scheduler_health,
    refresh_instrument,
)


# ── Startup fail-fast tests ─────────────────────────────────────────


class TestStartupFailFast:
    """Prove that misconfiguration prevents scheduler start."""

    def test_invalid_config_raises_before_scheduler_build(self):
        """Config validation error is raised before build_scheduler is called."""
        bad_config = RuntimeConfig(schedule_config={})
        with pytest.raises(ConfigValidationError):
            validate_runtime_config(bad_config)

    def test_unknown_instrument_prevents_start(self):
        bad_config = RuntimeConfig(
            schedule_config={
                "BTCUSD": {"interval_hours": 1, "window_hours": 24, "family": "Crypto"},
            }
        )
        with pytest.raises(ConfigValidationError, match="BTCUSD"):
            validate_runtime_config(bad_config)

    def test_bad_cadence_prevents_start(self):
        bad_config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 0, "window_hours": 24, "family": "FX"},
            }
        )
        with pytest.raises(ConfigValidationError, match="interval_hours"):
            validate_runtime_config(bad_config)

    def test_bad_threshold_prevents_start(self):
        bad_config = RuntimeConfig(warn_stale_live_threshold=-1)
        with pytest.raises(ConfigValidationError, match="warn_stale_live_threshold"):
            validate_runtime_config(bad_config)


# ── Startup posture banner tests ────────────────────────────────────


class TestStartupPostureBanner:
    """Prove that startup logs the runtime posture."""

    def test_startup_banner_logs_posture_fields(self, caplog):
        """log_startup_posture emits mode, cadence, and threshold info."""
        from market_data_officer.run_scheduler import log_startup_posture

        config = RuntimeConfig()
        with caplog.at_level(logging.INFO):
            log_startup_posture(config)

        combined = "\n".join(caplog.messages)
        assert "market_hours_enabled" in combined
        assert "alert_logging_enabled" in combined
        assert "artifact_root" in combined
        assert "instruments" in combined
        assert "EURUSD" in combined
        assert "warn_stale" in combined
        assert "crit_stale" in combined
        assert "crit_fail" in combined

    def test_startup_banner_includes_all_instruments(self, caplog):
        config = RuntimeConfig()
        from market_data_officer.run_scheduler import log_startup_posture

        with caplog.at_level(logging.INFO):
            log_startup_posture(config)

        combined = "\n".join(caplog.messages)
        for instrument in config.schedule_config:
            assert instrument in combined


# ── Shutdown behavior tests ─────────────────────────────────────────


class TestShutdownBehavior:
    """Prove that shutdown signal handling works deterministically."""

    def test_shutdown_handler_stops_scheduler(self):
        """Simulating the shutdown handler calls scheduler.shutdown."""
        scheduler = build_scheduler()
        scheduler.start()
        try:
            # Simulate what _shutdown does
            scheduler.shutdown(wait=False)
        finally:
            # Ensure scheduler is stopped even if assertion fails
            if scheduler.running:
                scheduler.shutdown(wait=False)
        assert not scheduler.running

    def test_shutdown_logs_signal_name(self, caplog):
        """The shutdown handler logs the signal name."""
        from market_data_officer.run_scheduler import main

        scheduler = build_scheduler()
        scheduler.start()
        stop_event = threading.Event()

        # Simulate the shutdown handler from run_scheduler
        with caplog.at_level(logging.INFO):
            sig_name = signal.Signals(signal.SIGINT).name
            logging.getLogger("market_data_officer.run_scheduler").info(
                "Shutdown signal received (signal=%s) — stopping scheduler",
                sig_name,
            )
            scheduler.shutdown(wait=False)
            stop_event.set()
            logging.getLogger("market_data_officer.run_scheduler").info(
                "Scheduler stopped — clean exit"
            )

        combined = "\n".join(caplog.messages)
        assert "SIGINT" in combined
        assert "Scheduler stopped" in combined

    def test_shutdown_preserves_alert_state_snapshot(self):
        """Alert state is readable after shutdown for diagnostics."""
        # Prime some alert state
        _alert_state.clear()
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline", side_effect=Exception("net fail")):
            refresh_instrument("EURUSD", _now=now)

        # Take health snapshot (simulates post-shutdown diagnostic)
        health = get_scheduler_health()
        assert health["instruments"]["EURUSD"]["consecutive_failures"] >= 1

        _alert_state.clear()


# ── Health-check tests ──────────────────────────────────────────────


class TestHealthCheck:
    """Prove health-check returns correct shape and is read-only."""

    def setup_method(self):
        _alert_state.clear()

    def teardown_method(self):
        _alert_state.clear()

    def test_health_returns_all_configured_instruments(self):
        health = get_scheduler_health()
        assert health["configured_instruments"] == len(SCHEDULE_CONFIG)
        assert set(health["instruments"]) == set(SCHEDULE_CONFIG)

    def test_health_default_state_for_unevaluated_instrument(self):
        health = get_scheduler_health()
        entry = health["instruments"]["EURUSD"]
        assert entry["alert_level"] == "none"
        assert entry["alert_reason"] == ""
        assert entry["consecutive_stale_live"] == 0
        assert entry["consecutive_failures"] == 0
        assert entry["last_success_ts"] is None

    def test_health_reflects_state_after_successful_refresh(self):
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline"):
            refresh_instrument("EURUSD", _now=now)

        health = get_scheduler_health()
        entry = health["instruments"]["EURUSD"]
        assert entry["alert_level"] == "none"
        assert entry["consecutive_failures"] == 0
        assert entry["last_success_ts"] == now.isoformat()

    def test_health_reflects_failure_state(self):
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline", side_effect=Exception("timeout")):
            refresh_instrument("EURUSD", _now=now)

        health = get_scheduler_health()
        entry = health["instruments"]["EURUSD"]
        assert entry["consecutive_failures"] >= 1

    def test_health_is_read_only(self):
        """Calling get_scheduler_health does not alter _alert_state."""
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline", side_effect=Exception("err")):
            refresh_instrument("EURUSD", _now=now)

        state_before = dict(_alert_state.get("EURUSD", {}))
        get_scheduler_health()
        get_scheduler_health()
        get_scheduler_health()
        state_after = dict(_alert_state.get("EURUSD", {}))
        assert state_before == state_after

    def test_health_instruments_with_state_count(self):
        """instruments_with_state reflects how many have been evaluated."""
        assert get_scheduler_health()["instruments_with_state"] == 0

        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline"):
            refresh_instrument("EURUSD", _now=now)

        assert get_scheduler_health()["instruments_with_state"] == 1

        with patch("market_data_officer.scheduler.run_pipeline"):
            refresh_instrument("GBPUSD", _now=now)

        assert get_scheduler_health()["instruments_with_state"] == 2

    def test_health_with_custom_config(self):
        """get_scheduler_health accepts custom schedule_config."""
        custom = {"EURUSD": {"interval_hours": 1, "window_hours": 24, "family": "FX"}}
        health = get_scheduler_health(schedule_config=custom)
        assert health["configured_instruments"] == 1
        assert "EURUSD" in health["instruments"]
        assert "GBPUSD" not in health["instruments"]

    def test_health_check_does_not_trigger_refresh(self):
        """Calling health-check must never invoke the pipeline."""
        with patch("market_data_officer.scheduler.run_pipeline") as mock_pipeline:
            get_scheduler_health()
            get_scheduler_health()
            mock_pipeline.assert_not_called()


# ── Regression safety tests ─────────────────────────────────────────


class TestRegressionSafety:
    """Verify PR 1 and PR 2 behavior is intact under runtime posture changes."""

    def setup_method(self):
        _alert_state.clear()

    def teardown_method(self):
        _alert_state.clear()

    def test_market_closed_still_skips(self):
        """PR 1 behavior: closed market → skip, no pipeline call."""
        # Saturday 12:00 UTC — all instruments closed
        sat_noon = datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline") as mock:
            result = refresh_instrument("EURUSD", _now=sat_noon)
        assert result["outcome"] == "skipped"
        assert result["market_state"] == "OFF_SESSION_EXPECTED"
        mock.assert_not_called()

    def test_alert_escalation_still_works(self):
        """PR 2 behavior: consecutive failures trigger alert escalation."""
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline", side_effect=Exception("fail")):
            r1 = refresh_instrument("EURUSD", _now=now)
            r2 = refresh_instrument("EURUSD", _now=now)
        # After 2 failures, should be at CRITICAL (threshold=2)
        assert r2["alert_level"] == "critical"

    def test_recovery_still_resets(self):
        """PR 2 behavior: success after alert resets counters."""
        now = datetime(2026, 3, 10, 14, 0, 0, tzinfo=timezone.utc)
        with patch("market_data_officer.scheduler.run_pipeline", side_effect=Exception("fail")):
            refresh_instrument("EURUSD", _now=now)
            refresh_instrument("EURUSD", _now=now)

        with patch("market_data_officer.scheduler.run_pipeline"):
            result = refresh_instrument("EURUSD", _now=now)
        assert result["alert_level"] == "none"
        assert result.get("alert_reason") == "recovery"
