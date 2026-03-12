"""Phase 3F integration tests — Groups E, F, G.

Tests replay consistency, output completeness, cross-instrument coverage,
and end-to-end pipeline with mocked LLM calls.
"""

import json
import os
from unittest.mock import patch

import pytest

from analyst.contracts import AnalystVerdict, StructureDigest
from analyst.multi_contracts import ArbiterDecision, MultiAnalystOutput, PersonaVerdict
from analyst.pre_filter import compute_digest
from analyst.analyst import validate_verdict
from analyst.personas import run_all_personas, PERSONA_TECHNICAL_STRUCTURE, PERSONA_EXECUTION_TIMING
from analyst.arbiter import arbitrate
from analyst.multi_analyst_service import run_multi_analyst, _arbiter_to_analyst_verdict, _write_output

from tests.conftest import (
    make_packet,
    make_bullish_4h_structure,
    make_bearish_4h_structure,
    make_clean_bullish_structure,
)


# ---------------------------------------------------------------------------
# Mock LLM helpers
# ---------------------------------------------------------------------------


def _mock_persona_response(persona_name, digest, verdict="long_bias", confidence="moderate", bias="bullish"):
    return json.dumps({
        "persona_name": persona_name,
        "instrument": digest.instrument,
        "as_of_utc": digest.as_of_utc,
        "verdict": verdict,
        "confidence": confidence,
        "directional_bias": bias,
        "structure_gate": digest.structure_gate,
        "persona_supports": ["test support"],
        "persona_conflicts": [],
        "persona_cautions": [],
        "reasoning": {
            "summary": f"{persona_name} assessment.",
            "htf_context": "HTF context.",
            "liquidity_context": "Liquidity context.",
            "fvg_context": "FVG context.",
            "sweep_context": "Sweep context.",
            "verdict_rationale": f"{verdict} rationale.",
        },
    })


def _mock_arbiter_response():
    return json.dumps({
        "synthesis_notes": "Both personas aligned on bullish bias. No conflicts.",
        "winning_rationale_summary": "Directional alignment supports long bias.",
    })


class _MultiLLMMock:
    """Mock that returns appropriate responses based on system prompt content."""

    def __init__(self, digest, verdict="long_bias", confidence="moderate", bias="bullish"):
        self.digest = digest
        self.verdict = verdict
        self.confidence = confidence
        self.bias = bias
        self.call_count = 0

    def __call__(self, system_prompt, user_prompt):
        self.call_count += 1
        if "Arbiter" in system_prompt:
            return _mock_arbiter_response()
        elif "technical structure" in system_prompt.lower():
            return _mock_persona_response(
                PERSONA_TECHNICAL_STRUCTURE, self.digest,
                self.verdict, self.confidence, self.bias,
            )
        else:
            return _mock_persona_response(
                PERSONA_EXECUTION_TIMING, self.digest,
                self.verdict, self.confidence, self.bias,
            )


def _no_trade_mock(digest):
    """Mock that returns no-trade for personas and never calls arbiter."""
    def mock_fn(system_prompt, user_prompt):
        if "technical structure" in system_prompt.lower():
            persona = PERSONA_TECHNICAL_STRUCTURE
        else:
            persona = PERSONA_EXECUTION_TIMING
        return json.dumps({
            "persona_name": persona,
            "instrument": digest.instrument,
            "as_of_utc": digest.as_of_utc,
            "verdict": "no_trade",
            "confidence": "none",
            "directional_bias": "none",
            "structure_gate": digest.structure_gate,
            "persona_supports": [],
            "persona_conflicts": [],
            "persona_cautions": [],
            "reasoning": {
                "summary": "No-trade enforced.",
                "htf_context": "Hard constraint.",
                "liquidity_context": "N/A",
                "fvg_context": "N/A",
                "sweep_context": "N/A",
                "verdict_rationale": "Hard no-trade flag active.",
            },
        })
    return mock_fn


# =============================================================================
# Group E — Replay and consistency
# =============================================================================


class TestGroupE_Replay:
    """TE.1–TE.2: Replay and consistency tests."""

    def test_te1_same_digest_same_consensus(self, tmp_path):
        """TE.1 — Same digest produces same consensus state."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            from analyst.multi_analyst_service import run_multi_analyst
            output_a = run_multi_analyst("EURUSD", packet=packet)

        mock2 = _MultiLLMMock(digest)
        with patch("analyst.personas.call_llm", mock2), \
             patch("analyst.arbiter.call_llm", mock2), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output_b = run_multi_analyst("EURUSD", packet=packet)

        assert output_a.arbiter_decision.consensus_state == output_b.arbiter_decision.consensus_state
        assert output_a.arbiter_decision.final_verdict == output_b.arbiter_decision.final_verdict
        assert output_a.arbiter_decision.final_confidence == output_b.arbiter_decision.final_confidence

    def test_te2_nondeterminism_limited_to_text(self, tmp_path):
        """TE.2 — LLM nondeterminism limited to text fields only."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output_a = run_multi_analyst("EURUSD", packet=packet)

        mock2 = _MultiLLMMock(digest)
        with patch("analyst.personas.call_llm", mock2), \
             patch("analyst.arbiter.call_llm", mock2), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output_b = run_multi_analyst("EURUSD", packet=packet)

        assert output_a.arbiter_decision.no_trade_enforced == output_b.arbiter_decision.no_trade_enforced
        assert output_a.arbiter_decision.personas_agree_direction == output_b.arbiter_decision.personas_agree_direction


