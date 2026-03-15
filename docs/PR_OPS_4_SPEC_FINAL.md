# PR-OPS-4 — Agent Ops Trace + Detail Backend

**Phase:** 7
**Lane:** Operator / Observability
**Type:** Backend + Contract Extension
**Status:** ✅ Complete — PR-OPS-4a (trace) + PR-OPS-4b (detail) both implemented
**Date:** 2026-03-14
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Extends:** `docs/ui/AGENT_OPS_CONTRACT.md` (Phase 7 reserved endpoints from §6)
**Depends on:** PR-OPS-1 (contract — merged ✅), PR-OPS-2 (backend — merged ✅), Phase 6 shipped UI ✅
**Blocks:** PR-OPS-5 (frontend Agent Ops wiring — do not draft until PR-OPS-4 merges)

---

## 1. Objective

Add the first **run-level** and **entity-level** observability endpoints for the Agent Ops workspace.

This PR introduces two new **read-side** backend endpoints:

- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`

These endpoints must be:

- compact
- typed
- UI-ready
- read-only
- derived from existing artifacts / registry data
- consistent with the existing Agent Ops contract patterns

This PR does **not** add any control-plane actions, mutations, or backend orchestration changes.

---

## 2. Why this PR exists

Phase 6 shipped the first Agent Ops MVP:
- roster
- health
- workspace shell

That gives the user a static operator view.

Phase 7 begins the next layer:
- **run observability**
- **entity drilldown**
- **traceability**
- **trust / explainability support**

Without these endpoints, the Agent Ops workspace cannot:
- show which agents participated in a run
- show how influence flowed through a run
- show whether the arbiter overrode analyst direction
- show meaningful detail in the right-side detail panel

| Without PR-OPS-4 | With PR-OPS-4 |
|-------------------|---------------|
| Agent Ops shows roster structure and health but can't answer "what happened in this run?" | Run mode shows ordered execution trace with participant highlighting and lineage |
| Clicking an entity card shows only the roster summary — no deep-dive | Selected Node Detail sidebar shows expanded identity, status, dependencies, recent participation |
| Arbiter decisions are opaque — no visibility into overrides or synthesis approach | Arbiter trace summary shows override count, overridden entities, dissent summary |
| Frontend (PR-OPS-5) cannot be built — no endpoints to wire to | PR-OPS-5 has two tested, contracted endpoints ready for frontend wiring |

This PR creates the backend read models required for that UX.

---

## 3. Governance / sequencing rule

This PR must land **before** any UI wiring in PR-OPS-5.

Reason:
- backend contract first
- shared response shapes locked before frontend integration
- no speculative frontend wiring against unstable endpoint shapes

---

## 4. Non-goals

This PR must **not** do any of the following:

1. No UI work — that is PR-OPS-5
2. No control actions (start/stop agent, retry, toggle, enable/disable, mutate config)
3. No raw prompt dumps
4. No full LLM transcript exposure
5. No unbounded internal debug blobs
6. No new persistence layer — read-side projection only
7. No scheduler/runtime changes
8. No change to existing analysis flow
9. No broad refactor of roster/health endpoints
10. No SSE / WebSocket / live-push — polling model locked (inherited from `AGENT_OPS_CONTRACT.md` §5.3)
11. No new top-level module — work confined to existing agent_ops package (or equivalent PR-OPS-2 location)
12. No SQLite or database layer introduced

This is a **read-side projection PR only**.

---

## 5. Existing contract alignment

This PR extends the Agent Ops contract established in `AGENT_OPS_CONTRACT.md` and must preserve the same shared patterns:

- `ResponseMeta` — flat response envelope, not `data`/`meta` nesting (see §5.1)
- `OpsErrorEnvelope`
- `DepartmentKey`
- existing envelope / meta conventions
- existing API router / model / test style from PR-OPS-2

Implementation rule:

> Follow the same backend patterns established by PR-OPS-2 unless the new endpoint requirements force a deviation. If deviation is required, it must be explicitly justified in the PR notes.

### 5.1 Envelope style decision (LOCKED)

**Both new endpoints must use the same flat `ResponseMeta & { ... }` pattern established by PR-OPS-2.**

Do not introduce a new `data`/`meta` wrapper style. All four Agent Ops endpoints (roster, health, trace, detail) must share one envelope convention. This simplifies PR-OPS-5 frontend wiring.

If the diagnostic finds a slightly different real implementation shape than expected, match the implementation pattern that is already live and tested.

### 5.2 Entity identifier convention (LOCKED)

**Both new endpoints must reuse the existing `entity_id` convention from roster/health endpoints.**

Do not introduce namespaced IDs (e.g. `persona:ict_analyst`) unless that convention is already established in PR-OPS-2. The diagnostic must confirm the current `entity_id` format and match it exactly.

Entity type discrimination is handled by the explicit `entity_type` field, not by parsing the ID string. If current IDs are not sufficiently expressive, keep existing `entity_id` and rely on `entity_type` for discrimination. A cross-endpoint identifier migration is out of scope for PR-OPS-4.

---

## 6. Endpoint 1 — `GET /runs/{run_id}/agent-trace`

### 6.1 Purpose

Return a compact, ordered, UI-ready projection of agent participation and influence for a specific run.

This endpoint powers:
- participant highlighting
- influence overlays
- lineage edge rendering
- arbiter override indicators
- run detail inspection in Agent Ops

### 6.2 Design intent

This is **not** a raw engine dump.

It is a structured observability projection that answers:

- which entities participated?
- in what stage order?
- what role did each entity play?
- what was each entity's directional / evaluative contribution?
- how did the arbiter synthesize or override those contributions?
- what source artifacts back this projection?

### 6.3 Source data

Read-side only. `/runs/{run_id}/agent-trace` is projected primarily from the per-run `run_record.json` artifact.

**Primary source of truth:**
- `run_record.json` → normalized run identity, request context, ordered stages, executed analysts, skipped analysts, failed analysts, arbiter summary, artifact references, usage summary, warnings/errors

**Optional enrichment source:**
- `dev_diagnostics.json` → request/event timing enrichment only when present and cheap to read

`dev_diagnostics.json` is not required for a valid trace response. If diagnostics are absent, the endpoint must still return a valid trace projected from `run_record.json`.

Do **not** introduce a new persistence layer. If the run artifacts are missing or malformed, return an appropriate error via `OpsErrorEnvelope`.

### 6.4 Response shape

```typescript
type AgentTraceResponse = ResponseMeta & {
  run_id: string;
  run_status: "completed" | "failed" | "partial";
  instrument?: string;
  session?: string;
  started_at?: string;
  finished_at?: string;
  summary: TraceSummary;
  stages: TraceStage[];
  participants: TraceParticipant[];
  trace_edges: TraceEdge[];
  arbiter_summary: ArbiterTraceSummary | null;
  artifact_refs: ArtifactRef[];
};
```

**Notes:**
- Uses flat `ResponseMeta & { ... }` pattern per §5.1
- `run_status: "partial"` covers runs that died mid-execution — trace returns whatever stages completed
- `instrument` and `session` are optional run-level trading context for the trace header

### 6.5 TraceSummary

```typescript
type TraceSummary = {
  entity_count: number;
  stage_count: number;
  arbiter_override: boolean;
  final_bias?: "bullish" | "bearish" | "neutral";
  final_decision?: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `entity_count` | `number` | yes | How many entities participated in this run |
| `stage_count` | `number` | yes | How many stages executed |
| `arbiter_override` | `boolean` | yes | Whether the arbiter overrode any analyst direction |
| `final_bias` | see type | no | Directional outcome if the run produced one |
| `final_decision` | `string` | no | Decision label (e.g. `"NO_TRADE"`, `"LONG"`) — compact, not freeform prose |

The `summary` block gives the UI a compact overview for the trace header without parsing the full `stages`/`participants` arrays.

### 6.6 TraceStage

```typescript
type TraceStage = {
  stage_key: string;
  stage_index: number;
  status: "completed" | "failed" | "skipped";
  started_at?: string;
  finished_at?: string;
  participant_ids: string[];
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `stage_key` | `string` | yes | Machine-readable stage identifier (e.g. `"input_validation"`, `"analysis"`, `"arbiter"`) — stable for frontend routing |
| `stage_index` | `number` | yes | Explicit execution order — stages must be returned in ascending `stage_index` order |
| `status` | see type | yes | Stage outcome |
| `started_at` | `string` | no | ISO 8601 timestamp of stage start |
| `finished_at` | `string` | no | ISO 8601 timestamp of stage completion |
| `participant_ids` | `string[]` | yes | Entity IDs that participated in this stage — joins to roster `id` using existing convention (§5.2) |

Stages must be returned in execution order (ascending `stage_index`). The frontend renders these as an ordered timeline.

### 6.6b Trace stage vocabulary decision (LOCKED)

V1 `agent-trace` reuses the normalized stage vocabulary already present in `run_record.json` instead of inventing a second stage taxonomy.

Expected stage keys include:
- `validate_input`
- `macro_context`
- `chart_setup`
- `analyst_execution`
- `arbiter`
- `logging`

If future pipeline changes add more granularity, the backend may still project to this stable UI-facing vocabulary, but PR-OPS-4 should not invent a parallel taxonomy now.

**`run_status` and response-level `data_state` are distinct dimensions:**
- `run_status` = execution outcome (`completed` | `failed` | `partial`) — describes what happened during the run
- `data_state` = projection freshness / availability (`live` | `stale` | `unavailable`) — describes whether the trace data can be trusted right now

These must not be conflated. A run may have `run_status: "completed"` with `data_state: "stale"` if the artifacts are old.

### 6.7 TraceParticipant

```typescript
type TraceParticipant = {
  entity_id: string;
  entity_type: "persona" | "officer" | "arbiter" | "subsystem";
  display_name: string;
  department?: DepartmentKey;
  participated: boolean;
  contribution: ParticipantContribution;
  status: "completed" | "failed" | "skipped";
};

type ParticipantContribution = {
  stance?: "bullish" | "bearish" | "neutral" | "abstain";
  confidence?: number;
  role: string;
  summary: string;
  was_overridden: boolean;
  override_reason?: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `entity_id` | `string` | yes | Joins to roster `id` — existing convention per §5.2 |
| `entity_type` | see type | yes | Entity classification — discrimination handled here, not by parsing ID |
| `display_name` | `string` | yes | Human-readable name for the participant card |
| `department` | `DepartmentKey` | no | Department affiliation if applicable |
| `participated` | `boolean` | yes | Whether this entity actively contributed (vs. was scheduled but skipped) |
| `contribution.stance` | see type | no | Directional assessment if the entity produced one |
| `contribution.confidence` | `number` | no | Confidence score (0.0–1.0) if available |
| `contribution.role` | `string` | yes | Role within this run (e.g. `"primary_structure_analysis"`) |
| `contribution.summary` | `string` | yes | Compact summary of what this entity contributed (1–3 sentences) |
| `contribution.was_overridden` | `boolean` | yes | Whether the entity's contribution was treated as overridden/discounted in the final synthesis, when reconstructable from v1 artifacts |
| `contribution.override_reason` | `string` | no | Explanation — present only if `was_overridden` is true |
| `status` | see type | yes | Participant-level outcome |

### 6.8 TraceEdge

```typescript
type TraceEdge = {
  from: string;
  to: string;
  type: "considered_by_arbiter" | "skipped_before_arbiter" | "failed_before_arbiter" | "override";
  stage_index?: number;
  summary?: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `from` | `string` | yes | Source entity — joins to roster `id` |
| `to` | `string` | yes | Target entity — joins to roster `id` |
| `type` | see type | yes | Run-scoped relationship classification |
| `stage_index` | `number` | no | Stage reference for filtering / visualization |
| `summary` | `string` | no | Compact tooltip-safe explanation |

V1 trace edges are intentionally conservative. They represent run-scoped participation / arbiter-consideration / skip / failure / override relationships that can be honestly derived from existing artifacts.

They do not claim to encode a fully faithful causal reasoning graph or weighted influence network unless that information is explicitly present in the source artifacts.

This endpoint complements static roster relationships; it does not replace them.

### 6.9 ArbiterTraceSummary

```typescript
type ArbiterTraceSummary = {
  entity_id: string;
  override_applied: boolean;
  override_type?: string;
  override_count: number;
  overridden_entity_ids: string[];
  synthesis_approach?: string;
  final_bias?: "bullish" | "bearish" | "neutral";
  confidence?: number;
  dissent_summary?: string;
  summary: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `entity_id` | `string` | yes | The arbiter entity — joins to roster `id` |
| `override_applied` | `boolean` | yes | Whether any override was applied — explicit, not inferred |
| `override_type` | `string` | no | Classification of override (e.g. `"confidence_suppression"`, `"directional_reversal"`) |
| `override_count` | `number` | yes | How many entity contributions were overridden |
| `overridden_entity_ids` | `string[]` | yes | Which entities were overridden — cross-references `contribution.was_overridden` |
| `synthesis_approach` | `string` | no | How the arbiter combined inputs (compact label) |
| `final_bias` | see type | no | The arbiter's final directional call |
| `confidence` | `number` | no | Arbiter confidence (0.0–1.0) |
| `dissent_summary` | `string` | no | Compact summary of dissenting views that were overridden |
| `summary` | `string` | yes | Human-readable summary of the arbiter's synthesis |

`ArbiterTraceSummary` is `null` if the run did not reach the arbiter stage (e.g. run failed during analyst fan-out).

### 6.9b Override semantics (V1)

In PR-OPS-4, `override_applied` is returned explicitly in the API response, but may be best-effort derived from existing run artifacts and arbiter/result surfaces when the source artifacts do not carry a first-class typed override object.

Therefore:
- `override_applied` is required
- `override_type` is optional
- `override_count` and `overridden_entity_ids` are returned only when reconstructable from artifacts
- absence of `override_type` does not mean "no override" — it may mean "override kind not reconstructable from v1 artifacts"

If future run artifacts carry richer typed override metadata, subsequent phases may strengthen this projection without changing the top-level response shape.

### 6.10 ArtifactRef

```typescript
type ArtifactRef = {
  artifact_type: string;
  artifact_key: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `artifact_type` | `string` | yes | Classification (e.g. `"run_record"`, `"multi_analyst_output"`) |
| `artifact_key` | `string` | yes | File or artifact identifier (e.g. `"run_record.json"`) |

Artifact references belong at the run level, not per-participant. They are compact pointers — the full artifacts are not inlined.

### 6.11 Bounded payload rules

This endpoint must not include:
- raw LLM prompt bodies
- raw full analyst transcripts
- arbitrarily deep nested internal state
- entire source artifacts inline

Use summaries and artifact references only.

**Explicit limits (testable):**

| Field | Max |
|-------|-----|
| `contribution.summary` | 500 characters |
| `contribution.override_reason` | 300 characters |
| `arbiter_summary.summary` | 500 characters |
| `arbiter_summary.dissent_summary` | 500 characters |
| `trace_edges` array | 50 entries per run |
| `TraceEdge.summary` | 300 characters |

The backend must truncate if source data exceeds these limits. These prevent UI-hostile unbounded text blobs.

### 6.12 `data_state` semantics for agent-trace

| Value | Meaning | UI behavior |
|-------|---------|-------------|
| `live` | Run artifacts successfully read and projected | Normal render |
| `stale` | Run artifacts exist but may be from an incomplete or interrupted run | Render with stale indicator |
| `unavailable` | Run artifacts could not be read or do not exist for this `run_id` | Error state — show "trace unavailable" message |

### 6.13 Error responses

All HTTP errors use `OpsErrorEnvelope`.

| HTTP status | `error` code | When |
|------------|-------------|------|
| 404 | `RUN_NOT_FOUND` | No run artifacts exist for the given `run_id` |
| 422 | `RUN_ARTIFACTS_MALFORMED` | Run artifacts exist but could not be parsed into a valid trace |
| 500 | `TRACE_PROJECTION_FAILED` | Unexpected error during trace projection |

Avoid vague string-only error responses.

### 6.14 Illustrative success response

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-14T11:02:18Z",
  "data_state": "live",
  "source_of_truth": "run_artifacts",
  "run_id": "run_20260314_abc123",
  "run_status": "completed",
  "instrument": "XAUUSD",
  "session": "NY",
  "started_at": "2026-03-14T11:02:00Z",
  "finished_at": "2026-03-14T11:02:18Z",
  "summary": {
    "entity_count": 6,
    "stage_count": 5,
    "arbiter_override": true,
    "final_bias": "neutral",
    "final_decision": "NO_TRADE"
  },
  "stages": [
    {
      "stage_key": "validate_input",
      "stage_index": 1,
      "status": "completed",
      "started_at": "2026-03-14T11:02:00Z",
      "finished_at": "2026-03-14T11:02:01Z",
      "participant_ids": ["input_validator"]
    },
    {
      "stage_key": "macro_context",
      "stage_index": 2,
      "status": "completed",
      "started_at": "2026-03-14T11:02:01Z",
      "finished_at": "2026-03-14T11:02:03Z",
      "participant_ids": ["market_data_officer"]
    },
    {
      "stage_key": "analyst_execution",
      "stage_index": 3,
      "status": "completed",
      "started_at": "2026-03-14T11:02:03Z",
      "finished_at": "2026-03-14T11:02:11Z",
      "participant_ids": ["persona_default_analyst", "persona_ict_purist", "persona_macro_analyst"]
    },
    {
      "stage_key": "arbiter",
      "stage_index": 4,
      "status": "completed",
      "started_at": "2026-03-14T11:02:12Z",
      "finished_at": "2026-03-14T11:02:14Z",
      "participant_ids": ["arbiter"]
    },
    {
      "stage_key": "logging",
      "stage_index": 5,
      "status": "completed",
      "started_at": "2026-03-14T11:02:14Z",
      "finished_at": "2026-03-14T11:02:18Z",
      "participant_ids": []
    }
  ],
  "participants": [
    {
      "entity_id": "persona_ict_purist",
      "entity_type": "persona",
      "display_name": "ICT Purist",
      "department": "TECHNICAL_ANALYSIS",
      "participated": true,
      "contribution": {
        "stance": "bearish",
        "confidence": 0.62,
        "role": "primary_structure_analysis",
        "summary": "Observed weak reclaim and lack of continuation structure.",
        "was_overridden": false
      },
      "status": "completed"
    }
  ],
  "trace_edges": [
    {
      "from": "persona_ict_purist",
      "to": "arbiter",
      "type": "considered_by_arbiter",
      "summary": "Structure view considered in arbiter no-trade decision."
    },
    {
      "from": "persona_macro_analyst",
      "to": "arbiter",
      "type": "considered_by_arbiter"
    }
  ],
  "arbiter_summary": {
    "entity_id": "arbiter",
    "override_applied": true,
    "override_type": "confidence_suppression",
    "override_count": 1,
    "overridden_entity_ids": ["persona_macro_analyst"],
    "summary": "Consensus insufficient for actionable setup."
  },
  "artifact_refs": [
    {
      "artifact_type": "run_record",
      "artifact_key": "run_record.json"
    },
    {
      "artifact_type": "multi_analyst_output",
      "artifact_key": "multi_analyst_output_XAUUSD_20260314T110214Z.json"
    }
  ]
}
```

**Note:** Example IDs and stage keys should mirror the live PR-OPS-2 roster/health and run artifact conventions: plain stable IDs, canonical `DepartmentKey` values, and `run_record.json` stage vocabulary. The diagnostic (§12 Step 2) must confirm actual ID format before implementation.

---

## 7. Endpoint 2 — `GET /ops/agent-detail/{entity_id}`

### 7.1 Purpose

Return a typed, discriminated-union detail view for a single Agent Ops entity.

This endpoint powers the Selected Node Detail sidebar in the Agent Ops workspace.

### 7.2 Design intent

This endpoint must be strongly typed and not devolve into a dumping ground.

It should answer:

- what is this entity?
- what department does it belong to?
- what is its role?
- what does it do?
- how healthy is it?
- what does it depend on?
- how has it been participating recently?
- are there recent warnings or errors?

### 7.3 Source data

Read-side projection from:
- **Profile / registry metadata** → identity, purpose, capabilities, configuration
- **Roster source** → department, relationships, visual family
- **Health projection source** → current health/run state (reuse PR-OPS-2 health logic)
- **Recent run summaries** → derived from existing run artifacts (scan recent `run_record.json` files)

No new persistence layer. If a data source is unavailable, the endpoint returns the detail it can with appropriate `data_state` degradation — it does not fail entirely because one source is missing (see §7.11).

### 7.4 Response shape — discriminated union

```typescript
type AgentDetailResponse = ResponseMeta & {
  entity_id: string;
  entity_type: "persona" | "officer" | "arbiter" | "subsystem";
  display_name: string;
  department?: DepartmentKey;
  identity: EntityIdentity;
  status: EntityStatus;
  dependencies: EntityDependency[];
  recent_participation: RecentParticipation[];
  recent_warnings: string[];
  type_specific: PersonaDetail | OfficerDetail | ArbiterDetail | SubsystemDetail;
};
```

Uses flat `ResponseMeta & { ... }` pattern per §5.1.

The `entity_type` field is the **discriminant**. The `type_specific` field contains a variant keyed by `entity_type`. The frontend switches on `entity_type` to render the correct detail panel.

Entity ID uses the existing roster/health convention per §5.2 — type discrimination is handled by the explicit `entity_type` field, not by parsing the ID string.

### 7.5 Shared detail types

```typescript
type EntityIdentity = {
  purpose: string;
  role: string;
  visual_family: "governance" | "officer" | "technical" | "risk" | "review" | "infra";
  capabilities: string[];
  responsibilities: string[];
  initials?: string;
};

type EntityStatus = {
  run_state: "idle" | "running" | "completed" | "failed";
  health_state: "live" | "stale" | "degraded" | "unavailable" | "recovered";
  last_active_at?: string;
  last_run_id?: string;
  health_summary?: string;
};

type EntityDependency = {
  entity_id: string;
  display_name: string;
  direction: "upstream" | "downstream";
  relationship_type: "supports" | "challenges" | "feeds" | "synthesizes" | "overrides"
                     | "degraded_dependency" | "recovered_dependency";
};

type RecentParticipation = {
  run_id: string;
  run_completed_at?: string;
  verdict_direction?: "bullish" | "bearish" | "neutral" | "abstain";
  was_overridden: boolean;
  contribution_summary: string;
};
```

| Type | Key fields | Purpose |
|------|-----------|---------|
| `EntityIdentity` | purpose, role, capabilities, responsibilities, visual_family | Expanded card — `capabilities` are what the entity *can* do, `responsibilities` are what it's *supposed* to do |
| `EntityStatus` | run_state, health_state, last_active, health_summary | Current state snapshot — reuses PR-OPS-2 health dimensions |
| `EntityDependency` | entity_id, direction, relationship_type | Upstream/downstream relationships for the dependency graph |
| `RecentParticipation` | run_id, verdict, was_overridden, summary | Last N runs this entity participated in |

### 7.6 PersonaDetail

```typescript
type PersonaDetail = {
  variant: "persona";
  analysis_focus: string[];
  verdict_style: string;
  department_role: string;
  typical_outputs: string[];
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `variant` | `"persona"` | yes | Discriminant tag — always `"persona"` |
| `analysis_focus` | `string[]` | yes | Analysis specialty areas (e.g. `["DIRECTIONAL", "MOMENTUM"]`) |
| `verdict_style` | `string` | yes | How this persona forms verdicts (compact label) |
| `department_role` | `string` | yes | Role within department context |
| `typical_outputs` | `string[]` | yes | What this persona typically produces |

### 7.7 OfficerDetail

```typescript
type OfficerDetail = {
  variant: "officer";
  officer_domain: string;
  data_sources: string[];
  monitored_surfaces: string[];
  update_cadence?: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `variant` | `"officer"` | yes | Discriminant tag |
| `officer_domain` | `string` | yes | Domain of responsibility (e.g. `"market_data"`, `"macro_risk"`) |
| `data_sources` | `string[]` | yes | What data sources this officer manages |
| `monitored_surfaces` | `string[]` | yes | What this officer monitors and projects health for |
| `update_cadence` | `string` | no | How often data is refreshed (e.g. `"15m"`, `"1h"`, `"on_demand"`) |

### 7.8 ArbiterDetail

```typescript
type ArbiterDetail = {
  variant: "arbiter";
  synthesis_method: string;
  veto_gates: string[];
  quorum_rule: string;
  override_capable: boolean;
  policy_summary: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `variant` | `"arbiter"` | yes | Discriminant tag |
| `synthesis_method` | `string` | yes | How this arbiter combines analyst inputs |
| `veto_gates` | `string[]` | yes | What conditions trigger a hard veto |
| `quorum_rule` | `string` | yes | Minimum participation rule for valid synthesis |
| `override_capable` | `boolean` | yes | Whether this arbiter can override analyst direction |
| `policy_summary` | `string` | yes | Compact summary of decision policy |

### 7.9 SubsystemDetail

```typescript
type SubsystemDetail = {
  variant: "subsystem";
  subsystem_type: string;
  monitored_resources: string[];
  health_check_method?: string;
  runtime_role: string;
};
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `variant` | `"subsystem"` | yes | Discriminant tag |
| `subsystem_type` | `string` | yes | Classification (e.g. `"scheduler"`, `"data_pipeline"`) |
| `monitored_resources` | `string[]` | yes | What this subsystem monitors or manages |
| `health_check_method` | `string` | no | How health is determined |
| `runtime_role` | `string` | yes | Service role in the system |

### 7.10 Bounded payload rules

The detail payload must remain bounded. Do not dump:
- raw registry blobs
- full config internals
- secrets
- opaque backend-only objects

**Explicit limits (testable):**

| Field | Max |
|-------|-----|
| `identity.purpose` | 500 characters |
| `status.health_summary` | 300 characters |
| `recent_participation` array | 5 most recent entries |
| `RecentParticipation.contribution_summary` | 500 characters per entry |
| `recent_warnings` array | 10 entries |
| `arbiter_detail.policy_summary` | 500 characters |

The backend must truncate if source data exceeds these limits.

### 7.10b Recent participation scan bound (LOCKED)

`agent-detail` recent participation must be derived from a bounded scan of existing run artifacts.

**Maximum scan scope:**
- the most recent 20 run artifact directories, **or**
- the last 7 days of run artifacts,
- whichever is smaller

Returned payload remains capped at the 5 most recent matching participation entries per §7.10.

This prevents unbounded directory walking while still giving the UI a useful recent history view.

### 7.11 Graceful degradation

If health data is unavailable but registry data is available, the endpoint must still return a response. `EntityStatus` fields should reflect the unavailability (e.g. `health_state: "unavailable"`) and the response-level `data_state` should be `stale` or `unavailable`.

The endpoint must **not** return a 500 simply because one data source is missing. Partial projection with degraded `data_state` is preferable to total failure.

### 7.12 `data_state` semantics for agent-detail

| Value | Meaning | UI behavior |
|-------|---------|-------------|
| `live` | All detail sources successfully read and projected | Normal render |
| `stale` | Detail projected but one or more sources may be outdated | Render with stale indicator on affected sections |
| `unavailable` | Entity exists in roster but detail projection failed entirely | Show entity card (from roster) with "detail unavailable" message |

### 7.13 Error responses

All HTTP errors use `OpsErrorEnvelope`.

| HTTP status | `error` code | When |
|------------|-------------|------|
| 404 | `ENTITY_NOT_FOUND` | No entity with this `entity_id` exists in the roster |
| 422 | `ENTITY_DETAIL_MALFORMED` | Entity exists but detail could not be projected |
| 500 | `DETAIL_PROJECTION_FAILED` | Unexpected error during detail projection |

Avoid vague string-only error responses.

### 7.14 Illustrative success response

```json
{
  "version": "2026.03",
  "generated_at": "2026-03-14T11:05:00Z",
  "data_state": "live",
  "source_of_truth": "registry+health+run_artifacts",
  "entity_id": "arbiter",
  "entity_type": "arbiter",
  "display_name": "Trade Arbiter",
  "department": "REVIEW_GOVERNANCE",
  "identity": {
    "purpose": "Synthesizes analyst outputs into a final governed verdict.",
    "role": "Final Decision Authority",
    "visual_family": "governance",
    "capabilities": ["SYNTHESIS", "OVERRIDE", "VETO"],
    "responsibilities": [
      "final verdict generation",
      "confidence normalization",
      "policy override enforcement"
    ]
  },
  "status": {
    "run_state": "completed",
    "health_state": "live",
    "last_active_at": "2026-03-14T11:02:14Z",
    "last_run_id": "run_20260314_abc123",
    "health_summary": "Healthy — last run completed successfully"
  },
  "dependencies": [
    {
      "entity_id": "persona_ict_purist",
      "display_name": "ICT Purist",
      "direction": "upstream",
      "relationship_type": "synthesizes"
    },
    {
      "entity_id": "persona_default_analyst",
      "display_name": "Default Analyst",
      "direction": "upstream",
      "relationship_type": "synthesizes"
    }
  ],
  "recent_participation": [
    {
      "run_id": "run_20260314_abc123",
      "run_completed_at": "2026-03-14T11:02:18Z",
      "verdict_direction": "neutral",
      "was_overridden": false,
      "contribution_summary": "Synthesized 3 analyst inputs. Applied confidence suppression override on macro analyst."
    }
  ],
  "recent_warnings": [],
  "type_specific": {
    "variant": "arbiter",
    "synthesis_method": "weighted_consensus",
    "veto_gates": ["quorum_not_met", "confidence_below_threshold"],
    "quorum_rule": "minimum 2 of 3 analysts must contribute",
    "override_capable": true,
    "policy_summary": "May suppress directional action when consensus or setup quality is insufficient."
  }
}
```

**Note:** Example IDs and field values should mirror the live PR-OPS-2 roster/health conventions: plain stable IDs, canonical `DepartmentKey` values, `run_state`/`health_state` dimensions. The diagnostic (§12 Step 2) must confirm actual ID format before implementation.

---

## 8. Backend implementation guidance

Follow existing PR-OPS-2 structure for:
- router placement
- response model structure
- envelope/meta patterns
- test module organization
- naming

Recommended implementation style:
- thin router
- projection/service helpers
- typed response models
- no business logic in the route body beyond validation + handoff

Suggested implementation split:
- router layer
- projection/service layer
- response model layer
- tests

Do not over-engineer this into a new subsystem.

---

## 9. Data model guidance

### 9.1 Stable identifiers

All UI-addressable entities must have stable IDs matching the existing roster/health convention (§5.2). The diagnostic must confirm the current format.

Entity type is expressed via the explicit `entity_type` field, not by parsing the ID.

### 9.2 Department consistency

`department` must reuse existing `DepartmentKey` conventions — the closed enum of four values from `AGENT_OPS_CONTRACT.md` §2.1.

Do not invent parallel department vocabularies.

### 9.3 Edge typing

For agent trace, edge types are explicit, finite, and intentionally conservative:

```typescript
type TraceEdgeType = "considered_by_arbiter" | "skipped_before_arbiter" | "failed_before_arbiter" | "override";
```

These represent relationships that can be honestly derived from existing run artifacts. Keep this bounded. New edge types require a contract update.

---

## 10. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Router location | PR-OPS-2 established a router file for `/ops/` endpoints — new endpoints follow same placement |
| Response models | PR-OPS-2 uses Pydantic models composing `ResponseMeta` — new models follow same style |
| Error handling | `OpsErrorEnvelope` is already implemented and tested — reuse, do not redefine |
| Run artifacts | `run_record.json` is the primary trace substrate per run; `dev_diagnostics.json` is optional timing enrichment |
| Profile registry | Persona profile registry exists and is source of truth for entity metadata |
| Health projection | Health projection logic exists from PR-OPS-2 — agent-detail can reuse same health source |
| Entity IDs | Stable and consistent between roster, health, and run artifacts — same namespace |
| `DepartmentKey` | Closed enum of four values — unchanged, reused as-is |

**Core question:** Can the two new endpoints be built as pure read-side projections over existing artifacts and registries, following PR-OPS-2 patterns, without requiring changes to the analysis pipeline or introducing new runtime state?

---

## 11. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Trace shape | `/runs/{run_id}/agent-trace` returns a valid `AgentTraceResponse` with all required fields | ✅ Pass |
| AC-2 | Trace ordering | `stages` array is returned in ascending `stage_index` order | ✅ Pass |
| AC-3 | Trace participant join | Every `entity_id` in `participants` maps to a valid roster `id` | ✅ Pass |
| AC-4 | Trace edges | Every `from` and `to` in `trace_edges` maps to a valid roster `id` | ✅ Pass |
| AC-5 | Trace arbiter null | `arbiter_summary` is `null` when run did not reach arbiter stage | ✅ Pass |
| AC-6 | Trace run not found | Missing `run_id` returns 404 with `RUN_NOT_FOUND` error envelope | ✅ Pass |
| AC-7 | Trace bounded payload | `contribution.summary` ≤ 500 chars, `override_reason` ≤ 300 chars — truncation proven by test | ✅ Pass |
| AC-8 | Trace summary block | `summary` block contains valid `entity_count`, `stage_count`, `arbiter_override` | ✅ Pass |
| AC-9 | Trace artifact refs | `artifact_refs` array present with valid `artifact_type` and `artifact_key` | ✅ Pass |
| AC-10 | Detail shape (persona) | `/ops/agent-detail/{entity_id}` returns valid response with `PersonaDetail` variant | ✅ Pass |
| AC-11 | Detail shape (officer) | Same endpoint returns valid response with `OfficerDetail` variant | ✅ Pass |
| AC-12 | Detail shape (arbiter) | Same endpoint returns valid response with `ArbiterDetail` variant | ✅ Pass |
| AC-13 | Detail shape (subsystem) | Same endpoint returns valid response with `SubsystemDetail` variant | ✅ Pass |
| AC-14 | Detail not found | Unknown `entity_id` returns 404 with `ENTITY_NOT_FOUND` error envelope | ✅ Pass |
| AC-15 | Detail bounded payload | `purpose` ≤ 500 chars, `RecentParticipation` array ≤ 5 entries — proven by test | ✅ Pass |
| AC-16 | Detail graceful degradation | Health source unavailable → endpoint still returns with degraded `data_state`, not 500 | ✅ Pass |
| AC-17 | Detail recent_warnings | `recent_warnings` is a typed array, not freeform prose | ✅ Pass |
| AC-18 | ResponseMeta consistency | Both endpoints include valid `ResponseMeta` with correct `version`, `generated_at`, `data_state` | ✅ Pass |
| AC-19 | Error envelope | All HTTP errors from both endpoints use `OpsErrorEnvelope` — no freeform string `detail` | ✅ Pass |
| AC-20 | No raw dumps (negative) | Neither endpoint returns raw prompt text, full LLM transcripts, or unbounded blobs — proven by content-length or field absence test | ✅ Pass |
| AC-21 | Existing endpoints unchanged | PR-OPS-2 roster and health endpoint tests still pass — zero regressions | ✅ Pass |
| AC-22 | No new persistence | No SQLite, no new database, no new file-write operations — read-side projection only | ✅ Pass |
| AC-23 | Contract doc updated | `AGENT_OPS_CONTRACT.md` §6 promoted from "reserved" to full contract — shapes match implementation | ✅ Pass |
| AC-24 | Envelope consistency | Both new endpoints use flat `ResponseMeta & {}` pattern matching PR-OPS-2 — no `data`/`meta` wrapper | ✅ Pass |
| AC-25 | ID convention consistency | Both new endpoints use existing roster/health `entity_id` convention — no namespaced ID migration | ✅ Pass |

---

## 12. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1: Locate PR-OPS-2 backend patterns

```bash
# Find the router file(s) for /ops/ endpoints
grep -r "agent-roster\|agent-health\|/ops/" ai_analyst/ --include="*.py" -l

# Find the Pydantic response models
grep -r "AgentRosterResponse\|AgentHealthSnapshotResponse\|ResponseMeta\|OpsErrorEnvelope" ai_analyst/ --include="*.py" -l

# Find the test files
grep -r "agent_roster\|agent_health\|ops" ai_analyst/tests/ --include="*.py" -l
```

**Expected:** Router file, models file, test file(s) identified. Report exact paths.

**Report:** File paths, model inheritance style, router registration pattern, **exact envelope shape** (flat `ResponseMeta & {}` confirmed vs. any other pattern).

### Step 2: Confirm entity_id convention

```bash
# Examine what entity_id format roster/health actually returns
grep -r "entity_id\|\"id\"" ai_analyst/ --include="*.py" | grep -i "ops\|roster\|health" | head -20
```

**Expected:** Current `entity_id` format identified (plain slugs vs. namespaced `type:slug`).

**Report:** Exact ID convention in use. If namespaced, document the pattern. If plain, confirm.

### Step 3: Audit run artifact structure

```bash
# Find run_record.json output location
grep -r "run_record" ai_analyst/ --include="*.py" -l

# Examine the structure of run_record.json fields used for trace projection
grep -r "stage_trace\|analyst_results\|arbiter_meta\|run_record" ai_analyst/ --include="*.py" -l
```

**Expected:** `run_record.json` output path identified. Key fields for trace projection located — stages, analyst results, arbiter summary, artifact references.

**Report:** Artifact path, `run_record.json` top-level structure, available fields for stage ordering / participant extraction / arbiter summary, whether `dev_diagnostics.json` is co-located. Flag any gaps between spec assumptions and actual artifact shape.

### Step 4: Audit profile registry structure

```bash
# Find persona profile registry
grep -r "profile.*registry\|persona.*config\|PROFILE_REGISTRY" ai_analyst/ --include="*.py" -l

# Examine what metadata is available per entity
grep -r "display_name\|capabilities\|visual_family\|department" ai_analyst/ --include="*.py" | head -30
```

**Expected:** Registry module identified. Available metadata fields confirmed.

**Report:** Registry location, available fields per entity type, any gaps between spec assumptions and actual registry content.

### Step 5: Run baseline test suite

```bash
# Run existing PR-OPS-2 tests — confirm green baseline
python -m pytest ai_analyst/tests/ -k "agent_ops or ops" -v --tb=short
```

**Expected:** All PR-OPS-2 tests pass. Record count as baseline.

**Report:** Test count (N/N pass), any failures, baseline number.

### Step 6: Propose smallest patch set

Based on Steps 1–5, report:

1. **Files to create** — new response models, new router endpoints, new test files. One-line description + estimated line delta per file.
2. **Files to modify** — existing router registration, any shared model files. One-line description + estimated line delta.
3. **Files with no changes expected** — pipeline code, existing roster/health endpoints, scheduler, config files.
4. **Assumption corrections** — any spec assumptions that don't match the codebase (field names, file paths, data shapes, ID conventions, envelope patterns).
5. **Smallest safe option** — if the diagnostic reveals that agent-trace projection requires changes to the pipeline's output format, **flag before proceeding**. The spec assumes existing artifacts are sufficient.

---

## 13. Implementation Constraints

### 13.1 General rule

Follow the same backend patterns established by PR-OPS-2 unless the new endpoint requirements force a deviation. If a deviation is needed, document it in the diagnostic findings before proceeding.

### 13.1b Implementation sequence

1. **Create response models** for `AgentTraceResponse` and `AgentDetailResponse` (Pydantic)
   - Verify: models import cleanly, no circular dependencies
2. **Implement `/runs/{run_id}/agent-trace` endpoint** with artifact-based runtime projection logic and deterministic fixture-based tests
   - Verify: PR-OPS-2 tests still pass (N/N)
3. **Write trace endpoint tests** (AC-1 through AC-9, AC-18, AC-19, AC-20, AC-24, AC-25)
   - Gate: all new tests pass + PR-OPS-2 baseline preserved
4. **Implement `/ops/agent-detail/{entity_id}` endpoint** with artifact-based runtime projection logic (registry + health + run artifacts) and deterministic fixture-based tests
   - Verify: all trace tests + PR-OPS-2 tests still pass
5. **Write detail endpoint tests** (AC-10 through AC-17, AC-18, AC-19, AC-20, AC-24, AC-25)
   - Gate: all new tests pass + all previous tests pass
6. **Add regression safety tests** (AC-21, AC-22)
   - Final gate: full test suite green (PR-OPS-2 baseline + all new tests)
7. **Update `AGENT_OPS_CONTRACT.md`** — promote §6 to full contract (AC-23)
   - Verify: no contradictions with existing contract sections

### 13.2 Code change surface

**New files (expected):**
- Response models file for trace + detail types
- Router endpoints for the two new routes (may be same file as PR-OPS-2 router — diagnostic decides)
- Projection/service helpers for run artifact reading and entity detail assembly
- Test file(s) for new endpoints

**Modified files (expected):**
- Router registration (if endpoints are added to existing router)
- `AGENT_OPS_CONTRACT.md` (§6 promotion)

**No changes expected to:**
- Existing roster/health endpoints or models
- Analysis pipeline code
- Run artifact generation logic
- Scheduler / orchestration code
- Frontend code (that is PR-OPS-5)
- Any config files outside the agent_ops scope

**Scope flag:** If the diagnostic reveals that run artifacts lack fields needed for the trace projection, flag before proceeding. Do not modify the pipeline — propose a degraded trace shape that works with existing artifacts.

### 13.3 Out of scope (repeated for agent prompt clarity)

- No frontend wiring (PR-OPS-5)
- No new persistence layer
- No mutation endpoints
- No SSE / WebSocket / live-push
- No raw prompt dumps or unbounded payloads
- No new top-level module
- No SQLite or database layer
- No scheduler changes
- No changes to existing PR-OPS-2 endpoints
- No namespaced ID migration

---

## 14. Contract Test Checklist

Explicit test coverage requirements for PR-OPS-4, following the PR-OPS-2 pattern (§7 of `AGENT_OPS_CONTRACT.md`).

### 14.1 Agent trace — response shape tests

- [ ] Returns valid `AgentTraceResponse` with all required fields
- [ ] `ResponseMeta` fields present and correctly typed (flat envelope — not `data`/`meta`)
- [ ] `stages` array is non-empty for a completed run
- [ ] `stages` ordered by ascending `stage_index`
- [ ] `summary` block contains valid counts and arbiter_override flag
- [ ] `TraceParticipant` contains all required fields with correct types
- [ ] `TraceEdge` contains all required fields with correct types
- [ ] `ArbiterTraceSummary` present for runs that reached arbiter stage
- [ ] `artifact_refs` array present with valid entries

### 14.2 Agent trace — missing/not-found behavior

- [ ] Unknown `run_id` returns 404 with `OpsErrorEnvelope` containing `RUN_NOT_FOUND`
- [ ] Malformed run artifacts return 422 with `RUN_ARTIFACTS_MALFORMED`
- [ ] Error responses use `OpsErrorEnvelope` — not freeform string `detail`

### 14.3 Agent trace — ordered trace semantics

- [ ] `stage_index` values are monotonically increasing
- [ ] `stage_key` is present and non-empty for each stage
- [ ] `participant_ids` in each stage reference valid roster entities
- [ ] Stages with `status: "skipped"` have empty or absent timing fields

### 14.4 Agent trace — trace edge validity

- [ ] Every `from` in `trace_edges` maps to a roster `id`
- [ ] Every `to` in `trace_edges` maps to a roster `id`
- [ ] `type` values are within the allowed enum (`considered_by_arbiter`, `skipped_before_arbiter`, `failed_before_arbiter`, `override`)
- [ ] `stage_index` on edges (when present) references a valid stage

### 14.5 Agent trace — arbiter override indicators

- [ ] `ArbiterTraceSummary` is `null` when run did not reach arbiter
- [ ] `override_applied` is explicit — not inferred
- [ ] `override_count` matches length of `overridden_entity_ids`
- [ ] `overridden_entity_ids` cross-reference participants with `contribution.was_overridden: true`
- [ ] `was_overridden: false` proven for participants not in the override list (negative test)

### 14.6 Agent detail — success shape per variant

- [ ] Persona entity returns `AgentDetailResponse` with `type_specific.variant === "persona"`
- [ ] Officer entity returns response with `type_specific.variant === "officer"`
- [ ] Arbiter entity returns response with `type_specific.variant === "arbiter"`
- [ ] Subsystem entity returns response with `type_specific.variant === "subsystem"`
- [ ] `entity_type` field matches `type_specific.variant` (consistency check)
- [ ] `EntityIdentity`, `EntityStatus`, `EntityDependency`, `RecentParticipation` shapes validated

### 14.7 Agent detail — unknown entity behavior

- [ ] Unknown `entity_id` returns 404 with `OpsErrorEnvelope` containing `ENTITY_NOT_FOUND`
- [ ] Error response uses `OpsErrorEnvelope` — not freeform string `detail`

### 14.8 Agent detail — department/type consistency

- [ ] `department` field matches roster `department` for the same entity
- [ ] `entity_type` matches roster `type` for the same entity
- [ ] `identity.visual_family` matches roster `visual_family`

### 14.9 Bounded payload / no raw dump tests

- [ ] `contribution.summary` does not exceed 500 characters (trace)
- [ ] `contribution.override_reason` does not exceed 300 characters
- [ ] `identity.purpose` does not exceed 500 characters (detail)
- [ ] `RecentParticipation` array contains ≤ 5 entries
- [ ] `recent_warnings` array contains ≤ 10 entries
- [ ] `arbiter_summary.dissent_summary` does not exceed 500 characters
- [ ] No field contains raw LLM prompt text or full transcript content (content pattern assertion)

### 14.10 Envelope and meta consistency

- [ ] Both endpoints include `version`, `generated_at`, `data_state` in `ResponseMeta`
- [ ] `data_state` values are within the allowed enum for each endpoint
- [ ] `generated_at` is a valid ISO 8601 timestamp
- [ ] Both endpoints use flat `ResponseMeta & {}` pattern — no `data`/`meta` wrapper

### 14.11 Graceful degradation tests

- [ ] Agent-detail with health source unavailable returns response with degraded `data_state`
- [ ] Agent-detail with health unavailable does NOT return 500
- [ ] Agent-trace for a partially completed run returns `run_status: "partial"` with available stages

### 14.12 Regression safety

- [ ] All PR-OPS-2 roster endpoint tests still pass
- [ ] All PR-OPS-2 health endpoint tests still pass
- [ ] No new file-write operations introduced (read-side only assertion)
- [ ] Entity IDs in new endpoints match roster/health convention (no namespace migration)

---

## 15. Success Definition

PR-OPS-4 is done when: both `/runs/{run_id}/agent-trace` and `/ops/agent-detail/{entity_id}` return valid, typed, bounded responses conforming to the contract shapes defined in §6–§7; all 25 acceptance criteria pass with deterministic fixture-based tests; PR-OPS-2 baseline tests show zero regressions; `AGENT_OPS_CONTRACT.md` §6 is promoted from reserved to full contract; both new endpoints use flat `ResponseMeta` envelope matching PR-OPS-2; entity IDs match existing convention; and no new persistence, mutation, or pipeline changes have been introduced — no SQLite → no new top-level module.

---

## 16. Documentation closure

This PR must update:

- `AGENT_OPS_CONTRACT.md` — promote §6 from reserved to full contract
- `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row
- `repo_map.md` — if new backend files are introduced
- `technical_debt.md` — if projection shortcuts or temporary assumptions are added

---

## 17. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| PR-OPS-1 | Contract docs (roster + health) | ✅ Done |
| PR-OPS-2 | Backend: roster + health endpoints | ✅ Done |
| PR-OPS-3 | Frontend: Agent Ops workspace shell | ✅ Done |
| Phase 6 | Core product lane (PR-UI-0 through PR-UI-6) | ✅ Done |
| **PR-OPS-4** | **Backend: agent-trace + agent-detail endpoints** | **✅ Complete** |
| PR-OPS-5 | Frontend: wire Agent Ops to new endpoints | ⏳ Blocked on PR-OPS-4 |

---

## 18. Diagnostic Findings

### PR-OPS-4a Diagnostic (2026-03-15)

**File paths found:**
- Router: `ai_analyst/api/routers/ops.py`
- Models: `ai_analyst/api/models/ops.py` (shared), `ai_analyst/api/models/ops_trace.py` (new)
- Service: `ai_analyst/api/services/ops_trace.py` (new)
- Tests: `tests/test_ops_trace_endpoints.py` (new)
- Fixtures: `tests/fixtures/sample_run_record.json`, `tests/fixtures/sample_audit_log.jsonl`
- Run artifacts: `ai_analyst/output/runs/{run_id}/run_record.json` (primary)
- Audit log: `ai_analyst/logs/runs/{run_id}.jsonl` (secondary — analyst stances, override detail)

**ID convention confirmed:** Plain lowercase slugs (e.g. `persona_default_analyst`, `arbiter`). No namespace prefix.

**Envelope pattern confirmed:** Flat `ResponseMeta` inheritance — `AgentTraceResponse(ResponseMeta)`. No data/meta wrapper.

**Assumption corrections:**
1. `run_record.json` lacks per-analyst stances/confidence — audit log used as secondary source
2. `run_record.json` stores bare persona names (e.g. `default_analyst`) — mapping to `persona_default_analyst` done in trace service
3. No per-stage `started_at`/`finished_at` timestamps — `duration_ms` used instead
4. `_dev_diagnostics.jsonl` is a single file for all runs, not per-run — skipped entirely

**Artifact shape surprises:**
- Arbiter block has `verdict`/`confidence` but no `risk_override_applied` — that field is only in `FinalVerdict` via audit log
- Analyst entries in run_record have no stance/bias — only persona name, status, model, provider

**Regression gate:** 55/55 PR-OPS-2 baseline preserved → 126/126 total (55 baseline + 71 new trace tests)

**Patch set (PR-OPS-4a):**
| File | Action | Lines |
|------|--------|-------|
| `ai_analyst/api/models/ops_trace.py` | Created | 109 |
| `ai_analyst/api/services/ops_trace.py` | Created | 308 |
| `ai_analyst/api/routers/ops.py` | Modified | +30 |
| `tests/fixtures/sample_run_record.json` | Created | 48 |
| `tests/fixtures/sample_audit_log.jsonl` | Created | 1 |
| `tests/test_ops_trace_endpoints.py` | Created | 491 |
| `docs/PR_OPS_4_SPEC_FINAL.md` | Updated | AC flips, §18 |

---

## 19. Follow-on PR

After this backend PR lands:
- draft and implement PR-OPS-5
- wire Agent Ops workspace to: run mode, health mode, detail sidebar, trace visualization

No PR-OPS-5 wiring should begin against unstable endpoint shapes before this contract lands.

---

## 20. Appendix A — Recommended Agent Prompt

```
Read `docs/PR_OPS_4_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 12 and report findings
before changing any code:

1. Locate PR-OPS-2 backend patterns (router, models, tests — exact paths)
2. Confirm entity_id convention (plain slugs vs namespaced — report exact format)
3. Confirm envelope style (flat ResponseMeta & {} vs data/meta wrapper)
4. Audit run artifact structure (run_record.json as primary source, dev_diagnostics.json as optional enrichment)
5. Audit profile registry structure (available metadata fields per entity type)
6. Run baseline test suite — confirm green, record count
7. Propose smallest patch set: files, one-line description, estimated line delta
8. Flag if run artifacts lack fields needed for trace projection

Hard constraints:
- Follow PR-OPS-2 backend patterns unless deviation is forced and documented
- AGENT_OPS_CONTRACT.md shared types (ResponseMeta, OpsErrorEnvelope, DepartmentKey) are locked
  — reuse, do not redefine
- Flat ResponseMeta envelope — do not introduce data/meta wrapper (§5.1)
- Existing entity_id convention — do not introduce namespaced IDs (§5.2)
- No raw prompt dumps, no unbounded payloads — bounded payload rules in §6.11 and §7.10
- No mutation, no new persistence, no pipeline changes
- No frontend wiring — that is PR-OPS-5
- No SQLite, no new top-level module, no scheduler
- Deterministic tests only — no live provider dependency in CI
- If run artifacts require pipeline changes, flag before proceeding

Do not change any code until the diagnostic report is reviewed and the
patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/PR_OPS_4_SPEC.md` — mark ✅ Complete, flip all AC cells,
   populate §18 Diagnostic Findings with: file paths found, assumption
   corrections, patch set, regression gate results, ID convention confirmed,
   envelope pattern confirmed, any artifact shape surprises
2. `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row,
   update next actions (PR-OPS-5 unblocked), update debt register if applicable
3. `docs/ui/AGENT_OPS_CONTRACT.md` — promote §6 from reserved to full contract,
   add endpoint specs matching implementation
4. Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`,
   `AI_ORIENTATION.md` — update only if this phase changed architecture,
   structure, or debt state
5. Cross-document sanity check: no contradictions, no stale phase refs
6. Return Phase Completion Report (see Workflow E.8)

Commit all doc changes on the same branch as the implementation.
```

---

## 21. Appendix B — Spec Quality Checklist

- [x] Status header says "Spec drafted — implementation pending"
- [x] Roadmap status for this phase says "⏳ Spec drafted — implementation pending"
- [x] All AC status cells say "⏳ Pending"
- [x] §Diagnostic Findings says "*To be populated...*"
- [x] Out of scope list names at least 5 hard constraints (12 listed in §4)
- [x] At least one negative-case AC (AC-20: no raw dumps; AC-5: arbiter null; §14.5 negative override test)
- [x] Implementation sequence has at least two regression gates (gates at steps 3, 5, 6)
- [x] Agent prompt footer includes doc-close instruction referencing Workflow E
- [x] Agent prompt footer includes debt register update instruction
- [x] Agent prompt says "Read [spec] in full before starting"
- [x] "Smallest safe option" language present in diagnostic protocol (Step 6)
- [x] No spec table values presented as fact before diagnostic confirms them (file paths marked TBC, ID convention marked "confirm from diagnostic")
- [x] Bounded payload limits specified with exact numbers (§6.11, §7.10)
- [x] Envelope style decision locked and documented (§5.1)
- [x] Entity ID convention decision locked and documented (§5.2)

---

## 22. One-sentence summary

PR-OPS-4 adds two governed, read-only, UI-ready observability endpoints — one run-centric, one entity-centric — that let Agent Ops inspect how a run unfolded and what each agent is, without turning the backend into an uncontrolled engine-internals dump.
