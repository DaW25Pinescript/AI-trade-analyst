# CONTRACTS — PR-OPS-3

## Contract source of truth
This PR must follow:

- `docs/ui/AGENT_OPS_CONTRACT.md`
- `docs/ui/UI_CONTRACT.md`

Do not redefine backend semantics in the UI layer.

## Endpoints used

### 1) `GET /ops/agent-roster`
The workspace must consume the contracted `AgentRosterResponse`.

The UI should assume the response includes:

- `meta`
- `governance_layer`
- `officer_layer`
- `departments`
- `relationships`

The UI must preserve the hierarchy encoded by these fields rather than flattening everything into a single undifferentiated list.

### 2) `GET /ops/agent-health`
The workspace must consume the contracted `AgentHealthSnapshotResponse`.

The UI should assume the response includes:

- `meta`
- `entities`
- poll-based snapshot semantics
- separate `run_state` and `health_state`

The UI must not collapse `run_state` and `health_state` into a single invented status label.

## Join rule
`AgentHealthItem.entity_id` must join against `AgentSummary.id` from the roster contract.

UI behavior rules:

- if a roster entity has no matching health item, show it as **no health data yet** / unavailable according to the contract semantics
- if the health query fails entirely but roster succeeds, render the structure and show a degraded banner
- do not render health items that have no valid roster join as standalone entities

## Required states

### Roster query
Must handle:

- loading
- success
- error

Roster-empty is invalid per contract and should be treated as an error/degraded contract violation rather than a normal empty state.

### Health query
Must handle:

- loading
- success with entities
- success with empty entities (fresh start)
- error

Health-empty is valid on fresh start and should not block the roster view.

## MVP UI contract
The Agent Ops MVP should include, at minimum:

1. workspace page/screen for `/ops`
2. top-level summary / trust region
3. visible hierarchy:
   - governance layer
   - officer layer
   - departments
4. entity cards/nodes with health indication
5. relationship visibility
6. selected-node detail panel or equivalent detail surface
7. degraded-state banner when roster succeeds but health fails

## Allowed new frontend abstractions
This PR may introduce:

- `ui/src/shared/api/ops.ts`
- `ui/src/shared/hooks/useAgentRoster.ts`
- `ui/src/shared/hooks/useAgentHealth.ts`
- `ui/src/workspaces/ops/adapters/*`
- `ui/src/workspaces/ops/components/*`

## Disallowed contract expansion
This PR must not assume or add fields for:

- run event streams
- trace nodes
- timeline events
- detail endpoint payloads
- control actions
- mutable settings

## Mode switch (MVP limitation)
The workspace toolbar should show mode pills (Org / Run / Health) but only **Org** is functional in this PR.

- Org: active, renders the roster+health view
- Run: visually disabled, tooltip: "Requires run trace endpoint (Phase 7)"
- Health: visually disabled, tooltip: "Requires run trace endpoint (Phase 7)"

Showing disabled modes communicates future capability without pretending the modes work. Do not hide them.

## Visual direction
The workspace should follow the dark control-room aesthetic established in the HTML prototype (`operations.html`). Key visual tokens:

- Dark background (`bg-zinc-950` or similar)
- Teal orb = `health_state: "live"` or `"recovered"`
- Amber orb = `health_state: "stale"` or `"degraded"`
- Red orb = `health_state: "unavailable"`
- Cyan hover accent on clickable card surfaces
- All-caps section titles for GOVERNANCE LAYER, OFFICER LAYER, department names
- Framed department boxes (subtle border, grouped cards inside)
- Sidebar or panel for selected-node detail

These are visual targets, not pixel-perfect requirements. Functional correctness matters more than aesthetics.

## Polling
Health is a poll-based snapshot, not a stream.

The UI may use a modest polling interval for health, for example 15–30 seconds, but must not introduce SSE/WebSocket behavior.

Roster should usually be treated as relatively stable and may be fetched on mount/refocus with a much lower refresh cadence.
