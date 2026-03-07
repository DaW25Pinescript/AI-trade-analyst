"""Phase 3F contracts: PersonaVerdict, ArbiterDecision, MultiAnalystOutput.

These dataclasses extend the 3E contract layer for multi-analyst consensus.
They live in a separate file — analyst/contracts.py is not modified.
"""

from dataclasses import dataclass, field
from typing import Optional

from analyst.contracts import AnalystVerdict, ReasoningBlock, StructureDigest


@dataclass
class PersonaVerdict:
    """Structured verdict from a single LLM persona.

    Produced by analyst/personas.py. Never produced by Arbiter or pre-filter.
    """

    persona_name: str  # "technical_structure" | "execution_timing"
    instrument: str
    as_of_utc: str

    verdict: str  # "long_bias" | "short_bias" | "no_trade" | "conditional" | "no_data"
    confidence: str  # "high" | "moderate" | "low" | "none"
    directional_bias: str  # "bullish" | "bearish" | "neutral" | "none"

    structure_gate: str  # echoed from digest — must not differ
    persona_supports: list[str]  # what this persona found supportive
    persona_conflicts: list[str]  # what this persona found conflicting
    persona_cautions: list[str]  # persona-specific caution flags

    reasoning: ReasoningBlock  # reuse existing ReasoningBlock schema

    def is_directional(self) -> bool:
        return self.verdict in ("long_bias", "short_bias")

    def is_blocked(self) -> bool:
        return self.verdict in ("no_trade", "no_data")

    def to_dict(self) -> dict:
        return {
            "persona_name": self.persona_name,
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "directional_bias": self.directional_bias,
            "structure_gate": self.structure_gate,
            "persona_supports": list(self.persona_supports),
            "persona_conflicts": list(self.persona_conflicts),
            "persona_cautions": list(self.persona_cautions),
            "reasoning": self.reasoning.to_dict(),
        }


@dataclass
class ArbiterDecision:
    """Final synthesized decision from the Arbiter.

    Directional fields are pre-determined by Python conflict rules.
    LLM writes synthesis_notes and winning_rationale_summary only.
    """

    instrument: str
    as_of_utc: str

    # Pre-determined by Python conflict rules (no LLM involvement)
    consensus_state: str  # see taxonomy in OBJECTIVE.md
    final_verdict: str  # "long_bias" | "short_bias" | "no_trade" | "conditional" | "no_data"
    final_confidence: str  # "high" | "moderate" | "low" | "none"
    final_directional_bias: str  # "bullish" | "bearish" | "neutral" | "none"
    no_trade_enforced: bool  # True if Python hard-constraint triggered override

    # Agreement/conflict record
    personas_agree_direction: bool
    personas_agree_confidence: bool
    confidence_spread: str  # e.g. "high vs moderate" or "aligned"

    # LLM-written fields (synthesis call only)
    synthesis_notes: str
    winning_rationale_summary: str

    def is_actionable(self) -> bool:
        return (
            self.final_verdict in ("long_bias", "short_bias")
            and self.final_confidence in ("high", "moderate")
            and not self.no_trade_enforced
        )

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "consensus_state": self.consensus_state,
            "final_verdict": self.final_verdict,
            "final_confidence": self.final_confidence,
            "final_directional_bias": self.final_directional_bias,
            "no_trade_enforced": self.no_trade_enforced,
            "personas_agree_direction": self.personas_agree_direction,
            "personas_agree_confidence": self.personas_agree_confidence,
            "confidence_spread": self.confidence_spread,
            "synthesis_notes": self.synthesis_notes,
            "winning_rationale_summary": self.winning_rationale_summary,
        }


@dataclass
class MultiAnalystOutput:
    """Top-level container for one full multi-analyst run.

    Preserved entirely for audit and replay.
    """

    instrument: str
    as_of_utc: str

    digest: StructureDigest  # shared input — identical for both personas
    persona_outputs: list[PersonaVerdict]  # ordered: [technical_structure, execution_timing]
    arbiter_decision: ArbiterDecision
    final_verdict: AnalystVerdict  # Arbiter decision re-expressed as AnalystVerdict

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "digest": self.digest.to_dict(),
            "persona_outputs": [pv.to_dict() for pv in self.persona_outputs],
            "arbiter_decision": self.arbiter_decision.to_dict(),
            "final_verdict": self.final_verdict.to_dict(),
        }
