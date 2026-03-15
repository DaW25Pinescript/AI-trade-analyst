"""Agent Operations — Detail response models (PR-OPS-4b).

Implements the contract shapes from docs/PR_OPS_4_SPEC_FINAL.md §7.
Uses flat ResponseMeta inheritance per §5.1.
Discriminated union via entity_type + type_specific variant tag.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

from ai_analyst.api.models.ops import (
    DepartmentKey,
    HealthState,
    RelationshipType,
    ResponseMeta,
    RunState,
    VisualFamily,
)


# ── Shared detail types (§7.5) ──────────────────────────────────────────────


class EntityIdentity(BaseModel):
    """Expanded identity card for an entity (§7.5)."""

    purpose: str = Field(max_length=500)
    role: str
    visual_family: VisualFamily
    capabilities: list[str]
    responsibilities: list[str]
    initials: Optional[str] = None


class EntityStatus(BaseModel):
    """Current state snapshot — reuses PR-OPS-2 health dimensions (§7.5)."""

    run_state: RunState
    health_state: HealthState
    last_active_at: Optional[str] = None
    last_run_id: Optional[str] = None
    health_summary: Optional[str] = Field(default=None, max_length=300)


class EntityDependency(BaseModel):
    """Upstream/downstream relationship for the dependency graph (§7.5)."""

    entity_id: str
    display_name: str
    direction: Literal["upstream", "downstream"]
    relationship_type: RelationshipType


class RecentParticipation(BaseModel):
    """Summary of a recent run this entity participated in (§7.5)."""

    run_id: str
    run_completed_at: Optional[str] = None
    verdict_direction: Optional[Literal["bullish", "bearish", "neutral", "abstain"]] = None
    was_overridden: bool
    contribution_summary: str = Field(max_length=500)


# ── Type-specific variants (§7.6–§7.9) ──────────────────────────────────────


class PersonaDetail(BaseModel):
    """Detail variant for persona entities (§7.6)."""

    variant: Literal["persona"] = "persona"
    analysis_focus: list[str]
    verdict_style: str
    department_role: str
    typical_outputs: list[str]


class OfficerDetail(BaseModel):
    """Detail variant for officer entities (§7.7)."""

    variant: Literal["officer"] = "officer"
    officer_domain: str
    data_sources: list[str]
    monitored_surfaces: list[str]
    update_cadence: Optional[str] = None


class ArbiterDetail(BaseModel):
    """Detail variant for arbiter entities (§7.8)."""

    variant: Literal["arbiter"] = "arbiter"
    synthesis_method: str
    veto_gates: list[str]
    quorum_rule: str
    override_capable: bool
    policy_summary: str = Field(max_length=500)


class SubsystemDetail(BaseModel):
    """Detail variant for subsystem entities (§7.9)."""

    variant: Literal["subsystem"] = "subsystem"
    subsystem_type: str
    monitored_resources: list[str]
    health_check_method: Optional[str] = None
    runtime_role: str


TypeSpecific = Union[PersonaDetail, OfficerDetail, ArbiterDetail, SubsystemDetail]


# ── Top-level response (§7.4) ───────────────────────────────────────────────


class AgentDetailResponse(ResponseMeta):
    """GET /ops/agent-detail/{entity_id} response (§7.4).

    Flat ResponseMeta & {} pattern per §5.1.
    Discriminated union: entity_type is the discriminant,
    type_specific contains the variant keyed by entity_type.
    """

    entity_id: str
    entity_type: Literal["persona", "officer", "arbiter", "subsystem"]
    display_name: str
    department: Optional[DepartmentKey] = None
    identity: EntityIdentity
    status: EntityStatus
    dependencies: list[EntityDependency]
    recent_participation: list[RecentParticipation] = Field(max_length=5)
    recent_warnings: list[str] = Field(max_length=10)
    type_specific: TypeSpecific
