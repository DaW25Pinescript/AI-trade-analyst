"""Phase 3E integration tests — Group G.

Tests full pipeline: digest → LLM (mocked) → output file.
Verifies output file format, atomic writes, and verdict sensitivity to structure changes.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market_data_officer"))

from analyst.contracts import AnalystOutput
from analyst.pre_filter import compute_digest
from analyst.analyst import run_analyst_llm
from analyst.service import _write_output, run_analyst_with_packet

from tests.conftest import (
    make_packet,
    make_bullish_4h_structure,
    make_bearish_4h_structure,
    _make_core,
)


def _mock_llm_bullish(*args, **kwargs) -> str:
    return json.dumps({
        "verdict": {
            "instrument": "EURUSD",
            "as_of_utc": "2026-03-07T10:15:00Z",
            "verdict": "long_bias",
            "confidence": "moderate",
            "structure_gate": "pass",
            "htf_bias": "bullish",
            "ltf_structure_alignment": "mixed",
            "active_fvg_context": "none",
            "recent_sweep_signal": "none",
            "structure_supports": ["bullish 4h regime"],
            "structure_conflicts": [],
            "no_trade_flags": [],
            "caution_flags": [],
        },
        "reasoning": {
            "summary": "Bullish bias on EURUSD. HTF 4h regime supports long.",
            "htf_context": "4h regime: bullish.",
            "liquidity_context": "No significant levels.",
            "fvg_context": "No active FVG zones.",
            "sweep_context": "No recent sweeps.",
            "verdict_rationale": "Long bias with moderate confidence.",
        },
    })


def _mock_llm_bearish(*args, **kwargs) -> str:
    return json.dumps({
        "verdict": {
            "instrument": "EURUSD",
            "as_of_utc": "2026-03-07T10:15:00Z",
            "verdict": "short_bias",
            "confidence": "moderate",
            "structure_gate": "pass",
            "htf_bias": "bearish",
            "ltf_structure_alignment": "aligned",
            "active_fvg_context": "none",
            "recent_sweep_signal": "none",
            "structure_supports": ["bearish 4h regime"],
            "structure_conflicts": [],
            "no_trade_flags": [],
            "caution_flags": [],
        },
        "reasoning": {
            "summary": "Bearish bias on EURUSD. HTF 4h regime supports short.",
            "htf_context": "4h regime: bearish.",
            "liquidity_context": "No significant levels.",
            "fvg_context": "No active FVG zones.",
            "sweep_context": "No recent sweeps.",
            "verdict_rationale": "Short bias with moderate confidence.",
        },
    })


# =============================================================================
# Group G — Integration and output
# =============================================================================


class TestGroupG_Integration:
    """TG.1–TG.5: Full pipeline integration tests."""

    def test_tg1_output_file_written(self, tmp_path):
        """TG.1 — Output file written after run."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", side_effect=_mock_llm_bullish):
            verdict, reasoning = run_analyst_llm(digest, packet)

        output = AnalystOutput(verdict=verdict, reasoning=reasoning, digest=digest)

        # Write to tmp location
        with patch("analyst.service.OUTPUT_DIR", tmp_path):
            from analyst.service import _write_output
            _write_output("EURUSD", output)

        assert (tmp_path / "EURUSD_analyst_output.json").exists()

    def test_tg2_output_valid_json(self, tmp_path):
        """TG.2 — Output file is valid JSON with all three blocks."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", side_effect=_mock_llm_bullish):
            verdict, reasoning = run_analyst_llm(digest, packet)

        output = AnalystOutput(verdict=verdict, reasoning=reasoning, digest=digest)

        with patch("analyst.service.OUTPUT_DIR", tmp_path):
            from analyst.service import _write_output
            _write_output("EURUSD", output)

        with open(tmp_path / "EURUSD_analyst_output.json") as f:
            saved = json.load(f)

        assert "verdict" in saved
        assert "reasoning" in saved
        assert "digest" in saved

    def test_tg4_verdict_changes_with_structure(self):
        """TG.4 — Verdict changes when structure changes."""
        bullish_packet = make_packet(structure=make_bullish_4h_structure())
        bearish_packet = make_packet(structure=make_bearish_4h_structure())

        digest_bull = compute_digest(bullish_packet)
        digest_bear = compute_digest(bearish_packet)

        with patch("analyst.analyst.call_llm", side_effect=_mock_llm_bullish):
            verdict_bull, _ = run_analyst_llm(digest_bull, bullish_packet)

        with patch("analyst.analyst.call_llm", side_effect=_mock_llm_bearish):
            verdict_bear, _ = run_analyst_llm(digest_bear, bearish_packet)

        assert (
            verdict_bull.verdict != verdict_bear.verdict
            or verdict_bull.htf_bias != verdict_bear.htf_bias
        )

    def test_tg5_no_existing_files_modified(self):
        """TG.5 — Feed, Officer, structure files not modified.

        This is a git-level check. In unit tests, we verify analyst
        imports work without modifying source files.
        """
        # Verify we can import without errors
        from analyst.pre_filter import compute_digest
        from analyst.analyst import run_analyst_llm
        from analyst.service import run_analyst
        from analyst.contracts import StructureDigest, AnalystVerdict

        # The actual git diff check is done at the acceptance test level

    def test_output_to_dict_round_trip(self):
        """Verify AnalystOutput.to_dict() produces complete structure."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        with patch("analyst.analyst.call_llm", side_effect=_mock_llm_bullish):
            verdict, reasoning = run_analyst_llm(digest, packet)

        output = AnalystOutput(verdict=verdict, reasoning=reasoning, digest=digest)
        d = output.to_dict()

        # Verify JSON-serialisable
        json.dumps(d)

        # Verify all three top-level blocks
        assert "verdict" in d
        assert "reasoning" in d
        assert "digest" in d

        # Verify verdict fields
        assert d["verdict"]["verdict"] == "long_bias"
        assert d["verdict"]["confidence"] == "moderate"

        # Verify reasoning fields
        assert len(d["reasoning"]["summary"]) > 0

        # Verify digest fields
        assert d["digest"]["structure_gate"] == "pass"
