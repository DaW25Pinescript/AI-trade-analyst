"""Phase 3G explanation engine: produces ExplainabilityBlock from MultiAnalystOutput.

Zero LLM calls permitted. All classification is rule-based from saved artifacts.
"""

from __future__ import annotations

from typing import Optional

from analyst.contracts import StructureDigest
from analyst.multi_contracts import ArbiterDecision, MultiAnalystOutput, PersonaVerdict
from analyst.explain_contracts import (
    CausalChain,
    CausalDriver,
    ConfidenceProvenance,
    ConfidenceStep,
    ExplainabilityBlock,
    PersonaDominance,
    SignalInfluence,
    SignalInfluenceRanking,
)
from analyst.templates import render_audit_summary

# ---------------------------------------------------------------------------
# Required signals — Rule 8: all seven must be present in every ranking
# ---------------------------------------------------------------------------

REQUIRED_SIGNALS = {
    "htf_regime",
    "bos_mss",
    "liquidity",
    "fvg_context",
    "sweep_reclaim",
    "no_trade_flags",
    "caution_flags",
}

# ---------------------------------------------------------------------------
# Confidence ordering helper
# ---------------------------------------------------------------------------

_CONFIDENCE_ORDER = {"high": 3, "moderate": 2, "low": 1, "none": 0}


def _lower_confidence(a: str, b: str) -> str:
    return a if _CONFIDENCE_ORDER.get(a, 0) <= _CONFIDENCE_ORDER.get(b, 0) else b


# ---------------------------------------------------------------------------
# Verdict-to-bias mapping
# ---------------------------------------------------------------------------

_VERDICT_TO_BIAS = {
    "long_bias": "bullish",
    "short_bias": "bearish",
    "no_trade": "none",
    "conditional": "neutral",
    "no_data": "none",
}


# ---------------------------------------------------------------------------
# Signal influence classification — Rule 3: rule-based, not heuristic
# ---------------------------------------------------------------------------


def classify_signal_influence(
    signal_name: str,
    digest: StructureDigest,
    verdict: str,
) -> str:
    """Classify a single signal's influence on the verdict.

    Returns one of: "dominant", "supporting", "conflicting", "neutral", "absent".
    """
    verdict_bias = _VERDICT_TO_BIAS.get(verdict, "none")

    if signal_name == "htf_regime":
        return _classify_htf_regime(digest, verdict, verdict_bias)
    elif signal_name == "bos_mss":
        return _classify_bos_mss(digest, verdict_bias)
    elif signal_name == "liquidity":
        return _classify_liquidity(digest, verdict_bias)
    elif signal_name == "fvg_context":
        return _classify_fvg_context(digest, verdict_bias)
    elif signal_name == "sweep_reclaim":
        return _classify_sweep_reclaim(digest, verdict_bias)
    elif signal_name == "no_trade_flags":
        return _classify_no_trade_flags(digest)
    elif signal_name == "caution_flags":
        return _classify_caution_flags(digest)
    return "absent"


def _classify_htf_regime(digest: StructureDigest, verdict: str, verdict_bias: str) -> str:
    if not digest.structure_available:
        return "absent"
    if digest.structure_gate == "no_data":
        return "absent"
    if digest.structure_gate == "fail":
        return "conflicting"
    if digest.structure_gate == "pass":
        if digest.htf_bias and digest.htf_bias == verdict_bias:
            return "dominant"
        if digest.htf_bias and digest.htf_bias != verdict_bias and verdict_bias != "none":
            return "conflicting"
        return "supporting"
    # mixed gate
    return "neutral"


