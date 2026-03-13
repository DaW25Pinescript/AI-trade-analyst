# ACCEPTANCE TESTS — PR-OPS-3

## Merge criteria
PR-OPS-3 is complete only if all of the following are true.

### A. Route and render
- [ ] The `/ops` React route no longer renders a placeholder.
- [ ] The route renders a real Agent Operations workspace.
- [ ] The workspace consumes live data from `GET /ops/agent-roster` and `GET /ops/agent-health`.

### B. Hierarchy integrity
- [ ] Governance layer is visibly rendered.
- [ ] Officer layer is visibly rendered.
- [ ] Department groupings are visibly rendered.
- [ ] Relationships from the roster contract are represented or listed in the UI.
- [ ] The UI preserves the contracted structure instead of flattening all entities into a single generic list.

### C. Entity rendering
- [ ] Every rendered entity originates from the roster response.
- [ ] Health data is joined onto roster entities by `entity_id ↔ id`.
- [ ] Entities without matching health data are rendered with an honest unavailable / no-health-yet state.
- [ ] Unknown health-only entities are not rendered as standalone cards.

### D. Required state handling
- [ ] Loading state is rendered while roster/health are pending.
- [ ] Healthy success state renders roster + health.
- [ ] Roster success + health failure renders structure plus a degraded banner.
- [ ] Roster success + empty health entities renders structure without treating it as an error.
- [ ] Roster failure renders an error state.
- [ ] Contract-invalid roster-empty is not treated as a benign empty state.

### E. Selection/detail behavior
- [ ] Clicking or selecting an entity updates a detail surface.
- [ ] The detail surface renders only data available from roster + health.
- [ ] The detail surface does not pretend to show run-trace/detail-endpoint information that is not available yet.

### F. Scope discipline
- [ ] No trace endpoint is called.
- [ ] No detail endpoint is called.
- [ ] No backend files are changed.
- [ ] No control-plane actions exist in the UI.
- [ ] No SSE/WebSocket/live-stream implementation exists.

### G. Reuse and structure
- [ ] Existing shared components are reused where appropriate.
- [ ] Ops-specific components live under the workspace and are not pushed into shared prematurely.
- [ ] API / hooks / adapters / route concerns are separated cleanly.

### H. Verification
- [ ] `npm run typecheck` passes.
- [ ] `npm run build` passes.
- [ ] `npm run test` passes.
- [ ] New tests cover healthy, degraded, and error flows with explicit assertions.

## Suggested test cases

### 1. Healthy render
Fixture:
- roster success
- health success with matching entities

Assert:
- governance, officer, and department sections are visible
- entity health states render
- selected entity panel works

### 2. Degraded health
Fixture:
- roster success
- health request fails

Assert:
- structure still renders
- degraded banner appears
- no fake fallback data is injected

### 3. Fresh start / empty health
Fixture:
- roster success
- health success with empty `entities`

Assert:
- structure renders
- entity cards indicate no health data yet / unavailable
- no error state shown solely due to empty health entities

### 4. Roster error
Fixture:
- roster fails

Assert:
- route shows error state
- structure does not pretend to render valid data

### 5. Join safety
Fixture:
- health contains one valid entity and one unknown `entity_id`

Assert:
- unknown health-only item is ignored for rendering
- valid join renders on the correct roster entity

### 6. Scope guard
Assert:
- UI code imports only roster + health hooks/clients for this workspace
- no trace/detail client is introduced
