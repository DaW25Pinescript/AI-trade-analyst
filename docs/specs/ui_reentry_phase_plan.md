# AI Trade Analyst — UI Re-Entry Phase Plan

## Header

- **Status:** ▶️ In progress — Phase 3 complete, Phase 4 next
- **Date:** 13 March 2026
- **Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
- **Spec file:** `docs/specs/ui_reentry_phase_plan.md`
- **Owner lane:** UI implementation (resuming from parked state)
- **Depends on:** UI Phase 3A design (complete), Observability Phase 2 (closed), TD-3 packaging (closed), Cleanup Tranche (closed)
- **Controlling docs:** `UI_CONTRACT.md`, `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, `VISUAL_APPENDIX.md`

---

## 1. Purpose

This document reopens the UI implementation lane and defines the execution sequence for building the designed workspaces.

UI Phase 3A design was completed and intentionally parked while the repo underwent runtime hardening (Observability Phase 2, TD-3 packaging, cleanup tranche). That hardening is now complete. The backend is in its strongest state: structured logging across all lanes, proper Python packaging, centralised enums, clean imports, and a single canonical status source.

This plan defines:

- the forward frontend stack decision
- the phased build sequence from Triage Board through Agent Operations
- PR boundaries and acceptance criteria for each phase
- the governance rules that keep the implementation honest to the existing contract
- the classification of Agent Operations as a Phase 3B extension

### What question this plan answers

**How does the repo go from "UI fully designed but parked" to "working React workspaces against real data" in a disciplined, contract-faithful sequence?**

### What it moves FROM → TO

- **FROM:** Complete UI design bank (contract, wireframes, component system, design notes, visual appendix) but zero React implementation. Current `/app/` is vanilla JS. Agent Operations has a detailed spec and HTML prototype but no backend endpoints.
- **TO:** React + TypeScript + Tailwind app shell with working Triage Board, Journey Studio, Analysis Run, Journal & Review workspaces against existing endpoints. Agent Operations workspace against new read-only projection endpoints. Shared component system proven in production-like conditions.

---

## 2. Locked Decisions

These decisions are final and should not be re-litigated during implementation.

### 2.1 Forward frontend stack

**React + TypeScript + Tailwind** for all new UI work.

Rationale: the workspace complexity (shared cards, state models, diagnostics views, multi-workspace navigation, conditional panels, execution lifecycle rendering) requires a component-driven framework. Maintaining a split stack (vanilla JS for core workspaces, React for Agent Ops) would create duplicate component logic, duplicate state normalisation, and migration debt.

The existing `app/` vanilla JS surfaces remain functional during migration. React runs in parallel and replaces workspace-by-workspace.

### 2.2 Triage Board as component-system seed

The Triage Board is the first React workspace. It proves the stack against real data (existing `/watchlist/triage` and `/triage` endpoints) and establishes shared component primitives that all subsequent workspaces reuse.

This is preferred over building Agent Operations first because:
- Triage Board requires zero new backend endpoints
- it validates React + real data immediately
- it respects the Phase 3A → 3B sequencing in the repo docs
- it produces the same reusable primitives Agent Ops needs

### 2.3 Agent Operations as Phase 3B extension

Agent Operations is an operator workspace built on new read-only observability projections. It is classified as Phase 3B (backend capability exposure), not Phase 3A (existing contract surfaces).

Rules:
- no production contract exists for `/ops/*` until backend PRs merge
- the HTML prototype (`operations.html`) is visual reference only — not implementation debt
- Agent Ops must not displace Triage/Journey as the main product entry point
- Agent Ops lives in the operator navigation lane, not the runtime lane

**Product framing (locked):**
- Agent Operations is an **operator observability, explainability, and trust workspace** for the multi-agent analysis engine.
- Its north-star question is: **“Why should I trust this system right now?”**
- It exists to answer five operator questions:
  - Who participated?
  - What happened in this run?
  - Why did the system reach this verdict?
  - Where is trust weakened?
  - What needs attention?

**Negative scope (locked):**
- Agent Ops MVP is **not** a configuration interface.
- It is **not** a prompt editor.
- It is **not** a manual orchestration panel.
- It is **not** a model-switching console.
- It is **not** a chat-with-agents surface.

### 2.4 Contract-first implementation

All workspace implementation must stay faithful to `UI_CONTRACT.md`. No UI dependency on undocumented payload quirks. No backend contract drift without doc updates. Frontend implementation should not infer contracts directly from ad hoc backend code (governance rule §3.1 of the contract).

---

## 3. Phase Sequence

### Phase 0 — UI Re-Entry Governance

**Objective:** Reopen the UI lane deliberately with proper documentation.

**Deliverables:**
- Update `docs/AI_TradeAnalyst_Progress.md`:
  - Record: React + TypeScript + Tailwind is the forward stack
  - Record: Phase 3A implementation resumes with Triage Board first
  - Record: Agent Operations is a fenced Phase 3B extension
- Add design governance note:
  - Agent Operations is an operator observability / explainability / trust workspace on new read-only projections
  - Agent Ops north-star question: “Why should I trust this system right now?”
  - Agent Ops MVP is not config, prompt editing, manual orchestration, model-switching, or chat-with-agents
  - HTML prototype is visual reference only
  - No production contract for `/ops/*` until endpoints merge
  - Phase 5 = roster-first observability MVP; Phase 7 = run-scoped forensic explainability
- Define migration guardrail: React app coexists with existing `app/` during workspace-by-workspace migration

**Acceptance:**
- Progress hub reflects the new execution decision
- No code changes in this phase — governance only

**PR:** `PR-UI-0`

---

### Phase 1 — React App Shell + Triage Board Route

**Objective:** Establish the React + TypeScript + Tailwind foundation.

**Deliverables:**
- Base React/TS/Tailwind project setup
- Build tooling (Vite or equivalent)
- Routing framework for workspace navigation
- Typed API client layer (fetch wrapper with response typing)
- State management scaffolding
- Triage Board route placeholder

**Frontend repo-shape (lock before implementation):**

The filesystem layout must be explicit so contributors do not improvise structure. Lock the following in this PR:

- Where the React app lives (e.g. `app-react/` or `ui/` — must coexist with current `app/`)
- Where shared components live (e.g. `app-react/shared/components/`)
- Where typed API clients live (e.g. `app-react/shared/api/`)
- Where workspace-specific code lives (e.g. `app-react/workspaces/triage/`)
- Whether the React app has its own build pipeline or shares with the existing `app/` build path
- How the React app is served alongside the existing `app/` during migration (separate port, proxied route, or co-hosted)

This decision is made once in PR-UI-1 and not revisited per workspace.

**Acceptance:**
- React app builds and serves alongside existing `app/`
- Filesystem layout is documented and consistent with the locked repo-shape
- Route navigation works for at least `#/triage`
- Typed fetch layer can call existing endpoints
- No UI rendering of real data yet — shell only

**PR:** `PR-UI-1`

---

### Phase 2 — Triage Board MVP (Component-System Seed)

**Objective:** Prove the stack against real data and establish shared component primitives.

**Backend basis (existing, no new endpoints):**
- `GET /watchlist/triage` — ranked triage items with `data_state`
- `POST /triage` — trigger-and-refresh pattern

**Build:**
- Live data rendering from `/watchlist/triage`
- "Run Triage" action with idle/running/refreshed button states
- Row click → navigation to Journey route (placeholder target)

**First shared primitives (must be extracted, not page-local):**
- `DataStateBadge` — LIVE / STALE / UNAVAILABLE / DEMO-FALLBACK
- `TrustStrip` — data_state badge + feeder health chip + timestamp grouped
- `StatusPill` — reusable state indicator
- `EntityRowCard` — ranked instrument/entity row with hover affordance
- `PanelShell` — workspace panel container
- `EmptyState` / `UnavailableState` / `ErrorState` / `LoadingSkeleton`
- `FeederHealthChip` — compact cross-cutting trust signal

**Design reference:**
- `UI_WORKSPACES.md` §5 (Triage Board layout)
- `DESIGN_NOTES.md` §1.1 (per-row staleness), §1.2 (data_state read-only), §1.5 (triage→journey handoff)
- `VISUAL_APPENDIX.md` Triage Board wireframe
- Component Design System — Trust/Freshness Indicators column

**Acceptance:**
- Renders real triage data from backend
- Correctly distinguishes ready, empty, stale, unavailable, demo-fallback, error states
- No mock-only dependency — works against live backend
- Component primitives are shared modules, not inline in the page component
- `data_state` is always visible as a board-level trust signal
- Per-row staleness derived from `verdict_at` where available (no invented per-row `data_state`)

**PR:** `PR-UI-2`

---

### Phase 3 — Shared Component Extraction

**Objective:** Harden the Triage Board components into a reusable UI foundation before Agent Ops or other workspaces build on them.

**Deliverables:**
- Extract and normalise into a shared component/hooks/utils layer:
  - Layout primitives
  - Badge/state token system (data_state, run lifecycle, health)
  - Freshness/trust strip logic
  - Query hooks (typed fetch + polling + error handling)
  - Response normalisers / view-model mappers
  - Shared empty/error/degraded/loading shells
- Document component API contracts (prop types, usage rules)

**Acceptance:**
- Triage Board imports all components from the shared layer (no page-local component definitions)
- A new workspace could be built using only shared components + workspace-specific logic
- Component props match the contract entities (TriageItem, data_state, FeederHealth, etc.)

**PR:** `PR-UI-3`

---

### Phase 4 — Agent Ops Contract Spec + Backend MVP

**Objective:** Establish the first read-only operator surfaces.

**New endpoints (read-only projections):**

| Method | Route | Purpose | Backed by |
|--------|-------|---------|-----------|
| `GET` | `/ops/agent-roster` | Static architecture + roster truth | Persona config, roster definitions |
| `GET` | `/ops/agent-health` | Current health snapshot | Obs P2 structured events, scheduler health, feeder health |

**Contract requirements per endpoint:**
- Response shape locked before implementation
- `data_state` semantics explicit (live / stale / unavailable)
- Degraded/unavailable behavior defined
- Snapshot vs live vs cached semantics stated
- Error contract defined (structured, not freeform `detail`)
- Empty-state behavior defined

**Guardrails:**
- Read-only projections only — no new orchestration engine
- Derive from existing config / observability truth where possible
- No coupling to internal runtime objects
- `/ops/agent-health` is **poll-based snapshot only** in MVP — the UI fetches on load or on manual refresh. No SSE, no WebSocket, no live-push semantics. This must be explicit in the contract spec so no one sneaks live-stream behavior into the first cut.
- Update `UI_CONTRACT.md` extension section when endpoints merge

**Acceptance:**
- Endpoint contract spec documented
- `/ops/agent-roster` and `/ops/agent-health` return valid responses
- Deterministic tests for response shapes, empty states, and degraded behavior
- No new runtime behavior — pure read models

**PRs:** `PR-OPS-1` (contract docs), `PR-OPS-2` (backend implementation)

---

### Phase 5 — Agent Ops React Workspace MVP

**Objective:** Build the operator workspace on proven Triage Board component primitives.

**Backend basis:**
- `GET /ops/agent-roster` (from Phase 4)
- `GET /ops/agent-health` (from Phase 4)

**Build from component plan (`agent_operations_component_adapter_plan.refined.md`):**
- `AgentOperationsWorkspace` page component
- `WorkspaceToolbar` — environment, mode switch (Org/Run/Health), filters
- `LayerSection` — GOVERNANCE LAYER, OFFICER LAYER rendering
- `DepartmentBoxes` + `DepartmentBox` — PERSONA / DEPARTMENT GRID
- `AgentCard` — reusable entity card (extends shared `EntityRowCard` patterns)
- `AgentDetailPanel` — Selected Node Detail sidebar
- `ActivityStream` — bottom event ribbon
- Adapter layer: `mapRoster`, `mapHealth`, `mergeWorkspaceEntities`, `deriveVisualState`
- Hooks: `useAgentRoster`, `useAgentHealth`

**Important constraints:**
- Build from the refined component/adapter plan, not by porting the HTML prototype
- Reuse Triage Board shared primitives (badges, pills, panels, error states, hooks)
- Phase 5 is a **roster-first observability MVP**, not a full forensic run workspace
- MVP may include a passive activity/event strip and a lightweight recent-run summary list **only if** they can be derived safely from the roster/health read models without inventing new backend surfaces
- No run-detail forensic drilldown in this phase; that belongs to Phase 7
- Org mode is the primary mode for MVP. Any Health emphasis in MVP must remain snapshot-based and non-forensic until Phase 7
- Feature-flagged or operator-only route

**Acceptance:**
- Renders real roster and health data from new endpoints
- Governance → Officer → Department hierarchy driven by backend data, not hardcoded layout
- Relationship arrows driven by `relationships` array, not inferred from position
- Health/lifecycle states rendered as separate dimensions (not collapsed)
- Workspace clearly communicates trust/observability purpose rather than control-panel semantics
- Shared components reused from Phase 3 extraction
- Operator route, not product homepage

**PR:** `PR-OPS-3`

---

### Phase 6 — Remaining Phase 3A Workspaces

**Objective:** Complete the core product lane.

**Build order:**
1. **Journey Studio** — primary forward product workspace
2. **Analysis Run** — expert/compatibility execution surface
3. **Journal & Review** — decision readback loop

Journey Studio is first because it is the primary user-path workspace after Triage Board. The workspace blueprint defines Triage → Journey as the main product flow, and the repo docs designate Journey UI as the canonical forward consumer. Analysis Run is important but remains partly tied to legacy/manual execution surfaces and should not be treated as the default next workspace after Triage.

**Design references:**
- `UI_WORKSPACES.md` §6, §7, §8 (workspace layouts)
- `DESIGN_NOTES.md` (freeze behavior, Save Result gating, tab persistence, etc.)
- `VISUAL_APPENDIX.md` (wireframes)
- `UI_CONTRACT.md` §10.2, §10.3 (endpoint contracts)

**Key implementation rules per workspace:**

Journey Studio:
- Stages are a UI concept, not a backend entity
- Freeze locks entire center column to read-only
- Save Result disabled until freeze succeeds
- Conditional right rail driven by bootstrap field presence
- Demo-fallback explicitly flagged

Analysis Run:
- Four-state lifecycle rendering (pre-run, mid-run, post-success, failure)
- Tabs remain navigable post-run
- Verdict tab disabled on failure ("No verdict — run failed")
- Usage as inline accordion, not navigation away
- Streaming reserved for later — design the panel to accept it without redesign

Journal & Review:
- Two views in one workspace (separable later per §8.6)
- Graceful empty state is normal, not error
- No fake detail screen without backed contract
- ReviewRecord extends DecisionSnapshot (shared adapter, not duplicate model)

**Acceptance per workspace:**
- Renders against existing endpoints with real data
- State handling matches `UI_CONTRACT.md` semantics
- Shared components reused from Phase 3 extraction
- Design decisions from `DESIGN_NOTES.md` respected

**PRs:** `PR-UI-4` (Journey), `PR-UI-5` (Analysis Run), `PR-UI-6` (Journal & Review)

---

### Phase 7 — Agent Ops Trace + Detail Drilldown

**Objective:** Deepen the operator workspace from roster-first observability into run-scoped forensic explainability after the core UI foundation is stable.

**New endpoints:**

| Method | Route | Purpose | Guardrails |
|--------|-------|---------|-----------|
| `GET` | `/runs/{run_id}/agent-trace` | Run-specific participation + lineage | Trace/readback only — not a replay engine |
| `GET` | `/ops/agent-detail/{entity_id}` | Full detail for selected entity | Discriminated union: `entity_type: agent | provider | persona | run_node` |

**Build:**
- Run mode in Agent Ops workspace (participant highlighting, influence overlays, lineage edges)
- Health mode emphasis (problem-first sorting, stronger degraded/stale signaling)
- Run detail view and run-scoped agent detail panel
- Full detail sidebar content (purpose, influence history, error log, dependencies)
- `useRunAgentTrace` and `useAgentDetail` hooks

**Guardrails:**
- `agent-trace` is read-only trace data — no execution control
- `agent-detail` must use a discriminated union to prevent dumping-ground payloads
- No coupling to internal runtime objects
- Update contract docs when endpoints merge

**Acceptance:**
- Run mode renders participant data from trace endpoint
- Detail sidebar renders from detail endpoint
- Run-scoped drilldown answers: what happened, who mattered most, who objected, and where trust weakened
- Lineage edges driven by backend `lineage_edges` array
- Degraded/unavailable trace handled gracefully (workspace remains usable)

**PRs:** `PR-OPS-4` (backend endpoints + tests), `PR-OPS-5` (React workspace wiring)

---

## 4. Non-Negotiable Guardrails

These rules apply across all phases:

1. **Do not migrate the whole legacy UI at once.** React runs in parallel and replaces workspace-by-workspace.
2. **Do not let Agent Operations become the homepage.** The workspace doc is clear: Triage/Journey is the forward product lane. Agent Ops lives in the operator navigation lane.
3. **Do not let `/ops/agent-detail/{entity_id}` ship without a strict entity discriminator.**
4. **Do not let SSE or live trace work sneak into the first React milestone.** The contract notes `/analyse/stream` exists but is not the main UI path. No public run-status polling contract exists today.
5. **Do not treat the HTML prototype as implementation debt.** It is visual reference for hierarchy, tone, and interaction intent only.
6. **Do not build UI against undocumented backend behavior.** `UI_CONTRACT.md` governance rule §3.1 applies.
7. **Do not invent backend surfaces from the UI side.** Phase 3A workspaces use existing endpoints only. Agent Ops endpoints must be spec'd, built, tested, and merged before UI wires to them.

---

## 4.1 Testing Expectations by PR Class

Every PR must meet the verification standard for its class. This removes ambiguity when Codex or Claude picks up an individual PR.

| PR class | Required verification |
|----------|---------------------|
| **Frontend-only PRs** (`PR-UI-*`) | Build passes, TypeScript typecheck clean, route-level smoke test confirms workspace loads, state handling for empty/loading/error/live is visually confirmed |
| **Backend endpoint PRs** (`PR-OPS-2`, `PR-OPS-4`) | Deterministic response-shape tests, degraded/unavailable/empty-state tests, error contract tests, no live provider dependency in CI |
| **UI wiring PRs** (`PR-OPS-3`, `PR-OPS-5`) | Proves empty/loading/error/live/stale handling against real endpoint responses, shared component reuse confirmed, no mock-only dependency in the final acceptance pass |
| **Contract/docs PRs** (`PR-UI-0`, `PR-OPS-1`) | No code changes; doc accuracy verified against repo state |

---

## 5. PR Sequence Summary

| PR | Phase | Scope | Backend changes |
|----|-------|-------|----------------|
| `PR-UI-0` | 0 | Governance unlock — progress hub + design note | None |
| `PR-UI-1` | 1 | React app shell + routing + typed fetch | None |
| `PR-UI-2` | 2 | Triage Board MVP — real data + first components | None |
| `PR-UI-3` | 3 | Shared component extraction | None |
| `PR-OPS-1` | 4 | Agent Ops contract spec docs | None |
| `PR-OPS-2` | 4 | Agent Ops backend — roster + health endpoints | New endpoints |
| `PR-OPS-3` | 5 | Agent Ops React workspace MVP | None |
| `PR-UI-4` | 6 | Journey Studio React | None |
| `PR-UI-5` | 6 | Analysis Run React | None |
| `PR-UI-6` | 6 | Journal & Review React | None |
| `PR-OPS-4` | 7 | Agent Ops backend — trace + detail endpoints | New endpoints |
| `PR-OPS-5` | 7 | Agent Ops trace + detail wiring | None |

Total: 12 PRs. 8 frontend-only, 4 with backend changes. The first 4 PRs require zero new backend work.

---

## 6. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| UI Phase 1 | Backend Capability Audit | ✅ Done |
| UI Phase 2 | UI Contract | ✅ Done |
| UI Phase 3A Design | Workspace Blueprint + Visual Design | ✅ Done |
| **Phase 0** | **UI Re-Entry Governance** | **✅ Done** |
| **Phase 1** | **React App Shell + Triage Route** | **✅ Done** |
| **Phase 2** | **Triage Board MVP (component seed)** | **✅ Done** |
| **Phase 3** | **Shared Component Extraction** | **✅ Done** |
| **Phase 4** | **Agent Ops Contract + Backend MVP** | **🟡 Contract complete (PR-OPS-1), backend next (PR-OPS-2)** |
| **Phase 5** | **Agent Ops React MVP** | **⏳ Pending** |
| **Phase 6** | **Journey Studio + Analysis Run + Journal & Review** | **⏳ Pending** |
| **Phase 7** | **Agent Ops Trace + Detail** | **⏳ Pending** |
| UI Phase 3C | Chart Evidence + Run Artifact Inspector | ⏸️ Fenced |

---

## 7. Documentation Closure

At each phase close, update:

- `docs/AI_TradeAnalyst_Progress.md` — phase status, test counts, next actions
- `docs/specs/ui_reentry_phase_plan.md` — mark completed phases, note any scope adjustments
- `docs/ui/UI_CONTRACT.md` — update only if Agent Ops endpoints add new contract surfaces
- `docs/specs/README.md` — update spec inventory as needed
- Cross-document sanity check: no stale phase refs, no competing progress sources

---

## 8. Success Definition

This plan is complete when: the Triage Board, Journey Studio, Analysis Run, and Journal & Review workspaces are functional React applications consuming real backend data through the existing contract; Agent Operations is a working operator observability / explainability / trust workspace consuming new read-only projection endpoints; all workspaces share a common component system proven against real data; the forward frontend stack is React + TypeScript + Tailwind; and the legacy `app/` surfaces remain functional during migration. No invented backend surfaces. No contract drift. No Agent Ops on the homepage.

---

## 9. Why This Plan

| Without | With |
|---------|------|
| UI design bank sits idle while the repo has its strongest-ever backend | Design bank converts to working product within weeks |
| Framework decision deferred indefinitely | React + TS + Tailwind locked, no split-stack debt |
| Agent Ops tempts a backend-first approach that blocks UI on new endpoints | Triage Board proves the stack on real data immediately |
| Component primitives invented speculatively | Components proven against real triage data, then reused |
| Agent Ops classification ambiguous | Explicitly Phase 3B extension, operator lane, not product homepage |
| Legacy UI migration attempted as a big bang | Workspace-by-workspace parallel migration |
