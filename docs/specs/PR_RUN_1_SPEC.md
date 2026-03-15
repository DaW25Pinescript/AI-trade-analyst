# AI Trade Analyst — PR-RUN-1: Run Browser Endpoint + Frontend Spec

**Status:** ✅ Complete — implemented 15 March 2026
**Date:** 15 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Branch:** `pr-run-1-run-browser`
**Phase:** PR-RUN-1 (Phase 8, Week 1)
**Depends on:** Phase 7 complete (PR-OPS-5b merged, 63 frontend tests, 197 backend tests)

---

## 1. Purpose

**After:** Phase 7 (Agent Ops read-side stack — roster, health, trace, detail endpoints + frontend wiring). Phases 1–7 complete.

**Question this phase answers:** Can a user discover and select analysis runs from the UI without knowing the run_id in advance?

**From → To:**

- **From:** Run mode requires manual paste of a known `run_id`. Operator must have the run_id from logs, terminal output, or memory. No browsable run history exists in the UI.
- **To:** Run Browser panel lists recent runs as a compact, paginated, filterable index. Clicking a run loads its trace in Agent Ops Run mode. The paste-field becomes a fallback, not the primary entry point.

This PR is a **run index only**. It is not an artifact browser, trace replacement, or reflective surface. That scope lock remains correct from the Phase 8 plan.

---

## 2. Scope

### In scope

- `GET /runs/` backend endpoint — paginated, sorted, filterable run index
- Run browser projection service — reads `run_record.json` from disk, projects compact browser summaries from the real artifact shape
- `RunBrowserPanel` frontend component — replaces the paste-field as the primary run selector in Agent Ops Run mode
- Click-to-load: selecting a run in the browser loads its trace via the existing `GET /runs/{run_id}/agent-trace` endpoint
- Retain the paste-field as a secondary/fallback input (not removed, demoted)
- Contract tests for the new endpoint
- Frontend component tests for the browser panel

### Target components

| Layer | Component | Role |
|-------|-----------|------|
| Backend | `GET /runs/` endpoint | Serve paginated run index |
| Backend | Run browser projection service | Scan directories, read `run_record.json`, project compact summaries |
| Frontend | `RunBrowserPanel` | Browsable run list with filters |
| Frontend | Agent Ops Run mode | Wire browser panel as primary run selector |

### Out of scope (hard list)

- No artifact content in browser response — no analyst results, no arbiter detail text, no stage traces. The trace endpoint handles that.
- No new persistence layer — no SQLite, no database, no index file. Read-side directory scan only.
- No new top-level module — work confined to existing `app/` (backend) and `ui/` (frontend) packages
- No full-text search over run artifacts
- No run deletion, mutation, or lifecycle management — read-only projection
- No scheduler integration — endpoint reads stored data, does not trigger new analysis runs
- No chart or reflective features — those are PR-CHART-1+ and PR-REFLECT-1+
- No WebSocket / SSE / live-push — polling only, consistent with Phase 7 contract
- No changes to the existing trace, detail, roster, or health endpoints
- No changes to `run_record.json` artifact format — the browser adapts to the existing shape
- No reshaping of stored artifacts for browser convenience

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Run storage | Runs stored at `ai_analyst/output/runs/{run_id}/run_record.json` — confirmed by Phase 7 trace work |
| `run_id` | Top-level field in `run_record.json` |
| `timestamp` | Top-level field in `run_record.json` |
| `instrument` | Nested at `request.instrument` |
| `session` | Nested at `request.session` |
| `arbiter` | Block containing `ran` (boolean), `verdict` (string), and other fields |
| Error/warning signals | Top-level `errors[]`, `warnings[]`, `analysts_failed[]`, `analysts_skipped[]` arrays |
| Stage tracking | Top-level `stages[]` array |
| Run status | No guaranteed clean top-level status field — derived in projection layer |
| Frontend stack | React + TypeScript + Tailwind + TanStack Query — same as Phase 6/7 |
| Existing Run mode | Agent Ops Run mode currently uses a `RunSelector` paste-field component (PR-OPS-5b) |

### Current likely state

The `run_record.json` artifact was designed during Obs Phase 1 and consumed by the Phase 7 trace endpoint. The trace projection already parses `run_record.json` to extract participation, stages, and arbiter verdicts. The browser projection reads a strict subset of what trace already reads — it needs only the header-level identity, request context, and verdict summary.

