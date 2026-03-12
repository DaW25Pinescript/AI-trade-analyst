"""
Feeder ingest — local MRO entry point for Modal feeder payloads.

Accepts the versioned feeder contract JSON produced by modal_macro_worker,
validates the contract_version, maps feeder events to MacroEvent objects,
and hands them to the existing normaliser + ReasoningEngine pipeline.

Integration path:
    feeder JSON
      → ingest_feeder_payload()
        → _feeder_event_to_macro_event()  [field mapping]
        → normalise_events()              [dedup + sign correction]
        → ReasoningEngine.generate_context()
        → MacroContext

Fallback: the existing MacroScheduler.get_context() flow is unchanged and
continues to work independently of this module.  If the feeder is unavailable,
callers fall back to MacroScheduler as before.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from macro_risk_officer.config.loader import load_weights
from macro_risk_officer.core.models import MacroEvent, MacroContext
from macro_risk_officer.core.reasoning_engine import ReasoningEngine
from macro_risk_officer.ingestion.normalizer import normalise_events

logger = logging.getLogger(__name__)

SUPPORTED_CONTRACT_VERSION = "1.0.0"

# Valid MacroEvent categories (mirrors the Literal in models.py)
_VALID_CATEGORIES = frozenset(
    {
        "monetary_policy",
        "inflation",
        "employment",
        "growth",
        "geopolitical",
        "systemic_risk",
    }
)

_IMPORTANCE_TO_TIER: dict[str, int] = {
    "high": 1,
    "medium": 2,
    "low": 3,
}


# ─── Field mapping ─────────────────────────────────────────────────────────────


def _importance_to_tier(importance: str) -> int:
    """Map feeder importance string to MRO tier integer."""
    return _IMPORTANCE_TO_TIER.get(importance, 3)


def _feeder_event_to_macro_event(event_dict: dict) -> MacroEvent:
    """
    Map a single feeder contract event dict to a MacroEvent.

    Field mapping:
        feeder.title        → MacroEvent.description
        feeder.importance   → MacroEvent.tier  ("high"→1, "medium"→2, "low"→3)
        feeder.timestamp    → MacroEvent.timestamp  (ISO string → datetime)
        All other fields (event_id, source, category, actual, forecast,
        previous) map directly by name.

    Feeder-only fields (region, surprise_direction, pressure_direction,
    raw_reference, tags) are not carried into MacroEvent — they are
    informational contract fields only.
    """
    category = event_dict.get("category", "growth")
    if category not in _VALID_CATEGORIES:
        raise ValueError(
            f"Unknown feeder event category '{category}'. "
            f"Valid values: {sorted(_VALID_CATEGORIES)}"
        )

    timestamp_raw = event_dict.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(timestamp_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        ts = datetime.now(timezone.utc)

    return MacroEvent(
        event_id=event_dict["event_id"],
        category=category,
        tier=_importance_to_tier(event_dict.get("importance", "low")),
        timestamp=ts,
        actual=event_dict.get("actual"),
        forecast=event_dict.get("forecast"),
        previous=event_dict.get("previous"),
        description=event_dict.get("title", event_dict.get("event_id", "")),
        source=event_dict.get("source", "feeder"),
    )


# ─── Public API ────────────────────────────────────────────────────────────────


def events_from_feeder(payload: dict) -> List[MacroEvent]:
    """
    Validate the feeder payload contract_version and return a normalised list
    of MacroEvent objects.

    Raises ValueError if contract_version is not SUPPORTED_CONTRACT_VERSION.
    Individual malformed events are skipped (with no exception raised) to
    preserve robustness when ingesting partial payloads.
    """
    version = payload.get("contract_version")
    if version != SUPPORTED_CONTRACT_VERSION:
        raise ValueError(
            f"Unsupported feeder contract_version '{version}'. "
            f"Expected '{SUPPORTED_CONTRACT_VERSION}'."
        )

    raw_events = payload.get("events", [])
    total = len(raw_events)
    raw: List[MacroEvent] = []
    skipped_ids: list[str] = []
    for ev in raw_events:
        try:
            raw.append(_feeder_event_to_macro_event(ev))
        except (KeyError, ValueError) as exc:
            eid = ev.get("event_id", "<unknown>") if isinstance(ev, dict) else "<malformed>"
            skipped_ids.append(eid)
            logger.warning(
                json.dumps({
                    "event": "feeder.event.mapping_failed",
                    "top_level_category": "request_validation_failure",
                    "event_code": "feeder_event_mapping_failure",
                    "event_id": eid,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            )
            continue

    mapped = len(raw)
    if skipped_ids:
        logger.info(
            json.dumps({
                "event": "feeder.ingest.mapping_summary",
                "top_level_category": "request_validation_failure",
                "event_code": "feeder_event_mapping_failure",
                "total_events": total,
                "mapped": mapped,
                "skipped": len(skipped_ids),
                "skipped_ids": skipped_ids[:20],
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        )
    else:
        logger.info(
            json.dumps({
                "event": "feeder.ingest.mapping_complete",
                "top_level_category": "runtime_execution_failure",
                "event_code": "feeder_ingest_success",
                "total_events": total,
                "mapped": mapped,
                "skipped": 0,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        )

    return normalise_events(raw)


def ingest_feeder_payload(
    payload: dict,
    instrument: str = "XAUUSD",
) -> MacroContext:
    """
    Accept a feeder contract payload and return a MacroContext.

    This is the canonical integration point:
        feeder JSON → MacroEvent mapping → normalise_events → ReasoningEngine

    The existing MacroScheduler.get_context() path is untouched; callers
    can use either path independently.

    Args:
        payload:    The full feeder contract dict (contract_version checked).
        instrument: Instrument symbol for conflict_score computation.
                    Defaults to "XAUUSD".

    Returns:
        MacroContext — same object the Arbiter prompt builder consumes.

    Raises:
        ValueError if contract_version is not supported.
    """
    logger.info(
        json.dumps({
            "event": "feeder.ingest.received",
            "top_level_category": "runtime_execution_failure",
            "event_code": "feeder_ingest_received",
            "contract_version": payload.get("contract_version"),
            "instrument": instrument,
            "event_count": len(payload.get("events", [])),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    )

    events = events_from_feeder(payload)

    raw_exposures: dict = load_weights().get("instrument_exposures", {})
    exposures: dict[str, float] = dict(raw_exposures.get(instrument, {}))

    engine = ReasoningEngine()
    context = engine.generate_context(events, exposures)

    logger.info(
        json.dumps({
            "event": "feeder.ingest.complete",
            "top_level_category": "runtime_execution_failure",
            "event_code": "feeder_ingest_success",
            "instrument": instrument,
            "events_ingested": len(events),
            "regime": context.regime,
            "vol_bias": context.vol_bias,
            "confidence": context.confidence,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    )

    return context
