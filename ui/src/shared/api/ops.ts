// ---------------------------------------------------------------------------
// Agent Operations endpoint clients — shapes from AGENT_OPS_CONTRACT.md.
// Typed fetch functions for all four Agent Operations endpoints.
// ---------------------------------------------------------------------------

import { apiFetch, type ApiResult } from "./client";

// ---- Shared types (§2) ----

export type DepartmentKey =
  | "TECHNICAL_ANALYSIS"
  | "RISK_CHALLENGE"
  | "REVIEW_GOVERNANCE"
  | "INFRA_HEALTH";

export type ResponseMeta = {
  version: string;
  generated_at: string;
  data_state: "live" | "stale" | "unavailable";
  source_of_truth?: string;
};

export type OpsError = {
  error: string;
  message: string;
  entity_id?: string;
};

export type OpsErrorEnvelope = {
  detail: OpsError;
};

// ---- Roster types (§4) ----

export type AgentSummary = {
  id: string;
  display_name: string;
  type: "persona" | "officer" | "arbiter" | "subsystem";
  department?: DepartmentKey;
  role: string;
  capabilities: string[];
  supports_verdict: boolean;
  initials?: string;
  visual_family:
    | "governance"
    | "officer"
    | "technical"
    | "risk"
    | "review"
    | "infra";
  orb_color: "teal" | "amber" | "red";
};

export type EntityRelationship = {
  from: string;
  to: string;
  type:
    | "supports"
    | "challenges"
    | "feeds"
    | "synthesizes"
    | "overrides"
    | "degraded_dependency"
    | "recovered_dependency";
};

export type AgentRosterResponse = ResponseMeta & {
  governance_layer: AgentSummary[];
  officer_layer: AgentSummary[];
  departments: Record<DepartmentKey, AgentSummary[]>;
  relationships: EntityRelationship[];
};

// ---- Health types (§5) ----

export type RunState = "idle" | "running" | "completed" | "failed";

export type HealthState =
  | "live"
  | "stale"
  | "degraded"
  | "unavailable"
  | "recovered";

export type AgentHealthItem = {
  entity_id: string;
  run_state: RunState;
  health_state: HealthState;
  last_active_at?: string;
  last_run_id?: string;
  health_summary?: string;
  recent_event_summary?: string;
};

export type AgentHealthSnapshotResponse = ResponseMeta & {
  entities: AgentHealthItem[];
};

// ---- Trace types (§6) ----

export type TraceSummary = {
  instrument: string;
  session: string;
  timeframes: string[];
  duration_ms: number | null;
  completed_at: string | null;
  final_verdict: string | null;
  final_confidence: number | null;
};

export type TraceStage = {
  stage: string;
  status: string;
  order: number;
  duration_ms: number | null;
};

export type ParticipantContribution = {
  summary: string;
  stance: string | null;
  confidence: number | null;
  was_overridden: boolean;
  override_reason: string | null;
};

export type TraceParticipant = {
  entity_id: string;
  display_name: string;
  role: string;
  participation_status: "active" | "skipped" | "failed";
  contribution: ParticipantContribution;
};

export type TraceEdge = {
  from: string;
  to: string;
  type:
    | "supports"
    | "challenges"
    | "feeds"
    | "synthesizes"
    | "overrides"
    | "degraded_dependency"
    | "recovered_dependency";
  summary: string | null;
};

export type ArbiterTraceSummary = {
  verdict: string;
  confidence: number | null;
  method: string | null;
  override_applied: boolean;
  dissent_summary: string | null;
};

export type ArtifactRef = {
  name: string;
  path: string;
  type: string;
};

export type AgentTraceResponse = ResponseMeta & {
  run_id: string;
  summary: TraceSummary;
  stages: TraceStage[];
  participants: TraceParticipant[];
  edges: TraceEdge[];
  arbiter_summary: ArbiterTraceSummary | null;
  artifacts: ArtifactRef[];
};

// ---- Detail types (§7) ----

export type VisualFamily =
  | "governance"
  | "officer"
  | "technical"
  | "risk"
  | "review"
  | "infra";

export type EntityType = "persona" | "officer" | "arbiter" | "subsystem";

export type RelationshipType =
  | "supports"
  | "challenges"
  | "feeds"
  | "synthesizes"
  | "overrides"
  | "degraded_dependency"
  | "recovered_dependency";

