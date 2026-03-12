"""Runtime configuration and startup validation for the MDO scheduler.

Defines the RuntimeConfig dataclass with defaults that exactly match the
current hardcoded values in scheduler.py, market_hours.py, and alert_policy.py.

This is a validation surface, not a config management system.  No env-var
loading, YAML/TOML parsing, or config file discovery — those are future
concerns.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from market_data_officer.alert_policy import (
    CRITICAL_FAILURE_THRESHOLD,
    CRITICAL_STALE_LIVE_THRESHOLD,
    WARN_STALE_LIVE_THRESHOLD,
)
from market_data_officer.market_hours import FAMILY_SESSION_POLICY, INSTRUMENT_FAMILY


# ---------------------------------------------------------------------------
# Default schedule config — matches scheduler.SCHEDULE_CONFIG exactly
# ---------------------------------------------------------------------------

_DEFAULT_SCHEDULE_CONFIG: Dict[str, Dict[str, Any]] = {
    "EURUSD": {"interval_hours": 1, "window_hours": 24, "family": "FX"},
    "GBPUSD": {"interval_hours": 1, "window_hours": 24, "family": "FX"},
    "XAUUSD": {"interval_hours": 4, "window_hours": 48, "family": "Metals"},
    "XAGUSD": {"interval_hours": 4, "window_hours": 48, "family": "Metals"},
    "XPTUSD": {"interval_hours": 4, "window_hours": 48, "family": "Metals"},
}


# ---------------------------------------------------------------------------
# RuntimeConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuntimeConfig:
    """Validated runtime configuration for the MDO scheduler.

    Defaults match the current hardcoded values across the codebase.  The
    frozen dataclass ensures configuration is immutable once loaded.
    """

    # Schedule config — one entry per instrument
    schedule_config: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: dict(_DEFAULT_SCHEDULE_CONFIG),
    )

    # Artifact output root — matches feed/config.py DATA_ROOT
    artifact_root: Path = Path("market_data")

    # Alert thresholds — match alert_policy.py constants
    warn_stale_live_threshold: int = WARN_STALE_LIVE_THRESHOLD    # 2
    critical_stale_live_threshold: int = CRITICAL_STALE_LIVE_THRESHOLD  # 4
    critical_failure_threshold: int = CRITICAL_FAILURE_THRESHOLD   # 2

    # Feature flags
    market_hours_enabled: bool = True
    alert_logging_enabled: bool = True


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ConfigValidationError(Exception):
    """Raised when runtime configuration fails validation."""


def validate_runtime_config(config: RuntimeConfig) -> None:
    """Validate runtime configuration.  Raises ConfigValidationError on failure.

    Checks:
    1. schedule_config is non-empty
    2. Every instrument has a non-empty family string
    3. Every instrument's interval_hours and window_hours are positive numbers
    4. Every instrument in schedule_config exists in INSTRUMENT_FAMILY
    5. Every family referenced by schedule_config is covered by FAMILY_SESSION_POLICY
    6. Alert thresholds are positive integers
    7. warn < critical for stale-live thresholds
    """
    errors: List[str] = []

    # 1. Non-empty schedule
    if not config.schedule_config:
        errors.append("schedule_config is empty — at least one instrument required")

    for instrument, cfg in config.schedule_config.items():
        # 2. Family present
        family = cfg.get("family")
        if not family or not isinstance(family, str):
            errors.append(
                f"{instrument}: missing or invalid 'family' in schedule_config"
            )

        # 3. Cadence values
        interval = cfg.get("interval_hours")
        if not isinstance(interval, (int, float)) or interval <= 0:
            errors.append(
                f"{instrument}: interval_hours must be a positive number, got {interval!r}"
            )

        window = cfg.get("window_hours")
        if not isinstance(window, (int, float)) or window <= 0:
            errors.append(
                f"{instrument}: window_hours must be a positive number, got {window!r}"
            )

        # 4. Instrument → INSTRUMENT_FAMILY cross-check
        if instrument not in INSTRUMENT_FAMILY:
            errors.append(
                f"{instrument}: not found in INSTRUMENT_FAMILY — "
                f"known instruments: {sorted(INSTRUMENT_FAMILY)}"
            )

        # 5. Family → FAMILY_SESSION_POLICY cross-check
        if family and isinstance(family, str) and family not in FAMILY_SESSION_POLICY:
            errors.append(
                f"{instrument}: family '{family}' has no entry in "
                f"FAMILY_SESSION_POLICY — known families: "
                f"{sorted(FAMILY_SESSION_POLICY)}"
            )

    # 6. Alert thresholds positive
    if not isinstance(config.warn_stale_live_threshold, int) or config.warn_stale_live_threshold <= 0:
        errors.append(
            f"warn_stale_live_threshold must be a positive integer, "
            f"got {config.warn_stale_live_threshold!r}"
        )
    if not isinstance(config.critical_stale_live_threshold, int) or config.critical_stale_live_threshold <= 0:
        errors.append(
            f"critical_stale_live_threshold must be a positive integer, "
            f"got {config.critical_stale_live_threshold!r}"
        )
    if not isinstance(config.critical_failure_threshold, int) or config.critical_failure_threshold <= 0:
        errors.append(
            f"critical_failure_threshold must be a positive integer, "
            f"got {config.critical_failure_threshold!r}"
        )

    # 7. Threshold ordering
    if (isinstance(config.warn_stale_live_threshold, int)
            and isinstance(config.critical_stale_live_threshold, int)
            and config.warn_stale_live_threshold >= config.critical_stale_live_threshold):
        errors.append(
            f"warn_stale_live_threshold ({config.warn_stale_live_threshold}) "
            f"must be less than critical_stale_live_threshold "
            f"({config.critical_stale_live_threshold})"
        )

    if errors:
        msg = "Runtime configuration validation failed:\n  - " + "\n  - ".join(errors)
        raise ConfigValidationError(msg)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_runtime_config() -> RuntimeConfig:
    """Return the default RuntimeConfig.

    Future phases may extend this to read from env vars or config files.
    For now it returns the frozen default that matches current hardcoded values.
    """
    return RuntimeConfig()
