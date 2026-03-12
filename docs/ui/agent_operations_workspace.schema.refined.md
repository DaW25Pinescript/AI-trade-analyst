# AI Trade Analyst — Agent Operations Workspace Schema

**File:** `docs/schema/agent_operations_workspace.schema.md`  
**Status:** Proposed (repo-ready draft for post-foundation UI extension)  
**Scope:** Backend → UI Contract Extension  
**Depends on:** `docs/design-notes/agent_operations_workspace.md`, `docs/ui/UI_CONTRACT.md`, `docs/ui/UI_WORKSPACES.md`  
**Phase:** UI Extension (after Triage Board + Journey Studio + Review are stable)  
**Visual Reference:** Latest mockup (hierarchical business structure with **GOVERNANCE LAYER** → **OFFICER LAYER** → **PERSONA / DEPARTMENT GRID**)

---

## 1. Purpose

This contract exposes the exact architecture shown in the current UI mockup: a clean Bloomberg-style hierarchical org view with:

- **GOVERNANCE LAYER** (2 cards)
- **OFFICER LAYER** (2 cards with connecting arrow / hierarchy line)
- **PERSONA / DEPARTMENT GRID** (4 framed business-unit boxes: **TECHNICAL ANALYSIS**, **RISK / CHALLENGE**, **REVIEW / GOVERNANCE**, **INFRA / HEALTH**)
- right sidebar titled **Selected Node Detail**
- bottom ribbon titled **Activity / Event Stream**

All visible hierarchy — layers, arrows, framed department boxes, card placement, and participation overlays — must be driven by backend data. The frontend may arrange the display, but it must not invent the structure.

This document is not a full backend implementation spec. It is the backend → UI handoff required so the frontend can render the workspace without inventing hierarchy, status, contribution, or relationship data.

---

## 2. Core Principles

These rules are mandatory.

### 2.1 Read-only MVP
All Agent Operations Workspace surfaces are read-only in MVP.

No write, refresh, override, or orchestration endpoints are included in this contract.

### 2.2 Backend Authority
Every field shown in cards, hierarchy lines, department frames, detail panels, run overlays, and health ribbons must originate from backend responses.

The UI must not invent:

- fake entities
- fake reporting lines
- fake contribution weights
- fake recovery states
- fake dependency relationships
- fake department placement

### 2.3 Canonical State Discipline
This workspace must reuse the state discipline established in `UI_CONTRACT.md`.

In particular:

- **run / lifecycle state** and **health / freshness state** are separate dimensions
- `data_state` remains a response-level contract concept
- entity-level status rendering must not collapse multiple dimensions into a single ambiguous label

### 2.4 Decision Lineage Over Decorative Org Charts
A static roster is only the first layer.

The real value of this workspace is:

- who participated in a run
- who supported or challenged the verdict
- which dependencies were degraded
- whether caution, veto, or override pressure occurred

### 2.5 UI-Controlled Presentation Tokens
The backend may expose semantic visual families and orb tokens, but it must not own raw theme values such as hex colors.

The visual palette remains defined by the UI layer and `VISUAL_APPENDIX.md`.

---

## 3. Proposed Endpoints

These are the only new surfaces the UI may call for this extension.

| Method | Route | Purpose | Return Shape | Notes |
|---|---|---|---|---|
| `GET` | `/ops/agent-roster` | Static architecture + roster truth | `AgentRosterResponse` | powers the visible hierarchy |
| `GET` | `/ops/agent-health` | Current health snapshot of all visible entities | `AgentHealthSnapshotResponse` | merged with roster in Org and Health views |
| `GET` | `/runs/{run_id}/agent-trace` | Run-specific participation + lineage | `RunAgentTraceResponse` | used only in Run view |
| `GET` | `/ops/agent-detail/{entity_id}` | Full detail for selected card | `AgentDetailResponse` | on-demand for **Selected Node Detail** sidebar |

No streaming, no POSTs, and no auth changes are assumed in MVP.

---

## 4. Response Envelope Metadata

