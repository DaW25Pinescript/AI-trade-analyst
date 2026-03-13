# ACCEPTANCE TESTS — PR-UI-1

## Primary acceptance
PR-UI-1 is complete only if all of the following are true:

### Foundation
- [ ] A React + TypeScript + Tailwind app exists in the repo
- [ ] The app location and repo-shape are clearly documented
- [ ] The React app can run without breaking the current legacy `app/`

### Routing
- [ ] Hash-based routing exists
- [ ] Triage route (`#/triage`) is reachable and renders placeholder
- [ ] All other defined routes (`#/journey/:asset`, `#/analysis`, `#/journal`, `#/review`, `#/ops`) render placeholders (no blank pages)
- [ ] Default route (`/`) redirects to `#/triage`
- [ ] Unknown-route behavior is sane (404 or redirect)

### API layer
- [ ] A generic typed fetch wrapper (`apiFetch<T>`) exists with no `any` types
- [ ] Triage endpoint types (`TriageItem`, `WatchlistTriageResponse`, `TriggerTriageResponse`) match `UI_CONTRACT.md` §9.5
- [ ] Triage client functions (`fetchWatchlistTriage`, `triggerTriage`) exist and compile
- [ ] Error handling preserves mixed `detail` patterns (string, object, structured with `request_id`/`run_id`) — not normalised to a single string
- [ ] API base URL/environment handling is defined
- [ ] Vite proxy config exists for backend API calls during dev

### UI shell
- [ ] App shell/layout exists
- [ ] Triage route placeholder exists
- [ ] Placeholder clearly communicates "foundation only", not fake finished UI
- [ ] Tailwind utility classes render correctly

### Tooling
- [ ] Build passes (`npm run build` or equivalent)
- [ ] TypeScript typecheck passes (`tsc --noEmit` or equivalent)
- [ ] Dev run path is documented
- [ ] Any added test/smoke verification passes

### Docs
- [ ] Progress hub updated to reflect PR-UI-1 completion and PR-UI-2 next
- [ ] Phase plan updated if needed to reflect actual implementation details
- [ ] Run instructions for the new frontend are documented (install, dev, build, typecheck)
- [ ] README inside the new React app directory explains repo-shape, coexistence, and what remains for PR-UI-2

## Explicit non-acceptance
The PR is **not** complete if:
- [ ] it renders mock triage data as though Phase 2 already happened
- [ ] it adds unrelated design-system work
- [ ] it changes backend behavior or modifies Python files
- [ ] it introduces Agent Ops UI
- [ ] it breaks legacy `app/`
- [ ] it leaves repo-shape ambiguous
- [ ] it cannot be built or typechecked cleanly
- [ ] any route renders a blank page
- [ ] the API error wrapper normalises all errors to a single string

## Verification commands
Use repo-appropriate commands, but the final summary should report the exact commands run, such as:
- `cd ui && npm install`
- `npm run build`
- `npx tsc --noEmit`
- `npm run dev` (confirm routes load)
- `npm test` (if test harness added)

## Expected PR summary format
Ask the implementer to return:
1. Summary of what was built
2. Exact repo-shape chosen and rationale
3. Files added/changed
4. Commands run
5. Verification results (build, typecheck, route check)
6. Any deviations from plan and why
7. Suggested commit message
8. Suggested PR description
