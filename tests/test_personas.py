"""Phase 3F persona tests — Groups A & B.

Tests persona isolation, prompt construction, output schema, and hard constraint enforcement.
All LLM calls are mocked.
"""

import json
from unittest.mock import patch

import pytest

from analyst.contracts import ReasoningBlock, StructureDigest
from analyst.multi_contracts import PersonaVerdict
from analyst.pre_filter import compute_digest
from analyst.personas import (
    PERSONA_EXECUTION_TIMING,
    PERSONA_TECHNICAL_STRUCTURE,
    build_persona_prompt,
    run_all_personas,
    validate_persona_verdict,
)

from tests.conftest import (
    make_packet,
    make_bullish_4h_structure,
    make_clean_bullish_structure,
)


# ---------------------------------------------------------------------------
# Mock LLM responses
# ---------------------------------------------------------------------------


def _make_persona_response(
    persona_name: str,
    digest: StructureDigest,
    verdict: str = "long_bias",
    confidence: str = "moderate",
    directional_bias: str = "bullish",
) -> str:
    """Build a valid persona LLM JSON response."""
    return json.dumps({
        "persona_name": persona_name,
        "instrument": digest.instrument,
        "as_of_utc": digest.as_of_utc,
        "verdict": verdict,
        "confidence": confidence,
        "directional_bias": directional_bias,
        "structure_gate": digest.structure_gate,
        "persona_supports": ["bullish 4h regime"],
        "persona_conflicts": [],
        "persona_cautions": [],
        "reasoning": {
            "summary": f"Persona {persona_name} assessment.",
            "htf_context": "4h regime: bullish.",
            "liquidity_context": "No significant barriers.",
            "fvg_context": "No active FVG.",
            "sweep_context": "No sweeps.",
            "verdict_rationale": f"{verdict} with {confidence} confidence.",
        },
    })


def _make_no_trade_persona_response(persona_name: str, digest: StructureDigest) -> str:
    """Build a valid no-trade persona LLM JSON response."""
    return json.dumps({
        "persona_name": persona_name,
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
            "summary": "No-trade condition enforced.",
            "htf_context": "Hard no-trade flag active.",
            "liquidity_context": "N/A",
            "fvg_context": "N/A",
            "sweep_context": "N/A",
            "verdict_rationale": "Hard constraint prevents any directional bias.",
        },
    })


def _build_mock_llm(digest: StructureDigest, verdict="long_bias", confidence="moderate", directional_bias="bullish"):
    """Build a side_effect function that returns appropriate persona responses."""
    call_count = [0]

    def mock_fn(*args, **kwargs):
        persona = PERSONA_TECHNICAL_STRUCTURE if call_count[0] == 0 else PERSONA_EXECUTION_TIMING
        call_count[0] += 1
        return _make_persona_response(persona, digest, verdict, confidence, directional_bias)

    return mock_fn


def _build_no_trade_mock_llm(digest: StructureDigest):
    """Build a side_effect function that returns no-trade responses."""
    call_count = [0]

    def mock_fn(*args, **kwargs):
        persona = PERSONA_TECHNICAL_STRUCTURE if call_count[0] == 0 else PERSONA_EXECUTION_TIMING
        call_count[0] += 1
        return _make_no_trade_persona_response(persona, digest)

    return mock_fn


# =============================================================================
# Group A — Persona isolation
# =============================================================================


