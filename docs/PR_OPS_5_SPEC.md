# PR-OPS-5 — Agent Ops Frontend Wiring (Run Mode + Health Mode + Detail Sidebar)

**Phase:** 7 (continued)
**Lane:** Operator / Observability
**Type:** Frontend-only
**Status:** ⏳ Spec drafted — implementation pending
**Date:** 2026-03-15
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Extends:** PR-OPS-3 (workspace shell), `docs/ui/AGENT_OPS_CONTRACT.md` (all four endpoints now contracted)
**Depends on:** PR-OPS-3 (workspace shell ✅), PR-OPS-4a (trace backend ✅), PR-OPS-4b (detail backend ✅)
**Blocks:** Nothing at the phase level — this completes the Phase 7 Agent Ops read-side stack
**Implementation split:** PR-OPS-5a (types + adapters + Health mode) then PR-OPS-5b (Run mode + Detail sidebar). 5b depends on 5a baseline.

---

## 1. Objective

Wire the existing React Agent Ops workspace to the now-stable backend observability surface.

PR-OPS-5 consumes these read-only endpoints:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`
- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`

This PR enables:

- **Org mode** (existing roster/health view, preserved and tightened)
- **Health mode** (operator health-focused workspace lens)
- **Run mode** (trace-driven view for a selected run)
- **Selected Node Detail** sidebar backed by the detail endpoint
- **Trace visualization** using conservative trace edges and ordered stages

This PR is **frontend-only**. No backend contract changes are allowed.

**Moves the system:**
- **FROM →** Workspace shell with live roster + health but disabled Run/Health modes; four backend endpoints live (197 tests) but trace and detail unconsumed
- **TO →** Fully wired workspace: Org mode preserved, Health mode shows operator-attention view, Run mode shows trace visualization, Detail sidebar shows typed entity deep-dive

---

## 2. Why this PR exists

PR-OPS-3 shipped the first Agent Ops MVP: live roster, live health, operator shell, selected-node panel, mode pills with Run/Health disabled. PR-OPS-4 delivered the missing backend projections: agent-trace for run observability, agent-detail for entity drilldown.

| Endpoint | Backend PR | Tests | Status |
|----------|-----------|-------|--------|
| `GET /ops/agent-roster` | PR-OPS-2 | 55 (shared) | ✅ Live |
| `GET /ops/agent-health` | PR-OPS-2 | 55 (shared) | ✅ Live |
| `GET /runs/{run_id}/agent-trace` | PR-OPS-4a | 70 | ✅ Live |
| `GET /ops/agent-detail/{entity_id}` | PR-OPS-4b | 72 | ✅ Live |

| Without PR-OPS-5 | With PR-OPS-5 |
|-------------------|---------------|
| Run mode disabled | Run mode shows ordered trace, participants, arbiter summary |
| Health mode shallow | Health mode elevates degraded/stale entities with operator attention |
| Detail sidebar shows roster summary only | Detail sidebar shows typed backend-backed entity deep-dive |
| Trace endpoint invisible in UI | Full trace visualization with stage timeline and edge overlay |

---

## 3. Governance / sequencing rule

PR-OPS-5 must treat the backend contract as **locked**. The contract surface: flat ResponseMeta pattern, plain stable entity IDs, entity_type discriminated detail, conservative trace edges, response-level data_state, graceful degradation semantics.

If a frontend integration mismatch is found, log it as debt; do **not** silently redefine the backend contract.

---

## 4. Non-goals

1. No backend changes
2. No endpoint contract edits
3. No polling model changes (no SSE / WebSocket / streaming)
4. No control-plane actions (retry, toggle, enable/disable, mutate config)
5. No prompt editing or "chat with agent" interactions
6. No artifact inspector for raw JSON blobs
7. No new workspace route — work stays inside `/ops`
8. No speculative analytics layer
9. No redesign of Org mode beyond consistency needs
10. No new frontend persistence beyond normal query cache
11. No trace semantics invented beyond what backend exposes
12. No Phase 6 core product lane changes

This PR is a **wiring + rendering** pass, not a product redesign.

