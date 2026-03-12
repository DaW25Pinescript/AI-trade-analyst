"""Phase 3E analyst verdict tests — Groups E, F.

These tests mock the LLM call to verify schema validation,
hard constraint enforcement, and reasoning block completeness.
"""

import json
from unittest.mock import patch

import pytest

from analyst.contracts import AnalystVerdict, ReasoningBlock, StructureDigest
from analyst.analyst import validate_verdict, parse_llm_response, run_analyst_llm
from analyst.pre_filter import compute_digest

from tests.conftest import (
    make_packet,
    make_bullish_4h_structure,
    make_no_fvg_structure,
    _make_core,
)


def _make_llm_response(
    verdict: str = "long_bias",
    confidence: str = "moderate",
    structure_gate: str = "pass",
    htf_bias: str = "bullish",
    ltf_structure_alignment: str = "mixed",
    no_trade_flags: list | None = None,
    caution_flags: list | None = None,
    instrument: str = "EURUSD",
) -> str:
    """Build a synthetic LLM JSON response."""
    return json.dumps({
        "verdict": {
            "instrument": instrument,
            "as_of_utc": "2026-03-07T10:15:00Z",
            "verdict": verdict,
            "confidence": confidence,
            "structure_gate": structure_gate,
            "htf_bias": htf_bias,
            "ltf_structure_alignment": ltf_structure_alignment,
            "active_fvg_context": "none",
            "recent_sweep_signal": "none",
            "structure_supports": ["bullish 4h regime"],
            "structure_conflicts": [],
            "no_trade_flags": no_trade_flags or [],
            "caution_flags": caution_flags or [],
        },
        "reasoning": {
            "summary": "Bullish bias on EURUSD with moderate confidence based on HTF structure.",
            "htf_context": "4h regime: bullish. Structure quality is clean.",
            "liquidity_context": "No significant levels identified in current digest.",
            "fvg_context": "No active FVG zones at present.",
            "sweep_context": "No recent sweep events.",
            "verdict_rationale": "Long bias with moderate confidence. HTF gate passes.",
        },
    })


def _make_no_trade_response(
    structure_gate: str = "no_data",
    no_trade_flags: list | None = None,
) -> str:
    """Build a no-trade LLM response."""
    return json.dumps({
        "verdict": {
            "instrument": "EURUSD",
            "as_of_utc": "2026-03-07T10:15:00Z",
            "verdict": "no_trade",
            "confidence": "none",
            "structure_gate": structure_gate,
            "htf_bias": None,
            "ltf_structure_alignment": "unknown",
            "active_fvg_context": "none",
            "recent_sweep_signal": "none",
            "structure_supports": [],
            "structure_conflicts": [],
            "no_trade_flags": no_trade_flags or ["no_structure_data"],
            "caution_flags": [],
        },
        "reasoning": {
            "summary": "No trade — structure data unavailable. Cannot form a directional view.",
            "htf_context": "No HTF regime available — structure block missing.",
            "liquidity_context": "No liquidity data available.",
            "fvg_context": "No FVG data available.",
            "sweep_context": "No sweep data available.",
            "verdict_rationale": "No trade verdict due to no_structure_data flag. Confidence is none.",
        },
    })


# =============================================================================
# Group E — LLM analyst: verdict schema
# =============================================================================