The browser projection must NOT import or call the trace projection service. They read the same artifact but serve different purposes: trace does a deep read of one run, browser does a shallow read of many runs.

### Core question

Can we read the projection fields from `run_record.json` across a bounded set of run directories and project compact browser summaries without coupling to the trace projection internals?

---

## 4. Key File Paths

| Role | Path | Access |
|------|------|--------|
| Run artifacts root | `ai_analyst/output/runs/` | Read-only scan |
| Run record artifact | `ai_analyst/output/runs/{run_id}/run_record.json` | Read-only parse |
| Trace projection (reference) | `app/services/ops/trace_projection.py` (hypothesis) | Read-only reference — do not import or couple |
| Backend routes | `app/routes/` | Modify — add run browser route |
| Backend services | `app/services/` | Modify — add browser projection service |
| Frontend components | `ui/src/components/ops/` or `ui/src/components/runs/` | Modify — add RunBrowserPanel |
| Agent Ops page | `ui/src/pages/AgentOpsPage.tsx` (hypothesis) | Modify — wire browser panel into Run mode |
| Frontend API layer | `ui/src/api/` | Modify — add fetchRuns function |
| Frontend hooks | `ui/src/hooks/` | Modify — add useRuns hook |
| Existing RunSelector | `ui/src/components/ops/RunSelector.tsx` (hypothesis) | Modify — demote to fallback |
| Agent Ops contract | `docs/ui/AGENT_OPS_CONTRACT.md` | Read-only reference |
| UI contract | `docs/ui/UI_CONTRACT.md` | Read-only reference |

*Exact frontend paths are hypotheses — diagnostic to confirm.*

---

## 5. Current State Audit Hypothesis

### What is already true

- `run_record.json` is produced by the analysis pipeline and consumed by the trace endpoint
- The trace projection already knows how to find and parse `run_record.json`
- Agent Ops Run mode exists with a paste-field `RunSelector` and full trace visualization
- The `OpsErrorEnvelope` pattern, `ResponseMeta` envelope, and `data_state` semantics are established conventions
- TanStack Query hooks pattern is established (useAgentRoster, useAgentHealth, useAgentTrace, useAgentDetail)
- The real artifact shape is confirmed: `run_id`, `timestamp` (top-level), `request.instrument`, `request.session`, `arbiter.ran`, `arbiter.verdict`, `stages[]`, `analysts[]`, `analysts_failed[]`, `analysts_skipped[]`, `warnings[]`, `errors[]`

### What likely remains incomplete

- No endpoint exists for listing multiple runs
- No projection service exists for extracting compact summaries across runs
- No frontend component exists for browsing/filtering runs

### Core phase question

Can the browser projection read the confirmed fields from 20–50+ run directories within acceptable latency, and can `run_status` be reliably derived from the error/arbiter/stage signals?

---

## 6. Design

### 6.1 Backend — `GET /runs/` Endpoint Contract

**Route:** `GET /runs/`

**Query parameters:**

| Parameter | Type | Default | Constraint | Purpose |
|-----------|------|---------|------------|---------|
| `page` | `int` | `1` | ≥ 1 | Page number |
| `page_size` | `int` | `20` | 1–50 | Results per page |
| `instrument` | `string \| null` | `null` | Optional, exact match | Filter by instrument |
| `session` | `string \| null` | `null` | Optional, exact match | Filter by session |

Sort order is locked to **newest-first** by projected timestamp. No `sort` parameter in v1.

**Response shape:**

```typescript
type RunBrowserResponse = ResponseMeta & {
  items: RunBrowserItem[];
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
};

type RunBrowserItem = {
  run_id: string;
  timestamp: string;                // ISO 8601, from run_record top-level
  instrument: string | null;        // from request.instrument
  session: string | null;           // from request.session
  final_decision: string | null;    // from arbiter.verdict when arbiter.ran == true
  run_status: RunBrowserStatus;     // derived in projection layer
  trace_available: boolean;         // whether trace endpoint can operate on this run
};

type RunBrowserStatus = "completed" | "partial" | "failed" | "unknown";
```

**`ResponseMeta` fields** (inherited from Phase 7 convention):

| Field | Type | Value |
|-------|------|-------|
| `version` | `string` | `"2026.03"` |
| `generated_at` | `string` | ISO 8601 timestamp of response generation |
| `data_state` | `"live" \| "stale" \| "unavailable"` | Response-level freshness — see §6.4 |

