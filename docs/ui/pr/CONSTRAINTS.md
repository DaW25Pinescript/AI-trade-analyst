# CONSTRAINTS — PR-UI-1

## Hard scope boundaries
This PR must stay narrow.

### In scope
- Create the React + TypeScript + Tailwind app shell
- Choose and implement build tooling (Vite preferred unless repo reality dictates otherwise)
- Lock the frontend repo-shape
- Add workspace routing
- Add typed API fetch scaffolding
- Add minimal state/query scaffolding
- Add placeholder Triage route
- Add minimal layout shell
- Add scripts and docs needed to run and verify the new frontend lane

### Out of scope
- No real Triage Board data rendering
- No `Run Triage` action UI
- No shared component extraction pass
- No design-polish sprint
- No Agent Ops work
- No backend endpoint additions or changes
- No contract changes to existing backend routes
- No SSE, WebSocket, or live trace work
- No big-bang replacement of `app/`

## Contract discipline
- Do not infer contracts from ad hoc backend code.
- Stay faithful to existing documented contract surfaces.
- UI must not depend on undocumented payload quirks.
- If an existing endpoint is called, the typed client should model it conservatively and tolerate incomplete/null fields where the contract allows.

## Migration discipline
- React must coexist with the current `app/`.
- Do not break the legacy surface.
- Do not move unrelated files just to “clean things up”.
- Do not create a repo layout that assumes the migration is complete.

## UI discipline
- Build a shell, not a fake finished product.
- The placeholder Triage route should make the direction obvious, but it should not masquerade as Phase 2.
- No hardcoded Agent Ops framing in this PR. Agent Ops belongs later.

## Testing discipline
- Frontend-only verification for this PR:
  - build passes
  - TypeScript typecheck passes
  - route-level smoke test or equivalent proves the shell loads
  - API layer compiles and is callable
- Do not introduce flaky test harnesses just to satisfy the PR.

## Documentation closure
At PR close, update:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`
- `docs/specs/README.md` if needed
Any docs updates should reflect actual implementation, not aspirational future work.
