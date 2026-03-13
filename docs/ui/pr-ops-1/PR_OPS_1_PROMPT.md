# PR-OPS-1 Implementation Prompt

Implement **PR-OPS-1 — Agent Operations Endpoint Contract Spec** for the AI Trade Analyst repo.

## Context
The repo has completed Phase 0–3 of the UI re-entry plan:
- PR-UI-0: governance unlock (React + TS + Tailwind locked, Agent Ops classified as Phase 3B)
- PR-UI-1: React app shell in `ui/`
- PR-UI-2: Triage Board MVP with live data, shared components, trust strip
- PR-UI-3: shared component extraction and hardening (66 tests, barrel exports, README)

Phase 4 begins Agent Operations work. This PR is the **contract docs** portion. PR-OPS-2 (backend implementation) follows.

## Your task
Create the endpoint contract specification for the first two Agent Operations endpoints. This is a **docs-only PR** — zero code changes.

## Before writing anything
Read these docs:
- `docs/ui/agent_operations_workspace.schema.refined.md` — design-level response shapes (the input)
- `docs/ui/agent_operations_component_adapter_plan.refined.md` — frontend component plan
- `docs/ui/DESIGN_NOTES.md` §5 — Agent Ops governance: north-star question, five operator questions, negative scope, classification
- `docs/specs/ui_reentry_phase_plan.md` Phase 4 — contract requirements per endpoint
- `docs/ui/UI_CONTRACT.md` §5.1, §5.6, §6, §11.5, §12.1–12.2 — shared conventions

These documents are the inputs. The contract extension is the output.

## Primary deliverable
Create `docs/ui/AGENT_OPS_CONTRACT.md` containing implementation-ready endpoint contracts for:

### Shared types and transport envelope
Use TypeScript notation and lock these shared types first:

```typescript
type DepartmentKey =
  | "TECHNICAL_ANALYSIS"
  | "RISK_CHALLENGE"
  | "REVIEW_GOVERNANCE"
  | "INFRA_HEALTH";

type ResponseMeta = {
  version: string;
  generated_at: string;
  data_state: "live" | "stale" | "unavailable";
  source_of_truth?: string;
};

type OpsError = {
  error: string;
  message: string;
  entity_id?: string;
};

type OpsErrorEnvelope = {
  detail: OpsError;
};
```

When either endpoint returns an HTTP error, the payload envelope is **locked** as `OpsErrorEnvelope`. Do not use freeform string-only `detail` values for these endpoints.

### `GET /ops/agent-roster`

**Purpose:** Static architecture and roster truth. Powers the visible hierarchy.

**Backed by:** Persona config, roster definitions. Config-derived, not runtime-derived.

**Response shape**:
```typescript
type AgentRosterResponse = ResponseMeta & {
  governance_layer: AgentSummary[];
  officer_layer: AgentSummary[];
  departments: Record<DepartmentKey, AgentSummary[]>;
  relationships: EntityRelationship[];
};

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

type EntityRelationship = {
  from: string;
  to: string;
  type: "supports" | "challenges" | "feeds" | "synthesizes" | "overrides"
        | "degraded_dependency" | "recovered_dependency";
};
```

**Specify:**
- `data_state` semantics
- current v1 structural expectation of 2 governance and 2 officer entities, documented in prose rather than tuple types
- four canonical department keys
- relationships are explicit contract output, not inferred from layout
- empty roster is NOT valid
- error shape uses `OpsErrorEnvelope`

### `GET /ops/agent-health`

**Purpose:** Current health snapshot for all visible entities. Merged with roster for status rendering.

**Backed by:** Obs P2 structured events, scheduler lifecycle, feeder health. Snapshot projection over existing observability data.

**Polling model (LOCKED):** Poll-based snapshot only. No SSE, no WebSocket, no live-push. Fetched on load or manual refresh.

**Response shape:**
```typescript
type AgentHealthSnapshotResponse = ResponseMeta & {
  entities: AgentHealthItem[];
};

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

**Specify:**
- `run_state` and `health_state` are separate dimensions
- all `health_state` values defined
- `data_state` semantics
- empty `entities` valid if system just started
- degraded behavior (health fails but roster succeeds → render structure with banner)
- error shape uses `OpsErrorEnvelope`
- explicit join rule: every `entity_id` must map to a roster `id`; unknown health items are invalid; missing health for a known roster entity is valid UI state

### Shared convention references
Reference (do not duplicate) from `UI_CONTRACT.md`:
- JSON transport (§5.1)
- auth assumptions (§5.6)
- failure boundaries (§11.5)
- timeout/retryability as simple reads (§12.1–12.2)

### Reserved future endpoints
Acknowledge but do NOT contract:
- `GET /runs/{run_id}/agent-trace` — Phase 7
- `GET /ops/agent-detail/{entity_id}` — Phase 7

### Contract test priorities
Include an appendix listing minimum tests PR-OPS-2 must implement. Cover:
- response shapes
- exact department keys
- relationship arrays
- `data_state`
- structured error envelopes
- separate `run_state` / `health_state`
- empty / degraded scenarios
- health `entity_id` values matching roster `id` values

## Secondary deliverable — `UI_CONTRACT.md` update
Add a cross-reference section (§10.6 or appropriate location):
- point to `docs/ui/AGENT_OPS_CONTRACT.md`
- list the two contracted endpoints
- list the two reserved future endpoints
- state endpoints don't exist until PR-OPS-2 merges
- state Phase 3B operator-lane classification

Do NOT rewrite or restructure existing `UI_CONTRACT.md` sections.

## Documentation updates
1. `docs/AI_TradeAnalyst_Progress.md` — Phase 4 contract work complete, backend MVP (PR-OPS-2) next
2. `docs/specs/README.md` — add link to new contract doc
3. `docs/specs/ui_reentry_phase_plan.md` — note Phase 4 contract portion complete

## Hard constraints
- **Zero Python files created or modified**
- **Zero TypeScript/React files created or modified**
- No existing endpoint contracts altered
- No Phase 7 endpoints contracted
- No changes to core workspace contracts
- No HTML prototype referenced as contract source
- Polling-only for health — no ambiguity

## Acceptance bar
The PR is successful only if:
- `AGENT_OPS_CONTRACT.md` exists with complete response shapes for both endpoints
- every field has a type and purpose
- `run_state` and `health_state` are separate dimensions
- the polling model is explicitly stated
- error responses use `OpsErrorEnvelope = { detail: OpsError }`
- `DepartmentKey` is typed, not freeform string
- governance/officer layers are arrays with documented v1 expected counts in prose
- the roster ↔ health join rule is explicit
- `UI_CONTRACT.md` has a cross-reference section
- reserved future endpoints are acknowledged but not contracted
- contract test priorities are listed
- zero code files changed
- no existing contracts altered

## Deliverables
1. **Summary** — what was documented
2. **Contract document** — name and location
3. **Endpoints contracted** — key response shape decisions
4. **UI_CONTRACT.md changes** — section added
5. **Reserved future endpoints** — noted
6. **Contract test priorities** — listed
7. **Verification** — no code files in diff
8. **Suggested commit message**: `docs(ops): define Agent Ops contract for /ops/agent-roster and /ops/agent-health`
9. **Suggested PR description**

## Quality bar
Could someone implement the backend endpoints (PR-OPS-2) using only this contract doc? Could someone build the React workspace (PR-OPS-3) using only this contract doc plus the component plan? If yes to both, the contract is sufficient.
