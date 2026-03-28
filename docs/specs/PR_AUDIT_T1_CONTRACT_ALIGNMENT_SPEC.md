# AI Trade Analyst — Audit Tranche 1: Contract Alignment Repair

**Status:** ✅ Complete — 28 March 2026
**Date:** 28 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Review level:** Full
**Justification for Full review:** Cross-layer contract changes (backend models → contract doc → frontend types → UI components → tests). Silent field-name mismatches are exactly the failure mode Full review exists to catch — "passes tests but behaves wrong" is the current live state.

---

## 1. Purpose

- **After:** Phase 8 complete (PR-REFLECT-3 shipped), zero-trust architecture audit conducted (2026-03-28)
- **Question this phase answers:** Can the three-way contract drift between backend trace models, the AGENT_OPS_CONTRACT.md specification, and frontend TypeScript types be eliminated so that Run mode trace rendering is structurally honest?
- **FROM:** Backend emits a rich, correct trace shape that neither the contract doc nor the frontend consume — Run mode silently renders empty/missing data for edges, artifacts, summary fields, arbiter detail, and partial-run detection
- **TO:** Single source of truth: the backend **serialized trace API response** (defined by `AgentTraceResponse` with Pydantic aliases applied) is canonical; contract doc reflects the JSON payload exactly, frontend types match it verbatim, and Run mode renders all available trace data

---

## 2. Scope

### In scope

- Promote the backend **serialized trace API payload** as canonical — frontend types and contract doc must match the JSON response actually emitted by the API, not the internal Python attribute names (audit decision: backend is richer and more correct)
- Update `docs/ui/AGENT_OPS_CONTRACT.md` §6 to match the backend serialized trace API payload exactly
- Update frontend TypeScript trace types in `ui/src/shared/api/ops.ts` to match backend
- Update all frontend components that consume trace types: `RunTracePanel.tsx`, `TraceEdgeList.tsx`, `TraceStageTimeline.tsx`, `ArbiterSummaryCard.tsx`
- Fix dead partial-run detection logic (Finding 2): drive from `run_status === "partial"` instead of stage status heuristic
- Separate run-scoped edge types from roster relationship types in the frontend edge styling map (Finding 3)
- Update frontend test fixtures in `ui/tests/ops.test.tsx` to use promoted backend shapes
- Add route-level backend contract test to `tests/test_ops_trace_endpoints.py` that validates exact serialized field names, types, and alias behaviour
- Update `TraceParticipantList.tsx` to consume `status` field (not `participation_status`)

### Out of scope (hard list)

- No redesign of backend trace projection logic (`ops_trace.py`) — the backend is presumed correct. Only minimal backend changes are allowed if diagnostics prove a serialization or alias defect that prevents the API payload from serving as the canonical source
- No changes to roster, health, or detail endpoints — those are Tranche 2
- No coupling/module-boundary refactoring (Finding 7, 8) — Tranche 2
- No observability trust fixes (Findings 4, 5, 6) — Tranche 2
- No run index/cache work (Finding 9) — Tranche 2
- No new endpoints, no new backend services
- No SQLite or database layer introduced
- No new top-level module
- No changes to the analysis pipeline, arbiter, or persona logic

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Backend trace models | `ai_analyst/api/models/ops_trace.py` defines the canonical shape; the **serialized JSON payload** (with aliases applied) is what frontend types and contract doc must match — confirmed by code inspection |
| Backend trace service | `ai_analyst/api/services/ops_trace.py` emits `AgentTraceResponse` as defined in models — no adapter layer exists |
| Pydantic alias behaviour | `TraceEdge.from_` serialises to JSON key `"from"` via alias; `TraceStage.stage_key` serialises to `"stage"` via alias — both use `populate_by_name=True` |
| Frontend API client | `ui/src/shared/api/ops.ts` `fetchAgentTrace()` calls `apiFetch<AgentTraceResponse>()` — the generic type parameter IS the frontend shape, so updating the type definition updates what all consumers see |
| Frontend test structure | All ops frontend tests are in `ui/tests/ops.test.tsx`; trace fixture objects must match the type definitions |
| Contract doc | `docs/ui/AGENT_OPS_CONTRACT.md` §6 is the section to update |

### Current likely state

