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

from scheduler import build_scheduler, SCHEDULE_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the scheduler and block until interrupted."""
    logger.info("Starting MDO scheduled feed refresh")
    for instrument, cfg in SCHEDULE_CONFIG.items():
        logger.info(
            "  %s  every %dh  window=%dh  family=%s",
            instrument,
            cfg["interval_hours"],
            cfg["window_hours"],
            cfg["family"],
        )

    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler running — Ctrl-C to stop")

    stop_event = threading.Event()

    def _shutdown(signum: int, frame: object) -> None:
        logger.info("Shutdown signal received — stopping scheduler")
        scheduler.shutdown(wait=False)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    stop_event.wait()
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
