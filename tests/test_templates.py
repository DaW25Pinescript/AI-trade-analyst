"""Phase 3G tests: template rendering.

All template functions must be deterministic string formatters — no LLM calls.
"""

from __future__ import annotations

import pytest

from analyst.contracts import LiquidityRef, StructureDigest
from analyst.multi_contracts import ArbiterDecision, PersonaVerdict
from analyst.contracts import ReasoningBlock
from analyst.explain_contracts import CausalChain, CausalDriver, SignalInfluenceRanking, SignalInfluence
from analyst.templates import (
    render_audit_summary,
    render_fvg_context,
    render_htf_context,
    render_liquidity_context,
    render_persona_summary,
    render_sweep_reclaim_context,
    render_verdict_summary,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_reasoning() -> ReasoningBlock:
    return ReasoningBlock(
        summary="s", htf_context="h", liquidity_context="l",
        fvg_context="f", sweep_context="sw", verdict_rationale="v",
    )


def _make_digest(**kwargs) -> StructureDigest:
    defaults = dict(
        instrument="EURUSD",
        as_of_utc="2026-03-07T10:00:00Z",
        structure_available=True,
        structure_gate="pass",
        gate_reason="test",
        htf_bias="bullish",
        htf_source_timeframe="4h",
        last_bos="bullish",
        last_mss=None,
        bos_mss_alignment="aligned",
        nearest_liquidity_above=LiquidityRef(
            type="prior_day_high", price=1.08720, scope="external_liquidity", status="active",
        ),
        nearest_liquidity_below=LiquidityRef(
            type="equal_lows", price=1.08410, scope="internal_liquidity", status="active",
        ),
        liquidity_bias="below_closer",
        active_fvg_context="discount_bullish",
        active_fvg_count=1,
        recent_sweep_signal="bullish_reclaim",
        no_trade_flags=[],
        caution_flags=[],
    )
    defaults.update(kwargs)
    return StructureDigest(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTemplateRenderers:

    def test_htf_context_bullish(self):
        digest = _make_digest()
        text = render_htf_context(digest)
        assert "4h" in text
        assert "bullish" in text
        assert "HTF Context" in text

    def test_htf_context_no_data(self):
        digest = _make_digest(structure_available=False, structure_gate="no_data")
        text = render_htf_context(digest)
        assert "unavailable" in text.lower()

    def test_htf_context_with_mss_conflict(self):
        digest = _make_digest(last_mss="bearish")
        text = render_htf_context(digest)
        assert "bearish" in text
        assert "conflict" in text.lower()

    def test_liquidity_context_with_levels(self):
        digest = _make_digest()
        text = render_liquidity_context(digest)
        assert "prior_day_high" in text
        assert "equal_lows" in text
        assert "1.08720" in text

    def test_liquidity_context_no_levels(self):
        digest = _make_digest(
            nearest_liquidity_above=None,
            nearest_liquidity_below=None,
        )
        text = render_liquidity_context(digest)
        assert "no active" in text.lower()

    def test_fvg_context_discount(self):
        digest = _make_digest(active_fvg_context="discount_bullish", active_fvg_count=1)
        text = render_fvg_context(digest)
        assert "bullish" in text.lower()
        assert "discount" in text.lower()

    def test_fvg_context_none(self):
        digest = _make_digest(active_fvg_context="none", active_fvg_count=0)
        text = render_fvg_context(digest)
        assert "no active" in text.lower()

    def test_sweep_reclaim_bullish(self):
        digest = _make_digest(recent_sweep_signal="bullish_reclaim")
        text = render_sweep_reclaim_context(digest)
        assert "bullish reclaim" in text.lower()

    def test_sweep_reclaim_none(self):
        digest = _make_digest(recent_sweep_signal="none")
        text = render_sweep_reclaim_context(digest)
        assert "no recent" in text.lower()

    def test_persona_summary(self):
        pa = PersonaVerdict(
            persona_name="technical_structure", instrument="EURUSD",
            as_of_utc="2026-03-07T10:00:00Z", verdict="long_bias",
            confidence="high", directional_bias="bullish", structure_gate="pass",
            persona_supports=[], persona_conflicts=[], persona_cautions=[],
            reasoning=_make_reasoning(),
        )
        pb = PersonaVerdict(
            persona_name="execution_timing", instrument="EURUSD",
            as_of_utc="2026-03-07T10:00:00Z", verdict="conditional",
            confidence="moderate", directional_bias="bullish", structure_gate="pass",
            persona_supports=[], persona_conflicts=[], persona_cautions=[],
            reasoning=_make_reasoning(),
        )
        arbiter = ArbiterDecision(
            instrument="EURUSD", as_of_utc="2026-03-07T10:00:00Z",
            consensus_state="directional_alignment_confidence_split",
            final_verdict="long_bias", final_confidence="moderate",
            final_directional_bias="bullish", no_trade_enforced=False,
            personas_agree_direction=True, personas_agree_confidence=False,
            confidence_spread="high vs moderate",
            synthesis_notes="test", winning_rationale_summary="test",
        )
        text = render_persona_summary([pa, pb], arbiter)
        assert "Technical Structure" in text
        assert "Execution/Timing" in text
        assert "long_bias" in text
        assert "lower" in text.lower()

    def test_verdict_summary_with_cautions(self):
        arbiter = ArbiterDecision(
            instrument="EURUSD", as_of_utc="2026-03-07T10:00:00Z",
            consensus_state="full_alignment", final_verdict="long_bias",
            final_confidence="high", final_directional_bias="bullish",
            no_trade_enforced=False, personas_agree_direction=True,
            personas_agree_confidence=True, confidence_spread="aligned",
            synthesis_notes="test", winning_rationale_summary="test",
        )
        chain = CausalChain(
            no_trade_drivers=[],
            caution_drivers=[CausalDriver(
                flag="ltf_mss_conflict", source="digest",
                raised_by="pre_filter", effect="caution",
            )],
            has_hard_block=False,
        )
        text = render_verdict_summary(arbiter, chain)
        assert "ltf_mss_conflict" in text
        assert "No hard no-trade" in text

    def test_audit_summary_deterministic(self):
        digest = _make_digest()
        pa = PersonaVerdict(
            persona_name="technical_structure", instrument="EURUSD",
            as_of_utc="2026-03-07T10:00:00Z", verdict="long_bias",
            confidence="high", directional_bias="bullish", structure_gate="pass",
            persona_supports=[], persona_conflicts=[], persona_cautions=[],
            reasoning=_make_reasoning(),
        )
        pb = PersonaVerdict(
            persona_name="execution_timing", instrument="EURUSD",
            as_of_utc="2026-03-07T10:00:00Z", verdict="long_bias",
            confidence="high", directional_bias="bullish", structure_gate="pass",
            persona_supports=[], persona_conflicts=[], persona_cautions=[],
            reasoning=_make_reasoning(),
        )
        arbiter = ArbiterDecision(
            instrument="EURUSD", as_of_utc="2026-03-07T10:00:00Z",
            consensus_state="full_alignment", final_verdict="long_bias",
            final_confidence="high", final_directional_bias="bullish",
            no_trade_enforced=False, personas_agree_direction=True,
            personas_agree_confidence=True, confidence_spread="aligned",
            synthesis_notes="test", winning_rationale_summary="test",
        )
        ranking = SignalInfluenceRanking(signals=[], dominant_signal=None, primary_conflict=None)
        chain = CausalChain(no_trade_drivers=[], caution_drivers=[], has_hard_block=False)

        text_a = render_audit_summary(digest, [pa, pb], arbiter, ranking, chain)
        text_b = render_audit_summary(digest, [pa, pb], arbiter, ranking, chain)
        assert text_a == text_b
        assert len(text_a) > 100