All four endpoint families should use a standard metadata block.

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-12T21:48:00Z",
  "data_state": "live",
  "source_of_truth": "roster_config+observability+run_artifacts"
}
```

### 4.1 Metadata fields

- `version` — contract or payload version
- `generated_at` — ISO timestamp for payload generation
- `data_state` — `live | stale | unavailable`
- `source_of_truth` — optional text describing the backend source composition

This metadata is contract-level. It does not replace entity-level health or run state.

---

## 5. Core Domain Models — Aligned to the Visual Hierarchy

### 5.1 AgentRosterResponse

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-12T21:48:00Z",
  "data_state": "live",
  "source_of_truth": "roster_config",
  "governance_layer": [AgentSummary, AgentSummary],
  "officer_layer": [AgentSummary, AgentSummary],
  "departments": {
    "TECHNICAL_ANALYSIS": [AgentSummary, AgentSummary],
    "RISK_CHALLENGE": [AgentSummary, AgentSummary],
    "REVIEW_GOVERNANCE": [AgentSummary, AgentSummary],
    "INFRA_HEALTH": [AgentSummary]
  },
  "relationships": [EntityRelationship]
}
```

#### Visual mapping note

The UI renders:

- `governance_layer` → top boxed section titled **GOVERNANCE LAYER**
- `officer_layer` → second boxed section titled **OFFICER LAYER**
- each `departments` key → one framed department box inside **PERSONA / DEPARTMENT GRID**
- `relationships` → connecting arrows / hierarchy lines between layers and boxes

#### Structural expectation

The current mockup assumes:

- exactly 2 governance cards
- exactly 2 officer cards
- exactly 4 framed department boxes with the keys listed above

The backend should return these keys explicitly so the frontend does not infer departments from display labels.

---

### 5.2 AgentSummary

Base card shape for any visible node.

```json
{
  "id": "default_analyst",
  "display_name": "DEFAULT ANALYST",
  "type": "persona",
  "department": "TECHNICAL_ANALYSIS",
  "role": "Senior Analyst",
  "capabilities": ["DIRECTIONAL", "BIAS"],
  "supports_verdict": true,
  "initials": "DA",
  "visual_family": "technical",
  "orb_color": "teal"
}
```

#### Fields

- `id` — stable entity identifier
- `display_name` — card title
- `type` — `persona | officer | arbiter | subsystem`
- `department` — canonical department key
- `role` — subtitle or card descriptor
- `capabilities` — tag list shown on the card
- `supports_verdict` — whether this entity can contribute directly to verdict formation
- `initials` — optional fallback for compact visual avatar treatments
- `visual_family` — semantic visual family token
- `orb_color` — semantic orb token only

#### Allowed visual tokens

`visual_family`:

- `governance`
- `officer`
- `technical`
- `risk`
- `review`
- `infra`

`orb_color`:

- `teal`
- `amber`
- `red`

These are semantic tokens. The UI maps them to the glowing orb / metallic avatar system.

---

### 5.3 EntityRelationship

Explicit relationship model for hierarchy lines and arrows.

```json
{
  "from": "arbiter",
  "to": "market_data_officer",
  "type": "supports"
}
```

#### Allowed relationship types

- `supports`
- `challenges`
- `feeds`
- `synthesizes`
- `overrides`
- `degraded_dependency`
- `recovered_dependency`

#### Visual use

For the current mockup, `relationships` should explicitly support:

- governance → officer connections
- officer → department box connections
- later run-trace overlays

The frontend must not infer hierarchy arrows from box position alone.

---

### 5.4 AgentHealthSnapshotResponse

Collection response for current health / lifecycle state across all visible entities.

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-12T21:48:00Z",
  "data_state": "live",
  "entities": [
    {
      "entity_id": "default_analyst",
      "run_state": "completed",
      "health_state": "live",
      "last_active_at": "2026-03-12T21:44:00Z",
      "last_run_id": "run_2026-03-12_2148",
      "health_summary": "Directional bias completed successfully",
      "recent_event_summary": "Recovered from stale feeder @ 19:12"
    }
  ]
}
```

#### Fields

- `entity_id` — joins to `AgentSummary.id`
- `run_state` — `idle | running | completed | failed`
- `health_state` — `live | stale | degraded | unavailable | recovered`
- `last_active_at` — ISO timestamp
- `last_run_id` — most recent known run
- `health_summary` — short card/detail summary
- `recent_event_summary` — event ribbon or detail panel summary

This response powers:
- glowing orb state
- health chips
- run-state chips
- detail-panel status content
- Health mode sorting

---

### 5.5 RunAgentTraceResponse

Run-specific participation and lineage overlay for **Run** mode.

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-12T21:48:00Z",
  "data_state": "live",
  "source_of_truth": "run_artifacts+lineage_trace",
  "run_id": "run_2026-03-12_2148",
  "trace_state": "complete",
  "participants": [
    {
      "entity_id": "default_analyst",
      "participated": true,
      "contribution_type": "directional",
      "influence_level": 0.68,
      "final_bias_alignment": "aligned",
      "last_error": null,
      "recovered_after_failure": false
    }
  ],
  "lineage_edges": [
    {
      "from": "risk_officer",
      "to": "arbiter",
      "type": "challenges",
      "timestamp": "2026-03-12T21:46:00Z"
    }
  ],
  "arbiter_override": true
}
```

