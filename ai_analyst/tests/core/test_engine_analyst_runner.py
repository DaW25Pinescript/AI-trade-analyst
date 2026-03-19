"""Tests for ai_analyst.core.engine_analyst_runner.

All LLM calls are mocked — no live API calls.
Covers: AC-12, AC-13, AC-14, AC-15, AC-19, AC-20.
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.engine_output import AnalysisEngineOutput
from ai_analyst.models.persona_contract import (
    DEFAULT_ANALYST_CONTRACT,
    RISK_OFFICER_CONTRACT,
)
from ai_analyst.core.engine_analyst_runner import (
    EngineAnalystRunResult,
    run_engine_analyst,
)
from ai_analyst.core.persona_validators import ValidationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_full_snapshot() -> dict:
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
            "evidence_version": "v1.0",
            "snapshot_id": "abc123",
        },
    }


def _make_structure_only_snapshot() -> dict:
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
            "evidence_version": "v1.0",
            "snapshot_id": "def456",
        },
    }


def _valid_output_json(
    persona_id: str = "default_analyst",
    confidence: float = 0.72,
    action: str = "BUY",
    bias: str = "BULLISH",
    evidence: list[str] | None = None,
    counterpoints: list[str] | None = None,
    falsifiable: list[str] | None = None,
) -> str:
    return json.dumps({
        "persona_id": persona_id,
        "bias": bias,
        "recommended_action": action,
        "confidence": confidence,
        "reasoning": "Structure HH_HL (lenses.structure.trend.structure_state) with trend bullish (lenses.trend.direction.overall).",
        "evidence_used": evidence if evidence is not None else [
            "lenses.structure.trend.structure_state",
            "lenses.trend.direction.overall",
        ],
        "counterpoints": counterpoints if counterpoints is not None else ["Price near resistance"],
        "what_would_change_my_mind": falsifiable if falsifiable is not None else ["Close below support"],
    })


def _mock_llm_response(raw_json: str):
    """Create a mock response object matching the acompletion_metered return shape."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw_json))],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )


def _mock_route():
    return SimpleNamespace(
        model="test-model",
        api_base="http://test",
        api_key="test-key",
        provider="test",
        to_call_kwargs=lambda: {},
    )


