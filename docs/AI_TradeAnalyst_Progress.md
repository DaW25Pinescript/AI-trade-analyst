# AI Trade Analyst — Repo Review & Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 15 March 2026
**Review date:** 10 March 2026
**Current phase:** Phase 7 — Complete (Agent Ops backend ✅, Agent Ops frontend wiring ✅)
**Planning horizon:** Next 6–8 weeks

> This file is the canonical progress/status document for the repo. Audit notes, phase notes, and review outputs should feed into this file rather than compete with it.

**See also**
- Docs navigation index: `docs/README.md`
- Specs inventory: `docs/specs/README.md`
- Enduring architecture references: `docs/architecture/README.md`
- Runbooks: `docs/runbooks/README.md`
- Historical snapshots/audits: `docs/archive/README.md`
- UI documentation lane: `docs/ui/` — `UI_BACKEND_AUDIT.md`, `UI_CONTRACT.md`, `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, `VISUAL_APPENDIX.md`

---

## Phase Index (at-a-glance)

- **Completed named phases:** Phase A, B, C, D, 1A, 1B, E+, Instrument Promotion, Provider Routing, Operationalise P1/P2, TD-1 Micro-PR, Security/API Hardening, CI Seam Hardening, LLM Routing Centralisation, Observability Phase 1, UI Phase 1, UI Phase 2, UI Phase 3A, PR-OPS-1/2/3, Phase 6 (PR-UI-1–6), Phase 7 (PR-OPS-4a/4b/5a/5b).
- **Current phase:** Phase 7 — Complete. Agent Ops read-side stack fully wired: 4 backend endpoints (197 tests), 3 workspace modes (63 frontend tests), typed detail sidebar, trace visualization.
- **Forward frontend stack:** React + TypeScript + Tailwind is the forward frontend stack.
- **Agent Operations classification:** Agent Operations read-side stack is complete — operator observability / explainability / trust workspace on four read-only projection endpoints (roster, health, trace, detail).
- **Next actions:** Phase 8 planned — Run Browser (PR-RUN-1), Live Charts (PR-CHART-1/2), Reflective Intelligence (PR-REFLECT-1/2/3). Run Browser first to enable run discovery and artifact volume.
- **Active decision gate:** the production-readiness gate remains satisfied. UI core product lane (Phase 6) and Agent Ops read-side stack (Phase 7) are both complete.

---

## Recent Activity

| Date | Phase | Activity |
|------|-------|----------|
| 15 Mar 2026 | PR-OPS-5b | Frontend Run mode + Detail sidebar — 7 new components, +24 tests (63 frontend total), Phase 7 complete |
| 15 Mar 2026 | PR-OPS-5a | Frontend types + adapters + Health mode — +16 tests (39 frontend total), foundation wiring |
| 15 Mar 2026 | PR-OPS-4b | Backend agent-detail endpoint — discriminated union, profile registry, +72 tests (197 backend total) |
| 14 Mar 2026 | PR-OPS-4a | Backend agent-trace endpoint — run_record.json + audit log projection, +70 tests (126 backend total) |
| 14 Mar 2026 | PR-UI-6 | Journal & Review workspace MVP — decision readback + review toggle, +42 tests (243 total), Phase 6 complete |
| 14 Mar 2026 | PR-UI-5 | Analysis Run workspace MVP — multipart /analyse, run lifecycle state machine, +69 tests (201 total) |
| 14 Mar 2026 | PR-UI-4 | Journey Studio workspace MVP — staged flow, freeze lifecycle, +43 tests (132 total) |
| 13 Mar 2026 | PR-OPS-3 | Agent Ops workspace shell — live roster + health, operator aesthetic, +23 tests (89 total) |
| 13 Mar 2026 | PR-OPS-1 | Agent Ops contract spec — endpoint contracts for roster + health, zero code changes |
| 13 Mar 2026 | PR-UI-3 | Shared component extraction — generic EntityRowCard, barrel exports, +36 tests (66 total) |
| 13 Mar 2026 | PR-UI-2 | Triage Board MVP — real data rendering, shared components, trust strip, +24 tests (30 total) |
| 13 Mar 2026 | PR-UI-1 | React app shell — Vite + routing + typed API client, 5 smoke tests |
| 12 Mar 2026 | Obs Phase 2 | Cross-lane runtime visibility — 16 event codes, +18 tests |
| 12 Mar 2026 | TD-3 | Packaging/import stability — 27 sys.path.insert removed, 16 import tests |

---

## Roadmap

| Priority | Phase | Description | Status | Depends On |
|----------|-------|-------------|--------|------------|
| 1 | PR-RUN-1 | Run Browser endpoint + frontend — replace paste-field run selector | 📋 Planned | Phase 7 complete |
| 2 | PR-CHART-1 | OHLCV data-seam validation + basic candlestick chart (lightweight-charts, embedded in Run mode) | 📋 Planned | PR-RUN-1 |
| 3 | PR-CHART-2 | Run context overlay + multi-timeframe chart support | 📋 Planned | PR-CHART-1 |
| 4 | PR-REFLECT-1 | Persona performance + pattern summary aggregation endpoints | 📋 Planned | PR-RUN-1 + run history |
| 5 | PR-REFLECT-2 | Reflective dashboard frontend — performance tables + anomaly highlighting | 📋 Planned | PR-REFLECT-1 |
| 6 | PR-REFLECT-3 | Integration + rules-based parameter suggestions v0 | 📋 Planned | PR-CHART-2 + PR-REFLECT-2 |
| — | Chart Indicators | Pine Script-style indicator overlays on candlestick charts | 💭 Concept | PR-CHART-2 |
| — | ML Pattern Detection | Statistical models replacing rules-based suggestions | 💭 Concept | PR-REFLECT-2 + run volume |
| — | Control-Plane Actions | Agent start/stop/retry in Ops workspace | 💭 Concept | Phase 7 complete |
| — | Live Push Updates | SSE/WebSocket for real-time health and trace updates | 💭 Concept | Phase 7 complete |

---

## 1) Executive Snapshot

The repository is in a **strong implementation state**:

- Core architecture is present across UI (`app/`), analyst engine (`ai_analyst/`), market data lane (`market_data_officer/`), and macro context lane (`macro_risk_officer/`).
- The tracked Market Data Officer build phases through **Operationalise Phase 2** are complete.
- **Security/API Hardening** is complete and closed cleanly.
- Two high-impact analyst debt items have now been resolved:
  - **TD-1** — arbiter assert-based runtime contract enforcement
  - **TD-2** — `call_llm()` without timeout/retry safeguards
- **TD-10** (LLM failure modes under-tested) was also closed as a side-effect of the TD-2 resilience test work.
- A formal UI documentation lane now exists under `docs/ui/`, with a completed backend capability audit, a canonical UI contract (Active), a workspace blueprint with visual design layer, written design decisions, and a visual appendix referencing all wireframes and the component system.
- Phase-gate test progression now reaches **677 tests green** at Security/API Hardening closure, with zero regressions reported.


### Latest increment — PR-OPS-5b: Agent Ops Frontend Wiring Complete (15 Mar 2026)

Delivered PR-OPS-5b — Run mode + Detail sidebar wiring for the Agent Ops workspace (Phase 7). New components: `RunSelector` (paste-field run ID input), `TraceStageTimeline` (ordered stages with status-aware dots and partial run indicator), `TraceParticipantList` (participants with stance/confidence/override indicators), `TraceEdgeList` (conservative from→to edge rendering with type labels), `ArbiterSummaryCard` (verdict/confidence/method/override/dissent), `RunTracePanel` (orchestrates full Run mode view with trace summary, stages, participants, edges, arbiter, artifacts), `AgentDetailSidebar` (backend-backed detail panel with discriminated union rendering — switches on `entity_type` NOT `type_specific.variant`). Four type-specific sections: `PersonaSection`, `OfficerSection`, `ArbiterSection`, `SubsystemSection`. `AgentOpsPage` updated: Run pill activated, run selector + trace panel wired, detail sidebar replaces old roster-based panel, degraded/stale banners scoped to Org/Health modes. Null arbiter → hidden (no fabrication). 404 error handling for both trace and detail. data_state stale indicators at both workspace and entity level. 63 frontend tests passing (39 baseline + 24 new). All 28 spec ACs (AC-1 through AC-28) verified ✅. PR-OPS-5 spec marked complete. Zero backend modifications. Agent Ops read-side stack fully wired.

### Previous increment — PR-OPS-5a: Agent Ops Frontend Wiring — Types + Health Mode (15 Mar 2026)

Delivered PR-OPS-5a — types, adapters, hooks, Org preservation, and Health mode activation for the Agent Ops workspace (Phase 7). Created contract-exact TypeScript types for all four endpoints (roster, health, trace, detail), API fetch functions with `OpsErrorEnvelope` parsing, TanStack Query hooks (`useAgentRoster`, `useAgentHealth`, `useAgentTrace`, `useAgentDetail`), view-model adapter (`buildOpsWorkspaceViewModel`) with roster-health join per §5.10 rules (unknown IDs discarded, missing health valid, roster as structural truth). Health mode activated with `elevateDegraded` sort. data_state stale/unavailable banners. 39 tests covering AC-1 through AC-7 + shared gates. Run mode and Detail sidebar deferred to 5b.

### Previous increment — PR-OPS-4b: Agent Detail Endpoint (15 Mar 2026)

Delivered PR-OPS-4b — agent-detail endpoint for the Agent Ops workspace (Phase 7). Added `GET /ops/agent-detail/{entity_id}` read-only composite projection endpoint that derives entity-level detail from roster (identity, department, visual_family), static profile registry (purpose, responsibilities, type-specific variant), health snapshot (graceful degradation when unavailable), and bounded recent-run scan (max 20 dirs or 7 days, capped at 5 entries). New Pydantic models (`AgentDetailResponse`, `EntityIdentity`, `EntityStatus`, `EntityDependency`, `RecentParticipation`, `PersonaDetail`, `OfficerDetail`, `ArbiterDetail`, `SubsystemDetail`) following flat `ResponseMeta` inheritance per PR-OPS-2 pattern. Discriminated union via `entity_type` + `type_specific.variant` tag. Static profile registry (`ops_profile_registry.py`) with hardcoded profiles for all 13 roster entities. Detail projection service builds dependency graph from roster relationships, maps upstream/downstream directions. Thin route handler with `OpsErrorEnvelope` for 404/422/500. 72 new deterministic tests covering AC-10 through AC-17, AC-18–AC-25 (all 25 spec ACs now passing). Test suite: 197 passed (55 baseline + 70 trace + 72 detail), zero regressions. `AGENT_OPS_CONTRACT.md` §6 promoted from "reserved" to full contract with both trace and detail endpoint specifications. All PR-OPS-4 spec acceptance criteria (AC-1 through AC-25) verified ✅. No pipeline changes, no new persistence. PR-OPS-5 (frontend wiring) is next.

### Previous increment — PR-OPS-4a: Agent Trace Endpoint (15 Mar 2026)

Delivered PR-OPS-4a — agent-trace endpoint for the Agent Ops workspace (Phase 7). Added `GET /runs/{run_id}/agent-trace` read-only projection endpoint that derives run-level observability from existing `run_record.json` (primary) and audit log (secondary, for analyst stances and override detail). New Pydantic models (`AgentTraceResponse`, `TraceSummary`, `TraceStage`, `TraceParticipant`, `ParticipantContribution`, `TraceEdge`, `ArbiterTraceSummary`, `ArtifactRef`) following flat `ResponseMeta` inheritance per PR-OPS-2 pattern. Trace projection service maps bare persona names to roster IDs, degrades to `data_state: "stale"` when audit log is missing (no 500), enforces bounded payload limits (§6.11), and uses locked stage vocabulary. Thin route handler added to existing ops router with `OpsErrorEnvelope` for 404/422/500. 71 new deterministic fixture-based tests covering AC-1 through AC-9, AC-18–AC-22, AC-24–AC-25 (15 of 25 spec ACs). Test suite: 126 passed (55 baseline + 71 new), zero regressions. No pipeline changes, no new persistence, no frontend wiring. PR-OPS-4b (agent-detail) is next.

### Previous increment — PR-UI-6: Journal & Review React Workspace MVP (14 Mar 2026)

Delivered PR-UI-6 — Journal & Review React workspace MVP. Replaced the /journal placeholder route with a real decision readback workspace consuming existing `GET /journal/decisions` and `GET /review/records` endpoints. Single `/journal` route with internal Journal | Review toggle — structurally separable per UI_WORKSPACES §8.6. New workspace-local API layer (`fetchDecisions`, `fetchReviewRecords`) with typed response shapes per UI_CONTRACT §9.7 (DecisionSnapshot) and §9.8 (ReviewRecord extends DecisionSnapshot). Workspace adapter (`journalAdapter.ts`) normalizes backend responses to view models, derives header summaries (decision count for Journal, outcome coverage for Review), derives per-record result indicators (has-result vs needs-follow-up), handles empty records as normal state. TanStack Query hooks (`useJournalDecisions`, `useReviewRecords`) with exported cache keys. Journal view shows frozen decisions list with metadata and lateral navigation to Journey Studio. Review view shows decisions plus result linkage (`has_result`) with visual distinction between "has result" and "needs follow-up". Both views handle empty records gracefully as welcoming state, not error. Row interaction navigates laterally to `#/journey/{instrument}` — required primary behavior per spec. No fake detail screen (DESIGN_NOTES §1.9). Shared components reused: PanelShell, LoadingSkeleton, EmptyState, ErrorState, EntityRowCard, StatusPill. Read-only workspace — no mutations, no result submission, no outcome logging. 42 new tests (adapter unit tests + component integration tests + view toggle tests + empty state tests + navigation tests + header summary tests + outcome coverage tests). Build passes, 243 tests green (42 new). No backend modifications. Phase 6 is now complete — all core product workspaces shipped (Journey Studio, Analysis Run, Journal & Review).