def _classify_bos_mss(digest: StructureDigest, verdict_bias: str) -> str:
    if not digest.structure_available:
        return "absent"
    if digest.last_bos is None and digest.last_mss is None:
        return "absent"
    bos_aligned = digest.last_bos == verdict_bias if digest.last_bos else False
    mss_aligned = digest.last_mss == verdict_bias if digest.last_mss else False
    if bos_aligned and mss_aligned:
        return "dominant"
    if bos_aligned and not mss_aligned and digest.last_mss is not None:
        return "supporting"
    if bos_aligned:
        return "supporting"
    if digest.last_mss and digest.last_mss != verdict_bias and verdict_bias != "none":
        return "conflicting"
    if digest.last_bos and digest.last_bos != verdict_bias and verdict_bias != "none":
        return "conflicting"
    return "neutral"


def _classify_liquidity(digest: StructureDigest, verdict_bias: str) -> str:
    if not digest.structure_available:
        return "absent"
    if digest.nearest_liquidity_above is None and digest.nearest_liquidity_below is None:
        return "absent"

    if verdict_bias == "bullish":
        # Internal below = supportive; external above close = conflicting
        below_internal = (
            digest.nearest_liquidity_below
            and digest.nearest_liquidity_below.scope == "internal_liquidity"
        )
        above_external_close = "liquidity_above_close" in digest.caution_flags
        if above_external_close:
            return "conflicting"
        if below_internal:
            return "supporting"
        if digest.liquidity_bias == "below_closer":
            return "supporting"
        return "neutral"

    if verdict_bias == "bearish":
        above_internal = (
            digest.nearest_liquidity_above
            and digest.nearest_liquidity_above.scope == "internal_liquidity"
        )
        if above_internal:
            return "supporting"
        if digest.liquidity_bias == "above_closer":
            return "supporting"
        return "neutral"

    return "neutral"


def _classify_fvg_context(digest: StructureDigest, verdict_bias: str) -> str:
    if not digest.structure_available:
        return "absent"
    if digest.active_fvg_context is None or digest.active_fvg_context == "none":
        if digest.active_fvg_count == 0:
            return "absent"
        return "neutral"
    if verdict_bias == "bullish" and digest.active_fvg_context == "discount_bullish":
        return "supporting"
    if verdict_bias == "bearish" and digest.active_fvg_context == "premium_bearish":
        return "supporting"
    if digest.active_fvg_context == "at_fvg":
        return "supporting"
    return "neutral"


def _classify_sweep_reclaim(digest: StructureDigest, verdict_bias: str) -> str:
    if not digest.structure_available:
        return "absent"
    if digest.recent_sweep_signal is None or digest.recent_sweep_signal == "none":
        return "absent"
    if verdict_bias == "bullish" and digest.recent_sweep_signal == "bullish_reclaim":
        return "supporting"
    if verdict_bias == "bearish" and digest.recent_sweep_signal == "bearish_reclaim":
        return "supporting"
    if digest.recent_sweep_signal == "accepted_beyond":
        return "neutral"
    # Reclaim in opposite direction
    if verdict_bias == "bullish" and digest.recent_sweep_signal == "bearish_reclaim":
        return "conflicting"
    if verdict_bias == "bearish" and digest.recent_sweep_signal == "bullish_reclaim":
        return "conflicting"
    return "neutral"


def _classify_no_trade_flags(digest: StructureDigest) -> str:
    if digest.no_trade_flags:
        return "conflicting"
    return "neutral"


def _classify_caution_flags(digest: StructureDigest) -> str:
    if digest.caution_flags:
        return "conflicting"
    return "neutral"


# ---------------------------------------------------------------------------
# Signal value and direction extraction
# ---------------------------------------------------------------------------


