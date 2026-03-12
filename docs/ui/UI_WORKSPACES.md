# UI_WORKSPACES

AI Trade Analyst – Workspace Blueprint  
File: `docs/ui/UI_WORKSPACES.md`  
Status: Commit-ready  
Scope: UI / Workflow Layer  
Phase: UI Phase 3  
Depends on: `docs/ui/UI_BACKEND_AUDIT.md`, `docs/ui/UI_CONTRACT.md`, `docs/ui/DESIGN_NOTES.md`

---

## 1. Purpose

This document translates the backend capability map and the UI contract into a practical workspace blueprint for AI Trade Analyst.

Its purpose is to define:

- which workspaces should exist
- which backend capabilities belong in each workspace
- which workspaces are primary versus secondary
- how runtime, review, and operator surfaces should be separated
- what the user should see first
- which features are current-state versus future extension only

This is a product- and workflow-level document, not a frontend framework specification.
It is intentionally non-framework-specific and must remain grounded in the current repo contract.

---

## 2. Design Rules

### 2.1 Contract-first, not screen-first

Every workspace in this document must map back to an existing contract surface in `UI_CONTRACT.md` or be explicitly labeled as a future extension.

No screen should be treated as "real" merely because it is easy to mock visually.

### 2.2 Runtime and review must stay distinct

AI Trade Analyst has two fundamentally different usage modes:

- **runtime work** — triaging assets, running analysis, making and freezing decisions
- **review work** — looking back at decisions, outcomes, diagnostics, analytics, and exports

These modes may share visual components, but they should not be collapsed into a single generic dashboard.

### 2.3 Journey UI is the primary forward path

The Phase 1 audit showed that Journey surfaces already expose triage, bootstrap, decision capture, journal, and review, while the legacy workflow owns analysis submission, usage, and feeder controls. That makes Journey the primary forward UI lane, with the legacy analysis workflow retained as a compatibility and expert-run surface.

### 2.4 `data_state` and run state are different dimensions

Read-oriented workspaces must display `data_state` clearly. Execution-oriented workspaces must display run lifecycle clearly. A workspace may need both at once, but they must not be conflated.

### 2.5 Do not invent missing backend surfaces

The audit confirmed that backend run state is persisted internally, but there is no public run-status endpoint for the UI. It also confirmed that `/analyse/stream` exists, but is not yet wired into the frontend. Workspace planning must respect those boundaries.

### 2.6 Extensions must be fenced as extensions

Features such as chart evidence, run artifact inspection, and richer replay should be planned, but they must be labeled clearly as post-foundation extensions unless the backend already exposes the required contract.

---

## 3. Workspace Map Overview

### 3.1 Primary lanes

| Lane | Purpose | Workspaces |
|---|---|---|
| Runtime | Find opportunities, inspect live context, run analysis, and make decisions | Triage Board, Journey Studio, Analysis Run |
| Review | Revisit frozen decisions and outcomes | Journal & Review, Analytics & Export |
| Operator | Monitor system health, feeder freshness, diagnostics, and platform internals | Feeder & Macro Context, Operations & Diagnostics |

### 3.2 Workspace priority map

| Workspace | Lane | Backend basis | Current repo support | UI priority |
|---|---|---|---|---|
| Triage Board | Runtime | `/watchlist/triage`, `/triage` | current and active-used | Highest |
| Journey Studio | Runtime | `/journey/{asset}/bootstrap`, `/journey/draft`, `/journey/decision`, `/journey/result` | current and active-used | Highest |
| Analysis Run | Runtime | `/analyse`, `/analyse/stream`, `/runs/{run_id}/usage` | current, partly active-used | High |
| Journal & Review | Review | `/journal/decisions`, `/review/records` | current and active-used | High |
| Feeder & Macro Context | Operator / support | `/feeder/ingest`, `/feeder/health` | current and active-used | Medium |
| Operations & Diagnostics | Operator | `/metrics`, `/dashboard`, `/e2e`, `/plugins` | current but active-unused | Medium |
| Analytics & Export | Review / operator | `/analytics/csv`, `/analytics/dashboard`, `/backtest` | current but active-unused | Medium |
| Chart Evidence Workspace | Extension | proposed future surface only | not current | Later |
| Run Artifact Inspector | Extension | no public read contract yet | not current | Later |

This sequencing follows the audit's recommended workspace structure and current capability map.

