"""Phase 3F persona definitions and per-persona prompt policies.

Two personas consume the same StructureDigest from different professional
perspectives. They differ by system prompt only — never by data access.
"""

from __future__ import annotations

import json
import re
from typing import Any

from analyst.contracts import ReasoningBlock, StructureDigest
from analyst.enums import VALID_CONFIDENCES, VALID_DIRECTIONAL_BIASES, VALID_VERDICTS
from analyst.multi_contracts import PersonaVerdict
from analyst.analyst import call_llm

# ---------------------------------------------------------------------------
# Persona names
# ---------------------------------------------------------------------------

PERSONA_TECHNICAL_STRUCTURE = "technical_structure"
PERSONA_EXECUTION_TIMING = "execution_timing"
PERSONA_NAMES = (PERSONA_TECHNICAL_STRUCTURE, PERSONA_EXECUTION_TIMING)

# ---------------------------------------------------------------------------
# System prompts — per CONTRACTS.md
# ---------------------------------------------------------------------------

_PERSONA_VERDICT_SCHEMA = (
    "PersonaVerdict JSON schema:\n"
    "{\n"
    '  "persona_name": string,\n'
    '  "instrument": string,\n'
    '  "as_of_utc": string,\n'
    '  "verdict": "long_bias" | "short_bias" | "no_trade" | "conditional" | "no_data",\n'
    '  "confidence": "high" | "moderate" | "low" | "none",\n'
    '  "directional_bias": "bullish" | "bearish" | "neutral" | "none",\n'
    '  "structure_gate": string (must match digest value exactly),\n'
    '  "persona_supports": [string],\n'
    '  "persona_conflicts": [string],\n'
    '  "persona_cautions": [string],\n'
    '  "reasoning": {\n'
    '    "summary": string,\n'
    '    "htf_context": string,\n'
    '    "liquidity_context": string,\n'
    '    "fvg_context": string,\n'
    '    "sweep_context": string,\n'
    '    "verdict_rationale": string\n'
    "  }\n"
    "}\n"
)

SYSTEM_PROMPT_TECHNICAL_STRUCTURE = (
    "You are a disciplined ICT-style technical structure analyst.\n"
    "Your job is to assess whether the structural case for a trade is valid.\n"
    "You do not re-derive structure from raw price data.\n"
    "Your structural knowledge comes exclusively from the structure digest provided.\n"
    "\n"
    "You assess: HTF regime consistency, BOS/MSS direction and quality,\n"
    "liquidity positioning (internal vs external), FVG zone context (discount/premium),\n"
    "and sweep/reclaim outcomes.\n"
    "\n"
    "You do not optimise for timing or execution cleanliness.\n"
    "You answer only: is the structural case for a directional bias sound?\n"
    "\n"
    + _PERSONA_VERDICT_SCHEMA
    + "\n"
    "Output only valid JSON matching PersonaVerdict schema. No preamble. No markdown.\n"
)

SYSTEM_PROMPT_EXECUTION_TIMING = (
    "You are a disciplined ICT-style execution and timing analyst.\n"
    "Your job is to assess whether the current context is a good place and time to act.\n"
    "You do not re-derive structure from raw price data.\n"
    "Your structural knowledge comes exclusively from the structure digest provided.\n"
    "\n"
    "You assess: proximity and quality of nearby liquidity barriers, FVG positioning\n"
    "relative to current price, reclaim vs acceptance outcomes, execution cleanliness,\n"
    "and short-term conflict signals (LTF MSS, partial FVG fills, unresolved sweeps).\n"
    "\n"
    "You do not re-assess HTF regime validity. You take the HTF gate result as given\n"
    "and focus entirely on execution context quality.\n"
    "\n"
    "You answer only: is this a good place and time to act on the structural case?\n"
    "\n"
    + _PERSONA_VERDICT_SCHEMA
    + "\n"
    "Output only valid JSON matching PersonaVerdict schema. No preamble. No markdown.\n"
)

