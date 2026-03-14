# CONSTRAINTS — PR-UI-4

## Scope boundaries

This PR is **frontend only**.

It may:
- add Journey Studio UI files in `ui/src/workspaces/journey/`
- add supporting shared UI code only where clearly justified
- add typed API functions for already-existing endpoints
- add view-model adapters, workspace-local hooks, and tests
- update docs/progress files for phase closure

It may **not**:
- add or modify backend endpoints
- add new FastAPI routes
- change backend response shapes
- add Agent Ops functionality
- add run-trace or entity-detail features
- introduce SSE, WebSockets, or polling beyond what existing endpoints already support
- redesign unrelated workspaces

## Existing-endpoints rule

PR-UI-4 must use **existing backend contract surfaces only**.

Do not invent missing endpoints.
Do not rely on undocumented payload quirks.
Do not create mock-only UI that implies backend support that does not exist.

## Product-lane rule

Journey Studio belongs to the **primary user workflow lane**, not the operator lane.

It should feel like:
- a structured planning workspace
- a staging surface for analysis
- a disciplined continuation from Triage

It should **not** feel like:
- Agent Ops
- a debugging console
- a review journal
- a prompt editor
- a generic blank form

## Reuse-before-invent rule

Prefer reuse of:
- `PanelShell`
- `StatusPill`
- `DataStateBadge`
- `TrustStrip` where appropriate
- feedback shells
- generic entity card patterns
- existing hook / API organization patterns

Create new shared components only when:
- they are genuinely reusable beyond Journey Studio, and
- keeping them workspace-local would create obvious duplication.

## State-handling rule

Journey Studio must explicitly handle:
- loading
- ready
- empty
- unavailable
- error

If existing endpoint semantics support stale/degraded/demo-fallback distinctions, handle them honestly.
Do not fabricate state classes that do not exist in the contract.

## Freeze discipline

If Journey Studio implements a freeze/decision endpoint:
- the freeze must feel deliberate, not accidental — like placing a trade, not saving a form
- post-freeze visual shift must be immediate and total
- 409 conflict on duplicate freeze must be surfaced as a meaningful conflict, not collapsed into a generic error
- do not auto-retry an ambiguous freeze failure — the write may have succeeded

## Save Result gating discipline

If the contract supports a result-save that depends on a prior freeze:
- the result action must be disabled/unavailable until the freeze has succeeded
- do not allow result submission without a confirmed frozen snapshot

## No hidden execution rule

This PR must not silently become Analysis Run.

Allowed:
- prepare for analysis handoff
- show staged information
- provide clear next action

Not allowed:
- full analysis execution workflow
- persona trace rendering
- arbiter verdict experience
- run forensic surfaces

## No broad architecture rewrite

Do not use PR-UI-4 to refactor the entire frontend.
Only make structural changes that are directly needed for Journey Studio and are obviously consistent with the current frontend architecture.