### 3.3 Default product posture

The default user journey should be:

1. land on **Triage Board**
2. select an asset and enter **Journey Studio**
3. optionally escalate into **Analysis Run** for deeper/manual analysis
4. freeze the decision and later revisit it in **Journal & Review**

This makes the UI feel like a guided trade ideation system rather than a blank analysis form.

---

## 4. Navigation Model

### 4.1 Navigation principle

Navigation should be organized by work mode, not by backend ownership.

Recommended top-level grouping:

- **Runtime**
  - Triage
  - Journey
  - Analysis
- **Review**
  - Journal
  - Review
  - Analytics / Export
- **System**
  - Macro / Feeder
  - Ops / Diagnostics

### 4.2 Non-framework-specific URL plan

This document does not mandate a routing library.
The following paths are a capability map, not a framework commitment.

| Suggested route | Workspace | Notes |
|---|---|---|
| `#/triage` | Triage Board | Recommended default landing route |
| `#/journey/:asset` | Journey Studio | Already aligns with current staged journey model |
| `#/analysis` | Analysis Run | Compatibility / advanced execution workspace |
| `#/journal` | Journal list | Frozen decisions |
| `#/review` | Review list | Decisions with result linkage |
| `#/macro` | Feeder & Macro Context | Support / operator surface |
| `#/ops` | Operations & Diagnostics | Operator-facing surface |
| `#/analytics` | Analytics & Export | Export and historical analysis |

If existing route names differ, retain current implementation and treat this as the logical workspace map.

### 4.3 Lateral navigation

Navigation is not limited to the primary linear flows described in Section 13. Lateral navigation between workspaces should be supported wherever entity linkage exists.

Examples of supported lateral jumps:

- from Journal back to Journey Studio to revisit a decision's context
- from Analysis Run back to Journey Studio when the run was escalated from a journey
- from Review to a related triage item if the symbol is still on the board

These cross-links should be driven by shared entity references (instrument, snapshot_id, run_id) rather than hardcoded routes.

---

## 5. Workspace A — Triage Board

### 5.1 Purpose

The Triage Board is the primary landing workspace.

Its job is to answer:

- what is interesting right now?
- which assets deserve deeper attention?
- is the board live, stale, unavailable, or demo-backed?

### 5.2 Backend basis

- `GET /watchlist/triage`
- `POST /triage`

The audit confirmed this flow is already live and active-used by the Journey Dashboard. `/triage` is a synchronous trigger that writes triage artifacts, and `/watchlist/triage` is the read surface that returns ranked items plus `data_state`.

### 5.3 Primary entities

- `TriageItem`
- triage freshness metadata
- per-symbol confidence / bias summary
- `data_state`

### 5.4 Recommended layout

**Top bar**
- board title
- last generated time
- `data_state` badge
- feeder health chip (compact cross-cutting trust signal)
- "Run Triage" action

**Main board**
- ranked asset cards or rows
- bias / confidence / setup interest summary
- freshness or stale flags per row where derivable from `verdict_at`

**Side / secondary rail**
- contextual board state explanation (conditional — only shows the relevant state)
- demo-fallback badge if applicable
- operator note when board is unavailable

### 5.5 Key actions

- run triage (trigger-and-refresh pattern with idle/running/refreshed button states)
- refresh triage read surface
- open selected asset in Journey Studio (entire row is clickable with hover affordance)
- optionally filter/sort by confidence, regime, or bias if current payload already supports it

### 5.6 Triage → Journey handoff

When the user clicks a triage row, navigation moves to `#/journey/:asset` and the Journey Studio header shows a brief loading state on the bootstrap freshness badge while the synchronous `GET /journey/{asset}/bootstrap` completes. No full-page interstitial is needed.

This is the single most important micro-interaction in the product flow and should feel immediate and intentional.

### 5.7 UX rules

- `POST /triage` should be treated as a trigger-and-refresh flow, not a fully browsable run lifecycle surface
- the board should not imply analyst-by-analyst partial progress unless streaming or progress semantics actually exist
- `data_state` must always be visible because it is a board-level trust signal

### 5.8 Build priority

**Phase 3A — first-class, immediate build/refinement target**

This is the default landing page and the highest-value runtime surface.

---

## 6. Workspace B — Journey Studio

### 6.1 Purpose

Journey Studio is the core decision workspace.