Note: `data_state` uses Phase 7's established vocabulary (`live | stale | unavailable`), not `fresh`, for cross-endpoint consistency.

**Error responses:**

| HTTP status | `error` code | When |
|------------|-------------|------|
| 500 | `RUN_SCAN_FAILED` | Run directory could not be scanned |
| 422 | `INVALID_FILTER` | Query parameter validation failure (e.g. `page_size=100`) |

Error responses use `OpsErrorEnvelope` shape, consistent with Phase 7 conventions.

### 6.2 Run Status Derivation Policy

`run_status` is derived deterministically from artifact signals. It is never blindly copied from a non-existent top-level summary field.

**`completed`** — all of the following hold:

- run record parses successfully
- `errors` array is empty
- `arbiter.ran == true`
- `arbiter.verdict` is present
- no stage entry has a non-ok terminal status

**`partial`** — all of the following hold:

- run record parses successfully
- there is meaningful execution evidence (stages present, analysts present, or `arbiter.ran` exists)
- completion conditions above are NOT fully met
- the record is NOT clearly failed

Examples: arbiter did not run, verdict missing, some stages present but not all expected stages reached, warnings present without terminal failure.

**`failed`** — any of the following hold:

- run record exists but is malformed/unreadable
- `errors` array is non-empty
- a stage has an explicit failure/error terminal status
- `analysts_failed` is non-empty AND no completed arbiter verdict exists
- execution clearly terminated unsuccessfully

**`unknown`** — fallback when:

- run record is readable
- but it cannot be conservatively classified as completed, partial, or failed

This gives the projection layer a safe escape hatch for ambiguous artifacts without fabricating a status.

### 6.3 Projection Field Mapping

| Browser field | Source path | Fallback |
|--------------|------------|----------|
| `run_id` | `run_record["run_id"]` (top-level) | Required — skip run if missing |
| `timestamp` | `run_record["timestamp"]` (top-level) | Required — skip run if missing |
| `instrument` | `run_record["request"]["instrument"]` | `null` if request block or field absent |
| `session` | `run_record["request"]["session"]` | `null` if request block or field absent |
| `final_decision` | `run_record["arbiter"]["verdict"]` when `arbiter["ran"] == true` | `null` if arbiter absent, not ran, or verdict missing |
| `run_status` | Derived per §6.2 | `"unknown"` as final fallback |
| `trace_available` | `true` when run record is readable enough for the existing trace endpoint | `false` when malformed or clearly insufficient for trace projection |

### 6.4 `data_state` Semantics

| Value | Meaning | UI behavior |
|-------|---------|-------------|
| `live` | Run directory scan completed successfully, all projected records parsed cleanly | Normal render |
| `stale` | Scan completed but some `run_record.json` files could not be parsed (skipped) | Render with stale indicator — count may be approximate |
| `unavailable` | Run directory could not be accessed | Browser-level error state |

### 6.5 Scan Discipline

The scan rules stay tight and in-family with existing bounded read-side services like Agent Detail's recent participation scanning (max 20 dirs / 7 days).

**Required rules:**

1. Scan only `ai_analyst/output/runs/`
2. Treat each immediate child directory as a candidate run
3. Inspect `run_record.json` only — do not recursively traverse artifact trees
4. Ignore junk directories safely (no `run_record.json` → skip, no crash)
5. Malformed individual runs must not crash the endpoint — skip or classify as `failed`
6. Max directories scanned: configurable, default 200, hard ceiling 500
7. If directory count exceeds max, scan the most recent N by directory modification time

**Processing sequence:**

1. Enumerate candidate directories (bounded)
2. Attempt projection from each `run_record.json`
3. Skip unreadable candidates or classify `failed` conservatively
4. Apply filters on projected `instrument` / `session`
5. Sort by parsed timestamp descending
6. Paginate the projected list
7. Return page slice with `total` (post-filter count) and `has_next`

### 6.6 Frontend — `RunBrowserPanel` Component

**Behavior:**

