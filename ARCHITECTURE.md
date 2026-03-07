# ARCHITECTURE.md

# AI Trade Analyst – Trade Ideation Journey Architecture
Version: 1.0  
Status: Draft / Implementation-Ready

## 1. Architectural Intent

AI Trade Analyst is moving from a static, screenshot-first analysis form into a staged **Trade Ideation Journey**. The target product is a guided trading workspace that arrives pre-loaded with market, macro, and structure intelligence, triages assets by relevance, and walks the user through a disciplined, auditable trade-construction flow.

The architecture must preserve three separations:

1. **System context** — what the platform knows before the user acts
2. **System recommendation** — what the analyst/arbiter recommends
3. **User commitment** — what the human actually chooses to do

Those separations are necessary for later review, self-critique, override analysis, and policy refinement.

---

## 2. Product Surfaces

The Trade Ideation Journey is composed of four product surfaces:

### 2.1 Triage Surface
The user lands on an already-informed market view rather than a blank form.

Purpose:
- surface relevant assets first
- explain why each asset matters now
- route the user into a selected journey

### 2.2 Journey Surface
A staged workspace for trade construction.

Stages:
1. Market Overview / Asset Selection
2. Asset Context
3. Structure & Liquidity
4. Macro / News Alignment
5. Gate Checks
6. Verdict & Plan
7. Journal Capture / AAR Prep

### 2.3 Persistence Surface
The system freezes a decision record at save time.

Frozen artifacts:
- market/structure context
- macro context
- gate states
- system verdict
- user decision
- execution plan
- evidence references
- provenance metadata

### 2.4 Review Surface
A later rules-based review engine compares planned vs actual outcomes and produces transparent review signals.

---

## 3. Mandatory Pre-UI Stage: Interface Audit

Before serious UI implementation, the repo must complete a formal **Interface Audit**.

This is a hard prerequisite. The frontend must not infer or invent payload shapes from comments, assumptions, or aspirational schemas.

### 3.1 Why this stage exists
Without an interface audit, frontend work will:
- guess API shapes
- create placeholder objects that drift from backend reality
- force later churn across routes, stores, and components
- obscure which data is actually available vs merely desired

### 3.2 Audit scope
The audit must inspect all meaningful repo inputs/outputs that may power the journey UI, including:
- existing JSON schemas
- CLI outputs
- Python service layer DTOs
- FastAPI request/response models
- macro officer outputs
- market data officer outputs
- arbiter/multi-analyst outputs
- journal/ticket persistence shapes
- current frontend storage/export/import formats

### 3.3 Audit deliverables
The audit must produce an explicit artifact set:

1. **Input inventory**
   - every upstream input the UI may consume
2. **Output inventory**
   - every persisted or emitted object the UI may create or update
3. **Contract map**
   - source file → producer → consumer → schema/model → current status
4. **Availability matrix**
   - available now / derivable now / missing / needs adapter
5. **Field reliability notes**
   - stable / unstable / deprecated / ambiguous
6. **UI contract freeze proposal**
   - recommended shapes the frontend is allowed to depend on in v1

### 3.4 Exit criteria for the audit
The audit is complete only when:
- backend-owned shapes are named and located
- ambiguous fields are marked explicitly
- fake placeholder production payloads are removed from frontend planning
- every planned journey screen can trace its required inputs to a real or deliberately stubbed producer
- a v1 contract freeze is signed off before broad UI build proceeds

---

## 4. Architecture Principles

### 4.1 Pre-loaded intelligence
No blank-page UX. The app should open into an already-informed market view.

### 4.2 Triage before deep analysis
The user first sees what matters now and why.

### 4.3 Strong stage structure, flexible local interaction
The journey is opinionated across stages but permits AI prefill, user confirmation, user override, notes, and evidence within each stage.

### 4.4 Gates are a control boundary
Gate checks are not decorative. They are the formal discipline checkpoint of the journey.

### 4.5 Recommendation is not commitment
The system verdict and user decision must remain separate objects.

### 4.6 Freeze records, not just screens
At save time, the platform must persist a decision snapshot suitable for replay and review.

### 4.7 Transparent review framing
The feedback loop is framed as:
- Decision Review Engine
- Pattern Review
- Policy Refinement
- Self-Critique Loop

Not as an opaque “learning” black box.

---

## 5. Frontend Domain Model

The journey state should be treated as a domain object, not a loose bag of component state.

### 5.1 Core state concepts
- `currentStage`
- `journeyStatus`
- `selectedAsset`
- `triageStatus`
- `whyInterestingTags`
- `stageData`
- `gateStates`
- `systemVerdict`
- `userDecision`
- `executionPlan`
- `decisionSnapshot`
- `resultSnapshot`

### 5.2 Journey status
- `draft`
- `in_review`
- `blocked`
- `ready`
- `saved`
- `archived`

