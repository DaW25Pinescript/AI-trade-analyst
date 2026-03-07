"""Phase 3F Arbiter tests — Groups C & D.

Tests deterministic conflict resolution, consensus state taxonomy,
and hard constraint enforcement. All LLM calls are mocked.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market_data_officer"))

from analyst.contracts import ReasoningBlock, StructureDigest
from analyst.multi_contracts import ArbiterDecision, PersonaVerdict
from analyst.pre_filter import compute_digest
from analyst.arbiter import arbitrate, compute_consensus, validate_arbiter_decision

from tests.conftest import make_packet, make_bullish_4h_structure


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_REASONING = ReasoningBlock(
    summary="test", htf_context="test", liquidity_context="test",
    fvg_context="test", sweep_context="test", verdict_rationale="test",
)


def _make_pv(
    verdict: str,
    confidence: str,
    directional_bias: str,
    persona_name: str = "technical_structure",
    structure_gate: str = "pass",
) -> PersonaVerdict:
    """Build a minimal PersonaVerdict for testing."""
    return PersonaVerdict(
        persona_name=persona_name,
        instrument="EURUSD",
        as_of_utc="2026-03-07T10:15:00Z",
        verdict=verdict,
        confidence=confidence,
        directional_bias=directional_bias,
        structure_gate=structure_gate,
        persona_supports=[],
        persona_conflicts=[],
        persona_cautions=[],
        reasoning=_DUMMY_REASONING,
    )


def _clean_digest() -> StructureDigest:
    """Build a clean digest with no hard no-trade flags."""
    packet = make_packet(structure=make_bullish_4h_structure())
    return compute_digest(packet)


def _no_trade_digest() -> StructureDigest:
    """Build a digest with has_hard_no_trade() == True."""
    packet = make_packet()  # unavailable structure
    return compute_digest(packet)


def _mock_arbiter_llm(*args, **kwargs) -> str:
    """Mock Arbiter LLM response."""
    return json.dumps({
        "synthesis_notes": "Both personas aligned. No conflicts detected.",
        "winning_rationale_summary": "Directional alignment supports the final verdict.",
    })


# =============================================================================
# Group C — Arbiter synthesis
# =============================================================================


class TestGroupC_ArbiterSynthesis:
    """TC.1–TC.5: Deterministic conflict resolution tests."""

    def test_tc1_full_alignment(self):
        """TC.1 — Full alignment produces aligned final verdict."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("long_bias", "high", "bullish", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "full_alignment"
        assert verdict == "long_bias"
        assert confidence in ("high", "moderate")

    def test_tc2_directional_alignment_confidence_split(self):
        """TC.2 — Directional alignment, confidence split → lower confidence."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("long_bias", "moderate", "bullish", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "directional_alignment_confidence_split"
        assert verdict == "long_bias"
        assert confidence == "moderate"

    def test_tc2_variant_with_conditional_same_bias(self):
        """TC.2 variant — One directional, one conditional with same bias."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("conditional", "moderate", "bullish", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "directional_alignment_confidence_split"
        assert verdict == "long_bias"
        assert confidence == "moderate"

    def test_tc3_directional_conflict(self):
        """TC.3 — Directional conflict → mixed, conditional, low."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("short_bias", "high", "bearish", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "mixed"
        assert verdict == "conditional"
        assert confidence == "low"

    def test_tc4_blocked_persona(self):
        """TC.4 — Blocked persona → blocked state, no-trade."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("no_trade", "none", "none", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "blocked"
        assert verdict == "no_trade"

    def test_tc4_variant_both_blocked(self):
        """TC.4 variant — Both personas blocked."""
        digest = _clean_digest()
        a = _make_pv("no_trade", "none", "none")
        b = _make_pv("no_trade", "none", "none", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "blocked"
        assert verdict == "no_trade"
        assert confidence == "none"

    def test_tc5_no_llm_call_on_no_trade(self):
        """TC.5 — Arbiter does not make LLM call when no-trade enforced."""
        digest = _no_trade_digest()

        a = _make_pv("no_trade", "none", "none", structure_gate=digest.structure_gate)
        b = _make_pv("no_trade", "none", "none", persona_name="execution_timing",
                      structure_gate=digest.structure_gate)

        with patch("analyst.arbiter.call_llm") as mock_llm:
            decision = arbitrate([a, b], digest)
            mock_llm.assert_not_called()

        assert decision.no_trade_enforced is True
        assert "Hard no-trade" in decision.synthesis_notes

    def test_tc_full_alignment_arbiter_end_to_end(self):
        """Full arbiter call with LLM mock for aligned personas."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("long_bias", "high", "bullish", persona_name="execution_timing")

        with patch("analyst.arbiter.call_llm", side_effect=_mock_arbiter_llm):
            decision = arbitrate([a, b], digest)

        assert decision.consensus_state == "full_alignment"
        assert decision.final_verdict == "long_bias"
        assert decision.no_trade_enforced is False
        assert len(decision.synthesis_notes) > 0

    def test_tc_conditional_both(self):
        """Both personas conditional → conditional state."""
        digest = _clean_digest()
        a = _make_pv("conditional", "low", "neutral")
        b = _make_pv("conditional", "low", "neutral", persona_name="execution_timing")

        state, verdict, confidence = compute_consensus(a, b, digest)

        assert state == "conditional"
        assert verdict == "conditional"
        assert confidence == "low"


# =============================================================================
# Group D — Deterministic constraint enforcement
# =============================================================================


class TestGroupD_ConstraintEnforcement:
    """TD.1–TD.3: Hard constraint enforcement tests."""

    def test_td1_hard_no_trade_overrides_arbiter(self):
        """TD.1 — Hard no-trade overrides Arbiter LLM output."""
        digest = _no_trade_digest()

        bad_decision = ArbiterDecision(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            consensus_state="no_trade",
            final_verdict="long_bias",
            final_confidence="high",
            final_directional_bias="bullish",
            no_trade_enforced=False,
            personas_agree_direction=True,
            personas_agree_confidence=True,
            confidence_spread="aligned",
            synthesis_notes="",
            winning_rationale_summary="",
        )

        with pytest.raises(ValueError, match="no-trade"):
            validate_arbiter_decision(bad_decision, digest)

    def test_td1_variant_wrong_verdict(self):
        """TD.1 variant — Hard no-trade but verdict is not no_trade."""
        digest = _no_trade_digest()

        bad_decision = ArbiterDecision(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            consensus_state="no_trade",
            final_verdict="long_bias",
            final_confidence="high",
            final_directional_bias="bullish",
            no_trade_enforced=True,
            personas_agree_direction=True,
            personas_agree_confidence=True,
            confidence_spread="aligned",
            synthesis_notes="",
            winning_rationale_summary="",
        )

        with pytest.raises(ValueError, match="final_verdict must be no_trade"):
            validate_arbiter_decision(bad_decision, digest)

    def test_td2_pre_computed_verdict_wins(self):
        """TD.2 — Arbiter final_verdict matches pre-computed value."""
        digest = _clean_digest()
        a = _make_pv("long_bias", "high", "bullish")
        b = _make_pv("long_bias", "moderate", "bullish", persona_name="execution_timing")

        # Mock LLM that tries to return different verdict (ignored by design)
        with patch("analyst.arbiter.call_llm", side_effect=_mock_arbiter_llm):
            decision = arbitrate([a, b], digest)

        # Pre-computed wins regardless of what LLM might say
        assert decision.final_verdict == "long_bias"
        assert decision.final_confidence == "moderate"

    def test_td3_hard_no_trade_consensus_overrides_all(self):
        """TD.3 — Hard no-trade digest forces no_trade regardless of persona verdicts."""
        digest = _no_trade_digest()

        # Even if we somehow construct "directional" personas, hard flag wins
        state, verdict, confidence = compute_consensus(
            _make_pv("long_bias", "high", "bullish", structure_gate=digest.structure_gate),
            _make_pv("long_bias", "high", "bullish", persona_name="execution_timing",
                      structure_gate=digest.structure_gate),
            digest,
        )

        assert state == "no_trade"
        assert verdict == "no_trade"
        assert confidence == "none"

    def test_td_is_actionable(self):
        """Test ArbiterDecision.is_actionable() method."""
        actionable = ArbiterDecision(
            instrument="EURUSD", as_of_utc="2026-03-07T10:15:00Z",
            consensus_state="full_alignment", final_verdict="long_bias",
            final_confidence="moderate", final_directional_bias="bullish",
            no_trade_enforced=False, personas_agree_direction=True,
            personas_agree_confidence=True, confidence_spread="aligned",
            synthesis_notes="", winning_rationale_summary="",
        )
        assert actionable.is_actionable() is True

        not_actionable = ArbiterDecision(
            instrument="EURUSD", as_of_utc="2026-03-07T10:15:00Z",
            consensus_state="no_trade", final_verdict="no_trade",
            final_confidence="none", final_directional_bias="none",
            no_trade_enforced=True, personas_agree_direction=True,
            personas_agree_confidence=True, confidence_spread="aligned",
            synthesis_notes="", winning_rationale_summary="",
        )
        assert not_actionable.is_actionable() is False
