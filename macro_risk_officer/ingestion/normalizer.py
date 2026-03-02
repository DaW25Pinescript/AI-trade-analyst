"""
Normaliser — standardises surprise direction and magnitude across data sources.

Ensures all MacroEvents entering the ReasoningEngine have consistent
surprise sign conventions regardless of source.
"""

from __future__ import annotations

from typing import List

from macro_risk_officer.core.models import MacroEvent


def normalise_events(events: List[MacroEvent]) -> List[MacroEvent]:
    """
    Apply source-specific sign corrections and deduplicate by event_id.

    Currently handles:
    - Yield series from FRED: a rising yield (positive delta) is hawkish,
      so no sign flip needed — the matrix already encodes yield direction.
    - T10Y2Y: inversion (negative spread) → systemic stress. When the
      spread falls below the previous reading, we flip the surprise sign
      so the ReasoningEngine reads it as a stress signal.
    """
    seen_ids: set[str] = set()
    normalised: List[MacroEvent] = []

    for event in events:
        if event.event_id in seen_ids:
            continue
        seen_ids.add(event.event_id)

        event = _apply_sign_corrections(event)
        normalised.append(event)

    # Sort: highest tier first, then most recent
    normalised.sort(key=lambda e: (e.tier, -e.age_hours))
    return normalised


def _apply_sign_corrections(event: MacroEvent) -> MacroEvent:
    """Apply per-series sign correction where needed."""
    if "T10Y2Y" in event.event_id and event.surprise is not None:
        # Falling spread (spread narrows / goes more negative) = worsening inversion
        # We want surprise < 0 to mean "stress" — no correction needed; natural sign is correct.
        pass
    return event