export type EntityIdentity = {
  purpose: string;
  role: string;
  visual_family: VisualFamily;
  capabilities: string[];
  responsibilities: string[];
  initials: string | null;
};

export type EntityStatus = {
  run_state: RunState;
  health_state: HealthState;
  last_active_at: string | null;
  last_run_id: string | null;
  health_summary: string | null;
};

export type EntityDependency = {
  entity_id: string;
  display_name: string;
  direction: "upstream" | "downstream";
  relationship_type: RelationshipType;
};

export type RecentParticipation = {
  run_id: string;
  run_completed_at: string | null;
  verdict_direction: "bullish" | "bearish" | "neutral" | "abstain" | null;
  was_overridden: boolean;
  contribution_summary: string;
};

export type PersonaDetail = {
  variant: "persona";
  analysis_focus: string[];
  verdict_style: string;
  department_role: string;
  typical_outputs: string[];
};

export type OfficerDetail = {
  variant: "officer";
  officer_domain: string;
  data_sources: string[];
  monitored_surfaces: string[];
  update_cadence: string | null;
};

export type ArbiterDetail = {
  variant: "arbiter";
  synthesis_method: string;
  veto_gates: string[];
  quorum_rule: string;
  override_capable: boolean;
  policy_summary: string;
};

export type SubsystemDetail = {
  variant: "subsystem";
  subsystem_type: string;
  monitored_resources: string[];
  health_check_method: string | null;
  runtime_role: string;
};

export type TypeSpecific =
  | PersonaDetail
  | OfficerDetail
  | ArbiterDetail
  | SubsystemDetail;

export type AgentDetailResponse = ResponseMeta & {
  entity_id: string;
  entity_type: EntityType;
  display_name: string;
  department: DepartmentKey | null;
  identity: EntityIdentity;
  status: EntityStatus;
  dependencies: EntityDependency[];
  recent_participation: RecentParticipation[];
  recent_warnings: string[];
  type_specific: TypeSpecific;
};

// ---- OpsErrorEnvelope parsing ----

/**
 * Parse an OpsErrorEnvelope from an API error detail.
 * Returns the structured OpsError if the shape matches, otherwise null.
 */
export function parseOpsErrorEnvelope(
  detail: unknown,
): OpsError | null {
  if (detail === null || typeof detail !== "object") return null;
  const obj = detail as Record<string, unknown>;

  // OpsErrorEnvelope: { detail: { error, message } }
  // But client.ts already unwraps the outer { detail: ... }, so we may
  // receive either the OpsError directly or still wrapped.
  if (typeof obj.error === "string" && typeof obj.message === "string") {
    return {
      error: obj.error,
      message: obj.message,
      entity_id: typeof obj.entity_id === "string" ? obj.entity_id : undefined,
    };
  }

  // Wrapped form: { detail: { error, message } }
  if (obj.detail && typeof obj.detail === "object") {
    const inner = obj.detail as Record<string, unknown>;
    if (typeof inner.error === "string" && typeof inner.message === "string") {
      return {
        error: inner.error,
        message: inner.message,
        entity_id:
          typeof inner.entity_id === "string" ? inner.entity_id : undefined,
      };
    }
  }

  return null;
}

// ---- Endpoint functions ----

/** Fetch the agent roster (static architecture). */
export function fetchAgentRoster(): Promise<ApiResult<AgentRosterResponse>> {
  return apiFetch<AgentRosterResponse>("/ops/agent-roster");
}

/** Fetch the current agent health snapshot. */
export function fetchAgentHealth(): Promise<
  ApiResult<AgentHealthSnapshotResponse>
> {
  return apiFetch<AgentHealthSnapshotResponse>("/ops/agent-health");
}

/** Fetch the agent trace for a specific run. */
export function fetchAgentTrace(
  runId: string,
): Promise<ApiResult<AgentTraceResponse>> {
  return apiFetch<AgentTraceResponse>(`/runs/${encodeURIComponent(runId)}/agent-trace`);
}

/** Fetch entity-level detail for the detail sidebar. */
export function fetchAgentDetail(
  entityId: string,
): Promise<ApiResult<AgentDetailResponse>> {
  return apiFetch<AgentDetailResponse>(`/ops/agent-detail/${encodeURIComponent(entityId)}`);
}
