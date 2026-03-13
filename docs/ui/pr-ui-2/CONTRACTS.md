# CONTRACTS — PR-UI-2

## Contract authority
The implementation must stay faithful to the repo's existing UI contract and UI re-entry plan.

Relevant governing guidance already captured in the plan:
- Phase 2 is Triage Board MVP on real endpoints
- Backend basis is `GET /watchlist/triage` and `POST /triage`
- `data_state` must remain visible as a board-level trust signal
- Per-row staleness should be derived from `verdict_at` where available
- No invented per-row `data_state`
- No mock-only dependency for this phase

## Expected functional contract assumptions
The exact payloads should be read from the repo contract/docs and existing typed client scaffolding, but the UI should be written around these practical rules:

### 1. Triage list source
`GET /watchlist/triage`

Assume it provides, directly or indirectly:
- ranked triage entities / instruments
- trust/freshness information (`data_state`, timestamps, feeder or freshness hints)
- enough row-level metadata to render a ranked board

### 2. Trigger action
`POST /triage`

Trigger-and-refresh semantics with explicit lifecycle:

```
idle → running → completed | failed
         ↓
   (on success, invalidate triage query → board re-fetches)
```

Rules:
- user clicks **Run Triage**
- mutation enters running/pending state
- on success, triage board refreshes via cache invalidation (not by parsing POST response into board items)
- UI reflects idle / running / refreshed / failed states cleanly
- do NOT invent `partial` state — triage is not a streaming endpoint
- do NOT auto-retry on failure (UI_CONTRACT §12.2) — allow explicit user rerun
- partial failure (`{ message, partial }`) should be surfaced, not collapsed into generic error

### 3. Trust semantics
The board must surface trust clearly.

Expected UI dimensions:
- board-level `data_state`
- feeder health / availability signal where present
- freshness timestamp / last updated signal
- row freshness derived from `verdict_at` or equivalent timestamp when available

### 4. UI states to support

| Condition | Trigger | UI behavior |
|-----------|---------|-------------|
| `loading` | Initial fetch in progress | Skeleton or spinner |
| `ready` | Valid response with `items.length > 0` | Render board normally |
| `empty` | Valid response, `items: []` | "No triage items" — not error |
| `stale` | `data_state === "stale"` | Board renders with stale warning badge |
| `unavailable` | `data_state === "unavailable"` | "Triage data unavailable" message |
| `demo-fallback` | Fallback data used when API fails | Demo badge visible |
| `error` | Fetch failed or response unusable | Error with optional retry |

### 5. Error handling
Use the typed fetch wrapper introduced in PR-UI-1.
If backend `detail` is mixed-shape, preserve it rather than collapsing it into a lossy generic string.

### 6. Navigation contract
Clicking a triage row should navigate to the Journey route placeholder.
This is a handoff affordance only; it does not imply Journey Studio is implemented.

## Feeder health API (new in this PR)

PR-UI-1 created the triage API client but not the feeder client. This PR must add it.

Create `ui/src/shared/api/feeder.ts`:

```typescript
type FeederHealth = {
  status: string;
  ingested_at?: string;
  age_seconds?: number;
  stale?: boolean;
  source_health?: string;
  regime?: string;
  vol_bias?: string;
  confidence?: number;
};

function fetchFeederHealth(): Promise<FeederHealth>;
```

## Hook contract

### Required hooks

| Hook | Purpose | Behavior |
|------|---------|----------|
| `useWatchlistTriage()` | Fetches `GET /watchlist/triage` via TanStack Query | Supports manual refetch; configurable polling (off by default); exposes `isLoading`, `isError`, `error`, `data` |
| `useTriggerTriage()` | Mutation for `POST /triage` | Invalidates triage query cache on success, triggering fresh board render; no auto-retry |
| `useFeederHealth()` | Fetches `GET /feeder/health` | Lightweight read; short stale time; no aggressive polling |

## Shared primitives expected in this PR
These are the first shared components called for by the phase plan and should be created only as needed by Triage:

Suggested subdirectory structure:
- `ui/src/shared/components/state/DataStateBadge.tsx`
- `ui/src/shared/components/state/StatusPill.tsx`
- `ui/src/shared/components/trust/TrustStrip.tsx`
- `ui/src/shared/components/trust/FeederHealthChip.tsx`
- `ui/src/shared/components/layout/PanelShell.tsx`
- `ui/src/shared/components/feedback/EmptyState.tsx`
- `ui/src/shared/components/feedback/UnavailableState.tsx`
- `ui/src/shared/components/feedback/ErrorState.tsx`
- `ui/src/shared/components/feedback/LoadingSkeleton.tsx`
- `ui/src/shared/components/entity/EntityRowCard.tsx`

## Non-invention rule
If the backend contract does not yet expose a field the design would ideally like, do not fabricate it. Render the board from what exists, degrade gracefully, and leave a tight TODO note only where justified.

## Design reference index

| Document | Relevant sections |
|----------|-------------------|
| `UI_WORKSPACES.md` §5 | Triage Board workspace spec |
| `DESIGN_NOTES.md` §1.1 | Per-row staleness derivation |
| `DESIGN_NOTES.md` §1.2 | data_state is read-only |
| `DESIGN_NOTES.md` §1.5 | Triage → Journey handoff |
| `DESIGN_NOTES.md` §2 | Component system — trust strip composition |
| `DESIGN_NOTES.md` §3 | Density and scanability rule |
| `VISUAL_APPENDIX.md` | Triage Board wireframe |
| `UI_CONTRACT.md` §6 | Shared state semantics |
| `UI_CONTRACT.md` §9.5 | TriageItem domain model |
| `UI_CONTRACT.md` §9.9 | FeederHealth domain model |
| `UI_CONTRACT.md` §10.2 | Triage endpoint contracts |
| `UI_CONTRACT.md` §11 | Error contract rules |
| `UI_CONTRACT.md` §12.2 | Timeout/retryability — triage = explicit rerun only |