### Previous increment — PR-UI-5: Analysis Run React Workspace MVP (14 Mar 2026)

Delivered PR-UI-5 — Analysis Run React workspace MVP. Replaced the /analysis placeholder route with a real expert execution surface consuming existing `POST /analyse` (multipart/form-data) and `GET /runs/{run_id}/usage` (JSON) endpoints. New workspace-local API layer (`submitAnalysis`, `fetchRunUsage`) with multipart transport for /analyse — deliberately separated from the shared JSON `apiFetch` to avoid Content-Type contamination. Workspace adapter (`analysisAdapter.ts`) normalizes backend responses to UI view models, handles mixed error detail shapes (string or structured object per UI_CONTRACT §11.1), derives tab enablement and submission read-only state, tolerates empty-but-valid usage summaries. Standalone run lifecycle state machine (`runLifecycle.ts`) implementing UI_CONTRACT §7 canonical states (idle → validating → submitting → running → completed | failed) with `partial` reserved in type for future streaming. State machine enforces valid transitions only, preserves run_id/request_id across all states including failure. Three-panel tabbed layout with tab persistence (Submission | Execution | Verdict) — all tabs remain navigable post-run. Submission locks to read-only post-submit for "what did I submit?" verification. Execution panel shows spinner with elapsed time counter during running state — no fake progress indicators. Verdict panel renders full FinalVerdict at expert density (final_bias, decision, approved_setups, no_trade_conditions, overall_confidence, analyst_agreement_pct, arbiter_notes). Verdict tab shows "No verdict — run failed" on failure state. Usage accordion inline below verdict, closed by default, tolerates artifact-missing gracefully. Journey → Analysis escalation via ?asset=SYMBOL query parameter with provenance breadcrumb and "Return to Journey" link. Multipart field names discovered from backend FastAPI route: instrument, session, timeframes, account_balance, min_rr, max_risk_per_trade, max_daily_risk, chart_h4/h1/m15/m5, lens_* flags, enable_deliberation, smoke_mode, source_ticket_id. 69 new tests (state machine unit tests + adapter unit tests + component tests + integration tests + escalation tests + E2E submission→verdict test). Build passes, typecheck clean, 201 tests green. No backend modifications.

