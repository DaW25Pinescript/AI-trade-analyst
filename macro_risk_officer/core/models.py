from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class MacroEvent(BaseModel):
    event_id: str
    category: Literal[
        "monetary_policy",
        "inflation",
        "employment",
        "growth",
        "geopolitical",
        "systemic_risk",
    ]
    tier: Literal[1, 2, 3]
    timestamp: datetime
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    description: str
    source: str

    @property
    def surprise(self) -> Optional[float]:
        """Actual minus forecast. Positive = beat, negative = miss."""
        if self.actual is not None and self.forecast is not None:
            return self.actual - self.forecast
        return None

    @property
    def age_hours(self) -> float:
        """Hours elapsed since the event timestamp."""
        now_utc = datetime.now(timezone.utc)
        event_ts = self.timestamp if self.timestamp.tzinfo else self.timestamp.replace(tzinfo=timezone.utc)
        delta = now_utc - event_ts
        return delta.total_seconds() / 3600


class AssetPressure(BaseModel):
    USD: float = 0.0
    SPX: float = 0.0
    NQ: float = 0.0
    T10Y: float = 0.0
    GOLD: float = 0.0
    OIL: float = 0.0
    VIX: float = 0.0

    @field_validator("*", mode="before")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(-1.0, min(1.0, float(v)))


class MacroContext(BaseModel):
    regime: Literal["risk_on", "risk_off", "neutral"]
    vol_bias: Literal["expanding", "contracting", "neutral"]
    asset_pressure: AssetPressure
    conflict_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    time_horizon_days: int = Field(ge=1, le=90)
    explanation: List[str]
    active_event_ids: List[str]

    def arbiter_block(self) -> str:
        """Render the macro section injected into the Arbiter prompt."""
        lines = [
            "=== MACRO RISK CONTEXT (advisory only — do not override valid price structure) ===",
            f"Regime       : {self.regime}",
            f"Vol bias     : {self.vol_bias}",
            f"Conflict     : {self.conflict_score:+.2f}  (negative = macro headwind vs price structure)",
            f"Confidence   : {self.confidence:.0%}",
            f"Horizon      : {self.time_horizon_days}d",
            "",
            "Asset pressure (–1.0 bearish → +1.0 bullish):",
        ]
        for asset, val in self.asset_pressure.model_dump().items():
            if val != 0.0:
                lines.append(f"  {asset:<6}: {val:+.2f}")
        lines.append("")
        lines.append("Explanation:")
        for note in self.explanation:
            lines.append(f"  • {note}")
        lines.append(
            "\nARBITER RULE: macro context is contextual evidence only. "
            "Valid price structure takes precedence."
        )
        return "\n".join(lines)