def _get_signal_value(signal_name: str, digest: StructureDigest) -> str:
    if signal_name == "htf_regime":
        return digest.htf_bias or "none"
    if signal_name == "bos_mss":
        parts = []
        if digest.last_bos:
            parts.append(f"{digest.last_bos}_bos")
        if digest.last_mss:
            parts.append(f"{digest.last_mss}_mss")
        return ", ".join(parts) if parts else "none"
    if signal_name == "liquidity":
        return digest.liquidity_bias or "none"
    if signal_name == "fvg_context":
        return digest.active_fvg_context or "none"
    if signal_name == "sweep_reclaim":
        return digest.recent_sweep_signal or "none"
    if signal_name == "no_trade_flags":
        return ", ".join(digest.no_trade_flags) if digest.no_trade_flags else "none"
    if signal_name == "caution_flags":
        return ", ".join(digest.caution_flags) if digest.caution_flags else "none"
    return "none"


def _get_signal_direction(signal_name: str, digest: StructureDigest) -> str:
    if signal_name == "htf_regime":
        return digest.htf_bias or "n/a"
    if signal_name == "bos_mss":
        if digest.last_bos:
            return digest.last_bos
        if digest.last_mss:
            return digest.last_mss
        return "n/a"
    if signal_name == "liquidity":
        if digest.liquidity_bias == "below_closer":
            return "bullish"
        if digest.liquidity_bias == "above_closer":
            return "bearish"
        return "neutral"
    if signal_name == "fvg_context":
        if digest.active_fvg_context == "discount_bullish":
            return "bullish"
        if digest.active_fvg_context == "premium_bearish":
            return "bearish"
        return "neutral"
    if signal_name == "sweep_reclaim":
        if digest.recent_sweep_signal == "bullish_reclaim":
            return "bullish"
        if digest.recent_sweep_signal == "bearish_reclaim":
            return "bearish"
        return "n/a"
    return "n/a"


def _get_signal_note(signal_name: str, digest: StructureDigest, influence: str) -> str:
    if signal_name == "htf_regime":
        if influence == "absent":
            return "HTF regime data unavailable."
        tf = digest.htf_source_timeframe or "HTF"
        bias = digest.htf_bias or "unknown"
        gate = digest.structure_gate
        return f"{tf} regime {bias} — HTF gate {gate}."

    if signal_name == "bos_mss":
        if influence == "absent":
            return "No BOS or MSS events recorded."
        parts = []
        if digest.last_bos:
            parts.append(f"{digest.last_bos.capitalize()} BOS confirmed")
        if digest.last_mss:
            parts.append(f"{digest.last_mss} MSS recorded")
        return ". ".join(parts) + "."

    if signal_name == "liquidity":
        if influence == "absent":
            return "No active liquidity levels."
        above = digest.nearest_liquidity_above
        below = digest.nearest_liquidity_below
        parts = []
        if above:
            parts.append(f"Overhead: {above.type} at {above.price:.5f} ({above.scope.replace('_', ' ')})")
        if below:
            parts.append(f"Support: {below.type} at {below.price:.5f} ({below.scope.replace('_', ' ')})")
        return ". ".join(parts) + "." if parts else "Liquidity levels present."

    if signal_name == "fvg_context":
        if influence == "absent":
            return "No active FVG zones."
        ctx = digest.active_fvg_context or "none"
        count = digest.active_fvg_count
        return f"FVG context: {ctx}, {count} active zone(s)."

    if signal_name == "sweep_reclaim":
        if influence == "absent":
            return "No recent sweep/reclaim activity."
        sweep = digest.recent_sweep_signal or "none"
        return f"Sweep/reclaim: {sweep}."

    if signal_name == "no_trade_flags":
        if not digest.no_trade_flags:
            return "No hard no-trade flags active."
        return f"Hard no-trade flags: {', '.join(digest.no_trade_flags)}."

    if signal_name == "caution_flags":
        if not digest.caution_flags:
            return "No caution flags active."
        return f"Caution flags: {', '.join(digest.caution_flags)}."

    return ""


# ---------------------------------------------------------------------------
# Signal influence ranking builder
# ---------------------------------------------------------------------------


