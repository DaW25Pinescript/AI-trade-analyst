# PR-UI-2 Implementation Prompt

Implement **PR-UI-2 — Triage Board MVP on real endpoints** for the AI Trade Analyst repo.

## Context
PR-UI-0 reopened the UI lane and locked the forward stack to **React + TypeScript + Tailwind**.
PR-UI-1 created the React shell in `ui/`, including routing, typed API scaffolding, Query provider setup, and placeholder workspace pages.

This PR is the next narrow step:
**replace the Triage placeholder with a working Triage Board rendered from real backend data.**

## Before writing any code
Read these docs:
- `docs/specs/ui_reentry_phase_plan.md` (Phase 2)
- `docs/ui/UI_CONTRACT.md` §6 (state semantics), §9.5 (TriageItem), §9.9 (FeederHealth), §10.2 (triage endpoints), §11 (error contracts), §12.2 (retryability)
- `docs/ui/UI_WORKSPACES.md` §5 (Triage Board layout)
- `docs/ui/DESIGN_NOTES.md` §1.1 (per-row staleness), §1.2 (data_state read-only), §1.5 (triage→journey handoff), §2 (trust strip), §3 (density rule)
- `docs/ui/VISUAL_APPENDIX.md` (Triage Board wireframe)

Then audit the current `ui/` shell:
- confirm typed triage API functions exist (`fetchWatchlistTriage`, `triggerTriage`)
- confirm TanStack Query provider is wired
- confirm Vite proxy works for backend API calls
- note: PR-UI-1 did NOT create a feeder health API client — that is new work for this PR

## Governing phase intent
Phase 2 in the UI re-entry plan is explicitly:
- live data rendering from `GET /watchlist/triage`
- **Run Triage** action via `POST /triage`
- row click → Journey placeholder route
- first shared primitives extracted, but only those genuinely needed
- correct handling of ready / empty / stale / unavailable / demo-fallback / error states
- board-level `data_state` visible at all times
- per-row freshness derived from `verdict_at` where available, not invented per-row `data_state`

## Required scope
Use only existing endpoints:
- `GET /watchlist/triage`
- `POST /triage`
- `GET /feeder/health` (for trust strip feeder chip)

Build in `ui/` only.
No backend changes.
No legacy `app/` migration.
No Agent Ops work.
No Journey implementation beyond navigation handoff.
No SSE/live-stream behavior.

## Deliverables
1. **Feeder health API client** — create `ui/src/shared/api/feeder.ts` with `FeederHealth` type (matching UI_CONTRACT §9.9) and `fetchFeederHealth()` function.

2. **View-model / adapter layer** — create a thin mapping between raw API responses and view rendering so backend quirks do not leak into JSX.

3. **TanStack Query hooks** in `ui/src/shared/hooks/`:
   - `useWatchlistTriage()` — query for `GET /watchlist/triage`, supports manual refetch
   - `useTriggerTriage()` — mutation for `POST /triage`, invalidates triage query cache on success
   - `useFeederHealth()` — query for `GET /feeder/health`, lightweight with short stale time

4. **Shared components** in `ui/src/shared/components/` subdirectories:
   - `state/DataStateBadge` — LIVE / STALE / UNAVAILABLE / DEMO-FALLBACK
   - `state/StatusPill` — reusable state indicator
   - `trust/TrustStrip` — data_state badge + feeder chip + timestamp grouped
   - `trust/FeederHealthChip` — compact feeder freshness signal
   - `layout/PanelShell` — workspace panel container
   - `feedback/EmptyState` / `UnavailableState` / `ErrorState` / `LoadingSkeleton`
   - `entity/EntityRowCard` — triage row with symbol, bias, confidence, why_interesting, hover + click

5. **Triage Board page** — replace PR-UI-1 placeholder with:
   - top bar: title + TrustStrip + "Run Triage" button
   - main board: ranked EntityRowCard list
   - all 7 state conditions handled (see table below)
   - row click → `#/journey/{symbol}`

