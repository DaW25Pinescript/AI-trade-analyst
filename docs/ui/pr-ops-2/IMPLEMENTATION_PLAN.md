# IMPLEMENTATION PLAN — PR-OPS-2

## Goal
Ship the first Agent Ops backend implementation slice: roster + health endpoints as read-only projections.

## Recommended order

### 1. Read the controlling contract
Read `docs/ui/AGENT_OPS_CONTRACT.md` in full before writing any code. This is the single source of truth for response shapes.

### 2. Locate current backend API entry points
Identify where FastAPI routes for existing runtime/status/ops surfaces live.

Decide the clean route location for:
- `GET /ops/agent-roster`
- `GET /ops/agent-health`

Keep naming and router organization consistent with the existing API layout.

### 3. Inspect existing data sources
Before building projections, inspect what the repo already has:

**For roster (config/structural truth):**
- `analyst/personas.py` — persona definitions, names, capabilities
- `analyst/arbiter.py` — arbiter role and governance behavior
- `analyst/enums.py` — centralised verdict/confidence/alignment enums
- `ai_analyst/core/` — any persona registry or config definitions
- `llm_routing.yaml` — model/provider assignments per persona
- any config/definition files that enumerate the system's agents and their relationships

**For health (observability/runtime evidence):**
- Obs P2 structured event emitters in `ai_analyst/api/main.py`, `ai_analyst/api/routers/journey.py`, `ai_analyst/graph/pipeline.py`
- Scheduler events in `market_data_officer/scheduler.py`
- Feeder ingest events in `macro_risk_officer/ingestion/feeder_ingest.py`
- `app.state` or equivalent runtime state in the FastAPI app
- Existing `/feeder/health` and `/metrics` endpoints for reference patterns

Document what exists before deciding how to project it.

### 4. Create contract-facing schema / serializer layer
Add typed response models that exactly match the docs contract.

Prefer explicit serializer models over passing through raw internal objects. Note: `EntityRelationship` has a `from` field which is a Python reserved word — use `from_` with `Field(alias="from")` and appropriate model config.

### 5. Implement roster projection service
Create a small projection/service function that builds `AgentRosterResponse` from existing repo truth.

Responsibilities:
- construct governance layer entities
- construct officer layer entities
- construct department buckets via `DepartmentKey`
- construct explicit relationships
- validate internal consistency before returning response

### 6. Implement health projection service
Create a projection/service function that builds `AgentHealthSnapshotResponse` from current runtime/observability evidence.

Responsibilities:
- derive `entities` using known roster ids only
- preserve separate `run_state` and `health_state`
- support valid empty snapshot on fresh start
- support degraded-but-structured responses when health evidence is partial
- for entities with no health signals, return `health_state: "unavailable"` with null optionals — do not omit

### 7. Enforce roster ↔ health consistency
Add validation so the health response cannot emit orphan `entity_id` values.

### 8. Add FastAPI routes
Wire both services to the new GET routes. Keep projection logic out of route handlers.

### 9. Add deterministic tests
Cover all contract test priorities from `AGENT_OPS_CONTRACT.md` §7:

| Category | What to verify |
|----------|----------------|
| Roster response shape | Valid `AgentRosterResponse` with governance/officer/department structure |
| Department keys | Exactly four canonical `DepartmentKey` values |
| Roster layers | Arrays for governance/officer (v1: expect 2 each, documented in prose) |
| Relationships | Explicit array, all IDs resolve to roster entities |
| Roster error | Structured `OpsErrorEnvelope` on config failure |
| Roster data_state | Reflects config source freshness |
| Health response shape | Valid `AgentHealthSnapshotResponse` |
| State separation | `run_state` and `health_state` as separate fields per entity |
| Health↔roster join | `entity_id` values match roster `id` values |
| Empty health | Tolerates empty `entities` on fresh start |
| Health error | Structured `OpsErrorEnvelope` on aggregation failure |
| Health data_state | Reflects observability data freshness |
| Missing health | Missing health for known roster entity = valid, not error |

### 10. Docs closure
Update phase/progress docs to record PR-OPS-2 completion.

If the implementation evolves the error envelope shape or response structure from what was locked in PR-OPS-1, update `AGENT_OPS_CONTRACT.md` explicitly and document the change in the PR description.

## Design guidance

### Keep roster boring and stable
Roster should come from durable structural truth, not from whether something happened to emit a recent event.

### Keep health honest
Health should reflect evidence the system already has. Do not invent rich liveness semantics without supporting data.

### Favor explicit fallbacks
When evidence is missing, prefer contracted empty/degraded states over guessed values.
