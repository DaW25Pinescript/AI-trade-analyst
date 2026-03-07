"""Phase 3F Arbiter: deterministic conflict resolution + optional LLM synthesis.

Direction and confidence are always pre-computed by Python logic.
The LLM writes synthesis_notes and winning_rationale_summary only.
No LLM call is made when hard no-trade is enforced (RULE 7).
"""

from __future__ import annotations

import json
import re
from typing import Any

from analyst.contracts import StructureDigest
from analyst.multi_contracts import ArbiterDecision, PersonaVerdict
from analyst.analyst import call_llm


# ---------------------------------------------------------------------------
# Confidence ordering
# ---------------------------------------------------------------------------

_CONFIDENCE_ORDER = {"high": 3, "moderate": 2, "low": 1, "none": 0}


def _lower_confidence(a: str, b: str) -> str:
    """Return the lower of two confidence levels."""
    return a if _CONFIDENCE_ORDER[a] <= _CONFIDENCE_ORDER[b] else b


# ---------------------------------------------------------------------------
# Directional bias mapping
# ---------------------------------------------------------------------------

_VERDICT_TO_BIAS = {
    "long_bias": "bullish",
    "short_bias": "bearish",
    "no_trade": "none",
    "conditional": "neutral",
    "no_data": "none",
}


# ---------------------------------------------------------------------------
# Deterministic consensus computation (RULE 8)
# ---------------------------------------------------------------------------


def compute_consensus(
    a: PersonaVerdict,
    b: PersonaVerdict,
    digest: StructureDigest,
) -> tuple[str, str, str]:
    """Compute (consensus_state, final_verdict, final_confidence).

    Evaluated in priority order — first match wins.
    """
    # Priority 1 — hard no-trade overrides everything
    if digest.has_hard_no_trade():
        return "no_trade", "no_trade", "none"

    # Priority 2 — either persona blocked
    if a.is_blocked() or b.is_blocked():
        return "blocked", "no_trade", "none"

    # Priority 3 & 4 — both directional, same direction
    if a.is_directional() and b.is_directional() and a.verdict == b.verdict:
        if a.confidence == b.confidence:
            return "full_alignment", a.verdict, a.confidence
        else:
            lower = _lower_confidence(a.confidence, b.confidence)
            return "directional_alignment_confidence_split", a.verdict, lower

    # Priority 5 — both directional, opposite directions
    if a.is_directional() and b.is_directional():
        return "mixed", "conditional", "low"

    # Priority 6 — one or both conditional (neither blocked)
    # Check if we have directional agreement via directional_bias even when
    # one persona is conditional
    if (a.is_directional() or b.is_directional()):
        # One directional, one conditional — check if biases align
        directional = a if a.is_directional() else b
        other = b if a.is_directional() else a
        if other.directional_bias == directional.directional_bias:
            lower = _lower_confidence(a.confidence, b.confidence)
            return "directional_alignment_confidence_split", directional.verdict, lower

    return "conditional", "conditional", "low"


# ---------------------------------------------------------------------------
# Arbiter system prompt
# ---------------------------------------------------------------------------

ARBITER_SYSTEM_PROMPT = (
    "You are the Arbiter. You do not form opinions about the market.\n"
    "You have been given a pre-computed ArbiterDecision skeleton:\n"
    "- consensus_state, final_verdict, final_confidence, no_trade_enforced are already determined.\n"
    "\n"
    "Your only job is to write:\n"
    "1. synthesis_notes: 2-4 sentences explaining what aligned, what conflicted, and how it resolved.\n"
    "2. winning_rationale_summary: 1-2 sentences stating why the final verdict is the right outcome.\n"
    "\n"
    "Do not change final_verdict. Do not change final_confidence.\n"
    "Do not argue against no_trade_enforced if it is True.\n"
    'Output only valid JSON with exactly two fields: synthesis_notes, winning_rationale_summary.\n'
)


# ---------------------------------------------------------------------------
# Arbiter LLM synthesis
# ---------------------------------------------------------------------------


def _build_arbiter_user_prompt(
    skeleton: dict[str, Any],
    persona_a: PersonaVerdict,
    persona_b: PersonaVerdict,
) -> str:
    """Build the user prompt for the Arbiter LLM call."""
    parts = [
        "--- PRE-COMPUTED ARBITER SKELETON ---",
        json.dumps(skeleton, indent=2),
        "",
        "--- PERSONA A: TECHNICAL STRUCTURE ---",
        json.dumps(persona_a.to_dict(), indent=2),
        "",
        "--- PERSONA B: EXECUTION TIMING ---",
        json.dumps(persona_b.to_dict(), indent=2),
        "",
        "Write synthesis_notes and winning_rationale_summary. Output JSON only.",
    ]
    return "\n".join(parts)


