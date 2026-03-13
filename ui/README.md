# AI Trade Analyst — React UI

> **PR-UI-3 hardened.** This is the forward React + TypeScript + Tailwind frontend. It coexists with the legacy `app/` during workspace-by-workspace migration.

## Repo-Shape

```
ui/                          ← React app root (own build pipeline)
├── index.html
├── package.json
├── vite.config.ts           ← Vite build + dev proxy to FastAPI :8000
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── public/
├── tests/                   ← Vitest tests (smoke + component + integration)
└── src/
    ├── main.tsx              ← Entry point
    ├── app/
    │   ├── App.tsx           ← Root component (QueryClientProvider)
    │   ├── AppShell.tsx      ← Top-level layout + nav
    │   └── router.tsx        ← Hash-based routing (react-router-dom)
    ├── shared/
    │   ├── README.md         ← Component inventory + contributor guide
    │   ├── api/
    │   │   ├── client.ts     ← Generic apiFetch<T> wrapper
    │   │   ├── triage.ts     ← Typed triage endpoint functions
    │   │   └── feeder.ts     ← Feeder health endpoint client
    │   ├── components/       ← Shared UI components (barrel exports per subdir)
    │   │   ├── state/        ← DataStateBadge, StatusPill
    │   │   ├── trust/        ← TrustStrip, FeederHealthChip
    │   │   ├── layout/       ← PanelShell
    │   │   ├── feedback/     ← EmptyState, ErrorState, UnavailableState, LoadingSkeleton
    │   │   └── entity/       ← EntityRowCard (generic)
    │   ├── hooks/            ← useWatchlistTriage, useFeederHealth (barrel export)
    │   ├── styles/
    │   │   └── index.css     ← Tailwind base
    │   └── types/
    └── workspaces/
        ├── triage/           ← Triage Board workspace
        │   ├── adapters/     ← triageViewModel.ts
        │   ├── components/   ← TriageRowCard (wraps EntityRowCard)
        │   ├── hooks/        ← useTriggerTriage (triage-specific mutation)
        │   └── routes/       ← TriageBoardPage.tsx
        ├── journey/
        ├── analysis/
        ├── journal/
        ├── review/
        └── ops/
```

### Why this shape

- **`ui/` at repo root** — clean separation from legacy `app/`, own `package.json` and build pipeline, no conflict with existing vanilla JS.
- **`src/shared/`** — API clients, components, hooks, and types shared across all workspaces.
- **`src/workspaces/<name>/`** — workspace-specific routes, components, hooks, types. Each workspace is self-contained except for shared imports.
- **Own build pipeline** — `ui/` has its own Vite build. It does not share tooling with `app/`.

## Quick Start

```bash
cd ui/
npm install
npm run dev          # Vite dev server on :5173, proxies API to :8000
npm run build        # Production build (runs tsc --noEmit first)
npm run typecheck    # TypeScript check only
npm run test         # Vitest smoke tests
npm run preview      # Preview production build
```

## Coexistence with Legacy `app/`

The React app and the legacy `app/` run independently:

- **Legacy `app/`** is served by the FastAPI backend (static files) on port 8000.
- **React `ui/`** runs its own Vite dev server on port 5173 during development.
- The Vite dev server proxies all API requests (`/watchlist/*`, `/triage/*`, `/journey/*`, etc.) to `localhost:8000` so no CORS configuration is needed.
- In production, `ui/` builds to `ui/dist/` which can be served by any static file server or reverse proxy alongside the backend.

No changes to the backend or `app/` are required.

## Routing

Hash-based routing via `react-router-dom`:

| Route | Component | Status |
|-------|-----------|--------|
| `#/triage` | TriageBoardPage | Placeholder |
| `#/journey/:asset` | WorkspacePlaceholder | Placeholder |
| `#/analysis` | WorkspacePlaceholder | Placeholder |
| `#/journal` | WorkspacePlaceholder | Placeholder |
| `#/review` | WorkspacePlaceholder | Placeholder |
| `#/ops` | WorkspacePlaceholder | Placeholder |
| `/` (default) | Redirect → `#/triage` | |
| Unknown | 404 with link to Triage | |

## State/Query Choice

**TanStack Query** (`@tanstack/react-query`) is used for server state management.

Rationale: the workspace model benefits from TanStack Query's built-in cache, stale-while-revalidate, refetch-on-focus, and error/loading state handling — all of which align with the `data_state` semantics in `UI_CONTRACT.md` §6. This avoids reinventing async state management while keeping the surface small.

The `QueryClient` is configured in `App.tsx` with sensible defaults (30s stale time, 1 retry).

## API Client

`src/shared/api/client.ts` exports a generic `apiFetch<T>()` wrapper. Error handling preserves the mixed `detail` patterns from `UI_CONTRACT.md` §11 — errors are NOT normalised to a single string.

`src/shared/api/triage.ts` exports typed `fetchWatchlistTriage()` and `triggerTriage()` functions matching §9.5. These compile but are not consumed in the UI yet (that's PR-UI-2).

## What This Delivers vs PR-UI-2

**PR-UI-1 (this shell):**
- Project setup, build tooling, routing
- Typed API scaffolding (compiles, not consumed)
- Placeholder pages for all workspaces
- TanStack Query wiring
- Vite proxy config

**PR-UI-2 (next):**
- Live data rendering from `/watchlist/triage`
- "Run Triage" action
- First shared component primitives (DataStateBadge, TrustStrip, StatusPill, etc.)
- Real `data_state` handling in the UI