### Previous increment — PR-UI-4: Journey Studio React Workspace MVP (14 Mar 2026)

Delivered PR-UI-4 — Journey Studio React workspace MVP. Replaced the /journey/:asset placeholder route with a real structured trade ideation workspace consuming all four journey backend endpoints: `GET /journey/{asset}/bootstrap`, `POST /journey/draft`, `POST /journey/decision`, `POST /journey/result`. New API layer (`fetchJourneyBootstrap`, `saveJourneyDraft`, `saveJourneyDecision`, `saveJourneyResult`) with typed response shapes from UI_CONTRACT.md §9.6, §10.3, §11.2. TanStack Query hook (`useJourneyBootstrap`) with 60s stale time. Three mutation hooks (`useJourneyDraft`, `useJourneyDecision`, `useJourneyResult`) with typed error handling including 409 conflict detection. Deterministic view-model adapter (`buildJourneyWorkspaceViewModel`) that maps bootstrap to workspace condition, derives right rail panel visibility from field presence, tracks UI-only staged flow (explore → draft → frozen → result), and computes action enablement (canSaveDraft, canFreeze, canSaveResult). Full workspace UI: header with asset/stage/freshness/status, staged center column with collapse/expand, conditional right rail panels (arbiter summary, approved setups, no-trade conditions, reasoning), action bar with Save Draft / Freeze Decision / Save Result. Freeze lifecycle: pre-freeze interactive forms → freeze locks to read-only → Save Result gated until freeze succeeds. 409 conflict handling with explicit conflict UX distinct from generic errors. All required state handling: loading, ready, empty, stale, partial, unavailable, error. Triage → Journey navigation continuity via row click. No-asset fallback. 43 new tests (adapter unit tests + component integration tests + navigation continuity tests + route tests). Build passes, typecheck clean, 132 tests green. No backend modifications.

### Previous increment — PR-OPS-3: Agent Ops React Workspace MVP (13 Mar 2026)

Delivered PR-OPS-3 — Agent Operations React workspace MVP. Replaced the /ops placeholder route with a real operator observability workspace consuming live `GET /ops/agent-roster` and `GET /ops/agent-health` endpoints. New API layer (`fetchAgentRoster`, `fetchAgentHealth`) with typed response shapes from AGENT_OPS_CONTRACT.md. TanStack Query hooks (`useAgentRoster`, `useAgentHealth`) with appropriate stale times. Deterministic view-model adapter (`buildOpsWorkspaceViewModel`) that joins health onto roster by entity_id, preserves hierarchy, ignores unknown health-only entities, and marks missing-health roster entities as unavailable. Full workspace UI: summary/trust bar, governance layer section, officer layer section, department sections with framed boxes, entity cards with health orb indicators, selected-node detail panel. Mode pills (Org/Run/Health) with Run and Health disabled (Phase 7). Degraded banners for health-failed and empty-health states. All required state handling: loading, healthy success, roster success + health failure, roster success + empty health, roster failure, join mismatch safety. Dark control-room aesthetic with teal/amber/red orb system. 23 new tests (adapter unit tests + component integration tests). Build passes, typecheck clean, 89 tests green. No backend modifications. `/ops` proxy added to Vite dev server config.

### Previous increment — PR-OPS-1: Agent Ops Contract Spec (13 Mar 2026)

Delivered PR-OPS-1 — Agent Operations endpoint contract specification. Created `docs/ui/AGENT_OPS_CONTRACT.md` with implementation-ready contracts for `GET /ops/agent-roster` (static architecture and roster truth) and `GET /ops/agent-health` (current health snapshot). Shared types locked: `DepartmentKey` (4 canonical values), `ResponseMeta`, `OpsErrorEnvelope`. Full response shapes specified: `AgentRosterResponse` (governance_layer, officer_layer, departments, relationships), `AgentHealthSnapshotResponse` (entities with separate run_state and health_state dimensions). Polling model locked (no SSE, no WebSocket). Roster ↔ health join rule explicit. Contract test priorities listed for PR-OPS-2. Reserved future endpoints acknowledged (Phase 7: agent-trace, agent-detail). `UI_CONTRACT.md` updated with §10.6 cross-reference. Zero code files changed.

### Previous increment — PR-UI-3: Shared Component Extraction (13 Mar 2026)

Delivered PR-UI-3 — shared component extraction and hardening. EntityRowCard made generic (Option A: label/pill/meta/description/badge props), triage-specific TriageRowCard wrapper created. useTriggerTriage moved to workspaces/triage/hooks/ (triage-specific mutation). Hook cache key conventions standardised (exported named constants, explicit return types, documented stale times). All shared component props exported. Barrel index files created for all 5 component subdirectories and hooks. TriageBoardPage refactored to barrel imports with zero inline shared components. 36 new isolated component tests. Shared README with component inventory, import examples, hook reference, and contributor guidance. Build passes, typecheck clean, 66 tests green (36 new). No backend modifications.

### Previous increment — PR-UI-2: Triage Board MVP (13 Mar 2026)

Delivered PR-UI-2 — the Triage Board MVP with real backend data rendering, shared components, and trust strip. Replaces the Phase 1 placeholder with a working triage board consuming `GET /watchlist/triage` and `POST /triage`. Includes: feeder health API client (`fetchFeederHealth`) matching §9.9, view-model adapter layer, TanStack Query hooks (`useWatchlistTriage`, `useTriggerTriage`, `useFeederHealth`), 10 shared components across 5 subdirectories (state, trust, layout, feedback, entity), all 7 state conditions handled (loading, ready, empty, stale, unavailable, demo-fallback, error), board-level trust strip always visible (data_state badge + feeder health chip + timestamp), per-row staleness derived from `verdict_at` only, Run Triage trigger-and-refresh with partial failure surfacing, row click navigates to `#/journey/{symbol}`. Build passes, typecheck clean, 30 tests green (24 new). No backend modifications.