#### Allowed trace fields

`trace_state`:
- `complete`
- `partial`
- `unavailable`

`contribution_type`:
- `directional`
- `cautionary`
- `veto`
- `supporting`
- `infrastructure`

`final_bias_alignment`:
- `aligned`
- `partial`
- `opposed`

This response powers:
- Run mode highlights
- influence overlays
- arbiter override banners
- lineage edge overlays

---

### 5.6 AgentDetailResponse

Full detail payload for **Selected Node Detail** sidebar.

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-12T21:48:00Z",
  "data_state": "live",
  "summary": {
    "id": "default_analyst",
    "display_name": "DEFAULT ANALYST",
    "type": "persona",
    "department": "TECHNICAL_ANALYSIS",
    "role": "Senior Analyst",
    "capabilities": ["DIRECTIONAL", "BIAS"],
    "supports_verdict": true,
    "initials": "DA",
    "visual_family": "technical",
    "orb_color": "teal"
  },
  "health": {
    "entity_id": "default_analyst",
    "run_state": "completed",
    "health_state": "live",
    "last_active_at": "2026-03-12T21:44:00Z",
    "last_run_id": "run_2026-03-12_2148",
    "health_summary": "Directional bias completed successfully",
    "recent_event_summary": "Recovered from stale feeder @ 19:12"
  },
  "purpose": "Balanced multi-timeframe analysis specialist used as the primary directional persona.",
  "influence_history": [
    {
      "run_id": "run_2026-03-12_2148",
      "influence_level": 0.68,
      "timestamp": "2026-03-12T21:48:00Z"
    }
  ],
  "error_log": [
    {
      "code": "STALE_FEEDER",
      "message": "Feeder was stale before recovery",
      "timestamp": "2026-03-12T19:12:00Z"
    }
  ],
  "upstream_dependencies": ["market_data_officer", "macro_risk_officer"],
  "downstream_consumers": ["arbiter"]
}
```

This response should extend, not replace, the summary/health model already rendered in the main workspace.

---

## 6. Exact Visual Mapping Rules

### 6.1 Layer titles
The frontend should render these exact section titles:

- **GOVERNANCE LAYER**
- **OFFICER LAYER**
- **PERSONA / DEPARTMENT GRID**

### 6.2 Department framing
The backend must return department keys exactly as:

- `TECHNICAL_ANALYSIS`
- `RISK_CHALLENGE`
- `REVIEW_GOVERNANCE`
- `INFRA_HEALTH`

This guarantees that the frontend can render the four framed boxes with the same business-unit layout as the current mockup.

### 6.3 Right sidebar
`AgentDetailResponse` powers a right sidebar titled:

- **Selected Node Detail**

### 6.4 Bottom ribbon
Activity summaries should be renderable in a bottom ribbon titled:

- **Activity / Event Stream**

The MVP event ribbon may derive from:
- `recent_event_summary`
- `health_summary`
- `arbiter_override`
- `error_log`
- trace lineage markers

### 6.5 Visual tokens
`visual_family` and `orb_color` are semantic visual tokens intended to support:
- metallic robot avatar family selection
- teal/amber/red glowing orb styling
- consistent layer/dept visual identity

The backend must not send raw CSS classes or hex colors.

---

## 7. Canonical Visual State Mapping

### 7.1 Health and lifecycle states
Entity state must remain split:

`health_state`:
- `live`
- `stale`
- `degraded`
- `unavailable`
- `recovered`

`run_state`:
- `idle`
- `running`
- `completed`
- `failed`

The frontend may choose a primary badge, but both dimensions must remain available.

### 7.2 Orb rules
Recommended orb mapping:

- `health_state = live` → teal orb
- `health_state = recovered` → teal orb + recovered badge
- `health_state = stale` → amber orb
- `health_state = degraded` → amber orb
- `health_state = unavailable` → red orb

### 7.3 Department-box ordering
The frontend should render department boxes in this order:

1. `TECHNICAL_ANALYSIS`
2. `RISK_CHALLENGE`
3. `REVIEW_GOVERNANCE`
4. `INFRA_HEALTH`

This matches the current visual reference.

### 7.4 Connecting arrows
`relationships` and `lineage_edges` explicitly drive hierarchy lines and arrows:

- governance → officer
- officer → department box
- run lineage overlays as needed

The frontend must not synthesize these relationships from placement.

---

## 8. Error and State Handling

This extension inherits the broader handling rules from `UI_CONTRACT.md`, with the following specifics:

### 8.1 Collection-level behavior
- roster failure → workspace-level blocking error
- health failure with roster success → render structure with degraded banner
- trace failure in Run mode → keep workspace usable with trace warning
- detail failure → keep sidebar open with structured error state

### 8.2 Unknown entity / run behavior
- unknown `entity_id` → structured `AGENT_NOT_FOUND`
- unknown `run_id` → treat as `artifact-missing` modifier in the UI

### 8.3 Structured error envelope
Where errors are returned, do not rely on freeform `detail` strings.

Preferred shape:

```json
{
  "error": "AGENT_NOT_FOUND",
  "message": "No agent exists for the requested entity_id",
  "entity_id": "missing_agent"
}
```

### 8.4 Empty-state caution
The UI must not assume demo-mode fallback unless the backend explicitly supports it.

An empty roster is not automatically valid.

---

## 9. View Composition Rules

### 9.1 Org View
Use:
- `/ops/agent-roster`
- `/ops/agent-health`

Render:
- **GOVERNANCE LAYER**
- **OFFICER LAYER**
- **PERSONA / DEPARTMENT GRID**
- hierarchy arrows
- current health/lifecycle badges

### 9.2 Run View
Use:
- `/ops/agent-roster`
- `/ops/agent-health`
- `/runs/{run_id}/agent-trace`

Render:
- same hierarchy as Org View
- participant highlighting
- influence overlays
- lineage edge overlays
- arbiter override indicator

### 9.3 Health View
Use:
- `/ops/agent-roster`
- `/ops/agent-health`

Render:
- same hierarchy
- degraded/unavailable/stale-first emphasis
- stronger health summaries
- activity/event ribbon weighted to problems and recoveries

---

## 10. Future-Proofing

These are explicitly out of MVP scope, but may be added later with separate contract sections:

- `GET /runs/{run_id}/decision-lineage`
- `GET /ops/agent-events`
- `POST /ops/force-refresh`

Do not extend existing payloads silently. Add new fields or routes deliberately and update this contract.

---

## 11. Implementation Checklist

- [ ] Expose `/ops/agent-roster` from roster/config truth
- [ ] Expose `/ops/agent-health` from observability + health aggregators
- [ ] Expose `/runs/{run_id}/agent-trace` from run artifacts / lineage sources
- [ ] Expose `/ops/agent-detail/{entity_id}` for sidebar detail
- [ ] Return canonical department keys and layer groupings
- [ ] Return explicit `relationships` for hierarchy lines
- [ ] Keep responses compact (< 50 KB for roster/health in MVP)
- [ ] Update `UI_CONTRACT.md` when these routes become active
- [ ] Add contract tests matching the models in this document

---

## 12. Summary

This schema is the minimal sufficient contract extension needed to turn the current Agent Operations Workspace mockup into a backend-authoritative, production-grade UI surface.

It gives the frontend exactly what it needs to render:

- **GOVERNANCE LAYER**
- **OFFICER LAYER**
- **PERSONA / DEPARTMENT GRID**
- connecting arrows / hierarchy lines
- **Selected Node Detail**
- **Activity / Event Stream**

without inventing structure, state, or lineage in the browser.