---

## 5. Backend contract dependencies

### 5.1 Contract references

All four endpoints are contracted in `AGENT_OPS_CONTRACT.md` (§4–§7) following the PR-OPS-4b §6 promotion. This is the single canonical contract source for frontend wiring.

| Endpoint | Contract section |
|----------|-----------------|
| `GET /ops/agent-roster` | `AGENT_OPS_CONTRACT.md` §4 |
| `GET /ops/agent-health` | `AGENT_OPS_CONTRACT.md` §5 |
| `GET /runs/{run_id}/agent-trace` | `AGENT_OPS_CONTRACT.md` §6 |
| `GET /ops/agent-detail/{entity_id}` | `AGENT_OPS_CONTRACT.md` §7 |

`PR_OPS_4_SPEC_FINAL.md` §6–§7 remain as design-level reference for trace and detail implementation intent, but `AGENT_OPS_CONTRACT.md` is the controlling contract for response shapes.

### 5.2 Contract assumptions the frontend must preserve

- Flat response shape — not data/meta
- data_state always respected
- entity_id stays plain/stable — do not infer type from ID
- entity_type drives detail rendering
- trace_edges are conservative run-scoped relationships, not a causal reasoning graph
- Missing detail/health should degrade visibly, not crash the workspace

### 5.3 TypeScript types to define

All types in a single shared file:

**Roster + health:** ResponseMeta, DepartmentKey, OpsError, OpsErrorEnvelope, AgentSummary, EntityRelationship, AgentRosterResponse, AgentHealthSnapshotResponse, AgentHealthItem

**Trace:** AgentTraceResponse, TraceSummary, TraceStage, TraceParticipant, ParticipantContribution, TraceEdge, ArbiterTraceSummary, ArtifactRef

**Detail:** AgentDetailResponse, EntityIdentity, EntityStatus, EntityDependency, RecentParticipation, PersonaDetail, OfficerDetail, ArbiterDetail, SubsystemDetail

### 5.4 Roster-health join rules (contract §5.10)

1. Every entity_id in health must map to a roster id — unknown health items discarded with console warning
2. Missing health for a known roster entity is valid — render card without health badges
3. Roster is structural source of truth — health augments but does not define hierarchy

### 5.5 Dual-layer edge rendering

Roster relationships (static architecture) and trace trace_edges (run-scoped) are distinct:
- Roster relationships: visible in Org/Health mode, persistent structural lines
- Trace edges: visible in Run mode only, overlaid for the selected run
- Distinct visual treatments — do not merge into a single edge layer

### 5.6 data_state rendering rules

| data_state | Roster | Health | Trace | Detail |
|------------|--------|--------|-------|--------|
| live | Normal render | Normal — merge with roster | Normal render | Normal render |
| stale | Stale warning banner | Stale banner — badges may lag | Stale indicator | Stale indicator on affected sections |
| unavailable | Workspace-level blocking error | Degraded banner — render roster without badges | Error — "trace unavailable" | Show entity card with "detail unavailable" |

---

## 6. User-facing outcome

Four operator questions, four answers:

1. **What entities exist?** → Org mode — structural view
2. **Why should I trust the system right now?** → Health mode — degraded/stale signals
3. **What happened in this run?** → Run mode — trace + participants + arbiter
4. **What is this thing I clicked on?** → Detail sidebar — typed entity deep-dive

---

## 7. Workspace architecture

### 7.1 Route
Existing `/ops` route. No new route.

### 7.2 View modes
Three internal modes: `org`, `health`, `run`. Mode pills exist from PR-OPS-3; this PR activates the remaining modes.

### 7.3 Core sections
Top summary/trust strip, mode switcher, primary canvas, selected node detail sidebar, run selector/context panel in Run mode.

### 7.4 Selection model

The workspace maintains:
- `selectedEntityId: string | null`
- `selectedMode: "org" | "health" | "run"`
- `selectedRunId: string | null`

Selection state stable across refetches. Mode change preserves selection unless invalid in new context.

---

## 8. Mode-by-mode behavior

