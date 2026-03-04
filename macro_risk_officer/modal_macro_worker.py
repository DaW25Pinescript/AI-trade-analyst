"""
Modal-based ingestion feeder for the Macro Risk Officer.

Fetches macro/news data from Finnhub, FRED, and GDELT, normalises records
into the versioned feeder contract, and returns structured JSON for the
local MRO reasoning engine to consume.

Architectural boundary (non-negotiable):
  Modal worker:  fetch, source-specific parsing, deduplication, canonical JSON
  Local MRO:     MacroEvent mapping, scoring, regime, confidence, MacroContext

Run locally:
    python -m modal run macro_risk_officer/modal_macro_worker.py

Required env vars (set locally or as Modal Secrets):
    FINNHUB_API_KEY
    FRED_API_KEY
    (GDELT requires no key — public API)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "1.0.0"
DEFAULT_INSTRUMENT = "XAUUSD"

# ─── Pure helpers (no external deps) ──────────────────────────────────────────


def _importance_from_tier(tier: int) -> str:
    """Map MRO tier to feeder importance string."""
    return {1: "high", 2: "medium", 3: "low"}.get(tier, "low")


def _surprise_direction(
    actual: float | None, forecast: float | None
) -> str | None:
    """Return 'positive', 'negative', or None based on actual vs forecast."""
    if actual is None or forecast is None:
        return None
    if actual > forecast:
        return "positive"
    if actual < forecast:
        return "negative"
    return None  # exact match — no directional surprise


def _region_for_source(source: str) -> str:
    """Return the geographic region label for a given source."""
    if source in ("finnhub", "fred"):
        return "US"
    return "global"


def _category_tags(category: str) -> list[str]:
    """Map MRO event category to a list of feeder tags."""
    mapping: dict[str, list[str]] = {
        "monetary_policy": ["central_bank", "rate_decision"],
        "inflation": ["economic_release", "inflation"],
        "employment": ["economic_release", "labour"],
        "growth": ["economic_release", "growth"],
        "geopolitical": ["geopolitical"],
        "systemic_risk": ["systemic_risk"],
    }
    return mapping.get(category, ["economic_release"])


def _macro_event_to_feeder_event(event: Any) -> dict:
    """
    Convert a MacroEvent (from any MRO client) to a feeder contract event dict.

    MacroEvent fields used:  event_id, source, description, category, tier,
                             timestamp, actual, forecast, previous.
    Feeder-only additions:   title (= description), region, importance,
                             surprise_direction, pressure_direction (null),
                             raw_reference (null), tags.

    pressure_direction is intentionally null — it is computed by the local
    ReasoningEngine, not the Modal worker.
    """
    return {
        "event_id": event.event_id,
        "source": event.source,
        "title": event.description,
        "category": event.category,
        "region": _region_for_source(event.source),
        "timestamp": event.timestamp.isoformat(),
        "importance": _importance_from_tier(event.tier),
        "actual": event.actual,
        "forecast": event.forecast,
        "previous": event.previous,
        "surprise_direction": _surprise_direction(event.actual, event.forecast),
        "pressure_direction": None,  # ReasoningEngine's domain — not computed here
        "raw_reference": None,
        "tags": _category_tags(event.category),
    }


def _dedup_events(events: list[dict]) -> list[dict]:
    """Deduplicate feeder events by event_id, preserving first occurrence."""
    seen: set[str] = set()
    out: list[dict] = []
    for ev in events:
        eid = ev.get("event_id", "")
        if eid not in seen:
            seen.add(eid)
            out.append(ev)
    return out


# ─── Source adapters (fetch + parse → feeder event dicts) ─────────────────────


def _run_finnhub_adapter(
    api_key: str,
    lookback_days: int = 14,
    lookahead_days: int = 2,
) -> tuple[list[dict], dict]:
    """
    Fetch Finnhub economic calendar and convert to feeder event dicts.

    Uses the existing FinnhubClient for source-specific HTTP fetch and
    parsing. The adapter's only additional responsibility is translating
    MacroEvent objects to the feeder contract format.

    Returns: (events, source_health_dict)
    """
    t0 = time.monotonic()
    try:
        from macro_risk_officer.ingestion.clients.finnhub_client import (
            FinnhubClient,
        )

        client = FinnhubClient(api_key=api_key)
        macro_events = client.fetch_calendar(
            lookback_days=lookback_days,
            lookahead_days=lookahead_days,
        )
        events = [_macro_event_to_feeder_event(e) for e in macro_events]
        latency_ms = int((time.monotonic() - t0) * 1000)
        return events, {
            "status": "ok",
            "record_count": len(events),
            "latency_ms": latency_ms,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as exc:
        return [], {"status": "failed", "error": str(exc)}


def _run_fred_adapter(api_key: str) -> tuple[list[dict], dict]:
    """
    Fetch FRED macro series and convert to feeder event dicts.

    Returns: (events, source_health_dict)
    """
    t0 = time.monotonic()
    try:
        from macro_risk_officer.ingestion.clients.fred_client import FredClient

        client = FredClient(api_key=api_key)
        macro_events = client.to_macro_events()
        events = [_macro_event_to_feeder_event(e) for e in macro_events]
        latency_ms = int((time.monotonic() - t0) * 1000)
        return events, {
            "status": "ok",
            "record_count": len(events),
            "latency_ms": latency_ms,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as exc:
        return [], {"status": "failed", "error": str(exc)}


def _run_gdelt_adapter(lookback_days: int = 3) -> tuple[list[dict], dict]:
    """
    Fetch GDELT geopolitical sentiment and convert to feeder event dicts.

    GDELT requires no API key. Returns an empty event list (and status "ok")
    when the tone signal is within the noise floor — that is expected behaviour.

    Returns: (events, source_health_dict)
    """
    t0 = time.monotonic()
    try:
        from macro_risk_officer.ingestion.clients.gdelt_client import GdeltClient

        client = GdeltClient()
        macro_events = client.fetch_geopolitical_events(
            lookback_days=lookback_days
        )
        events = [_macro_event_to_feeder_event(e) for e in macro_events]
        latency_ms = int((time.monotonic() - t0) * 1000)
        return events, {
            "status": "ok",
            "record_count": len(events),
            "latency_ms": latency_ms,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    except Exception as exc:
        return [], {"status": "failed", "error": str(exc)}


# ─── Contract assembler ────────────────────────────────────────────────────────


def build_feeder_payload(
    finnhub_key: str | None = None,
    fred_key: str | None = None,
    instrument: str = DEFAULT_INSTRUMENT,
    generated_at: str | None = None,
) -> dict:
    """
    Orchestrate all source adapters, deduplicate, and assemble the versioned
    feeder contract JSON.

    This is a pure function — no Modal SDK dependency.  It can be called
    directly in tests, in the Modal container, or from any Python context.

    Partial source failures are recorded in source_health and do NOT suppress
    results from healthy sources.  A missing API key is treated as a failed
    source (recorded in warnings) rather than a fatal error.

    Returns the complete feeder contract dict.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    all_events: list[dict] = []
    source_health: dict[str, dict] = {}
    sources_queried: list[str] = ["finnhub", "fred", "gdelt"]

    # Finnhub adapter
    if finnhub_key:
        fin_events, fin_health = _run_finnhub_adapter(finnhub_key)
    else:
        fin_events, fin_health = [], {
            "status": "failed",
            "error": "FINNHUB_API_KEY not set",
        }
    all_events.extend(fin_events)
    source_health["finnhub"] = fin_health

    # FRED adapter
    if fred_key:
        fred_events, fred_health = _run_fred_adapter(fred_key)
    else:
        fred_events, fred_health = [], {
            "status": "failed",
            "error": "FRED_API_KEY not set",
        }
    all_events.extend(fred_events)
    source_health["fred"] = fred_health

    # GDELT adapter (no key required)
    gdelt_events, gdelt_health = _run_gdelt_adapter()
    all_events.extend(gdelt_events)
    source_health["gdelt"] = gdelt_health

    # Deduplicate events across sources
    unique_events = _dedup_events(all_events)

    # Overall status: ok / partial / failed
    statuses = {s["status"] for s in source_health.values()}
    if all(s == "ok" for s in statuses):
        status = "ok"
    elif all(s == "failed" for s in statuses) or not unique_events:
        status = "failed"
    else:
        status = "partial"

    # Collect warnings from failed sources
    warnings: list[str] = []
    for src, health in source_health.items():
        if health["status"] == "failed":
            warnings.append(f"{src}: {health.get('error', 'unknown error')}")

    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": generated_at,
        "instrument_context": instrument,
        "sources_queried": sources_queried,
        "status": status,
        "warnings": warnings,
        "events": unique_events,
        "source_health": source_health,
    }


