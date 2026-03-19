"""Engine Prompt Builder — builds snapshot-based prompts for Analysis Engine personas.

Spec reference: Sections 6.5, 6.7

Loads v2.0 persona prompts and assembles system/persona/user message sections
from an evidence snapshot. Does NOT route through the legacy prompt loader.
"""

import json
from pathlib import Path
from typing import Literal

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.persona_contract import PersonaContract

# Resolve prompt library path relative to this file
_PROMPT_LIB = Path(__file__).resolve().parent.parent / "prompt_library" / "v2.0" / "personas"

_PERSONA_FILE_MAP: dict[PersonaType, str] = {
    PersonaType.DEFAULT_ANALYST: "default_analyst.txt",
    PersonaType.RISK_OFFICER: "risk_officer.txt",
}


def load_engine_persona_prompt(persona: PersonaType) -> str:
    """Load prompt text from prompt_library/v2.0/personas/."""
    filename = _PERSONA_FILE_MAP.get(persona)
    if filename is None:
        raise ValueError(f"No v2.0 persona prompt file for {persona.value}")
    path = _PROMPT_LIB / filename
    return path.read_text(encoding="utf-8")


_SYSTEM_TEMPLATE = """\
You are an Analysis Engine persona. Your task is to interpret pre-computed structured evidence and produce a single JSON analysis output.

EVIDENCE CITATION RULES:
- Cite evidence ONLY as `lenses.*` dot-paths.
- Every path in `evidence_used` must start with `lenses.`.
- Only cite paths that resolve under lenses listed in `meta.active_lenses`.
- Do NOT cite paths from inactive or failed lenses.
- Referencing inactive, failed, or nonexistent lens paths is a hard violation.

OUTPUT SCHEMA — exactly 8 fields:
{{
  "persona_id": "<your persona id>",
  "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "recommended_action": "BUY" | "SELL" | "NO_TRADE",
  "confidence": <float 0.0–1.0>,
  "reasoning": "<evidence-backed reasoning>",
  "evidence_used": ["lenses.<lens>.<path>", ...],
  "counterpoints": ["<opposing signal or risk>", ...],
  "what_would_change_my_mind": ["<falsification condition>", ...]
}}

CONFIDENCE BANDS:
- weak: 0.0–0.35
- moderate: 0.36–0.65
- strong: 0.66–1.00

DEGRADED CONFIDENCE RULE:
- If run_status is DEGRADED, confidence MUST NOT exceed 0.65.
- On DEGRADED runs, only cite paths from active (non-failed) lenses.
- Mention failed-lens context in counterpoints.

REASONING DISCIPLINE:
1. Identify relevant evidence fields.
2. Interpret directional alignment.
3. Evaluate cross-lens consistency.
4. Consider counterpoints / risk.
5. Conclude with action, bias, and confidence.

Return ONLY the JSON object. No markdown, no wrapper, no additional text."""


def build_engine_prompt(
    snapshot: dict,
    persona_contract: PersonaContract,
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"],
    macro_context: dict | None = None,
) -> dict[str, str]:
    """Return {'system': str, 'persona': str, 'user': str}."""
    # System
    system = _SYSTEM_TEMPLATE

    # Persona
    persona = load_engine_persona_prompt(persona_contract.persona_id)

    # User
    context = snapshot.get("context", {})
    meta = snapshot.get("meta", {})
    derived = snapshot.get("derived", {})

    user_parts: list[str] = []

    # Instrument / timeframe / timestamp block
    user_parts.append("=== INSTRUMENT ===")
    user_parts.append(f"Instrument: {context.get('instrument', 'UNKNOWN')}")
    user_parts.append(f"Timeframe: {context.get('timeframe', 'UNKNOWN')}")
    user_parts.append(f"Timestamp: {context.get('timestamp', 'UNKNOWN')}")
    user_parts.append("")

    # Run status
    user_parts.append(f"=== RUN STATUS ===")
    user_parts.append(f"run_status: {run_status}")
    user_parts.append("")

    # Full serialized evidence snapshot
    user_parts.append("=== EVIDENCE SNAPSHOT ===")
    user_parts.append(json.dumps(snapshot, indent=2, default=str))
    user_parts.append("")

    # Meta section
    user_parts.append("=== META ===")
    user_parts.append(json.dumps(meta, indent=2, default=str))
    user_parts.append("")

    # Derived section
    user_parts.append("=== DERIVED ===")
    user_parts.append(json.dumps(derived, indent=2, default=str))
    user_parts.append("")

    # Optional macro advisory block
    if macro_context is not None:
        user_parts.append("=== MACRO ADVISORY (context only, not authority) ===")
        user_parts.append(json.dumps(macro_context, indent=2, default=str))
        user_parts.append("")

    user = "\n".join(user_parts)

    return {
        "system": system,
        "persona": persona,
        "user": user,
    }
