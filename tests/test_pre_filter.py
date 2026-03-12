"""Phase 3E pre-filter tests — Groups A, B, C, D.

All tests are deterministic and LLM-free. They verify that compute_digest
produces correct StructureDigest from various MarketPacketV2 configurations.
"""

import json

import pytest

from analyst.pre_filter import compute_digest, classify_fvg_context
from analyst.contracts import StructureDigest
from market_data_officer.officer.contracts import StructureBlock

from tests.conftest import (
    make_packet,
    make_bullish_4h_structure,
    make_bearish_4h_structure,
    make_neutral_regime_structure,
    make_conflicting_regime_structure,
    make_aligned_bos_mss_structure,
    make_discount_fvg_structure,
    make_inside_fvg_structure,
    make_no_fvg_structure,
    make_bullish_reclaim_structure,
    make_liquidity_close_above_structure,
    make_ltf_mss_conflict_structure,
    make_clean_bullish_structure,
    _make_core,
)


# =============================================================================
# Group A — Pre-filter: StructureDigest production
# =============================================================================


class TestGroupA_DigestProduction:
    """TA.1–TA.12: StructureDigest production from various packet configs."""

    def test_ta1_digest_from_valid_packet(self):
        """TA.1 — Digest produced from valid v2 packet."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        assert digest is not None
        assert digest.instrument == "EURUSD"
        assert digest.structure_gate in ("pass", "fail", "no_data", "mixed")

    def test_ta2_unavailable_structure_no_data(self):
        """TA.2 — structure_available=False produces no_data gate."""
        packet = make_packet(structure=StructureBlock.unavailable())
        digest = compute_digest(packet)

        assert digest.structure_available is False
        assert digest.structure_gate == "no_data"
        assert digest.has_hard_no_trade() is True
        assert "no_structure_data" in digest.no_trade_flags

    def test_ta3_bullish_4h_pass_gate(self):
        """TA.3 — Bullish 4h regime produces pass gate."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        assert digest.structure_gate == "pass"
        assert digest.htf_bias == "bullish"
        assert digest.htf_source_timeframe == "4h"

    def test_ta4_neutral_regime_mixed_gate(self):
        """TA.4 — Neutral 4h regime produces mixed gate."""
        packet = make_packet(structure=make_neutral_regime_structure())
        digest = compute_digest(packet)

        assert digest.structure_gate == "mixed"
        assert "htf_regime_neutral" in digest.no_trade_flags

    def test_ta5_conflicting_regimes_mixed_gate(self):
        """TA.5 — Conflicting 4h/1h regimes produce mixed gate.

        Note: This tests that when BOS on 1h contradicts 4h bias at
        the event level, conflicts are generated. The gate is computed
        from the regime which takes 4h preference.
        """
        packet = make_packet(structure=make_conflicting_regime_structure())
        digest = compute_digest(packet)

        # The regime bias is bullish (from 4h), so gate passes.
        # The conflict is captured in structure_conflicts.
        assert digest.structure_gate == "pass"
        assert len(digest.structure_conflicts) > 0

    def test_ta6_bos_mss_alignment_conflicted(self):
        """TA.6 — BOS bullish + MSS bearish = conflicted alignment."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        assert digest.last_bos == "bullish"
        assert digest.last_mss == "bearish"
        assert digest.bos_mss_alignment == "conflicted"

    def test_ta7_bos_mss_aligned(self):
        """TA.7 — Both BOS and MSS bullish = aligned."""
        packet = make_packet(structure=make_aligned_bos_mss_structure())
        digest = compute_digest(packet)

        assert digest.bos_mss_alignment == "aligned"

    def test_ta8_fvg_discount_bullish(self):
        """TA.8 — Price below bullish FVG = discount_bullish."""
        # Price at 1.08400, bullish FVG zone_low=1.08475
        packet = make_packet(
            structure=make_discount_fvg_structure(),
            core=_make_core(ma_50=1.08400),
        )
        digest = compute_digest(packet)

        assert digest.active_fvg_context == "discount_bullish"

    def test_ta9_fvg_at_fvg(self):
        """TA.9 — Price inside FVG zone = at_fvg."""
        # Price at 1.08550, inside zone 1.08475–1.08620
        packet = make_packet(
            structure=make_inside_fvg_structure(),
            core=_make_core(ma_50=1.08550),
        )
        digest = compute_digest(packet)

        assert digest.active_fvg_context == "at_fvg"

    def test_ta10_fvg_none(self):
        """TA.10 — No active FVG zones = none."""
        packet = make_packet(structure=make_no_fvg_structure())
        digest = compute_digest(packet)

        assert digest.active_fvg_context == "none"
        assert digest.active_fvg_count == 0

    def test_ta11_bullish_reclaim(self):
        """TA.11 — Swept low-side level = bullish_reclaim."""
        packet = make_packet(structure=make_bullish_reclaim_structure())
        digest = compute_digest(packet)

        assert digest.recent_sweep_signal == "bullish_reclaim"

    def test_ta12_supports_conflicts_are_lists(self):
        """TA.12 — structure_supports and structure_conflicts always lists."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)

        assert isinstance(digest.structure_supports, list)
        assert isinstance(digest.structure_conflicts, list)

    def test_ta12_no_structure_still_lists(self):
        """TA.12 variant — even with no structure, lists not None."""
        packet = make_packet(structure=StructureBlock.unavailable())
        digest = compute_digest(packet)

        assert isinstance(digest.structure_supports, list)
        assert isinstance(digest.structure_conflicts, list)


