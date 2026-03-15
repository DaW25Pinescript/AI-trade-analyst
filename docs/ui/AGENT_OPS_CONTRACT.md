# Agent Operations — Endpoint Contract Specification

**File:** `docs/ui/AGENT_OPS_CONTRACT.md`
**Status:** Active — contract locked, endpoints implemented (PR-OPS-2, PR-OPS-4a, PR-OPS-4b)
**Phase:** PR-OPS-1 (contract docs) ✓ — PR-OPS-2 (backend) ✓ — PR-OPS-4a (agent-trace) ✓ — PR-OPS-4b (agent-detail) ✓ — PR-OPS-3 (frontend) follows
**Scope:** Backend → UI contract extension for Agent Operations read-only projection endpoints
**Depends on:** `UI_CONTRACT.md`, `agent_operations_workspace.schema.refined.md`, `agent_operations_component_adapter_plan.refined.md`, `DESIGN_NOTES.md` §5
**Classification:** Phase 3B extension — operator observability / explainability / trust workspace

---

## 1. Purpose

This document defines the implementation-ready endpoint contracts for all four Agent Operations endpoints. It extends `UI_CONTRACT.md` with the response shapes, state semantics, error contracts, and behavioral rules needed to implement the backend (PR-OPS-2, PR-OPS-4a, PR-OPS-4b) and the frontend workspace (PR-OPS-3).

These endpoints expose the multi-agent analysis engine's architecture and health as read-only projections. They answer the Agent Operations north-star question: **"Why should I trust this system right now?"**

This contract covers:

- exact response shapes with typed fields
- shared types and transport envelope
- `data_state` semantics per endpoint
- error envelope contract
- polling model (locked)
- roster ↔ health join rules
- degraded behavior specifications
- contract test priorities for PR-OPS-2

---

## 2. Shared Types

All types are expressed in TypeScript notation for precision. Backend implementations must produce JSON payloads that conform to these shapes.

### 2.1 DepartmentKey

```typescript
type DepartmentKey =
  | "TECHNICAL_ANALYSIS"
  | "RISK_CHALLENGE"
  | "REVIEW_GOVERNANCE"
  | "INFRA_HEALTH";
```

These are the four canonical department keys. They are a closed enum — the backend must return exactly these values. The frontend must not accept freeform strings in place of `DepartmentKey`.

### 2.2 ResponseMeta

```typescript
type ResponseMeta = {
  version: string;
  generated_at: string;
  data_state: "live" | "stale" | "unavailable";
  source_of_truth?: string;
};
```

**Field definitions:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `version` | `string` | yes | Contract or payload version (e.g. `"2026.03"`) |
| `generated_at` | `string` | yes | ISO 8601 timestamp of payload generation |
| `data_state` | `"live" \| "stale" \| "unavailable"` | yes | Response-level freshness qualifier |
| `source_of_truth` | `string` | no | Describes backend source composition (e.g. `"roster_config"`, `"observability+scheduler"`) |

`data_state` is a response-level concept inherited from `UI_CONTRACT.md` §6.1. It does not replace entity-level health or run state.

### 2.3 OpsError and OpsErrorEnvelope

```typescript
type OpsError = {
  error: string;
  message: string;
  entity_id?: string;
};

type OpsErrorEnvelope = {
  detail: OpsError;
};
```

**Field definitions:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `error` | `string` | yes | Machine-readable error code (e.g. `"ROSTER_UNAVAILABLE"`, `"AGENT_NOT_FOUND"`) |
| `message` | `string` | yes | Human-readable error description |
| `entity_id` | `string` | no | The entity ID that caused the error, when applicable |

When either Agent Operations endpoint returns an HTTP error (4xx or 5xx), the response body **must** use the `OpsErrorEnvelope` shape. Freeform string-only `detail` values are not permitted for these endpoints — this is a stricter contract than the general FastAPI `detail` style described in `UI_CONTRACT.md` §11.1.

---

## 3. Shared Convention References

The following conventions from `UI_CONTRACT.md` apply to both Agent Operations endpoints. They are referenced here, not duplicated:

| Convention | UI_CONTRACT.md section | Application |
|-----------|----------------------|-------------|
| JSON transport | §5.1 | Both endpoints use JSON request/response |
| Auth assumptions | §5.6 | Same-origin/local-dev access; no frontend-managed auth header unless explicitly established |
| Failure boundaries | §11.5 | Transport, contract, domain, artifact absence, and freshness degradation remain distinct failure classes |
| Timeout / retryability | §12.1–12.2 | Both endpoints are simple reads — safe to refresh/retry (see §12.2 "simple reads" row) |

