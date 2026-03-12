"""Scheduled feed refresh — APScheduler integration for all trusted instruments.

Thin scheduling layer over the existing feed pipeline. Each instrument gets its
own job with per-family cadence. Job isolation ensures one failure does not
affect other instruments or crash the scheduler.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MISSED,
)
from apscheduler.schedulers.background import BackgroundScheduler

from feed.pipeline import run_pipeline
from market_hours import (
    FreshnessClassification,
    MarketState,
    classify_freshness,
    get_market_state,
    INSTRUMENT_FAMILY,
)
from alert_policy import (
    AlertDecision,
    AlertLevel,
    RefreshOutcome,
    derive_alert_decision,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-instrument alert state — process-local, resets on scheduler restart.
# Not persisted. Keys are instrument symbols.
# ---------------------------------------------------------------------------
_alert_state: Dict[str, Dict[str, Any]] = {}


def _get_alert_state(instrument: str) -> Dict[str, Any]:
    """Return the mutable alert-state dict for *instrument*, creating if needed."""
    if instrument not in _alert_state:
        _alert_state[instrument] = {
            "consecutive_stale_live": 0,
            "consecutive_failures": 0,
            "last_alert_level": AlertLevel.NONE,
            "last_alert_reason": "",
            "last_success_ts": None,
        }
    return _alert_state[instrument]


def _map_outcome(outcome_str: str) -> RefreshOutcome:
    """Map scheduler outcome string to RefreshOutcome enum."""
    return {
        "success": RefreshOutcome.SUCCESS,
        "skipped": RefreshOutcome.SKIPPED,
        "failure": RefreshOutcome.FAILED,
    }.get(outcome_str, RefreshOutcome.NOT_ATTEMPTED)

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

    After each refresh, alert policy is evaluated and edge-triggered
    structured logs are emitted when warranted.  Alert evaluation failure
    never crashes the scheduler.

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
        _emit_obs_event(
            "mdo.refresh.skipped",
            top_level_category="stale_but_readable",
            event_code="mdo_refresh_market_closed",
            instrument=instrument,
            market_state=market_state.value,
            ts=now.isoformat(),
        )
        result = {
            "instrument": instrument,
            "outcome": "skipped",
            "market_state": market_state.value,
            "evaluation_ts": now.isoformat(),
        }
        _evaluate_alert(instrument, market_state, None, result, now)
        return result

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
        _emit_obs_event(
            "mdo.refresh.complete",
            top_level_category="recovery_after_prior_failure"
            if _get_alert_state(instrument)["consecutive_failures"] > 0
            else "runtime_execution_failure",
            event_code="mdo_refresh_success",
            instrument=instrument,
            outcome="success",
            duration_ms=round(duration * 1000),
            market_state=market_state.value,
            freshness=freshness.classification.value,
            reason_code=freshness.reason_code.value,
            ts=now.isoformat(),
        )
        result = {
            "instrument": instrument,
            "outcome": "success",
            "duration": round(duration, 1),
            "market_state": market_state.value,
            "freshness": freshness.classification.value,
            "reason_code": freshness.reason_code.value,
            "evaluation_ts": now.isoformat(),
        }
        _evaluate_alert(instrument, market_state,
                        freshness.classification, result, now)
        return result
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
        _emit_obs_event(
            "mdo.refresh.failed",
            top_level_category="runtime_execution_failure",
            event_code="mdo_refresh_pipeline_error",
            instrument=instrument,
            outcome="failure",
            error_type=type(exc).__name__,
            error=str(exc)[:500],
            duration_ms=round(duration * 1000),
            market_state=market_state.value,
            freshness=freshness.classification.value,
            reason_code=freshness.reason_code.value,
            ts=now.isoformat(),
        )
        result = {
            "instrument": instrument,
            "outcome": "failure",
            "error": str(exc),
            "duration": round(duration, 1),
            "market_state": market_state.value,
            "freshness": freshness.classification.value,
            "reason_code": freshness.reason_code.value,
            "evaluation_ts": now.isoformat(),
        }
        _evaluate_alert(instrument, market_state,
                        freshness.classification, result, now)
        return result


# ---------------------------------------------------------------------------
# Alert evaluation — called after every refresh_instrument outcome
# ---------------------------------------------------------------------------

def _evaluate_alert(
    instrument: str,
    market_state: MarketState,
    freshness_classification: Optional[FreshnessClassification],
    result: Dict[str, Any],
    now: datetime,
) -> None:
    """Evaluate alert policy and emit edge-triggered structured logs.

    Wrapped in try/except — alert evaluation failure must never crash the
    scheduler or prevent the next refresh cycle (AC-11).
    """
    try:
        state = _get_alert_state(instrument)
        outcome = _map_outcome(result["outcome"])

        # ── Update counters per §6.3 ──────────────────────────────────
        if market_state in (MarketState.CLOSED_EXPECTED,
                            MarketState.OFF_SESSION_EXPECTED):
            # Hold rule: freeze counters during expected closure
            pass
        elif (outcome == RefreshOutcome.SUCCESS
              and freshness_classification == FreshnessClassification.FRESH):
            # Healthy: reset counters
            state["consecutive_stale_live"] = 0
            state["consecutive_failures"] = 0
            state["last_success_ts"] = now
        elif outcome == RefreshOutcome.FAILED:
            # Refresh failure during live/unknown: increment failures only
            state["consecutive_failures"] += 1
        elif freshness_classification in (FreshnessClassification.STALE_BAD,
                                          FreshnessClassification.MISSING_BAD):
            # Stale/missing during live market: increment stale counter only
            state["consecutive_stale_live"] += 1
        elif freshness_classification in (FreshnessClassification.STALE_EXPECTED,
                                          FreshnessClassification.MISSING_EXPECTED):
            # Expected stale/missing: hold (already covered by market_state check above,
            # but explicit for UNKNOWN state edge case)
            pass

        # ── Derive alert decision ─────────────────────────────────────
        # Use FRESH as default freshness for skipped outcomes where
        # freshness_classification is None (closed market skip)
        effective_freshness = (freshness_classification
                               if freshness_classification is not None
                               else FreshnessClassification.FRESH)

        decision = derive_alert_decision(
            instrument=instrument,
            market_state=market_state,
            freshness=effective_freshness,
            refresh_outcome=outcome,
            eval_ts=now,
            last_success_ts=state["last_success_ts"],
            consecutive_stale_live=state["consecutive_stale_live"],
            consecutive_failures=state["consecutive_failures"],
            previous_level=state["last_alert_level"],
            previous_reason_code=state["last_alert_reason"],
        )

        # ── Emit edge-triggered logs ──────────────────────────────────
        if decision.should_emit:
            if decision.level == AlertLevel.NONE:
                # Recovery log
                logger.warning(
                    "%s  ALERT  alert_level=%s  reason_code=%s"
                    "  recovered_from_level=%s  recovered_from_reason=%s"
                    "  market_state=%s  freshness=%s  refresh_outcome=%s"
                    "  consecutive_stale_live=%d  consecutive_failures=%d"
                    "  last_success_ts=%s  eval_ts=%s",
                    instrument,
                    decision.level.value,
                    decision.reason_code,
                    state["last_alert_level"].value,
                    state["last_alert_reason"],
                    market_state.value,
                    effective_freshness.value,
                    outcome.value,
                    state["consecutive_stale_live"],
                    state["consecutive_failures"],
                    state["last_success_ts"].isoformat()
                    if state["last_success_ts"] else "null",
                    now.isoformat(),
                )
            else:
                # Alert log (WARN or CRITICAL)
                logger.warning(
                    "%s  ALERT  alert_level=%s  reason_code=%s"
                    "  market_state=%s  freshness=%s  refresh_outcome=%s"
                    "  consecutive_stale_live=%d  consecutive_failures=%d"
                    "  last_success_ts=%s  eval_ts=%s",
                    instrument,
                    decision.level.value,
                    decision.reason_code,
                    market_state.value,
                    effective_freshness.value,
                    outcome.value,
                    state["consecutive_stale_live"],
                    state["consecutive_failures"],
                    state["last_success_ts"].isoformat()
                    if state["last_success_ts"] else "null",
                    now.isoformat(),
                )

        # ── Update state from decision ────────────────────────────────
        if decision.should_reset:
            state["consecutive_stale_live"] = 0
            state["consecutive_failures"] = 0
            state["last_alert_level"] = AlertLevel.NONE
            state["last_alert_reason"] = ""
        else:
            state["last_alert_level"] = decision.level
            state["last_alert_reason"] = decision.reason_code

        # Attach alert decision to result for testability
        result["alert_level"] = decision.level.value
        result["alert_reason"] = decision.reason_code
        result["alert_emitted"] = decision.should_emit

    except Exception:
        logger.exception(
            "%s  ALERT_EVAL_ERROR  Alert evaluation failed — "
            "scheduler continues normally",
            instrument,
        )


def get_scheduler_health(
    schedule_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return a read-only snapshot of scheduler health.

    This is a pure read — calling it does not trigger a refresh, alter
    alert state, or cause any side effects.  It is designed to be consumed
    by future phases that need an HTTP health endpoint or CLI status command.

    Returns a dict with:
        - ``instruments``: per-instrument status including alert level,
          consecutive counters, and last success timestamp.
        - ``configured_instruments``: number of instruments in schedule config.
        - ``instruments_with_state``: number of instruments that have been
          evaluated at least once (present in ``_alert_state``).
    """
    cfg = schedule_config or SCHEDULE_CONFIG
    instruments: Dict[str, Any] = {}

    for instrument in cfg:
        state = _alert_state.get(instrument)
        if state is not None:
            instruments[instrument] = {
                "alert_level": state["last_alert_level"].value,
                "alert_reason": state["last_alert_reason"],
                "consecutive_stale_live": state["consecutive_stale_live"],
                "consecutive_failures": state["consecutive_failures"],
                "last_success_ts": (
                    state["last_success_ts"].isoformat()
                    if state["last_success_ts"] else None
                ),
            }
        else:
            instruments[instrument] = {
                "alert_level": AlertLevel.NONE.value,
                "alert_reason": "",
                "consecutive_stale_live": 0,
                "consecutive_failures": 0,
                "last_success_ts": None,
            }

    return {
        "configured_instruments": len(cfg),
        "instruments_with_state": sum(
            1 for i in cfg if i in _alert_state
        ),
        "instruments": instruments,
    }


