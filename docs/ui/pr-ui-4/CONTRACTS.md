# CONTRACTS — PR-UI-4

## Contract basis

PR-UI-4 must follow the existing repo UI contract and active phase plan.
It must remain within existing backend capability and existing frontend governance.

This PR is not allowed to invent backend surfaces.

## Workspace contract position

Journey Studio is the first core workflow workspace after Triage and before Analysis Run.

Conceptually:

`Triage Board → Journey Studio → Analysis Run → Journal & Review`

Journey Studio should therefore consume existing state and present a structured planning surface that can later hand off into Analysis Run.

## Backend surface usage

The journey endpoints are documented in `UI_CONTRACT.md` §10.3. The expected surfaces are:

- `GET /journey/{asset}/bootstrap` — preloaded evidence/decision context
- `POST /journey/draft` — mutable draft save
- `POST /journey/decision` — immutable decision freeze
- `POST /journey/result` — post-decision outcome save

The implementer must:
1. inspect `UI_CONTRACT.md` §10.3, §9.6, §9.7, §11.2 to confirm these endpoints and their exact response shapes
2. use only those endpoints
3. document the chosen endpoint basis in the PR summary

## Required typed-client rule

Any backend endpoint used by Journey Studio must have:
- a typed API function in `ui/src/shared/api/` or a justified workspace-local API module
- explicit frontend types matching the current backend contract
- no `any`
- no untyped ad hoc fetch logic inside the page component

## View-model adapter rule

Journey Studio should have a workspace-local adapter layer in a path like:

`ui/src/workspaces/journey/adapters/`

The adapter should:
- normalize backend payloads into UI-ready structures
- isolate contract-to-UI mapping
- keep rendering components presentation-oriented
- avoid leaking backend payload complexity into JSX

## Navigation contract

PR-UI-4 should support a clean navigation story from Triage into Journey Studio.

The existing Triage Board row click navigates to `#/journey/{symbol}` (built in PR-UI-2). Journey Studio reads the asset from the route parameter and bootstraps from it.

The navigation method must:
- be explicit
- be testable
- not depend on hidden global mutable state

"Return to Triage" navigation should exist. An "Escalate to Analysis" link to `#/analysis` is acceptable as an affordance but Analysis Run itself is not built in this PR.

## Freeze behavior contract

If the implementation uses `POST /journey/decision`, the freeze is the most important interaction in Journey Studio. Read `DESIGN_NOTES.md` §1.3 for full context.

**Pre-freeze state:**
- center column has interactive form fields
- header shows draft status
- Save Draft available, Freeze Decision available, Save Result disabled

**On freeze:**
- calls `POST /journey/decision`
- on success: entire center column locks to read-only
- on 409 conflict: surface as meaningful "decision already exists" message — not generic error
- on ambiguous failure: do not silently allow retry — suggest reconciliation through readback

**Post-freeze state:**
- form fields become non-editable text
- header shifts to frozen status with snapshot identifier
- Save Draft disappears
- Freeze shows as confirmed
- Save Result becomes enabled

The visual shift must be immediate and total. A user must never be uncertain about whether a freeze has occurred.

## Save Result gating contract

If the implementation uses `POST /journey/result`, read `DESIGN_NOTES.md` §1.4.

- Save Result is disabled until a frozen `snapshot_id` exists
- This enforces the contract sequence: draft → freeze → result
- Save Result without a prior freeze is architecturally invalid

## Conditional right rail contract

If the bootstrap response includes optional context fields (e.g. `arbiter_decision`, `explanation`, `reasoning_summary`, `no_trade_conditions`), the right rail should render panels conditionally based on field presence:

- field exists and is non-null → panel renders
- field missing or null → panel does not render
- when `data_state === "unavailable"` → collapse to a single fallback message, not stacked empty panels

See `UI_WORKSPACES.md` §6.4 for full context.

## Error envelope contract

Journey write endpoints use an explicit success envelope (`UI_CONTRACT.md` §11.2):
- success: `{ success: true, ... }`
- failure: `{ success: false, error: ... }`

The API client and hooks must preserve this shape. The UI must surface the `error` content, not collapse failures into generic messages.

409 on the decision endpoint is a **meaningful conflict** (duplicate immutable decision), not a generic error. Handle it distinctly.

## MVP responsibilities

Journey Studio MVP should include only what is supported today.

Expected kinds of content:
- selected instrument / candidate identity
- why-interesting or triage-origin context
- current known planning metadata
- staged planning context if bootstrap provides sufficient data
- explicit next-action toward analysis run

The exact section set must be grounded in real existing backend data, not speculative mock content.

## Out-of-scope future surfaces

The following belong to later phases, not this PR:
- full Analysis Run experience
- persona outputs and arbiter synthesis rendering
- Journal & Review
- Agent Ops trace/detail
- reflective / review intelligence surfaces