---

## 4. `GET /ops/agent-roster`

### 4.1 Purpose

Static architecture and roster truth. Powers the visible hierarchy: GOVERNANCE LAYER → OFFICER LAYER → PERSONA / DEPARTMENT GRID.

### 4.2 Backend source

Config-derived, not runtime-derived. Backed by persona config and roster definitions. This endpoint does not depend on runtime observability data.

### 4.3 Response shape

```typescript
type AgentRosterResponse = ResponseMeta & {
  governance_layer: AgentSummary[];
  officer_layer: AgentSummary[];
  departments: Record<DepartmentKey, AgentSummary[]>;
  relationships: EntityRelationship[];
};
```

### 4.4 AgentSummary

```typescript
type AgentSummary = {
  id: string;
  display_name: string;
  type: "persona" | "officer" | "arbiter" | "subsystem";
  department?: DepartmentKey;
  role: string;
  capabilities: string[];
  supports_verdict: boolean;
  initials?: string;
  visual_family: "governance" | "officer" | "technical" | "risk" | "review" | "infra";
  orb_color: "teal" | "amber" | "red";
};
```

**Field definitions:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `id` | `string` | yes | Stable entity identifier — must be unique across the entire roster |
| `display_name` | `string` | yes | Card title (e.g. `"DEFAULT ANALYST"`, `"ARBITER"`) |
| `type` | `"persona" \| "officer" \| "arbiter" \| "subsystem"` | yes | Entity classification |
| `department` | `DepartmentKey` | no | Canonical department key. Required for entities in the `departments` record. Governance and officer layer entities may omit this field |
| `role` | `string` | yes | Subtitle or descriptor (e.g. `"Senior Analyst"`, `"Risk Officer"`) |
| `capabilities` | `string[]` | yes | Tag list shown on the card (e.g. `["DIRECTIONAL", "BIAS"]`). May be empty |
| `supports_verdict` | `boolean` | yes | Whether this entity can contribute directly to verdict formation |
| `initials` | `string` | no | Fallback text for compact avatar treatments (e.g. `"DA"`) |
| `visual_family` | see type | yes | Semantic visual family token — the UI maps this to avatar/styling, not raw CSS |
| `orb_color` | `"teal" \| "amber" \| "red"` | yes | Semantic orb color token — the UI maps this to the glowing orb system |

### 4.5 EntityRelationship

```typescript
type EntityRelationship = {
  from: string;
  to: string;
  type: "supports" | "challenges" | "feeds" | "synthesizes" | "overrides"
        | "degraded_dependency" | "recovered_dependency";
};
```

**Field definitions:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `from` | `string` | yes | Source entity `id` |
| `to` | `string` | yes | Target entity `id` |
| `type` | see type | yes | Relationship classification |

Relationships are explicit contract output, not inferred from layout. The frontend must not synthesize hierarchy arrows from visual position alone — all connecting lines between governance → officer → department entities must be driven by this array.

### 4.6 `data_state` semantics for roster

| Value | Meaning | UI behavior |
|-------|---------|-------------|
| `live` | Roster config loaded successfully and is current | Normal render |
| `stale` | Roster config loaded but may be outdated (e.g. config reload pending) | Render with stale warning banner |
| `unavailable` | Roster config could not be loaded | Workspace-level blocking error — do not render partial hierarchy |

### 4.7 Structural expectations (v1)

The current system architecture contains:

- **2 governance-layer entities** (e.g. Arbiter and a governance-level synthesis entity)
- **2 officer-layer entities** (e.g. Market Data Officer and Macro Risk Officer)
- **4 department groups** keyed by the canonical `DepartmentKey` values, each containing one or more persona entities

These counts reflect the v1 architecture and are documented here for frontend layout expectations. They are not enforced as tuple types — the arrays may grow as the system evolves. The frontend should handle arrays of any non-zero length.

### 4.8 Validation rules

- An **empty roster is NOT valid**. If the backend cannot populate the roster, it must return an HTTP error with `OpsErrorEnvelope`, not an empty response.
- Every `departments` key must be one of the four canonical `DepartmentKey` values.
- Every `from` and `to` value in `relationships` must reference an `id` that exists in the roster (governance_layer, officer_layer, or departments).
- All four canonical department keys must be present in the `departments` record, even if a department contains only one entity.