def build_signal_ranking(
    digest: StructureDigest,
    verdict: str,
) -> SignalInfluenceRanking:
    """Build the full signal influence ranking from a digest and verdict."""
    signals = []
    for signal_name in sorted(REQUIRED_SIGNALS):
        influence = classify_signal_influence(signal_name, digest, verdict)
        value = _get_signal_value(signal_name, digest)
        direction = _get_signal_direction(signal_name, digest)
        note = _get_signal_note(signal_name, digest, influence)
        signals.append(SignalInfluence(
            signal=signal_name,
            value=value,
            influence=influence,
            direction=direction,
            note=note,
        ))

    # Validate all 7 present
    signal_names = {s.signal for s in signals}
    assert signal_names == REQUIRED_SIGNALS, f"Missing signals: {REQUIRED_SIGNALS - signal_names}"

    # Determine dominant and primary conflict
    dominant_signal = None
    primary_conflict = None
    order = {"dominant": 0, "supporting": 1, "conflicting": 2, "neutral": 3, "absent": 4}
    ranked = sorted(signals, key=lambda s: order.get(s.influence, 5))

    for s in ranked:
        if s.influence == "dominant" and dominant_signal is None:
            dominant_signal = s.signal
        if s.influence == "conflicting" and primary_conflict is None:
            primary_conflict = s.signal

    return SignalInfluenceRanking(
        signals=signals,
        dominant_signal=dominant_signal,
        primary_conflict=primary_conflict,
    )


# ---------------------------------------------------------------------------
# Persona dominance computation — from CONTRACTS.md rules
# ---------------------------------------------------------------------------


def _render_dominance_note(
    direction_driver: str,
    confidence_driver: str,
    effect: str,
    stricter: Optional[str],
) -> str:
    parts = []
    if direction_driver == "both":
        parts.append("Both personas agreed on directional bias.")
    elif direction_driver == "arbiter_override":
        parts.append("Python hard no-trade constraint overrode both personas.")
    elif direction_driver == "technical_structure":
        parts.append("Technical Structure persona drove the directional verdict.")
    else:
        parts.append("Execution/Timing persona drove the directional verdict.")

    if stricter:
        persona_label = "Execution/Timing" if stricter == "execution_timing" else "Technical Structure"
        parts.append(f"{persona_label} was stricter on confidence.")

    if effect == "downgraded":
        parts.append("Arbiter used lower confidence tier.")
    elif effect == "overridden_by_python":
        parts.append("Python override set confidence to none.")
    elif effect == "held":
        parts.append("Confidence was held at persona level.")

    return " ".join(parts)


def compute_persona_dominance(
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision,
) -> PersonaDominance:
    """Compute persona dominance record from persona outputs and arbiter decision."""
    pa = next((p for p in persona_outputs if p.persona_name == "technical_structure"), persona_outputs[0])
    pb = next((p for p in persona_outputs if p.persona_name == "execution_timing"), persona_outputs[-1])

    if arbiter.no_trade_enforced:
        return PersonaDominance(
            direction_driver="arbiter_override",
            confidence_driver="arbiter_rule",
            confidence_effect="overridden_by_python",
            stricter_persona=None,
            python_override_active=True,
            note="Python hard no-trade constraint overrode both personas.",
        )

    # Direction driver
    if pa.directional_bias == pb.directional_bias:
        direction_driver = "both"
    elif pa.is_directional() and not pb.is_directional():
        direction_driver = "technical_structure"
    elif pb.is_directional() and not pa.is_directional():
        direction_driver = "execution_timing"
    else:
        direction_driver = "both"

    # Confidence driver
    conf_order = {"high": 3, "moderate": 2, "low": 1, "none": 0}
    pa_conf = conf_order.get(pa.confidence, 0)
    pb_conf = conf_order.get(pb.confidence, 0)

    if pa_conf < pb_conf:
        stricter = "technical_structure"
        confidence_driver = "technical_structure"
    elif pb_conf < pa_conf:
        stricter = "execution_timing"
        confidence_driver = "execution_timing"
    else:
        stricter = None
        confidence_driver = "arbiter_rule"

    # Confidence effect
    lower = _lower_confidence(pa.confidence, pb.confidence)
    if arbiter.final_confidence != pa.confidence and arbiter.final_confidence != pb.confidence:
        effect = "downgraded"
    elif stricter and arbiter.final_confidence == lower:
        effect = "downgraded"
    else:
        effect = "held"

    note = _render_dominance_note(direction_driver, confidence_driver, effect, stricter)

    return PersonaDominance(
        direction_driver=direction_driver,
        confidence_driver=confidence_driver,
        confidence_effect=effect,
        stricter_persona=stricter,
        python_override_active=False,
        note=note,
    )