6. **Run Triage action** with explicit lifecycle:
   - `idle → running → completed | failed`
   - on success: invalidate triage query → board re-fetches
   - on failure: show error, allow explicit retry, no auto-retry
   - partial failure (`{ message, partial }`) surfaced, not collapsed
   - do NOT invent `partial` state — triage is not streaming

7. **Tests** for loading, ready, empty, unavailable/error, mutation flow, row click.

## State handling rules

| Condition | Trigger | UI |
|-----------|---------|-----|
| loading | Initial fetch in progress | Skeleton/spinner |
| ready | `items.length > 0`, data_state is live | Render board |
| empty | `items.length === 0` | "No triage items" — NOT error |
| stale | `data_state === "stale"` | Board + stale warning |
| unavailable | `data_state === "unavailable"` | "Triage data unavailable" |
| demo-fallback | Fallback data used | Demo badge visible |
| error | Fetch failed | Error + optional retry |

## Per-row staleness rules
- Derive from `verdict_at` on each TriageItem
- Fresh = no badge (absence is trust signal)
- Stale = show stale badge
- Do NOT invent per-row data_state

## Layout (DESIGN_NOTES §3, UI_WORKSPACES §5)
- Medium-density TradingView watchlist style
- `why_interesting` gets widest column and breathing room
- Entire row clickable with hover affordance
- Content expands downward, not overlay
- Trust strip always visible in top bar

## Non-invention rule
If the backend contract does not yet expose a field the design would ideally like, do not fabricate it. Render from what exists, degrade gracefully, and leave a tight TODO note only where justified.

## Implementation guidance
- Audit the current `ui/` repo shape before coding and reuse existing typed API/query infrastructure from PR-UI-1.
- Introduce a thin view-model / adapter layer so backend quirks do not leak into rendering.
- Preserve mixed error detail behavior from the typed fetch wrapper.
- Keep extraction proportional: this is not PR-UI-3.
- Use Tailwind and existing shell conventions.
- Prefer structured human-readable trust UI over raw payload dumps.
- The page should feel like a trustworthy triage board, not a raw JSON viewer and not a decorative dashboard.

## Hard constraints
- No backend modifications
- No other workspace implementations
- No SSE/streaming
- No Agent Ops
- data_state is read-only — no dropdown
- No auto-retry on triage failure
- Shared components in shared/ subdirectories, not inlined
- Functional correctness over visual polish

## Acceptance bar
The PR is successful only if:
- Triage Board renders real backend data
- **Run Triage** works with trigger-and-refresh pattern
- All 7 state conditions handled correctly
- Board-level trust strip always visible with data_state + feeder chip + timestamp
- Per-row staleness from verdict_at only
- Row click navigates to `#/journey/{symbol}`
- Shared components in `ui/src/shared/components/` subdirectories
- Named hooks exist (`useWatchlistTriage`, `useTriggerTriage`, `useFeederHealth`)
- Feeder health API client exists
- No backend files changed
- `ui/` build, typecheck, and tests all pass

## Documentation closure
At the end of the PR, update:
- `docs/AI_TradeAnalyst_Progress.md` — Phase 2 ✅ Complete, Phase 3 ▶️ Next
- `docs/specs/ui_reentry_phase_plan.md` — Phase 2 marked complete
- any relevant `ui/README.md` notes if frontend commands or route behavior changed

## Output format requested
Please return:
1. Summary of changes
2. Shared components created (with subdirectory structure)
3. Hooks created
4. File-by-file change list
5. State handling verification (all 7 conditions)
6. Verification results (`build`, `typecheck`, `test`)
7. Any deviations from scope and why
8. Suggested commit message: `feat(ui): implement Triage Board MVP with real triage data, shared components, and trust strip`
9. Suggested PR description

## Quality bar
The Triage Board should feel like a trustworthy triage board showing real data with real trust signals — not a raw JSON viewer, not a decorative dashboard, and not a demo mockup. Functional correctness and correct state handling matter more than visual polish. This is the component-system seed that every future workspace inherits from.
