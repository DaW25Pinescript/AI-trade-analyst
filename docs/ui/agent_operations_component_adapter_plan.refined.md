# AI Trade Analyst — Agent Operations Workspace
## Component + Adapter Plan

**Target:** exact match to the latest hierarchical mockup (**GOVERNANCE LAYER** → **OFFICER LAYER** → **PERSONA / DEPARTMENT GRID** with 4 framed department boxes, right **Selected Node Detail** sidebar, and bottom **Activity / Event Stream** ribbon)

---

## 1. Implementation posture

This workspace should be rebuilt as a **state-driven frontend surface**, not ported as a DOM-manipulating HTML page.

Use:
- React + TypeScript
- Tailwind styling
- one adapter layer between raw API responses and UI components
- schema-faithful data merging:
  - `/ops/agent-roster`
  - `/ops/agent-health`
  - `/runs/{run_id}/agent-trace` (Run mode only)
  - `/ops/agent-detail/{entity_id}` (detail sidebar on demand)

Do **not**:
- keep one merged demo `agents[]` array
- use inline `onclick`
- infer relationships from visual position only
- collapse `run_state` and `health_state` into one field
- let presentation colors come from backend hex values

---

## 2. Recommended file structure

```text
app/
  workspaces/
    agent-operations/
      page.tsx
      AgentOperationsWorkspace.tsx
      components/
        WorkspaceToolbar.tsx
        LayerSection.tsx
        DepartmentBoxes.tsx
        DepartmentBox.tsx
        AgentCard.tsx
        AgentDetailPanel.tsx
        ActivityStream.tsx
        RelationshipArrows.tsx
        EmptyState.tsx
        LoadingState.tsx
        ErrorState.tsx
      hooks/
        useAgentRoster.ts
        useAgentHealth.ts
        useRunAgentTrace.ts
        useAgentDetail.ts
      adapters/
        mapRoster.ts
        mapHealth.ts
        mapTrace.ts
        mergeWorkspaceEntities.ts
        deriveVisualState.ts
      types/
        agentOperations.ts
      utils/
        filters.ts
        status.ts
        layout.ts
```

---

## 3. Component model — Aligned to the mockup

### 3.1 Top-level page

### `AgentOperationsWorkspace.tsx`
Responsible for:
- loading workspace mode state (`org | run | health`)
- loading selected `runId`
- coordinating roster + health + optional trace
- applying filters (`all | active | degraded | participated`)
- tracking selected entity for sidebar
- passing normalized view model to child components

This component should be the only place that knows how the workspace is composed.

---

### 3.2 Toolbar

### `WorkspaceToolbar.tsx`
Props:
```ts
type WorkspaceToolbarProps = {
  environment: string
  runId?: string
  instrument?: string
  mode: WorkspaceMode
  onModeChange: (mode: WorkspaceMode) => void
  filter: WorkspaceFilter
  onFilterChange: (filter: WorkspaceFilter) => void
  freshnessSummary?: string
}
```

Responsibilities:
- environment badge
- run ID display
- instrument/mode metadata
- mode switch (`Org`, `Run`, `Health`)
- filter switch
- freshness summary

This should visually mirror the exact toolbar pills from the mockup.

---

### 3.3 LayerSection.tsx

Supports the exact top layer titles from the mockup.

```ts
type LayerSectionProps = {
  title: "GOVERNANCE LAYER" | "OFFICER LAYER"
  children: React.ReactNode
  showArrow?: boolean
}
```

Responsibilities:
- render the section title in all caps
- render the 2-card row layout for governance/officer cards
- optionally render a connecting arrow / line to the next layer

---

### 3.4 DepartmentBoxes.tsx

Replaces the earlier generic department grid.

```ts
type DepartmentBoxesProps = {
  departments: {
    TECHNICAL_ANALYSIS: WorkspaceEntityViewModel[]
    RISK_CHALLENGE: WorkspaceEntityViewModel[]
    REVIEW_GOVERNANCE: WorkspaceEntityViewModel[]
    INFRA_HEALTH: WorkspaceEntityViewModel[]
  }
  onSelectEntity: (id: string) => void
  selectedEntityId?: string
}
```

Responsibilities:
- render the parent title **PERSONA / DEPARTMENT GRID**
- render exactly four framed boxes
- preserve visual ordering:
  1. Technical Analysis
  2. Risk / Challenge
  3. Review / Governance
  4. Infra / Health