### 5.3 Provenance
Every user-visible field that may be AI-prefilled should track provenance:
- `ai_prefill`
- `user_confirm`
- `user_override`
- `user_manual`

This provenance is essential for later analytics and override review.

---

## 6. Route and Component Direction

### 6.1 Suggested route surfaces
- `/dashboard` → watchlist triage landing
- `/journey/:asset` → staged ideation flow
- `/journal` → saved ideas and results
- `/review` → review/pattern analysis

### 6.2 Foundational reusable components

The canonical component names are defined in `UI_STYLE_GUIDE.md` Section 16. Use these names consistently across all files and implementations:

- `AppShell` — top-level layout wrapper
- `PageHeader` — page-level title and context bar
- `SurfaceCard` — standard card for triage items, summaries, review metrics
- `SeverityCard` — elevated severe-treatment card for gate/compliance surfaces
- `StatusBadge` — semantic state badge (triage status, gate state, verdict)
- `ProvenanceBadge` — AI-prefill / user-confirm / user-override / manual marker
- `StageStepper` — journey progress navigation
- `EvidencePanel` — evidence/attachment container
- `SplitVerdictPanel` — three-panel layout for SystemVerdict / UserDecision / ExecutionPlan
- `AIPrefillCard` — system-generated context block with indigo provenance marker
- `GateChecklist` — gate rows with passed/conditional/blocked state and inline justification
- `ChartAnnotationLayer` — placeholder initially; real chart area with annotation support later
- `NotesTextarea` — user note input with provenance framing

### 6.3 Store and type placement
- `app/types/`
- `app/stores/`
- `app/lib/`

---

## 7. Backend Integration Direction

The frontend journey must only depend on explicit contracts. Suggested endpoint classes:
- `GET /watchlist/triage`
- `GET /journey/:asset/bootstrap`
- `POST /journey/update`
- `POST /tickets/create`
- `POST /journal/result`
- `GET /review/patterns`

These endpoints are architectural placeholders until the interface audit confirms exact ownership, field availability, and transport shape.

---

## 8. Staged Implementation Plan

### Phase 0 — Interface Audit and Contract Freeze
Goal:
- audit repo inputs/outputs
- identify what the UI can truly consume
- freeze the first contract layer

Outputs:
- interface audit report
- availability matrix
- v1 contract freeze
- list of adapters/stubs required

### Phase 1 — Journey Domain Model
Goal:
- define typed journey schemas
- define stage keys, provenance, snapshots, gate state model
- lock initial store API

Outputs:
- shared types
- journey store scaffold
- contract-aligned frontend models

### Phase 2 — Shell and Navigation Backbone
Goal:
- build route skeletons and stage shell
- add progress stepper and journey navigation

Outputs:
- route stubs
- shell layout
- stage navigation behavior

### Phase 3 — Triage Board
Goal:
- build the landing market overview that answers “why should I care right now?”

Outputs:
- triage card
- triage list/grid
- watchlist data adapter

### Phase 4 — Context, Structure, and Macro Stages
Goal:
- scaffold the journey middle stages with clear extension points

Outputs:
- asset context screen
- structure/liquidity screen
- macro alignment screen
- placeholder chart/evidence areas

### Phase 5 — Gate Checks
Goal:
- implement the risk-committee boundary

Outputs:
- gate checklist UI
- severity styling
- override justification rules
- next-step policy enforcement hooks

### Phase 6 — Verdict and Plan
Goal:
- formalize recommendation vs human choice vs execution commitment

Outputs:
- verdict split UI
- user decision capture
- execution plan model

### Phase 7 — Journal Capture and Snapshots
Goal:
- freeze auditable decision records

Outputs:
- evidence upload baseline
- decision snapshot preview
- persistence hooks for save flow

### Phase 8 — Review Engine Surface
Goal:
- create a transparent review view for comparison and refinement

Outputs:
- review page scaffold
- planned vs actual frame
- override/gate pattern placeholders

### Phase 9 — Hardening and Policy Refinement
Goal:
- stabilize contracts, test flows, remove placeholder drift, improve review fidelity

Outputs:
- contract conformance tests
- UX tightening
- adapter cleanup
- documentation refresh

---

## 9. Non-Goals for v1

Out of scope for the initial UI upgrade:
- full multi-persona analyst UI
- advanced chart drawing suite
- collaborative workflows
- excessive settings sprawl
- black-box learning claims
- mobile-first redesign as a primary objective

The first goal is a disciplined, auditable journey workspace.

---

## 10. Definition of Architectural Success

The architecture is successful when:
- the frontend is grounded in real audited contracts
- the journey stages form a coherent trade-construction workflow
- gate checks are enforced as a control boundary
- system verdict and user action are persistently separated
- the app can freeze a decision snapshot suitable for later review
- later review and self-critique can trace back to explicit provenance rather than reconstructed guesswork
