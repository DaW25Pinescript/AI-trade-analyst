"""CLI entrypoint — start the scheduled feed refresh for all trusted instruments.

Usage:
    python market_data_officer/run_scheduler.py

Starts a BackgroundScheduler that refreshes each instrument on its configured
cadence. Ctrl-C or SIGTERM for clean shutdown.
"""

import logging
import signal
import sys
import threading

from runtime_config import (
    ConfigValidationError,
    RuntimeConfig,
    load_runtime_config,
    validate_runtime_config,
)
from scheduler import build_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def log_startup_posture(config: RuntimeConfig) -> None:
    """Log a structured startup banner describing the runtime posture."""
    logger.info("=" * 60)
    logger.info("MDO Scheduler — startup posture")
    logger.info("-" * 60)
    logger.info("  market_hours_enabled : %s", config.market_hours_enabled)
    logger.info("  alert_logging_enabled: %s", config.alert_logging_enabled)
    logger.info("  artifact_root        : %s", config.artifact_root)
    logger.info("  instruments          : %d", len(config.schedule_config))
    for instrument, cfg in config.schedule_config.items():
        logger.info(
            "    %s  every %dh  window=%dh  family=%s",
            instrument,
            cfg["interval_hours"],
            cfg["window_hours"],
            cfg["family"],
        )
    logger.info(
        "  alert thresholds     : warn_stale=%d  crit_stale=%d  crit_fail=%d",
        config.warn_stale_live_threshold,
        config.critical_stale_live_threshold,
        config.critical_failure_threshold,
    )
    logger.info("=" * 60)


def main() -> None:
    """Start the scheduler and block until interrupted."""
    # ── Load and validate runtime config ────────────────────────────
    config = load_runtime_config()
    try:
        validate_runtime_config(config)
    except ConfigValidationError as exc:
        logger.error("STARTUP FAILED — config validation error:\n%s", exc)
        sys.exit(1)

    # ── Log startup posture ─────────────────────────────────────────
    log_startup_posture(config)

    # ── Build and start scheduler ───────────────────────────────────
    scheduler = build_scheduler(config.schedule_config)
    scheduler.start()
    logger.info("Scheduler running — Ctrl-C or SIGTERM to stop")

    stop_event = threading.Event()

    def _shutdown(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(
            "Shutdown signal received (signal=%s) — stopping scheduler",
            sig_name,
        )
        scheduler.shutdown(wait=False)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    stop_event.wait()
    logger.info("Scheduler stopped — clean exit")


if __name__ == "__main__":
    main()