- render department cards in compact layout (2-column where appropriate)

---

### 3.5 DepartmentBox.tsx

One framed department box.

```ts
type DepartmentBoxProps = {
  title: "TECHNICAL ANALYSIS" | "RISK / CHALLENGE" | "REVIEW / GOVERNANCE" | "INFRA / HEALTH"
  entities: WorkspaceEntityViewModel[]
  onSelectEntity: (id: string) => void
  selectedEntityId?: string
}
```

Responsibilities:
- render framed box with all-caps title
- render teal orb accent beside title
- lay out cards in 2-column compact presentation where count allows
- preserve the clean, boxed “business unit” look from the mockup

---

### 3.6 AgentCard.tsx

Main reusable card for any entity.

```ts
type AgentCardProps = {
  entity: WorkspaceEntityViewModel
  selected?: boolean
  onClick: (entityId: string) => void
  compact?: boolean
}
```

Rendering rules:
- flat dark card with subtle border
- 1px cyan hover border
- metallic robot / icon avatar on the left, selected via `visualFamily`
- small glowing orb top-right driven by `orbColor` + `healthState`
- display name, role, tags, and last active timestamp
- compact spacing when rendered inside department boxes

Important:
- do not collapse health and lifecycle into one label
- orb is a health / emphasis token, not the only state indicator
- influence overlays appear only in Run mode

---

### 3.7 RelationshipArrows.tsx

New dedicated SVG hierarchy-line renderer.

```ts
type RelationshipArrowsProps = {
  relationships: AgentRelationship[]
  highlightedEntityId?: string
  traceEdges?: LineageEdgeViewModel[]
}
```

Responsibilities:
- draw governance → officer arrows
- draw officer → department arrows
- highlight selected relationships
- optionally overlay Run mode lineage edges

The arrows must be driven by backend relationships and frontend layout coordinates, not hardcoded assumptions.

---

### 3.8 AgentDetailPanel.tsx

Powers the exact right sidebar titled **Selected Node Detail**.

```ts
type AgentDetailPanelProps = {
  entity?: WorkspaceEntityViewModel
  detail?: AgentDetailResponse | null
  loading?: boolean
  error?: string | null
  mode: WorkspaceMode
  onClose: () => void
}
```

Sections:
- identity
- purpose
- health state
- run state
- recent events
- influence history
- dependency info
- last error
- run-specific contribution block (when trace exists)

---

### 3.9 ActivityStream.tsx

Bottom ribbon component titled **Activity / Event Stream**.

```ts
type ActivityStreamProps = {
  events: WorkspaceEventViewModel[]
}
```

Responsibilities:
- render compact event rows
- emphasize failure / recovery / override events
- support later migration to richer event feeds without changing the outer layout

---

## 4. Contract-facing TypeScript types

Use strict types matching the refined schema.

```ts
export type WorkspaceMode = "org" | "run" | "health"
export type WorkspaceFilter = "all" | "active" | "degraded" | "participated"

export type HealthState =
  | "live"
  | "stale"
  | "degraded"
  | "unavailable"
  | "recovered"

export type RunState =
  | "idle"
  | "running"
  | "completed"
  | "failed"

export type RelationshipType =
  | "supports"
  | "challenges"
  | "feeds"
  | "synthesizes"
  | "overrides"
  | "degraded_dependency"
  | "recovered_dependency"

export type ContributionType =
  | "directional"
  | "cautionary"
  | "veto"
  | "supporting"
  | "infrastructure"

export type FinalBiasAlignment =
  | "aligned"
  | "partial"
  | "opposed"

export type VisualFamily =
  | "governance"
  | "officer"
  | "technical"
  | "risk"
  | "review"
  | "infra"

export type OrbColor = "teal" | "amber" | "red"
```

Then mirror the API contracts:

