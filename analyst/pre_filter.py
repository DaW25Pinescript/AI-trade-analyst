"""Phase 3E pre-filter: deterministic StructureDigest from MarketPacketV2.

This module is pure Python — no LLM calls, no randomness, no side effects.
Same MarketPacketV2 input produces the same StructureDigest output every time.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure imports resolve from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "market_data_officer"))

from market_data_officer.officer.contracts import (
    MarketPacketV2,
    StructureBlock,
    LiquidityNearest,
)
from analyst.contracts import LiquidityRef, StructureDigest


# ---------------------------------------------------------------------------
# HTF regime gate
# ---------------------------------------------------------------------------


def compute_structure_gate(
    structure: StructureBlock,
    proposed_direction: str | None = None,
) -> tuple[str, str]:
    """Compute the HTF regime gate status.

    Args:
        structure: StructureBlock from MarketPacketV2.
        proposed_direction: Optional "long" or "short" for directional check.

    Returns:
        (gate_status, gate_reason) tuple.
    """
    if not structure.available:
        return "no_data", "structure block unavailable"

    regime = structure.regime
    if regime is None:
        return "no_data", "regime summary missing"

    bias = regime.bias

    if bias == "neutral":
        return "mixed", "HTF regime is neutral — no directional confirmation"

    # If a proposed direction is given, check for contradiction
    if proposed_direction is not None:
        direction_to_bias = {"long": "bullish", "short": "bearish"}
        expected_bias = direction_to_bias.get(proposed_direction)
        if expected_bias and expected_bias != bias:
            return "fail", f"HTF regime {bias} contradicts proposed {proposed_direction}"

    return "pass", f"HTF regime {bias} — no contradiction"


# ---------------------------------------------------------------------------
# BOS / MSS extraction
# ---------------------------------------------------------------------------


def _extract_bos_mss(structure: StructureBlock) -> tuple[str | None, str | None, str | None]:
    """Extract last BOS direction, last MSS direction, and alignment.

    Returns:
        (last_bos, last_mss, bos_mss_alignment)
    """
    if not structure.available or not structure.recent_events:
        return None, None, None

    last_bos = None
    last_mss = None

    for event in structure.recent_events:
        if last_bos is None and event.type in ("bos_bull", "bos_bear"):
            last_bos = "bullish" if "bull" in event.type else "bearish"
        if last_mss is None and event.type in ("mss_bull", "mss_bear"):
            last_mss = "bullish" if "bull" in event.type else "bearish"
        if last_bos is not None and last_mss is not None:
            break

    if last_bos is None and last_mss is None:
        return None, None, None
    if last_bos is None or last_mss is None:
        return last_bos, last_mss, "incomplete"
    if last_bos == last_mss:
        return last_bos, last_mss, "aligned"
    return last_bos, last_mss, "conflicted"


# ---------------------------------------------------------------------------
# Liquidity context
# ---------------------------------------------------------------------------


def _liq_nearest_to_ref(nearest: LiquidityNearest | None) -> LiquidityRef | None:
    """Convert officer's LiquidityNearest to analyst's LiquidityRef."""
    if nearest is None:
        return None
    return LiquidityRef(
        type=nearest.type,
        price=nearest.price,
        scope=nearest.scope,
        status=nearest.status,
    )


def _extract_liquidity(
    structure: StructureBlock,
    current_price: float,
) -> tuple[LiquidityRef | None, LiquidityRef | None, str | None]:
    """Extract nearest liquidity above/below and compute bias.

    Returns:
        (nearest_above, nearest_below, liquidity_bias)
    """
    if not structure.available or not structure.liquidity:
        return None, None, None

    # Prefer 1h, then 4h, then 15m
    preferred_tf = None
    for tf in ("1h", "4h", "15m"):
        if tf in structure.liquidity:
            preferred_tf = tf
            break

    if preferred_tf is None:
        return None, None, None

    summary = structure.liquidity[preferred_tf]
    above = _liq_nearest_to_ref(summary.nearest_above)
    below = _liq_nearest_to_ref(summary.nearest_below)

    if above is None and below is None:
        return None, None, None

    if above is None:
        bias = "below_closer"
    elif below is None:
        bias = "above_closer"
    else:
        dist_above = abs(above.price - current_price)
        dist_below = abs(current_price - below.price)
        if dist_above < dist_below * 0.8:
            bias = "above_closer"
        elif dist_below < dist_above * 0.8:
            bias = "below_closer"
        else:
            bias = "balanced"

    return above, below, bias


# ---------------------------------------------------------------------------
# FVG context
# ---------------------------------------------------------------------------


def classify_fvg_context(active_zones: list, current_price: float) -> str:
    """Classify FVG context relative to current price.

    Returns one of: "discount_bullish", "premium_bearish", "at_fvg", "none".
    """
    if not active_zones:
        return "none"

    for zone in active_zones:
        zone_low = zone.zone_low if hasattr(zone, "zone_low") else zone.get("zone_low", 0)
        zone_high = zone.zone_high if hasattr(zone, "zone_high") else zone.get("zone_high", 0)
        if zone_low <= current_price <= zone_high:
            return "at_fvg"

    bullish_below = []
    bearish_above = []
    for zone in active_zones:
        fvg_type = zone.fvg_type if hasattr(zone, "fvg_type") else zone.get("fvg_type", "")
        zone_low = zone.zone_low if hasattr(zone, "zone_low") else zone.get("zone_low", 0)
        zone_high = zone.zone_high if hasattr(zone, "zone_high") else zone.get("zone_high", 0)

        if fvg_type == "bullish_fvg" and current_price < zone_low:
            bullish_below.append(zone)
        if fvg_type == "bearish_fvg" and current_price > zone_high:
            bearish_above.append(zone)

    if bullish_below:
        return "discount_bullish"
    if bearish_above:
        return "premium_bearish"
    return "none"


# ---------------------------------------------------------------------------
# Sweep / reclaim
# ---------------------------------------------------------------------------


def _extract_sweep_signal(structure: StructureBlock) -> str:
    """Classify recent sweep/reclaim outcomes.

    Returns one of: "bullish_reclaim", "bearish_reclaim", "accepted_beyond", "none".
    """
    if not structure.available or not structure.liquidity:
        return "none"

    for tf in ("1h", "4h", "15m"):
        if tf not in structure.liquidity:
            continue
        summary = structure.liquidity[tf]
        # Check swept levels via nearest above/below
        for nearest in (summary.nearest_above, summary.nearest_below):
            if nearest is None:
                continue
            if nearest.status == "swept":
                # Determine direction from level type
                low_types = {"prior_day_low", "prior_week_low", "equal_lows"}
                high_types = {"prior_day_high", "prior_week_high", "equal_highs"}
                if nearest.type in low_types:
                    return "bullish_reclaim"
                if nearest.type in high_types:
                    return "bearish_reclaim"
                return "accepted_beyond"

    return "none"


# ---------------------------------------------------------------------------
# Supports / conflicts / flags
# ---------------------------------------------------------------------------


def _build_signals(
    structure: StructureBlock,
    htf_bias: str | None,
    last_bos: str | None,
    last_mss: str | None,
    active_fvg_context: str,
    recent_sweep_signal: str,
    nearest_above: LiquidityRef | None,
    nearest_below: LiquidityRef | None,
    current_price: float,
    atr_14: float,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Build structure_supports, structure_conflicts, no_trade_flags, caution_flags."""
    supports: list[str] = []
    conflicts: list[str] = []
    no_trade: list[str] = []
    caution: list[str] = []

    # HTF bias supports
    if htf_bias in ("bullish", "bearish"):
        supports.append(f"{htf_bias} {_htf_source(structure)} regime")

    # BOS alignment
    if last_bos:
        if htf_bias and last_bos == htf_bias:
            supports.append(f"bullish BOS on {_bos_timeframe(structure)}" if last_bos == "bullish" else f"bearish BOS on {_bos_timeframe(structure)}")
        elif htf_bias and last_bos != htf_bias:
            conflicts.append(f"{last_bos} BOS against HTF {htf_bias} regime")

    # MSS alignment / conflict
    if last_mss:
        if htf_bias and last_mss != htf_bias:
            conflicts.append(f"{last_mss} MSS on {_mss_timeframe(structure)} against HTF {htf_bias} regime")
            caution.append("ltf_mss_conflict")
        elif htf_bias and last_mss == htf_bias:
            supports.append(f"{last_mss} MSS on {_mss_timeframe(structure)}")

    # FVG supports
    if active_fvg_context == "discount_bullish":
        fvg_price = _nearest_fvg_price(structure, "bullish_fvg")
        supports.append(f"active discount FVG at {fvg_price}" if fvg_price else "active discount FVG")
    elif active_fvg_context == "premium_bearish":
        fvg_price = _nearest_fvg_price(structure, "bearish_fvg")
        supports.append(f"active premium FVG at {fvg_price}" if fvg_price else "active premium FVG")

    # Sweep signal
    if recent_sweep_signal == "bullish_reclaim":
        supports.append("bullish reclaim of swept lows")
    elif recent_sweep_signal == "bearish_reclaim":
        supports.append("bearish reclaim of swept highs")
    elif recent_sweep_signal == "accepted_beyond":
        caution.append("sweep_unresolved")

    # Liquidity proximity caution
    if nearest_above and atr_14 > 0:
        dist = abs(nearest_above.price - current_price)
        if dist < 0.5 * atr_14 and nearest_above.scope == "external_liquidity":
            caution.append("liquidity_above_close")
            conflicts.append(f"external liquidity above at {nearest_above.type} {nearest_above.price:.5f}")

    # HTF MSS caution
    if structure.available and structure.regime:
        if structure.regime.last_mss_direction is not None:
            # HTF MSS fired recently
            if structure.regime.last_mss_direction != htf_bias:
                caution.append("htf_mss_present")

    return supports, conflicts, no_trade, caution


