# CONSTRAINTS — PR-OPS-3

## Scope discipline
This PR is **frontend-only**. Do not modify backend endpoint contracts or add new endpoints.

Consume only the already-shipped Agent Ops endpoints:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

Do not consume:

- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`

Those belong to the later forensic phase.

## Product constraints
Agent Operations must remain an **operator workspace**, not the main user workflow. It must not displace:

- Triage Board
- Journey Studio
- Analysis Run
- Journal & Review

The MVP is **Org / Structure mode only**.

## Behavioral constraints
Do not implement any of the following:

- run trace inspection
- control actions
- prompt editing
- manual orchestration
- live streaming / SSE / WebSocket
- optimistic updates
- artificial mock fallback when backend fetch fails

The UI must reflect actual backend responses honestly.

## Data constraints
Roster and health are separate data sources and may disagree temporarily.

The UI must handle at least these cases:

1. roster loads, health loads
2. roster loads, health fails
3. roster loads, health returns empty entities on fresh start
4. roster fails
5. both loading
6. both fail
7. health contains items with valid roster joins only

Do not invent extra entities client-side.

## Shared-component discipline
Prefer the existing shared component layer where it fits:

- `PanelShell`
- `DataStateBadge`
- `StatusPill`
- `LoadingSkeleton`
- `ErrorState`
- `UnavailableState`
- `EmptyState`
- generic `EntityRowCard` if appropriate

However, do not force generic reuse where an Ops-specific component is clearer. It is acceptable to introduce new workspace-owned components under `ui/src/workspaces/ops/` for:

- hierarchy sections
- relationship rendering
- selected-node detail panel
- health summary banners
- operator trust messaging

## Routing / access constraints
Use the existing React app routing conventions established in PR-UI-1.

If a feature-flag or operator-only gating mechanism already exists, use it. Otherwise, keep the route available but clearly labeled as an operator workspace.

## Documentation closure
Update only the minimal project docs necessary to record:

- Phase 5 / PR-OPS-3 completion
- any small README/UI route notes that are materially helpful

Do not perform broad docs rewrites.
