"""Phase 3E contracts: StructureDigest, AnalystVerdict, ReasoningBlock, AnalystOutput.

These dataclasses define the canonical interface between the pre-filter,
LLM analyst, and downstream consumers. StructureDigest is produced by Python
only. AnalystVerdict and ReasoningBlock are produced by the LLM and parsed
back into these structures.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class LiquidityRef:
    """Reference to a nearby liquidity level."""

    type: str  # e.g. "prior_day_high"
    price: float
    scope: str  # "external_liquidity" | "internal_liquidity" | "unclassified"
    status: str  # "active" | "swept"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StructureDigest:
    """Deterministic, compact summary of structure block state.

    Produced by pre_filter.py. Consumed by prompt_builder.py and analyst.py.
    Never produced by the LLM.
    """

    instrument: str
    as_of_utc: str
    structure_available: bool

    # Gate
    structure_gate: str  # "pass" | "fail" | "no_data" | "mixed"
    gate_reason: Optional[str] = None

    # Regime
    htf_bias: Optional[str] = None  # "bullish" | "bearish" | "neutral" | None
    htf_source_timeframe: Optional[str] = None
    last_bos: Optional[str] = None  # "bullish" | "bearish" | None
    last_mss: Optional[str] = None  # "bullish" | "bearish" | None
    bos_mss_alignment: Optional[str] = None  # "aligned" | "conflicted" | "incomplete"

    # Liquidity
    nearest_liquidity_above: Optional[LiquidityRef] = None
    nearest_liquidity_below: Optional[LiquidityRef] = None
    liquidity_bias: Optional[str] = None  # "above_closer" | "below_closer" | "balanced"

    # FVG
    active_fvg_context: Optional[str] = None  # "discount_bullish" | "premium_bearish" | "at_fvg" | "none"
    active_fvg_count: int = 0

    # Sweep/reclaim
    recent_sweep_signal: Optional[str] = None  # "bullish_reclaim" | "bearish_reclaim" | "accepted_beyond" | "none"

    # Signal lists
    structure_supports: list[str] = field(default_factory=list)
    structure_conflicts: list[str] = field(default_factory=list)

    # Flags
    no_trade_flags: list[str] = field(default_factory=list)
    caution_flags: list[str] = field(default_factory=list)

    def has_hard_no_trade(self) -> bool:
        return len(self.no_trade_flags) > 0

    def to_prompt_dict(self) -> dict:
        """Compact dict for LLM prompt injection. Excludes raw packet data."""
        d: dict = {
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "structure_available": self.structure_available,
            "structure_gate": self.structure_gate,
            "gate_reason": self.gate_reason,
            "htf_bias": self.htf_bias,
            "htf_source_timeframe": self.htf_source_timeframe,
            "last_bos": self.last_bos,
            "last_mss": self.last_mss,
            "bos_mss_alignment": self.bos_mss_alignment,
            "liquidity_bias": self.liquidity_bias,
            "active_fvg_context": self.active_fvg_context,
            "active_fvg_count": self.active_fvg_count,
            "recent_sweep_signal": self.recent_sweep_signal,
            "structure_supports": list(self.structure_supports),
            "structure_conflicts": list(self.structure_conflicts),
            "no_trade_flags": list(self.no_trade_flags),
            "caution_flags": list(self.caution_flags),
        }
        if self.nearest_liquidity_above:
            d["nearest_liquidity_above"] = self.nearest_liquidity_above.to_dict()
        else:
            d["nearest_liquidity_above"] = None
        if self.nearest_liquidity_below:
            d["nearest_liquidity_below"] = self.nearest_liquidity_below.to_dict()
        else:
            d["nearest_liquidity_below"] = None
        return d

    def to_dict(self) -> dict:
        """Full serialization for audit/replay."""
        d = self.to_prompt_dict()
        return d


@dataclass
class AnalystVerdict:
    """Structured machine-readable verdict. Produced by LLM, parsed by analyst.py."""

    instrument: str
    as_of_utc: str
    verdict: str  # "long_bias" | "short_bias" | "no_trade" | "conditional" | "no_data"
    confidence: str  # "high" | "moderate" | "low" | "none"
    structure_gate: str  # echoed from digest
    htf_bias: Optional[str]
    ltf_structure_alignment: str  # "aligned" | "mixed" | "conflicted" | "unknown"
    active_fvg_context: Optional[str]
    recent_sweep_signal: Optional[str]
    structure_supports: list[str] = field(default_factory=list)
    structure_conflicts: list[str] = field(default_factory=list)
    no_trade_flags: list[str] = field(default_factory=list)
    caution_flags: list[str] = field(default_factory=list)

    def is_actionable(self) -> bool:
        """True if verdict is long_bias or short_bias with at least moderate confidence."""
        return (
            self.verdict in ("long_bias", "short_bias")
            and self.confidence in ("high", "moderate")
            and not self.no_trade_flags
        )

    def to_dict(self) -> dict:
        return {
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "structure_gate": self.structure_gate,
            "htf_bias": self.htf_bias,
            "ltf_structure_alignment": self.ltf_structure_alignment,
            "active_fvg_context": self.active_fvg_context,
            "recent_sweep_signal": self.recent_sweep_signal,
            "structure_supports": list(self.structure_supports),
            "structure_conflicts": list(self.structure_conflicts),
            "no_trade_flags": list(self.no_trade_flags),
            "caution_flags": list(self.caution_flags),
        }


@dataclass
class ReasoningBlock:
    """Human-readable explanation of how structure influenced the verdict."""

    summary: str
    htf_context: str
    liquidity_context: str
    fvg_context: str
    sweep_context: str
    verdict_rationale: str

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "htf_context": self.htf_context,
            "liquidity_context": self.liquidity_context,
            "fvg_context": self.fvg_context,
            "sweep_context": self.sweep_context,
            "verdict_rationale": self.verdict_rationale,
        }


@dataclass
class AnalystOutput:
    """Top-level container: verdict + reasoning + digest for audit."""

    verdict: AnalystVerdict
    reasoning: ReasoningBlock
    digest: StructureDigest

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.to_dict(),
            "reasoning": self.reasoning.to_dict(),
            "digest": self.digest.to_dict(),
        }