### 8.1 Org mode
Structural/default view. Shows governance layer, officer layer, department boxes, relationship-driven hierarchy, health badges/orbs joined where available. Preserves PR-OPS-3 visual hierarchy.

### 8.2 Health mode
**Not a separate endpoint** — a frontend rendering mode composed from roster + health + detail on click. Emphasizes health_state, run_state, degraded/unavailable/recovered conditions. Recommended: elevate non-healthy entities, make stale/unavailable prominent, preserve selection + detail sidebar.

### 8.3 Run mode
Driven by selected run_id and GET /runs/{run_id}/agent-trace. Shows: run header (run_id, instrument, session, run_status, data_state), compact trace summary, ordered stage timeline (ascending stage_index, duration_ms), participant list with stance/confidence/contribution/override, conservative trace edges, arbiter summary panel, artifact references as compact labels.

---

## 9. Run selection strategy

### 9.1 Minimal requirement
Support providing a run_id manually or via known app navigation state.

### 9.2 Preferred v1 options
Any acceptable: query parameter (#/ops?run_id=...), lightweight paste field in Run mode, integration from Journey Studio run context.

### 9.3 Non-goal
Do not build a full run browser if no endpoint exists for it. Accept that Run mode requires an explicit run_id. Diagnostic should confirm what run context is already available.

---

## 10. Detail sidebar behavior

### 10.1 Trigger
Selecting entity card fetches GET /ops/agent-detail/{entity_id}.

### 10.2 Sidebar content
Common identity/status block, dependencies (upstream/downstream), recent participation (last 5), recent warnings, type-specific section by entity_type.

| entity_type | Variant | Key fields |
|-------------|---------|-----------|
| persona | PersonaDetail | analysis_focus, verdict_style, department_role, typical_outputs |
| officer | OfficerDetail | officer_domain, data_sources, monitored_surfaces, update_cadence |
| arbiter | ArbiterDetail | synthesis_method, veto_gates, quorum_rule, override_capable, policy_summary |
| subsystem | SubsystemDetail | subsystem_type, monitored_resources, health_check_method, runtime_role |

### 10.3 Discriminated rendering rule
Switch on `entity_type`. Do not infer type from `entity_id`. **UI discriminant is `entity_type`; `type_specific.variant` must never drive branch selection.** The variant tag exists as a contract consistency check only.

### 10.4 Degraded state
data_state stale → stale indicator. Health unavailable → degraded status section, rest normal. 404 → "entity not found". Fetch failure → show roster card with "detail unavailable".

### 10.5 Sidebar interactions
Close → return to mode view. Click dependency → navigate within sidebar. Click run_id → switch to Run mode (if supported).

---

## 11. Trace visualization rules

### 11.1 Stage timeline
Ordered by stage_index. Status-aware. duration_ms shown when present. Participant counts visible.

### 11.2 Participant rendering
Match roster display naming. Show entity_type, status, compact contribution summary, override indicator.

### 11.3 Edge rendering
Use backend from, to, type. Do not imply more certainty than contract provides. Tooltip may use summary. Types: considered_by_arbiter, skipped_before_arbiter, failed_before_arbiter, override.

### 11.4 Arbiter block
Render distinctly when present: override_applied, override_type, override_count, overridden entities, summary.

### 11.5 Missing/partial trace
Stale → stale indicator. Null arbiter → no arbiter block. Partial run → available stages + incomplete indicator. Sparse data → still render valid view. Unknown run_id → "run not found".

---

## 12. Frontend data layer

### 12.1 API functions
fetchAgentTrace(runId), fetchAgentDetail(entityId). Follow existing conventions. Roster/health fetch functions may already exist from PR-OPS-3.

### 12.2 Hooks
useAgentRoster(), useAgentHealth() (may exist), useAgentTrace(runId, enabled), useAgentDetail(entityId, enabled). All must handle data_state and parse OpsErrorEnvelope.

### 12.3 Query strategy
Roster: slower refresh. Health: shorter stale time. Trace: on-demand per run. Detail: on-demand per entity. Changing run_id/entity_id re-keys queries.

---

## 13. State handling matrix

| # | State | Behavior |
|---|-------|----------|
| 1 | Roster + health success | Normal full render |
| 2 | Roster + health degraded | Degraded health indicators |
| 3 | Roster failure | Workspace-level blocking error |
| 4 | Detail degraded | Sidebar with stale/degraded messaging |
| 5 | Detail 404 | "entity not found" in sidebar |
| 6 | Trace success | Run mode fully operational |
| 7 | Trace stale | Stale banner |
| 8 | Trace unavailable | Trace-unavailable without breaking workspace |
| 9 | Trace 404 | "run not found" message |
| 10 | Null arbiter summary | Render without arbiter block |
| 11 | Partial run | Available stages + incomplete indicator |
| 12 | Mode switching | Selection preserved unless invalid |

---

## 14. UI design rules

1. **Preserve visual identity** — dark control-room aesthetic from PR-OPS-3
2. **Trust indicators visible** — freshness, degraded state, current mode, run context
3. **Detail panel feels typed** — user can tell what entity type they selected
4. **No fake intelligence** — no fabricated influence intensity, causal certainty, or explanation beyond contract
5. **Trace remains operator-readable** — stage cards/timeline over ambitious graph visuals

---

## 15. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Framework | React |
| Workspace shell | PR-OPS-3 — structure TBC from diagnostic |
| Phase 6 patterns | Reuse hooks, adapters, state management |
| Backend URL | Verify in diagnostic — expected FastAPI port 8000, same-origin |
| UI port | Verify in diagnostic — expected 8080 |
| Existing hooks | Verify in diagnostic — PR-OPS-3 may already have roster/health hooks |
| Run context | Verify in diagnostic — Journey Studio integration or manual entry |

---

## 16. Key File Paths

All TBC from diagnostic — workspace shell, adapter pattern, hook pattern, types file, tests, API config.

---

## 17. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Roster wiring | Org mode renders live roster hierarchy | ⏳ Pending |
| AC-2 | Health wiring | Org/Health modes merge health data onto roster cards | ⏳ Pending |
| AC-3 | Roster-health join | Unknown health IDs discarded; missing health renders without badges | ⏳ Pending |
| AC-4 | Health degraded | Health failure → roster without badges + degraded banner | ⏳ Pending |
| AC-5 | Roster blocking | Roster failure → workspace-level blocking error | ⏳ Pending |
| AC-6 | Health mode active | Health mode enabled, elevates degraded/stale entities | ⏳ Pending |
| AC-7 | Relationship rendering | Org/Health modes render roster relationship lines | ⏳ Pending |
| AC-8 | Trace wiring | Run mode renders ordered stage timeline | ⏳ Pending |
| AC-9 | Participant cards | Participants render status and available contribution fields (stance/confidence/contribution/override when present) | ⏳ Pending |
| AC-10 | Trace edges | Trace edges with correct types | ⏳ Pending |
| AC-11 | Arbiter summary | Arbiter panel with override details | ⏳ Pending |
| AC-12 | Arbiter null | Null arbiter → panel hidden, no fabrication | ⏳ Pending |
| AC-13 | Trace not found | Invalid run_id → "run not found" | ⏳ Pending |
| AC-14 | Partial run | Partial → available stages + incomplete indicator | ⏳ Pending |
| AC-15 | Run selector | Mechanism to select run_id — not hardcoded | ⏳ Pending |
| AC-16 | Detail persona | Persona click → PersonaDetail fields | ⏳ Pending |
| AC-17 | Detail officer | Officer click → OfficerDetail fields | ⏳ Pending |
| AC-18 | Detail arbiter | Arbiter click → ArbiterDetail fields | ⏳ Pending |
| AC-19 | Detail subsystem | Subsystem click → SubsystemDetail fields | ⏳ Pending |
| AC-20 | Detail not found | Unknown entity_id → "entity not found" | ⏳ Pending |
| AC-21 | Detail degradation | Health unavailable → degraded status, rest normal | ⏳ Pending |
| AC-22 | data_state banners | Stale/unavailable renders appropriate banner | ⏳ Pending |
| AC-23 | Error envelope | OpsErrorEnvelope parsed, not generic error | ⏳ Pending |
| AC-24 | Typed adapters | Four adapters matching contract shapes | ⏳ Pending |
| AC-25 | No backend changes | Zero backend modifications | ⏳ Pending |
| AC-26 | Existing UI preserved | Phase 6 + PR-OPS-3 Org mode — zero regressions | ⏳ Pending |
| AC-27 | Mode switching | Selection preserved unless invalid in new context | ⏳ Pending |
| AC-28 | Build + typecheck | Build and typecheck pass | ⏳ Pending |

---

## 18. Recommended Split

| Sub-PR | Scope | ACs |
|--------|-------|-----|
| **PR-OPS-5a** | Types + adapters + hooks + Org mode preservation + Health mode wiring + relationships + data_state banners + error handling | AC-1–7, AC-22–24 (10 ACs) |
| **PR-OPS-5b** | Run mode + Detail sidebar + run selector + trace visualization | AC-8–21 (14 ACs) |
| **Shared gates** | Verified in both 5a and 5b | AC-25 (no backend changes), AC-26 (existing UI preserved), AC-27 (mode switching), AC-28 (build + typecheck) |

PR-OPS-5a lands first. 5b starts from 5a baseline. Shared gates are regression checks applied to both sub-PRs — not owned independently by either.

---

## 19. Pre-Code Diagnostic Protocol

**Do not implement until reviewed.**

### Step 1: Locate PR-OPS-3 workspace shell
Find Agent Ops components, examine tree structure, report what data is real vs mock, mode switching logic.

### Step 2: Locate Phase 6 frontend patterns
Find typed adapters, data-fetching hooks, existing Agent Ops types. Report adapter pattern, hook pattern, state management approach.

### Step 3: Check existing roster/health wiring
Confirm whether PR-OPS-3 already has hooks/adapters or just raw fetch. Report real vs mock.

### Step 4: Locate frontend test patterns
Find test files, check runner config. Report runner, patterns, existing count.

### Step 5: Check API base URL and fetch pattern
Find backend URL config and HTTP client usage.

### Step 6: Check run context availability
Determine if run_id is obtainable from existing app state. Recommend run selector approach.

### Step 7: Run frontend baseline
Confirm green. Record count.

### Step 8: Propose smallest patch set
Files to create/modify, assumption corrections, split confirmation, run selector recommendation.

---

## 20. Implementation Constraints

### 20.1 General rule
Follow Phase 6 / PR-OPS-3 patterns. Document deviations.

### 20.1b PR-OPS-5a sequence
1. Create shared types file
2. Create/extend typed adapters with OpsErrorEnvelope parsing
3. Create/extend hooks (roster, health, trace, detail)
4. Confirm Org mode preserved, implement roster-health join, relationship lines
5. Wire Health mode — activate pill, elevate degraded entities, data_state banners
6. Write tests — gate: existing baseline preserved
7. Update spec

### 20.1c PR-OPS-5b sequence
1. Implement run selector
2. Wire Run mode — stage timeline, participants, trace edges, arbiter summary, degraded behavior
3. Wire Detail sidebar — discriminated union rendering, all four variants, degraded behavior
4. Write tests — gate: all 5a + baseline preserved
5. Close spec and update docs

### 20.2 No changes expected to
Backend code, Phase 6 components, pipeline code, backend tests.

### 20.3 Out of scope
No backend changes, no new endpoints, no contract mods, no SSE/WebSocket, no control-plane UI, no mutation workflows, no Org mode redesign, no trace semantics beyond contract.

---

## 21. Suggested component additions

RunTracePanel, TraceStageTimeline, ParticipantList, ArbiterSummaryCard, HealthModeSection, AgentDetailSidebar, DataStateBanner, RunSelector. Names may vary.

---

## 22. Success Definition

PR-OPS-5 is done when: workspace renders live data from all four endpoints; Org mode preserved; Health mode enabled with operator attention; Run mode shows trace; Detail sidebar shows typed deep-dive; data_state and error handling correct; Phase 6 + PR-OPS-3 zero regressions; build + typecheck pass; no backend modified.

---

## 23. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| PR-OPS-1 | Contract docs | ✅ Done |
| PR-OPS-2 | Backend: roster + health | ✅ Done — 55 tests |
| PR-OPS-3 | Frontend: workspace shell | ✅ Done |
| Phase 6 | Core product lane | ✅ Done |
| PR-OPS-4a | Backend: agent-trace | ✅ Done — 70 tests |
| PR-OPS-4b | Backend: agent-detail | ✅ Done — 72 tests |
| **PR-OPS-5a** | **Frontend: types + adapters + Health mode** | **⏳ Spec drafted** |
| PR-OPS-5b | Frontend: Run mode + Detail sidebar | ⏳ Blocked on 5a |

---

## 24. Diagnostic Findings

*To be populated after running the diagnostic protocol (Section 19).*

---

## 25. Follow-on work (out of scope)

Run browser/search, artifact inspector, deeper graph vis, live push, control-plane actions, richer influence weighting.

---

## 26. Test Checklist

### 26.1 Mode rendering
- [ ] Org mode default, Health mode activation, Run mode activation, mode switching preserves selection

### 26.2 Roster + health join
- [ ] PR-OPS-3 behavior preserved, unknown health IDs discarded, missing health valid, health failure degrades

### 26.3 Health mode
- [ ] Degraded/stale elevated, badges correct, data_state banner renders

### 26.4 Detail sidebar
- [ ] Selection triggers fetch, persona/officer/arbiter/subsystem variants render, entity_type drives rendering, degraded state, 404 handled

### 26.5 Run trace
- [ ] Summary + stages + participants + arbiter render, stage ordering correct, null arbiter handled, stale/unavailable/404 handled, partial run handled

### 26.6 Contract safety
- [ ] Plain IDs, entity_type drives rendering, no hidden field assumptions, OpsErrorEnvelope parsed

### 26.7 Regression
- [ ] Phase 6 works, PR-OPS-3 Org preserved, build passes, typecheck passes, no backend modified

---

## 27. Appendix A — Agent Prompt (PR-OPS-5a)

Read docs/PR_OPS_5_SPEC.md in full. Also read AGENT_OPS_CONTRACT.md §4-§7 (canonical contract for all four endpoints). Scope: types, adapters, hooks, Org preservation, Health mode. NOT Run mode or Detail sidebar. Diagnostic first (§19). Hard constraints: contract shapes exact, roster-health join per §5.10, data_state per §5.6, OpsErrorEnvelope parsing, no backend changes, no Run/Detail, no SSE, no control-plane, no Org redesign. On completion: flip 5a ACs, update progress doc, return summary.

---

## 28. Appendix B — Agent Prompt (PR-OPS-5b)

Read docs/PR_OPS_5_SPEC.md in full. Also read AGENT_OPS_CONTRACT.md §4-§7 (canonical contract). Scope: Run mode, Detail sidebar, run selector. 5a already landed. Hard constraints: reuse 5a types/adapters, switch on entity_type not variant, trace edges run-scoped distinct from roster, null arbiter → hide, no fake intelligence, no backend changes. On completion: mark spec complete, update progress doc, Phase Completion Report.

---

## 29. Spec Quality Checklist

- [x] Status: spec drafted
- [x] All ACs pending
- [x] Diagnostic findings placeholder
- [x] 12 non-goals listed
- [x] Negative-case ACs (AC-12, AC-13, AC-20)
- [x] Regression gates in implementation sequence
- [x] Agent prompts with doc-close
- [x] All paths TBC from diagnostic
- [x] Contract references explicit
- [x] State handling matrix (§13)
- [x] Split with AC allocation (§18)
- [x] Types enumerated (§5.3)

---

## 30. One-sentence summary

PR-OPS-5 turns Agent Ops from a static roster/health workspace into a fully wired operator observability surface by enabling health mode, run trace mode, and typed entity detail — entirely against the already-shipped backend contract.
