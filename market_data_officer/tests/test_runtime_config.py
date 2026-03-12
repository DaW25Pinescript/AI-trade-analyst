"""Deterministic tests for runtime_config module.

Tests cover:
- Default config matches hardcoded values in scheduler/market_hours/alert_policy
- Valid config passes validation without error
- Missing/invalid schedule_config entries fail fast
- Instrument not in INSTRUMENT_FAMILY fails fast
- Family not in FAMILY_SESSION_POLICY fails fast
- Bad alert thresholds fail fast
- Threshold ordering (warn < critical) enforced
- load_runtime_config returns a valid default config
- ConfigValidationError message contains all failures
"""

import pytest

from market_data_officer.alert_policy import (
    CRITICAL_FAILURE_THRESHOLD,
    CRITICAL_STALE_LIVE_THRESHOLD,
    WARN_STALE_LIVE_THRESHOLD,
)
from market_data_officer.market_hours import FAMILY_SESSION_POLICY, INSTRUMENT_FAMILY
from market_data_officer.runtime_config import (
    ConfigValidationError,
    RuntimeConfig,
    load_runtime_config,
    validate_runtime_config,
)
from market_data_officer.scheduler import SCHEDULE_CONFIG


# ── Default value alignment tests ───────────────────────────────────


class TestDefaultAlignment:
    """Verify that RuntimeConfig defaults match hardcoded values exactly."""

    def test_schedule_config_matches_scheduler(self):
        config = RuntimeConfig()
        assert config.schedule_config == SCHEDULE_CONFIG

    def test_alert_thresholds_match_alert_policy(self):
        config = RuntimeConfig()
        assert config.warn_stale_live_threshold == WARN_STALE_LIVE_THRESHOLD
        assert config.critical_stale_live_threshold == CRITICAL_STALE_LIVE_THRESHOLD
        assert config.critical_failure_threshold == CRITICAL_FAILURE_THRESHOLD

    def test_all_default_instruments_in_instrument_family(self):
        config = RuntimeConfig()
        for instrument in config.schedule_config:
            assert instrument in INSTRUMENT_FAMILY, (
                f"{instrument} not in INSTRUMENT_FAMILY"
            )

    def test_all_default_families_in_session_policy(self):
        config = RuntimeConfig()
        families = {cfg["family"] for cfg in config.schedule_config.values()}
        for family in families:
            assert family in FAMILY_SESSION_POLICY, (
                f"family '{family}' not in FAMILY_SESSION_POLICY"
            )

    def test_config_is_frozen(self):
        config = RuntimeConfig()
        with pytest.raises(AttributeError):
            config.market_hours_enabled = False  # type: ignore[misc]


# ── Valid config tests ──────────────────────────────────────────────


class TestValidConfig:
    """Verify that valid configurations pass validation."""

    def test_default_config_valid(self):
        config = RuntimeConfig()
        validate_runtime_config(config)  # should not raise

    def test_single_instrument_valid(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 1, "window_hours": 24, "family": "FX"},
            }
        )
        validate_runtime_config(config)  # should not raise

    def test_all_instruments_valid(self):
        config = RuntimeConfig()
        validate_runtime_config(config)  # default has all 5 instruments


# ── Invalid schedule_config tests ───────────────────────────────────


class TestInvalidScheduleConfig:
    """Verify that invalid schedule configs are caught by validation."""

    def test_empty_schedule_config_fails(self):
        config = RuntimeConfig(schedule_config={})
        with pytest.raises(ConfigValidationError, match="schedule_config is empty"):
            validate_runtime_config(config)

    def test_missing_family_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 1, "window_hours": 24},
            }
        )
        with pytest.raises(ConfigValidationError, match="missing or invalid 'family'"):
            validate_runtime_config(config)

    def test_empty_family_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 1, "window_hours": 24, "family": ""},
            }
        )
        with pytest.raises(ConfigValidationError, match="missing or invalid 'family'"):
            validate_runtime_config(config)

    def test_zero_interval_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 0, "window_hours": 24, "family": "FX"},
            }
        )
        with pytest.raises(ConfigValidationError, match="interval_hours must be a positive number"):
            validate_runtime_config(config)

    def test_negative_window_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 1, "window_hours": -1, "family": "FX"},
            }
        )
        with pytest.raises(ConfigValidationError, match="window_hours must be a positive number"):
            validate_runtime_config(config)

    def test_missing_interval_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"window_hours": 24, "family": "FX"},
            }
        )
        with pytest.raises(ConfigValidationError, match="interval_hours must be a positive number"):
            validate_runtime_config(config)

    def test_string_interval_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": "one", "window_hours": 24, "family": "FX"},
            }
        )
        with pytest.raises(ConfigValidationError, match="interval_hours must be a positive number"):
            validate_runtime_config(config)


