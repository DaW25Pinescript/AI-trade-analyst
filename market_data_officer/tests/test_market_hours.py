"""Deterministic tests for the market-hours awareness module.

Covers the full test matrix from PR1 task card §9:
- Market state tests (OPEN, CLOSED_EXPECTED, OFF_SESSION_EXPECTED, UNKNOWN)
- Freshness classification tests (FRESH, STALE_BAD, STALE_EXPECTED, MISSING_BAD, MISSING_EXPECTED)
- Reason code correctness
- Conservative UNKNOWN path

All timestamps are injected — no real clock dependency.
No live provider calls.
"""

from datetime import datetime, timedelta, timezone

import pytest

from market_data_officer.market_hours import (
    FAMILY_SESSION_POLICY,
    INSTRUMENT_FAMILY,
    FreshnessClassification,
    FreshnessResult,
    MarketState,
    ReasonCode,
    SessionPolicy,
    classify_freshness,
    get_market_state,
    _is_in_session,
)


# ---------------------------------------------------------------------------
# Fixture timestamps (all UTC-aware, deterministic)
# ---------------------------------------------------------------------------

# Tuesday 14:00 UTC — mid-week, firmly in-session
TUESDAY_14 = datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc)

# Saturday 03:00 UTC — full weekend day, always closed
SATURDAY_03 = datetime(2026, 3, 14, 3, 0, tzinfo=timezone.utc)

# Sunday 20:00 UTC — before session open (22:00), off-session
SUNDAY_20 = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)

# Sunday 23:00 UTC — after session open, should be OPEN
SUNDAY_23 = datetime(2026, 3, 15, 23, 0, tzinfo=timezone.utc)

# Friday 21:59 UTC — just before close, still open
FRIDAY_2159 = datetime(2026, 3, 13, 21, 59, tzinfo=timezone.utc)

# Friday 22:00 UTC — close hour, session closed
FRIDAY_22 = datetime(2026, 3, 13, 22, 0, tzinfo=timezone.utc)

# Friday 23:30 UTC — after close
FRIDAY_2330 = datetime(2026, 3, 13, 23, 30, tzinfo=timezone.utc)

# Monday 10:00 UTC — regular weekday
MONDAY_10 = datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc)