@pytest.fixture
def mock_deps():
    """Patch LLM call, route resolution, and progress store."""
    with (
        patch("ai_analyst.core.engine_analyst_runner.acompletion_metered", new_callable=AsyncMock) as mock_llm,
        patch("ai_analyst.core.engine_analyst_runner.resolve_profile_route", return_value=_mock_route()) as mock_route,
        patch("ai_analyst.core.engine_analyst_runner.progress_store") as mock_progress,
    ):
        mock_progress.push_event = AsyncMock()
        yield mock_llm, mock_route, mock_progress


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_valid_output_parses_successfully(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json())

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-run-1",
            )
        )
        assert isinstance(result, EngineAnalystRunResult)
        assert isinstance(result.output, AnalysisEngineOutput)
        assert result.output.confidence == 0.72

    def test_missing_required_field_raises(self, mock_deps):
        mock_llm, _, _ = mock_deps
        bad_json = json.dumps({
            "persona_id": "default_analyst",
            "bias": "BULLISH",
            # missing recommended_action, confidence, etc.
        })
        mock_llm.return_value = _mock_llm_response(bad_json)

        with pytest.raises(Exception):
            asyncio.get_event_loop().run_until_complete(
                run_engine_analyst(
                    persona_contract=DEFAULT_ANALYST_CONTRACT,
                    snapshot=_make_full_snapshot(),
                    run_status="SUCCESS",
                    run_id="test-run-2",
                )
            )

    def test_confidence_out_of_range_raises(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(
            _valid_output_json(confidence=1.5)
        )

        with pytest.raises(Exception):
            asyncio.get_event_loop().run_until_complete(
                run_engine_analyst(
                    persona_contract=DEFAULT_ANALYST_CONTRACT,
                    snapshot=_make_full_snapshot(),
                    run_status="SUCCESS",
                    run_id="test-run-3",
                )
            )

    def test_invalid_bias_raises(self, mock_deps):
        mock_llm, _, _ = mock_deps
        bad_json = _valid_output_json(bias="VERY_BULLISH")
        mock_llm.return_value = _mock_llm_response(bad_json)

        with pytest.raises(Exception):
            asyncio.get_event_loop().run_until_complete(
                run_engine_analyst(
                    persona_contract=DEFAULT_ANALYST_CONTRACT,
                    snapshot=_make_full_snapshot(),
                    run_status="SUCCESS",
                    run_id="test-run-4",
                )
            )

    def test_invalid_action_raises(self, mock_deps):
        mock_llm, _, _ = mock_deps
        bad_json = _valid_output_json(action="HOLD")
        mock_llm.return_value = _mock_llm_response(bad_json)

        with pytest.raises(Exception):
            asyncio.get_event_loop().run_until_complete(
                run_engine_analyst(
                    persona_contract=DEFAULT_ANALYST_CONTRACT,
                    snapshot=_make_full_snapshot(),
                    run_status="SUCCESS",
                    run_id="test-run-5",
                )
            )


# ---------------------------------------------------------------------------
# Evidence / counterpoints / falsifiability tests
# ---------------------------------------------------------------------------

class TestEvidenceAndCounterpoints:

    def test_minimum_2_evidence_passes(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            evidence=["lenses.structure.trend.structure_state", "lenses.trend.direction.overall"],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-ev-1",
            )
        )
        evidence_validator = [r for r in result.validator_results
                              if r.validator_name == "default_analyst.requires_two_evidence_fields"]
        assert len(evidence_validator) == 1
        assert evidence_validator[0].passed is True

    def test_1_evidence_yields_validator_failure(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            evidence=["lenses.structure.trend.structure_state"],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-ev-2",
            )
        )
        evidence_validator = [r for r in result.validator_results
                              if r.validator_name == "default_analyst.requires_two_evidence_fields"]
        assert len(evidence_validator) == 1
        assert evidence_validator[0].passed is False

    def test_counterpoints_minimum_passes(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            counterpoints=["Risk near resistance"],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-cp-1",
            )
        )
        cp_validator = [r for r in result.validator_results
                        if r.validator_name == "all_personas.counterpoint_required"]
        assert len(cp_validator) == 1
        assert cp_validator[0].passed is True

    def test_empty_counterpoints_under_080_yields_failure(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            confidence=0.60,
            counterpoints=[],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-cp-2",
            )
        )
        cp_validator = [r for r in result.validator_results
                        if r.validator_name == "all_personas.counterpoint_required"]
        assert len(cp_validator) == 1
        assert cp_validator[0].passed is False

    def test_falsifiability_minimum_passes(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            falsifiable=["Close below support"],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-f-1",
            )
        )
        f_validator = [r for r in result.validator_results
                       if r.validator_name == "all_personas.falsifiable_required"]
        assert len(f_validator) == 1
        assert f_validator[0].passed is True

    def test_empty_falsifiability_yields_failure(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            falsifiable=[],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-f-2",
            )
        )
        f_validator = [r for r in result.validator_results
                       if r.validator_name == "all_personas.falsifiable_required"]
        assert len(f_validator) == 1
        assert f_validator[0].passed is False


# ---------------------------------------------------------------------------
# Confidence rule tests — AC-15
# ---------------------------------------------------------------------------

class TestDegradedConfidence:

    def test_degraded_run_high_confidence_yields_cap_failure(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(confidence=0.80))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="DEGRADED",
                run_id="test-deg-1",
            )
        )
        cap_result = [r for r in result.validator_results
                      if r.validator_name == "engine.degraded_confidence_cap"]
        assert len(cap_result) == 1
        assert cap_result[0].passed is False
        assert "exceeds 0.65" in cap_result[0].message

    def test_healthy_run_allows_high_confidence(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(confidence=0.80))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-deg-2",
            )
        )
        cap_result = [r for r in result.validator_results
                      if r.validator_name == "engine.degraded_confidence_cap"]
        assert len(cap_result) == 1
        assert cap_result[0].passed is True


