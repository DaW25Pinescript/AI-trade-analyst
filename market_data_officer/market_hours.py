"""Market-hours awareness — session policy and freshness classification.

Pure-function policy layer consumed by the scheduler to distinguish:
- expected market closure  vs  genuine refresh failure
- stale-but-acceptable artifacts  vs  stale-and-bad artifacts

All functions are deterministic: same inputs → same outputs.
No live provider calls, no real clock dependency, no external calendar.

Metals hours: using FX window as starting estimate. Refine if
instrument-specific session data becomes available.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Market state enum
# ---------------------------------------------------------------------------

class MarketState(str, Enum):
    """Current market-hours state for an instrument."""
    OPEN = "OPEN"
    CLOSED_EXPECTED = "CLOSED_EXPECTED"
    OFF_SESSION_EXPECTED = "OFF_SESSION_EXPECTED"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Freshness classification enum
# ---------------------------------------------------------------------------

class FreshnessClassification(str, Enum):
    """Artifact freshness relative to market state and cadence."""
    FRESH = "FRESH"
    STALE_BAD = "STALE_BAD"
    STALE_EXPECTED = "STALE_EXPECTED"
    MISSING_BAD = "MISSING_BAD"
    MISSING_EXPECTED = "MISSING_EXPECTED"


# ---------------------------------------------------------------------------
# Reason codes — stable strings for downstream alerting consumption
# ---------------------------------------------------------------------------

class ReasonCode(str, Enum):
    """Stable reason codes for every classification path."""
    OPEN_AND_FRESH = "open_and_fresh"
    OPEN_AND_OVERDUE = "open_and_overdue"
    OPEN_AND_MISSING = "open_and_missing"
    CLOSED_FRESH = "closed_fresh"
    CLOSED_STALE_EXPECTED = "closed_stale_expected"
    CLOSED_MISSING_EXPECTED = "closed_missing_expected"
    OFF_SESSION_FRESH = "off_session_fresh"
    OFF_SESSION_STALE_EXPECTED = "off_session_stale_expected"
    OFF_SESSION_MISSING_EXPECTED = "off_session_missing_expected"
    UNKNOWN_FRESH = "unknown_fresh"
    UNKNOWN_CONSERVATIVE_STALE = "unknown_conservative_stale"
    UNKNOWN_CONSERVATIVE_MISSING = "unknown_conservative_missing"


# ---------------------------------------------------------------------------
# Freshness result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FreshnessResult:
    """Complete result of a freshness classification evaluation."""
    classification: FreshnessClassification
    reason_code: ReasonCode
    market_state: MarketState
    instrument: str
    age_minutes: Optional[float]
    threshold_minutes: float
    evaluation_ts: datetime


# ---------------------------------------------------------------------------
# Instrument → family mapping (source of truth for scheduling layer)
# ---------------------------------------------------------------------------

INSTRUMENT_FAMILY: Dict[str, str] = {
    "EURUSD": "FX",
    "GBPUSD": "FX",
    "XAUUSD": "Metals",
    "XAGUSD": "Metals",
    "XPTUSD": "Metals",
}


# ---------------------------------------------------------------------------
# Session policy per family
#
# FX market: Sunday 22:00 UTC → Friday 22:00 UTC
# Metals hours: using FX window as starting estimate. Refine if
# instrument-specific session data becomes available.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionPolicy:
    """Weekly session window for an instrument family."""
    week_open_dow: int    # weekday() value: Mon=0 … Sun=6
    week_open_hour: int   # UTC hour when session opens on open day
    week_close_dow: int   # weekday() value for close day
    week_close_hour: int  # UTC hour when session closes on close day


FAMILY_SESSION_POLICY: Dict[str, SessionPolicy] = {
    "FX": SessionPolicy(
        week_open_dow=6,   # Sunday
        week_open_hour=22,
        week_close_dow=4,  # Friday
        week_close_hour=22,
    ),
    # Metals hours: using FX window as starting estimate. Refine if
    # instrument-specific session data becomes available.
    "Metals": SessionPolicy(
        week_open_dow=6,   # Sunday
        week_open_hour=22,
        week_close_dow=4,  # Friday
        week_close_hour=22,
    ),
}

# Default cadence thresholds (minutes) per family — matches SCHEDULE_CONFIG
_DEFAULT_CADENCE: Dict[str, float] = {
    "FX": 60.0,       # 1h interval
    "Metals": 240.0,  # 4h interval
}

# Grace buffer as a multiplier on cadence (e.g. 1.5× means 50% grace)
_GRACE_MULTIPLIER = 1.5


# ---------------------------------------------------------------------------
# Market state evaluation
# ---------------------------------------------------------------------------

def _is_in_session(ts: datetime, policy: SessionPolicy) -> bool:
    """Return True if *ts* falls within the weekly session window.

    Logic mirrors feed/gaps.py:is_fx_trading_hour() but is decoupled
    from the gap-detection module to keep the scheduling layer independent.
    """
    dow = ts.weekday()  # Mon=0 … Sun=6
    hour = ts.hour

    # Saturday: always closed
    if dow == 5:
        return False

    # Session open day (e.g. Sunday): only open from open_hour onwards
    if dow == policy.week_open_dow:
        return hour >= policy.week_open_hour

    # Session close day (e.g. Friday): only open until close_hour
    if dow == policy.week_close_dow:
        return hour < policy.week_close_hour

    # Mon–Thu: fully open
    return True


def get_market_state(instrument: str, timestamp: datetime) -> MarketState:
    """Evaluate the market state for *instrument* at *timestamp*.

    Returns:
        MarketState.OPEN — session window active, refresh expected
        MarketState.CLOSED_EXPECTED — outside weekly session (e.g. weekend)
        MarketState.OFF_SESSION_EXPECTED — known non-trading period
        MarketState.UNKNOWN — instrument not in INSTRUMENT_FAMILY
    """
    family = INSTRUMENT_FAMILY.get(instrument)
    if family is None:
        return MarketState.UNKNOWN

    policy = FAMILY_SESSION_POLICY.get(family)
    if policy is None:
        return MarketState.UNKNOWN

    if _is_in_session(timestamp, policy):
        return MarketState.OPEN

    # Distinguish weekend (Saturday full day, Sunday pre-open, Friday post-close)
    # from potential inter-session gaps. For the current weekly-window model
    # all non-open time is weekend closure.
    dow = timestamp.weekday()
    if dow == 5:
        # Saturday — full weekend day
        return MarketState.OFF_SESSION_EXPECTED

    # Sunday pre-open or Friday post-close
    return MarketState.CLOSED_EXPECTED


# ---------------------------------------------------------------------------
# Freshness classification
# ---------------------------------------------------------------------------

def classify_freshness(
    instrument: str,
    last_artifact_ts: Optional[datetime],
    now: datetime,
    market_state: MarketState,
    cadence_minutes: Optional[float] = None,
    grace_minutes: Optional[float] = None,
) -> FreshnessResult:
    """Classify artifact freshness given market state and cadence.

    Args:
        instrument: Instrument symbol.
        last_artifact_ts: Timestamp of the most recent successful artifact,
            or None if no artifact exists.
        now: Current evaluation timestamp (injected for determinism).
        market_state: Pre-evaluated market state for this instrument.
        cadence_minutes: Expected refresh cadence. Defaults per family.
        grace_minutes: Threshold beyond which an artifact is overdue.
            Defaults to cadence × grace multiplier.

    Returns:
        FreshnessResult with classification, reason code, and context.
    """
    family = INSTRUMENT_FAMILY.get(instrument)
    if cadence_minutes is None:
        cadence_minutes = _DEFAULT_CADENCE.get(family or "", 60.0)
    if grace_minutes is None:
        grace_minutes = cadence_minutes * _GRACE_MULTIPLIER

    # Compute artifact age
    age_minutes: Optional[float] = None
    artifact_present = last_artifact_ts is not None
    overdue = False

    if artifact_present:
        delta = (now - last_artifact_ts).total_seconds() / 60.0
        age_minutes = delta
        overdue = delta > grace_minutes

    # Effective state: UNKNOWN treated as OPEN (conservative)
    effective_open = market_state in (MarketState.OPEN, MarketState.UNKNOWN)
    is_unknown = market_state == MarketState.UNKNOWN

    if artifact_present and not overdue:
        # Fresh in all states
        if is_unknown:
            classification = FreshnessClassification.FRESH
            reason = ReasonCode.UNKNOWN_FRESH
        elif market_state == MarketState.OPEN:
            classification = FreshnessClassification.FRESH
            reason = ReasonCode.OPEN_AND_FRESH
        elif market_state == MarketState.OFF_SESSION_EXPECTED:
            classification = FreshnessClassification.FRESH
            reason = ReasonCode.OFF_SESSION_FRESH
        else:
            classification = FreshnessClassification.FRESH
            reason = ReasonCode.CLOSED_FRESH

    elif artifact_present and overdue:
        # Overdue — classification depends on market state
        if effective_open:
            classification = FreshnessClassification.STALE_BAD
            reason = (ReasonCode.UNKNOWN_CONSERVATIVE_STALE
                      if is_unknown else ReasonCode.OPEN_AND_OVERDUE)
        elif market_state == MarketState.OFF_SESSION_EXPECTED:
            classification = FreshnessClassification.STALE_EXPECTED
            reason = ReasonCode.OFF_SESSION_STALE_EXPECTED
        else:
            classification = FreshnessClassification.STALE_EXPECTED
            reason = ReasonCode.CLOSED_STALE_EXPECTED

    elif not artifact_present:
        # Missing — classification depends on market state
        if effective_open:
            classification = FreshnessClassification.MISSING_BAD
            reason = (ReasonCode.UNKNOWN_CONSERVATIVE_MISSING
                      if is_unknown else ReasonCode.OPEN_AND_MISSING)
        elif market_state == MarketState.OFF_SESSION_EXPECTED:
            classification = FreshnessClassification.MISSING_EXPECTED
            reason = ReasonCode.OFF_SESSION_MISSING_EXPECTED
        else:
            classification = FreshnessClassification.MISSING_EXPECTED
            reason = ReasonCode.CLOSED_MISSING_EXPECTED

    return FreshnessResult(
        classification=classification,
        reason_code=reason,
        market_state=market_state,
        instrument=instrument,
        age_minutes=round(age_minutes, 1) if age_minutes is not None else None,
        threshold_minutes=grace_minutes,
        evaluation_ts=now,
    )