Its job is to turn a promising asset into a disciplined, auditable trade decision flow.

It should feel like a structured ideation journey, not just a data dump.

### 6.2 Backend basis

- `GET /journey/{asset}/bootstrap`
- `POST /journey/draft`
- `POST /journey/decision`
- `POST /journey/result`

The audit confirmed that bootstrap, draft, decision, result, journal, and review routes are active-used by the Journey UI today.

### 6.3 Primary entities

- `JourneyBootstrap`
- draft snapshot
- `DecisionSnapshot`
- result snapshot
- stage-level derived UI state (stages are a UI concept, not a backend entity)

### 6.4 Recommended layout

**Header**
- asset
- current stage (UI-defined flow, not backend-driven)
- bootstrap freshness / availability
- draft status
- snapshot identity when frozen

**Main center column**
- staged trade ideation flow with active stage prominence (completed stages collapse to summary lines, active stage expanded, upcoming stages muted)
- system reading / reasoning summary
- decision form / checkpoints

**Right rail or lower context rail**
- conditional panels driven by bootstrap field presence: arbiter decision summary (when `arbiter_decision` exists), explanation / reasoning summary (when `explanation` or `reasoning_summary` exist), missing evidence or no-trade rationale (when `no_trade_conditions` present)
- single "Bootstrap unavailable" fallback when `data_state` = unavailable (no stacked empty panels)

**Footer / action rail**
- save draft (lightweight secondary)
- freeze decision (primary action, visually prominent)
- save result (disabled/greyed until freeze succeeds)
- return to triage or journal (navigation)

### 6.5 UX rules

- bootstrap must handle `live`, `stale`, `unavailable`, and demo-fallback cleanly
- `POST /journey/decision` is the freeze point and should be visually distinguished from a normal draft save
- freeze locks the entire center column to read-only review state (the immutable snapshot captures full staged context)
- result capture belongs in the same conceptual workspace, but should read as post-decision outcome logging, not pre-trade analysis
- if duplicate decision writes conflict, the UI should surface the conflict explicitly and avoid silent overwrite behavior

### 6.6 Journey → Analysis Run escalation

Users may escalate from Journey Studio into Analysis Run for deeper manual analysis. When this occurs, the Analysis Run workspace should carry context from the journey (instrument, asset identity) and display a provenance breadcrumb ("Escalated from Journey Studio") with a "Return to Journey" navigation option.

The escalation is a warm handoff — context travels with the user rather than requiring a blank-form restart.

### 6.7 Relationship to Journal and Review

Journey Studio is the write surface.
Journal and Review are the readback surfaces.

Do not duplicate review tables inside Journey Studio unless there is a specific in-context need.

### 6.8 Build priority

**Phase 3A — first-class, immediate build/refinement target**

This is the main product workspace.

---

## 7. Workspace C — Analysis Run

### 7.1 Purpose

Analysis Run is the deep execution workspace for manual or expert-triggered analysis.

It exists for cases where the user wants to:

- submit a direct analysis request
- inspect the final verdict and ticket draft immediately
- review per-run usage data
- optionally adopt live-progress mode later via SSE

### 7.2 Backend basis

- `POST /analyse`
- `POST /analyse/stream`
- `GET /runs/{run_id}/usage`

The audit confirmed that `/analyse` and `/runs/{run_id}/usage` are active-used by the legacy workflow UI, while `/analyse/stream` exists but is not wired into the current frontend.

### 7.3 Primary entities

- `AnalysisResponse`
- `FinalVerdict`
- `ticket_draft`
- `run_id`
- `UsageSummary`
- run lifecycle UI state

### 7.4 Recommended layout

**Submission panel**
- instrument/context inputs
- chart upload if applicable
- advanced execution flags where supported
- submission preview (read-only confirmation checkpoint before submit, aligns with `validating` state)

**Execution panel**
- run lifecycle state (idle → validating → submitting → running → completed | failed)
- spinner with elapsed time and preserved run_id/request_id during `running` state
- request validation and boundary errors
- reserved vertical space for future streaming event log (Phase 3B)

**Verdict panel**
- final decision at expert density (full FinalVerdict field set)
- approved setups / no-trade reasons
- confidence and agreement information
- ticket_draft as secondary output
- disabled/greyed with "No verdict — run failed" on failure state

