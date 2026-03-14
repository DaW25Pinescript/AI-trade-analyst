# ACCEPTANCE TESTS — PR-UI-4

## Merge criteria

PR-UI-4 is complete only if all of the following are true.

## 1. Scope correctness

- Journey Studio is implemented in the React UI.
- No backend files are changed.
- No new backend endpoints are introduced.
- No Agent Ops scope is added.
- No Analysis Run or Journal & Review surfaces are partially implemented under the Journey label.

## 2. Endpoint discipline

- The PR clearly identifies which existing backend endpoint(s) Journey Studio uses.
- All fetches are typed.
- No page component performs ad hoc untyped fetch logic.
- No undocumented endpoint assumptions are introduced.
- Journey write endpoints preserve the `{ success: false, error }` envelope.

## 3. Route behavior

- `/journey` renders a real workspace, not a placeholder.
- Entry into Journey from Triage is deterministic and testable.
- The page behaves safely when required route parameter is missing.

## 4. State handling

Journey Studio must visibly and correctly handle all relevant conditions supported by its chosen backend surface:

- loading
- ready
- empty
- unavailable
- error

If stale/degraded/demo-fallback semantics are present on the used endpoint(s), those must also be handled honestly. Demo-fallback must be explicitly flagged, not silently presented as live data.

## 5. Freeze behavior (if decision endpoint is used)

- Pre-freeze: form fields are interactive, Save Result is disabled.
- Freeze click calls the decision endpoint.
- Post-freeze: entire center column becomes read-only.
- Post-freeze: header shifts to frozen status, Save Draft disappears, Save Result enables.
- 409 on duplicate freeze surfaces as explicit conflict message, not generic error.
- Ambiguous freeze failure does not silently allow retry without reconciliation guidance.
- The visual shift is immediate and total — no uncertainty about whether a freeze occurred.

## 6. Save Result gating (if result endpoint is used)

- Save Result is disabled/unavailable until freeze has succeeded.
- Save Result only enables when a confirmed frozen snapshot exists.

## 7. Conditional right rail (if bootstrap has optional fields)

- Panels render only for present bootstrap fields.
- Missing or null fields produce no panel, not empty placeholders.
- When `data_state === "unavailable"`, a single fallback message replaces all panels.

## 8. Adapter discipline

- A Journey adapter exists.
- Backend payload mapping is isolated from rendering components.
- UI components receive normalized props / view models rather than raw backend payloads where practical.

## 9. Reuse discipline

- Existing shared components are reused where appropriate.
- New shared abstractions are introduced only when clearly justified.
- Domain-specific logic remains in the Journey workspace rather than leaking into shared without cause.

## 10. Testing

The following should pass:

- `npm run typecheck`
- `npm run build`
- `npm run test`

And tests should include:
- adapter behavior (field presence derivation, freeze state, gating logic)
- page/workspace state handling (loading, ready, unavailable, error)
- freeze lifecycle (pre-freeze → freeze → post-freeze read-only) if applicable
- 409 conflict handling if applicable
- Save Result gating (disabled → enabled) if applicable
- conditional right rail rendering if applicable
- navigation or continuity behavior
- at least one integration-style route test

Existing Triage Board and Agent Ops tests must not regress.

## 11. UX truthfulness

- The UI does not imply analysis execution if execution is not actually happening here.
- The UI does not imply missing backend capabilities.
- The "next step" toward Analysis Run is clear and honest.
- The freeze feels deliberate — like commitment, not like saving a form.

## 12. Documentation closure

The PR updates:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Those updates must accurately mark PR-UI-4 closure and identify the next phase without overstating later work.