def _htf_source(structure: StructureBlock) -> str:
    if structure.regime and structure.regime.source_timeframe:
        return structure.regime.source_timeframe
    return "HTF"


def _bos_timeframe(structure: StructureBlock) -> str:
    if structure.recent_events:
        for event in structure.recent_events:
            if event.type in ("bos_bull", "bos_bear"):
                return event.timeframe
    return "unknown"


def _mss_timeframe(structure: StructureBlock) -> str:
    if structure.recent_events:
        for event in structure.recent_events:
            if event.type in ("mss_bull", "mss_bear"):
                return event.timeframe
    return "unknown"


def _nearest_fvg_price(structure: StructureBlock, fvg_type: str) -> str | None:
    if structure.active_fvg_zones:
        for zone in structure.active_fvg_zones:
            if zone.fvg_type == fvg_type:
                return f"{zone.zone_low:.5f}"
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compute_digest(
    packet: MarketPacketV2,
    proposed_direction: str | None = None,
) -> StructureDigest:
    """Compute a deterministic StructureDigest from a MarketPacketV2.

    Args:
        packet: The v2 market packet.
        proposed_direction: Optional "long" or "short" for gate check.

    Returns:
        StructureDigest ready for prompt injection.
    """
    structure = packet.structure

    # Gate
    gate_status, gate_reason = compute_structure_gate(structure, proposed_direction)

    # Early out for unavailable structure
    if not structure.available:
        return StructureDigest(
            instrument=packet.instrument,
            as_of_utc=packet.as_of_utc,
            structure_available=False,
            structure_gate="no_data",
            gate_reason=gate_reason,
            no_trade_flags=["no_structure_data"],
            active_fvg_context="none",
            active_fvg_count=0,
            recent_sweep_signal="none",
        )

    # Regime
    htf_bias = structure.regime.bias if structure.regime else None
    htf_source = structure.regime.source_timeframe if structure.regime else None

    # BOS / MSS
    last_bos, last_mss, bos_mss_alignment = _extract_bos_mss(structure)

    # Current price from packet
    current_price = 0.0
    if packet.features and packet.features.core:
        # Use midpoint of swing range or last close
        core = packet.features.core
        if core.ma_50 > 0:
            current_price = core.ma_50  # reasonable proxy for current price
        elif core.swing_high > 0 and core.swing_low > 0:
            current_price = (core.swing_high + core.swing_low) / 2

    # Try to get actual close from timeframes
    if packet.timeframes:
        for tf in ("1h", "4h", "15m"):
            tf_data = packet.timeframes.get(tf)
            if tf_data and tf_data.get("rows"):
                rows = tf_data["rows"]
                if rows:
                    current_price = rows[-1].get("close", current_price)
                    break

    # Liquidity
    nearest_above, nearest_below, liquidity_bias = _extract_liquidity(
        structure, current_price
    )

    # FVG context
    active_zones = structure.active_fvg_zones or []
    fvg_context = classify_fvg_context(active_zones, current_price)
    fvg_count = len(active_zones)

    # Sweep signal
    sweep_signal = _extract_sweep_signal(structure)

    # ATR for proximity checks
    atr_14 = packet.features.core.atr_14 if packet.features and packet.features.core else 0.0

    # Build signals
    supports, conflicts, no_trade, caution = _build_signals(
        structure,
        htf_bias,
        last_bos,
        last_mss,
        fvg_context,
        sweep_signal,
        nearest_above,
        nearest_below,
        current_price,
        atr_14,
    )

    # Add gate-level no-trade flags
    if gate_status == "no_data":
        if "no_structure_data" not in no_trade:
            no_trade.append("no_structure_data")
    elif gate_status == "fail":
        no_trade.append("htf_gate_fail")
    elif gate_status == "mixed" and htf_bias == "neutral":
        no_trade.append("htf_regime_neutral")

    return StructureDigest(
        instrument=packet.instrument,
        as_of_utc=packet.as_of_utc,
        structure_available=True,
        structure_gate=gate_status,
        gate_reason=gate_reason,
        htf_bias=htf_bias,
        htf_source_timeframe=htf_source,
        last_bos=last_bos,
        last_mss=last_mss,
        bos_mss_alignment=bos_mss_alignment,
        nearest_liquidity_above=nearest_above,
        nearest_liquidity_below=nearest_below,
        liquidity_bias=liquidity_bias,
        active_fvg_context=fvg_context,
        active_fvg_count=fvg_count,
        recent_sweep_signal=sweep_signal,
        structure_supports=supports,
        structure_conflicts=conflicts,
        no_trade_flags=no_trade,
        caution_flags=caution,
    )