### 4.9 Error responses

All HTTP errors use `OpsErrorEnvelope`.

| HTTP status | `error` code | When |
|------------|-------------|------|
| 500 | `ROSTER_UNAVAILABLE` | Config could not be loaded or parsed |
| 503 | `ROSTER_SERVICE_UNAVAILABLE` | Backend service not ready |

---

## 5. `GET /ops/agent-health`

### 5.1 Purpose

Current health snapshot for all visible entities. Merged with roster data for status rendering in the Org and Health workspace views.

### 5.2 Backend source

Backed by Observability Phase 2 structured events, scheduler lifecycle data, and feeder health. This is a snapshot projection over existing observability data — it does not introduce new runtime state.

### 5.3 Polling model (LOCKED)

**Poll-based snapshot only.** The UI fetches this endpoint on page load or on manual refresh.

- No Server-Sent Events (SSE)
- No WebSocket connections
- No live-push semantics
- No background polling interval is required by contract (frontend may optionally poll, but the contract does not mandate it)

This is locked for the MVP. Any future change to a push model requires a new contract version and must not be silently introduced.

### 5.4 Response shape

```typescript
type AgentHealthSnapshotResponse = ResponseMeta & {
  entities: AgentHealthItem[];
};
```

### 5.5 AgentHealthItem

```typescript
type AgentHealthItem = {
  entity_id: string;
  run_state: "idle" | "running" | "completed" | "failed";
  health_state: "live" | "stale" | "degraded" | "unavailable" | "recovered";
  last_active_at?: string;
  last_run_id?: string;
  health_summary?: string;
  recent_event_summary?: string;
};
```

**Field definitions:**

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `entity_id` | `string` | yes | Joins to `AgentSummary.id` in the roster response |
| `run_state` | see type | yes | Current execution lifecycle state |
| `health_state` | see type | yes | Current health / freshness state |
| `last_active_at` | `string` | no | ISO 8601 timestamp of last activity |
| `last_run_id` | `string` | no | Most recent known run ID |
| `health_summary` | `string` | no | Short human-readable health description for card or detail panel |
| `recent_event_summary` | `string` | no | Recent event description for activity ribbon or detail panel |

### 5.6 `run_state` and `health_state` are separate dimensions

This is a **mandatory contract rule** inherited from `agent_operations_workspace.schema.refined.md` §7.1 and `DESIGN_NOTES.md` §5.

`run_state` describes **where an entity is in its execution lifecycle:**

| Value | Meaning |
|-------|---------|
| `idle` | No execution in progress |
| `running` | Execution is currently active |
| `completed` | Most recent execution completed successfully |
| `failed` | Most recent execution failed |

`health_state` describes **the entity's current health / freshness:**

| Value | Meaning |
|-------|---------|
| `live` | Entity is healthy and data is current |
| `stale` | Entity has data but freshness is degraded |
| `degraded` | Entity is partially functional or has dependency issues |
| `unavailable` | Entity is not currently available |
| `recovered` | Entity was previously degraded/unavailable and has recovered |

These dimensions must not be collapsed into a single status field. The frontend renders both (e.g. orb indicator for health emphasis, separate badge for run state). A single entity may be `run_state: "completed"` and `health_state: "degraded"` simultaneously.

### 5.7 `data_state` semantics for health

| Value | Meaning | UI behavior |
|-------|---------|-------------|
| `live` | Health snapshot successfully projected from current observability data | Normal render — merge with roster |
| `stale` | Health data exists but observability sources may be outdated | Render with stale banner — health badges may not reflect current state |
| `unavailable` | Health projection failed or observability data not accessible | Do not fabricate healthy cards — render roster structure with degraded banner (see §5.9) |

### 5.8 Empty entities

An empty `entities` array (`[]`) is valid if the system has just started and no health data has been projected yet. The frontend should render the roster structure (from `/ops/agent-roster`) with a "health data not yet available" indicator rather than treating this as an error.

### 5.9 Degraded behavior: health fails but roster succeeds

When `/ops/agent-health` returns an error or `data_state: "unavailable"` but `/ops/agent-roster` succeeds:

- The frontend **must** render the roster hierarchy (governance → officer → department structure)
- The frontend **must** display a workspace-level degraded banner indicating health data is unavailable
- Entity cards should render without health/run-state badges rather than showing fabricated healthy states
- The workspace remains usable for structural/architectural inspection

This is distinct from roster failure, which is a workspace-level blocking error (see §4.6).

### 5.10 Roster ↔ Health join rule

The join between roster and health data follows these rules:

1. **Every `entity_id` in the health response must map to an `id` in the roster response.** Health items with unknown entity IDs are invalid and should be discarded by the frontend with a warning.

2. **Missing health for a known roster entity is valid UI state.** If a roster entity has no corresponding health item, the frontend renders the entity card without health/run-state information. This is expected during initial system startup or when an entity has not yet produced observability data.

3. **The roster is the structural source of truth.** Health data augments the roster but does not define the hierarchy. An entity exists in the workspace if and only if it appears in the roster.

### 5.11 Error responses

All HTTP errors use `OpsErrorEnvelope`.

| HTTP status | `error` code | When |
|------------|-------------|------|
| 500 | `HEALTH_PROJECTION_FAILED` | Observability data could not be projected |
| 503 | `HEALTH_SERVICE_UNAVAILABLE` | Backend service not ready |

---

## 6. `GET /runs/{run_id}/agent-trace` (PR-OPS-4a)

### 6.1 Purpose

Run-level agent trace for a specific analysis run. Projects participation, lineage, stage ordering, and arbiter verdict from existing run artifacts.

### 6.2 Backend source

Read-side projection from two artifact sources:
- **Primary:** `run_record.json` — stage ordering, participation, arbiter verdict
- **Secondary:** `logs/runs/{run_id}.jsonl` (audit log) — analyst stances, override details

When the audit log is unavailable, the response degrades to `data_state: "stale"` rather than failing.

### 6.3 Response shape

```typescript
type AgentTraceResponse = ResponseMeta & {
  run_id: string;
  summary: TraceSummary;
  stages: TraceStage[];
  participants: TraceParticipant[];
  edges: TraceEdge[];
  arbiter_summary: ArbiterTraceSummary | null;
  artifacts: ArtifactRef[];
};
```

### 6.4 TraceSummary

```typescript
type TraceSummary = {
  instrument: string;
  session: string;
  timeframes: string[];
  duration_ms: number | null;
  completed_at: string | null;
  final_verdict: string | null;
  final_confidence: number | null;
};
```

### 6.5 TraceStage

```typescript
type TraceStage = {
  stage: string;
  status: string;
  order: number;
  duration_ms: number | null;
};
```

Stage vocabulary (locked): `validate_input`, `macro_context`, `chart_setup`, `analyst_execution`, `arbiter`, `logging`.

### 6.6 TraceParticipant

```typescript
type TraceParticipant = {
  entity_id: string;
  display_name: string;
  role: string;
  participation_status: "active" | "skipped" | "failed";
  contribution: ParticipantContribution;
};

type ParticipantContribution = {
  summary: string;          // max 500 chars
  stance: string | null;
  confidence: number | null;
  was_overridden: boolean;
  override_reason: string | null;  // max 300 chars
};
```

### 6.7 TraceEdge

```typescript
type TraceEdge = {
  from: string;
  to: string;
  type: "supports" | "challenges" | "feeds" | "synthesizes" | "overrides"
        | "degraded_dependency" | "recovered_dependency";
  summary: string | null;  // max 300 chars
};
```

### 6.8 ArbiterTraceSummary

```typescript
type ArbiterTraceSummary = {
  verdict: string;
  confidence: number | null;
  method: string | null;
  override_applied: boolean;
  dissent_summary: string | null;  // max 500 chars
};
```

### 6.9 Bounded payload limits

| Field | Limit |
|-------|-------|
| `contribution.summary` | ≤ 500 chars |
| `contribution.override_reason` | ≤ 300 chars |
| `edge.summary` | ≤ 300 chars |
| `arbiter_summary.dissent_summary` | ≤ 500 chars |
| `edges` array | ≤ 50 entries |

### 6.10 Error responses

| HTTP status | `error` code | When |
|------------|-------------|------|
| 404 | `RUN_NOT_FOUND` | No run artifacts for the given `run_id` |
| 422 | `RUN_ARTIFACTS_MALFORMED` | Artifacts exist but cannot be parsed |
| 500 | `TRACE_PROJECTION_FAILED` | Unexpected projection error |

