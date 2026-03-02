"""
Macro context node — fetches a TTL-cached MacroContext from the MRO scheduler.

Positioned immediately after validate_input, before chart analysis begins.
This ensures the Arbiter receives macro context without adding latency to the
chart-analysis fan-out (the TTL cache means most calls return in microseconds).

Design rules (enforced here and in the prompt):
  1. MacroContext is advisory only — never overrides valid price structure.
  2. This node NEVER raises — macro data failure must not block the pipeline.
  3. When macro_context is None, the arbiter receives an explicit unavailability
     notice and bases its verdict on price structure + risk constraints only.
"""
from __future__ import annotations

import logging
from typing import Optional

from .state import GraphState

logger = logging.getLogger(__name__)

# Module-level singleton — shared TTL cache across all pipeline invocations.
# Populated lazily on first call so that MRO is a soft dependency: if the
# macro_risk_officer package is not installed, this node silently yields None.
_scheduler: Optional[object] = None


def _get_scheduler() -> Optional[object]:
    global _scheduler
    if _scheduler is None:
        try:
            from macro_risk_officer.ingestion.scheduler import MacroScheduler
            _scheduler = MacroScheduler()
        except ImportError:
            logger.warning(
                "[MRO] macro_risk_officer package not available — macro context disabled."
            )
    return _scheduler


async def macro_context_node(state: GraphState) -> GraphState:
    """
    Populate state["macro_context"] with a fresh-or-cached MacroContext.

    On any failure (missing API keys, network error, import error) sets
    macro_context to None and logs a warning. The pipeline continues
    with clean price-only analysis.
    """
    instrument: str = state["ground_truth"].instrument
    scheduler = _get_scheduler()

    if scheduler is None:
        state["macro_context"] = None
        return state

    try:
        ctx = scheduler.get_context(instrument=instrument)
        state["macro_context"] = ctx
        if ctx is None:
            logger.warning(
                "[MRO] No macro context available for instrument=%s "
                "(API keys missing or all data sources failed).",
                instrument,
            )
        else:
            logger.info(
                "[MRO] MacroContext loaded: regime=%s vol_bias=%s "
                "conflict=%.2f confidence=%.0f%% horizon=%dd",
                ctx.regime,
                ctx.vol_bias,
                ctx.conflict_score,
                ctx.confidence * 100,
                ctx.time_horizon_days,
            )
    except Exception as exc:
        logger.warning(
            "[MRO] MacroContext fetch raised unexpectedly (%s: %s) — "
            "continuing without macro context.",
            type(exc).__name__,
            exc,
        )
        state["macro_context"] = None

    return state
