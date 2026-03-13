# CONTRACTS — PR-UI-3

## 1. Frontend ownership contract
The frontend now has three meaningful layers inside `ui/src/`:

- `app/` — shell, routing, providers, app-level concerns
- `shared/` — reusable primitives, API wrappers, hooks, styles, generic feedback/layout/state surfaces
- `workspaces/` — route-owned UI, adapters, page composition, workspace-specific behavior

PR-UI-3 should make these boundaries sharper.

## 2. Shared component contract
A component belongs in `shared/components/` if all of the following are true:
- it does not encode triage-specific domain assumptions in its visual contract
- its props can be described in general UI terms
- reusing it in another workspace would not feel misleading or forced
- its tests can be written without triage-only backend fixtures

Examples that are already plausibly shared:
- `DataStateBadge`
- `StatusPill`
- `TrustStrip`
- `FeederHealthChip` (if framed as feed freshness/health, not triage-only)
- `PanelShell`
- `LoadingSkeleton`
- `EmptyState`
- `UnavailableState`
- `ErrorState`

`EntityRowCard` should be reviewed carefully. If it is actually triage-specific, it should move under the triage workspace or split into:
- a smaller shared presentational primitive
- a triage-owned wrapper

## 3. Hook contract
Hooks belong in `shared/hooks/` if they are endpoint-stable and not workspace-owned orchestration.

Likely shared:
- feeder health query
- generic query helpers if truly justified

Potentially still workspace-owned:
- triage trigger orchestration
- triage-specific query composition

PR-UI-3 should decide this cleanly and document it in code structure.

## 4. Adapter contract
Adapters should remain close to the workspace unless there is a genuinely reusable transformation pattern.

For PR-UI-3:
- keep `triageViewModel` in the triage workspace unless extraction improves clarity without losing ownership
- it is acceptable to extract small formatting helpers into shared utilities if they are pure and non-domain-specific

## 5. Export contract
Shared surfaces should have stable barrel exports where useful, but avoid giant wildcard re-export files that obscure ownership.

A good outcome is:
- discoverable imports
- minimal path churn
- easier future reuse

## 6. Test contract
Shared surfaces should have tests proportionate to their importance.

Minimum expectation:
- components with meaningful state branching are covered
- helpers/adapters with transformation logic are covered
- Triage Board integration behavior still has end-to-end-ish route/component tests

## 7. Documentation contract
This PR should update the progress hub and the UI re-entry phase plan to mark PR-UI-3 complete only if the extraction/hardening work is actually finished.

If structure changes materially, `ui/README.md` should also be updated.
