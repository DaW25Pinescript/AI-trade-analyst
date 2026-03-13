# PR-OPS-2 — IMPLEMENT BACKEND ROSTER + HEALTH ENDPOINTS

Implement **PR-OPS-2** for AI Trade Analyst.

You are implementing the first backend slice of Agent Operations after the contract was locked in PR-OPS-1.

## Goal
Add two **read-only** FastAPI endpoints as deterministic projection surfaces:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

These must conform to:
- `docs/ui/AGENT_OPS_CONTRACT.md`
- `docs/ui/UI_CONTRACT.md` §10.6

## Product framing
Agent Operations is an **observability / explainability / trust** workspace.

These endpoints are not a control plane.
Do not add orchestration, prompt editing, model switching, config mutation, or chat-with-agents behavior.

## Before writing any code
Read the controlling contract:
- `docs/ui/AGENT_OPS_CONTRACT.md` — **the single source of truth** for response shapes

Then inspect existing data sources:

**For roster (config/structural truth):**
- `analyst/personas.py` — persona definitions, names, capabilities
- `analyst/arbiter.py` — arbiter role and governance behavior
- `analyst/enums.py` — centralised enums (TD-5 output)
- `ai_analyst/core/` — any persona registry or config
- `llm_routing.yaml` — model/provider assignments
- any config/definition files that enumerate the system's agents

**For health (observability/runtime evidence):**
- Obs P2 structured event emitters in `ai_analyst/api/main.py`, `ai_analyst/api/routers/journey.py`, `ai_analyst/graph/pipeline.py`
- Scheduler events in `market_data_officer/scheduler.py`
- Feeder ingest events in `macro_risk_officer/ingestion/feeder_ingest.py`
- `app.state` or equivalent runtime state in the FastAPI app
- Existing `/feeder/health` and `/metrics` endpoints for reference patterns

Document what exists before deciding how to project it.

## Hard scope
### Implement
- route wiring for the two GET endpoints
- projection/service logic (separate from route handlers)
- response models / serializers
- deterministic backend tests
- docs closure

### Do not implement
- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`
- any frontend/UI work
- SSE / websocket / streaming
- any mutation endpoints

## Key contract requirements
### `/ops/agent-roster`
Implement `AgentRosterResponse` with:
- `meta`
- `governance_layer`
- `officer_layer`
- `departments`
- `relationships`

Rules:
- roster cannot be empty
- departments must use the contracted `DepartmentKey`
- relationship ids must resolve to roster ids
- v1 expects 2 governance + 2 officer entities, but do not implement tuple-only transport typing
- derive from durable structural truth, not transient log events

### `/ops/agent-health`
Implement `AgentHealthSnapshotResponse` with:
- `meta`
- `entities`

Rules:
- poll-based snapshot only
- preserve separate `run_state` and `health_state`
- empty `entities` is valid on fresh start
- degraded structured output is allowed when evidence is partial
- entities with no health signals get `health_state: "unavailable"`, not omitted
- derive from existing observability evidence, not invented metrics

### Shared
- all `AgentHealthItem.entity_id` values must map to roster ids
- HTTP errors must use `OpsErrorEnvelope = { detail: OpsError }`

## Python implementation notes
- `EntityRelationship` has a `from` field — Python reserved word. Use `from_` with `Field(alias="from")` and `model_config = ConfigDict(populate_by_name=True)` so JSON serialization produces `"from"`.
- `DepartmentKey` should be a `StrEnum` or `Literal` union — not a freeform string.
- Use `HTTPException(detail=OpsError(...).model_dump())` to produce `{ "detail": { ... } }`.
- Keep projection logic in a service layer, not inline in route handlers.
- Inspect existing routers in `ai_analyst/api/routers/` for repo conventions before creating the new router.

## Contract evolution
If the implementation discovers a genuine mismatch or improvement needed in the locked contract (e.g. error envelope fields, response meta nesting), **do not silently deviate**. Instead:
- implement the improved shape
- update `docs/ui/AGENT_OPS_CONTRACT.md` to match
- document the change explicitly in the PR description
- flag it for PR-OPS-3 awareness

## Deliverables
1. backend implementation of both routes
2. projection/service layer
3. serializer/contract models
4. deterministic tests covering all §7 contract test priorities
5. progress/spec doc updates marking PR-OPS-2 complete
6. any contract evolution documented

## Acceptance bar
The PR is successful only if:
- both endpoints exist
- payloads match the locked docs contract (or evolved contract with explicit documentation)
- health↔roster join rule is enforced
- degraded and empty-valid cases are tested
- error envelope is tested
- `run_state` and `health_state` are separate dimensions
- no UI files change
- no extra Agent Ops routes are introduced
- all existing tests pass

## Output format
When done, return:
1. summary
2. files changed
3. data sources used (roster: what config; health: what observability data)
4. implementation notes (layering, any static roster mapping decisions)
5. test results (new + regression check)
6. any contract mismatches discovered and how they were handled
7. suggested commit message
8. suggested PR description
