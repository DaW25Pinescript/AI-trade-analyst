# IMPLEMENTATION PLAN — PR-UI-6

## Implementation strategy

Build Journal & Review as a **real, contract-safe, read-only readback workspace** using existing endpoints and proven frontend patterns.

Journal & Review is the reflective mirror to Journey Studio. Think of it like a trading journal: Journey Studio is where you write the entry ("I'm taking this trade because..."), and Journal & Review is where you look back at the ledger ("What decisions did I make? Which have outcomes?").

This is the simplest of the three Phase 6 workspaces — two read-only list views against two JSON GET endpoints, served as two internal views within a single route. No forms, no mutations, no long-running calls, no state machines. The design challenge is making the empty state feel welcoming (every new user sees it first) and keeping the review view honest about result coverage without inventing detail screens or outcome fields that don't exist.

Do not overreach.
The backend exposes list-level data only. No deep detail drill-down exists. No result submission belongs in this PR. Do not build any of these.

## Step 1 — Route and endpoint audit

Before coding, inspect:
- current backend routes for `/journal/decisions` and `/review/records`
- the actual response shapes returned by each endpoint
- `docs/ui/UI_CONTRACT.md` §9.7 (DecisionSnapshot), §9.8 (ReviewRecord extends DecisionSnapshot), §10.3 (endpoint contracts), §11.4 (graceful empty/unavailable)
- `docs/ui/UI_WORKSPACES.md` §8 (Journal & Review workspace spec)
- `docs/ui/DESIGN_NOTES.md` §1.9 (no fake detail screens)
- existing `ui/` route structure
- `ui/src/shared/api/` — check if stubs exist
- `ui/src/shared/` — available shared components from Phase 3

Confirm response shapes match the contract. Record the fields in the PR summary.

## Step 2 — Define Journal & Review MVP shape

**One route (`#/journal`), two internal views**, toggled by a view switch:

**Journal view:**
- frozen decisions list from `GET /journal/decisions`
- header summary: total count ("12 frozen decisions")
- each row: instrument, verdict summary, saved_at, journey_status
- lateral link to Journey context (`#/journey/{instrument}`) — required
- empty state: "No decisions recorded yet"

**Review view:**
- decisions with result linkage from `GET /review/records`
- header summary: outcome coverage ("7 of 12 decisions have results")
- each row: same as journal + `has_result` indicator
- visual distinction: "has result" vs "needs follow-up"
- empty state: same welcoming treatment

No detail drill-down. Row interaction → lateral jump to Journey, not a detail screen.
No mutations. No result submission. No outcome logging.

## Step 3 — Build API layer

Create at `ui/src/workspaces/journal/api/journalApi.ts`.

Functions:
- `fetchDecisions()` — `GET /journal/decisions`
- `fetchReviewRecords()` — `GET /review/records`

Both are simple JSON GETs, safe to refresh/retry. Empty `records` array is valid success. Normalize any backend failure into a single UI-safe error shape.

## Step 4 — Build workspace adapter

Create at `ui/src/workspaces/journal/adapters/journalAdapter.ts`.

Key rule: `ReviewRecord` extends `DecisionSnapshot`. One shared base type with `has_result` added for review. Not two separate models.

Responsibilities:
- normalize response shapes to view models
- derive empty vs populated state
- derive per-record result indicators (review view)
- derive header summaries:
  - Journal: total decision count
  - Review: outcome coverage ("X of Y have results")

## Step 5 — Implement Journal & Review UI

Build in `ui/src/workspaces/journal/`. One route, two views.

### View toggle
Journal | Review tabs or toggle. Each view fetches from its own endpoint. The toggle is the primary interaction — everything else is a list display.

### Header summaries
Both views display a concise adapter-derived summary:
- Journal: "12 frozen decisions"
- Review: "7 of 12 decisions have results"

### Decision rows
Shared `DecisionRow` component that renders for both views. In Review view, it additionally shows the `ReviewIndicator` (has result / needs follow-up).

### Row interaction
Required: lateral jump to `#/journey/{instrument}`. This is the primary row interaction.
Optional: secondary link to `#/triage` if genuinely useful. Do not clutter.

### Empty state
Welcoming, not broken. "No decisions recorded yet. Freeze a decision in Journey Studio to see it here." This is the first state a new user sees.

### No detail screen
No `/journal/:id` detail route. No fake drill-down. The lateral jump to Journey is the honest way to provide more context.

### No mutations
This PR is read-only. No result submission, no outcome logging, no AAR flows. `POST /journey/result` is Journey Studio's responsibility (PR-UI-4).

### Structural separability
Journal view and Review view must not be tightly coupled. Separate hooks, separate API calls, shared type with extension. If the review contract deepens later, the views can become separate workspaces without a rewrite.

## Step 6 — Test

Add tests covering: adapter normalization, `ReviewRecord extends DecisionSnapshot`, empty records handling, header summaries, outcome coverage, view toggle, decision row rendering, review indicator presence/absence, lateral navigation links, loading/error states with normalized error shapes, and at least one integration test per view.

No snapshots. Explicit assertions.

## Step 7 — Docs closure

Update:
- `docs/AI_TradeAnalyst_Progress.md` — mark Phase 6 complete
- `docs/specs/ui_reentry_phase_plan.md` — update phase status

Phase 6 is complete with this PR. All three Phase 6 workspaces shipped: Journey Studio, Analysis Run, Journal & Review. Next on the roadmap: Phase 7 (Agent Ops Trace + Detail).

## Design guidance

### Empty is normal, not broken
Every new user's first visit to Journal will show an empty list. This must feel like a clean slate — "nothing here yet, go make some decisions" — not like a missing feature.

### The ledger, not the laboratory
Journal & Review is where you look back, not where you work forward. Keep it scannable, tabular, information-dense. No elaborate cards or deep interaction — this is a reference surface.

### Headers tell the story at a glance
"12 frozen decisions" and "7 of 12 have results" — the user should know the state of their decision history without scrolling.

### Result coverage is the key signal
In Review view, the split between "has result" and "needs follow-up" is the most important visual signal. It should be immediately obvious how many decisions are still open.

### Don't build what doesn't exist
The backend gives you list data. Respect that boundary. A fake detail screen backed by aspirational fields is worse than no detail screen. The lateral jump to Journey is the honest way to provide more context.

### Read-only means read-only
No mutations. No result logging. No outcome tracking fields. If it's not in the GET response, it doesn't belong in this workspace.

### Separable by design
Journal and Review live together now. Code them so they can move apart later. Shared type with extension, not intertwined state. Two hooks, not one mega-hook.