# ─── Modal app (only defined when the modal SDK is available) ─────────────────

try:
    import modal as _modal

    _image = (
        _modal.Image.debian_slim(python_version="3.11")
        .pip_install(
            [
                "httpx>=0.27.0",
                "pydantic>=2.5.0",
                "pyyaml>=6.0",
            ]
        )
        # Bundle the local macro_risk_officer package so the existing client
        # classes are available inside the Modal container without reinstalling.
        .add_local_python_source("macro_risk_officer")
    )

    app = _modal.App(name="mro-macro-feeder", image=_image)

    @app.function(
        timeout=60,
    )
    def fetch_macro_payload(instrument: str = DEFAULT_INSTRUMENT) -> dict:
        """
        Modal-remote entry point.

        Reads FINNHUB_API_KEY and FRED_API_KEY from the container environment
        (set as Modal Secrets or inherited from the local shell for dev runs),
        then delegates to the pure build_feeder_payload() function.
        """
        finnhub_key = os.environ.get("FINNHUB_API_KEY")
        fred_key = os.environ.get("FRED_API_KEY")
        return build_feeder_payload(
            finnhub_key=finnhub_key,
            fred_key=fred_key,
            instrument=instrument,
        )

    @app.local_entrypoint()
    def main() -> None:
        """Local entrypoint: run feeder and print contract JSON to stdout."""
        import sys

        instrument = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INSTRUMENT
        result = fetch_macro_payload.remote(instrument)
        print(json.dumps(result, indent=2))

except ImportError:
    # modal SDK not installed — pure functions above remain usable for tests
    # and direct Python invocation.  Install with: pip install modal
    app = None  # type: ignore[assignment]