# ---------------------------------------------------------------------------
# Obs P2 — Structured event emitter
# ---------------------------------------------------------------------------

def _emit_obs_event(event: str, **fields: Any) -> None:
    """Emit a structured JSON observability event via the module logger.

    Every event carries ``top_level_category`` and ``event_code`` per the
    Obs P2 taxonomy nesting rule (6 canonical categories → 15 event codes).
    """
    fields["event"] = event
    if "ts" not in fields:
        fields["ts"] = datetime.now(timezone.utc).isoformat()
    try:
        logger.info(json.dumps(fields, default=str))
    except Exception:
        # Observability must never crash the scheduler
        pass


# ---------------------------------------------------------------------------
# Obs P2 — APScheduler lifecycle listeners
# ---------------------------------------------------------------------------

def _on_job_executed(event: Any) -> None:
    """Listener for EVENT_JOB_EXECUTED — job completed without exception."""
    _emit_obs_event(
        "scheduler.job.executed",
        top_level_category="runtime_execution_failure",  # category for lifecycle
        event_code="scheduler_job_executed",
        job_id=event.job_id,
        scheduled_run_time=str(getattr(event, "scheduled_run_time", None)),
    )


def _on_job_error(event: Any) -> None:
    """Listener for EVENT_JOB_ERROR — job raised an exception."""
    _emit_obs_event(
        "scheduler.job.error",
        top_level_category="runtime_execution_failure",
        event_code="scheduler_job_error",
        job_id=event.job_id,
        exception=str(getattr(event, "exception", "")),
        scheduled_run_time=str(getattr(event, "scheduled_run_time", None)),
    )