class TestGroupA_PersonaIsolation:
    """TA.1–TA.4: Persona isolation tests."""

    def test_ta1_both_personas_receive_same_digest(self):
        """TA.1 — Both personas receive the same digest object."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.personas.call_llm", side_effect=_build_mock_llm(digest)):
            persona_outputs = run_all_personas(digest)

        assert len(persona_outputs) == 2
        for pv in persona_outputs:
            assert pv.structure_gate == digest.structure_gate
            assert pv.instrument == digest.instrument

    def test_ta2_no_raw_structure_in_prompts(self):
        """TA.2 — Neither persona receives raw structure block."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        prompt_a = build_persona_prompt(PERSONA_TECHNICAL_STRUCTURE, digest)
        prompt_b = build_persona_prompt(PERSONA_EXECUTION_TIMING, digest)

        for prompt in (prompt_a, prompt_b):
            assert "swings" not in prompt["user_content"]
            assert '"events"' not in prompt["user_content"]
            assert '"rows"' not in prompt["user_content"]

    def test_ta3_personas_differ_in_system_prompt_only(self):
        """TA.3 — Persona prompts differ only in system prompt, not data payload."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        prompt_a = build_persona_prompt(PERSONA_TECHNICAL_STRUCTURE, digest)
        prompt_b = build_persona_prompt(PERSONA_EXECUTION_TIMING, digest)

        # Data sections must be identical
        assert prompt_a["user_content"] == prompt_b["user_content"]
        # System prompts must differ
        assert prompt_a["system"] != prompt_b["system"]

    def test_ta4_persona_names_correct(self):
        """TA.4 — Both persona names are correct."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.personas.call_llm", side_effect=_build_mock_llm(digest)):
            persona_outputs = run_all_personas(digest)

        names = [pv.persona_name for pv in persona_outputs]
        assert "technical_structure" in names
        assert "execution_timing" in names


# =============================================================================
# Group B — Persona output schema
# =============================================================================


class TestGroupB_PersonaSchema:
    """TB.1–TB.4: Persona output schema tests."""

    def test_tb1_persona_verdict_schema_valid(self):
        """TB.1 — PersonaVerdict schema valid for both personas."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.personas.call_llm", side_effect=_build_mock_llm(digest)):
            persona_outputs = run_all_personas(digest)

        for pv in persona_outputs:
            assert pv.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
            assert pv.confidence in ("high", "moderate", "low", "none")
            assert pv.directional_bias in ("bullish", "bearish", "neutral", "none")
            assert isinstance(pv.persona_supports, list)
            assert isinstance(pv.persona_conflicts, list)
            assert isinstance(pv.persona_cautions, list)
            assert pv.reasoning is not None

    def test_tb2_structure_gate_echoed(self):
        """TB.2 — structure_gate echoed correctly from digest."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.personas.call_llm", side_effect=_build_mock_llm(digest)):
            persona_outputs = run_all_personas(digest)

        for pv in persona_outputs:
            assert pv.structure_gate == digest.structure_gate

    def test_tb3_malformed_verdict_raises(self):
        """TB.3 — Malformed LLM output raises, not silently accepted."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        bad_verdict = PersonaVerdict(
            persona_name="technical_structure",
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            verdict="STRONG_BUY",
            confidence="moderate",
            directional_bias="bullish",
            structure_gate=digest.structure_gate,
            persona_supports=[],
            persona_conflicts=[],
            persona_cautions=[],
            reasoning=ReasoningBlock(
                summary="", htf_context="", liquidity_context="",
                fvg_context="", sweep_context="", verdict_rationale="",
            ),
        )
        with pytest.raises(ValueError):
            validate_persona_verdict(bad_verdict, digest)

    def test_tb4_hard_no_trade_forces_both_personas(self):
        """TB.4 — Hard no-trade forces both personas to no_trade."""
        # Build a packet with unavailable structure → has_hard_no_trade() == True
        packet = make_packet()  # default: unavailable structure
        digest = compute_digest(packet)
        assert digest.has_hard_no_trade()

        with patch("analyst.personas.call_llm", side_effect=_build_no_trade_mock_llm(digest)):
            persona_outputs = run_all_personas(digest)

        for pv in persona_outputs:
            assert pv.verdict == "no_trade"
            assert pv.confidence == "none"

    def test_tb4_hard_no_trade_validation_catches_override(self):
        """TB.4 variant — Persona overriding hard no-trade raises."""
        packet = make_packet()  # unavailable → no-trade
        digest = compute_digest(packet)
        assert digest.has_hard_no_trade()

        bad_verdict = PersonaVerdict(
            persona_name="technical_structure",
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            verdict="long_bias",
            confidence="high",
            directional_bias="bullish",
            structure_gate=digest.structure_gate,
            persona_supports=[],
            persona_conflicts=[],
            persona_cautions=[],
            reasoning=ReasoningBlock(
                summary="", htf_context="", liquidity_context="",
                fvg_context="", sweep_context="", verdict_rationale="",
            ),
        )
        with pytest.raises(ValueError, match="overrode hard no-trade"):
            validate_persona_verdict(bad_verdict, digest)
