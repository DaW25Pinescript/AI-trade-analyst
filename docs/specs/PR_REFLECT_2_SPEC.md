# AI Trade Analyst — PR-REFLECT-2: Reflect Workspace Frontend Spec

**Status:** ⏳ Spec drafted — implementation pending
**Date:** 16 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Branch:** `pr-reflect-2-workspace`
**Phase:** PR-REFLECT-2 (Phase 8)
**Depends on:** PR-REFLECT-1 complete (3 endpoints: persona-performance, pattern-summary, run bundle)

---

## 1. Purpose

**After:** PR-REFLECT-1 (Reflect aggregation + bundle endpoints, +11 tests). Three backend endpoints ready: `GET /reflect/persona-performance`, `GET /reflect/pattern-summary`, `GET /reflect/run/{run_id}`.

**Question this phase answers:** Can the operator view cross-run persona performance, pattern distributions, and individual run deep-dives in a dedicated Reflect workspace?

**From → To:**

- **From:** The three Reflect endpoints exist but have no frontend surface. The operator must use the API directly to see aggregation data. There is no `/reflect` route in the UI.
- **To:** A new top-level Reflect workspace provides two tabs: an **Overview** tab showing persona performance and pattern summary tables, and a **Runs** tab with a run history list and inline run detail panel for inspecting artifact bundles. The workspace is table-driven, operator-readable, and read-only.

**What this workspace is:**

Reflect is the AI system's **self-evaluation lab**. It occupies a distinct position from other workspaces:

| Workspace | Role | Focus |
|-----------|------|-------|
| Agent Ops | System health + operator trust | Current state |
| Journal / Review | Decision ledger | Trade outcomes |
| **Reflect** | **AI decision evaluation** | **Historical patterns + deep inspection** |

> **Scope note:** PR-REFLECT-2 is a **descriptive presentation of endpoint outputs**, not an interpretive analysis surface. It displays what PR-REFLECT-1's endpoints return — no additional computation, no outcome tracking, no parameter suggestions, no ML. Those come in later Reflect phases.

---

## 2. Scope

### In scope

- New top-level `#/reflect` route added to the app hash router and navigation
- `ReflectPage` orchestrator component with two-tab navigation (Overview / Runs)
- **Overview tab:** persona performance table + pattern summary table, consuming the two aggregation endpoints
- **Runs tab:** run history list (reusing `GET /runs/` from PR-RUN-1 with existing pagination) + inline run detail panel (consuming `GET /reflect/run/{run_id}`)
- Typed API fetch functions for all three Reflect endpoints
- TanStack Query hooks for the three Reflect endpoints (reuses `useRuns` from PR-RUN-1 for run history)
- View-model adapters normalising backend responses to display models
- Loading, empty, error, stale, below-threshold, 404-on-detail, and all-null-metric states
- Component tests for all new components

### Target components

| Layer | Component | Role |
|-------|-----------|------|
| Frontend | `ReflectPage` | Workspace orchestrator with two-tab navigation |
| Frontend | `PersonaPerformanceTable` | Per-persona stats table with flagged highlighting |
| Frontend | `PatternSummaryTable` | Instrument × session verdict distribution table |
| Frontend | `RunDetailView` | Full artifact bundle inspector |
| Frontend | `UsageSummaryCard` | Token/model/cost display from usage data |
| Frontend | API layer | `fetchPersonaPerformance`, `fetchPatternSummary`, `fetchRunBundle` |
| Frontend | Hooks | `usePersonaPerformance`, `usePatternSummary`, `useRunBundle` |
| Frontend | Adapter | `reflectAdapter.ts` — normalise responses to view models |

### Out of scope (hard list)

