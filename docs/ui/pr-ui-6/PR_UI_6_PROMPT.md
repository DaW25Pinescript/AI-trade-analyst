# PR-UI-6 — Journal & Review Workspace MVP

Implement **PR-UI-6** for the AI Trade Analyst repo.

This is the final Phase 6 PR, completing the core product lane. It follows PR-UI-4 (Journey Studio), PR-UI-4a (canFreeze hardening), and PR-UI-5 (Analysis Run).

## Mission

Build a real `/journal` workspace — the **readback lane** that closes the decision loop.

Journal & Review is where the user looks back at frozen decisions and their outcomes. It completes the core product workflow:

**Triage Board → Journey Studio → Analysis Run → Journal & Review**

This workspace answers three questions:
1. What decisions have been recorded?
2. Which ones have outcomes?
3. What should be revisited?

This PR is **frontend only**, **read-only**, and must use **existing backend endpoints only**.

## Governance

Frontend behavior must conform to the UI contract. The contract hierarchy is:

```
Backend code
    ↓
UI_CONTRACT.md
    ↓
Frontend implementation
```

The frontend must not derive contracts from OpenAPI or ad-hoc backend observation.

---

## Hard scope boundaries

Do:
- implement Journal & Review in `ui/src/workspaces/journal/`
- inspect the repo and confirm the response shapes of `GET /journal/decisions` and `GET /review/records`
- add typed API client(s) for both endpoints
- add workspace-local hook(s) and adapter(s)
- implement two views within one workspace route (Journal view + Review view)
- implement `ReviewRecord` as an extension of `DecisionSnapshot` (UI_CONTRACT §9.8) — shared adapter, not duplicate model
- implement lateral navigation to Journey Studio where entity linkage exists
- reuse proven shared components where appropriate
- add tests
- update progress docs — mark Phase 6 complete

