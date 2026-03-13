# Shared Components & Hooks

Cross-workspace primitives for the AI Trade Analyst React UI. These belong in `shared/` because they encode no workspace-specific domain logic.

## Components by Subdirectory

### `components/state/`
- **DataStateBadge** — Board-level data freshness badge (LIVE / STALE / UNAVAILABLE / DEMO-FALLBACK)
- **StatusPill** — Compact categorical label pill with variant coloring

### `components/trust/`
- **TrustStrip** — Composed strip: DataStateBadge + FeederHealthChip + timestamp (per DESIGN_NOTES §2)
- **FeederHealthChip** — Feeder freshness signal with age formatting and health dot

### `components/layout/`
- **PanelShell** — Workspace panel container with consistent spacing

### `components/feedback/`
- **EmptyState** — Zero-items state (not an error)
- **ErrorState** — Fetch failure with optional retry button
- **UnavailableState** — Data source unavailable (not a failure)
- **LoadingSkeleton** — Animated placeholder rows during loading

### `components/entity/`
- **EntityRowCard** — Generic clickable row card with label, pill, meta, description, badge

## Import Paths

Barrel imports (preferred):
```ts
import { DataStateBadge, StatusPill } from "@shared/components/state";
import { TrustStrip, FeederHealthChip } from "@shared/components/trust";
import { PanelShell } from "@shared/components/layout";
import { EmptyState, ErrorState, LoadingSkeleton, UnavailableState } from "@shared/components/feedback";
import { EntityRowCard } from "@shared/components/entity";
import { useWatchlistTriage, useFeederHealth } from "@shared/hooks";
```

Direct imports (when barrel is not desired):
```ts
import { DataStateBadge } from "@shared/components/state/DataStateBadge";
```

## Hooks

| Hook | Cache Key Constant | Endpoint | Stale Time |
|------|--------------------|----------|------------|
| `useWatchlistTriage` | `WATCHLIST_TRIAGE_KEY` | `GET /watchlist/triage` | 30s (default) |
| `useFeederHealth` | `FEEDER_HEALTH_KEY` | `GET /feeder/health` | 15s |

Convention: cache key exported as named constant, return type explicit, stale time documented.

## API Clients (`api/`)

- **client.ts** — `apiFetch<T>()` generic typed fetch wrapper with `ApiResult<T>` discriminated union
- **triage.ts** — `fetchWatchlistTriage()`, `triggerTriage()`
- **feeder.ts** — `fetchFeederHealth()`

## How to Add a New Shared Component

1. Create the component in the appropriate subdirectory (state, trust, layout, feedback, entity)
2. Export typed props interface (`export interface FooProps`)
3. Add to the subdirectory barrel file (`index.ts`)
4. Write isolated component tests in `tests/shared-components.test.tsx`
5. Update this README

A component belongs in `shared/` only if:
- It does not encode workspace-specific domain assumptions
- Its props can be described in general UI terms
- Reusing it in another workspace would not feel misleading
- Its tests can be written without workspace-specific fixtures

## EntityRowCard Decision (PR-UI-3)

**Decision: Option A — Made generic, stays in shared.**

The original `EntityRowCard` accepted `TriageRowViewModel` directly, coupling it to the triage workspace. It was refactored to accept generic props (`label`, `pill`, `meta`, `description`, `badge`, `onClick`). The triage workspace wraps it with `TriageRowCard` in `workspaces/triage/components/` for domain-specific field mapping (bias → pill variant, confidence → meta string, freshness → badge).

Rationale: the card's visual pattern (label + pill + meta + description + trailing badge + arrow) is reusable across Journey Studio, Analysis Run, and other ranked-entity views. Only the field mapping is triage-specific.
