"""
Unit tests for OutcomeTracker (MRO-P3 SQLite implementation).

All tests use a tmp_path-scoped SQLite DB to avoid touching the real DB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from macro_risk_officer.core.models import AssetPressure, MacroContext
from macro_risk_officer.history.tracker import OutcomeTracker


# ── Helpers ────────────────────────────────────────────────────────────────


def _ctx(
    regime: str = "risk_off",
    vol_bias: str = "expanding",
    conflict_score: float = -0.45,
    confidence: float = 0.72,
) -> MacroContext:
    return MacroContext(
        regime=regime,
        vol_bias=vol_bias,
        asset_pressure=AssetPressure(USD=0.6, GOLD=0.4),
        conflict_score=conflict_score,
        confidence=confidence,
        time_horizon_days=45,
        explanation=["Hawkish Fed → risk_off."],
        active_event_ids=["fed-test"],
    )


class _FakeVerdict:
    """Minimal object matching the FinalVerdict duck type."""
    def __init__(self, decision: str = "NO_TRADE", confidence: float = 0.6):
        self.decision = decision
        self.overall_confidence = confidence
        self.analyst_agreement_pct = 67
        self.risk_override_applied = False


# ── Tests ──────────────────────────────────────────────────────────────────


class TestOutcomeTrackerRecord:
    def test_record_without_verdict_succeeds(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(), run_id="run-001", instrument="XAUUSD")
        # Verify row exists
        import sqlite3
        conn = sqlite3.connect(tmp_path / "outcomes.db")
        row = conn.execute("SELECT * FROM runs WHERE run_id = 'run-001'").fetchone()
        conn.close()
        assert row is not None

    def test_record_with_verdict_stores_decision(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        verdict = _FakeVerdict(decision="ENTER_SHORT", confidence=0.72)
        tracker.record(_ctx(), run_id="run-002", instrument="XAUUSD", verdict=verdict)

        import sqlite3
        conn = sqlite3.connect(tmp_path / "outcomes.db")
        row = conn.execute(
            "SELECT decision, overall_confidence FROM runs WHERE run_id = 'run-002'"
        ).fetchone()
        conn.close()
        assert row[0] == "ENTER_SHORT"
        assert abs(row[1] - 0.72) < 1e-6

    def test_record_stores_regime_and_conflict(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(regime="risk_on", conflict_score=0.30), run_id="run-003", instrument="EURUSD")

        import sqlite3
        conn = sqlite3.connect(tmp_path / "outcomes.db")
        row = conn.execute(
            "SELECT regime, conflict_score FROM runs WHERE run_id = 'run-003'"
        ).fetchone()
        conn.close()
        assert row[0] == "risk_on"
        assert abs(row[1] - 0.30) < 1e-6

    def test_duplicate_run_id_is_replaced(self, tmp_path: Path):
        """INSERT OR REPLACE: a second record() with the same run_id overwrites."""
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(regime="neutral"), run_id="run-dup", instrument="XAUUSD")
        tracker.record(_ctx(regime="risk_off"), run_id="run-dup", instrument="XAUUSD")

        import sqlite3
        conn = sqlite3.connect(tmp_path / "outcomes.db")
        rows = conn.execute("SELECT COUNT(*) FROM runs WHERE run_id = 'run-dup'").fetchone()
        regime = conn.execute("SELECT regime FROM runs WHERE run_id = 'run-dup'").fetchone()[0]
        conn.close()
        assert rows[0] == 1
        assert regime == "risk_off"

    def test_instrument_stored_correctly(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(), run_id="run-ins", instrument="NAS100")

        import sqlite3
        conn = sqlite3.connect(tmp_path / "outcomes.db")
        instrument = conn.execute(
            "SELECT instrument FROM runs WHERE run_id = 'run-ins'"
        ).fetchone()[0]
        conn.close()
        assert instrument == "NAS100"

    def test_db_created_if_not_exists(self, tmp_path: Path):
        nested = tmp_path / "nested" / "dir" / "outcomes.db"
        assert not nested.exists()
        tracker = OutcomeTracker(db_path=nested)
        tracker.record(_ctx(), run_id="run-new", instrument="XAUUSD")
        assert nested.exists()


class TestAuditReport:
    def test_empty_db_returns_no_data_message(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        report = tracker.audit_report()
        assert "No runs recorded" in report

    def test_report_contains_regime_distribution(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        for i in range(3):
            tracker.record(_ctx(regime="risk_off"), run_id=f"r{i}", instrument="XAUUSD")
        tracker.record(_ctx(regime="neutral"), run_id="r3", instrument="XAUUSD")

        report = tracker.audit_report()
        assert "REGIME DISTRIBUTION" in report
        assert "risk_off" in report
        assert "neutral" in report

    def test_report_contains_decision_breakdown(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(
            _ctx(), run_id="d1", instrument="XAUUSD",
            verdict=_FakeVerdict(decision="ENTER_LONG"),
        )
        tracker.record(
            _ctx(), run_id="d2", instrument="XAUUSD",
            verdict=_FakeVerdict(decision="NO_TRADE"),
        )
        report = tracker.audit_report()
        assert "DECISION BREAKDOWN" in report
        assert "ENTER_LONG" in report
        assert "NO_TRADE" in report

    def test_report_contains_confidence_section(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(confidence=0.80), run_id="c1", instrument="XAUUSD")
        report = tracker.audit_report()
        assert "CONFIDENCE BY REGIME" in report

    def test_report_contains_recent_runs(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(), run_id="recent-abc-123", instrument="XAUUSD")
        report = tracker.audit_report()
        # run_id is shown truncated to 8 chars followed by ellipsis
        assert "recent-a" in report

    def test_report_total_count_matches(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        for i in range(7):
            tracker.record(_ctx(), run_id=f"count-{i}", instrument="XAUUSD")
        report = tracker.audit_report()
        assert "7 runs" in report

    def test_vol_bias_section_present(self, tmp_path: Path):
        tracker = OutcomeTracker(db_path=tmp_path / "outcomes.db")
        tracker.record(_ctx(vol_bias="expanding"), run_id="v1", instrument="XAUUSD")
        report = tracker.audit_report()
        assert "VOLATILITY BIAS" in report
        assert "expanding" in report
