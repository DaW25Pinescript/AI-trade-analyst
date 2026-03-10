"""Deterministic unit tests for the alert_policy module.

All tests are pure — no live provider, no real clock, no scheduler mutation.
Tests exercise:
- Closed/off-session suppression
- Fresh live recovery
- Stale-live escalation through WARN → CRITICAL
- Refresh failure escalation
- Failure reason dominance over stale-live
- Edge-triggered emission (no duplicate spam)
- Reason change at same level → re-emit
- UNKNOWN conservative path
- Counter behavior per §6.3
"""

from datetime import datetime, timezone

import pytest

from alert_policy import (
    AlertDecision,
    AlertLevel,
    CRITICAL_FAILURE_THRESHOLD,
    CRITICAL_STALE_LIVE_THRESHOLD,
    RefreshOutcome,
    WARN_STALE_LIVE_THRESHOLD,
    derive_alert_decision,
)
from market_hours import FreshnessClassification, MarketState


# ── Helpers ────────────────────────────────────────────────────────────

_TS = datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc)


def _decide(**overrides) -> AlertDecision:
    """Call derive_alert_decision with sensible defaults, overridden by kwargs."""
    defaults = dict(
        instrument="EURUSD",
        market_state=MarketState.OPEN,
        freshness=FreshnessClassification.FRESH,
        refresh_outcome=RefreshOutcome.SUCCESS,
        eval_ts=_TS,
        last_success_ts=_TS,
        consecutive_stale_live=0,
        consecutive_failures=0,
        previous_level=AlertLevel.NONE,
        previous_reason_code="",
    )
    defaults.update(overrides)
    return derive_alert_decision(**defaults)


# ── Alert policy unit tests (§10 matrix) ──────────────────────────────


class TestClosedSuppression:
    """Closed/off-session state always returns NONE — no alerts emitted."""

    def test_closed_expected_returns_none(self):
        d = _decide(market_state=MarketState.CLOSED_EXPECTED)
        assert d.level == AlertLevel.NONE
        assert d.should_emit is False

    def test_off_session_returns_none(self):
        d = _decide(market_state=MarketState.OFF_SESSION_EXPECTED)
        assert d.level == AlertLevel.NONE
        assert d.should_emit is False

    def test_closed_with_high_counters_still_none(self):
        """Even with high counters, closed market produces no alert."""
        d = _decide(
            market_state=MarketState.CLOSED_EXPECTED,
            consecutive_stale_live=10,
            consecutive_failures=10,
            previous_level=AlertLevel.CRITICAL,
        )
        assert d.level == AlertLevel.NONE
        assert d.should_emit is False

    def test_off_session_with_failure_outcome_still_none(self):
        """Refresh failure during off-session produces no alert."""
        d = _decide(
            market_state=MarketState.OFF_SESSION_EXPECTED,
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_EXPECTED,
        )
        assert d.level == AlertLevel.NONE
        assert d.should_emit is False


class TestFreshLiveRecovery:
    """Fresh live success returns NONE with should_reset=True."""

    def test_healthy_no_prior_alert(self):
        d = _decide()
        assert d.level == AlertLevel.NONE
        assert d.should_reset is True
        assert d.should_emit is False
        assert d.reason_code == "healthy"

    def test_recovery_from_warn(self):
        d = _decide(previous_level=AlertLevel.WARN, previous_reason_code="stale_live_warn")
        assert d.level == AlertLevel.NONE
        assert d.should_reset is True
        assert d.should_emit is True
        assert d.reason_code == "recovery"

    def test_recovery_from_critical(self):
        d = _decide(
            previous_level=AlertLevel.CRITICAL,
            previous_reason_code="stale_live_critical",
        )
        assert d.level == AlertLevel.NONE
        assert d.should_emit is True
        assert d.should_reset is True
        assert d.reason_code == "recovery"


