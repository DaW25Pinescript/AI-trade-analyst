# CONTRACTS — PR-OPS-1

## 1. Contract document structure

PR-OPS-1 creates a standalone contract extension document at:

`docs/ui/AGENT_OPS_CONTRACT.md`

This document references `UI_CONTRACT.md` for shared conventions (error handling, `data_state` semantics, transport rules) and adds the Agent Ops–specific endpoint contracts.

This path is locked for PR-OPS-1 because:
- Agent Ops endpoints do not exist yet (they ship in PR-OPS-2), while the core contract primarily covers existing endpoints
- keeping them separate prevents the core contract from growing indefinitely
- the extension document can be expanded later in Phase 7 when trace + detail endpoints are contracted
- it mirrors the repo's pattern of separate design docs per lane

`UI_CONTRACT.md` must gain a cross-reference noting that Agent Ops endpoint contracts exist and where they live.

## 2. Shared types and conventions

Use TypeScript-style notation in the contract document.

```typescript
type DepartmentKey =
  | "TECHNICAL_ANALYSIS"
  | "RISK_CHALLENGE"
  | "REVIEW_GOVERNANCE"
  | "INFRA_HEALTH";

type ResponseMeta = {
  version: string;               // contract version, e.g. "2026.03"
  generated_at: string;          // ISO timestamp
  data_state: "live" | "stale" | "unavailable";
  source_of_truth?: string;      // e.g. "roster_config" or "obs_p2_projection"
};

type OpsError = {
  error: string;                 // error code, e.g. "ROSTER_UNAVAILABLE"
  message: string;               // human-readable explanation
  entity_id?: string;            // if error is entity-specific
};

type OpsErrorEnvelope = {
  detail: OpsError;
};
```

### Transport error envelope (locked)
When either endpoint returns an HTTP error, the payload envelope is:

```typescript
type OpsErrorEnvelope = {
  detail: OpsError;
};
```

This aligns with the repo's existing mixed-detail handling while still locking a structured Agent Ops payload shape. The contract must not fall back to freeform string-only `detail` values for these endpoints.

## 3. Endpoint contracts to define

### 3.1 `GET /ops/agent-roster`

**Purpose:** Return the static architecture and roster truth for the multi-agent system. Powers the visible hierarchy: GOVERNANCE LAYER → OFFICER LAYER → PERSONA / DEPARTMENT GRID.

**Backed by:** Persona configuration files, roster definitions, and relationship metadata. This is config-derived, not runtime-derived. It changes when the system architecture changes, not per-run.

**Response shape:**
```typescript
type AgentRosterResponse = ResponseMeta & {
  governance_layer: AgentSummary[];
  officer_layer: AgentSummary[];
  departments: Record<DepartmentKey, AgentSummary[]>;
  relationships: EntityRelationship[];
};

type AgentSummary = {
  id: string;                    // stable entity identifier
  display_name: string;          // card title
  type: "persona" | "officer" | "arbiter" | "subsystem";
  department?: DepartmentKey;    // present for department-grid entities; optional for top-layer entities
  role: string;                  // subtitle / card descriptor
  capabilities: string[];        // tag list
  supports_verdict: boolean;     // contributes to verdict formation
  initials?: string;             // compact avatar fallback
  visual_family: "governance" | "officer" | "technical" | "risk" | "review" | "infra";
  orb_color: "teal" | "amber" | "red";
};

type EntityRelationship = {
  from: string;                  // entity id
  to: string;                    // entity id
  type: "supports" | "challenges" | "feeds" | "synthesizes" | "overrides"
        | "degraded_dependency" | "recovered_dependency";
};
```

**Structural expectations:**
- `governance_layer` is an array; current v1 expectation is 2 entities
- `officer_layer` is an array; current v1 expectation is 2 entities
- `departments` uses exactly four canonical keys matching the workspace hierarchy
- `relationships` drives hierarchy arrows — the frontend must not infer relationships from layout position
- `visual_family` and `orb_color` are semantic tokens — the backend must not send CSS classes or hex colors

**data_state semantics:**
- `live` — roster loaded from config truth, current
- `stale` — roster loaded but config source may be outdated
- `unavailable` — roster config could not be read

**Empty behavior:**
- An empty roster is NOT automatically valid. If `governance_layer` or `officer_layer` are missing or empty, the workspace should show a structured error, not an empty board.

**Error contract:**
- HTTP error responses use `OpsErrorEnvelope`
- The `detail` payload must contain a structured `OpsError`, not a freeform string

---

### 3.2 `GET /ops/agent-health`

**Purpose:** Return current health and lifecycle state snapshot for all visible entities. Merged with roster data to power orb colors, health badges, and status chips.

**Backed by:** Observability Phase 2 structured events, scheduler lifecycle events, feeder health state, and runtime health aggregation. This is a **snapshot projection** over existing observability data, not a new monitoring system.

**Polling model (locked decision):** Poll-based snapshot only in MVP. The UI fetches on load or on manual refresh. No SSE, no WebSocket, no live-push semantics.

