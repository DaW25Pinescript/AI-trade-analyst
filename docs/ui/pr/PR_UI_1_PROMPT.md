# PR-UI-1 IMPLEMENTATION PROMPT

Implement **PR-UI-1 — React App Shell + Triage Board Route** for the `AI-trade-analyst` repo.

You are implementing the first code PR after the UI governance unlock. This is a **frontend foundation PR**, not a feature-complete workspace PR.

## Mission
Create the new React + TypeScript + Tailwind frontend shell that will become the forward UI lane, while preserving coexistence with the current legacy `app/`.

This PR must establish:
- the new frontend repo-shape
- build tooling
- routing
- typed API scaffolding
- minimal state/query scaffolding
- a Triage route placeholder
- enough documentation and scripts for the new lane to be runnable and verifiable

## Critical repo context
Follow these locked decisions:
- React + TypeScript + Tailwind is the forward stack for all new UI work.
- Triage Board is the first React workspace because it uses existing endpoints and becomes the component-system seed.
- Agent Operations is a later Phase 3B extension and is **not** part of this PR.
- React must coexist with the existing `app/` during workspace-by-workspace migration.
- Do not infer contracts from undocumented backend behavior.
- Do not create new backend endpoints.
- Do not add SSE/WebSocket/live-stream behavior.
- Do not turn this into a full Triage Board implementation yet.

## Before writing any code
Inspect the current repo first:
- inspect current `app/` structure
- inspect existing package/tooling setup (any existing `package.json`, `vite.config`, `tsconfig`?)
- inspect how the backend is currently served in dev
- inspect any existing route/path assumptions in docs
- check whether a `ui/` directory already exists

Do not blindly impose a structure that fights the repo. Adapt to what you find.

## Authoritative scope for PR-UI-1
This PR should deliver:
1. Base React/TS/Tailwind project setup
2. Build tooling (Vite preferred unless repo fit strongly suggests equivalent)
3. Routing framework for workspace navigation (hash-based)
4. Typed API client layer with error handling matching `UI_CONTRACT.md` §11
5. State/query scaffolding (TanStack Query recommended; document the choice)
6. Triage Board route placeholder
7. Locked frontend repo-shape and coexistence documentation

## Mandatory repo-shape decision
In this PR, explicitly lock:
- where the React app lives (`ui/` preferred unless repo reality demands otherwise)
- where shared components live (e.g. `ui/src/shared/components/`)
- where typed API clients live (e.g. `ui/src/shared/api/`)
- where workspace-specific code lives (e.g. `ui/src/workspaces/triage/`)
- whether the React app has its own build pipeline
- how the React app is served alongside the existing `app/`

Make this decision once and apply it consistently. Do not leave structure ambiguous.

## Routing (hash-based, all routes created in this PR)

| Route | Component | Status |
|-------|-----------|--------|
| `#/triage` | TriageBoardPage | Placeholder shell |
| `#/journey/:asset` | — | Placeholder |
| `#/analysis` | — | Placeholder |
| `#/journal` | — | Placeholder |
| `#/review` | — | Placeholder |
| `#/ops` | — | Placeholder |
| Default (`/`) | — | Redirect to `#/triage` |

All placeholder routes must render workspace name + "shell" indicator. No blank pages.
Unknown routes should redirect to triage or show a 404 placeholder.

## Typed API client requirements

Read `docs/ui/UI_CONTRACT.md` §5 (transport), §9 (domain model), and §11 (error contracts).

Create a generic `apiFetch<T>` wrapper in the shared API layer. No `any` types.

Error handling must preserve the mixed `detail` patterns from `UI_CONTRACT.md` §11:
- `detail` may be a string
- `detail` may be an object
- structured objects may include `message`, `code`, `request_id`, `run_id`
- do NOT normalise all errors into a single string

Create typed triage endpoint functions matching `UI_CONTRACT.md` §9.5:

```typescript
type TriageItem = {
  symbol: string;
  triage_status?: string;
  bias?: string;
  confidence?: number;
  why_interesting?: string;
  rationale?: string;
  verdict_at?: string;
};

type WatchlistTriageResponse = {
  data_state: string;
  generated_at?: string;
  items: TriageItem[];
};

type TriggerTriageResponse = {
  status: string;
  artifacts_written?: number;
  symbols_processed?: number;
  output_dir?: string;
};
```