class TestStaleLiveEscalation:
    """Persistent stale-live conditions escalate through WARN → CRITICAL."""

    def test_below_warn_threshold_no_alert(self):
        d = _decide(
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD - 1,
        )
        assert d.level == AlertLevel.NONE

    def test_at_warn_threshold_emits_warn(self):
        d = _decide(
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
        )
        assert d.level == AlertLevel.WARN
        assert d.should_emit is True
        assert d.reason_code == "stale_live_warn"

    def test_at_critical_threshold_emits_critical(self):
        d = _decide(
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=CRITICAL_STALE_LIVE_THRESHOLD,
        )
        assert d.level == AlertLevel.CRITICAL
        assert d.should_emit is True
        assert d.reason_code == "stale_live_critical"

    def test_missing_bad_also_escalates(self):
        d = _decide(
            freshness=FreshnessClassification.MISSING_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
        )
        assert d.level == AlertLevel.WARN
        assert d.reason_code == "stale_live_warn"


class TestFailureEscalation:
    """Repeated live-market refresh failures escalate faster than stale-live."""

    def test_single_failure_emits_warn(self):
        d = _decide(
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_BAD,
            consecutive_failures=1,
        )
        assert d.level == AlertLevel.WARN
        assert d.reason_code == "refresh_failure"

    def test_failure_at_critical_threshold(self):
        d = _decide(
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_BAD,
            consecutive_failures=CRITICAL_FAILURE_THRESHOLD,
        )
        assert d.level == AlertLevel.CRITICAL
        assert d.reason_code == "consecutive_failures_critical"

    def test_failure_escalates_faster_than_stale(self):
        """Failure reaches CRITICAL at threshold=2, stale needs threshold=4."""
        assert CRITICAL_FAILURE_THRESHOLD < CRITICAL_STALE_LIVE_THRESHOLD

    def test_failure_reason_dominates_stale_reason(self):
        """When both failure and stale apply, failure reason wins."""
        d = _decide(
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_BAD,
            consecutive_failures=1,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
        )
        # Failure reason should dominate
        assert "failure" in d.reason_code


class TestEdgeTriggering:
    """Edge-triggered emission prevents duplicate spam."""

    def test_same_level_same_reason_no_emit(self):
        d = _decide(
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
            previous_level=AlertLevel.WARN,
            previous_reason_code="stale_live_warn",
        )
        assert d.level == AlertLevel.WARN
        assert d.should_emit is False

    def test_same_level_different_reason_emits(self):
        """Reason materially changes at the same level → re-emit."""
        d = _decide(
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_BAD,
            consecutive_failures=1,
            previous_level=AlertLevel.WARN,
            previous_reason_code="stale_live_warn",
        )
        assert d.level == AlertLevel.WARN
        assert d.should_emit is True

    def test_level_increase_emits(self):
        d = _decide(
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=CRITICAL_STALE_LIVE_THRESHOLD,
            previous_level=AlertLevel.WARN,
            previous_reason_code="stale_live_warn",
        )
        assert d.level == AlertLevel.CRITICAL
        assert d.should_emit is True


class TestUnknownConservativePath:
    """UNKNOWN market state treated as live — increments stale counter."""

    def test_unknown_stale_escalates(self):
        d = _decide(
            market_state=MarketState.UNKNOWN,
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
        )
        assert d.level == AlertLevel.WARN

    def test_unknown_missing_escalates(self):
        d = _decide(
            market_state=MarketState.UNKNOWN,
            freshness=FreshnessClassification.MISSING_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=CRITICAL_STALE_LIVE_THRESHOLD,
        )
        assert d.level == AlertLevel.CRITICAL


# ── Counter behavior tests (§10 matrix) ──────────────────────────────
# These tests verify the counter update rules documented in §6.3.
# The policy function itself doesn't update counters (that's the scheduler's
# job), but we test the decision outputs that guide counter updates.