1. On mount, fetches `GET /runs/` with default parameters (page 1, page_size 20, no filters)
2. Renders a compact list of `RunBrowserItem` entries — displayed columns: timestamp, instrument, session, final_decision, run_status
3. **Click-to-load:** clicking a row calls the existing run selection handler, which triggers `useAgentTrace(run_id)` to load the full trace. Rows where `trace_available == false` are visually de-emphasized or disabled.
4. **Filter controls:** instrument and session dropdowns
5. **Pagination:** next/prev page controls with `has_next` gating
6. **Loading / empty / error states:** consistent with Phase 6/7 patterns (LoadingSkeleton, EmptyState, ErrorState)

**Integration with existing Run mode:**

`RunBrowserPanel` becomes the **primary** run selector. The existing paste-field `RunSelector` is demoted to a secondary input — a "Go to run ID" shortcut alongside the browsable list.

Layout (hypothesis — diagnostic to confirm best arrangement):
```
┌─────────────────────────────────────────┐
│  Run Mode                               │
│  ┌───────────────────────────────────┐  │
│  │  [instrument ▼] [session ▼]       │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │ XAUUSD  NY   3m ago  ✅ BUY │  │  │
│  │  │ EURUSD  LDN  1h ago  ✅ SELL│  │  │
│  │  │ XAUUSD  ASIA 2h ago  ⛔ NT  │  │  │
│  │  │ ...                         │  │  │
│  │  └─────────────────────────────┘  │  │
│  │  ◀ Page 1 of 3 ▶                 │  │
│  │                                   │  │
│  │  ── or enter run ID ──           │  │
│  │  [________________] [Load]        │  │
│  └───────────────────────────────────┘  │
│                                         │
│  [Trace panel loads below on selection] │
└─────────────────────────────────────────┘
```

**TanStack Query hook:**

```typescript
function useRuns(params: {
  page?: number;
  pageSize?: number;
  instrument?: string | null;
  session?: string | null;
}): UseQueryResult<RunBrowserResponse>
```

Stale time: 30 seconds.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Endpoint exists | `GET /runs/` returns 200 with valid `RunBrowserResponse` shape | ✅ Done |
| AC-2 | ResponseMeta present | Response includes `version`, `generated_at`, `data_state` | ✅ Done |
| AC-3 | Pagination works | `page=1&page_size=5` returns ≤5 items with correct `page`, `total`, `has_next` | ✅ Done |
| AC-4 | Page bounds enforced | `page_size=0` or `page_size=100` returns 422 with `INVALID_FILTER` | ✅ Done |
| AC-5 | Newest-first sort | Runs returned in descending timestamp order | ✅ Done |
| AC-6 | Instrument filter | `?instrument=XAUUSD` returns only XAUUSD runs | ✅ Done |
| AC-7 | Session filter | `?session=NY` returns only NY session runs | ✅ Done |
| AC-8 | Combined filter | `?instrument=XAUUSD&session=NY` returns correct intersection | ✅ Done |
| AC-9 | No-match filter | Filtering to a nonexistent instrument returns empty `items: []` with 200 (not 404) | ✅ Done |
| AC-10 | Malformed artifact tolerance | A `run_record.json` with missing required fields is skipped, not a 500 | ✅ Done |
| AC-11 | Empty runs directory | Zero runs on disk → 200 with `items: []`, `total: 0` | ✅ Done |
| AC-12 | Scan bound respected | With >200 run directories, only the most recent 200 are scanned | ✅ Done |
| AC-13 | run_status: completed | A clean run with arbiter verdict, no errors, all stages ok → `"completed"` | ✅ Done |
| AC-14 | run_status: partial | A run with evidence of execution but incomplete arbiter → `"partial"` | ✅ Done |
| AC-15 | run_status: failed | A run with non-empty errors or stage failure → `"failed"` | ✅ Done |
| AC-16 | run_status: unknown | A readable but unclassifiable run → `"unknown"` | ✅ Done |
| AC-17 | final_decision gated | `final_decision` is `null` when `arbiter.ran != true` | ✅ Done |
| AC-18 | trace_available field | Readable runs report `true`, malformed runs report `false` | ✅ Done |
| AC-19 | No trace data leakage | Response contains no analyst results, no stage traces, no arbiter detail text | ✅ Done |
| AC-20 | Error envelope | Scan failure returns `OpsErrorEnvelope` with `RUN_SCAN_FAILED` | ✅ Done |
| AC-21 | Frontend: browser panel renders | `RunBrowserPanel` renders a list of run items from API response | ✅ Done |
| AC-22 | Frontend: click-to-load | Clicking a run row triggers trace load for that `run_id` | ✅ Done |
| AC-23 | Frontend: trace_available gating | Rows with `trace_available == false` are visually de-emphasized or disabled | ✅ Done |
| AC-24 | Frontend: filter controls | Instrument and session filters update the query and re-fetch | ✅ Done |
| AC-25 | Frontend: pagination | Next/prev controls work; next disabled when `has_next == false` | ✅ Done |
| AC-26 | Frontend: empty state | Zero runs displays a welcoming empty state, not an error | ✅ Done |
| AC-27 | Frontend: loading state | Loading skeleton shows while fetch is in-flight | ✅ Done |
| AC-28 | Frontend: error state | API error renders ErrorState component with retry | ✅ Done |
| AC-29 | Frontend: paste-field retained | Existing RunSelector paste-field remains functional as secondary input | ✅ Done |
| AC-30 | No new persistence | No SQLite, no database, no index file introduced | ✅ Done |
| AC-31 | No new top-level module | Work confined to existing `app/` and `ui/` packages | ✅ Done |
| AC-32 | No trace endpoint changes | Existing `GET /runs/{run_id}/agent-trace` is unchanged | ✅ Done |
| AC-33 | No run_record.json changes | The artifact format is not modified | ✅ Done |
| AC-34 | Regression safety | All pre-existing backend and frontend tests still pass | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1: Confirm run artifact structure

