"""Market Packet v1 dataclass contracts.

Defines the canonical data structures for the Market Data Officer's output.
These contracts are the interface between the Officer and all downstream agents.
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