class TestCounterBehaviorDecisions:
    """Verify decisions that guide counter updates match §6.3."""

    def test_fresh_success_resets_both_counters(self):
        """FRESH + success → should_reset=True (scheduler resets both to 0)."""
        d = _decide(
            consecutive_stale_live=3,
            consecutive_failures=2,
        )
        assert d.should_reset is True

    def test_stale_bad_increments_stale_not_failures(self):
        """STALE_BAD with success: stale counter drives level, failures unchanged."""
        d = _decide(
            freshness=FreshnessClassification.STALE_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
            consecutive_failures=0,
        )
        assert d.level == AlertLevel.WARN
        assert d.reason_code == "stale_live_warn"

    def test_missing_bad_increments_stale_not_failures(self):
        """MISSING_BAD: same behavior as STALE_BAD for counter purposes."""
        d = _decide(
            freshness=FreshnessClassification.MISSING_BAD,
            refresh_outcome=RefreshOutcome.SUCCESS,
            consecutive_stale_live=WARN_STALE_LIVE_THRESHOLD,
            consecutive_failures=0,
        )
        assert d.level == AlertLevel.WARN

    def test_failure_during_live_increments_failures_not_stale(self):
        """Refresh failure during live: failure counter drives, stale unchanged."""
        d = _decide(
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_BAD,
            consecutive_failures=CRITICAL_FAILURE_THRESHOLD,
            consecutive_stale_live=0,
        )
        assert d.level == AlertLevel.CRITICAL
        assert "failure" in d.reason_code

    def test_failure_during_closed_holds_counters(self):
        """Refresh failure during closed: NONE, no counter change."""
        d = _decide(
            market_state=MarketState.CLOSED_EXPECTED,
            refresh_outcome=RefreshOutcome.FAILED,
            freshness=FreshnessClassification.MISSING_EXPECTED,
        )
        assert d.level == AlertLevel.NONE
        assert d.should_reset is False

    def test_stale_expected_holds_counters(self):
        """STALE_EXPECTED: NONE, no counter change."""
        d = _decide(
            market_state=MarketState.CLOSED_EXPECTED,
            freshness=FreshnessClassification.STALE_EXPECTED,
        )
        assert d.level == AlertLevel.NONE
        assert d.should_reset is False

    def test_missing_expected_holds_counters(self):
        """MISSING_EXPECTED: NONE, no counter change."""
        d = _decide(
            market_state=MarketState.OFF_SESSION_EXPECTED,
            freshness=FreshnessClassification.MISSING_EXPECTED,
        )
        assert d.level == AlertLevel.NONE
        assert d.should_reset is False

    def test_skipped_outcome_holds_counters(self):
        """SKIPPED outcome: NONE, no reset."""
        d = _decide(
            refresh_outcome=RefreshOutcome.SKIPPED,
            market_state=MarketState.CLOSED_EXPECTED,
        )
        assert d.level == AlertLevel.NONE
        assert d.should_reset is False


class TestThresholdConstants:
    """Verify threshold constants are sensible."""

    def test_warn_below_critical_stale(self):
        assert WARN_STALE_LIVE_THRESHOLD < CRITICAL_STALE_LIVE_THRESHOLD

    def test_failure_escalates_faster(self):
        assert CRITICAL_FAILURE_THRESHOLD < CRITICAL_STALE_LIVE_THRESHOLD

    def test_warn_stale_threshold_value(self):
        assert WARN_STALE_LIVE_THRESHOLD == 2

    def test_critical_stale_threshold_value(self):
        assert CRITICAL_STALE_LIVE_THRESHOLD == 4

    def test_critical_failure_threshold_value(self):
        assert CRITICAL_FAILURE_THRESHOLD == 2


class TestAlertDecisionFrozen:
    """AlertDecision is immutable."""

    def test_frozen(self):
        d = _decide()
        with pytest.raises(AttributeError):
            d.level = AlertLevel.WARN


class TestNotAttemptedOutcome:
    """NOT_ATTEMPTED outcome is handled gracefully."""

    def test_not_attempted_no_crash(self):
        d = _decide(refresh_outcome=RefreshOutcome.NOT_ATTEMPTED)
        assert d.level == AlertLevel.NONE