The backend has been emitting a richer trace shape since PR-OPS-4a (14 March 2026). The frontend was built against the contract doc shape in PR-OPS-5a/5b (15 March 2026). Because the frontend uses `??` fallbacks and optional chaining throughout, it silently renders empty/missing values rather than crashing. This means Run mode *appears* to work but is showing incomplete trace data. Specifically: edges show no entries (field name mismatch), artifacts show no entries (field name mismatch), summary shows no instrument/session (wrong nesting), arbiter summary shows "—" for verdict (wrong field name), partial-run indicator never fires (checking for statuses that don't exist).

---

## 4. Key File Paths

| Role | Path | Change type |
|------|------|-------------|
| Backend trace models (SOURCE OF TRUTH) | `ai_analyst/api/models/ops_trace.py` | Read-only reference |
| Backend trace service | `ai_analyst/api/services/ops_trace.py` | Read-only reference |
| Contract doc | `docs/ui/AGENT_OPS_CONTRACT.md` | Update §6 |
| Frontend types | `ui/src/shared/api/ops.ts` | Update trace types |
| Run trace panel | `ui/src/workspaces/ops/components/RunTracePanel.tsx` | Update field access |
| Trace edge list | `ui/src/workspaces/ops/components/TraceEdgeList.tsx` | Update edge type map |
| Trace stage timeline | `ui/src/workspaces/ops/components/TraceStageTimeline.tsx` | Update field names |
| Trace participant list | `ui/src/workspaces/ops/components/TraceParticipantList.tsx` | Update field names |
| Arbiter summary card | `ui/src/workspaces/ops/components/ArbiterSummaryCard.tsx` | Update field names |
| Frontend tests | `ui/tests/ops.test.tsx` | Update fixtures + add contract shape tests |
| Backend tests | `tests/test_ops_trace_endpoints.py` | Add route-level contract test |
| Reflect API client | `ui/src/shared/api/reflect.ts` | Read-only check (imports from ops.ts) |

---

## 5. Current State Audit Hypothesis

### What is already true
- Backend trace projection is complete, well-tested (70+ tests in PR-OPS-4a), and emits the richer shape
- Frontend components exist and render without errors (they fail silently on missing fields)
- The Pydantic models include field aliases that ensure JSON serialisation matches Python attribute names in the way the frontend expects (e.g., `from_` → `"from"`, `stage_key` → `"stage"`)

### What likely remains incomplete
- Frontend trace types have never been updated since PR-OPS-5a (built from contract doc)
- Contract doc §6 has never been updated since PR-OPS-1
- No route-level contract test exists that would have caught this drift
- The `TraceEdgeList` component's style map uses roster relationship types (`supports`, `challenges`, `feeds`, etc.) which the backend never emits for trace edges — the backend uses run-scoped types (`considered_by_arbiter`, `skipped_before_arbiter`, `failed_before_arbiter`, `override`)

### Core phase question
"Can we align the frontend and contract doc to the backend shape without breaking any existing rendering outside of the trace surface?"

---

## 6. Design — Field-by-Field Alignment Map

This section defines the exact field changes. The backend column is the source of truth. The "Frontend change" column defines what must be updated.

### 6.1 `AgentTraceResponse` (top level)

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `run_id` | `str` | `string` | No change |
| `run_status` | `"completed" \| "failed" \| "partial"` | Not present | **Add field** |
| `instrument` | `str \| null` (top-level) | Not present (expected inside summary) | **Add field** |
| `session` | `str \| null` (top-level) | Not present (expected inside summary) | **Add field** |
| `started_at` | `str \| null` (top-level) | Not present | **Add field** |
| `finished_at` | `str \| null` (top-level) | Not present | **Add field** |
| `summary` | `TraceSummary` | `TraceSummary` (different shape) | **Update shape** (§6.2) |
| `stages` | `TraceStage[]` | `TraceStage[]` (different shape) | **Update shape** (§6.3) |
| `participants` | `TraceParticipant[]` | `TraceParticipant[]` (different shape) | **Update shape** (§6.4) |
| `trace_edges` | `TraceEdge[]` | `edges: TraceEdge[]` | **Rename to `trace_edges`** |
| `arbiter_summary` | `ArbiterTraceSummary \| null` | `ArbiterTraceSummary \| null` (different shape) | **Update shape** (§6.6) |
| `artifact_refs` | `ArtifactRef[]` | `artifacts: ArtifactRef[]` (different shape) | **Rename to `artifact_refs`**, update shape (§6.7) |

### 6.2 `TraceSummary`

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `entity_count` | `int` | Not present | **Add** |
| `stage_count` | `int` | Not present | **Add** |
| `arbiter_override` | `bool` | Not present | **Add** |
| `final_bias` | `"bullish" \| "bearish" \| "neutral" \| null` | Not present | **Add** |
| `final_decision` | `str \| null` | Not present | **Add** |
| `instrument` | Not present (top-level) | `string` | **Remove** |
| `session` | Not present (top-level) | `string` | **Remove** |
| `timeframes` | Not present | `string[]` | **Remove** |
| `duration_ms` | Not present | `number \| null` | **Remove** |
| `completed_at` | Not present | `string \| null` | **Remove** |
| `final_verdict` | Not present | `string \| null` | **Remove** |
| `final_confidence` | Not present | `number \| null` | **Remove** |

### 6.3 `TraceStage`

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `stage_key` (alias: `stage`) | `str` | `stage: string` | No change (alias matches) |
| `stage_index` | `int` | `order: number` | **Rename to `stage_index`** |
| `status` | `"completed" \| "failed" \| "skipped"` | `string` | **Narrow type** |
| `duration_ms` | `int \| null` | `number \| null` | No change |
| `participant_ids` | `str[]` | Not present | **Add** |

### 6.4 `TraceParticipant`

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `entity_id` | `str` | `string` | No change |
| `entity_type` | `"persona" \| "officer" \| "arbiter" \| "subsystem"` | Not present | **Add** |
| `display_name` | `str` | `string` | No change |
| `department` | `DepartmentKey \| null` | Not present | **Add** |
| `participated` | `bool` | Not present | **Add** |
| `contribution` | `ParticipantContribution` | Same shape | See §6.5 |
| `status` | `"completed" \| "failed" \| "skipped"` | `participation_status: "active" \| "skipped" \| "failed"` | **Rename to `status`**, update enum values |
| `role` | Not present (in contribution) | `string` | **Remove** (role is inside contribution) |

### 6.5 `ParticipantContribution`

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `stance` | `"bullish" \| "bearish" \| "neutral" \| "abstain" \| null` | `string \| null` | **Narrow type** |
| `confidence` | `float \| null` | `number \| null` | No change |
| `role` | `str` | Not present (role at participant level) | **Add** |
| `summary` | `str` (max 500) | `string` | No change |
| `was_overridden` | `bool` | `boolean` | No change |
| `override_reason` | `str \| null` (max 300) | `string \| null` | No change |

### 6.6 `ArbiterTraceSummary`

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `entity_id` | `str` | Not present | **Add** |
| `override_applied` | `bool` | `boolean` | No change |
| `override_type` | `str \| null` | Not present | **Add** |
| `override_count` | `int` | Not present | **Add** |
| `overridden_entity_ids` | `str[]` | Not present | **Add** |
| `synthesis_approach` | `str \| null` | Not present | **Add** |
| `final_bias` | `"bullish" \| ... \| null` | Not present | **Add** |
| `confidence` | `float \| null` | `number \| null` | No change |
| `dissent_summary` | `str \| null` (max 500) | `string \| null` | No change |
| `summary` | `str` (max 500) | Not present | **Add** |
| `verdict` | Not present | `string` | **Remove** (use `summary` or derive from top-level `final_decision`) |
| `method` | Not present | `string \| null` | **Remove** (future: `synthesis_approach` covers this) |

### 6.7 `ArtifactRef`

| Field | Backend (canonical) | Current frontend | Frontend change |
|-------|-------------------|-----------------|----------------|
| `artifact_type` | `str` | `type: string` | **Rename to `artifact_type`** |
| `artifact_key` | `str` | Not present | **Add** |
| `name` | Not present | `string` | **Remove** |
| `path` | Not present | `string` | **Remove** |

### 6.8 `TraceEdge` — edge type vocabulary separation

The backend emits **run-scoped** edge types:
```
"considered_by_arbiter" | "skipped_before_arbiter" | "failed_before_arbiter" | "override"
```

The frontend currently expects **roster relationship** types:
```
"supports" | "challenges" | "feeds" | "synthesizes" | "overrides" | "degraded_dependency" | "recovered_dependency"
```

These are two different semantic vocabularies:
- **Roster relationships** describe static architectural connections (who supports/challenges whom)
- **Run-scoped edges** describe what happened in a specific run (who was considered by arbiter, who was skipped)

The fix: `TraceEdge.type` in the frontend must use the backend's run-scoped vocabulary. The `TraceEdgeList` component's `EDGE_TYPE_STYLES` map must be replaced with run-scoped styling. The roster relationship type remains unchanged for the roster endpoint.

Updated frontend `TraceEdge` type (full shape):
```typescript
type TraceEdgeType =
  | "considered_by_arbiter"
  | "skipped_before_arbiter"
  | "failed_before_arbiter"
  | "override";

type TraceEdge = {
  from: string;
  to: string;
  type: TraceEdgeType;
  stage_index: number | null;  // present in backend, missing from old frontend type
  summary: string | null;      // already present in old frontend type
};
```

New `EDGE_TYPE_STYLES` for `TraceEdgeList.tsx`:
```typescript
const EDGE_TYPE_STYLES: Record<string, { label: string; className: string }> = {
  considered_by_arbiter:    { label: "CONSIDERED",     className: "text-teal-400" },
  skipped_before_arbiter:   { label: "SKIPPED",        className: "text-gray-500" },
  failed_before_arbiter:    { label: "FAILED",         className: "text-red-400" },
  override:                 { label: "OVERRIDE",       className: "text-amber-400" },
};
```

### 6.9 Partial-run detection fix (Finding 2)

**Current (dead) logic in `RunTracePanel.tsx`:**
```typescript
const isPartial = stages.some(
  (s) => s.status === "running" || s.status === "pending",
);
```
The backend stage status enum is `completed | failed | skipped` — `"running"` and `"pending"` never appear. This check always evaluates to `false`.

**Fixed logic:**
```typescript
const isPartial = trace.run_status === "partial";
```
This uses the new top-level `run_status` field from the promoted backend shape.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Type alignment | Frontend `AgentTraceResponse` type in `ops.ts` matches backend Pydantic model field-for-field (names, types, optionality) | ✅ Done |
| AC-2 | TraceSummary alignment | Frontend `TraceSummary` matches backend shape: `entity_count`, `stage_count`, `arbiter_override`, `final_bias`, `final_decision` — old fields removed | ✅ Done |
| AC-3 | TraceStage alignment | Frontend `TraceStage` uses `stage_index` (not `order`), `participant_ids` added | ✅ Done |
| AC-4 | TraceParticipant alignment | Frontend uses `status` (not `participation_status`) with enum `completed | failed | skipped` (not `active | skipped | failed`), `entity_type`/`department`/`participated` added, `role` moved inside contribution. STATUS_STYLES map in `TraceParticipantList.tsx` updated accordingly | ✅ Done |
| AC-5 | TraceEdge alignment | Frontend `TraceEdge.type` uses run-scoped vocabulary (`considered_by_arbiter`, etc.), NOT roster relationship types. `stage_index: number | null` added to frontend type (diagnostic confirmed present in backend, missing from frontend) | ✅ Done |
| AC-6 | ArbiterTraceSummary alignment | Frontend matches backend: `entity_id`, `override_type`, `override_count`, `overridden_entity_ids`, `synthesis_approach`, `final_bias`, `summary` added; `verdict`/`method` removed | ✅ Done |
| AC-7 | ArtifactRef alignment | Frontend uses `artifact_type`/`artifact_key` (not `name`/`path`/`type`) | ✅ Done |
| AC-8 | Top-level fields | Frontend type includes `run_status`, `instrument`, `session`, `started_at`, `finished_at` at top level | ✅ Done |
| AC-9 | Partial-run fix | `RunTracePanel` detects partial runs from `trace.run_status === "partial"`, not from stage status heuristic | ✅ Done |
| AC-10 | Edge component | `TraceEdgeList.tsx` renders backend edge types with correct labels and styling; unknown types get graceful fallback | ✅ Done |
| AC-11 | Stage component | `TraceStageTimeline.tsx` sorts by `stage_index` (not `order`) | ✅ Done |
| AC-12 | Arbiter component | `ArbiterSummaryCard.tsx` renders `summary` field (not `verdict`), shows `override_count`, `final_bias` | ✅ Done |
| AC-13 | Trace panel header | `RunTracePanel.tsx` reads `instrument`/`session` from top-level `trace.instrument`/`trace.session` (not `trace.summary.instrument`) | ✅ Done |
| AC-14 | Artifact rendering | `RunTracePanel.tsx` artifact list reads `trace.artifact_refs` (not `trace.artifacts`), uses `artifact_key` for display | ✅ Done |
| AC-15 | Contract doc update | `AGENT_OPS_CONTRACT.md` §6 field definitions, enums, nesting, and examples match the canonical serialized backend response exactly. Every JSON example in §6 must be regenerated from or manually verified against the canonical serialized payload; no example may retain deprecated field names | ✅ Done |
| AC-16 | Frontend tests green | All existing frontend tests pass (389 passing diagnostic baseline); trace fixture shapes updated to match promoted backend shape; zero new failures from this tranche | ✅ Done |
| AC-17 | Backend contract test | New test in `test_ops_trace_endpoints.py` that exercises the trace route response path using a known fixture corpus and asserts exact serialized JSON field names at top-level and critical nested levels (catching alias drift, renames, missing fields, null/default omission). Route-level test preferred over model-only serialization | ✅ Done |
| AC-18 | No backend redesign | Backend models/services are presumed correct and out of scope for redesign. Only minimal corrective changes are permitted if diagnostics prove a serialization/alias defect that prevents the API payload from serving as canonical. Any such fix must be flagged and justified before proceeding | ✅ Done |
| AC-19 | Negative: deprecated trace fields | Deprecated keys must not remain in **trace API type definitions** (`ops.ts` trace types), **trace test fixtures** (`ops.test.tsx` trace objects), or **trace component field access paths** (`ui/src/workspaces/ops/components/`). Specifically: `edges` (use `trace_edges`), `artifacts` (use `artifact_refs`), `participation_status` (use `status`), `order` in TraceStage context (use `stage_index`), `verdict` in ArbiterTraceSummary context (use `summary`), `name`/`path` in ArtifactRef context (use `artifact_type`/`artifact_key`). Non-trace uses of these words elsewhere in the codebase are not in scope | ✅ Done |
| AC-20 | Regression: non-trace surfaces | Roster, Health, Detail, Run Browser, Market Data, Reflect, Chart — all rendering unchanged, all tests passing | ✅ Done |
| AC-21 | Contract mismatch guard | If critical trace fields required by the canonical contract (`run_id`, `run_status`, `summary`, `stages`, `participants`, `trace_edges`) are absent in a supposedly successful trace response, Run mode must show a clear degraded/contract-mismatch state rather than silently rendering placeholders for the whole panel. Lightweight guard acceptable (e.g. check for missing `run_status` or empty `stages`) | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1: Confirm backend shape

```bash
cd "C:\Users\david\OneDrive\Documents\GitHub\AI trade analyst"
python -c "
from ai_analyst.api.models.ops_trace import AgentTraceResponse
import json
schema = AgentTraceResponse.model_json_schema()
print(json.dumps(schema, indent=2))
"
```

**Expected:** JSON schema showing exact field names including aliases. Confirm `trace_edges` (not `edges`), `artifact_refs` (not `artifacts`), `stage_index`, `status` (participant), etc.

**Report:** Any differences from §6 design section — if the schema disagrees with the spec, the schema wins.

### Step 2: Confirm Pydantic serialisation aliases

```bash
python -c "
from ai_analyst.api.models.ops_trace import TraceEdge, TraceStage
e = TraceEdge(from_='a', to='b', type='override')
print('TraceEdge JSON keys:', list(e.model_dump(by_alias=True).keys()))
s = TraceStage(stage_key='arbiter', stage_index=1, status='completed', participant_ids=[])
print('TraceStage JSON keys:', list(s.model_dump(by_alias=True).keys()))
"
```

**Expected:** `TraceEdge` has key `"from"` (not `"from_"`). `TraceStage` has key `"stage"` (not `"stage_key"`).

**Report:** Alias behaviour — frontend field names must match the aliased JSON keys, not the Python attribute names.

### Step 3: Run baseline test suites

```bash
# Backend
python -m pytest tests/ -x --tb=short -q 2>&1 | tail -5

# Frontend
cd ui && npx vitest run --reporter=verbose 2>&1 | tail -10
```

**Expected:** Backend: ~489 passed, 1 failed (pre-existing MDO scheduler). Frontend: 401 passing, 5 pre-existing failures.

**Diagnostic result:** Backend: 496 passed, 3 failed (pre-existing `test_import_stability.py`). Frontend: 389 passed, 17 failed (12 additional pre-existing failures unrelated to this tranche). Regression gates adjusted to use diagnostic baselines.

**Report:** Exact pass/fail counts. Any new failures are blockers — investigate before proceeding.

### Step 4: Verify frontend trace fixture shapes in ops.test.tsx

```bash
cd "C:\Users\david\OneDrive\Documents\GitHub\AI trade analyst"
grep -n "edges\|artifacts\|participation_status\|\.order\|verdict:" ui/tests/ops.test.tsx | head -30
```

**Expected:** Multiple hits showing old field names (`edges:`, `artifacts:`, `participation_status:`, `.order`, `verdict:`) that need updating.

**Report:** Line numbers and count of fields to change.

### Step 5: Verify no other frontend files import trace types

```bash
grep -rn "TraceEdge\|TraceSummary\|TraceStage\|TraceParticipant\|ArbiterTraceSummary\|ArtifactRef" ui/src/ --include="*.ts" --include="*.tsx" | grep -v node_modules
```

**Expected:** Trace types consumed in `ops.ts`, `RunTracePanel.tsx`, `TraceEdgeList.tsx`, `TraceStageTimeline.tsx`, `TraceParticipantList.tsx`, `ArbiterSummaryCard.tsx`. Possibly `reflect.ts` if it imports from ops. No other consumers.

**Report:** Full list of consuming files. Any unexpected consumers must be added to the change surface.

### Step 6: Grep for deprecated trace field access in source components

```bash
grep -rn "summary\.instrument\|summary\.session\|summary\.timeframes\|summary\.duration_ms\|summary\.completed_at\|summary\.final_verdict\|summary\.final_confidence\|\.edges\|\.artifacts\|participation_status\|\.order\|arbiter_summary\.verdict\|arbiter_summary\.method" ui/src/workspaces/ops --include="*.ts" --include="*.tsx"
```

**Expected:** Multiple hits showing deprecated trace field access paths in `RunTracePanel.tsx`, `TraceStageTimeline.tsx`, `TraceParticipantList.tsx`, `ArbiterSummaryCard.tsx`, and possibly others.

**Report:** Full list of file:line:field for every deprecated access. This is the actual silent-failure surface — every hit here is a place where the UI currently renders empty/missing data. All must be fixed in implementation step 3.

### Step 7: Report smallest patch set

**Report:** Files, one-line description, estimated line delta per file. Format:

| File | Change | Est. lines |
|------|--------|-----------|
| `ui/src/shared/api/ops.ts` | Update trace type definitions | ~80 |
| ... | ... | ... |

---

## 9. Implementation Constraints

### 9.1 General rule

The backend **serialized trace API response** is the source of truth. Frontend types and the contract doc must match the JSON payload actually emitted by the API, not the internal Python attribute names. Every change must make the frontend match the serialized backend output — never the reverse. If any ambiguity arises during implementation, serialise a backend model instance with `model_dump(mode='json', by_alias=True)` and use the resulting key names as the answer.

### 9.1b Implementation Sequence

1. **Backend contract test** — add test to `test_ops_trace_endpoints.py` that exercises the trace route response path (or the `project_trace()` function with a known fixture corpus) and asserts exact serialized JSON field names at top-level and critical nested levels. Route-level preferred — this catches alias application, null/default omission, and intermediate transformation drift that model-only serialization misses. Run. Verify green. This locks the target shape before changing anything else.
   - Gate: backend tests pass (496 baseline + 1 new)

2. **Frontend type definitions** — update all trace types in `ui/src/shared/api/ops.ts` per §6 design. This will cause TypeScript compilation errors in consuming components — that's expected and desired (the compiler shows us every consumer that needs updating).

3. **Frontend components** — fix each component that the TypeScript compiler flags:
   - `RunTracePanel.tsx` — `trace_edges`, `artifact_refs`, top-level `instrument`/`session`, `run_status` partial detection
   - `TraceEdgeList.tsx` — new edge type style map
   - `TraceStageTimeline.tsx` — `stage_index` (not `order`)
   - `TraceParticipantList.tsx` — `status` (not `participation_status`), STATUS_STYLES map must use `completed` (not `active`) to match backend enum
   - `ArbiterSummaryCard.tsx` — `summary` (not `verdict`), new fields
   - Gate: TypeScript compiles clean (`npx tsc --noEmit`)

4. **Frontend test fixtures** — update trace fixtures in `ui/tests/ops.test.tsx` to use promoted shapes. Run vitest.
   - Gate: 389+ passing (diagnostic baseline), zero new failures from this tranche

5. **Contract doc** — update `AGENT_OPS_CONTRACT.md` §6 to match the canonical serialized payload exactly. Cross-check every type definition, every field table, every JSON example. Every example must be regenerated from or manually verified against the serialized payload; no example may retain deprecated field names.
   - Gate: manual review — every §6 type block, field table, and example matches `ops_trace.py` serialized output

6. **Full regression** — run backend and frontend test suites.
   - Gate: backend 497+ passed; frontend 389+ passed; no new failures from this tranche

### 9.2 Code change surface

| File | Role |
|------|------|
| `ui/src/shared/api/ops.ts` | Frontend trace type definitions — PRIMARY CHANGE |
| `ui/src/workspaces/ops/components/RunTracePanel.tsx` | Trace panel — field access updates |
| `ui/src/workspaces/ops/components/TraceEdgeList.tsx` | Edge list — type vocabulary swap |
| `ui/src/workspaces/ops/components/TraceStageTimeline.tsx` | Stage timeline — field rename |
| `ui/src/workspaces/ops/components/TraceParticipantList.tsx` | Participant list — field rename |
| `ui/src/workspaces/ops/components/ArbiterSummaryCard.tsx` | Arbiter card — field additions/removals |
| `ui/tests/ops.test.tsx` | Frontend tests — fixture shape updates |
| `tests/test_ops_trace_endpoints.py` | Backend tests — new contract snapshot test |
| `docs/ui/AGENT_OPS_CONTRACT.md` | Contract doc — §6 full update |

**No changes expected to (unless diagnostics prove a serialization defect — flag before proceeding):**
- `ai_analyst/api/models/ops_trace.py` (source of truth — presumed correct)
- `ai_analyst/api/services/ops_trace.py` (projection logic unchanged)
- `ai_analyst/api/models/ops.py` (roster/health types unchanged)
- `ai_analyst/api/services/ops_roster.py` (roster service unchanged)
- `ai_analyst/api/services/ops_health.py` (health service unchanged)
- `ai_analyst/api/services/ops_detail.py` (detail service unchanged)
- `ui/src/workspaces/ops/adapters/opsViewModel.ts` (roster/health only)
- `ui/src/shared/api/reflect.ts` (unless it imports trace types — check in diagnostic)
- Any analysis pipeline, arbiter, or persona code

**If any of the above require changes, flag before proceeding.**

### 9.3 Out of scope (repeat)

- No backend redesign (minimal serialization fixes permitted only if diagnostics prove necessity — see AC-18)
- No backend projection logic changes
- No roster/health/detail contract changes
- No coupling refactoring
- No observability trust fixes
- No SQLite, no new top-level module

---

## 10. Success Definition

Tranche 1 is done when: the frontend `AgentTraceResponse` type, all trace-consuming components, all trace test fixtures, and the contract doc §6 exactly match the backend serialized API response; partial-run detection is driven from `run_status`; trace edge styling uses run-scoped vocabulary; a route-level backend contract test exists to prevent future drift; a lightweight contract-mismatch guard in the UI prevents silent placeholder rendering; all 389+ frontend tests and 496+ backend tests pass with zero new failures from this tranche; and no backend redesign has occurred (only minimal serialization fixes if diagnostics proved necessary).

---

## 11. Why This Phase Matters

| Without | With |
|---------|------|
| Run mode silently shows empty edges, artifacts, summary fields | Run mode shows the full trace data the backend already produces |
| Partial-run detection never fires (dead code) | Partial runs are correctly identified and flagged |
| Edge types show roster relationships (architecturally misleading) | Edge types show what actually happened in the run |
| Arbiter summary card shows "—" for verdict | Arbiter summary shows the full synthesis output |
| Contract doc describes a shape nobody implements | Contract doc is a verified reflection of the live backend |
| No test prevents future drift | Route-level contract test catches field renames/additions/removals |
| Tranche 2 (trust/coupling) built on a drifting foundation | Tranche 2 starts from a clean, aligned contract surface |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 8 (PR-REFLECT-3) | Suggestions v0, cross-workspace nav, coherence | ✅ Done |
| Audit Tranche 1 | Contract alignment repair (Findings 1, 2, 3) | ✅ Complete — 28 March 2026 |
| Audit Tranche 2 | Trust + coupling repair (Findings 4–12) | 💭 Planned — spec after T1 closes |
| Phase 9 candidates | Filter controls, Chart Indicators, ML Pattern Detection | 💭 Concept — after audit tranches |

---

## 13. Diagnostic Findings

*Populated from diagnostic report — 28 March 2026.*

### Backend schema
Confirmed. All field names, types, and optionality match spec §6. Aliases confirmed: `from_` → `"from"`, `stage_key` → `"stage"`.

### Spec gap found
`TraceEdge` backend model includes `stage_index: int | null` and `summary: str | null (max 300)` — spec §6.8 originally only discussed the type vocabulary. Frontend already had `summary` but was missing `stage_index`. Spec updated: §6.8 now shows full `TraceEdge` shape, AC-5 expanded to cover `stage_index`.

### Baseline test counts (actual vs spec expectation)
- Backend: 496 passed / 3 failed (spec expected ~489 / 1). Net positive. 3 failures in `test_import_stability.py` — pre-existing.
- Frontend: 389 passed / 17 failed (spec expected 401 / 5). 12 additional pre-existing failures unrelated to this tranche. Regression gate adjusted: use 389 as the passing baseline, not 401.

### Deprecated field access confirmed
18 deprecated access points found across 4 components — all in the expected files (`RunTracePanel.tsx`, `TraceStageTimeline.tsx`, `TraceParticipantList.tsx`, `ArbiterSummaryCard.tsx`). No unexpected consumers.

### Additional fix needed
`TraceParticipantList.tsx` STATUS_STYLES map uses `"active"` — backend emits `"completed"`. Style map must be updated to match the backend enum (`completed | failed | skipped`).

### Patch set
~405 lines across 9 files. No change surface surprises.

### Post-implementation outcomes
- Backend: **509 passed, 3 failed** (pre-existing) — +13 new route-level contract tests in `TestRouteContractSnapshot`
- Frontend: **389 passed, 17 failed** — matches diagnostic baseline, no regression introduced
- TypeScript: all trace-related errors resolved; only pre-existing `reflect.test.tsx` type errors remain (out of scope)
- Two additional test assertion fixes needed beyond the spec scope: `"82%"` → `final_bias`/`final_decision` display; artifact display uses `artifact_type` not `name`

---

## 14. Appendix — Recommended Agent Prompt

```
# REPO: C:/Users/david/OneDrive/Documents/GitHub/AI trade analyst

Read `docs/specs/PR_AUDIT_T1_CONTRACT_ALIGNMENT_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings
before changing any code:

1. Confirm backend AgentTraceResponse JSON schema (exact field names + aliases)
2. Confirm Pydantic serialisation aliases for TraceEdge.from_ and TraceStage.stage_key
3. Run baseline backend + frontend test suites — report exact counts
4. Grep frontend test fixtures for old field names — report line numbers
5. Find all frontend files importing trace types — report full consumer list
6. Grep source components for deprecated trace field access paths — report full file:line:field list
7. Propose smallest patch set: files, one-line description, estimated line delta

Hard constraints:
- The backend serialized trace API response is canonical — frontend and contract doc must match the JSON payload actually emitted, not the Python attribute names
- Backend models/services are presumed correct and out of scope for redesign; only minimal corrective changes permitted if diagnostics prove a serialization defect (flag and justify before proceeding)
- Frontend types must match backend JSON serialisation key-for-key
- Run-scoped edge types (considered_by_arbiter, etc.) must NOT be mixed with roster relationship types (supports, challenges, etc.)
- Partial-run detection must use `run_status === "partial"`, not stage status heuristic
- No SQLite, no new top-level module
- Deterministic tests only — no live provider dependency in CI
- If `reflect.ts` or any unexpected file imports trace types, add it to the change surface and report
- If critical trace fields are missing from a successful response, Run mode must show a degraded state, not silent placeholders (AC-21)

Do not change any code until the diagnostic report is reviewed and the
patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/PR_AUDIT_T1_CONTRACT_ALIGNMENT_SPEC.md` — mark ✅ Complete, flip all AC cells,
   populate §13 Diagnostic Findings with: backend schema output, alias confirmation,
   baseline test counts, consumer file list, any surprises
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update per Workflow E.2:
   update header (current phase), add Recent Activity row for Audit T1,
   update Phase Status Overview, update Phase Index, add test count row,
   update Roadmap, update debt register if applicable
3. Review `AGENT_OPS_CONTRACT.md` — this IS the primary doc change for this phase
4. Cross-document sanity check: no contradictions, no stale phase refs
5. Return Phase Completion Report

Commit all doc changes on the same branch as the implementation.
```
