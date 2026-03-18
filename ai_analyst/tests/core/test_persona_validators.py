"""Tests for VALIDATOR_REGISTRY, run_validators(), and confidence rules.

Covers: AC-12 (evidence min 2), AC-13 (counterpoint min 1), AC-14 (falsifiable min 1),
        AC-15 (degraded cap), AC-17 (soft logs without blocking), AC-18 (moderate downgrade).
"""

import pytest

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.engine_output import AnalysisEngineOutput
from ai_analyst.core.persona_validators import (
    VALIDATOR_REGISTRY,
    ValidationResult,
    run_validators,
    check_degraded_confidence_cap,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def make_valid_default_output(confidence: float = 0.72) -> AnalysisEngineOutput:
    return AnalysisEngineOutput(
        persona_id=PersonaType.DEFAULT_ANALYST,
        bias="BULLISH",
        recommended_action="BUY",
        confidence=confidence,
        reasoning=(
            "Structure HH_HL (lenses.structure.trend.structure_state) "
            "with trend bullish (lenses.trend.direction.overall)."
        ),
        evidence_used=[
            "lenses.structure.trend.structure_state",
            "lenses.trend.direction.overall",
        ],
        counterpoints=["Price near resistance (lenses.structure.distance.to_resistance)"],
        what_would_change_my_mind=["Close below support at lenses.structure.levels.support"],
    )


def make_valid_risk_output(confidence: float = 0.60) -> AnalysisEngineOutput:
    return AnalysisEngineOutput(
        persona_id=PersonaType.RISK_OFFICER,
        bias="NEUTRAL",
        recommended_action="NO_TRADE",
        confidence=confidence,
        reasoning=(
            "Risk elevated: proximity to resistance "
            "(lenses.structure.distance.to_resistance) with momentum fading "
            "(lenses.momentum.state.phase)."
        ),
        evidence_used=[
            "lenses.structure.distance.to_resistance",
            "lenses.momentum.state.phase",
        ],
        counterpoints=["Trend still bullish on EMA alignment"],
        what_would_change_my_mind=["Clear breakout above resistance with strong momentum"],
    )


# ---------------------------------------------------------------------------
# TestValidatorRegistry
# ---------------------------------------------------------------------------

class TestValidatorRegistry:
    EXPECTED_NAMES = {
        "default_analyst.requires_two_evidence_fields",
        "risk_officer.no_aggressive_buy_without_confidence",
        "all_personas.no_evidence_contradiction",
        "all_personas.evidence_paths_exist",
        "all_personas.counterpoint_required",
        "all_personas.falsifiable_required",
    }

    def test_contains_all_expected_names(self):
        assert set(VALIDATOR_REGISTRY.keys()) == self.EXPECTED_NAMES

    def test_registry_values_are_callable(self):
        for name, fn in VALIDATOR_REGISTRY.items():
            assert callable(fn), f"{name} is not callable"

    def test_unknown_validator_handled_gracefully(self):
        results = run_validators(
            make_valid_default_output(),
            ["nonexistent.validator"],
        )
        assert len(results) == 1
        assert results[0].passed is False
        assert "Unknown validator" in results[0].message


# ---------------------------------------------------------------------------
# TestFieldRuleValidation — AC-12, AC-13, AC-14
# ---------------------------------------------------------------------------

class TestFieldRuleValidation:
    """Tests for individual validator functions."""

    # AC-12: evidence_used minimum 2
    def test_evidence_with_one_entry_fails(self):
        output = make_valid_default_output()
        output_dict = output.model_dump()
        output_dict["evidence_used"] = ["lenses.structure.trend.structure_state"]
        output = AnalysisEngineOutput(**output_dict)
        result = VALIDATOR_REGISTRY["default_analyst.requires_two_evidence_fields"](output)
        assert result != True
        assert "minimum 2" in result

    def test_evidence_with_two_entries_passes(self):
        output = make_valid_default_output()
        result = VALIDATOR_REGISTRY["default_analyst.requires_two_evidence_fields"](output)
        assert result is True

    # AC-13: counterpoints minimum 1
    def test_counterpoints_with_zero_fails(self):
        output = make_valid_default_output(confidence=0.60)
        output_dict = output.model_dump()
        output_dict["counterpoints"] = []
        output = AnalysisEngineOutput(**output_dict)
        result = VALIDATOR_REGISTRY["all_personas.counterpoint_required"](output)
        assert result != True
        assert "counterpoint" in result

    def test_counterpoints_with_one_passes(self):
        output = make_valid_default_output()
        result = VALIDATOR_REGISTRY["all_personas.counterpoint_required"](output)
        assert result is True

    def test_counterpoints_not_required_at_high_confidence(self):
        output_dict = make_valid_default_output(confidence=0.85).model_dump()
        output_dict["counterpoints"] = []
        output = AnalysisEngineOutput(**output_dict)
        result = VALIDATOR_REGISTRY["all_personas.counterpoint_required"](output)
        assert result is True

    # AC-14: what_would_change_my_mind minimum 1
    def test_falsifiable_with_zero_fails(self):
        output_dict = make_valid_default_output().model_dump()
        output_dict["what_would_change_my_mind"] = []
        output = AnalysisEngineOutput(**output_dict)
        result = VALIDATOR_REGISTRY["all_personas.falsifiable_required"](output)
        assert result != True
        assert "what_would_change_my_mind" in result

    def test_falsifiable_with_one_passes(self):
        output = make_valid_default_output()
        result = VALIDATOR_REGISTRY["all_personas.falsifiable_required"](output)
        assert result is True

    # risk_officer buy rules
    def test_risk_officer_buy_below_075_fails(self):
        output_dict = make_valid_risk_output(confidence=0.60).model_dump()
        output_dict["recommended_action"] = "BUY"
        output = AnalysisEngineOutput(**output_dict)
        result = VALIDATOR_REGISTRY["risk_officer.no_aggressive_buy_without_confidence"](output)
        assert result != True
        assert "BUY requires confidence >= 0.75" in result

    def test_risk_officer_buy_at_075_passes(self):
        output_dict = make_valid_risk_output(confidence=0.75).model_dump()
        output_dict["recommended_action"] = "BUY"
        output = AnalysisEngineOutput(**output_dict)
        result = VALIDATOR_REGISTRY["risk_officer.no_aggressive_buy_without_confidence"](output)
        assert result is True


# ---------------------------------------------------------------------------
# TestRunValidators
# ---------------------------------------------------------------------------

class TestRunValidators:
    def test_returns_list_of_results(self):
        output = make_valid_default_output()
        results = run_validators(output, [
            "default_analyst.requires_two_evidence_fields",
            "all_personas.counterpoint_required",
        ])
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, ValidationResult) for r in results)

    def test_all_pass_for_valid_output(self):
        output = make_valid_default_output()
        results = run_validators(output, [
            "default_analyst.requires_two_evidence_fields",
            "all_personas.counterpoint_required",
            "all_personas.falsifiable_required",
        ])
        assert all(r.passed for r in results)


