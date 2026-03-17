"""Agent Operations — Trace response models (PR-OPS-4a).

Implements the contract shapes from docs/PR_OPS_4_SPEC_FINAL.md §6.
Uses flat ResponseMeta inheritance per §5.1.
TraceEdge.from_ uses alias "from" per PR-OPS-2 pattern (EntityRelationship).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ai_analyst.api.models.ops import DepartmentKey, ResponseMeta


# ── Trace sub-types (§6.5–§6.10) ────────────────────────────────────────────


class TraceSummary(BaseModel):
    """Compact overview for the trace header (§6.5)."""

    entity_count: int
    stage_count: int
    arbiter_override: bool
    final_bias: Optional[Literal["bullish", "bearish", "neutral"]] = None
    final_decision: Optional[str] = None


class TraceStage(BaseModel):
    """Single pipeline stage in execution order (§6.6)."""

    model_config = ConfigDict(populate_by_name=True)

    stage_key: str = Field(alias="stage")
    stage_index: int
    status: Literal["completed", "failed", "skipped"]
    duration_ms: Optional[int] = None
    participant_ids: list[str]


class ParticipantContribution(BaseModel):
    """Per-participant contribution details (§6.7)."""

    stance: Optional[Literal["bullish", "bearish", "neutral", "abstain"]] = None
    confidence: Optional[float] = None
    role: str
    summary: str = Field(max_length=500)
    was_overridden: bool
    override_reason: Optional[str] = Field(default=None, max_length=300)


class TraceParticipant(BaseModel):
    """Entity that participated (or was scheduled) in a run (§6.7)."""

    entity_id: str
    entity_type: Literal["persona", "officer", "arbiter", "subsystem"]
    display_name: str
    department: Optional[DepartmentKey] = None
    participated: bool
    contribution: ParticipantContribution
    status: Literal["completed", "failed", "skipped"]


TraceEdgeType = Literal[
    "considered_by_arbiter",
    "skipped_before_arbiter",
    "failed_before_arbiter",
    "override",
]


class TraceEdge(BaseModel):
    """Run-scoped directed edge between participants (§6.8).

    ``from`` is a Python reserved word — use ``from_`` with alias.
    Same pattern as EntityRelationship in ops.py.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    type: TraceEdgeType
    stage_index: Optional[int] = None
    summary: Optional[str] = Field(default=None, max_length=300)


class ArbiterTraceSummary(BaseModel):
    """Arbiter synthesis overview for the trace (§6.9)."""

    entity_id: str
    override_applied: bool
    override_type: Optional[str] = None
    override_count: int
    overridden_entity_ids: list[str]
    synthesis_approach: Optional[str] = None
    final_bias: Optional[Literal["bullish", "bearish", "neutral"]] = None
    confidence: Optional[float] = None
    dissent_summary: Optional[str] = Field(default=None, max_length=500)
    summary: str = Field(max_length=500)


class ArtifactRef(BaseModel):
    """Compact pointer to a run artifact (§6.10)."""

    artifact_type: str
    artifact_key: str


# ── Top-level response (§6.4) ───────────────────────────────────────────────


class AgentTraceResponse(ResponseMeta):
    """GET /runs/{run_id}/agent-trace response (§6.4).

    Flat ResponseMeta & {} pattern per §5.1.
    """

    run_id: str
    run_status: Literal["completed", "failed", "partial"]
    instrument: Optional[str] = None
    session: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    summary: TraceSummary
    stages: list[TraceStage]
    participants: list[TraceParticipant]
    trace_edges: list[TraceEdge]
    arbiter_summary: Optional[ArbiterTraceSummary] = None
    artifact_refs: list[ArtifactRef]
