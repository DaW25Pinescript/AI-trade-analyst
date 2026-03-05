"""
Macro context node — fetches a MacroContext for the Arbiter prompt.

Priority order (Phase 2a — live feeder bridge):
  1. If a live feeder MacroContext is injected via GraphState, use it.
  2. Otherwise fall back to the TTL-cached MacroScheduler.

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

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from .state import GraphState

logger = logging.getLogger(__name__)

# Module-level singleton — shared TTL cache across all pipeline invocations.
# Populated lazily on first call so that MRO is a soft dependency: if the
# macro_risk_officer package is not installed, this node silently yields None.
_scheduler: Optional[object] = None

# Feeder staleness threshold (matches the API default; overridden via env).
_FEEDER_STALE_SECONDS: int = int(os.environ.get("FEEDER_STALE_SECONDS", "3600"))


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


def _try_feeder_context(state: GraphState) -> Optional[object]:
    """
    Phase 2a: check if a live feeder MacroContext is available and fresh.

    The feeder context is injected into GraphState by the /analyse endpoint
    when the POST /feeder/ingest endpoint has been called previously.
    For CLI / test usage where no feeder state exists, this returns None
    and the scheduler fallback is used.

    Returns a MacroContext if available and not stale, otherwise None.
    """
    feeder_ctx = state.get("_feeder_context")
    feeder_ts = state.get("_feeder_ingested_at")

    if feeder_ctx is None or feeder_ts is None:
        return None

    # Check staleness
    age = (datetime.now(timezone.utc) - feeder_ts).total_seconds()
    if age > _FEEDER_STALE_SECONDS:
        logger.info(
            "[MRO] Feeder context is stale (%.0fs > %ds) — falling back to scheduler.",
            age,
            _FEEDER_STALE_SECONDS,
        )
        return None

    logger.info(
        "[MRO] Using live feeder context (age=%.0fs): regime=%s vol_bias=%s "
        "confidence=%.0f%%",
        age,
        feeder_ctx.regime,
        feeder_ctx.vol_bias,
        feeder_ctx.confidence * 100,
    )
    return feeder_ctx


async def macro_context_node(state: GraphState) -> dict:
    """
    Populate state["macro_context"] with a MacroContext.

    Phase 2a priority:
      1. Live feeder context (from POST /feeder/ingest) if fresh.
      2. TTL-cached MacroScheduler as fallback.

    On any failure (missing API keys, network error, import error) sets
    macro_context to None and logs a warning. The pipeline continues
    with clean price-only analysis.

    Phase 4: returns a partial state dict (only "macro_context") so this node
    can run in parallel with the chart setup branch without merge conflicts.
    """
    # Phase 2a: prefer live feeder context
    feeder_ctx = _try_feeder_context(state)
    if feeder_ctx is not None:
        return {"macro_context": feeder_ctx}

    # Fallback: TTL-cached scheduler
    instrument: str = state["ground_truth"].instrument
    scheduler = _get_scheduler()

    if scheduler is None:
        return {"macro_context": None}

    try:
        ctx = await asyncio.to_thread(scheduler.get_context, instrument=instrument)
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
        return {"macro_context": ctx}
    except Exception as exc:
        logger.warning(
            "[MRO] MacroContext fetch raised unexpectedly (%s: %s) — "
            "continuing without macro context.",
            type(exc).__name__,
            exc,
        )
        return {"macro_context": None}