### Previous increment — PR-UI-1: React App Shell (13 Mar 2026)

Delivered PR-UI-1 — the React + TypeScript + Tailwind app shell in `ui/`. Includes Vite build tooling, hash-based routing for all workspaces, typed API client layer (`apiFetch<T>`) with mixed error-detail preservation per UI_CONTRACT.md §11, typed triage endpoint functions (`fetchWatchlistTriage`, `triggerTriage`) matching §9.5, TanStack Query scaffolding, Vite proxy config for backend API, Tailwind styling, and Vitest smoke tests. All routes render placeholder pages (no blank pages). Default route redirects to `#/triage`. Build passes, typecheck clean, 5 smoke tests green. Repo-shape locked: `ui/src/shared/` for cross-workspace code, `ui/src/workspaces/<name>/` for workspace-specific code. Coexists with legacy `app/` — no backend modifications.

### Previous increment — UI Re-Entry Governance (13 Mar 2026)

Reopened UI implementation lane. Locked React + TypeScript + Tailwind as forward stack. Triage Board is the first React workspace and component-system seed. Agent Operations classified as Phase 3B extension: an operator observability, explainability, and trust workspace built on new read-only projection endpoints. Agent Ops north-star question: "Why should I trust this system right now?" Agent Ops MVP is not config, prompt editing, manual orchestration, model-switching, or chat-with-agents. HTML prototype is visual reference only. Execution plan committed as `docs/specs/ui_reentry_phase_plan.md`.

### Previous increment — Observability Phase 2 implementation (12 Mar 2026)

- Implemented structured JSON event emission across 4 under-instrumented lanes (MDO scheduler, feeder ingest, triage, graph orchestration).
- APScheduler lifecycle listeners registered for job executed/error/missed/max_instances events.
- Feeder ingest zero-logging gap closed: ingest received/complete, per-event mapping failures, staleness recovery detection.
- Triage batch summary with partial-failure classification, per-symbol timing, and error categorization (Guardrail B: log-only, no response shape change).
- Graph routing decisions logged at both conditional branch points; pipeline start event with fan-out info.
- /metrics endpoint additively extended with feeder_status section.
- 16 event codes mapped under 6 canonical categories per taxonomy nesting rule (Guardrail A).
- 18 new deterministic tests in `ai_analyst/tests/test_obs_p2_events.py`.
- Test suite: 1236 passed (+18), 70 failed (pre-existing), 4 collection errors (pre-existing). Zero new regressions.

### Previous increment — Observability Phase 2 diagnostic pass (12 Mar 2026)

- Executed the full Section 10 diagnostic protocol for cross-lane runtime visibility.
- Audited logging infrastructure across 8 runtime lanes.
- Published spec: `docs/specs/observability_phase_2.md` with logging inventory, failure taxonomy, patch set proposal.

### Previous increment — UI Phase 3A workspace blueprint + visual design (12 Mar 2026)

- Completed the full workspace blueprint and visual design layer for Phase 3A core product workspaces.
- Published `docs/ui/UI_WORKSPACES.md` — defines seven workspaces organized into Runtime, Review, and Operator lanes with a Triage Board → Journey Studio → Analysis Run → Journal & Review primary flow.
- Published `docs/ui/DESIGN_NOTES.md` — captures all visual and interaction decisions (per-row staleness derivation, freeze-locks-entire-flow, Save Result gating, tab persistence, data_state read-only rule, no-fake-detail-screen constraint) so implementation can proceed without reverse-engineering wireframes.
- Published `docs/ui/VISUAL_APPENDIX.md` — consolidated reference sheet linking all final wireframe and component system images.
- Wireframes produced and locked for: Triage Board (3 iterations), Journey Studio (2 iterations), Analysis Run (3 iterations with 4-state lifecycle grid).
- Component Design System produced with four columns (Trust/Freshness Indicators, Action Buttons, Information Panels, State Labels) plus four Composition Patterns (trust strip, execution stack, conditional rail, post-action lock).
- All design artifacts are contract-faithful — every element maps to `UI_CONTRACT.md` sections 6, 7, 9–12 and `UI_WORKSPACES.md` sections 5–7.
- Phased exposure plan defined: Phase 3A (Triage Board, Journey Studio, Journal & Review, Analysis Run cleanup), Phase 3B (Feeder, Ops, Analytics, optional streaming), Phase 3C (Chart Evidence, Run Artifact Inspector).

### Previous increment — UI Phase 2 UI contract (12 Mar 2026)

- Completed the canonical frontend handoff doc for the current repo surface: `docs/ui/UI_CONTRACT.md`.
- The contract locks source-of-truth rules (Python routes first, stale generated OpenAPI second), endpoint-family error behavior, shared `data_state` semantics, and a canonical UI run-state model.
- It also formalizes the Journey-vs-legacy split, timeout/retryability expectations, and the rule that frontend implementation should update the contract deliberately rather than rediscover backend behavior ad hoc.

### Previous increment — UI Phase 1 backend capability audit (12 Mar 2026)

- Completed a repo-grounded backend-to-UI capability audit and published `docs/ui/UI_BACKEND_AUDIT.md`.
- Inventory includes live FastAPI routes, request/response model shapes, runtime execution modes (sync vs SSE), artifact surfaces, and current `/app` usage coverage.
- Audit explicitly maps active-used vs active-unused capabilities to guide follow-on `UI_CONTRACT` and `UI_WORKSPACES` documentation phases.

### Previous increment — AI Analyst dev diagnostics (11 Mar 2026)

- Added dev-gated diagnostics for `/analyse` and `/analyse/stream` to improve local failure triage without external observability tooling.
- JSON-backed multipart fields now emit raw-value parse logs in dev mode and return structured 422 details (`field`, `raw_value`, `expected_shape`, parse error, `request_id`).
- Request lifecycle stage tracing now records high-signal checkpoints (request/auth/parse/graph/fan-out/arbiter/artifact/complete) and persists local diagnostics records per request.
- Added `AI_ANALYST_DEV_DIAGNOSTICS=true` / `DEBUG=true` gating so production behavior remains conservative by default.
- Multipart request parsing for string-array form fields (`timeframes`, `no_trade_windows`, `open_positions`, `overlay_indicator_claims`) now tolerates both JSON array strings and Swagger-style CSV input while preserving structured 422 diagnostics and request-id traceability.

### Current position (plain language)

You are no longer proving feasibility, building runtime behavior, or standing up initial UI surfaces. The full UI documentation lane, runtime-hardening sequence, core product lane (Phase 6: Triage Board → Journey Studio → Analysis Run → Journal & Review), and Agent Ops read-side stack (Phase 7: roster, health, trace, detail endpoints + Org/Health/Run frontend modes) are all complete and shipped. **The repo is between active phases.** 197 backend ops tests + 63 frontend ops tests + 243 total frontend tests. Forward frontend stack remains React + TypeScript + Tailwind. Next decision: evaluate Phase 8 candidates (see Roadmap).

### Phase Status Overview

