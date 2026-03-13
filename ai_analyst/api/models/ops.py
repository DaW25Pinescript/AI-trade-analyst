"""Agent Operations — Pydantic response models.

Implements the contract shapes from docs/ui/AGENT_OPS_CONTRACT.md §2–§5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Shared types (§2) ────────────────────────────────────────────────────────


class DepartmentKey(str, Enum):
    """Canonical department keys — closed enum (§2.1)."""

    TECHNICAL_ANALYSIS = "TECHNICAL_ANALYSIS"
    RISK_CHALLENGE = "RISK_CHALLENGE"
    REVIEW_GOVERNANCE = "REVIEW_GOVERNANCE"
    INFRA_HEALTH = "INFRA_HEALTH"


DataState = Literal["live", "stale", "unavailable"]


class ResponseMeta(BaseModel):
    """Response-level metadata (§2.2)."""

    version: str
    generated_at: str
    data_state: DataState
    source_of_truth: Optional[str] = None


# ── Error envelope (§2.3) ────────────────────────────────────────────────────


class OpsError(BaseModel):
    error: str
    message: str
    entity_id: Optional[str] = None


# ── Roster types (§4) ────────────────────────────────────────────────────────


AgentType = Literal["persona", "officer", "arbiter", "subsystem"]
VisualFamily = Literal["governance", "officer", "technical", "risk", "review", "infra"]
OrbColor = Literal["teal", "amber", "red"]


class AgentSummary(BaseModel):
    """Single entity in the roster hierarchy (§4.4)."""

    id: str
    display_name: str
    type: AgentType
    department: Optional[DepartmentKey] = None
    role: str
    capabilities: list[str]
    supports_verdict: bool
    initials: Optional[str] = None
    visual_family: VisualFamily
    orb_color: OrbColor


RelationshipType = Literal[
    "supports",
    "challenges",
    "feeds",
    "synthesizes",
    "overrides",
    "degraded_dependency",
    "recovered_dependency",
]


class EntityRelationship(BaseModel):
    """Directed edge between two roster entities (§4.5).

    ``from`` is a Python reserved word — use ``from_`` with alias.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: RelationshipType


class AgentRosterResponse(ResponseMeta):
    """GET /ops/agent-roster response (§4.3)."""

    governance_layer: list[AgentSummary]
    officer_layer: list[AgentSummary]
    departments: dict[DepartmentKey, list[AgentSummary]]
    relationships: list[EntityRelationship]


# ── Health types (§5) ────────────────────────────────────────────────────────


RunState = Literal["idle", "running", "completed", "failed"]
HealthState = Literal["live", "stale", "degraded", "unavailable", "recovered"]


class AgentHealthItem(BaseModel):
    """Per-entity health snapshot (§5.5)."""

    entity_id: str
    run_state: RunState
    health_state: HealthState
    last_active_at: Optional[str] = None
    last_run_id: Optional[str] = None
    health_summary: Optional[str] = None
    recent_event_summary: Optional[str] = None


class AgentHealthSnapshotResponse(ResponseMeta):
    """GET /ops/agent-health response (§5.4)."""

    entities: list[AgentHealthItem]