# ---------------------------------------------------------------------------
# Confidence provenance computation — Rule 7: step-complete
# ---------------------------------------------------------------------------


def _confidence_rule_for_state(consensus_state: str) -> str:
    rules = {
        "full_alignment": "both personas aligned — hold confidence",
        "directional_alignment_confidence_split": "use lower confidence on split",
        "mixed": "directional conflict — use low",
        "blocked": "persona blocked — no confidence",
        "no_trade": "hard no-trade — none",
        "conditional": "conditional consensus — use low",
    }
    return rules.get(consensus_state, "arbiter rule applied")


def compute_confidence_provenance(
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision,
    digest: StructureDigest,
) -> ConfidenceProvenance:
    """Compute the step-by-step confidence provenance chain."""
    pa = next((p for p in persona_outputs if p.persona_name == "technical_structure"), persona_outputs[0])
    pb = next((p for p in persona_outputs if p.persona_name == "execution_timing"), persona_outputs[-1])

    steps = [
        ConfidenceStep(1, "Technical Structure Analyst", pa.confidence, "persona output"),
        ConfidenceStep(2, "Execution/Timing Analyst", pb.confidence, "persona output"),
        ConfidenceStep(3, "Consensus state", arbiter.consensus_state, "arbiter classification"),
    ]

    rule = _confidence_rule_for_state(arbiter.consensus_state)
    steps.append(ConfidenceStep(4, "Arbiter rule applied", arbiter.final_confidence, rule))

    if digest.has_hard_no_trade():
        steps.append(ConfidenceStep(
            5, "Python override", "none",
            f"hard no-trade flags: {digest.no_trade_flags}",
        ))
        return ConfidenceProvenance(
            steps=steps,
            final_confidence="none",
            python_override=True,
            override_reason=str(digest.no_trade_flags),
        )

    steps.append(ConfidenceStep(5, "Final confidence", arbiter.final_confidence, "no override"))
    return ConfidenceProvenance(
        steps=steps,
        final_confidence=arbiter.final_confidence,
        python_override=False,
        override_reason=None,
    )


# ---------------------------------------------------------------------------
# Causal chain computation
# ---------------------------------------------------------------------------


