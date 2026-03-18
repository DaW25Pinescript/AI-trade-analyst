"""Tests for ai_analyst.core.snapshot_builder — Evidence Snapshot Builder.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Sections 4.6, 5, 8.1
Acceptance criteria: AC-5, AC-6, AC-7, AC-8, AC-9
"""

import pytest

from ai_analyst.core.snapshot_builder import SnapshotBuildResult, build_evidence_snapshot
from ai_analyst.lenses.base import LensOutput


# ---------------------------------------------------------------------------
# Frozen test fixtures
# ---------------------------------------------------------------------------

def make_structure_success(direction="bullish", state="HH_HL") -> LensOutput:
    return LensOutput(
        lens_id="structure", version="v1.0", timeframe="1H", status="success", error=None,
        data={
            "timeframe": "1H",
            "levels": {"support": 2000.0, "resistance": 2100.0},
            "distance": {"to_support": 0.8, "to_resistance": 1.5},
            "swings": {"recent_high": 2095.0, "recent_low": 2010.0},
            "trend": {"local_direction": direction, "structure_state": state},
            "breakout": {"status": "holding", "level_broken": "resistance"},
            "rejection": {"at_support": False, "at_resistance": True},
        },
    )


def make_trend_success(overall="bullish") -> LensOutput:
    return LensOutput(
        lens_id="trend", version="v1.0", timeframe="1H", status="success", error=None,
        data={
            "timeframe": "1H",
            "direction": {"ema_alignment": "bullish", "price_vs_ema": "above", "overall": overall},
            "strength": {"slope": "positive", "trend_quality": "strong"},
            "state": {"phase": "continuation", "consistency": "aligned"},
        },
    )


def make_momentum_success(state="bullish") -> LensOutput:
    return LensOutput(
        lens_id="momentum", version="v1.0", timeframe="1H", status="success", error=None,
        data={
            "timeframe": "1H",
            "direction": {"state": state, "roc_sign": "positive"},
            "strength": {"impulse": "strong", "acceleration": "rising"},
            "state": {"phase": "expanding", "trend_alignment": "aligned"},
            "risk": {"exhaustion": False, "chop_warning": False},
        },
    )


def make_failed_output(lens_id="momentum", error="insufficient bars") -> LensOutput:
    return LensOutput(
        lens_id=lens_id, version="v1.0", timeframe="1H",
        status="failed", error=error, data=None,
    )


DEFAULT_KWARGS = {
    "instrument": "XAUUSD",
    "timeframe": "1H",
    "timestamp": "2026-03-18T10:30:00Z",
}


def _build(**overrides):
    """Helper to call build_evidence_snapshot with defaults."""
    kwargs = {**DEFAULT_KWARGS, **overrides}
    return build_evidence_snapshot(**kwargs)


# ---------------------------------------------------------------------------
# TestSnapshotBuilderSchema — AC-5
# ---------------------------------------------------------------------------