---

## 7. `GET /ops/agent-detail/{entity_id}` (PR-OPS-4b)

### 7.1 Purpose

Entity-level detail for the Selected Node Detail sidebar. Returns extended metadata, current status, dependency graph, recent participation, and type-specific detail via a discriminated union.

### 7.2 Backend source

Composite read-side projection from:
- **Roster** — identity, department, visual_family, capabilities
- **Profile registry** — purpose, responsibilities, type-specific variant
- **Health snapshot** — run_state, health_state (graceful degradation when unavailable)
- **Recent run scan** — bounded participation history from run artifacts

### 7.3 Response shape

```typescript
type AgentDetailResponse = ResponseMeta & {
  entity_id: string;
  entity_type: "persona" | "officer" | "arbiter" | "subsystem";
  display_name: string;
  department: DepartmentKey | null;
  identity: EntityIdentity;
  status: EntityStatus;
  dependencies: EntityDependency[];
  recent_participation: RecentParticipation[];  // max 5 entries
  recent_warnings: string[];                     // max 10 entries
  type_specific: TypeSpecific;
};
```

### 7.4 EntityIdentity

```typescript
type EntityIdentity = {
  purpose: string;          // max 500 chars
  role: string;
  visual_family: VisualFamily;
  capabilities: string[];
  responsibilities: string[];
  initials: string | null;
};
```

### 7.5 EntityStatus

```typescript
type EntityStatus = {
  run_state: RunState;
  health_state: HealthState;
  last_active_at: string | null;
  last_run_id: string | null;
  health_summary: string | null;  // max 300 chars
};
```

### 7.6 EntityDependency

```typescript
type EntityDependency = {
  entity_id: string;
  display_name: string;
  direction: "upstream" | "downstream";
  relationship_type: RelationshipType;
};
```

### 7.7 RecentParticipation

```typescript
type RecentParticipation = {
  run_id: string;
  run_completed_at: string | null;
  verdict_direction: "bullish" | "bearish" | "neutral" | "abstain" | null;
  was_overridden: boolean;
  contribution_summary: string;  // max 500 chars
};
```

### 7.8 TypeSpecific (discriminated union)

`entity_type` is the discriminant. `type_specific.variant` contains the variant tag.

```typescript
type PersonaDetail = {
  variant: "persona";
  analysis_focus: string[];
  verdict_style: string;
  department_role: string;
  typical_outputs: string[];
};

type OfficerDetail = {
  variant: "officer";
  officer_domain: string;
  data_sources: string[];
  monitored_surfaces: string[];
  update_cadence: string | null;
};

type ArbiterDetail = {
  variant: "arbiter";
  synthesis_method: string;
  veto_gates: string[];
  quorum_rule: string;
  override_capable: boolean;
  policy_summary: string;  // max 500 chars
};

type SubsystemDetail = {
  variant: "subsystem";
  subsystem_type: string;
  monitored_resources: string[];
  health_check_method: string | null;
  runtime_role: string;
};

type TypeSpecific = PersonaDetail | OfficerDetail | ArbiterDetail | SubsystemDetail;
```

### 7.9 Bounded payload limits

| Field | Limit |
|-------|-------|
| `identity.purpose` | ≤ 500 chars |
| `status.health_summary` | ≤ 300 chars |
| `recent_participation` array | ≤ 5 entries |
| `recent_warnings` array | ≤ 10 entries |
| `contribution_summary` | ≤ 500 chars |
| `policy_summary` | ≤ 500 chars |

### 7.10 Recent participation scan bounds

- Max 20 run artifact directories scanned
- Max 7 days lookback
- Whichever bound is hit first stops the scan
- Returned array capped at 5 most recent entries

### 7.11 Graceful degradation

When health data is unavailable, the endpoint returns a valid response with `data_state: "stale"` and default status (`run_state: "idle"`, `health_state: "unavailable"`). It does not return a 500 error.

### 7.12 Error responses

| HTTP status | `error` code | When |
|------------|-------------|------|
| 404 | `ENTITY_NOT_FOUND` | `entity_id` not in roster |
| 422 | `DETAIL_PROJECTION_FAILED` | Entity exists but projection failed |
| 500 | `DETAIL_PROJECTION_FAILED` | Unexpected projection error |

---

## 8. Contract Test Priorities

Backend implementation must include deterministic tests covering the following areas. These are the minimum acceptance bar.