def _on_job_missed(event: Any) -> None:
    """Listener for EVENT_JOB_MISSED — trigger fired outside misfire_grace_time."""
    _emit_obs_event(
        "scheduler.job.missed",
        top_level_category="dependency_unavailability",
        event_code="scheduler_job_missed",
        job_id=event.job_id,
        scheduled_run_time=str(getattr(event, "scheduled_run_time", None)),
    )


def _on_job_max_instances(event: Any) -> None:
    """Listener for EVENT_JOB_MAX_INSTANCES — overlap skipped (coalesce)."""
    _emit_obs_event(
        "scheduler.job.overlap_skipped",
        top_level_category="stale_but_readable",
        event_code="scheduler_job_overlap_skipped",
        job_id=event.job_id,
        scheduled_run_time=str(getattr(event, "scheduled_run_time", None)),
    )


def build_scheduler(
    schedule_config: Optional[Dict[str, Dict[str, Any]]] = None,
) -> BackgroundScheduler:
    """Create a BackgroundScheduler with one job per instrument.

    Each job uses max_instances=1 to enforce the no-overlap policy —
    if a run is still active when the next trigger fires, the trigger
    is skipped (coalesced).

    Obs P2: APScheduler lifecycle listeners are registered for job executed,
    error, missed, and max-instances (overlap skip) events.
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

    # Obs P2: register APScheduler lifecycle event listeners
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)
    scheduler.add_listener(_on_job_max_instances, EVENT_JOB_MAX_INSTANCES)

    return scheduler