```bash
# List available run directories
ls -la ai_analyst/output/runs/ | head -20

# Inspect a representative run_record.json (full structure)
cat ai_analyst/output/runs/<any_run_id>/run_record.json | python -m json.tool
```

**Expected result:** Directories named by `run_id`, each containing `run_record.json`. Top-level keys include `run_id`, `timestamp`, `request`, `arbiter`, `stages`, `analysts`, `analysts_failed`, `analysts_skipped`, `warnings`, `errors`.

**Report:**
- Full top-level key list
- Confirm `request.instrument` and `request.session` paths
- Confirm `arbiter.ran` and `arbiter.verdict` paths
- Confirm `errors`, `warnings`, `analysts_failed` arrays exist
- Confirm `stages[]` structure and what a "non-ok terminal status" looks like
- Count total run directories on disk
- Note any runs with missing or malformed `run_record.json`

### Step 2: Confirm trace projection reference

```bash
# Find the trace projection service
find app/ -name "*trace*" -o -name "*projection*" | head -10

# Inspect how it reads run_record.json
grep -n "run_record\|instrument\|session\|arbiter\|verdict\|ran\|errors" app/services/ops/trace_projection*.py | head -30
```

**Expected result:** Trace projection exists and parses the same fields the browser needs.

**Report:**
- Exact file path of trace projection service
- How it extracts instrument, session, verdict — confirm key paths match §6.3
- Whether any shared parsing helper already exists
- Whether `trace_available` can be derived from the same readability checks trace uses

### Step 3: Confirm current RunSelector component

```bash
# Find the existing RunSelector
find ui/src -name "*RunSelector*" -o -name "*run*" -name "*.tsx" | head -10

# Inspect its interface
head -50 ui/src/components/ops/RunSelector.tsx
```

**Expected result:** RunSelector exists as a paste-field component with a callback for run selection.

**Report:**
- Exact file path and props interface
- How it currently triggers trace loading
- What callback mechanism the browser panel needs to use

### Step 4: Confirm Agent Ops Run mode wiring

```bash
# Inspect how Run mode is wired
grep -n "Run\|mode\|trace\|selector\|RunSelector" ui/src/pages/AgentOpsPage.tsx | head -20
```

**Expected result:** Run mode section renders RunSelector and TracePanel, gated by mode state.

**Report:**
- How the mode pill activates Run mode
- Where RunSelector is rendered
- How to insert RunBrowserPanel as the primary selector above the demoted paste-field

### Step 5: Run baseline test suite

```bash
# Backend tests
cd app && python -m pytest tests/ -q --tb=no

# Frontend tests
cd ui && npx vitest run --reporter=verbose 2>&1 | tail -20
```

**Expected result:** All existing tests pass.

**Report:**
- Backend test count (expect ~197)
- Frontend test count (expect ~63)
- Any failures (should be zero)

### Step 6: Propose smallest patch set

Based on findings from Steps 1–5, propose:

