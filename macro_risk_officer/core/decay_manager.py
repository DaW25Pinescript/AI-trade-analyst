"""
Temporal decay for macro events.

Tier 1 events (Fed, NFP, CPI) have longer relevance windows.
Tier 3 events decay quickly.

Decay is exponential: factor = exp(-age_hours / half_life_hours)
where half_life_hours is tier-dependent.
"""

from __future__ import annotations

import math

from macro_risk_officer.core.models import MacroEvent


# Hours at which a tier's relevance halves
_HALF_LIFE_HOURS: dict[int, float] = {
    1: 168.0,   # Tier 1: 7-day half-life (Fed, NFP, CPI)
    2: 72.0,    # Tier 2: 3-day half-life (retail sales, ISM, PMI)
    3: 24.0,    # Tier 3: 1-day half-life (minor releases)
}

# Minimum decay floor — even old events carry some residual weight
_MIN_DECAY: float = 0.05


class DecayManager:
    def get_decay_factor(self, event: MacroEvent) -> float:
        """Return a decay multiplier in [_MIN_DECAY, 1.0] for the event."""
        half_life = _HALF_LIFE_HOURS.get(event.tier, 72.0)
        factor = math.exp(-event.age_hours / half_life)
        return max(_MIN_DECAY, min(1.0, factor))