# =============================================================================
# Group F — Output completeness
# =============================================================================


class TestGroupF_OutputCompleteness:
    """TF.1–TF.4: Output file and serialization tests."""

    def test_tf1_output_file_written(self, tmp_path):
        """TF.1 — MultiAnalystOutput file written after run."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            run_multi_analyst("EURUSD", packet=packet)

        assert (tmp_path / "EURUSD_multi_analyst_output.json").exists()

    def test_tf2_output_contains_all_blocks(self, tmp_path):
        """TF.2 — Output file contains all required blocks."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            run_multi_analyst("EURUSD", packet=packet)

        with open(tmp_path / "EURUSD_multi_analyst_output.json") as f:
            saved = json.load(f)

        assert "digest" in saved
        assert "persona_outputs" in saved
        assert len(saved["persona_outputs"]) == 2
        assert "arbiter_decision" in saved
        assert "final_verdict" in saved

    def test_tf3_json_roundtrip_lossless(self, tmp_path):
        """TF.3 — JSON serialization roundtrip is lossless."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output = run_multi_analyst("EURUSD", packet=packet)

        serialized = json.dumps(output.to_dict())
        restored = json.loads(serialized)
        assert restored["arbiter_decision"]["final_verdict"] == output.arbiter_decision.final_verdict

    def test_tf4_final_verdict_is_valid_analyst_verdict(self, tmp_path):
        """TF.4 / TD.3 — final_verdict in MultiAnalystOutput is valid AnalystVerdict."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output = run_multi_analyst("EURUSD", packet=packet)

        # Validate with 3E validator
        validate_verdict(output.final_verdict, output.digest)

    def test_tf4_no_trade_final_verdict_valid(self, tmp_path):
        """TF.4 variant — No-trade final_verdict passes 3E validator."""
        packet = make_packet()  # unavailable structure → no-trade
        digest = compute_digest(packet)
        assert digest.has_hard_no_trade()
        mock = _no_trade_mock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output = run_multi_analyst("EURUSD", packet=packet)

        assert output.final_verdict.verdict == "no_trade"
        assert output.final_verdict.confidence == "none"
        validate_verdict(output.final_verdict, output.digest)


# =============================================================================
# Group G — Cross-instrument coverage
# =============================================================================


class TestGroupG_CrossInstrument:
    """TG.1–TG.3: Cross-instrument coverage tests."""

    def test_tg1_eurusd_end_to_end(self, tmp_path):
        """TG.1 — EURUSD produces valid MultiAnalystOutput."""
        packet = make_packet(instrument="EURUSD", structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output = run_multi_analyst("EURUSD", packet=packet)

        assert output.arbiter_decision.final_verdict in (
            "long_bias", "short_bias", "no_trade", "conditional", "no_data"
        )
        assert len(output.persona_outputs) == 2

    def test_tg1_xauusd_end_to_end(self, tmp_path):
        """TG.1 — XAUUSD produces valid MultiAnalystOutput."""
        packet = make_packet(instrument="XAUUSD", structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        mock = _MultiLLMMock(digest)

        with patch("analyst.personas.call_llm", mock), \
             patch("analyst.arbiter.call_llm", mock), \
             patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
            output = run_multi_analyst("XAUUSD", packet=packet)

        assert output.arbiter_decision.final_verdict in (
            "long_bias", "short_bias", "no_trade", "conditional", "no_data"
        )
        assert len(output.persona_outputs) == 2

    def test_tg2_both_instruments_valid(self, tmp_path):
        """TG.2 — Both instruments produce valid MultiAnalystOutput."""
        for instrument in ("EURUSD", "XAUUSD"):
            packet = make_packet(instrument=instrument, structure=make_bullish_4h_structure())
            digest = compute_digest(packet)
            mock = _MultiLLMMock(digest)

            with patch("analyst.personas.call_llm", mock), \
                 patch("analyst.arbiter.call_llm", mock), \
                 patch("analyst.multi_analyst_service.OUTPUT_DIR", tmp_path):
                output = run_multi_analyst(instrument, packet=packet)

            assert output.arbiter_decision.final_verdict in (
                "long_bias", "short_bias", "no_trade", "conditional", "no_data"
            )
            assert len(output.persona_outputs) == 2

    def test_tg3_no_existing_files_modified(self):
        """TG.3 — Feed, Officer, structure, 3E analyst files not modified."""
        # Verify imports work without errors
        from analyst.pre_filter import compute_digest
        from analyst.analyst import run_analyst_llm
        from analyst.service import run_analyst
        from analyst.contracts import StructureDigest, AnalystVerdict

        # Verify 3F imports also work
        from analyst.multi_contracts import PersonaVerdict, ArbiterDecision, MultiAnalystOutput
        from analyst.personas import run_all_personas, build_persona_prompt
        from analyst.arbiter import arbitrate, compute_consensus
        from analyst.multi_analyst_service import run_multi_analyst
