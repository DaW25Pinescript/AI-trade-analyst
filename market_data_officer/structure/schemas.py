"""Typed dataclasses for all Phase 3A structure objects.

Defines: SwingPoint, StructureEvent, LiquidityLevel, SweepEvent,
RegimeSummary, and StructurePacket. These are the canonical contract
for downstream consumers.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SwingPoint:
    """A confirmed swing high or low detected via fixed-pivot confirmation."""

    id: str
    type: str  # "swing_high" | "swing_low"
    price: float
    anchor_time: datetime
    confirm_time: datetime
    timeframe: str
    confirmation_method: str = "pivot_lr"
    left_bars: int = 3
    right_bars: int = 3
    strength: int = 3
    status: str = "confirmed"

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "price": self.price,
            "anchor_time": self.anchor_time.isoformat(),
            "confirm_time": self.confirm_time.isoformat(),
            "timeframe": self.timeframe,
            "confirmation_method": self.confirmation_method,
            "left_bars": self.left_bars,
            "right_bars": self.right_bars,
            "strength": self.strength,
            "status": self.status,
        }


@dataclass
class StructureEvent:
    """A BOS or MSS event confirmed from structural breaks."""

    id: str
    type: str  # "bos_bull" | "bos_bear" | "mss_bull" | "mss_bear"
    time: datetime
    timeframe: str
    reference_swing_id: str
    reference_price: float
    break_close: float
    prior_bias: Optional[str] = None
    status: str = "confirmed"

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "time": self.time.isoformat(),
            "timeframe": self.timeframe,
            "reference_swing_id": self.reference_swing_id,
            "reference_price": self.reference_price,
            "break_close": self.break_close,
            "prior_bias": self.prior_bias,
            "status": self.status,
        }


@dataclass
class LiquidityLevel:
    """A liquidity reference level — prior period high/low or EQH/EQL."""

    id: str
    type: str  # "prior_day_high" | "prior_day_low" | "prior_week_high" | "prior_week_low" | "equal_highs" | "equal_lows"
    price: float
    origin_time: datetime
    timeframe: str
    status: str = "active"
    swept_time: Optional[datetime] = None
    sweep_type: Optional[str] = None
    member_swing_ids: list = field(default_factory=list)
    tolerance_used: Optional[float] = None

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        d = {
            "id": self.id,
            "type": self.type,
            "price": self.price,
            "origin_time": self.origin_time.isoformat(),
            "timeframe": self.timeframe,
            "status": self.status,
            "swept_time": self.swept_time.isoformat() if self.swept_time else None,
            "sweep_type": self.sweep_type,
        }
        if self.member_swing_ids:
            d["member_swing_ids"] = list(self.member_swing_ids)
            d["tolerance_used"] = self.tolerance_used
        return d


@dataclass
class SweepEvent:
    """A confirmed liquidity sweep event."""

    id: str
    type: str  # "sweep_high" | "sweep_low"
    time: datetime
    timeframe: str
    liquidity_level_id: str
    sweep_price: float
    sweep_type: str  # "wick_sweep" | "close_sweep"
    status: str = "confirmed"

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "time": self.time.isoformat(),
            "timeframe": self.timeframe,
            "liquidity_level_id": self.liquidity_level_id,
            "sweep_price": self.sweep_price,
            "sweep_type": self.sweep_type,
            "status": self.status,
        }


@dataclass
class RegimeSummary:
    """Objective structural regime summary derived from confirmed events."""

    bias: str  # "bullish" | "bearish" | "neutral"
    last_bos_direction: Optional[str] = None
    last_mss_direction: Optional[str] = None
    trend_state: str = "unknown"  # "trending" | "ranging" | "unknown"
    structure_quality: str = "unknown"  # "clean" | "choppy" | "unknown"

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "bias": self.bias,
            "last_bos_direction": self.last_bos_direction,
            "last_mss_direction": self.last_mss_direction,
            "trend_state": self.trend_state,
            "structure_quality": self.structure_quality,
        }


@dataclass
class StructurePacket:
    """Top-level structure packet per instrument per timeframe."""

    schema_version: str
    instrument: str
    timeframe: str
    as_of: datetime
    build: dict
    swings: list  # list[SwingPoint]
    events: list  # list[StructureEvent]
    liquidity: list  # list[LiquidityLevel]
    sweep_events: list  # list[SweepEvent]
    regime: RegimeSummary
    diagnostics: dict

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        return {
            "schema_version": self.schema_version,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "as_of": self.as_of.isoformat(),
            "build": self.build,
            "swings": [s.to_dict() for s in self.swings],
            "events": [e.to_dict() for e in self.events],
            "liquidity": [l.to_dict() for l in self.liquidity],
            "sweep_events": [s.to_dict() for s in self.sweep_events],
            "regime": self.regime.to_dict(),
            "diagnostics": self.diagnostics,
        }
