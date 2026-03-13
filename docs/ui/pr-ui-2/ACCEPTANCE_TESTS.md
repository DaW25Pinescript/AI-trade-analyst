# ACCEPTANCE TESTS — PR-UI-2

## Functional acceptance
The PR must demonstrate all of the following:

### 1. Real backend rendering
- Triage Board renders real data from `GET /watchlist/triage`
- No mock-only dependency for the main board path

### 2. Trust visibility
- Board-level `data_state` is always visible
- `data_state` is read-only — no dropdown or toggle affordance
- Freshness / last-updated or equivalent trust signal is visible
- Feeder health chip renders from `GET /feeder/health`
- Trust strip groups data_state badge + feeder chip + timestamp together
- Per-row freshness is derived from `verdict_at` where available, not invented as synthetic `data_state`

### 3. Run Triage flow
- **Run Triage** button has clear idle / running / refreshed / failure behavior
- `POST /triage` triggers cache invalidation and refetch of the board
- User can see that refresh occurred
- No auto-retry on failure — explicit user rerun only
- Partial failure surfaced, not collapsed into generic error

### 4. State handling
UI must correctly distinguish:
- loading (skeleton or spinner during initial fetch)
- ready (items rendered normally)
- empty (valid response, no items — "No triage items", not error)
- stale (board renders with stale warning)
- unavailable ("Triage data unavailable" message)
- demo-fallback (demo badge visible if fallback data used)
- error (error message with context)

### 5. Navigation handoff
- Entire row is clickable with hover affordance
- Clicking a row navigates to `#/journey/{symbol}`
- No fake Journey implementation is added in this PR

### 6. Shared component discipline
- Shared primitives live in `ui/src/shared/components/` subdirectories, not inline page-local definitions
- At minimum: DataStateBadge, TrustStrip, EntityRowCard, PanelShell, EmptyState, UnavailableState, ErrorState, LoadingSkeleton, FeederHealthChip
- Components accept typed props

### 7. Hook discipline
- `useWatchlistTriage()` hook exists and drives the board data
- `useTriggerTriage()` hook exists and handles mutation + cache invalidation
- `useFeederHealth()` hook exists and drives the feeder chip

### 8. API client completeness
- Feeder health API client (`ui/src/shared/api/feeder.ts`) exists with typed `FeederHealth` type and `fetchFeederHealth()` function
- Triage API client from PR-UI-1 is reused, not rewritten

## Verification checklist
- [ ] `cd ui && npm run build` passes
- [ ] `cd ui && npm run typecheck` passes
- [ ] `cd ui && npm run test` passes
- [ ] Triage Board route renders real backend data
- [ ] Run Triage action works and refreshes the board
- [ ] Loading, empty, unavailable, stale, and error views are visibly distinct
- [ ] Board-level trust strip is present with data_state + feeder chip + timestamp
- [ ] Per-row staleness derived from verdict_at (not invented data_state)
- [ ] Row click navigates to `#/journey/{symbol}`
- [ ] Shared components in shared/ subdirectories, not page-local
- [ ] Named hooks exist for triage query, triage mutation, and feeder health
- [ ] Feeder health API client exists
- [ ] No backend files changed
- [ ] Legacy `app/` remains unaffected

## Explicit non-acceptance
The PR is **not** complete if:
- it renders hardcoded mock data as though it were real
- data_state is presented as a dropdown or toggle
- per-row staleness is invented from something other than verdict_at
- Run Triage auto-retries on failure
- shared components are inlined in the page component
- the board invents `partial` state for triage
- any backend files are modified
- other workspaces are implemented
- build or typecheck fails

## Documentation closure for this PR
At PR close, update:
- `docs/AI_TradeAnalyst_Progress.md` — mark Phase 2 complete, Phase 3 next
- `docs/specs/ui_reentry_phase_plan.md` — mark Phase 2 complete, note any bounded implementation clarifications
- any `ui/README.md` or frontend docs if route structure / commands changed

## Suggested PR title
`feat(ui): implement Triage Board MVP on real triage endpoints`

## Suggested commit message
`feat(ui): implement Triage Board MVP with real triage data, shared components, and trust strip`

## Expected PR summary format
1. Summary of what was built
2. Shared components created (with subdirectory structure)
3. Hooks created
4. Files added/changed
5. State handling verification (all 7 conditions)
6. Commands run and results
7. Any deviations from plan and why
8. Suggested PR description
