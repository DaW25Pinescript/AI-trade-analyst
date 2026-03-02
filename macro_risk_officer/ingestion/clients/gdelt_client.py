"""
GDELT geopolitical event client.

GDELT provides structured event data for geopolitical developments.
No API key required — public dataset.

In MRO-P1 this client is a stub. Full implementation in MRO-P2.
GDELT GKG (Global Knowledge Graph) requires significant parsing;
defer until core macro events are validated first.
"""

from __future__ import annotations

from typing import List

from macro_risk_officer.core.models import MacroEvent


class GdeltClient:
    """Stub — GDELT integration deferred to MRO-P2."""

    def fetch_geopolitical_events(self, lookback_days: int = 3) -> List[MacroEvent]:
        # TODO (MRO-P2): Implement GDELT GKG query
        # Endpoint: https://api.gdeltproject.org/api/v2/doc/doc
        # Parse tonality + actor codes to derive escalation/de-escalation
        return []
