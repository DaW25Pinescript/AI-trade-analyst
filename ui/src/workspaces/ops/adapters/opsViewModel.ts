// ---------------------------------------------------------------------------
// View-model adapter for Agent Operations workspace.
//
// Deterministic join of roster + health data following AGENT_OPS_CONTRACT.md
// §5.10 rules:
//   1. Health entity_id must map to roster id — unknowns are discarded.
//   2. Missing health for a roster entity is valid — rendered without health.
//   3. Roster is the structural source of truth.
// ---------------------------------------------------------------------------

import type {
  AgentRosterResponse,
  AgentHealthSnapshotResponse,
  AgentSummary,
  AgentHealthItem,
  DepartmentKey,
  EntityRelationship,
} from "@shared/api/ops";

// ---- Workspace condition ----

export type OpsCondition =
  | "loading"
  | "ready"
  | "degraded"       // roster OK, health failed or unavailable
  | "empty-health"   // roster OK, health returned empty entities
  | "error";         // roster failed — workspace-level block

// ---- Entity view model ----

export interface OpsEntityViewModel {
  id: string;
  displayName: string;
  type: AgentSummary["type"];
  department?: DepartmentKey;
  role: string;
  capabilities: string[];
  supportsVerdict: boolean;
  initials?: string;
  visualFamily: AgentSummary["visual_family"];
  orbColor: AgentSummary["orb_color"];
  // Health fields — undefined when health unavailable
  runState?: AgentHealthItem["run_state"];
  healthState?: AgentHealthItem["health_state"];
  lastActiveAt?: string;
  lastRunId?: string;
  healthSummary?: string;
  recentEventSummary?: string;
  hasHealth: boolean;
}

// ---- Department view model ----

export interface OpsDepartmentViewModel {
  key: DepartmentKey;
  label: string;
  entities: OpsEntityViewModel[];
}

// ---- Full workspace view model ----

export interface OpsWorkspaceViewModel {
  condition: OpsCondition;
  rosterDataState: string | null;
  healthDataState: string | null;
  generatedAt: string | null;
  governanceLayer: OpsEntityViewModel[];
  officerLayer: OpsEntityViewModel[];
  departments: OpsDepartmentViewModel[];
  relationships: EntityRelationship[];
  entityCount: number;
  healthyCount: number;
  degradedCount: number;
  unavailableCount: number;
}

// ---- Department label map ----

const DEPARTMENT_LABELS: Record<DepartmentKey, string> = {
  TECHNICAL_ANALYSIS: "TECHNICAL ANALYSIS",
  RISK_CHALLENGE: "RISK CHALLENGE",
  REVIEW_GOVERNANCE: "REVIEW GOVERNANCE",
  INFRA_HEALTH: "INFRA HEALTH",
};

// ---- Mapping functions ----

/** Build a health lookup map by entity_id. */
function buildHealthMap(
  health: AgentHealthSnapshotResponse | null,
): Map<string, AgentHealthItem> {
  const map = new Map<string, AgentHealthItem>();
  if (!health) return map;
  for (const item of health.entities) {
    map.set(item.entity_id, item);
  }
  return map;
}

/** Map a roster AgentSummary + optional health into an entity view model. */
export function mapEntityViewModel(
  agent: AgentSummary,
  healthMap: Map<string, AgentHealthItem>,
): OpsEntityViewModel {
  const health = healthMap.get(agent.id);
  return {
    id: agent.id,
    displayName: agent.display_name,
    type: agent.type,
    department: agent.department,
    role: agent.role,
    capabilities: agent.capabilities,
    supportsVerdict: agent.supports_verdict,
    initials: agent.initials,
    visualFamily: agent.visual_family,
    orbColor: agent.orb_color,
    runState: health?.run_state,
    healthState: health?.health_state,
    lastActiveAt: health?.last_active_at,
    lastRunId: health?.last_run_id,
    healthSummary: health?.health_summary,
    recentEventSummary: health?.recent_event_summary,
    hasHealth: health !== undefined,
  };
}

