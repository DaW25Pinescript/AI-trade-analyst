"""Phase 1A relay tests — prove the full handoff chain.

Test A: feed fixture → officer loader → MarketPacketV2 (all 6 TFs)
Test B: run_analyst() with injected packet + mocked LLM → structured result
"""

from unittest.mock import patch

import pytest

from market_data_officer.officer.contracts import MarketPacketV2
from market_data_officer.officer.service import refresh_from_latest_exports
from market_data_officer.officer.loader import EXPECTED_TIMEFRAMES


# ---------------------------------------------------------------------------
# Test A — Officer relay: fixture → refresh_from_latest_exports → MarketPacketV2
# ---------------------------------------------------------------------------

class TestOfficerRelay:
    """AC-3 / AC-4: prove officer assembles a valid packet from fixture artifacts."""

    def test_refresh_returns_valid_packet(self, hot_packages_dir):
        packet = refresh_from_latest_exports("EURUSD", packages_dir=hot_packages_dir)

        assert isinstance(packet, MarketPacketV2)
        assert packet.instrument == "EURUSD"
        assert packet.is_trusted()

    def test_packet_has_all_six_timeframes(self, hot_packages_dir):
        packet = refresh_from_latest_exports("EURUSD", packages_dir=hot_packages_dir)

        for tf in EXPECTED_TIMEFRAMES:
            assert tf in packet.timeframes, f"Missing timeframe: {tf}"
            assert packet.timeframes[tf]["count"] > 0

    def test_packet_quality_valid(self, hot_packages_dir):
        packet = refresh_from_latest_exports("EURUSD", packages_dir=hot_packages_dir)

        assert packet.quality.manifest_valid
        assert packet.quality.all_timeframes_present
        assert not packet.quality.partial

    def test_packet_serializes_roundtrip(self, hot_packages_dir):
        packet = refresh_from_latest_exports("EURUSD", packages_dir=hot_packages_dir)
        d = packet.to_dict()

        assert d["instrument"] == "EURUSD"
        assert "timeframes" in d
        assert len(d["timeframes"]) == 6
        assert "quality" in d
        assert "features" in d
        assert "state_summary" in d


# ---------------------------------------------------------------------------
# Test B — Analyst consumption: injected packet + mocked LLM → AnalystOutput
# ---------------------------------------------------------------------------

class TestAnalystConsumption:
    """AC-5: prove run_analyst() consumes a real packet without crashing."""

    def test_run_analyst_with_injected_packet(self, hot_packages_dir):
        # Build a real packet from fixture artifacts
        packet = refresh_from_latest_exports("EURUSD", packages_dir=hot_packages_dir)

        from analyst.contracts import (
            AnalystOutput,
            AnalystVerdict,
            ReasoningBlock,
        )
        from analyst.pre_filter import compute_digest
        from analyst.service import run_analyst

        # Build a synthetic verdict that the mock LLM will return
        digest = compute_digest(packet)
        mock_verdict = AnalystVerdict(
            instrument="EURUSD",
            as_of_utc=digest.as_of_utc,
            verdict="no_trade",
            confidence="low",
            structure_gate=digest.structure_gate,
            htf_bias=digest.htf_bias,
            ltf_structure_alignment="unknown",
            active_fvg_context=digest.active_fvg_context,
            recent_sweep_signal=digest.recent_sweep_signal,
        )
        mock_reasoning = ReasoningBlock(
            summary="Fixture test — no real LLM call.",
            htf_context="n/a",
            liquidity_context="n/a",
            fvg_context="n/a",
            sweep_context="n/a",
            verdict_rationale="Synthetic fixture data, no trade signal.",
        )

        with patch("analyst.service.run_analyst_llm", return_value=(mock_verdict, mock_reasoning)):
            output = run_analyst("EURUSD", packet=packet)

        assert isinstance(output, AnalystOutput)
        assert output.verdict.instrument == "EURUSD"
        assert output.verdict.verdict in (
            "long_bias", "short_bias", "no_trade", "conditional", "no_data",
        )
        assert output.digest.instrument == "EURUSD"
