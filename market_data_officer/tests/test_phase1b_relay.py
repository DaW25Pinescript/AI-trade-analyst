"""Phase 1B relay tests — prove the full XAUUSD handoff chain.

Test A: XAUUSD fixture → officer loader → MarketPacketV2 (4 TFs, gold-range prices)
Test B: run_analyst() with injected XAUUSD packet + mocked LLM → structured result
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from officer.contracts import MarketPacketV2
from officer.service import refresh_from_latest_exports

# The 4 analyst-target timeframes for XAUUSD (spec §2)
XAUUSD_TARGET_TFS = {"15m", "1h", "4h", "1d"}


# ---------------------------------------------------------------------------
# Test A — Officer relay: XAUUSD fixture → MarketPacketV2
# ---------------------------------------------------------------------------

class TestXAUUSDOfficerRelay:
    """AC-3 / AC-4 / AC-5: valid XAUUSD packet with correct TFs and prices."""

    def test_refresh_returns_valid_packet(self, xauusd_hot_packages_dir):
        packet = refresh_from_latest_exports(
            "XAUUSD", packages_dir=xauusd_hot_packages_dir,
        )

        assert isinstance(packet, MarketPacketV2)
        assert packet.instrument == "XAUUSD"
        # XAUUSD uses 4 TFs (not the full 6), so quality.partial is expected.
        # Verify the manifest itself is valid and data is fresh.
        assert packet.quality.manifest_valid
        assert not packet.quality.stale

    def test_packet_has_exactly_four_timeframes(self, xauusd_hot_packages_dir):
        packet = refresh_from_latest_exports(
            "XAUUSD", packages_dir=xauusd_hot_packages_dir,
        )

        assert set(packet.timeframes.keys()) == XAUUSD_TARGET_TFS
        for tf in XAUUSD_TARGET_TFS:
            assert packet.timeframes[tf]["count"] > 0

    def test_all_prices_in_gold_range(self, xauusd_hot_packages_dir):
        """AC-5: every OHLC value must be within $1,500–$3,500."""
        packet = refresh_from_latest_exports(
            "XAUUSD", packages_dir=xauusd_hot_packages_dir,
        )

        for tf, tf_data in packet.timeframes.items():
            for row in tf_data["rows"]:
                for field in ("open", "high", "low", "close"):
                    price = row[field]
                    assert 1_500.0 <= price <= 3_500.0, (
                        f"{tf} row {row['timestamp_utc']}: {field}={price} "
                        f"outside gold range $1,500–$3,500"
                    )

    def test_packet_serializes_roundtrip(self, xauusd_hot_packages_dir):
        packet = refresh_from_latest_exports(
            "XAUUSD", packages_dir=xauusd_hot_packages_dir,
        )
        d = packet.to_dict()

        assert d["instrument"] == "XAUUSD"
        assert len(d["timeframes"]) == 4
        assert "quality" in d
        assert "features" in d
        assert "state_summary" in d


# ---------------------------------------------------------------------------
# Test B — Analyst consumption: injected XAUUSD packet + mocked LLM
# ---------------------------------------------------------------------------

class TestXAUUSDAnalystConsumption:
    """AC-6: run_analyst() consumes a real XAUUSD packet without crashing."""

    def test_run_analyst_with_injected_xauusd_packet(self, xauusd_hot_packages_dir):
        packet = refresh_from_latest_exports(
            "XAUUSD", packages_dir=xauusd_hot_packages_dir,
        )

        analyst_root = Path(__file__).resolve().parent.parent.parent / "analyst"
        sys.path.insert(0, str(analyst_root.parent))

        from analyst.contracts import (
            AnalystOutput,
            AnalystVerdict,
            ReasoningBlock,
        )
        from analyst.pre_filter import compute_digest
        from analyst.service import run_analyst

        digest = compute_digest(packet)
        mock_verdict = AnalystVerdict(
            instrument="XAUUSD",
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
            summary="Phase 1B fixture test — no real LLM call.",
            htf_context="n/a",
            liquidity_context="n/a",
            fvg_context="n/a",
            sweep_context="n/a",
            verdict_rationale="Synthetic XAUUSD fixture data, no trade signal.",
        )

        with patch(
            "analyst.service.run_analyst_llm",
            return_value=(mock_verdict, mock_reasoning),
        ):
            output = run_analyst("XAUUSD", packet=packet)

        assert isinstance(output, AnalystOutput)
        assert output.verdict.instrument == "XAUUSD"
        assert output.verdict.verdict in (
            "long_bias", "short_bias", "no_trade", "conditional", "no_data",
        )
        assert output.digest.instrument == "XAUUSD"
