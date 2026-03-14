# IMPLEMENTATION PLAN — PR-UI-4

## Implementation strategy

Build Journey Studio as a **real, minimal, contract-safe workflow workspace** using existing endpoints and proven frontend patterns.

Do not overreach.
The goal is to make `/journey` meaningful and useful now, not to complete the entire trading workflow in one PR.

## Step 1 — Route and endpoint audit

Before coding, inspect:
- current repo backend routes
- `docs/ui/UI_CONTRACT.md` §10.3 (journey endpoint contracts), §9.6 (bootstrap model), §9.7 (decision snapshot), §11.2 (error envelope)
- `docs/ui/UI_WORKSPACES.md` §6 (Journey Studio workspace spec)
- `docs/ui/DESIGN_NOTES.md` §1.3 (freeze behavior), §1.4 (Save Result gating), §1.5 (handoff)
- `docs/ui/VISUAL_APPENDIX.md` (Journey Studio wireframe)
- existing `ui/` route structure
- current Triage navigation patterns (PR-UI-2 row click → `#/journey/{symbol}`)

Confirm the real existing backend endpoint(s) that support Journey Studio.
Record that basis in the PR summary.

## Step 2 — Define Journey MVP shape

From the real available endpoint data, define the minimum viable Journey Studio structure.

Possible shape:
- top summary / identity panel
- planning context panel (bootstrap data)
- staged ideation flow if bootstrap provides sufficient data
- conditional right rail driven by bootstrap field presence
- footer with save/freeze/result actions
- explicit next-step action area

Only include sections that can be backed by actual data.

## Step 3 — Add typed API + hooks

Implement:
- typed API client functions for the journey endpoints
- workspace-local hooks (`useJourneyBootstrap`, `useSaveDraft`, `useFreezeDecision`, `useSaveResult` or equivalent)
- explicit query keys
- deterministic loading/error behavior
- mutation hooks must preserve the `{ success: false, error }` envelope from §11.2
- freeze mutation must distinguish 409 (duplicate immutable decision) from other errors

Do not place domain-specific hooks in shared unless they are clearly cross-workspace.

## Step 4 — Add adapter layer

Create a workspace adapter in:

`ui/src/workspaces/journey/adapters/`

Responsibilities:
- map bootstrap payload → Journey view model
- normalize null/missing fields
- derive which right rail panels should render from field presence
- derive frozen/unfrozen state
- derive whether Save Result should be enabled
- preserve data-state honesty

## Step 5 — Implement Journey UI

Implement the real Journey Studio page.

Use the shared system where appropriate:
- `PanelShell`
- feedback components
- state pills / badges
- generic entity display patterns

Likely workspace-local components include:
- summary / identity header
- planning context panel(s)
- conditional right rail panels
- footer with save/freeze/result actions
- any staged flow components if the data supports it

Keep component naming precise and workspace-oriented.

### Freeze behavior (the critical interaction)

If implementing the freeze endpoint, this is the most important interaction:
- pre-freeze: form fields interactive, Save Draft available, Save Result disabled
- freeze click → `POST /journey/decision` → on success, entire center column locks to read-only
- post-freeze: header shifts to frozen status, Save Draft disappears, Save Result enables
- 409 → explicit conflict message, not generic error
- the visual shift must be immediate and total

### Conditional right rail

If bootstrap includes optional context fields:
- render panels only for present fields
- missing fields → no panel (not empty placeholder)
- `data_state === "unavailable"` → single fallback message, not stacked empties

### Save Result gating

- disabled/unavailable until freeze has succeeded
- only enables when a confirmed frozen `snapshot_id` exists

## Step 6 — Establish Triage → Journey continuity

Triage Board row click already navigates to `#/journey/{symbol}` (PR-UI-2). Verify this works end-to-end.

The receiving Journey page should behave safely when:
- the expected route parameter exists
- the route parameter is missing
- the bootstrap endpoint returns empty or unavailable data

"Return to Triage" navigation should exist in the Journey header or footer.

## Step 7 — Test

Add:
- adapter unit tests (field presence derivation, freeze state, Save Result gating)
- page/workspace state handling tests (loading, ready, stale, unavailable, error)
- freeze lifecycle test (pre-freeze interactive → freeze → post-freeze read-only)
- 409 conflict handling test
- Save Result gating test (disabled pre-freeze, enabled post-freeze)
- conditional right rail test (panels follow field presence)
- navigation / continuity tests
- at least one integration-style route test

Avoid snapshot tests.
Prefer explicit assertions.

## Step 8 — Docs closure

Update only the relevant docs:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Mark the phase accurately.
Do not overstate completion of later workflow phases.

## Design guidance

### The freeze is commitment, not save
Think of it like placing a trade: before freeze = pending order, after freeze = filled position. The shift must be unmistakable.

### Right rail follows the data
If a bootstrap field exists, its panel appears. If it doesn't, the panel doesn't. When the whole bootstrap is unavailable, one message replaces all panels.

### Don't overbuild the form
Journey Studio MVP needs working save/freeze/result mechanics, not a polished form builder. Textarea fields with clear labels are better than elaborate widgets that are hard to test.

### Only include what the data supports
If the bootstrap doesn't provide enough structure for a staged flow, a simpler layout is more honest than invented stages backed by empty data.
