from pydantic import BaseModel, model_validator
from typing import Optional, Literal


class KeyLevels(BaseModel):
    premium: list[str]
    discount: list[str]
    invalid_below: Optional[float] = None
    invalid_above: Optional[float] = None


class AnalystOutput(BaseModel):
    htf_bias: Literal["bullish", "bearish", "neutral", "ranging"]
    structure_state: Literal["continuation", "reversal", "range", "undefined"]
    key_levels: KeyLevels
    setup_valid: bool
    setup_type: Optional[str] = None
    entry_model: Optional[str] = None
    invalidation: Optional[str] = None
    disqualifiers: list[str]
    sweep_status: Optional[str] = None
    fvg_zones: Optional[list[str]] = None
    displacement_quality: Optional[Literal["strong", "medium", "weak", "none"]] = None
    confidence: float
    rr_estimate: Optional[float] = None
    notes: str
    recommended_action: Literal["WAIT", "LONG", "SHORT", "NO_TRADE"]

    @model_validator(mode="after")
    def enforce_no_trade_rule(self) -> "AnalystOutput":
        """
        Hard rule (enforced in code, not just in prompts):
        If setup_valid == false OR confidence < 0.45 OR disqualifiers list is
        non-empty then recommended_action MUST be NO_TRADE. No exceptions.
        """
        reasons: list[str] = []
        if not self.setup_valid:
            reasons.append("setup_valid=false")
        if self.confidence < 0.45:
            reasons.append(f"confidence={self.confidence:.2f} < 0.45")
        if self.disqualifiers:
            reasons.append("disqualifiers list is non-empty")

        if reasons and self.recommended_action != "NO_TRADE":
            raise ValueError(
                f"recommended_action must be 'NO_TRADE' when: {', '.join(reasons)}. "
                f"Got '{self.recommended_action}' instead."
            )
        return self


class OverlayDeltaReport(BaseModel):
    """
    Structured delta report comparing the 15M ICT overlay interpretation
    against the clean-price baseline produced in Phase 1.

    This report is ONLY produced when the 15M overlay screenshot is provided.
    Silent merging of clean and indicator interpretations is forbidden.
    All four fields are required; empty lists are valid but omitted fields are not.

    Evidence hierarchy:
    - Clean price is ground truth (primary authority).
    - The overlay is an interpretive aid (secondary authority).
    - Contradictions must surface here, never be resolved silently.
    """
    confirms: list[str]               # overlay confirms the clean-price reading
    refines: list[str]                # overlay refines without contradiction
    contradicts: list[str]            # overlay contradicts clean-price reading
    indicator_only_claims: list[str]  # constructs visible only in overlay, not price
