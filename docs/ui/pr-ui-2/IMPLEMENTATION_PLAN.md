# IMPLEMENTATION PLAN — PR-UI-2

## Recommended build order

### 1. Audit the current `ui/` shell and typed triage client
Confirm what PR-UI-1 already added:
- route location for Triage Board page
- typed API functions for triage endpoints (`fetchWatchlistTriage`, `triggerTriage`)
- query provider and fetch wrapper
- shared component layout conventions in `ui/src/shared/`
- Vite proxy config for backend API calls

Note: PR-UI-1 created the triage API client but NOT the feeder health client. That is new work for this PR.

### 2. Add feeder health API client
Create `ui/src/shared/api/feeder.ts` with:
- `FeederHealth` type matching `UI_CONTRACT.md` §9.9
- `fetchFeederHealth()` function using the existing `apiFetch<T>` wrapper

### 3. Build the Triage page view-model
Create a thin mapping layer between raw API response and view rendering.
Goal: keep page rendering components simple and avoid leaking backend response quirks into JSX.

Suggested shape:
- board summary / trust header model
- triage row model (with staleness derived from `verdict_at`)
- button state model (`idle | running | refreshed | error`)

### 4. Create TanStack Query hooks
Create hooks in `ui/src/shared/hooks/`:
- `useWatchlistTriage()` — query hook for `GET /watchlist/triage`, supports manual refetch
- `useTriggerTriage()` — mutation hook for `POST /triage`, invalidates triage query cache on success
- `useFeederHealth()` — query hook for `GET /feeder/health`, lightweight with short stale time

### 5. Add the first shared primitives
Add only the components Triage needs now.

Suggested placement:
- `ui/src/shared/components/state/DataStateBadge.tsx`
- `ui/src/shared/components/state/StatusPill.tsx`
- `ui/src/shared/components/trust/TrustStrip.tsx`
- `ui/src/shared/components/trust/FeederHealthChip.tsx`
- `ui/src/shared/components/layout/PanelShell.tsx`
- `ui/src/shared/components/feedback/{EmptyState,UnavailableState,ErrorState,LoadingSkeleton}.tsx`
- `ui/src/shared/components/entity/EntityRowCard.tsx`

Exact paths can follow the repo's existing `ui/` conventions if different, but keep the structure coherent.

### 6. Render the Triage Board layout
Suggested page sections:
- page header / title
- trust strip (board-level data_state + feeder chip + timestamp)
- action row with **Run Triage** button
- triage list panel (ranked EntityRowCard list)
- empty/unavailable/error replacement state when applicable

### 7. Handle row click navigation
Each row should navigate to the Journey placeholder route with enough routing context to preserve future extension.

Safe options:
- route to `#/journey/{symbol}`
- use the row's `symbol` field as the route parameter

### 8. Implement per-row staleness
For each TriageItem:
- if `verdict_at` exists and indicates staleness, show stale badge
- fresh rows show no badge (absence = trust signal)
- do NOT invent per-row `data_state`

### 9. Keep styling disciplined
Use Tailwind and the existing app shell visual language.
Focus on trust/readability:
- clear state labels
- compact but readable row cards
- obvious click affordance
- strong empty/error distinction
- medium-density TradingView watchlist style (DESIGN_NOTES §3)
- `why_interesting` gets the widest column

### 10. Add tests
At minimum, add frontend tests for:
- loading state render
- ready state render with rows
- empty state render
- unavailable/error handling
- run-triage action transitions / mutation trigger behavior
- row click navigation affordance

### 11. Verify against backend
- Start the backend (`uvicorn ai_analyst.api.main:app`)
- Start the React dev server (`cd ui && npm run dev`)
- Confirm triage data renders from the real backend
- Confirm "Run Triage" works end-to-end
- Confirm feeder health chip renders

### 12. Update docs
- `docs/AI_TradeAnalyst_Progress.md` — mark Phase 2 complete, Phase 3 next
- `docs/specs/ui_reentry_phase_plan.md` — mark Phase 2 complete
- Update `ui/README.md` if new run instructions are needed

## Implementation notes
- Prefer small adapter functions over deeply conditional JSX.
- Keep timestamp formatting centralized if added.
- Do not add broad abstraction layers yet.
- If query invalidation keys are introduced, name them cleanly because PR-UI-3 will likely build on them.
- Use the typed API client from PR-UI-1 — do not rewrite it.
- The wireframe in VISUAL_APPENDIX.md is the visual target, but functional correctness matters more than pixel-perfect styling in this PR.
