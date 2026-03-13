# IMPLEMENTATION PLAN — PR-OPS-3

## Recommended sequence

### 1. Create the Ops API client layer
Add typed frontend client functions under `ui/src/shared/api/ops.ts`:

- `fetchAgentRoster()`
- `fetchAgentHealth()`

These should use the existing `apiFetch<T>` wrapper and preserve the contract error envelope behavior already established in the UI layer.

### 2. Add query hooks
Add hooks such as:

- `useAgentRoster()`
- `useAgentHealth()`

Suggested behavior:

- roster: fetch on mount, normal refetch on window focus if that is the existing convention
- health: fetch on mount with modest polling / stale time appropriate for a snapshot signal

### 3. Add Ops adapters / view models
Create a small adapter layer under `ui/src/workspaces/ops/adapters/`.

Purpose:

- join roster and health safely
- normalize entities into UI-ready records
- preserve layer/group structure
- expose derived workspace summaries such as:
  - healthy entity count
  - degraded entity count
  - unavailable entity count
  - health query degraded banner state

Keep the adapter deterministic and thin. Do not invent semantics not present in the contract.

### 4. Build Ops-specific components
Introduce workspace-owned components as needed, for example:

- `AgentOpsPage`
- `OpsSummaryBar`
- `OpsLayerSection`
- `OpsDepartmentSection`
- `OpsEntityCard` or `OpsEntityRow`
- `OpsRelationshipList` or simple relationship visual
- `OpsSelectedDetailPanel`
- `OpsDegradedBanner`

Reuse shared components where appropriate.

### 5. Replace the `/ops` placeholder route
Wire the existing Ops route to the real Agent Operations workspace.

Expected route outcome:

- live roster + health rendering
- selected entity detail surface
- graceful loading / degraded / error handling

### 6. Add tests
Add focused tests for:

- successful render with real contract-shaped fixtures
- degraded roster-success / health-failure behavior
- fresh-start empty health behavior
- roster failure behavior
- entity selection and detail rendering
- join behavior between roster and health
- relationship rendering presence
- polling configuration / query behavior where feasible

### 7. Documentation closure
Update the minimal docs necessary:

- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Only note completion and next phase; do not expand scope.

## Suggested file shape

```text
ui/src/shared/api/ops.ts
ui/src/shared/hooks/useAgentRoster.ts
ui/src/shared/hooks/useAgentHealth.ts

ui/src/workspaces/ops/
├── adapters/
│   └── opsViewModel.ts
├── components/
│   ├── AgentOpsPage.tsx
│   ├── OpsSummaryBar.tsx
│   ├── OpsLayerSection.tsx
│   ├── OpsDepartmentSection.tsx
│   ├── OpsEntityCard.tsx
│   ├── OpsSelectedDetailPanel.tsx
│   └── OpsDegradedBanner.tsx
└── routes/
    └── AgentOpsRoute.tsx
```

Names may vary, but the separation of concerns should remain:

- API
- hooks
- adapters
- components
- route

## Review standard
This PR should read like the frontend analogue of PR-OPS-2:

- contract-aligned
- honest about degraded states
- free of speculative future features
- compositional rather than over-abstracted