/** Collect all roster entity IDs for join-safety validation. */
function collectRosterIds(roster: AgentRosterResponse): Set<string> {
  const ids = new Set<string>();
  for (const agent of roster.governance_layer) ids.add(agent.id);
  for (const agent of roster.officer_layer) ids.add(agent.id);
  for (const agents of Object.values(roster.departments)) {
    for (const agent of agents) ids.add(agent.id);
  }
  return ids;
}

/** Filter health map to only known roster IDs (§5.10 rule 1). */
function filterHealthToRoster(
  healthMap: Map<string, AgentHealthItem>,
  rosterIds: Set<string>,
): Map<string, AgentHealthItem> {
  const filtered = new Map<string, AgentHealthItem>();
  for (const [id, item] of healthMap) {
    if (rosterIds.has(id)) {
      filtered.set(id, item);
    }
  }
  return filtered;
}

/** Resolve workspace condition from query states and data. */
export function resolveOpsCondition(
  roster: AgentRosterResponse | null,
  health: AgentHealthSnapshotResponse | null,
  rosterLoading: boolean,
  healthLoading: boolean,
  rosterError: boolean,
  healthError: boolean,
): OpsCondition {
  if (rosterLoading || healthLoading) return "loading";
  if (rosterError || !roster) return "error";

  // Roster succeeded — check health
  if (healthError || !health || health.data_state === "unavailable") {
    return "degraded";
  }

  if (health.entities.length === 0) return "empty-health";

  return "ready";
}

/** Derive summary counts from entity view models. */
function deriveCounts(entities: OpsEntityViewModel[]) {
  let healthyCount = 0;
  let degradedCount = 0;
  let unavailableCount = 0;

  for (const e of entities) {
    if (!e.hasHealth) {
      unavailableCount++;
    } else if (
      e.healthState === "live" ||
      e.healthState === "recovered"
    ) {
      healthyCount++;
    } else if (
      e.healthState === "stale" ||
      e.healthState === "degraded"
    ) {
      degradedCount++;
    } else if (e.healthState === "unavailable") {
      unavailableCount++;
    }
  }

  return { healthyCount, degradedCount, unavailableCount };
}

/** Build the full ops workspace view model. */
export function buildOpsWorkspaceViewModel(
  roster: AgentRosterResponse | null,
  health: AgentHealthSnapshotResponse | null,
  rosterLoading: boolean,
  healthLoading: boolean,
  rosterError: boolean,
  healthError: boolean,
): OpsWorkspaceViewModel {
  const condition = resolveOpsCondition(
    roster,
    health,
    rosterLoading,
    healthLoading,
    rosterError,
    healthError,
  );

  if (!roster || condition === "error" || condition === "loading") {
    return {
      condition,
      rosterDataState: roster?.data_state ?? null,
      healthDataState: health?.data_state ?? null,
      generatedAt: roster?.generated_at ?? null,
      governanceLayer: [],
      officerLayer: [],
      departments: [],
      relationships: [],
      entityCount: 0,
      healthyCount: 0,
      degradedCount: 0,
      unavailableCount: 0,
    };
  }

  const rosterIds = collectRosterIds(roster);
  const rawHealthMap = buildHealthMap(health);
  const healthMap = filterHealthToRoster(rawHealthMap, rosterIds);

  const governanceLayer = roster.governance_layer.map((a) =>
    mapEntityViewModel(a, healthMap),
  );
  const officerLayer = roster.officer_layer.map((a) =>
    mapEntityViewModel(a, healthMap),
  );

  const departmentKeys = Object.keys(roster.departments) as DepartmentKey[];
  const departments: OpsDepartmentViewModel[] = departmentKeys.map((key) => ({
    key,
    label: DEPARTMENT_LABELS[key] ?? key,
    entities: roster.departments[key].map((a) =>
      mapEntityViewModel(a, healthMap),
    ),
  }));

  const allEntities = [
    ...governanceLayer,
    ...officerLayer,
    ...departments.flatMap((d) => d.entities),
  ];

  const counts = deriveCounts(allEntities);

  return {
    condition,
    rosterDataState: roster.data_state,
    healthDataState: health?.data_state ?? null,
    generatedAt: roster.generated_at,
    governanceLayer,
    officerLayer,
    departments,
    relationships: roster.relationships,
    entityCount: allEntities.length,
    ...counts,
  };
}
