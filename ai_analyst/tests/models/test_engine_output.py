"""Tests for AnalysisEngineOutput schema.

Covers: AC-11 (8 fields), AC-15 (confidence range).
"""

import pytest

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.engine_output import AnalysisEngineOutput


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


class TestOutputHasAll8Fields:
    """AC-11: AnalysisEngineOutput includes all 8 fields."""

    def test_all_8_fields_present(self):
        output = make_valid_default_output()
        expected_fields = {
            "persona_id", "bias", "recommended_action", "confidence",
            "reasoning", "evidence_used", "counterpoints", "what_would_change_my_mind",
        }
        assert set(AnalysisEngineOutput.model_fields.keys()) == expected_fields

    def test_field_values_correct(self):
        output = make_valid_default_output()
        assert output.persona_id == PersonaType.DEFAULT_ANALYST
        assert output.bias == "BULLISH"
        assert output.recommended_action == "BUY"
        assert output.confidence == 0.72
        assert isinstance(output.reasoning, str)
        assert len(output.evidence_used) == 2
        assert len(output.counterpoints) == 1
        assert len(output.what_would_change_my_mind) == 1


class TestConfidenceRange:
    """AC-15: Confidence must be 0.0–1.0."""

    def test_confidence_at_zero(self):
        output = make_valid_default_output(confidence=0.0)
        assert output.confidence == 0.0

    def test_confidence_at_one(self):
        output = make_valid_default_output(confidence=1.0)
        assert output.confidence == 1.0

    def test_confidence_rejects_negative(self):
        with pytest.raises(ValueError, match="confidence must be 0.0"):
            make_valid_default_output(confidence=-0.01)

    def test_confidence_rejects_above_one(self):
        with pytest.raises(ValueError, match="confidence must be 0.0"):
            make_valid_default_output(confidence=1.01)


class TestBiasLiteral:
    def test_valid_bias_values(self):
        for bias in ["BULLISH", "BEARISH", "NEUTRAL"]:
            output = make_valid_default_output()
            output_dict = output.model_dump()
            output_dict["bias"] = bias
            restored = AnalysisEngineOutput(**output_dict)
            assert restored.bias == bias

    def test_invalid_bias_rejected(self):
        with pytest.raises(Exception):
            AnalysisEngineOutput(
                persona_id=PersonaType.DEFAULT_ANALYST,
                bias="bullish",  # lowercase not allowed
                recommended_action="BUY",
                confidence=0.72,
                reasoning="test",
                evidence_used=["a", "b"],
                counterpoints=["c"],
                what_would_change_my_mind=["d"],
            )


class TestRecommendedActionLiteral:
    def test_valid_action_values(self):
        for action in ["BUY", "SELL", "NO_TRADE"]:
            output = make_valid_default_output()
            output_dict = output.model_dump()
            output_dict["recommended_action"] = action
            restored = AnalysisEngineOutput(**output_dict)
            assert restored.recommended_action == action

    def test_invalid_action_rejected(self):
        with pytest.raises(Exception):
            AnalysisEngineOutput(
                persona_id=PersonaType.DEFAULT_ANALYST,
                bias="BULLISH",
                recommended_action="LONG",  # not valid for engine output
                confidence=0.72,
                reasoning="test",
                evidence_used=["a", "b"],
                counterpoints=["c"],
                what_would_change_my_mind=["d"],
            )


class TestListFields:
    def test_evidence_used_accepts_list_of_strings(self):
        output = make_valid_default_output()
        assert all(isinstance(e, str) for e in output.evidence_used)

    def test_counterpoints_accepts_list_of_strings(self):
        output = make_valid_default_output()
        assert all(isinstance(c, str) for c in output.counterpoints)

    def test_what_would_change_my_mind_accepts_list_of_strings(self):
        output = make_valid_default_output()
        assert all(isinstance(w, str) for w in output.what_would_change_my_mind)
