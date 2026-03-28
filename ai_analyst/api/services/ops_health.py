"""Agent Operations — Health projection service.

Projects a poll-based health snapshot from existing observability evidence:
- app.state.feeder_context / feeder_ingested_at (feeder bridge state)
- app.state.feeder_payload_meta (feeder source health)
- Pipeline metrics (ai_analyst/core/pipeline_metrics.py)
- Scheduler events (market_data_officer/scheduler.py structured logs)

Entities with no health signals get health_state: "unavailable" (§5.10).
Empty entities list is valid on fresh start (§5.8).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ai_analyst.api.models.ops import (
    AgentHealthItem,
    AgentHealthSnapshotResponse,
)
from ai_analyst.api.services.ops_roster import get_all_roster_ids

# ── Contract version ─────────────────────────────────────────────────────────

_CONTRACT_VERSION = "2026.03"

# Staleness threshold for feeder data (seconds)
_FEEDER_STALE_SECONDS = 3600


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _feeder_health_item(
    feeder_ingested_at: Optional[datetime],
    feeder_payload_meta: Optional[dict],
) -> AgentHealthItem:
    """Project health for the feeder_ingest subsystem from app.state."""
    if feeder_ingested_at is None or feeder_payload_meta is None:
        return AgentHealthItem(
            entity_id="feeder_ingest",
            run_state="idle",
            health_state="unavailable",
            health_summary="No feeder payload ingested yet",
            evidence_basis="none",
        )

    now = datetime.now(timezone.utc)
    age_seconds = (now - feeder_ingested_at).total_seconds()
    stale = age_seconds > _FEEDER_STALE_SECONDS

    source_health = feeder_payload_meta.get("source_health", {})
    source_status = feeder_payload_meta.get("status", "unknown")

    if stale:
        health_state = "stale"
        summary = f"Feeder data is {int(age_seconds)}s old (stale)"
    elif source_status == "ok" or source_status == "success":
        health_state = "live"
        summary = f"Feeder data fresh ({int(age_seconds)}s old)"
    else:
        health_state = "degraded"
        summary = f"Feeder ingested but source status: {source_status}"

    return AgentHealthItem(
        entity_id="feeder_ingest",
        run_state="completed",
        health_state=health_state,
        last_active_at=feeder_ingested_at.isoformat(),
        health_summary=summary,
        recent_event_summary=f"Last ingest: {source_status}",
        evidence_basis="runtime_event",
    )


def _mdo_scheduler_health_item(
    feeder_ingested_at: Optional[datetime],
    feeder_payload_meta: Optional[dict],
) -> AgentHealthItem:
    """Project health for MDO scheduler.

    Uses feeder bridge state as proxy — the scheduler feeds MDO which in
    turn contributes to the pipeline context.
    """
    if feeder_ingested_at is None:
        return AgentHealthItem(
            entity_id="mdo_scheduler",
            run_state="idle",
            health_state="unavailable",
            health_summary="No scheduler data available",
            evidence_basis="none",
        )

    now = datetime.now(timezone.utc)
    age_seconds = (now - feeder_ingested_at).total_seconds()

    if age_seconds > _FEEDER_STALE_SECONDS:
        return AgentHealthItem(
            entity_id="mdo_scheduler",
            run_state="completed",
            health_state="stale",
            last_active_at=feeder_ingested_at.isoformat(),
            health_summary=f"Scheduler data is {int(age_seconds)}s old (stale)",
            evidence_basis="runtime_event",
        )

    return AgentHealthItem(
        entity_id="mdo_scheduler",
        run_state="completed",
        health_state="live",
        last_active_at=feeder_ingested_at.isoformat(),
        health_summary="Scheduler operating normally",
        evidence_basis="runtime_event",
    )


def _default_health_item(entity_id: str) -> AgentHealthItem:
    """Default health for entities with no observability evidence."""
    return AgentHealthItem(
        entity_id=entity_id,
        run_state="idle",
        health_state="unavailable",
        health_summary="No health signals available",
        evidence_basis="none",
    )


def project_health(app_state: Any) -> AgentHealthSnapshotResponse:
    """Build the agent health snapshot from available observability data.

    Parameters
    ----------
    app_state : FastAPI app.state
        The application state object containing feeder bridge data.

    Returns
    -------
    AgentHealthSnapshotResponse
        Poll-based snapshot with per-entity health items.
    """
    feeder_ingested_at: Optional[datetime] = getattr(
        app_state, "feeder_ingested_at", None
    )
    feeder_payload_meta: Optional[dict] = getattr(
        app_state, "feeder_payload_meta", None
    )
    feeder_context = getattr(app_state, "feeder_context", None)

    # Build health items for entities that have observability evidence
    evidence_items: dict[str, AgentHealthItem] = {}

    # Feeder ingest subsystem
    evidence_items["feeder_ingest"] = _feeder_health_item(
        feeder_ingested_at, feeder_payload_meta
    )

    # MDO scheduler subsystem
    evidence_items["mdo_scheduler"] = _mdo_scheduler_health_item(
        feeder_ingested_at, feeder_payload_meta
    )

    # Officer health derived from their subsystems
    # Market Data Officer — mirrors MDO scheduler health
    mdo_health = evidence_items["mdo_scheduler"]
    evidence_items["market_data_officer"] = AgentHealthItem(
        entity_id="market_data_officer",
        run_state=mdo_health.run_state,
        health_state=mdo_health.health_state,
        last_active_at=mdo_health.last_active_at,
        health_summary="Mirrors MDO scheduler status",
        evidence_basis="derived_proxy",
    )

    # Macro Risk Officer — mirrors feeder ingest health
    fi_health = evidence_items["feeder_ingest"]
    evidence_items["macro_risk_officer"] = AgentHealthItem(
        entity_id="macro_risk_officer",
        run_state=fi_health.run_state,
        health_state=fi_health.health_state,
        last_active_at=fi_health.last_active_at,
        health_summary="Mirrors feeder ingest status",
        evidence_basis="derived_proxy",
    )

    # Macro context provides evidence for governance entities
    if feeder_context is not None:
        evidence_items["arbiter"] = AgentHealthItem(
            entity_id="arbiter",
            run_state="idle",
            health_state="live",
            health_summary="Arbiter available with macro context",
            evidence_basis="derived_proxy",
        )
        evidence_items["governance_synthesis"] = AgentHealthItem(
            entity_id="governance_synthesis",
            run_state="idle",
            health_state="live",
            health_summary="Governance synthesis pipeline ready",
            evidence_basis="derived_proxy",
        )

    # Assemble: every roster entity gets a health item
    roster_ids = get_all_roster_ids()
    entities: list[AgentHealthItem] = []
    for entity_id in sorted(roster_ids):
        if entity_id in evidence_items:
            entities.append(evidence_items[entity_id])
        else:
            entities.append(_default_health_item(entity_id))

    # Determine response-level data_state
    health_states = [e.health_state for e in entities]
    if all(h == "unavailable" for h in health_states):
        data_state = "unavailable"
    elif any(h == "stale" for h in health_states):
        data_state = "stale"
    else:
        data_state = "live"

    return AgentHealthSnapshotResponse(
        version=_CONTRACT_VERSION,
        generated_at=_now_iso(),
        data_state=data_state,
        source_of_truth="observability+scheduler",
        entities=entities,
    )