def compute_causal_chain(
    digest: StructureDigest,
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision,
) -> CausalChain:
    """Build the causal chain of no-trade and caution drivers."""
    no_trade_drivers = []
    caution_drivers = []

    # Digest-level no-trade flags
    for flag in digest.no_trade_flags:
        no_trade_drivers.append(CausalDriver(
            flag=flag,
            source="digest",
            raised_by="pre_filter",
            effect="no-trade — hard block on all verdicts",
        ))

    # Digest-level caution flags
    for flag in digest.caution_flags:
        effect = "caution — did not block verdict"
        # Check if this caution contributed to a confidence downgrade
        pa = next((p for p in persona_outputs if p.persona_name == "technical_structure"), None)
        pb = next((p for p in persona_outputs if p.persona_name == "execution_timing"), None)
        if pa and pb and pa.confidence != pb.confidence:
            effect = "caution — contributed to confidence split"
        caution_drivers.append(CausalDriver(
            flag=flag,
            source="digest",
            raised_by="pre_filter",
            effect=effect,
        ))

    # Persona-level caution flags
    for pv in persona_outputs:
        persona_source = f"persona_{pv.persona_name}"
        for flag in pv.persona_cautions:
            # Skip if already covered by digest
            if flag in [d.flag for d in caution_drivers]:
                continue
            caution_drivers.append(CausalDriver(
                flag=flag,
                source=persona_source,
                raised_by="persona",
                effect=f"caution — raised by {pv.persona_name} persona",
            ))

    has_hard_block = len(no_trade_drivers) > 0

    return CausalChain(
        no_trade_drivers=no_trade_drivers,
        caution_drivers=caution_drivers,
        has_hard_block=has_hard_block,
    )


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def build_explanation(output: MultiAnalystOutput) -> ExplainabilityBlock:
    """Build a complete ExplainabilityBlock from a MultiAnalystOutput.

    This is the primary entry point. Fully deterministic, no LLM calls.
    """
    digest = output.digest
    arbiter = output.arbiter_decision
    verdict = arbiter.final_verdict

    signal_ranking = build_signal_ranking(digest, verdict)
    persona_dominance = compute_persona_dominance(output.persona_outputs, arbiter)
    confidence_provenance = compute_confidence_provenance(
        output.persona_outputs, arbiter, digest,
    )
    causal_chain = compute_causal_chain(digest, output.persona_outputs, arbiter)

    # Validate constraints
    assert len(confidence_provenance.steps) >= 5, (
        f"Confidence provenance must have >= 5 steps, got {len(confidence_provenance.steps)}"
    )
    signal_names = {s.signal for s in signal_ranking.signals}
    assert signal_names == REQUIRED_SIGNALS, (
        f"Signal ranking must contain all 7 signals: {REQUIRED_SIGNALS - signal_names}"
    )

    audit_summary = render_audit_summary(
        digest, output.persona_outputs, arbiter, signal_ranking, causal_chain,
    )

    return ExplainabilityBlock(
        instrument=output.instrument,
        as_of_utc=output.as_of_utc,
        source_verdict=verdict,
        source_confidence=arbiter.final_confidence,
        signal_ranking=signal_ranking,
        persona_dominance=persona_dominance,
        confidence_provenance=confidence_provenance,
        causal_chain=causal_chain,
        audit_summary=audit_summary,
    )


def build_explanation_from_dict(d: dict) -> ExplainabilityBlock:
    """Build an ExplainabilityBlock from a serialized MultiAnalystOutput dict.

    Used for replay from saved files.
    """
    output = _multi_analyst_output_from_dict(d)
    return build_explanation(output)


# ---------------------------------------------------------------------------
# Deserialization helpers for replay
# ---------------------------------------------------------------------------


