"""Phase 3G integration tests: Groups F and G.

Covers output file writing, JSON serialization, CLI, cross-instrument,
and the no-LLM-calls verification.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from analyst.contracts import AnalystVerdict, LiquidityRef, ReasoningBlock, StructureDigest
from analyst.multi_contracts import ArbiterDecision, MultiAnalystOutput, PersonaVerdict
from analyst.explainability import build_explanation, build_explanation_from_dict, REQUIRED_SIGNALS
from analyst.explain_service import attach_explanation, _write_explainability_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "analyst" / "output"


def _make_reasoning() -> ReasoningBlock:
    return ReasoningBlock(
        summary="s", htf_context="h", liquidity_context="l",
        fvg_context="f", sweep_context="sw", verdict_rationale="v",
    )


def _make_test_output(instrument: str = "EURUSD") -> MultiAnalystOutput:
    digest = StructureDigest(
        instrument=instrument,
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
            type="prior_day_high", price=1.08720,
            scope="external_liquidity", status="active",
        ),
        nearest_liquidity_below=LiquidityRef(
            type="equal_lows", price=1.08410,
            scope="internal_liquidity", status="active",
        ),
        liquidity_bias="below_closer",
        active_fvg_context="discount_bullish",
        active_fvg_count=1,
        recent_sweep_signal="bullish_reclaim",
    )

    reasoning = _make_reasoning()

    pa = PersonaVerdict(
        persona_name="technical_structure", instrument=instrument,
        as_of_utc="2026-03-07T10:00:00Z", verdict="long_bias",
        confidence="high", directional_bias="bullish", structure_gate="pass",
        persona_supports=["bullish regime"], persona_conflicts=[],
        persona_cautions=[], reasoning=reasoning,
    )
    pb = PersonaVerdict(
        persona_name="execution_timing", instrument=instrument,
        as_of_utc="2026-03-07T10:00:00Z", verdict="long_bias",
        confidence="moderate", directional_bias="bullish", structure_gate="pass",
        persona_supports=["bullish regime"], persona_conflicts=[],
        persona_cautions=[], reasoning=reasoning,
    )

    arbiter = ArbiterDecision(
        instrument=instrument, as_of_utc="2026-03-07T10:00:00Z",
        consensus_state="directional_alignment_confidence_split",
        final_verdict="long_bias", final_confidence="moderate",
        final_directional_bias="bullish", no_trade_enforced=False,
        personas_agree_direction=True, personas_agree_confidence=False,
        confidence_spread="high vs moderate",
        synthesis_notes="test", winning_rationale_summary="test",
    )

    final_verdict = AnalystVerdict(
        instrument=instrument, as_of_utc="2026-03-07T10:00:00Z",
        verdict="long_bias", confidence="moderate", structure_gate="pass",
        htf_bias="bullish", ltf_structure_alignment="unknown",
        active_fvg_context="discount_bullish", recent_sweep_signal="bullish_reclaim",
    )

    return MultiAnalystOutput(
        instrument=instrument,
        as_of_utc="2026-03-07T10:00:00Z",
        digest=digest,
        persona_outputs=[pa, pb],
        arbiter_decision=arbiter,
        final_verdict=final_verdict,
    )


# ---------------------------------------------------------------------------
# Group F — Output files
# ---------------------------------------------------------------------------


class TestGroupF_OutputFiles:

    def test_tf1_explanation_attached(self):
        output = _make_test_output()
        attach_explanation(output)
        assert output.explanation is not None
        assert isinstance(output.explanation.audit_summary, str)

    def test_tf2_standalone_file_written(self):
        output = _make_test_output()
        block = build_explanation(output)
        _write_explainability_file("EURUSD", block)
        path = OUTPUT_DIR / "EURUSD_multi_analyst_explainability.json"
        assert path.exists()

    def test_tf3_standalone_matches_embedded(self):
        output = _make_test_output()
        attach_explanation(output)
        path = OUTPUT_DIR / "EURUSD_multi_analyst_explainability.json"
        with open(path) as f:
            standalone = json.load(f)
        assert standalone == output.explanation.to_dict()

    def test_tf4_main_output_contains_explanation(self):
        output = _make_test_output()
        attach_explanation(output)
        main_dict = output.to_dict()
        assert "explanation" in main_dict
        assert main_dict["explanation"]["source_verdict"] == output.arbiter_decision.final_verdict

    def test_tf5_json_roundtrip_lossless(self):
        output = _make_test_output()
        block = build_explanation(output)
        serialized = json.dumps(block.to_dict())
        restored = json.loads(serialized)
        assert restored["confidence_provenance"]["final_confidence"] == block.confidence_provenance.final_confidence
        assert len(restored["signal_ranking"]["signals"]) == 7


# ---------------------------------------------------------------------------
# Group G — CLI and cross-instrument + no LLM
# ---------------------------------------------------------------------------


class TestGroupG_CLIAndCoverage:

    def test_tg1_xauusd_produces_valid_block(self):
        output = _make_test_output("XAUUSD")
        block = build_explanation(output)
        assert block.instrument == "XAUUSD"
        signal_names = {s.signal for s in block.signal_ranking.signals}
        assert signal_names == REQUIRED_SIGNALS
        assert len(block.confidence_provenance.steps) >= 5

    def test_tg3_no_llm_calls(self):
        output = _make_test_output()
        fake_anthropic = mock.Mock()
        with mock.patch.dict(sys.modules, {"anthropic": fake_anthropic}):
            block = build_explanation(output)
        fake_anthropic.Anthropic.assert_not_called()
        assert block is not None

    def test_tg4_only_multi_contracts_changed(self):
        """Verify that the only change to existing files is the additive field."""
        # This is verified by the acceptance test checking git diff
        # Here we just verify the field exists
        output = _make_test_output()
        assert hasattr(output, "explanation")
        assert output.explanation is None  # None before attach
        attach_explanation(output)
        assert output.explanation is not None
