"""Market Packet v1 and v2 dataclass contracts.

Defines the canonical data structures for the Market Data Officer's output.
These contracts are the interface between the Officer and all downstream agents.
Phase 3D adds StructureBlock and MarketPacketV2.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CoreFeatures:
    """Core feature set computed from 1h bars."""

    atr_14: float
    volatility_regime: str
    momentum: float
    ma_50: float
    ma_200: float
    swing_high: float
    swing_low: float
    rolling_range: float
    session_context: str


@dataclass
class FeatureBlock:
    """Feature container with core (Phase 2) and stub slots (Phase 3/4)."""

    core: CoreFeatures
    structure: None = None    # Phase 3
    imbalance: None = None    # Phase 4
    compression: None = None  # Phase 4


@dataclass
class StateSummary:
    """Compact derivative summary of market state."""

    trend_1h: str
    trend_4h: str
    trend_1d: str
    volatility_regime: str
    momentum_state: str
    session_context: str
    data_quality: str


@dataclass
class QualityBlock:
    """Read-side quality assessment of the hot package data."""

    manifest_valid: bool
    all_timeframes_present: bool
    staleness_minutes: int
    stale: bool
    partial: bool
    flags: list[str] = field(default_factory=list)


@dataclass
class MarketPacket:
    """The canonical Market Packet v1 — single consistent market view for all agents."""

    instrument: str
    as_of_utc: str
    source: dict
    timeframes: dict
    features: FeatureBlock
    state_summary: StateSummary
    quality: QualityBlock

    def to_dict(self) -> dict:
        """Serialize to the canonical Market Packet v1 JSON structure."""
        return {
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "source": self.source,
            "timeframes": self.timeframes,
            "features": {
                "core": asdict(self.features.core),
                "structure": self.features.structure,
                "imbalance": self.features.imbalance,
                "compression": self.features.compression,
            },
            "state_summary": asdict(self.state_summary),
            "quality": asdict(self.quality),
        }

    def is_trusted(self) -> bool:
        """Returns True only if packet is validated and not stale or partial."""
        return (
            not self.quality.stale
            and not self.quality.partial
            and self.quality.manifest_valid
            and self.state_summary.data_quality == "validated"
        )


# --- Phase 3D additions ---


@dataclass
class StructureRegime:
    """Regime summary from the highest-confidence structure timeframe."""

    bias: str
    last_bos_direction: Optional[str]
    last_mss_direction: Optional[str]
    trend_state: str
    structure_quality: str
    source_timeframe: str


@dataclass
class StructureRecentEvent:
    """A recent BOS/MSS event from the structure engine."""

    type: str
    time: str
    timeframe: str
    reference_price: float


@dataclass
class LiquidityNearest:
    """Nearest liquidity level above or below current price."""

    type: str
    price: float
    scope: str
    status: str


@dataclass
class LiquidityTimeframeSummary:
    """Per-timeframe liquidity summary."""

    active_count: int
    nearest_above: Optional[LiquidityNearest]
    nearest_below: Optional[LiquidityNearest]


@dataclass
class ActiveFVGZone:
    """An active (open or partially_filled) FVG zone."""

    id: str
    fvg_type: str
    zone_high: float
    zone_low: float
    zone_size: float
    status: str
    timeframe: str
    origin_time: str


@dataclass
class StructureBlock:
    """Structure state block for the Market Packet v2."""

    available: bool
    source_engine_version: Optional[str] = None
    as_of: Optional[str] = None
    regime: Optional[StructureRegime] = None
    recent_events: Optional[list[StructureRecentEvent]] = None
    liquidity: Optional[dict[str, LiquidityTimeframeSummary]] = None
    active_fvg_zones: Optional[list[ActiveFVGZone]] = None

    @classmethod
    def unavailable(cls) -> "StructureBlock":
        """Factory for the unavailable state."""
        return cls(available=False)

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dictionary."""
        if not self.available:
            return {
                "available": False,
                "source_engine_version": None,
                "as_of": None,
                "regime": None,
                "recent_events": None,
                "liquidity": None,
                "active_fvg_zones": None,
            }
        return {
            "available": True,
            "source_engine_version": self.source_engine_version,
            "as_of": self.as_of,
            "regime": asdict(self.regime) if self.regime else None,
            "recent_events": (
                [asdict(e) for e in self.recent_events]
                if self.recent_events is not None
                else None
            ),
            "liquidity": (
                {
                    tf: {
                        "active_count": summary.active_count,
                        "nearest_above": (
                            asdict(summary.nearest_above)
                            if summary.nearest_above
                            else None
                        ),
                        "nearest_below": (
                            asdict(summary.nearest_below)
                            if summary.nearest_below
                            else None
                        ),
                    }
                    for tf, summary in self.liquidity.items()
                }
                if self.liquidity is not None
                else None
            ),
            "active_fvg_zones": (
                [asdict(z) for z in self.active_fvg_zones]
                if self.active_fvg_zones is not None
                else None
            ),
        }


@dataclass
class MarketPacketV2:
    """Market Packet v2 — extends v1 with structure block."""

    instrument: str
    as_of_utc: str
    source: dict
    timeframes: dict
    features: FeatureBlock
    state_summary: StateSummary
    quality: QualityBlock
    structure: StructureBlock

    def to_dict(self) -> dict:
        """Serialize to Market Packet v2 JSON structure."""
        return {
            "schema_version": "market_packet_v2",
            "instrument": self.instrument,
            "as_of_utc": self.as_of_utc,
            "source": self.source,
            "timeframes": self.timeframes,
            "features": {
                "core": asdict(self.features.core),
                "structure": self.features.structure,
                "imbalance": self.features.imbalance,
                "compression": self.features.compression,
            },
            "state_summary": asdict(self.state_summary),
            "quality": asdict(self.quality),
            "structure": self.structure.to_dict(),
        }

    def is_trusted(self) -> bool:
        """Returns True only if packet is validated and not stale or partial."""
        return (
            not self.quality.stale
            and not self.quality.partial
            and self.quality.manifest_valid
            and self.state_summary.data_quality == "validated"
        )

    def has_structure(self) -> bool:
        """True if structure block is available AND at least one sub-field is non-null."""
        return (
            self.structure.available
            and any([
                self.structure.regime is not None,
                self.structure.recent_events is not None,
                self.structure.liquidity is not None,
                self.structure.active_fvg_zones is not None,
            ])
        )