def _multi_analyst_output_from_dict(d: dict) -> MultiAnalystOutput:
    """Reconstruct a MultiAnalystOutput from its dict representation."""
    from analyst.contracts import (
        AnalystVerdict,
        LiquidityRef,
        ReasoningBlock,
        StructureDigest,
    )

    # Reconstruct digest
    dd = d["digest"]
    liq_above = None
    if dd.get("nearest_liquidity_above"):
        la = dd["nearest_liquidity_above"]
        liq_above = LiquidityRef(
            type=la["type"], price=la["price"], scope=la["scope"], status=la["status"],
        )
    liq_below = None
    if dd.get("nearest_liquidity_below"):
        lb = dd["nearest_liquidity_below"]
        liq_below = LiquidityRef(
            type=lb["type"], price=lb["price"], scope=lb["scope"], status=lb["status"],
        )

    digest = StructureDigest(
        instrument=dd["instrument"],
        as_of_utc=dd["as_of_utc"],
        structure_available=dd["structure_available"],
        structure_gate=dd["structure_gate"],
        gate_reason=dd.get("gate_reason"),
        htf_bias=dd.get("htf_bias"),
        htf_source_timeframe=dd.get("htf_source_timeframe"),
        last_bos=dd.get("last_bos"),
        last_mss=dd.get("last_mss"),
        bos_mss_alignment=dd.get("bos_mss_alignment"),
        nearest_liquidity_above=liq_above,
        nearest_liquidity_below=liq_below,
        liquidity_bias=dd.get("liquidity_bias"),
        active_fvg_context=dd.get("active_fvg_context"),
        active_fvg_count=dd.get("active_fvg_count", 0),
        recent_sweep_signal=dd.get("recent_sweep_signal"),
        structure_supports=dd.get("structure_supports", []),
        structure_conflicts=dd.get("structure_conflicts", []),
        no_trade_flags=dd.get("no_trade_flags", []),
        caution_flags=dd.get("caution_flags", []),
    )

    # Reconstruct persona outputs
    persona_outputs = []
    for pd_dict in d["persona_outputs"]:
        rd = pd_dict.get("reasoning", {})
        reasoning = ReasoningBlock(
            summary=rd.get("summary", ""),
            htf_context=rd.get("htf_context", ""),
            liquidity_context=rd.get("liquidity_context", ""),
            fvg_context=rd.get("fvg_context", ""),
            sweep_context=rd.get("sweep_context", ""),
            verdict_rationale=rd.get("verdict_rationale", ""),
        )
        persona_outputs.append(PersonaVerdict(
            persona_name=pd_dict["persona_name"],
            instrument=pd_dict["instrument"],
            as_of_utc=pd_dict["as_of_utc"],
            verdict=pd_dict["verdict"],
            confidence=pd_dict["confidence"],
            directional_bias=pd_dict.get("directional_bias", "none"),
            structure_gate=pd_dict.get("structure_gate", digest.structure_gate),
            persona_supports=pd_dict.get("persona_supports", []),
            persona_conflicts=pd_dict.get("persona_conflicts", []),
            persona_cautions=pd_dict.get("persona_cautions", []),
            reasoning=reasoning,
        ))

    # Reconstruct arbiter decision
    ad = d["arbiter_decision"]
    arbiter_decision = ArbiterDecision(
        instrument=ad["instrument"],
        as_of_utc=ad["as_of_utc"],
        consensus_state=ad["consensus_state"],
        final_verdict=ad["final_verdict"],
        final_confidence=ad["final_confidence"],
        final_directional_bias=ad["final_directional_bias"],
        no_trade_enforced=ad["no_trade_enforced"],
        personas_agree_direction=ad["personas_agree_direction"],
        personas_agree_confidence=ad["personas_agree_confidence"],
        confidence_spread=ad["confidence_spread"],
        synthesis_notes=ad.get("synthesis_notes", ""),
        winning_rationale_summary=ad.get("winning_rationale_summary", ""),
    )

    # Reconstruct final_verdict
    fv = d["final_verdict"]
    final_verdict = AnalystVerdict(
        instrument=fv["instrument"],
        as_of_utc=fv["as_of_utc"],
        verdict=fv["verdict"],
        confidence=fv["confidence"],
        structure_gate=fv["structure_gate"],
        htf_bias=fv.get("htf_bias"),
        ltf_structure_alignment=fv.get("ltf_structure_alignment", "unknown"),
        active_fvg_context=fv.get("active_fvg_context"),
        recent_sweep_signal=fv.get("recent_sweep_signal"),
        structure_supports=fv.get("structure_supports", []),
        structure_conflicts=fv.get("structure_conflicts", []),
        no_trade_flags=fv.get("no_trade_flags", []),
        caution_flags=fv.get("caution_flags", []),
    )

    return MultiAnalystOutput(
        instrument=d["instrument"],
        as_of_utc=d["as_of_utc"],
        digest=digest,
        persona_outputs=persona_outputs,
        arbiter_decision=arbiter_decision,
        final_verdict=final_verdict,
    )
