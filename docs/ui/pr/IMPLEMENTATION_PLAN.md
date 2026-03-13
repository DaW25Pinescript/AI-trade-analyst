# IMPLEMENTATION PLAN — PR-UI-1

## Recommended execution order

### 1. Inspect current repo frontend reality
Before writing code:
- inspect current `app/` structure
- inspect existing package/tooling setup
- inspect how the backend is currently served in dev
- inspect any existing route/path assumptions in docs

Do not blindly impose a structure that fights the repo.

### 2. Lock the repo-shape
Choose the new React app location and document it.

Recommended default:
- `ui/` as the React workspace root
- keep it clearly distinct from `app/`

### 3. Create React shell
Set up:
- Vite
- React
- TypeScript
- Tailwind
- eslint/prettier only if low-friction and already aligned with repo norms

### 4. Create app foundation
Create:
- root `App`
- router with hash-based navigation
- top-level layout shell
- placeholder nav or route switch
- all route placeholders from the route table (triage, journey, analysis, journal, review, ops)
- default route redirect to `#/triage`
- Triage route placeholder page

All placeholder routes must render workspace name + shell indicator. No blank pages.

### 5. Add shared plumbing
Create:
- `src/shared/api/client.ts` — generic typed `apiFetch<T>` wrapper with error handling that preserves mixed `detail` patterns from `UI_CONTRACT.md` §11 (string detail, object detail, structured objects with `request_id`/`run_id`)
- `src/shared/api/triage.ts` — typed client for `/watchlist/triage` and `/triage` with `TriageItem`, `WatchlistTriageResponse`, `TriggerTriageResponse` types matching `UI_CONTRACT.md` §9.5
- `src/shared/types/api.ts` — shared API response/error types
- optional `src/app/providers/QueryProvider.tsx` or equivalent (TanStack Query recommended; document the choice)
- environment/base URL config

### 6. Add Vite proxy config
Configure `vite.config.ts` to proxy API requests to the backend port (default 8000). This avoids CORS issues during development without modifying backend code.

Do NOT modify any Python/backend files for CORS in this PR. If proxy config is insufficient, flag as a follow-up.

### 7. Add scripts
At minimum:
- install (`npm install`)
- dev (`npm run dev`)
- build (`npm run build`)
- preview (`npm run preview`)
- typecheck (`tsc --noEmit` or equivalent)
- test (if a test harness is added)

### 8. Add minimal smoke verification
Depending on repo fit:
- simple Vitest test
- route render smoke test
- or another very light verification path

Do not overbuild the test layer in this PR.

### 9. Document the result
Update docs so the repo now records:
- chosen repo-shape and rationale
- how to install, run dev server, build, and typecheck
- how coexistence with legacy `app/` works
- what PR-UI-1 delivered
- that PR-UI-2 is next

Specific doc updates:
- `docs/AI_TradeAnalyst_Progress.md` — mark Phase 1 as ✅ Complete, Phase 2 as ▶️ Next, add build/typecheck verification note
- `docs/specs/ui_reentry_phase_plan.md` — mark Phase 1 Complete if applicable
- Add a README inside the new React app directory

## Suggested file targets
These are examples, not mandatory exact paths.

```text
ui/
  README.md
  package.json
  vite.config.ts
  tsconfig.json
  postcss.config.js
  tailwind.config.js
  src/
    main.tsx
    app/
      App.tsx
      router.tsx
      providers/
        QueryProvider.tsx
    shared/
      api/
        client.ts
        triage.ts
      components/
        AppShell.tsx
      hooks/
      lib/
        env.ts
      styles/
        globals.css
      types/
        api.ts
    workspaces/
      triage/
        routes/
          TriageRoute.tsx
```

## Suggested implementation notes
- Keep aliases/path mapping simple.
- Keep the API wrapper small and readable.
- Avoid introducing state-management libraries beyond what is truly useful.
- Prefer boring, obvious structure over clever abstractions.
- The next PR should be able to start rendering real triage data without refactoring the entire shell.