| Phase | Description | Status |
|-------|-------------|--------|
| Phase A | Single analyst smoke path | ✅ Complete |
| Phase B | Central provider/model config | ✅ Complete |
| Phase C | Quorum/degraded failure handling | ✅ Complete |
| Phase D | V1.1 snapshot integrity patch (H-1 → H-4) | ✅ Complete |
| Phase 1A | Market Data Officer — EURUSD baseline spine | ✅ Complete |
| Phase 1B | Market Data Officer — XAUUSD spine (15m, 1h, 4h, 1d) | ✅ Complete |
| Phase E+ | Additional instruments, provider abstraction | ✅ Complete |
| Instrument Promotion | GBPUSD/XAGUSD/XPTUSD → trusted — 419/419 tests | ✅ Complete |
| Per-Instrument Provider Routing | Explicit per-instrument provider policy — 468/468 tests | ✅ Complete |
| Operationalise Phase 1 | APScheduler feed refresh — 494/494 tests | ✅ Complete |
| Operationalise Phase 2 | Market-hours awareness, alerting, runtime posture — 644/644 tests | ✅ Complete |
| TD-1 Micro-PR | Arbiter assert fix — explicit persona contract enforcement — 645 tests | ✅ Complete |
| Security/API Hardening | Auth gate, graph + LLM timeouts, error contracts, body limits, TD-2 closure — 677 tests | ✅ Complete |
| CI Seam Hardening | CI-gate MDO + root Python seams, stream event semantics — 1743 tests across 5 CI jobs | ✅ Complete |
| LLM Routing Centralisation | Single-source routing via ResolvedRoute contract, 13 bypass removals, 27 new tests — 643 tests | ✅ Complete |
| Observability Phase 1 | Analyst pipeline run visibility — run_record.json + stdout summary — 668 tests | ✅ Complete |
| UI Phase 1 | Backend Capability Audit — `docs/ui/UI_BACKEND_AUDIT.md` | ✅ Complete |
| UI Phase 2 | UI Contract — canonical frontend handoff / run-state + error semantics | ✅ Complete |
| UI Phase 3A | Workspace Blueprint + Visual Design — wireframes, component system, design notes, visual appendix | ✅ Complete |
| Phase 0 — UI Re-Entry Governance | Governance unlock — progress hub + design note + phase plan | ✅ Complete |
| UI Phase 3A Impl | UI implementation — Triage Board through Journal & Review (Phase 6 core product lane) — 243 frontend tests | ✅ Complete |
| Phase 1 — React App Shell + Triage Route | React app shell + routing + typed fetch — build clean, typecheck clean, 5 smoke tests | ✅ Complete |
| Phase 2 — Triage Board MVP | Real triage data + shared components + trust strip — build clean, typecheck clean, 30 tests | ✅ Complete |
| Phase 3 — Shared Component Extraction | Barrel exports, typed props, generic EntityRowCard, hook ownership, 36 component tests, shared README — 66 tests | ✅ Complete |
| Phase 4 — Agent Ops Contract (PR-OPS-1) | Endpoint contract spec for /ops/agent-roster and /ops/agent-health — zero code changes | ✅ Complete |
| Phase 5 — Journey Studio MVP (PR-UI-4) | Journey Studio workspace — staged flow, freeze lifecycle, bootstrap context, 43 tests — 132 tests | ✅ Complete |
| Phase 6a — Analysis Run MVP (PR-UI-5) | Analysis Run workspace — multipart /analyse, run lifecycle state machine, tab persistence, 69 tests — 201 tests | ✅ Complete |
| Phase 6b — Journal & Review MVP (PR-UI-6) | Journal & Review workspace — decision readback, review toggle, outcome coverage, 42 tests — 243 tests | ✅ Complete |
| Phase 4 — Agent Ops Backend (PR-OPS-2) | Backend implementation — roster + health endpoints — 55 tests | ✅ Complete |
| Phase 7 — Agent Trace (PR-OPS-4a) | Backend agent-trace endpoint — run_record.json + audit log projection — 70 tests (126 ops suite) | ✅ Complete |
| Phase 7 — Agent Detail (PR-OPS-4b) | Backend agent-detail endpoint — discriminated union, profile registry — 72 tests (197 ops suite) | ✅ Complete |
| Phase 7 — Frontend Health Mode (PR-OPS-5a) | Types, adapters, hooks, Health mode wiring — 16 new tests (39 frontend) | ✅ Complete |
| Phase 7 — Frontend Run + Detail (PR-OPS-5b) | Run mode, trace vis, detail sidebar, run selector — 24 new tests (63 frontend) | ✅ Complete |
| UI Phase 3B | Backend capability exposure — Agent Ops ✅ complete, Feeder/Analytics/streaming remain parked | ⏸️ Partial |
| Observability Phase 2 | Cross-lane runtime visibility — structured events across MDO, feeder, triage, graph; 18 new tests, 16 event codes under 6 canonical categories | ✅ Complete |
| TD-3 | Packaging/import-path stability — 27 sys.path.insert calls removed, pyproject.toml fixed, 16 import stability tests added — 1603 tests | ✅ Complete |
| Cleanup Tranche | Async markers, doc consolidation, TD-5/TD-9 micro-PRs | ✅ Complete |
| Doc Consolidation (PR-4) | Consolidate status tracking around canonical progress hub — README de-conflict, architecture de-conflict, UI lane framing, historical placement hygiene | ✅ Complete |
| Tidy | Async marker cleanup (8 files) | ✅ Complete — all 30 redundant `@pytest.mark.asyncio` markers removed; `asyncio_mode = "auto"` handles detection |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |

---

## 2) Where We Are Now (Grounded Status)

### Architecture and product posture

- Project doctrine is clearly data-first (market packets first, screenshots as optional supporting evidence).
- The product surface includes:
  - static browser workflow + gate logic
  - Python analyst API/CLI pipeline
  - MDO feed/packet generation
  - Macro Risk Officer context lane

### Runtime integration reality

The repo architecture is coherent, but the live runtime is **not yet a single fully unified lane**.

- The active `ai_analyst` API/graph path is GroundTruth/LangGraph-based.
- Direct `ai_analyst` → `market_data_officer` runtime coupling was **not** established in the audit.
- Concrete MDO coupling is present in the **legacy analyst lane** and in some root/test integrations.
- UI integration is API-first through FastAPI routes such as `/analyse`, `/triage`, `/watchlist/triage`, `/journey/*`, and `/feeder/*`.

This means Market Data Officer progress is strategically important, but it should not be overstated as the sole live runtime backbone of the current analysis path.

### Delivery maturity indicators

- `docs/specs/README.md` now serves as a specs inventory aligned to this canonical progress hub (not a competing status source).
- Security/API Hardening has now shipped four concrete hardening surfaces:
  - API auth gate
  - graph execution timeout
  - `call_llm()` timeout/retry/failure mapping
  - safer API error contracts and request-boundary enforcement