- No backend changes — PR-REFLECT-1 endpoints are consumed as-is
- No new backend endpoints
- No additional computation beyond what the endpoints return — display only
- No filter controls on persona performance — deferred to PR-REFLECT-2a (the backend supports filters, but the frontend ships without them in this PR to keep scope tight)
- No outcome tracking or bias accuracy scoring (PR-REFLECT-3+)
- No confidence calibration against outcomes (future phase)
- No parameter suggestions or "what should I change?" (PR-REFLECT-3)
- No decision simulation or "why was this wrong?" (PR-REFLECT-4)
- No chart integration — Reflect does not embed candlestick charts (that's Agent Ops Run mode)
- No config mutation — read-only workspace, no settings, no parameter tweaking
- No WebSocket / SSE / live-push — fetch on mount + manual refresh
- No premature abstraction — no shared analytics component framework
- No changes to other workspace internals (Agent Ops, Journey, Analysis, Journal, Triage)

---

## 3. Repo-Aligned Assumptions

| Area | Assumption | Confidence |
|------|-----------|------------|
| Frontend stack | React + TypeScript + Tailwind + TanStack Query | Confirmed |
| Workspace pattern | `ui/src/workspaces/{name}/` directory with components, adapters | Confirmed |
| Shared components | PanelShell, LoadingSkeleton, EmptyState, ErrorState, StatusPill available | Confirmed — **prop compatibility needs diagnostic** |
| Router | Hash router (`#/reflect`) — same pattern as `#/ops`, `#/journey`, etc. | Confirmed — **exact router file needs diagnostic** |
| API pattern | `apiFetch()` shared JSON client with `OpsErrorEnvelope` parsing | Confirmed |
| TanStack Query | Hooks with stale times, exported cache keys | Confirmed |
| Adapter pattern | View-model adapters normalise backend responses | Confirmed |
| Backend endpoints | `/reflect/persona-performance`, `/reflect/pattern-summary`, `/reflect/run/{run_id}` | Confirmed (PR-REFLECT-1) |
| `useRuns` hook | Available from PR-RUN-1 with pagination support (`page`, `pageSize`, `has_next`) | Confirmed — **semantics need diagnostic** |
| Persona metrics | `override_rate`, `stance_alignment_rate`, `avg_confidence` may be `null` for all personas | Confirmed (PR-REFLECT-1) |

### Runs endpoint contract assumption

The Runs tab relies on these exact fields from `GET /runs/` (PR-RUN-1's `RunBrowserItem`):

| Field | Type | Used for |
|-------|------|----------|
| `run_id` | `string` | Row key + detail fetch |
| `timestamp` | `string` (ISO 8601) | Display column |
| `instrument` | `string \| null` | Display column |
| `session` | `string \| null` | Display column |
| `final_decision` | `string \| null` | Display column |
| `run_status` | `"completed" \| "partial" \| "failed"` | Display column |
| `trace_available` | `boolean` | Not used in Reflect (used in Agent Ops only) |

### Run bundle field contract for detail view

The RunDetailView renders from the `RunBundleResponse`. Field availability:

| Section | Required field | Optional fields | Missing handling |
|---------|---------------|----------------|-----------------|
| Run header | `run_id` (always present) | — | — |
| Verdict | `run_record.arbiter.verdict` | `arbiter.confidence`, `arbiter.method` | "—" for absent optional fields |
| Analyst contributions | `run_record.analysts[].persona` (required per entry) | `status`, `model`, `stance`, `confidence` | "—" for absent optionals |
| Arbiter notes | `run_record.arbiter` | `dissent_summary`, override info | "Not available" if absent |
| Usage summary | `usage_summary` from bundle | all usage fields optional | "Not available" if `usage_summary` is null |
| Artifact status | `artifact_status.*` (always present) | — | Indicators shown for missing/malformed |

### Core question

Can the three Reflect endpoints be consumed by a table-driven frontend workspace that gracefully handles null metrics, below-threshold states, missing artifacts, 404 on detail fetch, and stale data?

---

## 4. Key File Paths

| Role | Path | Access |
|------|------|--------|
| Workspace root (new) | `ui/src/workspaces/reflect/` | Create |
| Page component (new) | `ui/src/workspaces/reflect/components/ReflectPage.tsx` | Create |
| Components (new) | `ui/src/workspaces/reflect/components/*.tsx` | Create |
| Adapters (new) | `ui/src/workspaces/reflect/adapters/reflectAdapter.ts` | Create |
| API functions (new) | `ui/src/shared/api/reflect.ts` | Create |
| Hooks (new) | `ui/src/shared/hooks/useReflect.ts` | Create |
| Tests (new) | `ui/tests/reflect.test.tsx` | Create |
| App router | Diagnostic must confirm exact file | Modify — add `#/reflect` route |
| Navigation component | Diagnostic must confirm exact file | Modify — add Reflect nav link |
| Shared hooks index | `ui/src/shared/hooks/index.ts` | Modify — export new hooks |
| Existing workspaces | `ui/src/workspaces/ops/`, `journey/`, `analysis/`, `journal/` | No changes to internals |
| Existing useRuns hook | `ui/src/shared/hooks/useRuns.ts` | Read-only — reuse, do not modify |

---

## 5. Design

### 5.1 Workspace Structure

The Reflect workspace has **two tabs**:

```
┌─────────────────────────────────────────────────────────────┐
│  Reflect                                                     │
│  [Overview]  [Runs]                                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  (active tab content renders here)                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Overview tab** (default): Persona performance table + pattern summary table — the "dashboard" view showing cross-run intelligence at a glance.

**Runs tab**: Run history list + inline run detail panel — the "drill-down" view for inspecting individual runs via the bundle endpoint.

Tab switching is in-workspace via local state. The diagnostic should check if an existing tab/mode-switch pattern exists in other workspaces (e.g., Agent Ops mode pills) for visual consistency.

### 5.2 Overview Tab — Persona Performance Table

Consumes: `GET /reflect/persona-performance` (no filters in v1 — deferred to PR-REFLECT-2a)

**Displayed columns:**

| Column | Source field | Display format |
|--------|------------|----------------|
| Persona | `display_name` | Text; prefixed with "⚠ " in amber if `flagged` |
| Participation | `participation_rate` | Percentage (e.g. "85%") |
| Skipped | `skip_count` | Integer |
| Failed | `fail_count` | Integer |
| Override Rate | `override_rate` | Percentage or "—" if null |
| Stance Alignment | `stance_alignment_rate` | Percentage or "—" if null |
| Avg Confidence | `avg_confidence` | Decimal (2dp) or "—" if null |

**Flagged visual treatment (LOCKED):** Flagged personas get amber text color on the row + "⚠ " prefix on the persona name. This is consistent with Agent Ops' amber = attention pattern.

**State handling:**

| State | Display |
|-------|---------|
| Loading | LoadingSkeleton |
| `threshold_met: false` | Welcoming message: "Not enough run history yet. Need at least {threshold} runs to show persona statistics." — NOT an error |
| `threshold_met: true` | Table populated |
| `threshold_met: true` but all override/stance/confidence columns are null | Table renders with "—" in those columns — table is still useful with participation/skip/fail |
| `data_state: "stale"` | Stale banner above table: "Some run records could not be parsed — statistics may be based on incomplete data" |
| `data_state: "stale"` + `threshold_met: true` | Both stale banner AND populated table (coexist — partial usability, not collapsed to error) |
| Error | ErrorState with retry |

**Null metric handling (IMPORTANT):** Because `override_rate`, `stance_alignment_rate`, and `avg_confidence` depend on audit log enrichment and may be `null` for ALL personas, the table must render cleanly with these columns showing "—". Do not hide or collapse the table when metrics are sparse. Do not hide columns dynamically based on data availability.

**Scan info footer:** Below the table: "Based on {run_count} runs ({skipped_runs} skipped) from {oldest_run_timestamp} to {newest_run_timestamp}."

### 5.3 Overview Tab — Pattern Summary Table

Consumes: `GET /reflect/pattern-summary`

**Displayed as:** A table with one row per instrument × session bucket.

| Column | Source field | Display format |
|--------|------------|----------------|
| Instrument | `instrument` | Text |
| Session | `session` | Text; row in amber if `flagged` |
| Runs | `run_count` | Integer |
| Verdicts | `verdict_distribution` | Inline: "BUY: 3 (30%), SELL: 2 (20%), NO_TRADE: 5 (50%)" — or "insufficient data ({run_count}/{threshold} runs)" if below threshold |
| NO_TRADE % | `no_trade_rate` | Percentage or "—" if null |

**Flagged visual treatment:** Same as persona table — amber text + "⚠ " prefix on instrument name.

**State handling:**

| State | Display |
|-------|---------|
| Loading | LoadingSkeleton |
| All buckets below threshold | "Not enough run history in any instrument/session combination yet" |
| Mixed (some above, some below) | Above-threshold buckets show data; below-threshold rows show "insufficient data" in Verdicts |
| `data_state: "stale"` | Stale banner |
| Error | ErrorState with retry |

### 5.4 Runs Tab — Run History + Run Detail

**Run History panel (left/top):** Reuses `GET /runs/` via the existing `useRuns` hook from PR-RUN-1. Inherits its pagination behavior (next/prev with `has_next` gating, default page_size 20). Display columns: timestamp, instrument, session, final_decision, run_status.

**useRuns adaptation rule:** The Runs tab may adapt `useRuns` output through a small local adapter in `reflectAdapter.ts` for display formatting, but must NOT modify the shared `useRuns` hook contract or add Reflect-specific parameters to it.

**Run Detail panel (right/bottom):** Consumes `GET /reflect/run/{run_id}`. Shows the full artifact bundle when a run is selected.

**Layout:**

```
┌──────────────────────────────────────────────────────────────┐
│  Runs Tab                                                     │
│  ┌──────────────────────┬───────────────────────────────────┐│
│  │ Run History           │ Run Detail                        ││
│  │                       │                                   ││
│  │ XAUUSD NY 3m ago ✅   │ Verdict: NO_TRADE                ││
│  │ EURUSD LDN 1h ago ✅  │ Arbiter Notes: ...               ││
│  │ XAUUSD ASIA 2h ago ⛔ │ Analyst Contributions:           ││
│  │ ...                   │   - Default Analyst: active       ││
│  │                       │   - Risk Challenger: active       ││
│  │ ◀ Page 1 of 3 ▶      │ Usage Summary:                   ││
│  │                       │   Calls: 5, Tokens: 12k          ││
│  └──────────────────────┴───────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

**Run Detail sections (from bundle):**

1. **Run Header:** run_id, instrument, session, timestamp (from `run_record`)
2. **Verdict:** arbiter verdict, confidence (if present), method (if present) — "—" for absent optionals
3. **Analyst Contributions:** list from `run_record.analysts[]` — persona name (required), status, stance, confidence all optional → "—" if absent
4. **Arbiter Notes:** dissent summary, override information — "Not available" if absent
5. **Usage Summary:** total calls, models used, tokens, cost — "Not available" if `usage_summary` is null
6. **Artifact Status:** indicator showing which artifacts are present/missing/malformed

**State handling:**

| State | Display |
|-------|---------|
| No run selected | "Select a run from the history to inspect its details" |
| Loading detail | LoadingSkeleton in detail panel |
| Bundle loaded, all artifacts present | Full detail sections rendered |
| Bundle loaded, some artifacts missing | Affected sections show "Not available" — other sections still render normally |
| Bundle loaded, `data_state: "stale"` | Stale indicator + still-renderable sections (coexist) |
| Run history empty | Welcoming message: "No analysis runs yet. Runs will appear here after analyses are executed." |
| Bundle 404 (run not found / no longer available) | "This run could not be found. It may have been removed." with option to reselect another run |
| Error loading detail | ErrorState with retry in detail panel — run history still usable |
| Error loading run history | ErrorState with retry in history panel |

### 5.5 Adapter Layer

`reflectAdapter.ts` normalises backend responses to view models:

**Responsibilities:**

- `normalizePersonaPerformance(response)` → view model with formatted percentages, "—" for nulls, flagged indicator
- `normalizePatternSummary(response)` → view model with formatted verdict distributions, per-bucket threshold state
- `normalizeRunBundle(response)` → view model with structured detail sections, artifact status indicators, usage formatting
- `normalizeRunForReflect(runBrowserItem)` → small local adapter for `useRuns` output if formatting differs from Agent Ops presentation (does NOT modify the shared hook)

**Formatting rules:**

- Percentages: multiply by 100, format to 0dp (e.g. `0.85` → `"85%"`)
- Confidence: format to 2dp (e.g. `0.72` → `"0.72"`)
- Null numeric fields: display as `"—"`
- Timestamps: relative format for recency ("3m ago"), absolute on hover or in detail
- `flagged: true`: amber text color + "⚠ " prefix on persona/instrument name

### 5.6 Hook Design

```typescript
// Persona performance — stale time 60s, no filters in v1
function usePersonaPerformance(params?: {
  maxRuns?: number;
}): UseQueryResult<PersonaPerformanceResponse>

// Pattern summary — stale time 60s
function usePatternSummary(params?: {
  maxRuns?: number;
}): UseQueryResult<PatternSummaryResponse>

// Run bundle — stale time 30s, enabled when runId is non-null
function useRunBundle(runId: string | null): UseQueryResult<RunBundleResponse>

// Reuse existing useRuns hook from PR-RUN-1 for run history
// Do NOT modify the shared hook — adapt output through reflectAdapter if needed
```

### 5.7 Navigation Integration

The `#/reflect` route is added to the hash router at the same level as `#/ops`, `#/journey`, `#/analysis`, `#/journal`. A "Reflect" navigation link is added to the app navigation, consistent with existing workspace links.

The diagnostic must confirm the exact router file and navigation component to modify.

---

## 6. Acceptance Criteria

### Workspace Structure

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Route exists | `#/reflect` route renders `ReflectPage` | ⏳ Pending |
| AC-2 | Navigation link | "Reflect" link in app navigation, navigates to `#/reflect` | ⏳ Pending |
| AC-3 | Tab navigation | Overview and Runs tabs switch content within the workspace | ⏳ Pending |
| AC-4 | Default tab | Overview tab is the default on workspace load | ⏳ Pending |
| AC-5 | Existing routes unaffected | All existing workspace routes (`#/ops`, `#/journey`, etc.) still work | ⏳ Pending |

### Overview Tab — Persona Performance

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-6 | Table renders | PersonaPerformanceTable displays persona rows from API response | ⏳ Pending |
| AC-7 | Null metrics | Columns with `null` values display "—", table still renders | ⏳ Pending |
| AC-8 | All-null columns | When ALL personas have null override/stance/confidence, table renders with "—" in every cell of those columns — no column hiding, no layout collapse | ⏳ Pending |
| AC-9 | Flagged highlight | Flagged personas show amber text + "⚠ " prefix | ⏳ Pending |
| AC-10 | Below threshold | `threshold_met: false` → welcoming message, no table | ⏳ Pending |
| AC-11 | Stale banner | `data_state: "stale"` → stale warning banner above table | ⏳ Pending |
| AC-12 | Stale + populated coexist | Stale banner AND populated table render simultaneously | ⏳ Pending |
| AC-13 | Scan info footer | Run count, skipped count, and timestamp range shown below table | ⏳ Pending |
| AC-14 | Loading state | LoadingSkeleton while fetching | ⏳ Pending |
| AC-15 | Error state | ErrorState with retry on API failure | ⏳ Pending |

### Overview Tab — Pattern Summary

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-16 | Table renders | PatternSummaryTable displays instrument × session rows | ⏳ Pending |
| AC-17 | Verdict distribution | Per-bucket verdict breakdown displayed inline | ⏳ Pending |
| AC-18 | Per-bucket threshold | Below-threshold buckets show "insufficient data (N/threshold runs)" | ⏳ Pending |
| AC-19 | Flagged highlight | Flagged buckets show amber text + "⚠ " prefix | ⏳ Pending |
| AC-20 | Loading state | LoadingSkeleton while fetching | ⏳ Pending |
| AC-21 | Error state | ErrorState with retry | ⏳ Pending |

### Runs Tab — Run History + Run Detail

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-22 | Run history renders | Run list displays with timestamp, instrument, session, decision, status | ⏳ Pending |
| AC-23 | Run history pagination | Next/prev controls work, using `useRuns` pagination (has_next gating) | ⏳ Pending |
| AC-24 | Empty run history | Zero runs → welcoming message, not an error | ⏳ Pending |
| AC-25 | Run selection | Clicking a run loads bundle via `GET /reflect/run/{run_id}` | ⏳ Pending |
| AC-26 | Detail: verdict | Arbiter verdict displayed; confidence/method show "—" if absent | ⏳ Pending |
| AC-27 | Detail: analysts | Analyst contributions listed with persona name; status/stance/confidence show "—" if absent | ⏳ Pending |
| AC-28 | Detail: usage | Usage summary displayed or "Not available" if null | ⏳ Pending |
| AC-29 | Detail: artifact status | Missing/malformed artifacts indicated, other sections still render | ⏳ Pending |
| AC-30 | Detail: partial bundle | `data_state: "stale"` on bundle + missing artifacts → stale indicator AND remaining sections both render (coexist) | ⏳ Pending |
| AC-31 | No selection state | "Select a run" placeholder when no run selected | ⏳ Pending |
| AC-32 | Detail: 404 handling | Bundle returns 404 → "Run not found" message with reselection guidance | ⏳ Pending |
| AC-33 | Loading state | LoadingSkeleton in detail panel while bundle fetches | ⏳ Pending |
| AC-34 | Error state | ErrorState with retry in detail panel — history panel still usable | ⏳ Pending |

### API / Adapter / Structural

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-35 | API functions | `fetchPersonaPerformance`, `fetchPatternSummary`, `fetchRunBundle` typed and working | ⏳ Pending |
| AC-36 | TanStack hooks | `usePersonaPerformance`, `usePatternSummary`, `useRunBundle` with stale times | ⏳ Pending |
| AC-37 | Adapter layer | `reflectAdapter.ts` normalises all response shapes | ⏳ Pending |
| AC-38 | Percentage formatting | Rates formatted as percentages (0.85 → "85%") | ⏳ Pending |
| AC-39 | Null display | All nullable fields show "—" when null | ⏳ Pending |
| AC-40 | useRuns not modified | Shared `useRuns` hook contract unchanged; Reflect adapts via local adapter | ⏳ Pending |
| AC-41 | No backend changes | Zero modifications to any backend files | ⏳ Pending |
| AC-42 | No workspace internal changes | Agent Ops, Journey, Analysis, Journal workspace internals unchanged | ⏳ Pending |
| AC-43 | Shared component reuse | Uses existing PanelShell, LoadingSkeleton, EmptyState, ErrorState where appropriate | ⏳ Pending |
| AC-44 | Regression safety | All pre-existing frontend tests pass; pre-existing failure count unchanged | ⏳ Pending |

---

## 7. Pre-Code Diagnostic Protocol

**Do not implement until this diagnostic is reviewed.**

### Step 1: Confirm workspace directory pattern

```bash
ls -la ui/src/workspaces/
ls -la ui/src/workspaces/ops/
ls -la ui/src/workspaces/ops/components/
ls -la ui/src/workspaces/ops/adapters/ 2>/dev/null || echo "No adapters dir"
```

**Report:**
- Exact directory structure for an existing workspace
- Where adapters live relative to components
- Whether hooks are workspace-local or in `ui/src/shared/hooks/`

### Step 2: Confirm router, navigation, and tab patterns

```bash
# Find the app router
grep -rn "Route\|route\|Router\|HashRouter" ui/src/App.tsx ui/src/main.tsx 2>/dev/null | head -15

# Find navigation links
grep -rn "ops\|journal\|journey\|analysis\|nav\|Nav\|sidebar\|Sidebar" ui/src/ --include="*.tsx" -l | head -10

# Find existing tab or mode-switch patterns
grep -rn "mode\|tab\|Tab\|OpsMode\|useState.*mode\|useState.*tab" ui/src/workspaces/ --include="*.tsx" | head -15
```

**Report:**
- Exact router file and how routes are registered
- Exact navigation component and how to add a workspace link
- Whether an existing tab/mode-switch pattern exists that Reflect should follow for visual consistency

### Step 3: Confirm shared component availability and prop compatibility

```bash
find ui/src -name "PanelShell*" -o -name "LoadingSkeleton*" -o -name "EmptyState*" \
  -o -name "ErrorState*" -o -name "StatusPill*" | head -10

# Check props interfaces
grep -n "interface.*Props\|type.*Props" ui/src/shared/components/*.tsx 2>/dev/null | head -20
```

**Report:**
- Which shared components exist and their import paths
- Props interfaces — do they support the states Reflect needs (tables, banners, inline warnings)?
- Any gaps requiring new props or local wrapper components

### Step 4: Inspect useRuns hook semantics

```bash
cat ui/src/shared/hooks/useRuns.ts
```

**Report:**
- Full hook interface (params, return type, stale time, cache key)
- Whether it supports pagination (`page`, `pageSize`, `has_next`)
- Whether output fields match the Runs tab's display needs (§3 contract assumption)
- Any filter or sort capabilities already built in

### Step 5: Confirm Reflect API availability + edge-state examples

```bash
# Test endpoints (adjust port if needed) — or note if mocking required
curl -s http://localhost:8000/reflect/persona-performance | python -m json.tool | head -30
curl -s http://localhost:8000/reflect/pattern-summary | python -m json.tool | head -30
curl -s http://localhost:8000/reflect/run/nonexistent-id 2>&1 | head -10
```

**Report:**
- Whether endpoints are accessible (or note if server not running — tests can mock)
- Sample showing below-threshold persona-performance response (if run_count < 10)
- Sample showing mixed-threshold pattern-summary (some buckets above, some below)
- Sample showing partial bundle (missing optional artifacts)
- Whether null metrics are present across all personas (audit log availability)

### Step 6: Confirm existing API/hook/adapter patterns

```bash
head -30 ui/src/shared/api/runs.ts
head -30 ui/src/shared/hooks/useRuns.ts

find ui/src/workspaces -name "*adapter*" -o -name "*Adapter*" | head -5
head -40 ui/src/workspaces/*/adapters/*.ts 2>/dev/null | head -60
```

**Report:**
- API function pattern (return type, error handling)
- Hook pattern (stale time, enabled flag, cache key export)
- Adapter pattern (normalisation approach, formatting conventions)

### Step 7: Run baseline frontend tests

```bash
cd ui && npx vitest run --reporter=verbose 2>&1 | tail -20
```

**Report:**
- Total test count (expect ~301 from PR-CHART-1)
- Pre-existing failures (expect ~5 journey-related)

### Step 8: Propose smallest patch set

- Files to create (one-line description, estimated line delta)
- Files to modify (one-line description, estimated line delta) — **must name exact router and navigation files**
- "No changes expected" confirmation
- Total estimated delta
- Any deviations from spec (e.g., shared component prop limitations requiring local wrappers)

---

## 8. Implementation Constraints

### 8.1 General rule

The Reflect workspace is a **read-only frontend surface** consuming existing backend endpoints. It displays what the endpoints return — no additional computation, no mutations, no new backend calls.

### 8.1b Implementation Sequence

1. **API layer** — create `fetchPersonaPerformance`, `fetchPatternSummary`, `fetchRunBundle`
   - Verify: frontend build compiles

2. **Hooks** — create `usePersonaPerformance`, `usePatternSummary`, `useRunBundle`
   - Verify: build compiles

3. **Adapter** — create `reflectAdapter.ts` with normalisation functions
   - Verify: adapter unit tests pass

4. **Overview tab components** — `PersonaPerformanceTable` + `PatternSummaryTable`
   - Verify: component tests pass (AC-6 through AC-21)

5. **Runs tab components** — run history list + `RunDetailView` + `UsageSummaryCard`
   - Verify: component tests pass (AC-22 through AC-34)

6. **ReflectPage orchestrator** — two-tab navigation, state management, wiring
   - Verify: page-level tests pass (AC-1 through AC-5)

7. **Router + navigation** — add `#/reflect` route and nav link
   - Gate: all frontend tests pass (baseline + new)
   - Verify: AC-5 (existing routes unaffected)

8. **Full regression** — AC-44
   - Pre-existing failure count unchanged

### 8.2 Code change surface

**New files:**

| File | Role | Est. lines |
|------|------|-----------|
| `ui/src/shared/api/reflect.ts` | API fetch functions for 3 Reflect endpoints | ~40 |
| `ui/src/shared/hooks/useReflect.ts` | 3 TanStack Query hooks | ~40 |
| `ui/src/workspaces/reflect/adapters/reflectAdapter.ts` | View-model normalisation | ~90 |
| `ui/src/workspaces/reflect/components/ReflectPage.tsx` | Workspace orchestrator + two-tab nav | ~70 |
| `ui/src/workspaces/reflect/components/PersonaPerformanceTable.tsx` | Persona stats table | ~100 |
| `ui/src/workspaces/reflect/components/PatternSummaryTable.tsx` | Pattern distribution table | ~90 |
| `ui/src/workspaces/reflect/components/RunDetailView.tsx` | Bundle inspector with sections | ~130 |
| `ui/src/workspaces/reflect/components/UsageSummaryCard.tsx` | Usage display | ~40 |
| `ui/tests/reflect.test.tsx` | Frontend tests | ~220 |

**Modified files:**

| File | Change | Est. delta |
|------|--------|-----------|
| Router config file (diagnostic must confirm) | Add `#/reflect` route | ~5 |
| Navigation component (diagnostic must confirm) | Add "Reflect" nav link | ~5 |
| `ui/src/shared/hooks/index.ts` | Export new hooks | ~3 |

**No changes to:**
- `ai_analyst/` — no backend changes
- `ui/src/workspaces/ops/` — Agent Ops internals unchanged
- `ui/src/workspaces/journey/` — Journey internals unchanged
- `ui/src/workspaces/analysis/` — Analysis internals unchanged
- `ui/src/workspaces/journal/` — Journal internals unchanged
- `ui/src/shared/hooks/useRuns.ts` — shared hook contract unchanged

### 8.3 Out of scope (repeat + negative scope lock)

**Hard constraints:**
- No backend changes — frontend only
- No additional computation — display what endpoints return
- No config mutation — read-only workspace
- No filter controls in v1 — deferred to PR-REFLECT-2a
- No WebSocket / SSE / live-push
- No chart integration
- Deterministic tests only

**No premature abstraction:**
- No shared "analytics dashboard" component framework
- No generic "stat table" reusable across workspaces
- Purpose-built components for Reflect only

**PR-REFLECT-2 does not:**
- Add filter controls (PR-REFLECT-2a)
- Add outcome tracking or bias accuracy (PR-REFLECT-3+)
- Add confidence calibration against outcomes (future)
- Add parameter suggestions (PR-REFLECT-3)
- Add decision simulation (PR-REFLECT-4)
- Add chart overlays or candlestick integration
- Modify existing workspace internals
- Modify the shared `useRuns` hook

---

## 9. Success Definition

PR-REFLECT-2 is done when: the `#/reflect` route renders a Reflect workspace with two tabs (Overview / Runs); the Overview tab displays a persona performance table and pattern summary table consuming PR-REFLECT-1 aggregation endpoints; the Runs tab displays a paginated run history list with a bundle-backed inline detail panel; null metrics display as "—" without breaking table layout even when all metrics are null; below-threshold states show welcoming messages not errors; flagged items show amber text with "⚠ " prefix; stale and partial states coexist with usable content rather than collapsing to error; bundle 404 shows reselection guidance; all 44 acceptance criteria pass with deterministic tests; no backend changes; no changes to other workspace internals; no regressions; no modifications to shared `useRuns` hook.

---

## 10. Why This Phase Matters

| Without Reflect Frontend | With Reflect Frontend |
|-------------------------|----------------------|
| Reflect endpoints require curl/Postman | Operators see cross-run intelligence in-product |
| Persona performance data invisible | "Which analyst gets overridden most?" answered in a table |
| Pattern distributions require API calls | "Which instrument/session produces the most NO_TRADE?" at a glance |
| Run deep-dives require Agent Ops trace (projected view) | Full artifact bundles inspectable from Reflect context |
| System self-evaluation has no surface | Reflect becomes a visible, navigable workspace |

---

## 11. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| PR-RUN-1 — Run Browser | `GET /runs/` + RunBrowserPanel | ✅ Done — +56 |
| PR-CHART-1 — OHLCV seam + chart | Market data endpoint + candlestick chart | ✅ Done — +48 |
| PR-REFLECT-1 — Aggregation endpoints | Persona perf + pattern summary + run bundle | ✅ Done — +11 |
| **PR-REFLECT-2 — Reflect workspace** | **`#/reflect` route, overview tables, run detail** | **⏳ Spec drafted** |
| PR-REFLECT-2a — Reflect filters | Instrument/session filters on persona performance | 📋 Planned |
| PR-CHART-2 — Run context overlay | Multi-timeframe, run marker, verdict annotation | 📋 Planned |
| PR-REFLECT-3 — Suggestions + influence | Rules-based suggestions, analyst influence | 📋 Planned |

---

## 12. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 7).*

*Must include: exact router file, navigation component file, tab pattern, shared component prop compatibility, useRuns semantics, edge-state endpoint responses. Also record any deviations or scope reductions if implementation requires them.*

---

## 13. Doc Corrections to Apply on Branch

1. **`docs/AI_TradeAnalyst_Progress.md`** — header, Recent Activity row, Phase Index, Roadmap (PR-REFLECT-2 → ✅ Done), §6 Next Actions, test count row
2. **`PHASE_8_Roadmap_Spec.md`** — update Reflect section status

### Review for update:

3. **`docs/architecture/system_architecture.md`** — add Reflect workspace to UI architecture section
4. **`docs/architecture/repo_map.md`** — new frontend files
5. **`docs/architecture/AI_ORIENTATION.md`** — update if new workspace route is onboarding-critical
6. **`docs/ui/UI_WORKSPACES.md`** or equivalent — add Reflect to workspace inventory if such a doc exists

---

## 14. Appendix — Recommended Agent Prompt

```
Read `docs/specs/PR_REFLECT_2_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 7 and report
findings before changing any code:

1. Confirm workspace directory pattern
2. Confirm router, navigation, and tab/mode-switch patterns
3. Confirm shared component availability and prop compatibility
4. Inspect useRuns hook semantics (pagination, fields, stale time)
5. Confirm Reflect API availability + edge-state examples
   (below-threshold, mixed-threshold, partial bundle, null metrics)
6. Confirm existing API/hook/adapter patterns
7. Run baseline frontend tests: record count
8. Propose smallest patch set — must name exact router and nav files

Hard constraints:
- No backend changes — frontend only
- No additional computation — display what endpoints return
- Read-only workspace — no mutations, no config changes
- Two tabs: Overview (default) and Runs — NOT three
- Route: #/reflect (hash router, same as other workspaces)
- Null metrics display as "—" — table renders cleanly even when ALL
  metrics in a column are null. Do not hide columns dynamically.
- Below-threshold state is a welcoming message, NOT an error
- Flagged items: amber text + "⚠ " prefix on name (locked visual treatment)
- Stale + populated states coexist — do not collapse to error
- Bundle 404 → "Run not found" with reselection guidance
- Empty run history → welcoming message, not error
- No filter controls in v1 — deferred to PR-REFLECT-2a
- Reuse useRuns hook from PR-RUN-1 — do NOT modify its contract.
  Adapt output via local adapter in reflectAdapter.ts if needed.
- Uses existing shared components (PanelShell, LoadingSkeleton, etc.)
- No chart integration — Reflect does not embed candlestick charts
- No premature abstraction — purpose-built components for Reflect
- No changes to other workspace internals
- Deterministic tests only

Do not change any code until diagnostic is reviewed and approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/PR_REFLECT_2_SPEC.md` — ✅ Complete, flip all 44 AC cells,
   populate §12 with: workspace directory structure, router/nav files,
   tab pattern used, shared components used, useRuns adaptation approach,
   any deviations/reductions, final patch set with line deltas, test count delta
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update:
   header, Recent Activity row, Phase Index, Roadmap, test count, §6 Next Actions
3. Apply doc corrections from §13
4. Review architecture/UI docs per §13 criteria
5. Cross-document sanity check
6. Return Phase Completion Report

Commit all doc changes on the same branch.
```
