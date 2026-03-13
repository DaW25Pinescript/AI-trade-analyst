// ---------------------------------------------------------------------------
// Agent Operations endpoint clients — shapes from AGENT_OPS_CONTRACT.md.
// Typed fetch functions for roster and health snapshot endpoints.
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

export type AgentHealthItem = {
  entity_id: string;
  run_state: "idle" | "running" | "completed" | "failed";
  health_state: "live" | "stale" | "degraded" | "unavailable" | "recovered";
  last_active_at?: string;
  last_run_id?: string;
  health_summary?: string;
  recent_event_summary?: string;
};

export type AgentHealthSnapshotResponse = ResponseMeta & {
  entities: AgentHealthItem[];
};

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
