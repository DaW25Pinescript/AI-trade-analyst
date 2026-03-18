"""AnalysisEngineOutput — new 8-field persona output schema.

Spec reference: Section 6.5

This is a NEW model, not a modification of the existing AnalystOutput.
The legacy model has an incompatible ICT-specific schema and remains untouched.
"""

from pydantic import BaseModel, field_validator
from typing import Literal

from ai_analyst.models.persona import PersonaType


class AnalysisEngineOutput(BaseModel):
    persona_id: PersonaType
    bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    recommended_action: Literal["BUY", "SELL", "NO_TRADE"]
    confidence: float  # 0.0–1.0
    reasoning: str  # must reference >= 2 evidence dot-paths
    evidence_used: list[str]  # minimum 2; valid lenses.* dot-paths
    counterpoints: list[str]  # minimum 1 (unless confidence >= 0.80)
    what_would_change_my_mind: list[str]  # minimum 1

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v