_SYSTEM_PROMPTS = {
    PERSONA_TECHNICAL_STRUCTURE: SYSTEM_PROMPT_TECHNICAL_STRUCTURE,
    PERSONA_EXECUTION_TIMING: SYSTEM_PROMPT_EXECUTION_TIMING,
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_persona_prompt(
    persona_name: str,
    digest: StructureDigest,
) -> dict[str, str]:
    """Build system + user prompt pair for a persona.

    Returns dict with "system" and "user_content" keys.
    Both personas receive identical user_content (same digest).
    """
    if persona_name not in _SYSTEM_PROMPTS:
        raise ValueError(f"Unknown persona: {persona_name}")

    digest_json = json.dumps(digest.to_prompt_dict(), indent=2)

    user_parts = [
        f"Instrument: {digest.instrument}",
        f"As of: {digest.as_of_utc}",
        "",
        "--- STRUCTURE DIGEST ---",
        digest_json,
    ]

    if digest.has_hard_no_trade():
        user_parts.extend([
            "",
            "--- HARD CONSTRAINTS ---",
            f"HARD NO-TRADE FLAGS PRESENT: {digest.no_trade_flags}",
            'You must set verdict = "no_trade" and confidence = "none" '
            'and directional_bias = "none".',
            "Do not override this constraint.",
        ])

    user_parts.extend([
        "",
        "Produce the PersonaVerdict JSON now.",
    ])

    return {
        "system": _SYSTEM_PROMPTS[persona_name],
        "user_content": "\n".join(user_parts),
    }


# ---------------------------------------------------------------------------
# LLM call + parse + validate
# ---------------------------------------------------------------------------


def _parse_persona_response(raw: str) -> dict[str, Any]:
    """Parse LLM persona JSON response."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def _to_persona_verdict(data: dict[str, Any], persona_name: str, digest: StructureDigest) -> PersonaVerdict:
    """Convert parsed dict to PersonaVerdict dataclass."""
    reasoning_data = data.get("reasoning", {})
    reasoning = ReasoningBlock(
        summary=reasoning_data.get("summary", ""),
        htf_context=reasoning_data.get("htf_context", ""),
        liquidity_context=reasoning_data.get("liquidity_context", ""),
        fvg_context=reasoning_data.get("fvg_context", ""),
        sweep_context=reasoning_data.get("sweep_context", ""),
        verdict_rationale=reasoning_data.get("verdict_rationale", ""),
    )

    return PersonaVerdict(
        persona_name=persona_name,
        instrument=data.get("instrument", digest.instrument),
        as_of_utc=data.get("as_of_utc", digest.as_of_utc),
        verdict=data["verdict"],
        confidence=data["confidence"],
        directional_bias=data.get("directional_bias", "none"),
        structure_gate=data.get("structure_gate", digest.structure_gate),
        persona_supports=data.get("persona_supports", []),
        persona_conflicts=data.get("persona_conflicts", []),
        persona_cautions=data.get("persona_cautions", []),
        reasoning=reasoning,
    )


def validate_persona_verdict(verdict: PersonaVerdict, digest: StructureDigest) -> None:
    """Post-parse validation of a PersonaVerdict.

    Raises ValueError on any violation.
    """
    if verdict.verdict not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict value: {verdict.verdict}")

    if verdict.confidence not in VALID_CONFIDENCES:
        raise ValueError(f"Invalid confidence value: {verdict.confidence}")

    if verdict.directional_bias not in VALID_DIRECTIONAL_BIASES:
        raise ValueError(f"Invalid directional_bias value: {verdict.directional_bias}")

    # Structure gate must match digest (RULE 5)
    if verdict.structure_gate != digest.structure_gate:
        raise ValueError(
            f"structure_gate mismatch: verdict={verdict.structure_gate}, "
            f"digest={digest.structure_gate}"
        )

    # Hard no-trade enforcement (RULE 3)
    if digest.has_hard_no_trade():
        if verdict.verdict != "no_trade":
            raise ValueError(
                f"Persona {verdict.persona_name} overrode hard no-trade. "
                f"Flags: {digest.no_trade_flags}"
            )
        if verdict.confidence != "none":
            raise ValueError(
                f"Persona {verdict.persona_name} must have confidence=none "
                f"under hard no-trade. Got: {verdict.confidence}"
            )

    # Lists must be lists
    if not isinstance(verdict.persona_supports, list):
        raise ValueError("persona_supports must be a list")
    if not isinstance(verdict.persona_conflicts, list):
        raise ValueError("persona_conflicts must be a list")
    if not isinstance(verdict.persona_cautions, list):
        raise ValueError("persona_cautions must be a list")


def run_persona(persona_name: str, digest: StructureDigest) -> PersonaVerdict:
    """Run a single persona LLM call and return validated PersonaVerdict."""
    prompt = build_persona_prompt(persona_name, digest)
    raw = call_llm(prompt["system"], prompt["user_content"])
    data = _parse_persona_response(raw)
    verdict = _to_persona_verdict(data, persona_name, digest)
    validate_persona_verdict(verdict, digest)
    return verdict


def run_all_personas(digest: StructureDigest) -> list[PersonaVerdict]:
    """Run both personas on the same digest. Returns [technical_structure, execution_timing]."""
    return [
        run_persona(PERSONA_TECHNICAL_STRUCTURE, digest),
        run_persona(PERSONA_EXECUTION_TIMING, digest),
    ]
