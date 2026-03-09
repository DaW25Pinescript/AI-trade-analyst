"""Scheduled feed refresh — APScheduler integration for all trusted instruments.

Thin scheduling layer over the existing feed pipeline. Each instrument gets its
own job with per-family cadence. Job isolation ensures one failure does not
affect other instruments or crash the scheduler.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from feed.pipeline import run_pipeline
from market_hours import (
    MarketState,
    classify_freshness,
    get_market_state,
    INSTRUMENT_FAMILY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cadence config — config-driven, not hardcoded.
# Change cadence or window by editing this dict. No code changes required.
# ---------------------------------------------------------------------------
SCHEDULE_CONFIG: Dict[str, Dict[str, Any]] = {
    "EURUSD": {"interval_hours": 1, "window_hours": 24, "family": "FX"},
    "GBPUSD": {"interval_hours": 1, "window_hours": 24, "family": "FX"},
    "XAUUSD": {"interval_hours": 4, "window_hours": 48, "family": "Metals"},
    "XAGUSD": {"interval_hours": 4, "window_hours": 48, "family": "Metals"},
    "XPTUSD": {"interval_hours": 4, "window_hours": 48, "family": "Metals"},
}


def refresh_instrument(
    instrument: str,
    config: Optional[Dict[str, Any]] = None,
    *,
    _now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Run the feed pipeline for a single instrument.

    This is the job function called by the scheduler. It wraps the entire
    pipeline call in a try/except to guarantee job isolation — no exception
    propagates out to crash the scheduler or affect other jobs.

    The *_now* parameter exists **only** for deterministic testing — production
    callers must not set it.

    Returns a dict with outcome details for testability.
    """
    cfg = config or SCHEDULE_CONFIG.get(instrument, {})
    window_hours = cfg.get("window_hours", 24)

    now = _now if _now is not None else datetime.now(timezone.utc)
    end_date = now
    start_date = now - timedelta(hours=window_hours)

    # ── Market-hours gate ─────────────────────────────────────────────
    market_state = get_market_state(instrument, now)

    if market_state in (MarketState.CLOSED_EXPECTED,
                        MarketState.OFF_SESSION_EXPECTED):
        logger.info(
            "%s  SKIPPED  market_state=%s  evaluation_ts=%s",
            instrument, market_state.value, now.isoformat(),
        )
        return {
            "instrument": instrument,
            "outcome": "skipped",
            "market_state": market_state.value,
            "evaluation_ts": now.isoformat(),
        }

    # ── Execute pipeline (OPEN or UNKNOWN — conservative) ─────────────
    t0 = time.monotonic()
    try:
        run_pipeline(
            symbol=instrument,
            start_date=start_date,
            end_date=end_date,
        )
        duration = time.monotonic() - t0

        freshness = classify_freshness(
            instrument=instrument,
            last_artifact_ts=now,  # just refreshed successfully
            now=now,
            market_state=market_state,
        )

        logger.info(
            "%s  SUCCESS  duration=%.1fs  market_state=%s"
            "  freshness=%s  reason=%s  evaluation_ts=%s",
            instrument, duration,
            market_state.value,
            freshness.classification.value,
            freshness.reason_code.value,
            now.isoformat(),
        )
        return {
            "instrument": instrument,
            "outcome": "success",
            "duration": round(duration, 1),
            "market_state": market_state.value,
            "freshness": freshness.classification.value,
            "reason_code": freshness.reason_code.value,
            "evaluation_ts": now.isoformat(),
        }
    except Exception as exc:
        duration = time.monotonic() - t0

        freshness = classify_freshness(
            instrument=instrument,
            last_artifact_ts=None,  # conservative: treat as missing
            now=now,
            market_state=market_state,
        )

        logger.error(
            "%s  FAILURE  error=%r  duration=%.1fs  market_state=%s"
            "  freshness=%s  reason=%s  evaluation_ts=%s",
            instrument, str(exc), duration,
            market_state.value,
            freshness.classification.value,
            freshness.reason_code.value,
            now.isoformat(),
        )
        return {
            "instrument": instrument,
            "outcome": "failure",
            "error": str(exc),
            "duration": round(duration, 1),
            "market_state": market_state.value,
            "freshness": freshness.classification.value,
            "reason_code": freshness.reason_code.value,
            "evaluation_ts": now.isoformat(),
        }


def build_scheduler(
    schedule_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> BackgroundScheduler:
    """Create a BackgroundScheduler with one job per instrument.

    Each job uses max_instances=1 to enforce the no-overlap policy —
    if a run is still active when the next trigger fires, the trigger
    is skipped (coalesced).
    """
    cfg = schedule_config or SCHEDULE_CONFIG
    scheduler = BackgroundScheduler(timezone="UTC")

    for instrument, inst_cfg in cfg.items():
        scheduler.add_job(
            refresh_instrument,
            trigger="interval",
            hours=inst_cfg["interval_hours"],
            args=[instrument, inst_cfg],
            id=f"refresh_{instrument}",
            name=f"Refresh {instrument}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60 * 30,  # 30 min grace
        )

    return scheduler
