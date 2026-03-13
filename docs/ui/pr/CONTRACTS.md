# CONTRACTS — PR-UI-1

## 1. Repo-shape contract
This PR must lock the repo-shape for the new React frontend so future contributors do not improvise structure.

A good default shape is:

```text
ui/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    app/
      App.tsx
      router.tsx
      providers/
    shared/
      api/
      components/
      hooks/
      lib/
      styles/
      types/
    workspaces/
      triage/
        routes/
        components/
        hooks/
        types/
```

Alternative names like `app-react/` are acceptable **only if** they are clearly justified and documented. The important thing is that the choice is made once here and used consistently.

### Must be explicit
Document:
- where the React app lives
- where shared components live
- where typed API clients live
- where workspace-specific code lives
- whether the React app has its own build pipeline
- how the React app is served alongside the current `app/`

## 2. Coexistence contract
The new React app must coexist with the legacy `app/`.

Acceptable coexistence patterns:
- separate dev port
- proxied route
- side-by-side served assets
- another documented local-dev strategy

This PR does **not** need to solve the final production hosting shape, but it must define a sane local/dev coexistence path.

### CORS / proxy handling
The Vite dev server will run on a different port from the FastAPI backend (default port 8000). Cross-origin requests will fail without either a Vite proxy config or backend CORS headers.

**Required in this PR:** add a Vite proxy configuration in `vite.config.ts` that forwards API requests (e.g. `/api/*` or bare paths like `/watchlist/triage`) to the backend port. This is the lowest-friction approach.

**Do NOT** modify any Python/backend files for CORS in this PR. If the Vite proxy config is insufficient for the repo's serving setup, flag as a follow-up — do not change backend code.

## 3. Routing contract
The new shell must support hash-based routing matching the URL plan in `UI_WORKSPACES.md` §4.2.

### Full route table (create all in this PR)

| Route | Component | Status in PR-UI-1 |
|-------|-----------|-------------------|
| `#/triage` | `TriageBoardPage` | Placeholder — shell only |
| `#/journey/:asset` | — | Route defined, placeholder component |
| `#/analysis` | — | Route defined, placeholder component |
| `#/journal` | — | Route defined, placeholder component |
| `#/review` | — | Route defined, placeholder component |
| `#/ops` | — | Route defined, placeholder component |
| Default (`/`) | — | Redirect to `#/triage` |

### Route behavior
- Triage route should render a workspace placeholder that clearly indicates Phase 2 will supply real data rendering.
- All other routes should render a minimal placeholder with workspace name (not blank pages).
- Unknown-route behavior should be handled gracefully (404 placeholder or redirect to triage).
- Default route redirects to `#/triage`.

## 4. API client contract
Create a typed API layer with:
- central base URL / environment config
- generic typed fetch wrapper
- typed success/error handling
- route-specific client functions for known existing surfaces that Phase 2 will need

### Fetch wrapper shape

```typescript
// shared/api/client.ts

type ApiResponse<T> = {
  data: T;
  status: number;
  ok: boolean;
};

type ApiError = {
  status: number;
  detail: string | Record<string, unknown>;
  raw?: unknown;
};

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<ApiResponse<T>>;
```

### Error handling contract
The fetch wrapper must preserve the mixed `detail` patterns documented in `UI_CONTRACT.md` §11:
- `detail` may be a string
- `detail` may be an object
- structured objects may include `message`, `code`, `request_id`, `run_id`

The wrapper must NOT normalise all errors into a single string. Preserve the original shape so workspace code can handle endpoint-family-specific errors.

### Triage endpoint types (match UI_CONTRACT.md §9.5)

```typescript
// shared/api/triage.ts

export type TriageItem = {
  symbol: string;
  triage_status?: string;
  bias?: string;
  confidence?: number;
  why_interesting?: string;
  rationale?: string;
  verdict_at?: string;
};

export type WatchlistTriageResponse = {
  data_state: string;
  generated_at?: string;
  items: TriageItem[];
};

export type TriggerTriageResponse = {
  status: string;
  artifacts_written?: number;
  symbols_processed?: number;
  output_dir?: string;
};

export async function fetchWatchlistTriage(): Promise<WatchlistTriageResponse>;
export async function triggerTriage(symbols?: string[]): Promise<TriggerTriageResponse>;
```

These types are derived from `UI_CONTRACT.md` §9.5 and §10.2. Optional fields use `?` to tolerate incomplete responses.

### Other endpoint modules
Other endpoint modules (journey, analysis, feeder, health) can be created as empty stubs with TODO comments or omitted until their workspace PR.

### Important
This PR does not need to fully consume these endpoints in the UI yet. The client just needs to exist, compile, and be ready.

## 5. State/query scaffolding contract
This PR should include only light scaffolding, such as:
- TanStack Query setup, or
- a minimal custom async state layer if the repo should stay lighter at this stage

Either is acceptable, but the decision should be intentional and documented.

Recommended:
- prefer TanStack Query if the future workspace model will benefit from cache/refetch/error state consistency
- otherwise keep it minimal and avoid overengineering

## 6. Styling contract
Tailwind should be wired and usable in the new app.
This PR does not need to fully encode the design system, but it should:
- establish global styles
- prove utility classes are working
- provide a sane app shell look
- avoid pulling in a large UI library prematurely unless clearly justified

## 7. Placeholder UI contract
The Triage placeholder should include:
- workspace title
- short note that this is the React shell / Phase 1 foundation
- obvious placeholder sections for future content
- optional API-status/dev panel if useful for proving the shell, but not a fake data board

It should **not** pretend to be the real Triage Board.

All other route placeholders should render workspace name + "shell" indicator. No blank pages.

## 8. Documentation contract
This PR should leave behind enough documentation that another contributor can answer:
- where the new frontend lives
- how to run it
- how it coexists with legacy `app/`
- what Phase 1 delivered
- what remains for PR-UI-2
