"""Instrument Promotion relay tests — Phase F.

Proves the full fixture → artifact → packet → analyst consumption chain
for GBPUSD, XAGUSD, and XPTUSD, with price plausibility validation.

Mirrors test_phase1a_relay.py (FX pattern) and test_phase1b_relay.py (metals
pattern) but parametrized across the three promotion candidates.
"""

from unittest.mock import patch

import pytest

from market_data_officer.instrument_registry import INSTRUMENT_REGISTRY, get_meta
from market_data_officer.officer.contracts import MarketPacketV2
from market_data_officer.officer.service import refresh_from_latest_exports


# ── Helpers ──────────────────────────────────────────────────────────────

def _analyst_import():
    """Import analyst modules (they live outside market_data_officer/)."""
    from analyst.contracts import AnalystOutput, AnalystVerdict, ReasoningBlock
    from analyst.pre_filter import compute_digest
    from analyst.service import run_analyst
    return AnalystOutput, AnalystVerdict, ReasoningBlock, compute_digest, run_analyst


# ═══════════════════════════════════════════════════════════════════════
# GBPUSD — FX family (6 timeframes, structural parity with EURUSD)
# ═══════════════════════════════════════════════════════════════════════

GBPUSD_TARGET_TFS = set(get_meta("GBPUSD").timeframes)  # {"1m","5m","15m","1h","4h","1d"}


class TestGBPUSDOfficerRelay:
    """AC-1/AC-2/AC-3/AC-4: GBPUSD fixture → valid MarketPacketV2."""

    def test_refresh_returns_valid_packet(self, gbpusd_hot_packages_dir):
        packet = refresh_from_latest_exports("GBPUSD", packages_dir=gbpusd_hot_packages_dir)
        assert isinstance(packet, MarketPacketV2)
        assert packet.instrument == "GBPUSD"
        assert packet.quality.manifest_valid
        assert not packet.quality.stale

    def test_packet_has_correct_timeframes(self, gbpusd_hot_packages_dir):
        packet = refresh_from_latest_exports("GBPUSD", packages_dir=gbpusd_hot_packages_dir)
        assert set(packet.timeframes.keys()) == GBPUSD_TARGET_TFS
        for tf in GBPUSD_TARGET_TFS:
            assert packet.timeframes[tf]["count"] > 0

    def test_all_prices_in_gbpusd_range(self, gbpusd_hot_packages_dir):
        """AC-5: every OHLC value within registry price_range."""
        meta = get_meta("GBPUSD")
        lo, hi = meta.price_range
        packet = refresh_from_latest_exports("GBPUSD", packages_dir=gbpusd_hot_packages_dir)
        for tf, tf_data in packet.timeframes.items():
            for row in tf_data["rows"]:
                for field in ("open", "high", "low", "close"):
                    price = row[field]
                    assert lo <= price <= hi, (
                        f"{tf} row {row['timestamp_utc']}: {field}={price} "
                        f"outside GBPUSD range {lo}–{hi}"
                    )

    def test_packet_serializes_roundtrip(self, gbpusd_hot_packages_dir):
        packet = refresh_from_latest_exports("GBPUSD", packages_dir=gbpusd_hot_packages_dir)
        d = packet.to_dict()
        assert d["instrument"] == "GBPUSD"
        assert len(d["timeframes"]) == len(GBPUSD_TARGET_TFS)
        assert "quality" in d
        assert "features" in d
        assert "state_summary" in d


class TestGBPUSDAnalystConsumption:
    """AC-6: run_analyst() consumes a real GBPUSD packet without crashing."""

    def test_run_analyst_with_injected_gbpusd_packet(self, gbpusd_hot_packages_dir):
        packet = refresh_from_latest_exports("GBPUSD", packages_dir=gbpusd_hot_packages_dir)
        AnalystOutput, AnalystVerdict, ReasoningBlock, compute_digest, run_analyst = _analyst_import()

        digest = compute_digest(packet)
        mock_verdict = AnalystVerdict(
            instrument="GBPUSD",
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
            summary="Promotion relay fixture test — no real LLM call.",
            htf_context="n/a",
            liquidity_context="n/a",
            fvg_context="n/a",
            sweep_context="n/a",
            verdict_rationale="Synthetic GBPUSD fixture data, no trade signal.",
        )

        with patch("analyst.service.run_analyst_llm", return_value=(mock_verdict, mock_reasoning)):
            output = run_analyst("GBPUSD", packet=packet)

        assert isinstance(output, AnalystOutput)
        assert output.verdict.instrument == "GBPUSD"
        assert output.verdict.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
        assert output.digest.instrument == "GBPUSD"


# ═══════════════════════════════════════════════════════════════════════
# XAGUSD — Metals family (4 timeframes, structural parity with XAUUSD)
# ═══════════════════════════════════════════════════════════════════════

XAGUSD_TARGET_TFS = set(get_meta("XAGUSD").timeframes)  # {"15m","1h","4h","1d"}