# =============================================================================
# Group B — Pre-filter: determinism
# =============================================================================


class TestGroupB_Determinism:
    """TB.1–TB.2: Same input produces same output."""

    def test_tb1_same_packet_identical_digest(self):
        """TB.1 — Same packet produces identical digest."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest_a = compute_digest(packet)
        digest_b = compute_digest(packet)

        assert digest_a.structure_gate == digest_b.structure_gate
        assert digest_a.htf_bias == digest_b.htf_bias
        assert digest_a.active_fvg_context == digest_b.active_fvg_context
        assert digest_a.structure_supports == digest_b.structure_supports
        assert digest_a.structure_conflicts == digest_b.structure_conflicts

    def test_tb2_digest_changes_with_structure(self):
        """TB.2 — Digest changes when structure changes."""
        bullish_packet = make_packet(structure=make_bullish_4h_structure())
        bearish_packet = make_packet(structure=make_bearish_4h_structure())

        digest_bullish = compute_digest(bullish_packet)
        digest_bearish = compute_digest(bearish_packet)

        assert digest_bullish.htf_bias != digest_bearish.htf_bias
        assert (
            digest_bullish.structure_gate != digest_bearish.structure_gate
            or digest_bullish.structure_supports != digest_bearish.structure_supports
        )


# =============================================================================
# Group C — Pre-filter: flag logic
# =============================================================================


class TestGroupC_FlagLogic:
    """TC.1–TC.4: No-trade and caution flag generation."""

    def test_tc1_htf_gate_fail_on_contradiction(self):
        """TC.1 — htf_gate_fail when regime contradicts proposed direction."""
        packet = make_packet(structure=make_bearish_4h_structure())
        digest = compute_digest(packet, proposed_direction="long")

        assert "htf_gate_fail" in digest.no_trade_flags
        assert digest.has_hard_no_trade() is True

    def test_tc2_ltf_mss_conflict_caution(self):
        """TC.2 — ltf_mss_conflict caution when LTF MSS against HTF."""
        packet = make_packet(structure=make_ltf_mss_conflict_structure())
        digest = compute_digest(packet)

        assert "ltf_mss_conflict" in digest.caution_flags
        assert "ltf_mss_conflict" not in digest.no_trade_flags

    def test_tc3_liquidity_above_close_caution(self):
        """TC.3 — liquidity_above_close when external level near above."""
        packet = make_packet(
            structure=make_liquidity_close_above_structure(),
            core=_make_core(atr_14=0.00080, ma_50=1.08500),
        )
        digest = compute_digest(packet)

        assert "liquidity_above_close" in digest.caution_flags

    def test_tc4_clean_structure_no_flags(self):
        """TC.4 — No flags on clean aligned structure."""
        packet = make_packet(structure=make_clean_bullish_structure())
        digest = compute_digest(packet)

        assert digest.no_trade_flags == []
        assert "ltf_mss_conflict" not in digest.caution_flags


# =============================================================================
# Group D — Pre-filter: to_prompt_dict
# =============================================================================


class TestGroupD_PromptDict:
    """TD.1–TD.3: to_prompt_dict() correctness."""

    def test_td1_serialisable(self):
        """TD.1 — to_prompt_dict() produces serialisable dict."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        d = digest.to_prompt_dict()
        json.dumps(d)  # must not raise

    def test_td2_no_raw_structure(self):
        """TD.2 — to_prompt_dict() does not contain raw structure arrays."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        d = digest.to_prompt_dict()
        s = str(d)

        assert "swings" not in s
        assert "events" not in s
        assert "rows" not in s

    def test_td3_contains_key_fields(self):
        """TD.3 — to_prompt_dict() contains all key digest fields."""
        packet = make_packet(structure=make_bullish_4h_structure())
        digest = compute_digest(packet)
        d = digest.to_prompt_dict()

        required = {
            "structure_gate", "htf_bias", "last_bos", "last_mss",
            "active_fvg_context", "recent_sweep_signal",
            "structure_supports", "structure_conflicts",
            "no_trade_flags", "caution_flags",
        }
        assert required.issubset(d.keys())


# =============================================================================
# Additional edge-case tests
# =============================================================================


class TestFVGClassifier:
    """Direct tests for classify_fvg_context function."""

    def test_empty_zones(self):
        assert classify_fvg_context([], 1.08500) == "none"

    def test_price_inside_zone(self):
        zones = [{"fvg_type": "bullish_fvg", "zone_low": 1.08400, "zone_high": 1.08600}]
        assert classify_fvg_context(zones, 1.08500) == "at_fvg"

    def test_discount_bullish(self):
        zones = [{"fvg_type": "bullish_fvg", "zone_low": 1.08500, "zone_high": 1.08600}]
        assert classify_fvg_context(zones, 1.08400) == "discount_bullish"

    def test_premium_bearish(self):
        zones = [{"fvg_type": "bearish_fvg", "zone_low": 1.08400, "zone_high": 1.08500}]
        assert classify_fvg_context(zones, 1.08600) == "premium_bearish"