# ── Cross-reference validation tests ────────────────────────────────


class TestCrossReference:
    """Verify instrument→family and family→session policy cross-checks."""

    def test_unknown_instrument_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "BTCUSD": {"interval_hours": 1, "window_hours": 24, "family": "Crypto"},
            }
        )
        with pytest.raises(ConfigValidationError, match="BTCUSD.*not found in INSTRUMENT_FAMILY"):
            validate_runtime_config(config)

    def test_unknown_family_fails(self):
        config = RuntimeConfig(
            schedule_config={
                "EURUSD": {"interval_hours": 1, "window_hours": 24, "family": "Crypto"},
            }
        )
        with pytest.raises(ConfigValidationError, match="family 'Crypto' has no entry"):
            validate_runtime_config(config)


# ── Alert threshold validation tests ────────────────────────────────


class TestAlertThresholds:
    """Verify alert threshold validation rules."""

    def test_zero_warn_threshold_fails(self):
        config = RuntimeConfig(warn_stale_live_threshold=0)
        with pytest.raises(ConfigValidationError, match="warn_stale_live_threshold must be a positive integer"):
            validate_runtime_config(config)

    def test_negative_critical_stale_fails(self):
        config = RuntimeConfig(critical_stale_live_threshold=-1)
        with pytest.raises(ConfigValidationError, match="critical_stale_live_threshold must be a positive integer"):
            validate_runtime_config(config)

    def test_zero_failure_threshold_fails(self):
        config = RuntimeConfig(critical_failure_threshold=0)
        with pytest.raises(ConfigValidationError, match="critical_failure_threshold must be a positive integer"):
            validate_runtime_config(config)

    def test_warn_equals_critical_fails(self):
        config = RuntimeConfig(
            warn_stale_live_threshold=3,
            critical_stale_live_threshold=3,
        )
        with pytest.raises(ConfigValidationError, match="must be less than"):
            validate_runtime_config(config)

    def test_warn_greater_than_critical_fails(self):
        config = RuntimeConfig(
            warn_stale_live_threshold=5,
            critical_stale_live_threshold=3,
        )
        with pytest.raises(ConfigValidationError, match="must be less than"):
            validate_runtime_config(config)


# ── Multiple errors reported ────────────────────────────────────────


class TestMultipleErrors:
    """Verify that validation reports all errors, not just the first."""

    def test_multiple_errors_all_reported(self):
        config = RuntimeConfig(
            schedule_config={
                "BTCUSD": {"interval_hours": -1, "window_hours": 0, "family": ""},
            },
            warn_stale_live_threshold=0,
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_runtime_config(config)
        msg = str(exc_info.value)
        # Should contain errors for: family, interval, window, instrument, threshold
        assert "missing or invalid 'family'" in msg
        assert "interval_hours must be a positive" in msg
        assert "window_hours must be a positive" in msg
        assert "BTCUSD" in msg
        assert "warn_stale_live_threshold" in msg


# ── load_runtime_config tests ───────────────────────────────────────


class TestLoadRuntimeConfig:
    """Verify the config loader returns a valid default."""

    def test_load_returns_runtime_config(self):
        config = load_runtime_config()
        assert isinstance(config, RuntimeConfig)

    def test_loaded_config_passes_validation(self):
        config = load_runtime_config()
        validate_runtime_config(config)  # should not raise

    def test_loaded_config_has_all_instruments(self):
        config = load_runtime_config()
        assert len(config.schedule_config) == 5

    def test_loaded_config_features_enabled(self):
        config = load_runtime_config()
        assert config.market_hours_enabled is True
        assert config.alert_logging_enabled is True