class TestXAGUSDOfficerRelay:
    """AC-1/AC-2/AC-3/AC-4: XAGUSD fixture → valid MarketPacketV2."""

    def test_refresh_returns_valid_packet(self, xagusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XAGUSD", packages_dir=xagusd_hot_packages_dir)
        assert isinstance(packet, MarketPacketV2)
        assert packet.instrument == "XAGUSD"
        assert packet.quality.manifest_valid
        assert not packet.quality.stale

    def test_packet_has_correct_timeframes(self, xagusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XAGUSD", packages_dir=xagusd_hot_packages_dir)
        assert set(packet.timeframes.keys()) == XAGUSD_TARGET_TFS
        for tf in XAGUSD_TARGET_TFS:
            assert packet.timeframes[tf]["count"] > 0

    def test_all_prices_in_xagusd_range(self, xagusd_hot_packages_dir):
        """AC-5: every OHLC value within registry price_range."""
        meta = get_meta("XAGUSD")
        lo, hi = meta.price_range
        packet = refresh_from_latest_exports("XAGUSD", packages_dir=xagusd_hot_packages_dir)
        for tf, tf_data in packet.timeframes.items():
            for row in tf_data["rows"]:
                for field in ("open", "high", "low", "close"):
                    price = row[field]
                    assert lo <= price <= hi, (
                        f"{tf} row {row['timestamp_utc']}: {field}={price} "
                        f"outside XAGUSD range {lo}–{hi}"
                    )

    def test_packet_serializes_roundtrip(self, xagusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XAGUSD", packages_dir=xagusd_hot_packages_dir)
        d = packet.to_dict()
        assert d["instrument"] == "XAGUSD"
        assert len(d["timeframes"]) == len(XAGUSD_TARGET_TFS)
        assert "quality" in d
        assert "features" in d
        assert "state_summary" in d


class TestXAGUSDAnalystConsumption:
    """AC-6: run_analyst() consumes a real XAGUSD packet without crashing."""

    def test_run_analyst_with_injected_xagusd_packet(self, xagusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XAGUSD", packages_dir=xagusd_hot_packages_dir)
        AnalystOutput, AnalystVerdict, ReasoningBlock, compute_digest, run_analyst = _analyst_import()

        digest = compute_digest(packet)
        mock_verdict = AnalystVerdict(
            instrument="XAGUSD",
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
            summary="Promotion relay fixture test — no real LLM call.",
            htf_context="n/a",
            liquidity_context="n/a",
            fvg_context="n/a",
            sweep_context="n/a",
            verdict_rationale="Synthetic XAGUSD fixture data, no trade signal.",
        )

        with patch("analyst.service.run_analyst_llm", return_value=(mock_verdict, mock_reasoning)):
            output = run_analyst("XAGUSD", packet=packet)

        assert isinstance(output, AnalystOutput)
        assert output.verdict.instrument == "XAGUSD"
        assert output.verdict.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
        assert output.digest.instrument == "XAGUSD"


# ═══════════════════════════════════════════════════════════════════════
# XPTUSD — Metals family (4 timeframes, structural parity with XAUUSD)
# ═══════════════════════════════════════════════════════════════════════

XPTUSD_TARGET_TFS = set(get_meta("XPTUSD").timeframes)  # {"15m","1h","4h","1d"}


class TestXPTUSDOfficerRelay:
    """AC-1/AC-2/AC-3/AC-4: XPTUSD fixture → valid MarketPacketV2."""

    def test_refresh_returns_valid_packet(self, xptusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XPTUSD", packages_dir=xptusd_hot_packages_dir)
        assert isinstance(packet, MarketPacketV2)
        assert packet.instrument == "XPTUSD"
        assert packet.quality.manifest_valid
        assert not packet.quality.stale

    def test_packet_has_correct_timeframes(self, xptusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XPTUSD", packages_dir=xptusd_hot_packages_dir)
        assert set(packet.timeframes.keys()) == XPTUSD_TARGET_TFS
        for tf in XPTUSD_TARGET_TFS:
            assert packet.timeframes[tf]["count"] > 0

    def test_all_prices_in_xptusd_range(self, xptusd_hot_packages_dir):
        """AC-5: every OHLC value within registry price_range."""
        meta = get_meta("XPTUSD")
        lo, hi = meta.price_range
        packet = refresh_from_latest_exports("XPTUSD", packages_dir=xptusd_hot_packages_dir)
        for tf, tf_data in packet.timeframes.items():
            for row in tf_data["rows"]:
                for field in ("open", "high", "low", "close"):
                    price = row[field]
                    assert lo <= price <= hi, (
                        f"{tf} row {row['timestamp_utc']}: {field}={price} "
                        f"outside XPTUSD range {lo}–{hi}"
                    )

    def test_packet_serializes_roundtrip(self, xptusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XPTUSD", packages_dir=xptusd_hot_packages_dir)
        d = packet.to_dict()
        assert d["instrument"] == "XPTUSD"
        assert len(d["timeframes"]) == len(XPTUSD_TARGET_TFS)
        assert "quality" in d
        assert "features" in d
        assert "state_summary" in d


class TestXPTUSDAnalystConsumption:
    """AC-6: run_analyst() consumes a real XPTUSD packet without crashing."""

    def test_run_analyst_with_injected_xptusd_packet(self, xptusd_hot_packages_dir):
        packet = refresh_from_latest_exports("XPTUSD", packages_dir=xptusd_hot_packages_dir)
        AnalystOutput, AnalystVerdict, ReasoningBlock, compute_digest, run_analyst = _analyst_import()

        digest = compute_digest(packet)
        mock_verdict = AnalystVerdict(
            instrument="XPTUSD",
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
            summary="Promotion relay fixture test — no real LLM call.",
            htf_context="n/a",
            liquidity_context="n/a",
            fvg_context="n/a",
            sweep_context="n/a",
            verdict_rationale="Synthetic XPTUSD fixture data, no trade signal.",
        )

        with patch("analyst.service.run_analyst_llm", return_value=(mock_verdict, mock_reasoning)):
            output = run_analyst("XPTUSD", packet=packet)

        assert isinstance(output, AnalystOutput)
        assert output.verdict.instrument == "XPTUSD"
        assert output.verdict.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
        assert output.digest.instrument == "XPTUSD"