**Response shape:**
```typescript
type AgentHealthSnapshotResponse = ResponseMeta & {
  entities: AgentHealthItem[];
};

type AgentHealthItem = {
  entity_id: string;             // joins to AgentSummary.id
  run_state: "idle" | "running" | "completed" | "failed";
  health_state: "live" | "stale" | "degraded" | "unavailable" | "recovered";
  last_active_at?: string;       // ISO timestamp
  last_run_id?: string;          // most recent known run
  health_summary?: string;       // short card/detail summary
  recent_event_summary?: string; // event ribbon / detail panel summary
};
```

**State semantics:**

`run_state` and `health_state` are separate dimensions (per `UI_CONTRACT.md` state-boundary rules):
- `run_state` — where an entity is in its execution lifecycle
- `health_state` — the entity's current health/availability posture

The frontend must not collapse these into a single status indicator. Both should be available for rendering.

**health_state values:**
- `live` — entity healthy, recently active
- `stale` — entity present but data is aged beyond freshness threshold
- `degraded` — entity operational but experiencing issues
- `unavailable` — entity not reachable or not producing data
- `recovered` — entity was previously degraded/unavailable and has recovered

**data_state semantics:**
- `live` — health snapshot is current
- `stale` — health data is aged
- `unavailable` — health aggregation failed or no observability data is available

**Join rule (locked):**
- Every `AgentHealthItem.entity_id` must map to a known `AgentSummary.id` from `/ops/agent-roster`
- Unknown health items are invalid contract output
- Missing health for a known roster entity is allowed and should render as "no health data yet" for that entity

**Empty behavior:**
- Empty `entities: []` is valid if no entities have health data yet (e.g. system just started)
- The workspace should render the roster structure from `/ops/agent-roster` and show "no health data" per entity rather than blocking the entire view

**Degraded behavior:**
- If health fails but roster succeeds, the workspace renders the structure with a degraded banner — it does NOT block entirely
- Individual entity health failures should be reflected per entity, not as a workspace-level error

**Error contract:**
- HTTP error responses use `OpsErrorEnvelope`
- Workspace-level error only when the entire health snapshot fails

## 4. Shared contract conventions

Both Agent Ops endpoints inherit the following from `UI_CONTRACT.md`:

| Convention | Source | Application |
|-----------|--------|-------------|
| Transport | §5.1 | JSON request/response |
| Auth | §5.6 | Same-origin/local-dev, no frontend auth header |
| Failure boundaries | §11.5 | Transport, contract, domain, artifact absence, freshness degradation |
| Timeout/retryability | §12.1–12.2 | Simple reads — short-to-moderate timeout, safe refresh/retry |

The contract extension document should reference these shared conventions rather than duplicating them.

## 5. Explicit non-contracts (Phase 7)

The following endpoints are acknowledged as future but **not contracted in this PR**:

| Endpoint | Phase | Why deferred |
|----------|-------|-------------|
| `GET /runs/{run_id}/agent-trace` | Phase 7 | Requires per-run trace stitching, not a global read model |
| `GET /ops/agent-detail/{entity_id}` | Phase 7 | Requires discriminated union design; riskiest endpoint to contract prematurely |

These should be mentioned as reserved future endpoints in the contract extension document with a note that they will be contracted separately.

## 6. UI_CONTRACT.md update contract

Add a cross-reference section to `UI_CONTRACT.md` (suggested placement: after the existing endpoint sections, before Error Contract Rules):

```markdown
## 10.6 Agent Operations Workspace (Extension)

Agent Operations endpoint contracts are defined in a separate extension document:
`docs/ui/AGENT_OPS_CONTRACT.md`

These endpoints do not exist until their backend implementation PR merges.
They are classified as Phase 3B operator-lane surfaces, not Phase 3A core workspaces.

Covered in the extension:
- `GET /ops/agent-roster` — static architecture and roster truth
- `GET /ops/agent-health` — current health snapshot (poll-based, no live-push)

Reserved for Phase 7 (not yet contracted):
- `GET /runs/{run_id}/agent-trace` — run-specific participation and lineage
- `GET /ops/agent-detail/{entity_id}` — full entity detail with discriminated union
```

## 7. Contract test priorities

The contract document should include a test priorities appendix listing minimum contract tests for PR-OPS-2 to implement:

- `/ops/agent-roster` returns valid `AgentRosterResponse` shape with governance/officer/department structure
- `/ops/agent-roster` returns exactly four canonical department keys
- `/ops/agent-roster` returns arrays for governance/officer layers, with v1 structural expectation of 2 entries each documented in prose
- `/ops/agent-roster` returns explicit `relationships` array
- `/ops/agent-roster` returns structured `OpsErrorEnvelope` on config failure, not freeform detail strings
- `/ops/agent-roster` `data_state` reflects config source freshness
- `/ops/agent-health` returns valid `AgentHealthSnapshotResponse` shape
- `/ops/agent-health` returns `run_state` and `health_state` as separate fields per entity
- `/ops/agent-health` `entity_id` values match roster `id` values
- `/ops/agent-health` tolerates empty `entities` when the system has just started
- `/ops/agent-health` returns structured `OpsErrorEnvelope` on aggregation failure
- `/ops/agent-health` `data_state` reflects observability data freshness
- missing health for a known roster entity is treated as valid UI state, not contract failure