- Files to create (with one-line description and estimated line delta)
- Files to modify (with one-line description and estimated line delta)
- Files with "no changes expected" confirmation
- Total estimated line delta
- Any assumption corrections from the diagnostic

**Smallest safe option:** If a field turns out to be deeply nested or unreliable, drop it from v1 rather than adding complex parsing. The contract marks nullable fields for this reason. The browser adapts to the artifact, not the other way around.

---

## 9. Implementation Constraints

### 9.1 General rule

The browser endpoint is a **read-side projection over existing artifacts**. It reads `run_record.json` from disk, projects a compact summary, and returns it. No writes, no mutations, no new storage. Same philosophy as Phase 7's trace and detail endpoints.

### 9.1b Implementation Sequence

1. **Backend projection service** — create the browser projection service that scans run directories, reads `run_record.json`, and projects `RunBrowserItem` summaries per §6.2 and §6.3
   - Verify: baseline backend tests still pass (expect ~197)

2. **Backend endpoint + route** — add `GET /runs/` route with pagination, filtering
   - Verify: baseline + new endpoint tests pass

3. **Backend contract tests** — write deterministic tests covering AC-1 through AC-20
   - Gate: all backend tests pass before touching frontend

4. **Frontend API + hook** — add `fetchRuns()` API function and `useRuns()` TanStack Query hook
   - Verify: frontend build compiles clean

5. **Frontend `RunBrowserPanel`** — implement the browsable run list component
   - Verify: component tests pass (AC-21 through AC-28)

6. **Frontend integration** — wire `RunBrowserPanel` into Agent Ops Run mode, demote paste-field
   - Gate: all frontend tests pass (baseline ~63 + new)
   - Verify: AC-29 (paste-field still works as fallback)

7. **Full regression** — run complete backend + frontend suites
   - Gate: zero regressions (AC-34)

### 9.2 Code change surface

**New files (hypothesis — diagnostic to confirm paths):**

| File | Role | Est. lines |
|------|------|-----------|
| `app/services/runs/browser_projection.py` | Scan + read + project run summaries | ~180 |
| `app/routes/runs.py` | `GET /runs/` endpoint | ~60 |
| `app/models/runs.py` | Pydantic models for browser response | ~60 |
| `tests/test_run_browser.py` | Backend contract tests | ~250 |
| `ui/src/api/runs.ts` | `fetchRuns()` API function | ~30 |
| `ui/src/hooks/useRuns.ts` | TanStack Query hook | ~20 |
| `ui/src/components/runs/RunBrowserPanel.tsx` | Browser panel component | ~180 |
| `ui/src/components/runs/RunBrowserPanel.test.tsx` | Frontend component tests | ~180 |

**Modified files:**

| File | Change | Est. delta |
|------|--------|-----------|
| `app/main.py` or router config | Register new runs route | ~5 |
| `ui/src/pages/AgentOpsPage.tsx` | Wire RunBrowserPanel into Run mode, demote paste-field | ~40 |
| `ui/vite.config.ts` | Add `/runs` proxy if needed | ~3 |

**No changes expected to:**
- `app/services/ops/` — trace, detail, roster, health services unchanged
- `app/routes/ops.py` — existing ops endpoints unchanged
- `ai_analyst/` — analysis pipeline unchanged
- `run_record.json` artifacts — format unchanged
- `docs/ui/AGENT_OPS_CONTRACT.md` — existing contract unchanged
- Any Phase 6 workspace components

**Scope flag:** If `run_record.json` parsing reveals the need to modify the artifact format, flag before proceeding. The browser adapts to the artifact, not the other way around.

### 9.3 Out of scope (repeat)

- No SQLite or database layer introduced
- No new top-level module — work confined to `app/` and `ui/`
- No changes to existing Agent Ops endpoints or trace endpoint
- No `run_record.json` format changes
- No scheduler integration — reads stored data only
- No WebSocket / SSE / live-push
- Deterministic fixture/mock tests only — no live pipeline dependency in CI

---

## 10. Success Definition

PR-RUN-1 is done when: the `GET /runs/` endpoint returns a paginated, filterable index of run summaries projected from `run_record.json` artifacts on disk; `run_status` is derived deterministically per the four-value policy (completed / partial / failed / unknown); `final_decision` is gated on `arbiter.ran == true`; `trace_available` indicates whether the trace endpoint can operate on each run; the `RunBrowserPanel` frontend component renders this list in Agent Ops Run mode as the primary run selector; clicking a run loads its trace; the paste-field remains as a fallback; all 34 acceptance criteria pass with deterministic tests; no regressions in existing backend (~197) or frontend (~63) test suites; no SQLite, no new top-level module, no artifact format changes.