```ts
export type ResponseMeta = {
  version: string
  generated_at: string
  data_state: "live" | "stale" | "unavailable"
  source_of_truth?: string
}

export type AgentSummary = {
  id: string
  display_name: string
  type: "persona" | "officer" | "arbiter" | "subsystem"
  department: string
  role: string
  capabilities: string[]
  supports_verdict: boolean
  initials?: string
  visual_family: VisualFamily
  orb_color: OrbColor
}

export type AgentRelationship = {
  from: string
  to: string
  type: RelationshipType
}

export type AgentRosterResponse = ResponseMeta & {
  governance_layer: [AgentSummary, AgentSummary]
  officer_layer: [AgentSummary, AgentSummary]
  departments: {
    TECHNICAL_ANALYSIS: AgentSummary[]
    RISK_CHALLENGE: AgentSummary[]
    REVIEW_GOVERNANCE: AgentSummary[]
    INFRA_HEALTH: AgentSummary[]
  }
  relationships: AgentRelationship[]
}

export type AgentHealthItem = {
  entity_id: string
  run_state: RunState
  health_state: HealthState
  last_active_at?: string
  last_run_id?: string
  health_summary?: string
  recent_event_summary?: string
}

export type AgentHealthSnapshotResponse = ResponseMeta & {
  entities: AgentHealthItem[]
}

export type RunParticipant = {
  entity_id: string
  participated: boolean
  contribution_type: ContributionType
  influence_level?: number
  final_bias_alignment?: FinalBiasAlignment
  last_error?: string | null
  recovered_after_failure?: boolean
}

export type LineageEdge = {
  from: string
  to: string
  type: RelationshipType
  timestamp?: string
}

export type RunAgentTraceResponse = ResponseMeta & {
  run_id: string
  trace_state: "complete" | "partial" | "unavailable"
  participants: RunParticipant[]
  lineage_edges: LineageEdge[]
  arbiter_override: boolean
}
```

---

## 5. View-model layer

Raw contract models should not go directly into components.

```ts
export type WorkspaceEntityViewModel = {
  id: string
  displayName: string
  role: string
  type: AgentSummary["type"]
  department: string
  visualFamily: VisualFamily
  orbColor: OrbColor
  capabilities: string[]
  supportsVerdict: boolean

  healthState: HealthState | null
  runState: RunState | null

  lastActiveAt?: string
  lastRunId?: string
  healthSummary?: string
  recentEventSummary?: string

  participatedInRun: boolean
  contributionType?: ContributionType
  influenceLevel?: number
  finalBiasAlignment?: FinalBiasAlignment
  recoveredAfterFailure?: boolean
  lastError?: string | null
}
```

All rendered cards should use this shape.

---

## 6. Adapter plan — Updated to the mockup hierarchy

### 6.1 `mapRoster.ts`
Responsibilities:
- preserve `governance_layer`
- preserve `officer_layer`
- preserve the exact four department keys
- normalize relationships
- create initial `WorkspaceEntityViewModel` objects with no health/trace attached

### 6.2 `mapHealth.ts`
Responsibilities:
- normalize `AgentHealthSnapshotResponse.entities` by `entity_id`
- expose response metadata (`data_state`, `generated_at`)

### 6.3 `mapTrace.ts`
Responsibilities:
- normalize `RunAgentTraceResponse.participants` by `entity_id`
- normalize lineage edges
- expose `trace_state` and `arbiter_override`

### 6.4 `mergeWorkspaceEntities.ts`
Responsibilities:
- merge roster entities with health and optional trace by ID
- group entities into the exact four department keys
- preserve governance and officer card order
- preserve explicit relationship list
- attach semantic visual tokens (`visualFamily`, `orbColor`)
- return:
  - `governanceLayer`
  - `officerLayer`
  - `departments`
  - `relationships`
  - `traceEdges`
  - `meta`

### 6.5 `deriveVisualState.ts`
Responsibilities:
- map `visualFamily` to the metallic avatar/icon system
- map `healthState` to orb and badge styling
- map `runState` to state chips
- derive freshness summary text
- derive compact department-card layout rules

Recommended helper:

```ts
function getOrbColor(entity: WorkspaceEntityViewModel): OrbColor {
  if (entity.healthState === "unavailable") return "red"
  if (entity.healthState === "degraded" || entity.healthState === "stale") return "amber"
  return entity.orbColor ?? "teal"
}
```

---

## 7. Data flow by mode

### Org mode
Fetch:
- `/ops/agent-roster`
- `/ops/agent-health`

Render:
- **GOVERNANCE LAYER**
- **OFFICER LAYER**
- **PERSONA / DEPARTMENT GRID**
- all hierarchy arrows
- teal/amber/red orbs based on `healthState`