class TestGroupE_VerdictSchema:
    """TE.1–TE.4: Verdict schema validation and hard constraint enforcement."""

    def test_te1_verdict_all_required_fields(self):
        """TE.1 — Verdict contains all required fields."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", return_value=_make_llm_response()):
            verdict, reasoning = run_analyst_llm(digest, packet)

        assert verdict.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
        assert verdict.confidence in ("high", "moderate", "low", "none")
        assert verdict.structure_gate in ("pass", "fail", "no_data", "mixed")
        assert isinstance(verdict.structure_supports, list)
        assert isinstance(verdict.structure_conflicts, list)
        assert isinstance(verdict.no_trade_flags, list)
        assert isinstance(verdict.caution_flags, list)

    def test_te2_hard_no_trade_forces_verdict(self):
        """TE.2 — Hard no-trade flag forces no_trade verdict."""
        packet = make_packet()  # unavailable structure
        digest = compute_digest(packet)

        assert digest.has_hard_no_trade()

        with patch("analyst.analyst.call_llm", return_value=_make_no_trade_response()):
            verdict, reasoning = run_analyst_llm(digest, packet)

        assert verdict.verdict == "no_trade"
        assert verdict.confidence == "none"

    def test_te3_validator_raises_on_override(self):
        """TE.3 — Validator raises if LLM overrides hard no-trade."""
        digest = StructureDigest(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            structure_available=False,
            structure_gate="no_data",
            no_trade_flags=["no_structure_data"],
            active_fvg_context="none",
            active_fvg_count=0,
            recent_sweep_signal="none",
        )

        bad_verdict = AnalystVerdict(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            verdict="long_bias",
            confidence="high",
            structure_gate="no_data",
            htf_bias=None,
            ltf_structure_alignment="unknown",
            active_fvg_context="none",
            recent_sweep_signal="none",
            structure_supports=[],
            structure_conflicts=[],
            no_trade_flags=["no_structure_data"],
            caution_flags=[],
        )

        with pytest.raises(ValueError, match="hard no-trade"):
            validate_verdict(bad_verdict, digest)

    def test_te3_validator_raises_on_wrong_confidence(self):
        """TE.3 variant — no_trade with non-none confidence raises."""
        digest = StructureDigest(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            structure_available=False,
            structure_gate="no_data",
            no_trade_flags=["no_structure_data"],
            active_fvg_context="none",
            active_fvg_count=0,
            recent_sweep_signal="none",
        )

        bad_verdict = AnalystVerdict(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            verdict="no_trade",
            confidence="moderate",  # wrong — must be "none"
            structure_gate="no_data",
            htf_bias=None,
            ltf_structure_alignment="unknown",
            active_fvg_context="none",
            recent_sweep_signal="none",
            structure_supports=[],
            structure_conflicts=[],
            no_trade_flags=["no_structure_data"],
            caution_flags=[],
        )

        with pytest.raises(ValueError, match="confidence=none"):
            validate_verdict(bad_verdict, digest)

    def test_te4_structure_gate_matches_digest(self):
        """TE.4 — structure_gate in verdict matches digest gate."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", return_value=_make_llm_response(
            structure_gate=digest.structure_gate
        )):
            verdict, reasoning = run_analyst_llm(digest, packet)

        assert verdict.structure_gate == digest.structure_gate

    def test_te4_gate_mismatch_raises(self):
        """TE.4 variant — gate mismatch raises ValueError."""
        digest = StructureDigest(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            structure_available=True,
            structure_gate="pass",
            active_fvg_context="none",
            active_fvg_count=0,
            recent_sweep_signal="none",
        )

        bad_verdict = AnalystVerdict(
            instrument="EURUSD",
            as_of_utc="2026-03-07T10:15:00Z",
            verdict="long_bias",
            confidence="moderate",
            structure_gate="mixed",  # doesn't match digest
            htf_bias="bullish",
            ltf_structure_alignment="aligned",
            active_fvg_context="none",
            recent_sweep_signal="none",
        )

        with pytest.raises(ValueError, match="structure_gate mismatch"):
            validate_verdict(bad_verdict, digest)


# =============================================================================
# Group F — LLM analyst: reasoning block
# =============================================================================


class TestGroupF_ReasoningBlock:
    """TF.1–TF.3: Reasoning block completeness."""

    def test_tf1_reasoning_all_fields(self):
        """TF.1 — ReasoningBlock contains all required fields."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", return_value=_make_llm_response()):
            verdict, reasoning = run_analyst_llm(digest, packet)

        assert reasoning.summary
        assert reasoning.htf_context
        assert reasoning.liquidity_context
        assert reasoning.fvg_context
        assert reasoning.sweep_context
        assert reasoning.verdict_rationale

    def test_tf2_reasoning_mentions_htf_bias(self):
        """TF.2 — Reasoning mentions HTF bias from digest."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", return_value=_make_llm_response()):
            verdict, reasoning = run_analyst_llm(digest, packet)

        if digest.htf_bias:
            assert (
                digest.htf_bias in reasoning.htf_context.lower()
                or digest.htf_bias in reasoning.summary.lower()
            )

    def test_tf3_no_trade_reasoning_explains(self):
        """TF.3 — No-trade reasoning explains the flag."""
        packet = make_packet()  # unavailable structure
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", return_value=_make_no_trade_response()):
            verdict, reasoning = run_analyst_llm(digest, packet)

        if verdict.verdict == "no_trade":
            assert len(reasoning.verdict_rationale) > 20


# =============================================================================
# Parse tests
# =============================================================================


class TestParsing:
    """LLM response parsing edge cases."""

    def test_parse_valid_json(self):
        raw = _make_llm_response()
        v, r = parse_llm_response(raw)
        assert "verdict" in v
        assert "summary" in r

    def test_parse_with_markdown_fences(self):
        raw = "```json\n" + _make_llm_response() + "\n```"
        v, r = parse_llm_response(raw)
        assert "verdict" in v

    def test_parse_missing_verdict_raises(self):
        raw = json.dumps({"reasoning": {"summary": "test"}})
        with pytest.raises(ValueError, match="missing 'verdict'"):
            parse_llm_response(raw)

    def test_parse_missing_reasoning_raises(self):
        raw = json.dumps({"verdict": {"verdict": "long_bias"}})
        with pytest.raises(ValueError, match="missing 'reasoning'"):
            parse_llm_response(raw)