**Usage panel**
- inline accordion below verdict (secondary artifact read)
- usage summary by `run_id`
- fallback-empty handling when usage logs are not yet available or artifact-missing

### 7.5 Tab persistence

All three panels (Submission | Execution | Verdict) remain navigable post-run. Submission becomes read-only but fully accessible so the user can verify "what did I submit?" after the run completes.

### 7.6 Mode split

**Standard mode**
- submit via `/analyse`
- wait for terminal response
- then hydrate usage by `run_id`

**Live mode (optional, not mandatory for Phase 3)**
- submit via `/analyse/stream`
- render heartbeat, analyst completion, verdict, and in-stream errors

The workspace should be designed so that live mode can be added later without redesigning the entire page.

### 7.7 UX rules

- do not promise resumability or browsable run history from this workspace because there is no public run-status/readback contract for that today
- use the canonical run state model from `UI_CONTRACT.md`
- treat streaming as optional enhancement, not baseline dependency
- retry is explicit user action only (no auto-retry per UI_CONTRACT §12.2)
- when escalated from Journey Studio, show provenance breadcrumb and "Return to Journey" navigation

### 7.8 Build priority

**Phase 3A/3B — important but secondary to Triage + Journey**

It should remain available and improved, but it is not the default product landing surface.

---

## 8. Workspace D — Journal & Review

### 8.1 Purpose

Journal & Review is the primary readback lane for frozen decisions and their outcomes.

Its job is to answer:

- what decisions have been recorded?
- which ones have outcomes?
- what should be revisited or reviewed?

### 8.2 Backend basis

- `GET /journal/decisions`
- `GET /review/records`

The audit confirmed that both are active-used and that `ReviewRecord` is essentially decision data plus result linkage.

### 8.3 Primary entities

- `DecisionRecord`
- `ReviewRecord`
- `has_result`
- snapshot identifiers
- saved timestamps

### 8.4 Recommended layout

**Journal view**
- frozen decisions list
- decision metadata
- quick jump back into associated journey context where possible

**Review view**
- decisions plus result linkage
- outcome coverage summary
- "missing result" or "needs follow-up" indicators

**Shared controls**
- search/filter by instrument, date, status
- open review detail when detail contract exists

### 8.5 UX rules

- graceful empty state is normal and must not be treated as failure
- review should visually distinguish "decision exists, no result yet" from "decision exists and has linked result"
- do not create a fake deep detail screen unless there is a backed contract to populate it

### 8.6 Future separation note

Journal and Review are currently presented as two views within one workspace. This is correct for Phase 3A given the thin backend surface. However, if the review contract deepens later (outcome tracking, win/loss attribution, AAR), these may warrant separation into distinct workspaces. Implementation should not hardcode them as inseparable — the shared adapter pattern (ReviewRecord extends DecisionSnapshot per UI_CONTRACT §9.8) already supports this.

### 8.7 Build priority

**Phase 3A — high-value current-state workspace**

This closes the loop on the decision journey and supports reflective workflow without requiring new backend invention.

---

## 9. Workspace E — Feeder & Macro Context

### 9.1 Purpose

This workspace is a support/operator surface for macro ingestion health and context freshness.

It is not the main decision workspace, but it matters because the audit found that parts of the frontend still rely on static local macro JSON rather than backend-fed context.

### 9.2 Backend basis

- `POST /feeder/ingest`
- `GET /feeder/health`

### 9.3 Primary entities

- feeder status
- source health
- age / staleness
- regime / vol bias / confidence when provided

### 9.4 Recommended layout

**Health strip / compact card**
- source status
- age seconds
- stale flag
- last ingest time

**Expanded operator panel**
- ingest trigger or tooling hook where appropriate
- macro context summary
- provenance / source health notes

### 9.5 UX rules

- this workspace should inform trust in macro context, not overwhelm the runtime flow
- compact exposure may be enough for main UI; full detail can live under System navigation
- frontend local fallback data should be visually distinguished from feeder-backed data where possible

### 9.6 Build priority

**Phase 3B — medium priority support surface**

A compact status widget may land earlier than a full dedicated page.

---

## 10. Workspace F — Operations & Diagnostics

### 10.1 Purpose

This workspace exposes system-health and engineering diagnostics that already exist in the backend but are not currently surfaced in the browser UI.

### 10.2 Backend basis

- `GET /metrics`
- `GET /dashboard`
- `GET /e2e`
- `GET /plugins`