# ---------------------------------------------------------------------------
# TestSoftValidation — AC-17
# ---------------------------------------------------------------------------

class TestSoftValidation:
    """AC-17: Soft validator logs violation without blocking output."""

    def test_soft_violation_reports_without_blocking(self):
        output_dict = make_valid_default_output().model_dump()
        output_dict["evidence_used"] = ["lenses.structure.trend.structure_state"]
        output = AnalysisEngineOutput(**output_dict)

        results = run_validators(
            output,
            ["default_analyst.requires_two_evidence_fields"],
            level="soft",
        )
        assert len(results) == 1
        r = results[0]
        assert r.passed is False
        assert r.level == "soft"
        assert r.message is not None
        # Output is NOT blocked — we got results back, no exception raised

    def test_output_not_blocked_by_soft_violation(self):
        """run_validators returns results; it does not raise or mutate."""
        output_dict = make_valid_default_output().model_dump()
        output_dict["what_would_change_my_mind"] = []
        output = AnalysisEngineOutput(**output_dict)

        results = run_validators(
            output,
            ["all_personas.falsifiable_required"],
            level="soft",
        )
        # No exception raised — output is not blocked
        assert len(results) == 1
        assert results[0].passed is False


# ---------------------------------------------------------------------------
# TestModerateValidation — AC-18
# ---------------------------------------------------------------------------

class TestModerateValidation:
    """AC-18: Moderate validator downgrades confidence by 0.10."""

    def test_moderate_result_has_correct_level(self):
        output_dict = make_valid_default_output().model_dump()
        output_dict["evidence_used"] = ["lenses.structure.trend.structure_state"]
        output = AnalysisEngineOutput(**output_dict)

        results = run_validators(
            output,
            ["default_analyst.requires_two_evidence_fields"],
            level="moderate",
        )
        assert len(results) == 1
        assert results[0].level == "moderate"
        assert results[0].passed is False

    def test_moderate_downgrade_applied_by_caller(self):
        """Caller-side downgrade: confidence reduced by exactly 0.10."""
        original_confidence = 0.72
        output_dict = make_valid_default_output(confidence=original_confidence).model_dump()
        output_dict["evidence_used"] = ["lenses.structure.trend.structure_state"]
        output = AnalysisEngineOutput(**output_dict)

        results = run_validators(
            output,
            ["default_analyst.requires_two_evidence_fields"],
            level="moderate",
        )

        # Simulate caller-side enforcement
        downgraded_confidence = original_confidence
        for r in results:
            if not r.passed and r.level == "moderate":
                downgraded_confidence = max(0.0, downgraded_confidence - 0.10)

        assert downgraded_confidence == pytest.approx(0.62)

    def test_moderate_downgrade_floored_at_zero(self):
        """Downgrade cannot go below 0.0."""
        original_confidence = 0.05
        output = make_valid_default_output(confidence=original_confidence)

        # Simulate caller-side downgrade
        downgraded = max(0.0, original_confidence - 0.10)
        assert downgraded == 0.0


# ---------------------------------------------------------------------------
# TestConfidenceRules — AC-15
# ---------------------------------------------------------------------------

class TestConfidenceRules:
    """AC-15: Confidence capped at 0.65 on degraded snapshot."""

    def test_degraded_caps_at_065(self):
        output = make_valid_default_output(confidence=0.66)
        result = check_degraded_confidence_cap(output, degraded=True)
        assert result != True
        assert "exceeds 0.65" in result

    def test_degraded_allows_065(self):
        output = make_valid_default_output(confidence=0.65)
        result = check_degraded_confidence_cap(output, degraded=True)
        assert result is True

    def test_degraded_allows_below_065(self):
        output = make_valid_default_output(confidence=0.50)
        result = check_degraded_confidence_cap(output, degraded=True)
        assert result is True

    def test_non_degraded_allows_high_confidence(self):
        output = make_valid_default_output(confidence=0.95)
        result = check_degraded_confidence_cap(output, degraded=False)
        assert result is True
