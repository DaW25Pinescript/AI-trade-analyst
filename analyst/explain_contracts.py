"""Phase 3G contracts: ExplainabilityBlock and supporting dataclasses.

All 3G dataclasses live here. No existing file is modified except the single
additive field on MultiAnalystOutput.

Zero LLM calls permitted anywhere in this module.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SignalInfluence:
    """Influence classification for one structure signal."""

    signal: str  # e.g. "htf_regime", "bos_mss", "fvg_context", "sweep_reclaim"
    value: str  # the actual value from the digest
    influence: str  # "dominant" | "supporting" | "conflicting" | "neutral" | "absent"
    direction: str  # "bullish" | "bearish" | "neutral" | "n/a"
    note: str  # one-line human-readable note, template-rendered

    def to_dict(self) -> dict:
        return {
            "signal": self.signal,
            "value": self.value,
            "influence": self.influence,
            "direction": self.direction,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SignalInfluence":
        return cls(
            signal=d["signal"],
            value=d["value"],
            influence=d["influence"],
            direction=d["direction"],
            note=d["note"],
        )


@dataclass
class SignalInfluenceRanking:
    """Ranked list of signal influences. Dominant first, absent last."""

    signals: list[SignalInfluence]
    dominant_signal: Optional[str]  # signal name of top-ranked dominant, or None
    primary_conflict: Optional[str]  # signal name of top-ranked conflicting, or None

    def ranked(self) -> list[SignalInfluence]:
        """Return signals sorted: dominant -> supporting -> conflicting -> neutral -> absent."""
        order = {"dominant": 0, "supporting": 1, "conflicting": 2, "neutral": 3, "absent": 4}
        return sorted(self.signals, key=lambda s: order.get(s.influence, 5))

    def to_dict(self) -> dict:
        return {
            "dominant_signal": self.dominant_signal,
            "primary_conflict": self.primary_conflict,
            "signals": [s.to_dict() for s in self.signals],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SignalInfluenceRanking":
        return cls(
            signals=[SignalInfluence.from_dict(s) for s in d["signals"]],
            dominant_signal=d.get("dominant_signal"),
            primary_conflict=d.get("primary_conflict"),
        )


@dataclass
class PersonaDominance:
    """Records which persona drove or constrained the final decision."""

    direction_driver: str  # "technical_structure" | "execution_timing" | "both" | "arbiter_override"
    confidence_driver: str  # persona whose confidence tier was used, or "arbiter_rule"
    confidence_effect: str  # "held" | "downgraded" | "upgraded" | "overridden_by_python"
    stricter_persona: Optional[str]  # persona with lower confidence, or None if aligned
    python_override_active: bool  # True if hard no-trade flag triggered
    note: str  # template-rendered summary sentence

    def to_dict(self) -> dict:
        return {
            "direction_driver": self.direction_driver,
            "confidence_driver": self.confidence_driver,
            "confidence_effect": self.confidence_effect,
            "stricter_persona": self.stricter_persona,
            "python_override_active": self.python_override_active,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaDominance":
        return cls(
            direction_driver=d["direction_driver"],
            confidence_driver=d["confidence_driver"],
            confidence_effect=d["confidence_effect"],
            stricter_persona=d.get("stricter_persona"),
            python_override_active=d["python_override_active"],
            note=d["note"],
        )


@dataclass
class ConfidenceStep:
    """One step in the confidence provenance chain."""

    step: int
    label: str  # e.g. "Technical Structure Analyst"
    value: str  # confidence value at this step
    rule: str  # rule applied

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "label": self.label,
            "value": self.value,
            "rule": self.rule,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceStep":
        return cls(
            step=d["step"],
            label=d["label"],
            value=d["value"],
            rule=d["rule"],
        )


@dataclass
class ConfidenceProvenance:
    """Step-by-step trace of how final_confidence was determined."""

    steps: list[ConfidenceStep]
    final_confidence: str
    python_override: bool
    override_reason: Optional[str]

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "final_confidence": self.final_confidence,
            "python_override": self.python_override,
            "override_reason": self.override_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceProvenance":
        return cls(
            steps=[ConfidenceStep.from_dict(s) for s in d["steps"]],
            final_confidence=d["final_confidence"],
            python_override=d["python_override"],
            override_reason=d.get("override_reason"),
        )


@dataclass
class CausalDriver:
    """One driver in the causal chain."""

    flag: str
    source: str  # "digest" | "persona_technical" | "persona_execution" | "arbiter"
    raised_by: str  # "pre_filter" | "persona" | "arbiter_rule"
    effect: str  # human-readable effect description

    def to_dict(self) -> dict:
        return {
            "flag": self.flag,
            "source": self.source,
            "raised_by": self.raised_by,
            "effect": self.effect,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CausalDriver":
        return cls(
            flag=d["flag"],
            source=d["source"],
            raised_by=d["raised_by"],
            effect=d["effect"],
        )


@dataclass
class CausalChain:
    """No-trade and caution driver lists."""

    no_trade_drivers: list[CausalDriver]
    caution_drivers: list[CausalDriver]
    has_hard_block: bool

    def to_dict(self) -> dict:
        return {
            "no_trade_drivers": [d.to_dict() for d in self.no_trade_drivers],
            "caution_drivers": [d.to_dict() for d in self.caution_drivers],
            "has_hard_block": self.has_hard_block,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CausalChain":
        return cls(
            no_trade_drivers=[CausalDriver.from_dict(x) for x in d["no_trade_drivers"]],
            caution_drivers=[CausalDriver.from_dict(x) for x in d["caution_drivers"]],
            has_hard_block=d["has_hard_block"],
        )


@dataclass
class ExplainabilityBlock:
    """Top-level explanation container. Fully deterministic.

    Produced by explainability.py from saved MultiAnalystOutput.
    No LLM calls permitted anywhere in this object's construction.
    """

    instrument: str
    as_of_utc: str
    source_verdict: str  # final_verdict echoed for quick reference
    source_confidence: str  # final_confidence echoed

    signal_ranking: SignalInfluenceRanking
    persona_dominance: PersonaDominance
    confidence_provenance: ConfidenceProvenance
    causal_chain: CausalChain

    audit_summary: str  # template-rendered human-readable text (no LLM)

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "source_verdict": self.source_verdict,
            "source_confidence": self.source_confidence,
            "signal_ranking": self.signal_ranking.to_dict(),
            "persona_dominance": self.persona_dominance.to_dict(),
            "confidence_provenance": self.confidence_provenance.to_dict(),
            "causal_chain": self.causal_chain.to_dict(),
            "audit_summary": self.audit_summary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExplainabilityBlock":
        return cls(
            instrument=d["instrument"],
            as_of_utc=d["as_of_utc"],
            source_verdict=d["source_verdict"],
            source_confidence=d["source_confidence"],
            signal_ranking=SignalInfluenceRanking.from_dict(d["signal_ranking"]),
            persona_dominance=PersonaDominance.from_dict(d["persona_dominance"]),
            confidence_provenance=ConfidenceProvenance.from_dict(d["confidence_provenance"]),
            causal_chain=CausalChain.from_dict(d["causal_chain"]),
            audit_summary=d["audit_summary"],
        )