def _parse_arbiter_response(raw: str) -> dict[str, str]:
    """Parse Arbiter LLM JSON response."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_arbiter_decision(decision: ArbiterDecision, digest: StructureDigest) -> None:
    """Post-parse validation of ArbiterDecision.

    Raises ValueError on any constraint violation.
    """
    if digest.has_hard_no_trade():
        if not decision.no_trade_enforced:
            raise ValueError(
                "Arbiter did not enforce hard no-trade condition. "
                f"Flags: {digest.no_trade_flags}"
            )
        if decision.final_verdict != "no_trade":
            raise ValueError(
                f"Arbiter final_verdict must be no_trade when flags present. "
                f"Got: {decision.final_verdict}"
            )
        if decision.final_confidence != "none":
            raise ValueError(
                f"Arbiter final_confidence must be none when no-trade enforced. "
                f"Got: {decision.final_confidence}"
            )


# ---------------------------------------------------------------------------
# Main arbiter function
# ---------------------------------------------------------------------------


def arbitrate(
    persona_outputs: list[PersonaVerdict],
    digest: StructureDigest,
) -> ArbiterDecision:
    """Run the Arbiter: deterministic conflict resolution + optional LLM synthesis.

    Args:
        persona_outputs: List of two PersonaVerdict objects
            [technical_structure, execution_timing].
        digest: The shared StructureDigest.

    Returns:
        ArbiterDecision with all fields populated.
    """
    assert len(persona_outputs) == 2, f"Expected 2 persona outputs, got {len(persona_outputs)}"
    persona_a, persona_b = persona_outputs

    # Step 1: Deterministic consensus computation
    consensus_state, final_verdict, final_confidence = compute_consensus(
        persona_a, persona_b, digest,
    )

    # Step 2: Compute agreement/conflict record
    personas_agree_direction = (
        persona_a.directional_bias == persona_b.directional_bias
    )
    personas_agree_confidence = (
        persona_a.confidence == persona_b.confidence
    )
    if personas_agree_confidence:
        confidence_spread = "aligned"
    else:
        confidence_spread = f"{persona_a.confidence} vs {persona_b.confidence}"

    # Step 3: Derive directional bias from final verdict
    final_directional_bias = _VERDICT_TO_BIAS.get(final_verdict, "none")

    # Step 4: Determine no-trade enforcement
    no_trade_enforced = digest.has_hard_no_trade()

    # Step 5: Synthesis — either deterministic (no-trade) or LLM
    if no_trade_enforced:
        # RULE 7: skip LLM call entirely
        synthesis_notes = (
            f"Hard no-trade condition enforced. "
            f"Flags: {digest.no_trade_flags}. No synthesis performed."
        )
        winning_rationale_summary = (
            "No-trade is the only valid outcome under active hard constraint flags."
        )
    else:
        # Build skeleton for LLM
        skeleton = {
            "consensus_state": consensus_state,
            "final_verdict": final_verdict,
            "final_confidence": final_confidence,
            "no_trade_enforced": no_trade_enforced,
            "personas_agree_direction": personas_agree_direction,
            "personas_agree_confidence": personas_agree_confidence,
            "confidence_spread": confidence_spread,
        }

        arbiter_prompt = _build_arbiter_user_prompt(skeleton, persona_a, persona_b)
        raw = call_llm(ARBITER_SYSTEM_PROMPT, arbiter_prompt)
        llm_data = _parse_arbiter_response(raw)

        synthesis_notes = llm_data.get("synthesis_notes", "")
        winning_rationale_summary = llm_data.get("winning_rationale_summary", "")

    # Step 6: Assemble decision
    decision = ArbiterDecision(
        instrument=digest.instrument,
        as_of_utc=digest.as_of_utc,
        consensus_state=consensus_state,
        final_verdict=final_verdict,
        final_confidence=final_confidence,
        final_directional_bias=final_directional_bias,
        no_trade_enforced=no_trade_enforced,
        personas_agree_direction=personas_agree_direction,
        personas_agree_confidence=personas_agree_confidence,
        confidence_spread=confidence_spread,
        synthesis_notes=synthesis_notes,
        winning_rationale_summary=winning_rationale_summary,
    )

    # Step 7: Validate
    validate_arbiter_decision(decision, digest)

    return decision
