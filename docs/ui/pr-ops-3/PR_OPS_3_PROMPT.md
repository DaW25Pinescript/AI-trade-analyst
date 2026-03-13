# PR-OPS-3 IMPLEMENTATION PROMPT

Implement **PR-OPS-3 — Agent Operations React Workspace MVP** for the AI Trade Analyst repo.

## Mission
Replace the existing `/ops` placeholder route in the React UI with a real **Agent Operations** workspace that consumes the live backend endpoints delivered in PR-OPS-2:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

This is the first frontend slice of Agent Operations. It is an **operator observability / explainability / trust workspace**, not a control panel and not a trace-forensics screen.

The north-star question is:

> **Why should I trust this system right now?**

The MVP must answer that question using current roster structure, current health snapshot, honest degraded-state handling, and selected-node detail.

## Hard scope
Build **Org / Structure mode only**.

Required outcomes:

- `/ops` route renders a real workspace
- live roster and health data are fetched
- governance layer, officer layer, departments, and relationships are visible
- entity selection opens/shows a detail surface
- degraded roster-success / health-failure state is handled honestly
- fresh-start empty-health state is handled honestly

## Do not implement
Do **not** add or consume:

- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`
- event timelines
- run forensics
- prompt editing
- model switching
- orchestration / retry / restart controls
- SSE / WebSocket / live stream behavior
- backend changes

## Source-of-truth docs
Follow these documents exactly:

- `docs/ui/AGENT_OPS_CONTRACT.md`
- `docs/ui/UI_CONTRACT.md`

Do not invent new backend semantics.

## Technical direction

### API / hooks
Add typed frontend API + hooks for:

- `fetchAgentRoster()`
- `fetchAgentHealth()`
- `useAgentRoster()`
- `useAgentHealth()`

Use the existing `apiFetch<T>` wrapper.

### View-model / adapter layer
Add a deterministic Ops adapter that:

- joins health onto roster by `entity_id ↔ id`
- preserves hierarchy and department structure
- derives small UI summaries only where clearly justified
- ignores unknown health-only entities for rendering
- marks missing-health roster entities as unavailable / no-health-yet

### UI structure
Implement a workspace layout that includes:

1. summary / trust region
2. governance layer section
3. officer layer section
4. department sections
5. entity cards/nodes with health indication
6. selected-node detail panel
7. degraded banner when roster succeeds but health fails

Reuse the existing shared component foundation where appropriate, but keep Ops-specific rendering inside `ui/src/workspaces/ops/`.

### Suggested file shape
Use a clean separation similar to:

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

Exact names may vary, but maintain clear boundaries between API, hooks, adapters, components, and route.

## Required state handling
Support these truthfully:

- loading
- healthy success
- roster success + health failure
- roster success + empty health entities
- roster failure
- join mismatch safety

Do not inject fake demo fallback data.

## Mode switch
Show Org / Run / Health mode pills in the toolbar. Only **Org** is functional. Run and Health pills should be visually disabled with a tooltip: "Requires run trace endpoint (Phase 7)". Do not hide them.

## Visual direction
Dark control-room aesthetic. Key tokens:
- Teal orb = live/recovered, amber orb = stale/degraded, red orb = unavailable
- Cyan hover accent on clickable cards
- All-caps layer/department section titles
- Framed department boxes with subtle borders
- Reference `operations.html` for tone; build from the component plan, not a port

Functional correctness over pixel-perfect styling.

## Testing requirements
Add explicit frontend tests for:

- healthy render
- degraded health state
- fresh-start empty health state
- roster error state
- entity selection detail behavior
- join safety / unknown health-only item ignored
- route render

No snapshots. Use explicit assertions.

## Completion checklist
Before finishing, ensure:

- `npm run typecheck` passes
- `npm run build` passes
- `npm run test` passes
- `/ops` renders live roster + health
- no backend files changed
- no future forensic features were smuggled in

## Documentation closure
Update only what is necessary to mark PR-OPS-3 complete, such as:

- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Keep doc edits minimal and factual.