The audit confirmed all of these exist today and are active-unused from the UI perspective.

### 10.3 Recommended layout

**Summary cards**
- metrics snapshot
- system status
- plugin counts
- e2e pass/fail overview

**Link-out / embedded surfaces**
- operator dashboard HTML
- diagnostics reports

**Engineering utility blocks**
- plugin registry / hook catalog
- end-to-end check summary

### 10.4 UX rules

- treat this as an operator/engineering workspace, not a trader-first workspace
- HTML dashboard endpoints should be linked or embedded intentionally, not forced into JSON UI assumptions
- avoid mixing this page into the main runtime lane navigation hierarchy

### 10.5 Build priority

**Phase 3B — medium priority, already-backed capability exposure**

This is a high-leverage UI improvement because the backend capability already exists.

---

## 11. Workspace G — Analytics & Export

### 11.1 Purpose

This workspace exposes historical analysis, export, and research-oriented surfaces that already exist but are not yet brought into the main UI.

### 11.2 Backend basis

- `GET /analytics/csv`
- `GET /analytics/dashboard`
- `GET /backtest`

The audit confirmed these routes are current backend capabilities and currently unused by `/app/`.

### 11.3 Recommended layout

**Export panel**
- one-click analytics CSV export
- export scope notes

**Historical analytics panel**
- analytics dashboard link or embed
- basic explanation of what data is included

**Research panel**
- backtest query controls when appropriate
- report render area

### 11.4 UX rules

- CSV export is a download action, not a standard JSON fetch surface
- analytics dashboard is HTML and should be treated as an operator/review surface
- backtest belongs in a research area, not the core triage-to-decision runtime path

### 11.5 Build priority

**Phase 3B — medium priority review/ops surface**

This is useful once the core runtime and review workspaces are clean.

---

## 12. Shared UX State Model Across Workspaces

Every workspace should implement the shared state semantics from `UI_CONTRACT.md` consistently.

Minimum shared states:

- `loading`
- `ready`
- `partial`
- `empty`
- `stale`
- `unavailable`
- `demo-fallback`
- `error`

### 12.1 Runtime-specific emphasis

Triage Board and Journey Studio should prominently surface:

- freshness / availability
- missing evidence or no-trade conditions
- conflict or immutability boundaries for decision freezing

Analysis Run should prominently surface:

- run lifecycle state
- validation failures
- timeout/failure boundaries
- usage readback availability

### 12.2 Review-specific emphasis

Journal & Review should prominently surface:

- empty-but-valid state
- missing-result state
- record linkage clarity

### 12.3 Operator-specific emphasis

Feeder, Ops, and Analytics workspaces should prominently surface:

- stale/unavailable
- link-out vs in-app rendering distinction
- operator confidence signals

### 12.4 Cross-workspace feeder context

Feeder health is not only relevant in its dedicated workspace. Because macro context quality informs analysis results, the Triage Board and Journey Studio should display a compact feeder health indicator (the feeder health chip from the component system) as a cross-cutting trust signal.

This does not require deep feeder integration in runtime workspaces — a lightweight status chip driven by `GET /feeder/health` is sufficient for Phase 3A. Full macro context integration is a Phase 3B decision (see Section 16).

---

## 13. Workspace Relationships

### 13.1 Primary user flow

```text
Triage Board
   ↓
Journey Studio
   ↓
Freeze Decision
   ↓
Journal / Review
```

### 13.2 Expert / compatibility flow

```text
Analysis Run
   ↓
Final Verdict + Ticket Draft
   ↓
Usage by Run ID
```

### 13.3 Support / operator flow

```text
Feeder Health
   ↓
Ops / Diagnostics
   ↓
Analytics / Export
```

### 13.4 Lateral and cross-flow navigation

These flows should be visually distinct even if they share shell navigation. However, navigation is not limited to linear forward progression. Lateral jumps between workspaces should be supported wherever entity linkage exists:

- Journal → Journey Studio (revisit decision context)
- Analysis Run → Journey Studio (return from escalation)
- Review → Triage Board (check if symbol is still active)

These cross-links should be driven by shared entity references (instrument, snapshot_id, run_id) rather than hardcoded routes.

---

## 14. Phased Exposure Plan

### 14.1 Phase 3A — core product workspaces

Prioritize the current-state workspaces that already have strong backend support and high user value:

1. Triage Board
2. Journey Studio
3. Journal & Review
4. Analysis Run compatibility cleanup

Objective:
- make the runtime decision journey feel coherent and deliberate
- reduce blank-page behavior
- strengthen trust with clear state handling and explicit freeze/review loops

### 14.2 Phase 3B — backend capability exposure

After the core product workspaces are coherent, surface already-existing but currently unused capabilities:

1. Feeder & Macro Context
2. Operations & Diagnostics
3. Analytics & Export
4. optional `/analyse/stream` live mode inside Analysis Run

Objective:
- expose dormant backend power without inventing new backend work
- improve operator visibility and research utility

### 14.3 Phase 3C — post-foundation extensions

Only after the core workspaces and current-state exposure are stable:

1. Chart Evidence Workspace
2. Run Artifact Inspector
3. richer replay and comparison surfaces
4. multi-timeframe visual evidence panels if and when backed by contract

Objective:
- add transparency and advanced review depth without polluting the core contract with aspirational UI

---

## 15. Non-Goals

This document does not:

- define a component library or framework migration
- invent new backend routes
- assume a public run-history or run-detail API that does not exist
- force SSE adoption as a prerequisite for core UI flow
- treat chart evidence as current-state contract
- replace `UI_CONTRACT.md` as the frontend source-of-truth document

---

## 16. Open Decisions for Later Phases

These are important, but should not block Phase 3 drafting:

1. Whether `/analyse/stream` should be adopted inside the current Analysis Run workspace or surfaced as a separate live-analysis mode.
2. Whether operator HTML endpoints should be embedded or link-out only.
3. Whether feeder-backed macro context should replace local static macro loading everywhere in the current UI.
4. Whether a public run-detail or run-status endpoint should be added in a future backend phase.
5. When Chart Evidence should move from design-note lane into active implementation.

---

## 17. Visual Design Layer

This document is intentionally layout-agnostic (per Non-Goals §15). The visual layer has been fully specified in a separate contract-backed design system so that implementation can proceed as assembly rather than invention.

**Visual artifacts produced:**
- Triage Board (final locked wireframe, 3 iterations)
- Journey Studio (final locked wireframe, 2 iterations)
- Analysis Run (4-state lifecycle wireframe, final locked, 3 iterations)
- Component Design System + Composition Patterns (reusable library)

**Key visual decisions** are recorded in `DESIGN_NOTES.md` and include: per-row staleness derivation, freeze-locks-entire-flow behavior, Save Result gating, triage-to-journey handoff, Analysis Run tab persistence, verdict tab disabled on failure, inline usage accordion, and Journey escalation breadcrumb.

**Component Design System** (see `DESIGN_NOTES.md` for full spec):
- Trust/freshness indicators (data_state badges, feeder chip, derived stale badges, loading indicators)
- Action buttons with full execution states (primary, secondary, navigation, retry, disabled+tooltip)
- Information panels (verdict card, error detail box, usage accordion, conditional rail panels, empty state, conflict state)
- State labels (run lifecycle, conflict/409, bootstrap unavailable, post-freeze lock, click affordances)

**Composition Patterns** (how components chain in workspaces):
1. Triage header: data_state badge + feeder chip + timestamp (always together as trust strip)
2. Analysis Run execution panel: lifecycle label → spinner → run_id (vertical stack)
3. Journey right rail: conditional stacking vs single unavailable fallback
4. Post-freeze / post-run: uniform read-only lock + disabled buttons + greyed panels

These patterns and the component library are the single source of visual truth for Phase 3A implementation. They map directly to the recommended layouts in sections 5–7 and the contract surfaces in `UI_CONTRACT.md`.

---

## 18. Summary

The workspace model for AI Trade Analyst is organized around a guided runtime flow, a separate review flow, and a clearly demarcated operator lane.

The correct current-state product shape is:

- **Triage Board** as the landing workspace
- **Journey Studio** as the primary decision workspace
- **Analysis Run** as the expert/compatibility execution surface
- **Journal & Review** as the readback loop
- **Feeder, Ops, and Analytics** as secondary capability exposure layers

The workspace blueprint is now complete with both capability planning and visual design layer. Implementation can begin as component assembly rather than design rediscovery.

This keeps the UI aligned with actual backend capability, uses the current contract responsibly, and leaves ambitious visual extensions fenced until their backend contracts are real.