class TestSnapshotBuilderSchema:
    """Snapshot shape and content tests."""

    def test_build_returns_result_object(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        assert isinstance(result, SnapshotBuildResult)
        assert result.snapshot is not None
        assert result.run_status == "SUCCESS"

    def test_snapshot_contains_context_lenses_derived_meta(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        snap = result.snapshot
        assert "context" in snap
        assert "lenses" in snap
        assert "derived" in snap
        assert "meta" in snap

    def test_context_preserves_instrument_timeframe_timestamp(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        ctx = result.snapshot["context"]
        assert ctx["instrument"] == "XAUUSD"
        assert ctx["timeframe"] == "1H"
        assert ctx["timestamp"] == "2026-03-18T10:30:00Z"

    def test_successful_lenses_are_namespaced_under_lenses(self):
        """AC-5: Snapshot Builder namespaces lens outputs under lenses.*"""
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        lenses = result.snapshot["lenses"]
        assert "structure" in lenses
        assert "trend" in lenses
        assert "momentum" in lenses

    def test_only_lens_data_stored_not_wrapper(self):
        """Lens data dict stored directly, not LensOutput wrapper."""
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        structure = result.snapshot["lenses"]["structure"]
        # Should be the data dict, not contain status/lens_id wrapper fields
        assert "status" not in structure
        assert "lens_id" not in structure
        assert "error" not in structure
        # Should contain actual data fields
        assert "levels" in structure
        assert "trend" in structure

    def test_coverage_is_null_at_snapshot_time(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        assert result.snapshot["derived"]["coverage"] is None

    def test_persona_agreement_score_is_null_at_snapshot_time(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        assert result.snapshot["derived"]["persona_agreement_score"] is None


# ---------------------------------------------------------------------------
# TestSnapshotBuilderFailureMeta — AC-6, AC-7
# ---------------------------------------------------------------------------

class TestSnapshotBuilderFailureMeta:
    """Failure-aware meta tests."""

    def test_failed_lens_appears_in_meta_failed_lenses(self):
        """AC-6: Failed lens recorded in meta.failed_lenses."""
        result = _build(lens_outputs=[
            make_structure_success(),
            make_trend_success(),
            make_failed_output(lens_id="momentum", error="insufficient bars"),
        ])
        assert "momentum" in result.snapshot["meta"]["failed_lenses"]

    def test_failed_lens_error_stored_in_meta_lens_errors(self):
        """AC-6: Error message in meta.lens_errors."""
        result = _build(lens_outputs=[
            make_structure_success(),
            make_trend_success(),
            make_failed_output(lens_id="momentum", error="insufficient bars"),
        ])
        assert result.snapshot["meta"]["lens_errors"]["momentum"] == "insufficient bars"

    def test_failed_lens_absent_from_lenses(self):
        """AC-6: Failed lens not in lenses.*"""
        result = _build(lens_outputs=[
            make_structure_success(),
            make_trend_success(),
            make_failed_output(lens_id="momentum"),
        ])
        assert "momentum" not in result.snapshot["lenses"]

    def test_inactive_lens_appears_in_meta_inactive_lenses(self):
        """AC-7: Inactive lens recorded in meta.inactive_lenses."""
        registry = [
            {"id": "structure", "version": "v1.0", "enabled": True},
            {"id": "trend", "version": "v1.0", "enabled": True},
            {"id": "momentum", "version": "v1.0", "enabled": False},
        ]
        result = _build(
            lens_outputs=[make_structure_success(), make_trend_success()],
            lens_registry=registry,
        )
        assert "momentum" in result.snapshot["meta"]["inactive_lenses"]

    def test_inactive_lens_absent_from_lenses(self):
        """AC-7: Inactive lens absent from lenses.*"""
        registry = [
            {"id": "structure", "version": "v1.0", "enabled": True},
            {"id": "trend", "version": "v1.0", "enabled": True},
            {"id": "momentum", "version": "v1.0", "enabled": False},
        ]
        result = _build(
            lens_outputs=[make_structure_success(), make_trend_success()],
            lens_registry=registry,
        )
        assert "momentum" not in result.snapshot["lenses"]

    def test_multiple_failed_lenses_all_recorded(self):
        result = _build(lens_outputs=[
            make_structure_success(),
            make_failed_output(lens_id="trend", error="bad data"),
            make_failed_output(lens_id="momentum", error="timeout"),
        ])
        meta = result.snapshot["meta"]
        assert set(meta["failed_lenses"]) == {"trend", "momentum"}
        assert meta["lens_errors"]["trend"] == "bad data"
        assert meta["lens_errors"]["momentum"] == "timeout"


# ---------------------------------------------------------------------------
# TestSnapshotBuilderDerivedSignals — AC-8
# ---------------------------------------------------------------------------

class TestSnapshotBuilderDerivedSignals:
    """Alignment/conflict score tests — 7-scenario table from spec."""

    def test_scenario_1_all_bullish(self):
        """All bullish → alignment=1.0, conflict=0.0, SIGNAL"""
        result = _build(lens_outputs=[
            make_structure_success(direction="bullish"),
            make_trend_success(overall="bullish"),
            make_momentum_success(state="bullish"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(1.0)
        assert d["conflict_score"] == pytest.approx(0.0)
        assert d["signal_state"] == "SIGNAL"

    def test_scenario_2_all_bearish(self):
        """All bearish → alignment=1.0, conflict=0.0, SIGNAL"""
        result = _build(lens_outputs=[
            make_structure_success(direction="bearish"),
            make_trend_success(overall="bearish"),
            make_momentum_success(state="bearish"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(1.0)
        assert d["conflict_score"] == pytest.approx(0.0)
        assert d["signal_state"] == "SIGNAL"

    def test_scenario_3_full_conflict(self):
        """bullish/bearish/neutral → alignment≈0.0, conflict≈1.0, SIGNAL"""
        result = _build(lens_outputs=[
            make_structure_success(direction="bullish"),
            make_trend_success(overall="bearish"),
            make_momentum_success(state="neutral"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(0.0, abs=1e-9)
        assert d["conflict_score"] == pytest.approx(1.0, abs=1e-9)
        assert d["signal_state"] == "SIGNAL"

    def test_scenario_4_two_bull_one_bear(self):
        """2 bull + 1 bear → alignment≈0.333, conflict≈0.667, SIGNAL"""
        result = _build(lens_outputs=[
            make_structure_success(direction="bullish"),
            make_trend_success(overall="bullish"),
            make_momentum_success(state="bearish"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(1 / 3, abs=1e-6)
        assert d["conflict_score"] == pytest.approx(2 / 3, abs=1e-6)
        assert d["signal_state"] == "SIGNAL"

    def test_scenario_5_all_neutral(self):
        """All neutral/ranging → alignment=0.0, conflict=0.0, NO_SIGNAL"""
        result = _build(lens_outputs=[
            make_structure_success(direction="ranging"),
            make_trend_success(overall="ranging"),
            make_momentum_success(state="neutral"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(0.0)
        assert d["conflict_score"] == pytest.approx(0.0)
        assert d["signal_state"] == "NO_SIGNAL"

    def test_scenario_6_two_bull_one_neutral(self):
        """2 bull + 1 neutral → alignment≈0.667, conflict≈0.333, SIGNAL"""
        result = _build(lens_outputs=[
            make_structure_success(direction="bullish"),
            make_trend_success(overall="bullish"),
            make_momentum_success(state="neutral"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(2 / 3, abs=1e-6)
        assert d["conflict_score"] == pytest.approx(1 / 3, abs=1e-6)
        assert d["signal_state"] == "SIGNAL"

    def test_scenario_7_one_lens_only_degraded(self):
        """1 surviving lens (bullish) → alignment=1.0, conflict=0.0, SIGNAL.

        Failed lenses must NOT contribute to derived signal computation.
        """
        result = _build(lens_outputs=[
            make_structure_success(direction="bullish"),
            make_failed_output(lens_id="trend"),
            make_failed_output(lens_id="momentum"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == pytest.approx(1.0)
        assert d["conflict_score"] == pytest.approx(0.0)
        assert d["signal_state"] == "SIGNAL"

    def test_alignment_and_conflict_in_valid_range(self):
        """AC-8: Both scores always in [0.0, 1.0]."""
        test_cases = [
            [make_structure_success("bullish"), make_trend_success("bearish"), make_momentum_success("neutral")],
            [make_structure_success("bullish"), make_trend_success("bullish"), make_momentum_success("bullish")],
            [make_structure_success("ranging"), make_trend_success("ranging"), make_momentum_success("neutral")],
        ]
        for outputs in test_cases:
            result = _build(lens_outputs=outputs)
            d = result.snapshot["derived"]
            assert 0.0 <= d["alignment_score"] <= 1.0
            assert 0.0 <= d["conflict_score"] <= 1.0

    def test_no_successful_lenses_produces_no_signal(self):
        """When all lenses fail, derived signals should be NO_SIGNAL."""
        result = _build(lens_outputs=[
            make_failed_output(lens_id="structure"),
            make_failed_output(lens_id="trend"),
            make_failed_output(lens_id="momentum"),
        ])
        d = result.snapshot["derived"]
        assert d["alignment_score"] == 0.0
        assert d["conflict_score"] == 0.0
        assert d["signal_state"] == "NO_SIGNAL"


# ---------------------------------------------------------------------------
# TestSnapshotBuilderRunStatus
# ---------------------------------------------------------------------------

class TestSnapshotBuilderRunStatus:
    """run_status derivation tests."""

    def test_all_success_returns_success(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        assert result.run_status == "SUCCESS"

    def test_one_failure_returns_degraded(self):
        result = _build(lens_outputs=[
            make_structure_success(),
            make_trend_success(),
            make_failed_output(lens_id="momentum"),
        ])
        assert result.run_status == "DEGRADED"

    def test_two_failures_returns_degraded(self):
        result = _build(lens_outputs=[
            make_structure_success(),
            make_failed_output(lens_id="trend"),
            make_failed_output(lens_id="momentum"),
        ])
        assert result.run_status == "DEGRADED"

    def test_all_failed_returns_failed(self):
        result = _build(lens_outputs=[
            make_failed_output(lens_id="structure"),
            make_failed_output(lens_id="trend"),
            make_failed_output(lens_id="momentum"),
        ])
        assert result.run_status == "FAILED"

    def test_missing_lens_output_treated_as_failed(self):
        """Enabled lens with no output provided → DEGRADED."""
        result = _build(lens_outputs=[
            make_structure_success(),
            make_trend_success(),
            # momentum not provided at all
        ])
        assert result.run_status == "DEGRADED"
        assert "momentum" in result.snapshot["meta"]["failed_lenses"]


# ---------------------------------------------------------------------------
# TestSnapshotId — AC-9
# ---------------------------------------------------------------------------

class TestSnapshotId:
    """snapshot_id determinism and uniqueness tests."""

    def test_snapshot_id_present_in_meta(self):
        result = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        sid = result.snapshot["meta"]["snapshot_id"]
        assert isinstance(sid, str)
        assert len(sid) == 64  # SHA-256 hex

    def test_identical_inputs_produce_identical_snapshot_id(self):
        """AC-9: Deterministic — same inputs → same hash."""
        r1 = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        r2 = _build(lens_outputs=[
            make_structure_success(), make_trend_success(), make_momentum_success(),
        ])
        assert r1.snapshot["meta"]["snapshot_id"] == r2.snapshot["meta"]["snapshot_id"]

    def test_changing_one_field_changes_snapshot_id(self):
        """AC-9: Different content → different hash."""
        r1 = _build(lens_outputs=[
            make_structure_success(direction="bullish"),
            make_trend_success(),
            make_momentum_success(),
        ])
        r2 = _build(lens_outputs=[
            make_structure_success(direction="bearish"),
            make_trend_success(),
            make_momentum_success(),
        ])
        assert r1.snapshot["meta"]["snapshot_id"] != r2.snapshot["meta"]["snapshot_id"]

    def test_snapshot_id_deterministic_across_repeated_runs(self):
        """Hash is stable across multiple invocations."""
        ids = set()
        for _ in range(5):
            result = _build(lens_outputs=[
                make_structure_success(), make_trend_success(), make_momentum_success(),
            ])
            ids.add(result.snapshot["meta"]["snapshot_id"])
        assert len(ids) == 1

    def test_snapshot_id_present_even_on_degraded(self):
        result = _build(lens_outputs=[
            make_structure_success(),
            make_failed_output(lens_id="trend"),
            make_failed_output(lens_id="momentum"),
        ])
        sid = result.snapshot["meta"]["snapshot_id"]
        assert isinstance(sid, str) and len(sid) == 64

    def test_snapshot_id_present_on_failed_run(self):
        result = _build(lens_outputs=[
            make_failed_output(lens_id="structure"),
            make_failed_output(lens_id="trend"),
            make_failed_output(lens_id="momentum"),
        ])
        sid = result.snapshot["meta"]["snapshot_id"]
        assert isinstance(sid, str) and len(sid) == 64
