"""Phase 3G tests: Groups A–E covering ExplainabilityBlock construction,
signal influence classification, persona dominance, confidence provenance,
and replay determinism.

All tests are pure Python — no LLM calls.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market_data_officer"))

from analyst.contracts import AnalystVerdict, ReasoningBlock, StructureDigest, LiquidityRef
from analyst.multi_contracts import ArbiterDecision, MultiAnalystOutput, PersonaVerdict
from analyst.explainability import (
    REQUIRED_SIGNALS,
    build_explanation,
    build_explanation_from_dict,
    classify_signal_influence,
    compute_confidence_provenance,
    compute_persona_dominance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_reasoning() -> ReasoningBlock:
    return ReasoningBlock(
        summary="Test summary",
        htf_context="Test HTF context",
        liquidity_context="Test liquidity context",
        fvg_context="Test FVG context",
        sweep_context="Test sweep context",
        verdict_rationale="Test rationale",
    )


def _make_digest(
    instrument: str = "EURUSD",
    structure_available: bool = True,
    structure_gate: str = "pass",
    htf_bias: str = "bullish",
    htf_source_timeframe: str = "4h",
    last_bos: str = "bullish",
    last_mss: str = None,
    bos_mss_alignment: str = "aligned",
    liquidity_bias: str = "below_closer",
    active_fvg_context: str = "discount_bullish",
    active_fvg_count: int = 1,
    recent_sweep_signal: str = "bullish_reclaim",
    no_trade_flags: list = None,
    caution_flags: list = None,
    nearest_above: LiquidityRef = None,
    nearest_below: LiquidityRef = None,
) -> StructureDigest:
    return StructureDigest(
        instrument=instrument,
        as_of_utc="2026-03-07T10:00:00Z",
        structure_available=structure_available,
        structure_gate=structure_gate,
        gate_reason="test gate reason",
        htf_bias=htf_bias if structure_available else None,
        htf_source_timeframe=htf_source_timeframe if structure_available else None,
        last_bos=last_bos if structure_available else None,
        last_mss=last_mss,
        bos_mss_alignment=bos_mss_alignment if structure_available else None,
        nearest_liquidity_above=nearest_above,
        nearest_liquidity_below=nearest_below,
        liquidity_bias=liquidity_bias if structure_available else None,
        active_fvg_context=active_fvg_context if structure_available else "none",
        active_fvg_count=active_fvg_count if structure_available else 0,
        recent_sweep_signal=recent_sweep_signal if structure_available else "none",
        no_trade_flags=no_trade_flags or [],
        caution_flags=caution_flags or [],
    )


def _make_persona(
    name: str = "technical_structure",
    verdict: str = "long_bias",
    confidence: str = "high",
    directional_bias: str = "bullish",
    gate: str = "pass",
) -> PersonaVerdict:
    return PersonaVerdict(
        persona_name=name,
        instrument="EURUSD",
        as_of_utc="2026-03-07T10:00:00Z",
        verdict=verdict,
        confidence=confidence,
        directional_bias=directional_bias,
        structure_gate=gate,
        persona_supports=["bullish regime"],
        persona_conflicts=[],
        persona_cautions=[],
        reasoning=_make_reasoning(),
    )


def _make_arbiter(
    verdict: str = "long_bias",
    confidence: str = "high",
    consensus: str = "full_alignment",
    no_trade: bool = False,
    agree_dir: bool = True,
    agree_conf: bool = True,
) -> ArbiterDecision:
    bias_map = {"long_bias": "bullish", "short_bias": "bearish", "no_trade": "none", "conditional": "neutral"}
    return ArbiterDecision(
        instrument="EURUSD",
        as_of_utc="2026-03-07T10:00:00Z",
        consensus_state=consensus,
        final_verdict=verdict,
        final_confidence=confidence,
        final_directional_bias=bias_map.get(verdict, "none"),
        no_trade_enforced=no_trade,
        personas_agree_direction=agree_dir,
        personas_agree_confidence=agree_conf,
        confidence_spread="aligned" if agree_conf else "high vs moderate",
        synthesis_notes="Test synthesis.",
        winning_rationale_summary="Test rationale.",
    )


def _make_final_verdict(verdict: str = "long_bias", confidence: str = "high") -> AnalystVerdict:
    return AnalystVerdict(
        instrument="EURUSD",
        as_of_utc="2026-03-07T10:00:00Z",
        verdict=verdict,
        confidence=confidence,
        structure_gate="pass",
        htf_bias="bullish",
        ltf_structure_alignment="unknown",
        active_fvg_context="discount_bullish",
        recent_sweep_signal="bullish_reclaim",
    )


def _make_output(
    digest: StructureDigest = None,
    persona_a: PersonaVerdict = None,
    persona_b: PersonaVerdict = None,
    arbiter: ArbiterDecision = None,
) -> MultiAnalystOutput:
    d = digest or _make_digest()
    pa = persona_a or _make_persona("technical_structure", "long_bias", "high", "bullish")
    pb = persona_b or _make_persona("execution_timing", "long_bias", "high", "bullish")
    arb = arbiter or _make_arbiter()
    fv = _make_final_verdict(arb.final_verdict, arb.final_confidence)
    return MultiAnalystOutput(
        instrument="EURUSD",
        as_of_utc="2026-03-07T10:00:00Z",
        digest=d,
        persona_outputs=[pa, pb],
        arbiter_decision=arb,
        final_verdict=fv,
    )


# ---------------------------------------------------------------------------
# Group A — ExplainabilityBlock construction
# ---------------------------------------------------------------------------


class TestGroupA_ExplainabilityBlock:

    def test_ta1_block_produced(self):
        output = _make_output()
        block = build_explanation(output)
        assert block is not None
        assert block.instrument == "EURUSD"
        assert block.source_verdict == output.arbiter_decision.final_verdict
        assert block.source_confidence == output.arbiter_decision.final_confidence

    def test_ta2_all_seven_signals(self):
        output = _make_output()
        block = build_explanation(output)
        signal_names = {s.signal for s in block.signal_ranking.signals}
        assert signal_names == REQUIRED_SIGNALS

    def test_ta3_valid_influences(self):
        output = _make_output()
        block = build_explanation(output)
        valid = {"dominant", "supporting", "conflicting", "neutral", "absent"}
        for s in block.signal_ranking.signals:
            assert s.influence in valid, f"Invalid influence: {s.influence} for {s.signal}"

    def test_ta4_confidence_provenance_steps(self):
        output = _make_output()
        block = build_explanation(output)
        assert len(block.confidence_provenance.steps) >= 5
        assert block.confidence_provenance.final_confidence == output.arbiter_decision.final_confidence

    def test_ta5_causal_chain(self):
        output = _make_output()
        block = build_explanation(output)
        assert isinstance(block.causal_chain.no_trade_drivers, list)
        assert isinstance(block.causal_chain.caution_drivers, list)
        nt_flags = {d.flag for d in block.causal_chain.no_trade_drivers}
        caution_flags = {d.flag for d in block.causal_chain.caution_drivers}
        assert nt_flags.isdisjoint(caution_flags)

    def test_ta6_audit_summary(self):
        output = _make_output()
        block = build_explanation(output)
        assert isinstance(block.audit_summary, str)
        assert len(block.audit_summary) > 100


# ---------------------------------------------------------------------------
# Group B — Signal influence classification
# ---------------------------------------------------------------------------


class TestGroupB_SignalInfluence:

    def test_tb1_bullish_htf_pass_dominant(self):
        digest = _make_digest(structure_gate="pass", htf_bias="bullish")
        influence = classify_signal_influence("htf_regime", digest, verdict="long_bias")
        assert influence == "dominant"

    def test_tb2_no_structure_absent(self):
        digest = _make_digest(structure_available=False, structure_gate="no_data")
        influence = classify_signal_influence("htf_regime", digest, verdict="long_bias")
        assert influence == "absent"

    def test_tb3_liquidity_above_close_conflicting(self):
        digest = _make_digest(
            caution_flags=["liquidity_above_close"],
            nearest_above=LiquidityRef(
                type="prior_day_high", price=1.08530,
                scope="external_liquidity", status="active",
            ),
            nearest_below=LiquidityRef(
                type="equal_lows", price=1.08200,
                scope="internal_liquidity", status="active",
            ),
        )
        influence = classify_signal_influence("liquidity", digest, verdict="long_bias")
        assert influence == "conflicting"

    def test_tb4_discount_fvg_supporting(self):
        digest = _make_digest(active_fvg_context="discount_bullish", active_fvg_count=1)
        influence = classify_signal_influence("fvg_context", digest, verdict="long_bias")
        assert influence in ("dominant", "supporting")

    def test_tb5_no_fvg_neutral_or_absent(self):
        digest = _make_digest(active_fvg_context="none", active_fvg_count=0)
        influence = classify_signal_influence("fvg_context", digest, verdict="long_bias")
        assert influence in ("neutral", "absent")

    def test_tb6_no_trade_flags_conflicting(self):
        digest = _make_digest(no_trade_flags=["htf_gate_fail"])
        influence = classify_signal_influence("no_trade_flags", digest, verdict="no_trade")
        assert influence == "conflicting"

    def test_tb7_no_flags_neutral(self):
        digest = _make_digest(no_trade_flags=[], caution_flags=[])
        influence = classify_signal_influence("no_trade_flags", digest, verdict="long_bias")
        assert influence == "neutral"


# ---------------------------------------------------------------------------
# Group C — Persona dominance
# ---------------------------------------------------------------------------


class TestGroupC_PersonaDominance:

    def test_tc1_both_agree_direction(self):
        pa = _make_persona("technical_structure", "long_bias", "high", "bullish")
        pb = _make_persona("execution_timing", "long_bias", "high", "bullish")
        arbiter = _make_arbiter("long_bias", "high", "full_alignment")
        dominance = compute_persona_dominance([pa, pb], arbiter)
        assert dominance.direction_driver == "both"

    def test_tc2_confidence_split(self):
        pa = _make_persona("technical_structure", "long_bias", "high", "bullish")
        pb = _make_persona("execution_timing", "long_bias", "moderate", "bullish")
        arbiter = _make_arbiter(
            "long_bias", "moderate",
            "directional_alignment_confidence_split",
            agree_dir=True, agree_conf=False,
        )
        dominance = compute_persona_dominance([pa, pb], arbiter)
        assert dominance.stricter_persona == "execution_timing"
        assert dominance.confidence_driver == "execution_timing"
        assert dominance.confidence_effect == "downgraded"

    def test_tc3_python_override(self):
        pa = _make_persona("technical_structure", "no_trade", "none", "none")
        pb = _make_persona("execution_timing", "no_trade", "none", "none")
        arbiter = _make_arbiter("no_trade", "none", "no_trade", no_trade=True)
        dominance = compute_persona_dominance([pa, pb], arbiter)
        assert dominance.direction_driver == "arbiter_override"
        assert dominance.python_override_active is True
        assert dominance.confidence_effect == "overridden_by_python"

    def test_tc4_note_non_empty(self):
        pa = _make_persona("technical_structure", "long_bias", "high", "bullish")
        pb = _make_persona("execution_timing", "long_bias", "high", "bullish")
        arbiter = _make_arbiter("long_bias", "high", "full_alignment")
        dominance = compute_persona_dominance([pa, pb], arbiter)
        assert isinstance(dominance.note, str)
        assert len(dominance.note) > 10


# ---------------------------------------------------------------------------
# Group D — Confidence provenance
# ---------------------------------------------------------------------------


class TestGroupD_ConfidenceProvenance:

    def test_td1_full_alignment(self):
        pa = _make_persona("technical_structure", "long_bias", "high", "bullish")
        pb = _make_persona("execution_timing", "long_bias", "high", "bullish")
        arbiter = _make_arbiter("long_bias", "high", "full_alignment")
        digest = _make_digest()
        prov = compute_confidence_provenance([pa, pb], arbiter, digest)
        assert prov.steps[0].value == "high"
        assert prov.steps[1].value == "high"
        assert prov.steps[2].value == "full_alignment"
        assert prov.final_confidence == "high"
        assert prov.python_override is False

    def test_td2_confidence_split(self):
        pa = _make_persona("technical_structure", "long_bias", "high", "bullish")
        pb = _make_persona("execution_timing", "long_bias", "moderate", "bullish")
        arbiter = _make_arbiter(
            "long_bias", "moderate",
            "directional_alignment_confidence_split",
        )
        digest = _make_digest()
        prov = compute_confidence_provenance([pa, pb], arbiter, digest)
        assert prov.steps[0].value == "high"
        assert prov.steps[1].value == "moderate"
        assert "lower" in prov.steps[3].rule.lower()
        assert prov.final_confidence == "moderate"

    def test_td3_python_override(self):
        pa = _make_persona("technical_structure", "no_trade", "none", "none")
        pb = _make_persona("execution_timing", "no_trade", "none", "none")
        arbiter = _make_arbiter("no_trade", "none", "no_trade", no_trade=True)
        digest = _make_digest(no_trade_flags=["htf_gate_fail"])
        prov = compute_confidence_provenance([pa, pb], arbiter, digest)
        assert prov.python_override is True
        assert prov.final_confidence == "none"
        assert prov.override_reason is not None
        assert len(prov.steps) >= 5


# ---------------------------------------------------------------------------
# Group E — Replay determinism
# ---------------------------------------------------------------------------


class TestGroupE_ReplayDeterminism:

    def test_te1_same_output_same_block(self):
        output = _make_output()
        block_a = build_explanation(output)
        block_b = build_explanation(output)
        assert block_a.to_dict() == block_b.to_dict()

    def test_te2_replay_from_saved_file(self):
        output = _make_output()
        block_a = build_explanation(output)

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(output.to_dict(), f)
            tmp_path = f.name

        try:
            # Reload and re-derive
            with open(tmp_path) as f:
                saved_dict = json.load(f)
            replayed_block = build_explanation_from_dict(saved_dict)
            assert block_a.to_dict() == replayed_block.to_dict()
        finally:
            os.unlink(tmp_path)

    def test_te3_different_inputs_different_rankings(self):
        output_bullish = _make_output(
            digest=_make_digest(htf_bias="bullish"),
            arbiter=_make_arbiter("long_bias", "high"),
        )
        output_no_trade = _make_output(
            digest=_make_digest(
                structure_available=False,
                structure_gate="no_data",
                no_trade_flags=["no_structure_data"],
            ),
            persona_a=_make_persona("technical_structure", "no_trade", "none", "none", "no_data"),
            persona_b=_make_persona("execution_timing", "no_trade", "none", "none", "no_data"),
            arbiter=_make_arbiter("no_trade", "none", "no_trade", no_trade=True),
        )
        block_a = build_explanation(output_bullish)
        block_b = build_explanation(output_no_trade)

        assert (
            block_a.signal_ranking.dominant_signal != block_b.signal_ranking.dominant_signal
            or block_a.confidence_provenance.final_confidence != block_b.confidence_provenance.final_confidence
        )