# Wednesday 00:00 UTC — midnight mid-week
WEDNESDAY_00 = datetime(2026, 3, 11, 0, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# Market state tests — §9 first matrix
# ═══════════════════════════════════════════════════════════════════════


class TestGetMarketState:
    """Deterministic market-state evaluation tests."""

    # ── Open market ───────────────────────────────────────────────────

    def test_open_tuesday_eurusd(self):
        """Tuesday 14:00 UTC → OPEN for FX."""
        assert get_market_state("EURUSD", TUESDAY_14) == MarketState.OPEN

    def test_open_tuesday_xauusd(self):
        """Tuesday 14:00 UTC → OPEN for Metals (same FX window estimate)."""
        assert get_market_state("XAUUSD", TUESDAY_14) == MarketState.OPEN

    def test_open_monday(self):
        """Monday 10:00 UTC → OPEN."""
        assert get_market_state("EURUSD", MONDAY_10) == MarketState.OPEN

    def test_open_wednesday_midnight(self):
        """Wednesday 00:00 UTC → OPEN."""
        assert get_market_state("GBPUSD", WEDNESDAY_00) == MarketState.OPEN

    def test_open_sunday_after_open(self):
        """Sunday 23:00 UTC → OPEN (session opens at 22:00)."""
        assert get_market_state("EURUSD", SUNDAY_23) == MarketState.OPEN

    def test_open_friday_before_close(self):
        """Friday 21:59 UTC → OPEN (close is at 22:00)."""
        assert get_market_state("EURUSD", FRIDAY_2159) == MarketState.OPEN

    # ── Closed market ─────────────────────────────────────────────────

    def test_closed_friday_post_close(self):
        """Friday 22:00 UTC → CLOSED_EXPECTED."""
        assert get_market_state("EURUSD", FRIDAY_22) == MarketState.CLOSED_EXPECTED

    def test_closed_friday_late(self):
        """Friday 23:30 UTC → CLOSED_EXPECTED."""
        assert get_market_state("GBPUSD", FRIDAY_2330) == MarketState.CLOSED_EXPECTED

    def test_closed_sunday_pre_open(self):
        """Sunday 20:00 UTC → CLOSED_EXPECTED (before 22:00 open)."""
        assert get_market_state("EURUSD", SUNDAY_20) == MarketState.CLOSED_EXPECTED

    # ── Off-session (Saturday) ────────────────────────────────────────

    def test_off_session_saturday(self):
        """Saturday 03:00 UTC → OFF_SESSION_EXPECTED."""
        assert get_market_state("EURUSD", SATURDAY_03) == MarketState.OFF_SESSION_EXPECTED

    def test_off_session_saturday_metals(self):
        """Saturday 03:00 UTC → OFF_SESSION_EXPECTED for metals too."""
        assert get_market_state("XAUUSD", SATURDAY_03) == MarketState.OFF_SESSION_EXPECTED

    # ── Unknown state ─────────────────────────────────────────────────

    def test_unknown_instrument(self):
        """Unknown instrument → UNKNOWN."""
        assert get_market_state("FAKEINST", TUESDAY_14) == MarketState.UNKNOWN

    def test_unknown_empty_symbol(self):
        """Empty string instrument → UNKNOWN."""
        assert get_market_state("", TUESDAY_14) == MarketState.UNKNOWN

    # ── Instrument-aware: same timestamp, different instruments ───────

    def test_same_timestamp_different_instruments(self):
        """Same timestamp yields same state for FX and Metals (same window
        estimate in PR 1). This test documents the known simplification."""
        state_fx = get_market_state("EURUSD", TUESDAY_14)
        state_metals = get_market_state("XAUUSD", TUESDAY_14)
        # Both use the same session window in PR 1
        assert state_fx == state_metals == MarketState.OPEN

    def test_saturday_all_instruments_off(self):
        """Saturday: all instruments are OFF_SESSION_EXPECTED."""
        for sym in INSTRUMENT_FAMILY:
            assert get_market_state(sym, SATURDAY_03) == MarketState.OFF_SESSION_EXPECTED


class TestIsInSession:
    """Low-level session window tests."""

    FX_POLICY = FAMILY_SESSION_POLICY["FX"]

    def test_saturday_never_in_session(self):
        for hour in (0, 6, 12, 18, 23):
            ts = datetime(2026, 3, 14, hour, 0, tzinfo=timezone.utc)
            assert _is_in_session(ts, self.FX_POLICY) is False

    def test_sunday_boundary(self):
        """Sunday: closed before 22:00, open from 22:00."""
        assert _is_in_session(
            datetime(2026, 3, 15, 21, 59, tzinfo=timezone.utc), self.FX_POLICY
        ) is False
        assert _is_in_session(
            datetime(2026, 3, 15, 22, 0, tzinfo=timezone.utc), self.FX_POLICY
        ) is True

    def test_friday_boundary(self):
        """Friday: open before 22:00, closed from 22:00."""
        assert _is_in_session(
            datetime(2026, 3, 13, 21, 59, tzinfo=timezone.utc), self.FX_POLICY
        ) is True
        assert _is_in_session(
            datetime(2026, 3, 13, 22, 0, tzinfo=timezone.utc), self.FX_POLICY
        ) is False

    def test_midweek_fully_open(self):
        """Mon–Thu all hours are in-session."""
        for dow_offset in range(4):  # Mon=0..Thu=3
            ts = datetime(2026, 3, 9 + dow_offset, 0, 0, tzinfo=timezone.utc)
            assert _is_in_session(ts, self.FX_POLICY) is True
            ts_late = datetime(2026, 3, 9 + dow_offset, 23, 59, tzinfo=timezone.utc)
            assert _is_in_session(ts_late, self.FX_POLICY) is True


# ═══════════════════════════════════════════════════════════════════════
# Freshness classification tests — §9 second matrix
# ═══════════════════════════════════════════════════════════════════════


class TestClassifyFreshness:
    """Deterministic freshness classification tests covering all matrix cells."""

    # Helper: artifact timestamp 30 minutes ago (fresh within 90min grace)
    @staticmethod
    def _fresh_ts(now: datetime) -> datetime:
        return now - timedelta(minutes=30)

    # Helper: artifact timestamp 3 hours ago (overdue for 90min grace)
    @staticmethod
    def _overdue_ts(now: datetime) -> datetime:
        return now - timedelta(hours=3)

    # ── OPEN + fresh artifact → FRESH ─────────────────────────────────

    def test_open_fresh(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=self._fresh_ts(TUESDAY_14),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.classification == FreshnessClassification.FRESH
        assert result.reason_code == ReasonCode.OPEN_AND_FRESH
        assert result.market_state == MarketState.OPEN

    # ── OPEN + overdue artifact → STALE_BAD ───────────────────────────

    def test_open_overdue(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=self._overdue_ts(TUESDAY_14),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.classification == FreshnessClassification.STALE_BAD
        assert result.reason_code == ReasonCode.OPEN_AND_OVERDUE

    # ── OPEN + missing artifact → MISSING_BAD ─────────────────────────

    def test_open_missing(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=None,
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.classification == FreshnessClassification.MISSING_BAD
        assert result.reason_code == ReasonCode.OPEN_AND_MISSING
        assert result.age_minutes is None

    # ── CLOSED_EXPECTED + stale artifact → STALE_EXPECTED ─────────────

    def test_closed_stale(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=self._overdue_ts(FRIDAY_22),
            now=FRIDAY_22,
            market_state=MarketState.CLOSED_EXPECTED,
        )
        assert result.classification == FreshnessClassification.STALE_EXPECTED
        assert result.reason_code == ReasonCode.CLOSED_STALE_EXPECTED

    # ── CLOSED_EXPECTED + missing artifact → MISSING_EXPECTED ─────────

    def test_closed_missing(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=None,
            now=FRIDAY_22,
            market_state=MarketState.CLOSED_EXPECTED,
        )
        assert result.classification == FreshnessClassification.MISSING_EXPECTED
        assert result.reason_code == ReasonCode.CLOSED_MISSING_EXPECTED

    # ── OFF_SESSION_EXPECTED + stale → STALE_EXPECTED ─────────────────

    def test_off_session_stale(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=self._overdue_ts(SATURDAY_03),
            now=SATURDAY_03,
            market_state=MarketState.OFF_SESSION_EXPECTED,
        )
        assert result.classification == FreshnessClassification.STALE_EXPECTED
        assert result.reason_code == ReasonCode.OFF_SESSION_STALE_EXPECTED

    # ── OFF_SESSION_EXPECTED + missing → MISSING_EXPECTED ─────────────

    def test_off_session_missing(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=None,
            now=SATURDAY_03,
            market_state=MarketState.OFF_SESSION_EXPECTED,
        )
        assert result.classification == FreshnessClassification.MISSING_EXPECTED
        assert result.reason_code == ReasonCode.OFF_SESSION_MISSING_EXPECTED

    # ── UNKNOWN + stale artifact → STALE_BAD (conservative) ──────────

    def test_unknown_stale(self):
        result = classify_freshness(
            instrument="FAKEINST",
            last_artifact_ts=self._overdue_ts(TUESDAY_14),
            now=TUESDAY_14,
            market_state=MarketState.UNKNOWN,
        )
        assert result.classification == FreshnessClassification.STALE_BAD
        assert result.reason_code == ReasonCode.UNKNOWN_CONSERVATIVE_STALE

    # ── UNKNOWN + missing artifact → MISSING_BAD (conservative) ───────

    def test_unknown_missing(self):
        result = classify_freshness(
            instrument="FAKEINST",
            last_artifact_ts=None,
            now=TUESDAY_14,
            market_state=MarketState.UNKNOWN,
        )
        assert result.classification == FreshnessClassification.MISSING_BAD
        assert result.reason_code == ReasonCode.UNKNOWN_CONSERVATIVE_MISSING

    # ── UNKNOWN + fresh → FRESH ───────────────────────────────────────

    def test_unknown_fresh(self):
        result = classify_freshness(
            instrument="FAKEINST",
            last_artifact_ts=self._fresh_ts(TUESDAY_14),
            now=TUESDAY_14,
            market_state=MarketState.UNKNOWN,
        )
        assert result.classification == FreshnessClassification.FRESH
        assert result.reason_code == ReasonCode.UNKNOWN_FRESH

    # ── CLOSED + fresh → FRESH (not stale just because closed) ────────

    def test_closed_fresh(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=self._fresh_ts(FRIDAY_22),
            now=FRIDAY_22,
            market_state=MarketState.CLOSED_EXPECTED,
        )
        assert result.classification == FreshnessClassification.FRESH
        assert result.reason_code == ReasonCode.CLOSED_FRESH

    # ── OFF_SESSION + fresh → FRESH ───────────────────────────────────

    def test_off_session_fresh(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=self._fresh_ts(SATURDAY_03),
            now=SATURDAY_03,
            market_state=MarketState.OFF_SESSION_EXPECTED,
        )
        assert result.classification == FreshnessClassification.FRESH
        assert result.reason_code == ReasonCode.OFF_SESSION_FRESH


# ═══════════════════════════════════════════════════════════════════════
# FreshnessResult contract tests
# ═══════════════════════════════════════════════════════════════════════


class TestFreshnessResult:
    """Verify FreshnessResult contract fields."""

    def test_result_fields_present(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=30),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.instrument == "EURUSD"
        assert result.market_state == MarketState.OPEN
        assert result.age_minutes is not None
        assert result.age_minutes == 30.0
        assert result.threshold_minutes > 0
        assert result.evaluation_ts == TUESDAY_14

    def test_missing_artifact_age_is_none(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=None,
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.age_minutes is None

    def test_custom_cadence_and_grace(self):
        """Custom cadence/grace overrides defaults."""
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=20),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
            cadence_minutes=10.0,
            grace_minutes=15.0,
        )
        # 20 minutes > 15 minute grace → STALE_BAD
        assert result.classification == FreshnessClassification.STALE_BAD
        assert result.threshold_minutes == 15.0

    def test_result_is_frozen(self):
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=5),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        with pytest.raises(AttributeError):
            result.classification = FreshnessClassification.STALE_BAD


# ═══════════════════════════════════════════════════════════════════════
# Registry / family mapping tests
# ═══════════════════════════════════════════════════════════════════════


class TestInstrumentFamily:
    """Verify INSTRUMENT_FAMILY covers all registered instruments."""

    def test_all_five_instruments_mapped(self):
        expected = {"EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "XPTUSD"}
        assert set(INSTRUMENT_FAMILY.keys()) == expected

    def test_fx_instruments(self):
        for sym in ("EURUSD", "GBPUSD"):
            assert INSTRUMENT_FAMILY[sym] == "FX"

    def test_metals_instruments(self):
        for sym in ("XAUUSD", "XAGUSD", "XPTUSD"):
            assert INSTRUMENT_FAMILY[sym] == "Metals"

    def test_family_session_policy_covers_all_families(self):
        families = set(INSTRUMENT_FAMILY.values())
        for family in families:
            assert family in FAMILY_SESSION_POLICY, f"No session policy for {family}"


# ═══════════════════════════════════════════════════════════════════════
# Default cadence tests
# ═══════════════════════════════════════════════════════════════════════


class TestDefaultCadence:
    """Verify default cadence per family produces correct thresholds."""

    def test_fx_default_threshold(self):
        """FX cadence=60min, grace=90min (1.5×)."""
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=89),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        # 89 min < 90 min grace → FRESH
        assert result.classification == FreshnessClassification.FRESH
        assert result.threshold_minutes == 90.0

    def test_fx_just_over_threshold(self):
        """FX: 91 min > 90 min grace → STALE_BAD."""
        result = classify_freshness(
            instrument="EURUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=91),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.classification == FreshnessClassification.STALE_BAD

    def test_metals_default_threshold(self):
        """Metals cadence=240min, grace=360min (1.5×)."""
        result = classify_freshness(
            instrument="XAUUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=359),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        # 359 min < 360 min grace → FRESH
        assert result.classification == FreshnessClassification.FRESH
        assert result.threshold_minutes == 360.0

    def test_metals_just_over_threshold(self):
        """Metals: 361 min > 360 min grace → STALE_BAD."""
        result = classify_freshness(
            instrument="XAUUSD",
            last_artifact_ts=TUESDAY_14 - timedelta(minutes=361),
            now=TUESDAY_14,
            market_state=MarketState.OPEN,
        )
        assert result.classification == FreshnessClassification.STALE_BAD
