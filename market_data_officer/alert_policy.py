"""Deterministic alerting policy — pure decision logic for scheduler alerts.

Stateless module: every function receives all inputs explicitly and returns
a decision without side effects.  No logging, no I/O, no scheduler mutation.

Consumed by the scheduler to decide whether a refresh outcome warrants an
operator-visible alert or recovery log.
"""

from dataclasses import dataclass
from enum import Enum

from market_hours import (
    FreshnessClassification,
    MarketState,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RefreshOutcome(Enum):
    """Explicit refresh outcome passed by the scheduler."""
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


class AlertLevel(Enum):
    """Operator-visible alert severity."""
    NONE = "none"
    WARN = "warn"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Decision contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AlertDecision:
    """Immutable result of alert policy evaluation."""
    level: AlertLevel
    reason_code: str
    should_emit: bool
    should_reset: bool


# ---------------------------------------------------------------------------
# Threshold constants — deterministic, not config-driven for this PR
# ---------------------------------------------------------------------------

WARN_STALE_LIVE_THRESHOLD = 2
CRITICAL_STALE_LIVE_THRESHOLD = 4
CRITICAL_FAILURE_THRESHOLD = 2


# ---------------------------------------------------------------------------
# Primary entrypoint
# ---------------------------------------------------------------------------

def derive_alert_decision(
    *,
    instrument: str,
    market_state: MarketState,
    freshness: FreshnessClassification,
    refresh_outcome: RefreshOutcome,
    eval_ts,
    last_success_ts,
    consecutive_stale_live: int,
    consecutive_failures: int,
    previous_level: AlertLevel,
    previous_reason_code: str,
) -> AlertDecision:
    """Derive an alert decision from current state.

    Pure function — deterministic, no side effects.

    Args:
        instrument: Instrument symbol (for reason codes).
        market_state: Current market-hours state.
        freshness: Freshness classification from market_hours module.
        refresh_outcome: Explicit outcome of the refresh attempt.
        eval_ts: Evaluation timestamp (for context, not used in logic).
        last_success_ts: Timestamp of last successful refresh (may be None).
        consecutive_stale_live: Current count of consecutive stale-live evals.
        consecutive_failures: Current count of consecutive refresh failures.
        previous_level: Alert level from the previous evaluation cycle.
        previous_reason_code: Reason code from the previous evaluation cycle.

    Returns:
        AlertDecision with level, reason_code, should_emit, and should_reset.
    """
    # ── Closed / off-session: always NONE, no emission ────────────────
    if market_state in (MarketState.CLOSED_EXPECTED,
                        MarketState.OFF_SESSION_EXPECTED):
        return AlertDecision(
            level=AlertLevel.NONE,
            reason_code="closed_no_alert",
            should_emit=False,
            should_reset=False,
        )

    # ── Skipped outcome (market-hours policy skip) ────────────────────
    if refresh_outcome == RefreshOutcome.SKIPPED:
        return AlertDecision(
            level=AlertLevel.NONE,
            reason_code="skipped_no_alert",
            should_emit=False,
            should_reset=False,
        )

    # ── Live market: healthy recovery ─────────────────────────────────
    if (refresh_outcome == RefreshOutcome.SUCCESS
            and freshness == FreshnessClassification.FRESH):
        should_emit = previous_level != AlertLevel.NONE
        return AlertDecision(
            level=AlertLevel.NONE,
            reason_code="recovery" if should_emit else "healthy",
            should_emit=should_emit,
            should_reset=True,
        )

    # ── Live market: determine new alert level ────────────────────────
    level = AlertLevel.NONE
    reason_code = ""

    # Failure escalation (faster than stale-live)
    if refresh_outcome == RefreshOutcome.FAILED:
        if consecutive_failures >= CRITICAL_FAILURE_THRESHOLD:
            level = AlertLevel.CRITICAL
            reason_code = "consecutive_failures_critical"
        elif consecutive_failures >= 1:
            level = AlertLevel.WARN
            reason_code = "refresh_failure"

    # Stale-live escalation
    if freshness in (FreshnessClassification.STALE_BAD,
                     FreshnessClassification.MISSING_BAD):
        stale_level = AlertLevel.NONE
        stale_reason = ""
        if consecutive_stale_live >= CRITICAL_STALE_LIVE_THRESHOLD:
            stale_level = AlertLevel.CRITICAL
            stale_reason = "stale_live_critical"
        elif consecutive_stale_live >= WARN_STALE_LIVE_THRESHOLD:
            stale_level = AlertLevel.WARN
            stale_reason = "stale_live_warn"

        # Failure reason dominates where both apply (§6.5)
        if level == AlertLevel.NONE or (
            stale_level.value > level.value
        ):
            # Only upgrade if stale is more severe
            if stale_level != AlertLevel.NONE:
                if level == AlertLevel.NONE:
                    level = stale_level
                    reason_code = stale_reason
                elif _level_rank(stale_level) > _level_rank(level):
                    level = stale_level
                    reason_code = stale_reason
                # If same rank, failure reason dominates — keep current

    # If no escalation triggered yet, but we have a non-fresh non-failure state
    if level == AlertLevel.NONE and reason_code == "":
        reason_code = "below_threshold"

    # ── Edge-trigger: decide whether to emit ──────────────────────────
    if level == AlertLevel.NONE:
        # No alert — but check if we need recovery emission
        should_emit = previous_level != AlertLevel.NONE
        return AlertDecision(
            level=AlertLevel.NONE,
            reason_code="recovery" if should_emit else reason_code,
            should_emit=should_emit,
            should_reset=should_emit,
        )

    # Level is WARN or CRITICAL — edge-trigger check
    level_changed = level != previous_level
    reason_changed = reason_code != previous_reason_code
    should_emit = level_changed or reason_changed

    return AlertDecision(
        level=level,
        reason_code=reason_code,
        should_emit=should_emit,
        should_reset=False,
    )


def _level_rank(level: AlertLevel) -> int:
    """Return numeric rank for comparison. Higher = more severe."""
    return {AlertLevel.NONE: 0, AlertLevel.WARN: 1, AlertLevel.CRITICAL: 2}[level]