### Run mode
Fetch:
- `/ops/agent-roster`
- `/ops/agent-health`
- `/runs/{run_id}/agent-trace`

Render:
- same layout as Org mode
- participant highlighting
- influence values on cards or detail panel
- lineage edge overlay
- arbiter override banner when true

### Health mode
Fetch:
- `/ops/agent-roster`
- `/ops/agent-health`

Render:
- same layout
- problem entities emphasized first within departments
- stronger degraded/stale/unavailable signaling
- event stream focused on failures and recoveries

---

## 8. Hook plan

### `useAgentRoster()`
Returns:
```ts
{
  data?: AgentRosterResponse
  isLoading: boolean
  error?: string
}
```

### `useAgentHealth()`
Returns:
```ts
{
  data?: AgentHealthSnapshotResponse
  isLoading: boolean
  error?: string
  refetch: () => void
}
```

### `useRunAgentTrace(runId?: string)`
Behavior:
- disabled when no `runId`
- no request in Org or Health mode unless a run is pinned

### `useAgentDetail(entityId?: string)`
Behavior:
- lazy fetch on sidebar selection
- cache by entity ID
- do not preload every detail in MVP

---

## 9. Mode-aware composition plan

```tsx
<AgentOperationsWorkspace>
  <WorkspaceToolbar />

  <LayerSection title="GOVERNANCE LAYER">
    {governanceCards}
  </LayerSection>

  <LayerSection title="OFFICER LAYER" showArrow>
    {officerCards}
  </LayerSection>

  <DepartmentBoxes departments={workspace.departments} />

  <AgentDetailPanel />

  <ActivityStream />
</AgentOperationsWorkspace>
```

The page component decides:
- current mode
- selected run
- selected entity
- filtered entities
- which relationships and trace edges to pass into `RelationshipArrows`

---

## 10. Filtering and sorting rules

### Filter rules
- `all` → all entities
- `active` → entities with:
  - `runState === "running"` or
  - `participatedInRun === true` or
  - `lastActiveAt` within recent threshold
- `degraded` → entities where:
  - `healthState === "degraded"` or
  - `healthState === "stale"` or
  - `healthState === "unavailable"`
- `participated` → run participants only

### Sort rules
Health mode:
1. unavailable
2. degraded
3. stale
4. recovered
5. live
6. idle/completed non-problem entities

Run mode:
1. governance entities
2. participating entities by influence descending
3. supporting officers
4. non-participants dimmed

Department boxes should preserve their outer order even when internal entities are re-sorted.

---

## 11. Status rendering rules

Do not render one generic dot for everything.

Each card should support:
- orb indicator (health emphasis)
- health badge
- run/lifecycle badge
- optional participation chip in Run mode
- optional influence display in Run mode

The detail panel should always show both health and run state explicitly.

---

## 12. Error-state plan

### Collection-level errors
- roster failure → workspace-level blocking error
- health failure with roster success → render structure with degraded global banner
- trace failure in Run mode → keep workspace usable, show trace-unavailable banner

### Detail errors
- detail fetch failure → keep sidebar open with structured error state
- 404 entity → show `AGENT_NOT_FOUND`
- no detail payload → show summary-only fallback from merged entity view model

### Data-state handling
- `data_state: stale` → workspace remains readable with stale banner
- `data_state: unavailable` on health → do not fabricate healthy cards

---

## 13. Relationship rendering plan

### Base relationships
From roster:
- used in Org and Health modes
- drives governance → officer arrows
- drives officer → department arrows

### Trace edges
From run trace:
- used in Run mode only
- overlays on top of base relationships
- highlight supports/challenges/overrides/degraded_dependency/recovered_dependency

The frontend must not infer relationship lines from layout alone.

---

## 14. Activity / Event Stream plan

For MVP, derive events from:
- `recent_event_summary`
- `health_summary`
- detail `error_log`
- `arbiter_override`
- trace recovery markers

View model:

```ts
type WorkspaceEventViewModel = {
  timestamp?: string
  entityId?: string
  entityName?: string
  severity: "info" | "warning" | "error" | "recovery"
  text: string
}
```

This component should remain visually identical even if a dedicated event endpoint is added later.

---

## 15. Migration plan from the HTML prototype