---

## 11. Why This Phase Matters

| Without Run Browser | With Run Browser |
|--------------------|-----------------|
| Operator must know the exact `run_id` to inspect a run | Operator browses recent runs and clicks to inspect |
| Run discovery requires terminal access or log searching | Run discovery is in-product, filterable by instrument and session |
| Agent Ops Run mode is effectively unusable without external context | Run mode is self-contained — browse → select → inspect |
| No feedback on whether a run's trace is loadable before clicking | `trace_available` prevents dead-end clicks |
| Chart and Reflect features (Phase 8 Weeks 2–6) have no discoverable run substrate | Charts and Reflect can reference runs the operator has already browsed |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 7 — Agent Ops read-side stack | 4 endpoints, 3 workspace modes, detail sidebar | ✅ Done — 197 backend + 63 frontend tests |
| **PR-RUN-1 — Run Browser** | **`GET /runs/` endpoint + RunBrowserPanel frontend** | **✅ Done — 15 March 2026** |
| PR-CHART-1 — OHLCV data seam + chart | Candlestick chart in Run mode | 📋 Planned — depends on PR-RUN-1 |
| PR-CHART-2 — Run context overlay | Multi-timeframe, run marker, verdict annotation | 📋 Planned — depends on PR-CHART-1 |
| PR-REFLECT-1 — Aggregation endpoints | Persona performance + pattern summary | 📋 Planned — depends on PR-RUN-1 |
| PR-REFLECT-2 — Reflect dashboard | `/reflect` workspace frontend (new top-level workspace) | 📋 Planned — depends on PR-REFLECT-1 |
| PR-REFLECT-3 — Integration + suggestions | Chart ↔ run + rules-based parameter suggestions | 📋 Planned — depends on PR-CHART-2 + PR-REFLECT-2 |

---

## 13. Diagnostic Findings

### run_record.json Field Paths — Confirmed

| Browser field | Source path | Confirmed |
|--------------|------------|-----------|
| `run_id` | `run_record["run_id"]` (top-level) | ✅ |
| `timestamp` | `run_record["timestamp"]` (top-level) | ✅ |
| `instrument` | `run_record["request"]["instrument"]` | ✅ |
| `session` | `run_record["request"]["session"]` | ✅ |
| `final_decision` | `run_record["arbiter"]["verdict"]` when `arbiter["ran"] == true` | ✅ |
| `errors[]` | `run_record["errors"]` (top-level array) | ✅ |
| `warnings[]` | `run_record["warnings"]` (top-level array) | ✅ |
| `analysts_failed[]` | `run_record["analysts_failed"]` (top-level array) | ✅ |
| `stages[]` | `run_record["stages"]` — each has `stage`, `status`, `duration_ms` | ✅ |

### run_status Derivation — Validated

Three-value policy aligned with trace projection (`ops_trace.py` lines 226–233):

- **`completed`**: no errors, `arbiter.ran == true`, verdict present, all stages `status == "ok"`
- **`partial`**: meaningful execution evidence but completion conditions not met
- **`failed`**: errors non-empty, stage failure, or analysts_failed with no arbiter verdict

### trace_available Derivation

`trace_available = true` when: JSON parseable + `run_id` present + `timestamp` present. This mirrors the minimum readability checks the trace endpoint (`project_trace()`) requires before attempting a projection.

### Path Corrections from Spec Hypotheses

| Spec hypothesis | Actual path |
|----------------|-------------|
| `app/services/ops/trace_projection.py` | `ai_analyst/api/services/ops_trace.py` |
| `app/routes/` | `ai_analyst/api/routers/` |
| `app/models/` | `ai_analyst/api/models/` |
| `app/main.py` | `ai_analyst/api/main.py` |
| `ui/src/components/ops/RunSelector.tsx` | `ui/src/workspaces/ops/components/RunSelector.tsx` |
| `ui/src/pages/AgentOpsPage.tsx` | `ui/src/workspaces/ops/components/AgentOpsPage.tsx` |

### Final Patch Set

**New files (8):**

