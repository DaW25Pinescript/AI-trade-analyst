"""
Temporal decay for macro events.

Tier 1 events (Fed, NFP, CPI) have longer relevance windows.
Tier 3 events decay quickly.

Decay is exponential: factor = exp(-age_hours / half_life_hours)
where half_life_hours is tier-dependent.

Half-lives and the minimum decay floor are loaded from
config/thresholds.yaml at instantiation time (MRO-P3).
"""

from __future__ import annotations

import math
from typing import Dict

from macro_risk_officer.config.loader import load_thresholds
from macro_risk_officer.core.models import MacroEvent


class DecayManager:
    def __init__(self) -> None:
        decay_cfg = load_thresholds()["decay"]
        self._half_life: Dict[int, float] = {
            1: decay_cfg["tier_1_half_life_hours"],
            2: decay_cfg["tier_2_half_life_hours"],
            3: decay_cfg["tier_3_half_life_hours"],
        }
        self._min_floor: float = decay_cfg["min_floor"]

    def get_decay_factor(self, event: MacroEvent) -> float:
        """Return a decay multiplier in [min_floor, 1.0] for the event."""
        half_life = self._half_life.get(event.tier, 72.0)
        factor = math.exp(-event.age_hours / half_life)
        return max(self._min_floor, min(1.0, factor))
