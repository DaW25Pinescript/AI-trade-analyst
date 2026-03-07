"""Phase 3G deterministic prose template renderer.

Zero LLM calls. All functions take structured inputs and return formatted strings.
Templates use conditionals (if/else) to vary phrasing based on field values.
They never produce freeform text beyond what the field values determine.
"""

from __future__ import annotations

from analyst.contracts import StructureDigest
from analyst.multi_contracts import ArbiterDecision, PersonaVerdict
from analyst.explain_contracts import CausalChain, SignalInfluenceRanking


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------


def render_htf_context(digest: StructureDigest) -> str:
    """Render HTF context section."""
    if not digest.structure_available or digest.structure_gate == "no_data":
        return "HTF Context: Structure data unavailable. No regime assessment possible."

    tf = digest.htf_source_timeframe or "HTF"
    bias = digest.htf_bias or "unknown"
    parts = [f"HTF Context: {tf} regime was {bias}."]

    if digest.last_bos:
        parts.append(f"Last confirmed BOS was {digest.last_bos}.")

    if digest.last_mss:
        if digest.htf_bias and digest.last_mss != digest.htf_bias:
            parts.append(
                f"Last MSS was {digest.last_mss} — classified as minor LTF conflict."
            )
        else:
            parts.append(f"Last MSS was {digest.last_mss} — aligned with regime.")

    return " ".join(parts)


def render_liquidity_context(digest: StructureDigest) -> str:
    """Render liquidity context section."""
    if not digest.structure_available:
        return "Liquidity: No structure data available."

    if digest.nearest_liquidity_above is None and digest.nearest_liquidity_below is None:
        return "Liquidity: No active liquidity levels identified."

    parts = ["Liquidity:"]

    if digest.nearest_liquidity_above:
        above = digest.nearest_liquidity_above
        scope = above.scope.replace("_", " ")
        parts.append(
            f"Nearest overhead level was {above.type} at {above.price:.5f} ({scope})."
        )

    if digest.nearest_liquidity_below:
        below = digest.nearest_liquidity_below
        scope = below.scope.replace("_", " ")
        parts.append(
            f"Nearest support was {below.type} at {below.price:.5f} ({scope})."
        )

    if digest.liquidity_bias:
        if digest.liquidity_bias == "above_closer":
            parts.append("Liquidity draw toward levels above.")
        elif digest.liquidity_bias == "below_closer":
            parts.append("Liquidity draw toward levels below.")
        else:
            parts.append("Liquidity balanced between above and below.")

    return " ".join(parts)


def render_fvg_context(digest: StructureDigest) -> str:
    """Render FVG context section."""
    if not digest.structure_available:
        return "FVG Context: No structure data available."

    ctx = digest.active_fvg_context
    count = digest.active_fvg_count

    if ctx is None or ctx == "none" or count == 0:
        return "FVG Context: No active FVG zones identified."

    if ctx == "discount_bullish":
        return f"FVG Context: Active bullish FVG zone in discount — {count} zone(s) active."
    if ctx == "premium_bearish":
        return f"FVG Context: Active bearish FVG zone in premium — {count} zone(s) active."
    if ctx == "at_fvg":
        return f"FVG Context: Price at active FVG zone — {count} zone(s) active."

    return f"FVG Context: {count} active FVG zone(s), context: {ctx}."


def render_sweep_reclaim_context(digest: StructureDigest) -> str:
    """Render sweep/reclaim context section."""
    if not digest.structure_available:
        return "Sweep/Reclaim: No structure data available."

    sweep = digest.recent_sweep_signal
    if sweep is None or sweep == "none":
        return "Sweep/Reclaim: No recent sweep or reclaim activity."

    if sweep == "bullish_reclaim":
        return "Sweep/Reclaim: Bullish reclaim confirmed. Supportive of bullish continuation."
    if sweep == "bearish_reclaim":
        return "Sweep/Reclaim: Bearish reclaim confirmed. Supportive of bearish continuation."
    if sweep == "accepted_beyond":
        return "Sweep/Reclaim: Price accepted beyond swept level. Neutral."

    return f"Sweep/Reclaim: {sweep}."


def render_persona_summary(
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision,
) -> str:
    """Render persona summary section."""
    pa = next((p for p in persona_outputs if p.persona_name == "technical_structure"), persona_outputs[0])
    pb = next((p for p in persona_outputs if p.persona_name == "execution_timing"), persona_outputs[-1])

    parts = [
        f"Persona Summary: Technical Structure returned {pa.verdict} at {pa.confidence} confidence.",
        f"Execution/Timing returned {pb.verdict} at {pb.confidence} confidence.",
        f"Consensus: {arbiter.consensus_state}.",
    ]

    if arbiter.no_trade_enforced:
        parts.append("Python hard constraint enforced no-trade.")
    elif not arbiter.personas_agree_confidence:
        parts.append("Arbiter used lower confidence tier.")
    else:
        parts.append(f"Arbiter held confidence at {arbiter.final_confidence}.")

    return " ".join(parts)


def render_verdict_summary(
    arbiter: ArbiterDecision,
    causal_chain: CausalChain,
) -> str:
    """Render final verdict summary section."""
    parts = [
        f"Final Verdict: {arbiter.final_verdict} — {arbiter.final_confidence} confidence."
    ]

    if causal_chain.caution_drivers:
        caution_flags = [d.flag for d in causal_chain.caution_drivers]
        parts.append(f"Active cautions: {', '.join(caution_flags)}.")

    if causal_chain.has_hard_block:
        nt_flags = [d.flag for d in causal_chain.no_trade_drivers]
        parts.append(f"Hard no-trade flags active: {', '.join(nt_flags)}.")
    else:
        parts.append("No hard no-trade flags were active.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main audit summary renderer
# ---------------------------------------------------------------------------


def render_audit_summary(
    digest: StructureDigest,
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision,
    signal_ranking: SignalInfluenceRanking,
    causal_chain: CausalChain,
) -> str:
    """Render the complete human-readable audit summary.

    This is a template fill-in, not LLM generation. The same saved output
    always produces the same audit text.
    """
    sections = [
        render_htf_context(digest),
        render_liquidity_context(digest),
        render_fvg_context(digest),
        render_sweep_reclaim_context(digest),
        render_persona_summary(persona_outputs, arbiter),
        render_verdict_summary(arbiter, causal_chain),
    ]

    return "\n\n".join(sections)