# ---------------------------------------------------------------------------
# AC-19 — hallucination protection
# ---------------------------------------------------------------------------

class TestHallucinationProtection:

    def test_structure_only_snapshot_momentum_path_fails(self, mock_deps):
        """structure-only active snapshot + momentum evidence path → validator failure."""
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            evidence=[
                "lenses.structure.trend.structure_state",
                "lenses.momentum.direction.state",  # momentum is failed
            ],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_structure_only_snapshot(),
                run_status="DEGRADED",
                run_id="test-h-1",
            )
        )
        path_result = [r for r in result.validator_results
                       if r.validator_name == "all_personas.evidence_paths_exist"]
        assert len(path_result) == 1
        assert path_result[0].passed is False

    def test_nonexistent_structure_path_fails(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            evidence=[
                "lenses.structure.trend.structure_state",
                "lenses.structure.nonexistent.field",
            ],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-h-2",
            )
        )
        path_result = [r for r in result.validator_results
                       if r.validator_name == "all_personas.evidence_paths_exist"]
        assert len(path_result) == 1
        assert path_result[0].passed is False

    def test_all_valid_paths_in_full_snapshot_pass(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            evidence=[
                "lenses.structure.trend.structure_state",
                "lenses.trend.direction.overall",
                "lenses.momentum.direction.state",
            ],
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-h-3",
            )
        )
        path_result = [r for r in result.validator_results
                       if r.validator_name == "all_personas.evidence_paths_exist"]
        assert len(path_result) == 1
        assert path_result[0].passed is True


# ---------------------------------------------------------------------------
# Risk Officer rule
# ---------------------------------------------------------------------------

class TestRiskOfficerRule:

    def test_buy_below_075_yields_failure(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            persona_id="risk_officer",
            action="BUY",
            confidence=0.60,
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=RISK_OFFICER_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-ro-1",
            )
        )
        ro_validator = [r for r in result.validator_results
                        if r.validator_name == "risk_officer.no_aggressive_buy_without_confidence"]
        assert len(ro_validator) == 1
        assert ro_validator[0].passed is False


# ---------------------------------------------------------------------------
# Progress / return contract tests
# ---------------------------------------------------------------------------

class TestReturnContract:

    def test_progress_event_pushed(self, mock_deps):
        mock_llm, _, mock_progress = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json())

        asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-prog-1",
            )
        )
        mock_progress.push_event.assert_called_once()
        call_args = mock_progress.push_event.call_args
        assert call_args[0][0] == "test-prog-1"
        event = call_args[0][1]
        assert event["type"] == "engine_analyst_done"

    def test_returns_engine_analyst_run_result(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json())

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-ret-1",
            )
        )
        assert isinstance(result, EngineAnalystRunResult)
        assert isinstance(result.output, AnalysisEngineOutput)
        assert isinstance(result.validator_results, list)

    def test_validator_results_preserved_on_return(self, mock_deps):
        mock_llm, _, _ = mock_deps
        mock_llm.return_value = _mock_llm_response(_valid_output_json(
            evidence=["lenses.structure.trend.structure_state"],  # only 1 → fails min-2
        ))

        result = asyncio.get_event_loop().run_until_complete(
            run_engine_analyst(
                persona_contract=DEFAULT_ANALYST_CONTRACT,
                snapshot=_make_full_snapshot(),
                run_status="SUCCESS",
                run_id="test-ret-2",
            )
        )
        # Should have multiple validator results including the failure
        assert len(result.validator_results) > 0
        failing = [r for r in result.validator_results if not r.passed]
        assert len(failing) >= 1