- The technical debt register summary in this file remains canonical for execution context; the enduring debt ledger is tracked in `docs/architecture/technical_debt.md`.
- The UI contract now serves as the intended anti-corruption layer between backend behavior and future `/app/` implementation work.
- The full UI documentation lane (`docs/ui/`) is complete with five artifacts: `UI_BACKEND_AUDIT.md`, `UI_CONTRACT.md`, `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, and `VISUAL_APPENDIX.md`.
- Test suites run cleanly in the current merged state.

### Test count progression

Phase-closure counts should be read as **phase-gate numbers**, not as a single additive suite inventory.

| Phase | Tests | What it proved |
|------|------:|----------------|
| Phase 1A | 359 | EURUSD full relay spine |
| Phase 1B | 364 | XAUUSD spine |
| Phase E+ | 404 | Instrument registry |
| Provider Switchover | 404 | yFinance fallback + vendor provenance |
| Phase F | 419 | All 5 instruments trusted |
| Provider Routing | 468 | Per-instrument provider policy |
| Operationalise Phase 1 | 494 | APScheduler feed refresh |
| Operationalise Phase 2 — PR 1 | 549 | Market-hours awareness + freshness classification |
| Operationalise Phase 2 — PR 2 | 597 | Deterministic failure alerting + edge-triggered recovery |
| Operationalise Phase 2 — PR 3 | 644 | Runtime posture, startup validation, health-check, operator runbook |
| TD-1 | 645 | Arbiter assert fix |
| Security/API Hardening | 677 | Auth gate, graph + LLM timeouts, error contracts, body limits, TD-2 closure |
| CI Seam Hardening | 1743 | MDO + root Python seams CI-gated, stream event semantics, 5 CI jobs |
| LLM Routing Centralisation | 643 | Single-source routing via ResolvedRoute; 13 bypass removals; 27 new deterministic route/bypass tests |
| Observability Phase 1 | 668 | Run record + stdout summary; per-analyst result/skip/fail visibility; 25 new deterministic tests |
| Observability Phase 2 (diagnostic) | 1218 passed, 70 failed (pre-existing), 4 collection errors | Cross-lane diagnostic baseline: ai_analyst 435, tests 139, MDO 644. Failures are code-vs-test drift, not new regressions. |
| Observability Phase 2 (implementation) | 1236 passed, 70 failed (pre-existing), 4 collection errors | +18 new tests: MDO events (3), APScheduler listeners (5), feeder ingest (3), triage batch (1), graph routing (3), taxonomy completeness (3). Zero new regressions. |
| PR-OPS-4a (Agent Trace) | 126 (ops suite) | +71 new trace tests. 55/55 baseline preserved. Zero regressions. |
| PR-OPS-4b (Agent Detail) | 197 (ops suite) | +72 new detail tests. 125/125 baseline+trace preserved. Zero regressions. All 25 spec ACs pass. |
| PR-OPS-5a (Health Mode Wiring) | 39 (frontend) | +16 new tests. Types, adapters, hooks, Health mode, data_state banners, OpsErrorEnvelope. 23/23 baseline preserved. |
| PR-OPS-5b (Run + Detail Wiring) | 63 (frontend) | +24 new tests. Run mode, trace vis, detail sidebar, discriminated union rendering. 39/39 baseline preserved. Phase 7 complete. |

### Known gaps and debt themes

From repo docs and current structure, the meaningful remaining work is concentrated in:

1. **Observability and seam visibility** — ✅ **Phase 2 Complete** (12 March 2026)
   - Observability Phase 1 shipped run records and stdout summaries.
   - Observability Phase 2 shipped 16 structured event codes across MDO scheduler, feeder, triage, graph.
   - Agent Ops trace endpoint (Phase 7) projects run-level observability to the UI.
2. **Packaging and import stability** — ✅ **Complete** (TD-3, 12 March 2026)
   - 27 `sys.path.insert` calls removed; `pyproject.toml` fixed; `pip install -e .` works in clean venv.
   - 16 import stability tests added (TD-11 resolved).
3. **Cleanup and consistency** — ✅ **Complete** (13 March 2026)
   - Async-marker cleanup done (30 markers removed).
   - TD-5 (enum centralisation) and TD-9 (unused vars) resolved.
   - Doc consolidation complete.
4. **UI implementation** — ✅ **Core product lane complete** (14 March 2026), **Agent Ops complete** (15 March 2026)
   - Phase 6: Triage Board, Journey Studio, Analysis Run, Journal & Review — all shipped.
   - Phase 7: Agent Ops Org/Health/Run modes + Detail sidebar — all shipped.
   - Forward stack: React + TypeScript + Tailwind.
   - Phase 3B remainder (Feeder, Analytics, streaming) and Phase 3C (Chart Evidence, Run Artifact Inspector) remain fenced.
5. **Future runtime-lane convergence**
   - The split between analyst, graph, MDO, and legacy lanes still shapes long-term architecture cleanup.
   - Now lower priority — observability, packaging, and cleanup are all done.

---


## 3) Where We Should Go Next

The production-readiness gate is **satisfied**. The UI documentation lane is complete. The runtime-hardening sequence is complete. The core product lane (Phase 6) and Agent Ops read-side stack (Phase 7) are both **complete and shipped**. 

**Phase 8 direction: Charts + Reflective Intelligence.** Two capability tracks after a Run Browser foundation:
1. **Live candlestick charts** — OHLCV data served from MDO pipeline, rendered via `lightweight-charts`, embedded in Run mode context (not a separate workspace)
2. **Reflective Intelligence v1** — persona performance aggregation, pattern summaries, rules-based advisory-only suggestions (aggregation only, no ML, minimum 10 runs per bucket before showing stats)

Both depend on run history volume. Run Browser (PR-RUN-1) ships first — header-only run index, bounded and paginated. Full plan: `docs/PHASE_8_PLAN.md`.

### Priority A — Observability Phase 2: Cross-Lane Runtime Visibility (✅ complete)

#### Objective
Standardize structured event logging across all runtime lanes and make it easy to answer "what failed, where, and why?" without manually tracing code paths.

#### Context
The repo has multiple moving lanes (analyst pipeline, graph orchestration, MDO feed refresh, feeder context, legacy surfaces). Observability Phase 1 shipped run records and stdout summaries for the analyst pipeline. Phase 2 should extend visibility across orchestration boundaries and tighten failure surfaces for operators and contributors.

#### Deliverables
- Standardize structured event logging for feed runs and analysis requests where still inconsistent.
- Tighten status surfaces around scheduler/runtime health and analysis-path failures.
- Clarify what success/failure/recovery looks like across MDO and analyst runtime lanes.
- Make cross-lane failures visible without requiring manual code-path tracing.

#### Done criteria
- Operators and contributors can answer "what failed, where, and why?" from logs and status surfaces alone.
- Seam behavior across orchestration boundaries is visible, not inferred.
- Structured logging is consistent enough that future monitoring/alerting can be built on top of it.

---

### Priority B — TD-3: Packaging and Import-Path Stability (✅ complete)

#### Objective
Remove the `sys.path.insert` wiring footgun and establish proper packaging discipline.

#### Context
The technical debt register flags TD-3 as the main prerequisite for multi-environment stability and contributor onboarding. This is the structural wiring fix that makes everything downstream safer.

#### Deliverables
- Replace `sys.path.insert` usage with proper packaging (`pyproject.toml` / editable install).
- Add import-path stability tests (TD-11 resolves as a follow-on).
- Validate that the repo works cleanly in fresh environments without manual path manipulation.

#### Done criteria
- The repo is less environment-sensitive.
- New contributors can set up and run without discovering import-path quirks.
- TD-11 (import-path stability tests) can be closed as a follow-on.

---

### Priority C — Cleanup Tranche (✅ complete)

#### Objective
Close small friction items that reduce drift and improve contributor experience, without expanding into architecture surgery.

#### Deliverables
- Resolve pending async-marker cleanup (4 files).
- Execute TD-5 (enum centralisation) and TD-9 (unused vars) as micro-PRs.
- Reconcile duplicate phase summaries across docs.
- Update `docs/specs/README.md` and docs indexes.
- Keep the technical debt register current.

#### Done criteria
- New contributors can identify current phase and next implementation target in under 5 minutes.
- There is no ambiguity about which progress document is authoritative.
- TD-5 and TD-9 are closed.

---

### Priority D — UI Phase 3A Implementation (✅ complete)

#### Objective
Build the Phase 3A core product workspaces using the locked design artifacts.

#### Status
**Complete.** All Phase 3A core product workspaces shipped (13–14 March 2026):
- PR-UI-1: React app shell (5 tests)
- PR-UI-2: Triage Board MVP (30 tests)
- PR-UI-3: Shared component extraction (66 tests)
- PR-UI-4: Journey Studio MVP (132 tests)
- PR-UI-5: Analysis Run MVP (201 tests)
- PR-UI-6: Journal & Review MVP (243 tests)

Agent Ops read-side stack also complete (Phase 7, 15 March 2026):
- PR-OPS-1/2/3: Contract, backend, workspace shell
- PR-OPS-4a/4b: Trace + detail backend endpoints (197 backend tests)
- PR-OPS-5a/5b: Frontend wiring — Org/Health/Run modes + detail sidebar (63 frontend tests)

Phase 3B remainder (Feeder, Analytics, streaming) and Phase 3C (Chart Evidence, Run Artifact Inspector) remain fenced.

---

### Priority E — Future Runtime-Lane Convergence and Extensions (later)

#### Objective
Reduce the architectural split between runtime lanes and address broader convergence only after observability, packaging, and cleanup are stronger.

#### Deliverables
- Revisit duplicated orchestration (TD-4) and mixed data-shape handling (TD-8) when seam confidence is stronger.
- Treat Chart Evidence and Run Artifact Inspector as Phase 3C post-foundation UI extensions.
- Address runtime-lane convergence (analyst, graph, MDO, legacy) as a deliberate architecture phase, not a side-effect of other work.

#### Done criteria
- Future cleanup and UI extension work can happen against stronger contracts and better CI coverage.

#### Future architecture direction (post-foundation)

**Future Design Direction — Reflective Intelligence Layer:** Human-governed review and policy-refinement architecture built on run-record audit trails. Intended to use Agent Ops observability and Journal & Review artifacts to surface recurring weaknesses, generate bounded hypotheses, and propose reversible policy changes for human approval. Becomes viable once the repo has stable run artifacts, Agent Ops observability surfaces, Journal & Review readback, and sufficient historical run volume. Not part of current UI re-entry implementation scope. Design note: `docs/design-notes/reflective_intelligence_layer.md`.

---

## 4) Proposed 6–8 Week Plan

### Completed (Weeks 1–4, 13–15 March 2026)

- **PR-UI-1** (React app shell) ✅
- **PR-UI-2** (Triage Board MVP) ✅
- **PR-UI-3** (Shared component extraction) ✅
- **PR-OPS-1** (Agent Ops contract spec) ✅
- **PR-UI-4** (Journey Studio MVP) ✅
- **PR-UI-5** (Analysis Run MVP) ✅
- **PR-UI-6** (Journal & Review MVP) ✅ — Phase 6 complete
- **PR-OPS-2** (Agent Ops roster + health backend) ✅
- **PR-OPS-3** (Agent Ops workspace shell) ✅
- **PR-OPS-4a/4b** (Agent trace + detail backend) ✅
- **PR-OPS-5a/5b** (Agent Ops frontend wiring) ✅ — Phase 7 complete

### Forward (Weeks 5–8, Phase 8: Charts + Reflective Intelligence)

Prioritisation complete (15 March 2026). Two capability tracks running in parallel after Run Browser:

**Week 5 (Week 1 of Phase 8): Run Browser**
- PR-RUN-1: `GET /runs/` endpoint + RunBrowserPanel frontend — replaces paste-field run selector

**Weeks 6–7 (Weeks 2–3): Live Candlestick Charts**
- PR-CHART-1: OHLCV data endpoint + `lightweight-charts` candlestick component
- PR-CHART-2: Run context overlay + multi-timeframe support

**Weeks 7–8 (Weeks 4–5): Reflective Intelligence v1**
- PR-REFLECT-1: Persona performance + pattern summary aggregation endpoints
- PR-REFLECT-2: Reflective dashboard frontend — performance tables + anomaly highlighting

**Week 9 (Week 6): Integration + Suggestions v0**
- PR-REFLECT-3: Chart ↔ run integration, rules-based parameter suggestions

Full plan: `docs/PHASE_8_PLAN.md`

---

## 5) Risks to Manage

- ~~**Observability gap risk:**~~ **Resolved** — Obs Phase 1 + Phase 2 complete. Agent Ops trace endpoint ships run-level visibility to the UI.
- ~~**Packaging fragility risk:**~~ **Resolved** — TD-3 complete (12 March 2026). All `sys.path.insert` calls removed; `pip install -e .` is the canonical install path.
- ~~**Contract drift risk:**~~ **Mitigated** — 12 PRs shipped against `UI_CONTRACT.md` and `AGENT_OPS_CONTRACT.md` without contract drift. Governance rules held.
- ~~**Design-implementation drift risk:**~~ **Mitigated** — all Phase 3A wireframes implemented faithfully across PR-UI-1 through PR-UI-6.
- **UI split risk:** Journey and legacy workflow surfaces diverge further if compatibility boundaries are not documented clearly.
- **Seam blind-spot risk:** broad unit coverage may still miss cross-module orchestration and integration regressions.
- ~~**Cleanup drift risk:**~~ **Resolved** — cleanup tranche complete (13 March 2026).
- **Scope-creep risk:** future extensions such as Chart Evidence or Run Artifact Inspector could jump ahead of prioritisation.
- **Run discovery gap:** Agent Ops Run mode requires manual run_id entry (paste field). No run browser/search endpoint exists yet. Operators must know the run_id to inspect a run. Tracked in Roadmap as Priority 1.

---

## 6) Immediate Next Actions (Concrete)

1. ~~CI Seam Hardening~~ — ✅ Complete (10 March 2026).
2. ~~LLM Routing Centralisation~~ — ✅ Complete (11 March 2026).
3. ~~Observability Phase 1~~ — ✅ Complete (11 March 2026). Run record + stdout summary shipped. 668 tests.
4. ~~UI Phase 1 — Backend Capability Audit~~ — ✅ Complete (12 March 2026). `docs/ui/UI_BACKEND_AUDIT.md`.
5. ~~UI Phase 2 — UI Contract~~ — ✅ Complete (12 March 2026). `docs/ui/UI_CONTRACT.md` promoted to **Active**.
6. ~~UI Phase 3A — Workspace Blueprint + Visual Design~~ — ✅ Complete (12 March 2026). `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, `VISUAL_APPENDIX.md`, wireframes, and component design system all locked.
7. ~~Observability Phase 2~~ — ✅ Complete (12 March 2026). Diagnostic + implementation shipped. 16 structured event codes across MDO scheduler, feeder, triage, graph. 18 new tests. Spec: `docs/specs/observability_phase_2.md`.
8. ~~TD-3 — packaging/import-path stability~~ — ✅ Complete (12 March 2026). 27 sys.path.insert calls removed, pyproject.toml fixed, 16 import stability tests added. Spec: `docs/specs/td3_packaging_import_stability.md`.
9. ~~Cleanup tranche~~ — ✅ Complete (13 March 2026). Async markers cleaned, TD-5 enum centralisation resolved, TD-9 unused vars resolved, doc consolidation complete.
10. ~~Runtime-hardening sequence~~ — ✅ Complete. Obs P2, TD-3, and cleanup tranche all closed.
11. ~~**UI + Agent Ops implementation lane**~~ — ✅ Complete (15 March 2026). PR-UI-1 through PR-UI-6 (Phase 6 core product lane) and PR-OPS-1 through PR-OPS-5b (Phase 7 Agent Ops read-side stack) all shipped. 197 backend tests + 63 frontend tests. All spec ACs verified.
12. Core product workflow lane is now complete end-to-end: Triage Board → Journey Studio → Analysis Run → Journal & Review.
13. Agent Ops operator trust surface is now complete: Org mode → Health mode → Run mode → Detail sidebar, all wired to four backend endpoints.
14. Keep **Chart Evidence Workspace** and **Run Artifact Inspector** in the post-foundation extension lane (Phase 3C).
15. **Next decision:** evaluate Phase 8 candidates — Run Browser endpoint (enables run discovery in Ops), Chart Evidence (Phase 3C), Control-Plane Actions, or Reflective Intelligence Layer. See Roadmap table.

