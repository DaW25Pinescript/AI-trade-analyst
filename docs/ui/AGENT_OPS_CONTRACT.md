# Agent Operations — Endpoint Contract Specification

**File:** `docs/ui/AGENT_OPS_CONTRACT.md`
**Status:** Active — contract locked, endpoints not yet implemented
**Phase:** PR-OPS-1 (contract docs) — PR-OPS-2 (backend implementation) follows
**Scope:** Backend → UI contract extension for Agent Operations read-only projection endpoints
**Depends on:** `UI_CONTRACT.md`, `agent_operations_workspace.schema.refined.md`, `agent_operations_component_adapter_plan.refined.md`, `DESIGN_NOTES.md` §5
**Classification:** Phase 3B extension — operator observability / explainability / trust workspace

---

## 1. Purpose

This document defines the implementation-ready endpoint contracts for the first two Agent Operations endpoints. It extends `UI_CONTRACT.md` with the response shapes, state semantics, error contracts, and behavioral rules needed to implement both the backend (PR-OPS-2) and the frontend workspace (PR-OPS-3).

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

## 6. Reserved Future Endpoints

The following endpoints are acknowledged as part of the Agent Operations roadmap but are **not contracted in this document**. They are reserved for Phase 7 (PR-OPS-4 / PR-OPS-5).

### `GET /runs/{run_id}/agent-trace` — Phase 7

Run-specific participation and lineage overlay for Run mode. Will power participant highlighting, influence overlays, lineage edge rendering, and arbiter override indicators.

### `GET /ops/agent-detail/{entity_id}` — Phase 7

Full detail payload for the Selected Node Detail sidebar. Must use a discriminated union (`entity_type`) to prevent dumping-ground payloads.

These endpoints must not be implemented or consumed until their own contract specification is written and merged. The design-level response shapes in `agent_operations_workspace.schema.refined.md` §5.5–5.6 serve as input for that future contract, not as the contract itself.

---

## 7. Contract Test Priorities

PR-OPS-2 (backend implementation) must include deterministic tests covering the following areas. These are the minimum acceptance bar for the backend PR.

### 7.1 Response shape tests

- [ ] `/ops/agent-roster` returns a valid `AgentRosterResponse` with all required fields
- [ ] `/ops/agent-health` returns a valid `AgentHealthSnapshotResponse` with all required fields
- [ ] All `ResponseMeta` fields are present and correctly typed
- [ ] `AgentSummary` contains all required fields with correct types
- [ ] `AgentHealthItem` contains all required fields with correct types

### 7.2 Department key tests

- [ ] `departments` record contains exactly the four canonical `DepartmentKey` values
- [ ] No freeform or misspelled department keys are accepted
- [ ] Each department key maps to a non-empty array of `AgentSummary` objects

### 7.3 Relationship array tests

- [ ] `relationships` array is present in roster response
- [ ] Every `from` and `to` value references a valid roster entity `id`
- [ ] Relationship `type` values are within the allowed enum

### 7.4 `data_state` tests

- [ ] Roster response includes `data_state` with a valid value
- [ ] Health response includes `data_state` with a valid value
- [ ] `data_state: "unavailable"` triggers appropriate error handling

### 7.5 Structured error envelope tests

- [ ] HTTP errors return `OpsErrorEnvelope` shape (not freeform string `detail`)
- [ ] `OpsError` contains `error` and `message` fields
- [ ] Error responses use appropriate HTTP status codes

### 7.6 Separate `run_state` / `health_state` tests

- [ ] `run_state` and `health_state` are separate fields on `AgentHealthItem`
- [ ] Both fields accept only their respective allowed values
- [ ] An entity can have independent values for each dimension (e.g. `run_state: "completed"` with `health_state: "degraded"`)

### 7.7 Empty and degraded scenario tests

- [ ] Empty roster (zero entities) returns HTTP error, not empty response
- [ ] Empty health `entities` array is a valid response (returns 200)
- [ ] Health failure with roster success is a handled degraded scenario
- [ ] Roster failure is a workspace-level blocking error

### 7.8 Health `entity_id` ↔ roster `id` join tests

- [ ] Every `entity_id` in health response matches a roster `id`
- [ ] Health items with unknown `entity_id` values are invalid
- [ ] Missing health for a known roster entity is a valid state

---

## 8. Summary

This contract specifies the first two Agent Operations endpoints:

| Endpoint | Purpose | Backend source | Response shape |
|----------|---------|---------------|----------------|
| `GET /ops/agent-roster` | Static architecture and roster truth | Persona config, roster definitions | `AgentRosterResponse` |
| `GET /ops/agent-health` | Current health snapshot | Obs P2 events, scheduler, feeder health | `AgentHealthSnapshotResponse` |

Key contract decisions:

- **Polling only** — no SSE, no WebSocket, no live-push for health
- **Separate dimensions** — `run_state` and `health_state` are independent
- **Structured errors** — `OpsErrorEnvelope` with typed `OpsError`, not freeform strings
- **Typed departments** — `DepartmentKey` is a closed enum of four values
- **Explicit relationships** — hierarchy arrows driven by `relationships` array, not layout inference
- **Roster authority** — roster is structural source of truth; health augments but does not define hierarchy
- **Empty roster is invalid** — backend must return an error, not an empty response
- **Join rule is explicit** — health `entity_id` must map to roster `id`; unknown health items are invalid; missing health for known entities is valid

The contract is sufficient for:
- PR-OPS-2 to implement the backend endpoints with deterministic tests
- PR-OPS-3 to build the React workspace using typed adapters and hooks