Do not:
- add backend routes
- modify backend response shapes
- introduce result-writing, outcome logging, or AAR mutation flows — **this PR is read-only**
- use `POST /journey/result` (that is Journey Studio's responsibility, already shipped in PR-UI-4)
- create a deep detail screen for individual decisions (no backed contract exists — DESIGN_NOTES §1.9)
- create a `/journal/:id` or `/review/:id` detail route
- add outcome tracking fields (P&L, win/loss, notes) that do not exist in the current backend response
- add lifecycle or state-machine complexity — this is a read-only list workspace, not an execution surface
- hardcode Journal and Review as inseparable (must be structurally separable per §8.6)
- modify Triage, Journey, or Analysis workspaces

---

## Workspace structure rule

PR-UI-6 implements a **single `/journal` workspace route** with an internal **Journal | Review** toggle — not two top-level workspaces and not two separate routes.

---

## Allowed endpoints

| Endpoint | Purpose | Contract ref | Transport |
|----------|---------|-------------|-----------|
| `GET /journal/decisions` | List frozen decision summaries | §10.3 | JSON |
| `GET /review/records` | List decisions with result linkage | §10.3 | JSON |

Both are simple JSON GETs. Safe to refresh/retry (UI_CONTRACT §12.2). No new endpoints may be introduced.

---

## Contract-aligned domain model

### DecisionSnapshot (UI_CONTRACT §9.7)

Represents an immutable stored decision record.

```
DecisionSnapshot {
  snapshot_id: string
  instrument: string
  saved_at: string
  journey_status: string
  verdict: object
  user_decision: string
}
```

### ReviewRecord (UI_CONTRACT §9.8)

Represents a decision record with result linkage. **Extends DecisionSnapshot** — the frontend adapter must extend the decision shape, not duplicate a separate incompatible model.

```
ReviewRecord extends DecisionSnapshot {
  has_result: boolean
}
```

### Response shapes

```
GET /journal/decisions → { records: DecisionSnapshot[] }
GET /review/records    → { records: ReviewRecord[] }
```

Both endpoints support graceful empty lists as valid success. Empty `records` is a normal state, not an error.

---

## Required implementation process

### 1. Audit first

Before implementing, inspect:
- current backend routes for `/journal/decisions` and `/review/records`
- the actual response shapes returned (confirm they match the contract)
- `docs/ui/UI_CONTRACT.md` §9.7 (DecisionSnapshot), §9.8 (ReviewRecord), §10.3 (endpoint contracts), §11.4 (graceful empty/unavailable)
- `docs/ui/UI_WORKSPACES.md` §8 (Journal & Review workspace spec)
- `docs/ui/DESIGN_NOTES.md` §1.9 (no fake detail screens)
- existing `ui/` route structure
- `ui/src/shared/api/` — check if journal/review stubs exist
- `ui/src/shared/` — check what shared components are available

Confirm the real response shapes. In your final summary, **explicitly state which fields you found in each endpoint response.**

### 2. Architecture

```
API Layer (ui/src/workspaces/journal/api/)
    ↓
Workspace Adapter (ui/src/workspaces/journal/adapters/)
    ↓
Workspace UI (ui/src/workspaces/journal/)
```

- **API layer** — typed fetch for both endpoints, normalize error shapes, handle empty responses gracefully
- **Adapter** — normalize backend responses to view models, enforce `ReviewRecord extends DecisionSnapshot`, derive result coverage indicators and header summaries
- **UI** — render based on adapter output, never derive state from ad-hoc response inspection

### 3. API Layer

Create journal API functions.

Location: `ui/src/workspaces/journal/api/journalApi.ts`

Functions:
- `fetchDecisions()` — `GET /journal/decisions`
- `fetchReviewRecords()` — `GET /review/records`

Error handling: these endpoints use the graceful empty/unavailable pattern (UI_CONTRACT §11.4). Empty `records` array is valid success, not error. Normalize any backend failure into a single UI-safe error shape — do not leak raw payload assumptions into components.

### 4. Workspace Adapter

Create adapter at `ui/src/workspaces/journal/adapters/journalAdapter.ts`.

Responsibilities:
- `normalizeDecisions()` — map `{ records: DecisionSnapshot[] }` → Journal view model
- `normalizeReviewRecords()` — map `{ records: ReviewRecord[] }` → Review view model
- **`ReviewRecord` must extend `DecisionSnapshot`** — shared type with `has_result` added, not a separate incompatible model
- derive empty vs populated state
- derive per-record result indicator for review records (`has_result` → "has result" vs "needs follow-up")
- derive **header summaries**:
  - Journal: total decision count (e.g. "12 frozen decisions")
  - Review: outcome coverage (e.g. "7 of 12 decisions have results")

### 5. Implement Journal & Review UI

Build as **two views within one workspace route** (UI_WORKSPACES §8.6). The implementation must be structurally separable — if the review contract deepens later, these views can become distinct workspaces without a rewrite.

Use the shared system where appropriate:
- `PanelShell`
- feedback components (`LoadingSkeleton`, `ErrorState`, `EmptyState`)
- `EntityRowCard` or equivalent for decision list items
- state pills / badges

Workspace-local components:

- **`JournalReviewPage`** — main orchestrator with view toggle (Journal | Review)
- **`JournalHeader`** — workspace title, view toggle, header summary (decision count for Journal, outcome coverage for Review)
- **`DecisionList`** — renders decision records for both views (shared component, receives either DecisionSnapshot[] or ReviewRecord[])
- **`DecisionRow`** — single decision record row with instrument, verdict summary, saved_at, journey_status, lateral navigation link to Journey
- **`ReviewIndicator`** — visual distinction for result linkage status (has result vs needs follow-up) — only rendered in Review view
- **`OutcomeCoverageSummary`** — compact header element: "X of Y decisions have results" — Review view only

### View toggle (Journal | Review)

Two views, one route. The toggle switches between:

**Journal view:**
- fetches from `GET /journal/decisions`
- shows frozen decisions list with metadata
- header summary: total count ("12 frozen decisions")
- each row links laterally to Journey context (`#/journey/{instrument}`)
- no result linkage column

**Review view:**
- fetches from `GET /review/records`
- shows decisions plus result linkage (`has_result`)
- header summary: outcome coverage ("7 of 12 decisions have results")
- each row visually distinguishes "decision exists, has result" from "decision exists, no result yet" (UI_WORKSPACES §8.5)
- "needs follow-up" indicators for records without results

### Empty state (critical — this is normal, not error)

Both views must handle empty `records` gracefully (UI_WORKSPACES §8.5, UI_CONTRACT §11.4):
- empty list → `EmptyState` component with guidance ("No decisions recorded yet. Freeze a decision in Journey Studio to see it here.")
- not an error state, not a loading state, not "something went wrong"
- the workspace must feel welcoming even when empty — this is the first state a new user will see

### No fake detail screen (DESIGN_NOTES §1.9)

Do not create a deep detail screen for individual decisions. The current backend exposes **list-level data only**. Building a richer detail view against aspirational fields violates the contract-first rule.

Row interaction:
- **Required:** lateral jump to `#/journey/{instrument}` where instrument linkage exists — this is the primary row interaction
- **Optional:** secondary link to `#/triage` to check if the symbol is still active — only if genuinely useful and does not clutter the workspace
- Do not create a dedicated `/journal/:id` or `/review/:id` detail route

### Lateral navigation

Journey lateral jump is the **required** primary behavior. Triage lateral jump is **optional** and secondary.

- Decision row → `#/journey/{instrument}` to revisit decision context (required)
- Decision row → `#/triage` to check if symbol is still active (optional, only if useful)
- These are driven by shared entity references (instrument), not hardcoded routes

### Header summaries

Both views must display a concise header summary for scanability:

- **Journal header:** total decision count — e.g. "12 frozen decisions"
- **Review header:** outcome coverage — e.g. "7 of 12 decisions have results"

These are derived from the adapter, not computed in the component.

### 6. Test properly

Add:
- **Adapter unit tests** — decision normalization, review record normalization, `ReviewRecord extends DecisionSnapshot` type safety, empty records handling, outcome coverage derivation, result indicator derivation, header summary derivation, error normalization
- **DecisionList/DecisionRow tests** — renders decision metadata, Journey lateral navigation link present, review indicator presence in Review view / absence in Journal view
- **View toggle tests** — Journal view fetches decisions, Review view fetches review records, toggle switches between views correctly
- **Empty state tests** — both views handle empty records gracefully (not error, welcoming message)
- **Loading/error tests** — loading skeleton renders, endpoint error with retry, error shape normalized
- **Header summary tests** — Journal shows count, Review shows coverage fraction
- **Outcome coverage tests** — coverage summary reflects correct has_result / no-result counts
- **Navigation/route tests** — route render, lateral links to Journey
- At least one **integration test per view** (fetch → render → verify content)

No snapshots. Explicit assertions.

### 7. Docs closure

Update only the relevant docs:
- `docs/AI_TradeAnalyst_Progress.md` — mark Phase 6 complete (all three Phase 6 workspaces shipped: Journey Studio, Analysis Run, Journal & Review)
- `docs/specs/ui_reentry_phase_plan.md` — update phase status

Phase 6 is now complete. Phase 7 (Agent Ops Trace + Detail) is next on the roadmap.

---

## Acceptance bar

The PR is successful only if:
- `/journal` is no longer a placeholder
- it uses real existing backend endpoints (`/journal/decisions` and `/review/records`)
- **the workspace is read-only — no mutations, no result submission, no outcome logging**
- it is a single `/journal` route with an internal Journal | Review toggle
- both views handle empty records as normal state, not error
- Review view visually distinguishes "has result" from "no result yet"
- `ReviewRecord` extends `DecisionSnapshot` in the adapter (shared type, not duplicate)
- header summaries display: decision count (Journal), outcome coverage (Review)
- no fake detail screen exists (DESIGN_NOTES §1.9)
- row interaction navigates laterally to `#/journey/{instrument}` (required)
- Journal and Review are structurally separable (not hardcoded as inseparable)
- shared components reused from Phase 3 extraction
- error shapes normalized into a single UI-safe model
- no backend files changed
- tests pass
- docs updated accurately — Phase 6 marked complete

---

## Final output format

When complete, return:

1. **Summary** — what Journal & Review now does
2. **Endpoint basis** — the exact existing backend endpoint(s) used, response fields discovered
3. **Files added / changed** — grouped by area (API, adapter, components, route, tests, docs)
4. **Architecture** — how API → Adapter → UI layering is implemented
5. **View toggle** — how Journal and Review views coexist and switch
6. **Empty state** — how each view handles empty records
7. **Header summaries** — what each view header displays
8. **Result linkage** — how Review distinguishes has-result from no-result
9. **Detail screen** — confirmation that no fake detail screen exists, and what happens on row interaction
10. **Lateral navigation** — how cross-workspace links work (Journey = required, Triage = optional)
11. **Structural separability** — how the implementation supports future workspace separation per §8.6
12. **Tests** — count and coverage
13. **Verification** — typecheck, build, test results
14. **Deviations** — anything changed from the plan
15. **Suggested commit message**
16. **Suggested PR description**

---

## Quality bar

Journal & Review should feel like a decision ledger — organized, scannable, and honest. It is the reflective counterpart to Journey Studio's forward-looking ideation. Empty state should feel like a clean slate, not a broken page. The review view should make it immediately obvious which decisions have outcomes and which are still open. The workspace should close the loop: "I made a decision in Journey, I can find it here."