---

## 7) Decision Gate Before "Production-Ready" Claim

Most of the earlier production-readiness gate has now been satisfied.

**Already satisfied:**
- Operational scheduler running with observable health.
- Market-hours behavior and stale-data handling tested and deterministic.
- Critical API guardrails tested and enforced.
- `call_llm()` safeguards and resilience coverage shipped.
- Single canonical progress/status document maintained.

**Remaining gate — now closed (CI Seam Hardening, 10 March 2026):**
- ✅ Important Python integration seams are CI-gated where intended — `mdo-tests` (644 tests) and `root-python-tests` (139 tests) jobs added.
- ✅ At least one orchestration integration path is green in CI — `test_multi_analyst_integration.py` (make_packet → digest → personas → arbitrate → output) runs in `root-python-tests`.

**The production-readiness gate is now satisfied.**

The current execution gate is no longer production-readiness; runtime hardening (observability, packaging, developer/operator confidence) and UI buildout (Phase 6 core product lane + Phase 7 Agent Ops) are both complete. The repo is between active phases.

---

## 8) Technical Debt Register

Findings from the senior architect audit conducted after Operationalise Phase 2 closure (644 tests, 10 March 2026). Items are severity-ranked and tagged with recommended resolution timing.

### Critical — resolve in next named phase or as micro-PR

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-1 | `assert` used for runtime contract enforcement | `analyst/arbiter.py` | Silent contract violation under `-O` flag; invalid state reaches downstream decision logic | **✅ Resolved — 10 March 2026** |
| TD-2 | `call_llm()` lacks timeout, retry, circuit-breaker | `analyst/analyst.py`, LLM call path | Stalled upstream call blocks processing; unstable tail latency; failure amplification | **✅ Resolved — 10 March 2026** — timeout (60s), retry (2 max, exponential backoff), failure mapping to `RuntimeError`. |
| TD-3 | `sys.path.insert` used as dependency wiring | Multiple core modules | Environment-dependent import resolution; deployment instability; shadowing risk | **✅ Resolved — 12 March 2026** — 27 path hacks removed, pyproject.toml fixed, all packages installable via `pip install -e .`, 16 import stability tests added |