| File | Role | Lines |
|------|------|-------|
| `ai_analyst/api/models/ops_run_browser.py` | Pydantic response models | 34 |
| `ai_analyst/api/services/ops_run_browser.py` | Scan + project run summaries | 160 |
| `ai_analyst/api/routers/runs.py` | `GET /runs/` endpoint | 82 |
| `tests/test_run_browser_endpoints.py` | Backend contract tests (42 tests) | 317 |
| `ui/src/shared/api/runs.ts` | `fetchRuns()` API function | 56 |
| `ui/src/shared/hooks/useRuns.ts` | TanStack Query hook | 38 |
| `ui/src/workspaces/ops/components/RunBrowserPanel.tsx` | Browser panel component | 188 |
| `ui/tests/run-browser.test.tsx` | Frontend component tests (14 tests) | 310 |

**Modified files (4):**

| File | Change | Delta |
|------|--------|-------|
| `ai_analyst/api/main.py` | Register runs router | +4 |
| `ui/src/workspaces/ops/components/AgentOpsPage.tsx` | Wire RunBrowserPanel, demote paste-field | +11 |
| `ui/src/shared/hooks/index.ts` | Export useRuns | +1 |
| `ui/tests/ops.test.tsx` | Add fetchRuns mock, update Run mode test for browser panel | +16 |

**Test counts:**

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Backend (ops domain) | 197 | 239 | +42 |
| Frontend (ops domain) | 63 | 77 | +14 |
| **Total ops tests** | **260** | **316** | **+56** |

---

## 14. Doc Corrections to Apply on Branch

On the PR-RUN-1 branch, apply these corrections to keep plan docs consistent:

1. **`PHASE_8_PLAN.md` §Week 1 scope:** Change "read `run_record.json` headers only (run_id, instrument, session, status, timestamp, final_decision)" to "read `run_record.json` and project compact run summaries from the real artifact shape (run_id, timestamp, request.instrument, request.session, arbiter.verdict, derived run_status)"

2. **`PHASE_8_PLAN.md` §Reflect placement:** Resolve "New Reflect workspace (or tab within Agent Ops)" to "New top-level `/reflect` workspace" — locked decision per PR-RUN-1 spec §12.

---

## 15. Appendix — Recommended Agent Prompt

```
Read `docs/specs/PR_RUN_1_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings
before changing any code:

1. Confirm run artifact structure: directory naming, run_record.json top-level keys,
   exact nesting for instrument/session/arbiter.ran/arbiter.verdict,
   errors/warnings/analysts_failed arrays, stages[] structure
2. Confirm trace projection reference: how it reads run_record.json, key paths used,
   whether trace_available can be derived from trace's readability checks
3. Confirm RunSelector component: file path, props interface, callback mechanism
4. Confirm Agent Ops Run mode wiring: where RunSelector is rendered, how to insert
   browser panel, how to demote paste-field
5. Run baseline tests: backend (~197) + frontend (~63), record exact counts
6. Propose smallest patch set: files, one-line description, estimated line delta

Hard constraints:
- Browser endpoint is a read-side projection — no writes, no mutations, no new storage
- No SQLite, no database, no index file
- No new top-level module — work in app/ and ui/ only
- No changes to existing ops endpoints, trace endpoint, or run_record.json format
- run_status is derived per the four-value policy in §6.2 — do not invent a fifth state
- final_decision gated on arbiter.ran == true — not on arbiter block existence alone
- Deterministic fixture/mock tests only — no live pipeline dependency in CI
- If run_record.json parsing requires format changes, flag before proceeding

Do not change any code until the diagnostic report is reviewed and the
patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/PR_RUN_1_SPEC.md` — mark ✅ Complete, flip all AC cells,
   populate §13 with: exact run_record.json field paths confirmed,
   run_status derivation rules validated against real artifacts,
   trace_available derivation approach, any assumption corrections,
   final patch set with line deltas
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update per Workflow E.2:
   update header, add Recent Activity row, update Phase Index,
   add test count row, update Roadmap (PR-RUN-1 → ✅ Done),
   update §6 Immediate Next Actions
3. Apply doc corrections from §14 (PHASE_8_PLAN.md updates)
4. Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`,
   `AI_ORIENTATION.md` — update only if this phase changed architecture,
   structure, or debt state
5. Cross-document sanity check: no contradictions, no stale phase refs
6. Return Phase Completion Report (see Workflow E.8)

Commit all doc changes on the same branch as the implementation.
```