### 8.1 Response shape tests

- [x] `/ops/agent-roster` returns a valid `AgentRosterResponse` with all required fields
- [x] `/ops/agent-health` returns a valid `AgentHealthSnapshotResponse` with all required fields
- [x] All `ResponseMeta` fields are present and correctly typed
- [x] `AgentSummary` contains all required fields with correct types
- [x] `AgentHealthItem` contains all required fields with correct types

### 8.2 Department key tests

- [x] `departments` record contains exactly the four canonical `DepartmentKey` values
- [x] No freeform or misspelled department keys are accepted
- [x] Each department key maps to a non-empty array of `AgentSummary` objects

### 8.3 Relationship array tests

- [x] `relationships` array is present in roster response
- [x] Every `from` and `to` value references a valid roster entity `id`
- [x] Relationship `type` values are within the allowed enum

### 8.4 `data_state` tests

- [x] Roster response includes `data_state` with a valid value
- [x] Health response includes `data_state` with a valid value
- [x] `data_state: "unavailable"` triggers appropriate error handling

### 8.5 Structured error envelope tests

- [x] HTTP errors return `OpsErrorEnvelope` shape (not freeform string `detail`)
- [x] `OpsError` contains `error` and `message` fields
- [x] Error responses use appropriate HTTP status codes

### 8.6 Separate `run_state` / `health_state` tests

- [x] `run_state` and `health_state` are separate fields on `AgentHealthItem`
- [x] Both fields accept only their respective allowed values
- [x] An entity can have independent values for each dimension (e.g. `run_state: "completed"` with `health_state: "degraded"`)

### 8.7 Empty and degraded scenario tests

- [x] Empty roster (zero entities) returns HTTP error, not empty response
- [x] Empty health `entities` array is a valid response (returns 200)
- [x] Health failure with roster success is a handled degraded scenario
- [x] Roster failure is a workspace-level blocking error

### 8.8 Health `entity_id` ↔ roster `id` join tests

- [x] Every `entity_id` in health response matches a roster `id`
- [x] Health items with unknown `entity_id` values are invalid
- [x] Missing health for a known roster entity is a valid state

---

## 9. Summary

This contract specifies all four Agent Operations endpoints:

| Endpoint | Purpose | Backend source | Response shape | PR |
|----------|---------|---------------|----------------|-----|
| `GET /ops/agent-roster` | Static architecture and roster truth | Persona config, roster definitions | `AgentRosterResponse` | PR-OPS-2 |
| `GET /ops/agent-health` | Current health snapshot | Obs P2 events, scheduler, feeder health | `AgentHealthSnapshotResponse` | PR-OPS-2 |
| `GET /runs/{run_id}/agent-trace` | Run-level agent trace | `run_record.json` + audit log | `AgentTraceResponse` | PR-OPS-4a |
| `GET /ops/agent-detail/{entity_id}` | Entity-level detail | Roster + profile + health + run scan | `AgentDetailResponse` | PR-OPS-4b |

Key contract decisions:

- **Polling only** — no SSE, no WebSocket, no live-push for health
- **Separate dimensions** — `run_state` and `health_state` are independent
- **Structured errors** — `OpsErrorEnvelope` with typed `OpsError`, not freeform strings
- **Typed departments** — `DepartmentKey` is a closed enum of four values
- **Explicit relationships** — hierarchy arrows driven by `relationships` array, not layout inference
- **Roster authority** — roster is structural source of truth; health augments but does not define hierarchy
- **Empty roster is invalid** — backend must return an error, not an empty response
- **Join rule is explicit** — health `entity_id` must map to roster `id`; unknown health items are invalid; missing health for known entities is valid
- **Flat envelope** — all endpoints use `ResponseMeta & {}` pattern, no `data`/`meta` wrapper
- **Plain slug IDs** — no namespace prefix (e.g. `persona_default_analyst`, not `agent:persona_default_analyst`)
- **Discriminated union** — detail `type_specific` keyed by `entity_type` with `variant` tag
- **Graceful degradation** — missing audit log → `data_state: "stale"`; missing health → degraded status, not 500
- **Bounded payloads** — all text fields and arrays have explicit size limits

The contract is sufficient for:
- PR-OPS-2 to implement roster/health backend endpoints
- PR-OPS-4a/4b to implement trace/detail backend endpoints
- PR-OPS-3 to build the React workspace using typed adapters and hooks
