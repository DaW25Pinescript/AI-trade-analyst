"""Tests for snapshot-aware evidence path validation.

Covers: AC-19 (no inactive/failed lens hallucination).
"""

import pytest

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.engine_output import AnalysisEngineOutput
from ai_analyst.core.persona_validators import (
    make_evidence_paths_validator,
    run_validators_with_snapshot,
    ValidationResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_full_snapshot() -> dict:
    """Full 3-lens snapshot with structure, trend, momentum all active."""
    return {
        "context": {"instrument": "XAUUSD", "timeframe": "1H", "timestamp": "2025-01-15T12:00:00Z"},
        "lenses": {
            "structure": {
                "trend": {"local_direction": "bullish", "structure_state": "HH_HL"},
                "levels": {"support": 2000.0, "resistance": 2100.0},
                "distance": {"to_support": 0.8, "to_resistance": 1.5},
            },
            "trend": {
                "direction": {"overall": "bullish", "ema_alignment": "bullish"},
                "strength": {"slope": "positive"},
            },
            "momentum": {
                "direction": {"state": "bullish", "roc_sign": "positive"},
                "strength": {"impulse": "strong"},
                "risk": {"exhaustion": False},
            },
        },
        "derived": {"alignment_score": 1.0, "conflict_score": 0.0, "signal_state": "SIGNAL"},
        "meta": {
            "active_lenses": ["structure", "trend", "momentum"],
            "inactive_lenses": [],
            "failed_lenses": [],
            "lens_errors": {},
        },
    }


def _make_structure_only_snapshot() -> dict:
    """Snapshot with only structure active; momentum and trend are failed/inactive."""
    return {
        "context": {"instrument": "XAUUSD", "timeframe": "1H", "timestamp": "2025-01-15T12:00:00Z"},
        "lenses": {
            "structure": {
                "trend": {"local_direction": "bearish", "structure_state": "LL_LH"},
                "levels": {"support": 1900.0, "resistance": 2000.0},
            },
        },
        "derived": {"alignment_score": 0.0, "conflict_score": 0.0, "signal_state": "NO_SIGNAL"},
        "meta": {
            "active_lenses": ["structure"],
            "inactive_lenses": ["trend"],
            "failed_lenses": ["momentum"],
            "lens_errors": {"momentum": "insufficient bars"},
        },
    }


def _make_null_leaf_snapshot() -> dict:
    """Snapshot where a valid path leads to a None leaf."""
    return {
        "context": {"instrument": "XAUUSD", "timeframe": "1H", "timestamp": "2025-01-15T12:00:00Z"},
        "lenses": {
            "structure": {
                "trend": {"local_direction": "bullish", "structure_state": None},
            },
        },
        "derived": {},
        "meta": {
            "active_lenses": ["structure"],
            "inactive_lenses": [],
            "failed_lenses": [],
        },
    }


def _make_output(evidence: list[str]) -> AnalysisEngineOutput:
    return AnalysisEngineOutput(
        persona_id=PersonaType.DEFAULT_ANALYST,
        bias="NEUTRAL",
        recommended_action="NO_TRADE",
        confidence=0.50,
        reasoning="Test reasoning citing evidence.",
        evidence_used=evidence,
        counterpoints=["Test counterpoint"],
        what_would_change_my_mind=["Test falsification"],
    )


# ---------------------------------------------------------------------------
# Tests — make_evidence_paths_validator
# ---------------------------------------------------------------------------

class TestEvidencePathValidator:

    def test_valid_path_resolves(self):
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output(["lenses.structure.trend.local_direction"])
        assert validator(output) is True

    def test_non_lenses_path_fails(self):
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output(["derived.alignment_score"])
        result = validator(output)
        assert result is not True
        assert "must start with 'lenses.'" in result

    def test_inactive_lens_path_fails(self):
        validator = make_evidence_paths_validator(_make_structure_only_snapshot())
        output = _make_output(["lenses.trend.direction.overall"])
        result = validator(output)
        assert result is not True
        assert "inactive/failed" in result

    def test_failed_lens_path_fails(self):
        validator = make_evidence_paths_validator(_make_structure_only_snapshot())
        output = _make_output(["lenses.momentum.direction.state"])
        result = validator(output)
        assert result is not True
        assert "inactive/failed" in result

    def test_nonexistent_nested_key_fails(self):
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output(["lenses.structure.nonexistent.field"])
        result = validator(output)
        assert result is not True
        assert "does not resolve" in result

    def test_empty_evidence_list_passes(self):
        """Empty evidence list passes the path validator (min-count is a separate validator)."""
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output([])
        assert validator(output) is True

    def test_null_leaf_value_allowed(self):
        validator = make_evidence_paths_validator(_make_null_leaf_snapshot())
        output = _make_output(["lenses.structure.trend.structure_state"])
        assert validator(output) is True

    def test_multiple_paths_stops_on_first_invalid(self):
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output([
            "lenses.structure.trend.local_direction",
            "lenses.structure.nonexistent.field",
            "lenses.trend.direction.overall",
        ])
        result = validator(output)
        assert result is not True
        assert "nonexistent" in result

    def test_all_three_lens_paths_pass(self):
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output([
            "lenses.structure.trend.local_direction",
            "lenses.trend.direction.overall",
            "lenses.momentum.direction.state",
        ])
        assert validator(output) is True

    def test_deep_nested_path_resolves(self):
        validator = make_evidence_paths_validator(_make_full_snapshot())
        output = _make_output(["lenses.structure.distance.to_support"])
        assert validator(output) is True


# ---------------------------------------------------------------------------
# Tests — run_validators_with_snapshot
# ---------------------------------------------------------------------------

class TestRunValidatorsWithSnapshot:

    def test_snapshot_validator_replaces_placeholder(self):
        """evidence_paths_exist actually validates against the snapshot, not the placeholder."""
        snapshot = _make_structure_only_snapshot()
        output = _make_output(["lenses.momentum.direction.state", "lenses.structure.trend.local_direction"])

        results = run_validators_with_snapshot(
            output=output,
            validator_names=["all_personas.evidence_paths_exist"],
            snapshot=snapshot,
        )
        assert len(results) == 1
        assert results[0].passed is False
        assert "inactive/failed" in results[0].message

    def test_valid_paths_pass_with_snapshot(self):
        snapshot = _make_full_snapshot()
        output = _make_output([
            "lenses.structure.trend.local_direction",
            "lenses.trend.direction.overall",
        ])

        results = run_validators_with_snapshot(
            output=output,
            validator_names=["all_personas.evidence_paths_exist"],
            snapshot=snapshot,
        )
        assert len(results) == 1
        assert results[0].passed is True

    def test_other_validators_still_work(self):
        """Non-evidence validators fall through to global registry."""
        snapshot = _make_full_snapshot()
        output = _make_output([
            "lenses.structure.trend.local_direction",
            "lenses.trend.direction.overall",
        ])

        results = run_validators_with_snapshot(
            output=output,
            validator_names=[
                "all_personas.evidence_paths_exist",
                "default_analyst.requires_two_evidence_fields",
                "all_personas.counterpoint_required",
            ],
            snapshot=snapshot,
        )
        assert len(results) == 3
        assert all(r.passed for r in results)