Export `fetchWatchlistTriage()` and `triggerTriage()` functions. They do not need to be consumed in the UI yet — just compiled and ready for PR-UI-2.

## CORS / proxy handling
The Vite dev server runs on a different port from the FastAPI backend (default 8000). Add a Vite proxy configuration in `vite.config.ts` that forwards API requests to the backend port. Do NOT modify any Python/backend files for CORS. If proxy config is insufficient, flag as a follow-up.

## Implementation instructions
1. Inspect the repo first and adapt to its current reality.
2. Choose the React app location and implement it cleanly.
3. Create a minimal but solid React shell with top-level layout.
4. Add routing and ensure all routes from the table above are reachable.
5. Add the typed API layer with the triage endpoint types above.
6. Add light state/query scaffolding (TanStack Query recommended; document choice).
7. Add Vite proxy config for backend API calls.
8. Create a Triage placeholder page that clearly signals "foundation only, real data in PR-UI-2".
9. Add scripts: install, dev, build, preview, typecheck.
10. Add minimal smoke verification (Vitest or equivalent if low-friction).
11. Update docs so another contributor can run and understand this frontend lane.
12. Keep the PR tight. No Phase 2 work should be smuggled in.

## Hard constraints
- No real Triage Board data rendering yet
- No shared component extraction pass yet
- No Agent Ops UI
- No backend modifications
- No contract drift
- No breaking legacy `app/`
- No giant cleanup/refactor unrelated to this PR
- No decorative overbuild
- No SSE/WebSocket/streaming setup

## Acceptance standard
The PR is acceptable only if:
- the new React app builds (`npm run build` or equivalent)
- TypeScript typecheck passes (`tsc --noEmit` or equivalent)
- the app can run alongside the existing `app/`
- routing works for all defined routes (no blank pages)
- default route redirects to `#/triage`
- typed API scaffolding exists and compiles for triage endpoints
- error handling preserves mixed detail patterns (not normalised to string)
- Vite proxy config exists for backend API
- Tailwind utility classes render correctly
- the shell is documented (where it lives, how to run it, how it coexists)
- the placeholder does not pretend to be the final Triage Board
- repo-shape is locked and documented

The PR is NOT acceptable if:
- it renders mock triage data as though Phase 2 already happened
- it adds unrelated design-system work
- it changes backend behavior or modifies Python files
- it introduces Agent Ops UI
- it breaks legacy `app/`
- it leaves repo-shape ambiguous
- it cannot be built or typechecked cleanly
- any route renders a blank page

## Documentation updates
On completion, update:

1. `docs/AI_TradeAnalyst_Progress.md`:
   - Mark Phase 1 as ✅ Complete
   - Mark Phase 2 (Triage Board MVP) as ▶️ Next
   - Add build/typecheck verification note in latest increment

2. `docs/specs/ui_reentry_phase_plan.md`:
   - Mark Phase 1 Complete if applicable

3. Add a README inside the new React app directory documenting:
   - chosen repo-shape and rationale
   - how to install, run dev server, build, and typecheck
   - how coexistence with legacy `app/` works
   - what this shell delivers vs what remains for PR-UI-2

## Deliverables
Please make the code changes directly in the repo and then return:

1. **Summary**
   - what you built
   - why the repo-shape was chosen

2. **Exact repo-shape chosen**
   - directory structure

3. **Files added/changed**
   - key files

4. **Commands run**
   - install, build, typecheck, dev server

5. **Verification results**
   - build pass/fail
   - typecheck pass/fail
   - route verification
   - any CORS or serving issues encountered

6. **Any deviations from plan and why**

7. **Suggested commit message**
   `feat(ui): React app shell with Vite, TypeScript, Tailwind, routing, and typed API client`

8. **Suggested PR description**

## Quality bar
Prefer a boring, durable foundation over a flashy partial product.
This PR should make PR-UI-2 easier, not tempt the repo into premature UI complexity.