### Maintenance — resolve opportunistically or as named cleanup

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-4 | Orchestration duplication (single vs multi-analyst) | `analyst/service.py`, `analyst/multi_analyst_service.py` | Parallel pipelines with drift risk; lifecycle changes must be made in two places | **Named cleanup** — extract shared orchestration steps into common helper; pick up after seam confidence improves |
| TD-5 | Magic-string enum duplication | `analyst/analyst.py`, `analyst/personas.py`, `analyst/arbiter.py` | Verdict/confidence/alignment enums hand-maintained in multiple modules; drift and inconsistent validation | **✅ Resolved — 13 March 2026** — canonical source `analyst/enums.py`; 5 duplicated definitions removed from 4 modules |
| TD-6 | `build_market_packet()` God-function | `market_data_officer/officer/service.py` | Trust policy, quality, feature extraction, serialization, and logging in one function; hard to test in isolation | **Future cleanup** — decompose when packet assembly needs to evolve; not blocking current work |
| TD-7 | `build_market_packet()` eager loading + `iterrows()` | `market_data_officer/officer/service.py` | O(total_rows) Python loop per request; CPU/memory pressure scales with instrument count | **Future optimisation** — current scale (5 instruments, 4–6 TFs) is within tolerance; revisit when concurrency or instrument count grows |
| TD-8 | Mixed data-shape handling in `classify_fvg_context` | `analyst/pre_filter.py` | `hasattr`/`get` branches for object vs dict payloads; weak upstream contracts | **Resolves with runtime lane convergence** — architectural, not a standalone cleanup |
| TD-9 | ~~Unused variables in `build_market_packet()`~~ | `market_data_officer/officer/service.py` | ~~`is_provisional`, `quality_label`, `quality_flags`, `struct_kwargs` assigned but unused~~ | ✅ **Resolved** (13 March 2026) — all four dead locals removed in PR-3 |

### Documentation / testing gaps — address as part of related phases

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-10 | LLM failure modes under-tested | Test suites for analyst path | Tests previously mocked `call_llm` but did not exercise timeout, malformed response, or retry behavior | **✅ Resolved — 10 March 2026** — resilience coverage landed alongside TD-2 closure |
| TD-11 | No import-path stability tests | No coverage for `sys.path.insert` patterns | Path mutation normalised in tests; packaging regressions not actively caught | **✅ Resolved — 12 March 2026** — 16 import stability tests in `tests/test_import_stability.py` including negative packaging test (AC-12) |
| TD-12 | Cross-module architecture contracts undocumented | Core service boundaries | Ownership of policy decisions, fallback semantics, scaling expectations embedded in code flow | **Future documentation** — address when runtime lanes converge or during next architecture review |

### Resolution sequence

1. **Resolved:** TD-1, TD-2, TD-3, TD-5, TD-10, and TD-11 are closed.
2. **Completed:** CI Seam Hardening (10 March 2026) — production-readiness gate satisfied.
3. **Completed:** TD-3 Packaging/Import Stability (12 March 2026) — 27 sys.path.insert calls removed, pyproject.toml fixed, editable install working, 16 import stability tests.
3. **Completed:** Observability Phase 2 (12 March 2026) — cross-lane runtime visibility.
4. **Completed:** TD-3 (12 March 2026) — packaging/import stability.
5. **Completed:** Cleanup tranche (13 March 2026) — async markers, doc consolidation, TD-5, TD-9.
6. **Completed:** UI Phase 3A Implementation (14 March 2026) — PR-UI-1 through PR-UI-6 shipped. Phase 6 core product lane complete.
7. **Completed:** Phase 7 Agent Ops (15 March 2026) — PR-OPS-4a/4b (backend trace+detail) + PR-OPS-5a/5b (frontend wiring). 197 backend + 63 frontend tests.
8. **Later named cleanup work:** TD-4 (orchestration duplication), TD-6/TD-7 (packet assembly), TD-8 (data-shape convergence), TD-12 (architecture docs).