### Keep
- dark control-room aesthetic
- exact toolbar concept
- governance / officer / department hierarchy
- right **Selected Node Detail** sidebar
- bottom **Activity / Event Stream** ribbon
- hover/select interaction model

### Replace
- one merged `agents` array → adapter-based contract data
- inline handlers → state-driven React handlers
- text-based demo filters → data-backed filtering
- emoji avatars → semantic avatar mapping from `visualFamily`
- single `status` field → split `healthState` + `runState`
- hardcoded detail text → trace/detail-backed content

---

## 16. Minimal implementation phases

### Phase A — Schema-faithful shell
Deliver:
- roster + health fetch
- merged entity adapter
- Org mode
- LayerSection + DepartmentBoxes rendering
- Selected Node Detail sidebar
- basic filters

### Phase B — Run overlay
Deliver:
- run trace fetch
- Run mode
- participant highlighting
- influence values
- arbiter override banner
- trace edge overlay

### Phase C — Health emphasis
Deliver:
- Health mode
- degraded/stale/unavailable emphasis
- stronger event stream
- problem-first entity sorting inside department boxes

### Phase D — Detail richness
Deliver:
- full detail fetch
- dependency panels
- influence history
- last error list

---

## 17. Implementation constraints

- keep all API-specific logic in `hooks/` and `adapters/`
- keep components unaware of raw response envelopes
- treat roster as structural source-of-truth
- treat health as mutable snapshot layer
- treat run trace as optional mode-specific overlay
- keep SVG arrow rendering isolated from card layout logic
- do not allow the frontend to invent layer placement or arrow relationships

---

## 18. Example top-level container skeleton

```tsx
export function AgentOperationsWorkspacePage() {
  const [mode, setMode] = useState<WorkspaceMode>("org")
  const [filter, setFilter] = useState<WorkspaceFilter>("all")
  const [selectedEntityId, setSelectedEntityId] = useState<string | undefined>()
  const [runId, setRunId] = useState<string | undefined>()

  const roster = useAgentRoster()
  const health = useAgentHealth()
  const trace = useRunAgentTrace(mode === "run" ? runId : undefined)
  const detail = useAgentDetail(selectedEntityId)

  const workspace = useMemo(() => {
    if (!roster.data) return null
    return mergeWorkspaceEntities({
      roster: roster.data,
      health: health.data ?? null,
      trace: trace.data ?? null,
    })
  }, [roster.data, health.data, trace.data])

  if (roster.isLoading) return <LoadingState />
  if (roster.error || !workspace) return <ErrorState title="Agent Operations unavailable" />

  return (
    <AgentOperationsWorkspaceShell>
      <WorkspaceToolbar
        mode={mode}
        onModeChange={setMode}
        filter={filter}
        onFilterChange={setFilter}
        runId={runId}
      />

      <RelationshipArrows
        relationships={workspace.relationships}
        traceEdges={workspace.traceEdges}
        highlightedEntityId={selectedEntityId}
      />

      <LayerSection title="GOVERNANCE LAYER">
        {workspace.governanceLayer.map((entity) => (
          <AgentCard key={entity.id} entity={entity} onClick={setSelectedEntityId} />
        ))}
      </LayerSection>

      <LayerSection title="OFFICER LAYER" showArrow>
        {workspace.officerLayer.map((entity) => (
          <AgentCard key={entity.id} entity={entity} onClick={setSelectedEntityId} />
        ))}
      </LayerSection>

      <DepartmentBoxes
        departments={workspace.departments}
        onSelectEntity={setSelectedEntityId}
        selectedEntityId={selectedEntityId}
      />

      <AgentDetailPanel
        entity={workspace.entityMap[selectedEntityId ?? ""]}
        detail={detail.data}
        loading={detail.isLoading}
        error={detail.error}
        mode={mode}
        onClose={() => setSelectedEntityId(undefined)}
      />

      <ActivityStream events={workspace.events} />
    </AgentOperationsWorkspaceShell>
  )
}
```

---

## 19. Final recommendation

Do not port the HTML directly.

Use it as:
- visual direction
- spacing and hierarchy reference
- interaction reference

Then build the real workspace around:
- typed contracts
- adapter-based data merging
- exact layer and department structure
- SVG relationship arrows
- strict health vs lifecycle state semantics

That gives AI Trade Analyst a native Agent Operations Workspace that matches the approved mockup **and** remains contract-faithful.
