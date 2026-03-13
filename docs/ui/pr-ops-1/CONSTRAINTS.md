# CONSTRAINTS — PR-OPS-1

## Hard scope boundaries

### In scope
- Define the response contract for `GET /ops/agent-roster`
- Define the response contract for `GET /ops/agent-health`
- Specify `data_state` semantics for both endpoints
- Specify the transport error envelope and structured `OpsError` payload for both endpoints
- Specify empty/degraded/unavailable behavior
- Specify what backs each endpoint (config truth vs observability evidence)
- Specify the roster ↔ health join rule (`AgentHealthItem.entity_id` → `AgentSummary.id`)
- Update `UI_CONTRACT.md` with an Agent Ops extension reference
- Update progress hub and phase plan

### Out of scope
- No backend code — zero Python files created or modified
- No React/UI code — zero frontend files created or modified
- No Phase 7 endpoints (`/runs/{run_id}/agent-trace`, `/ops/agent-detail/{entity_id}`) — those are contracted separately
- No changes to existing core UI endpoint contracts (triage, journey, analysis, feeder)
- No SSE/WebSocket/streaming contract — `/ops/agent-health` is poll-based snapshot only
- No write endpoints — Agent Ops MVP is read-only

## Contract discipline
- Response shapes must be locked before PR-OPS-2 implements them
- Every field must have a type and a purpose
- Every endpoint must define success, empty, degraded, unavailable, and error behavior
- The contract must specify what the backend derives each response from (config? observability events? run artifacts?)
- The contract must explicitly choose `docs/ui/AGENT_OPS_CONTRACT.md` as the extension document location
- Do not copy the full schema design note verbatim — extract the implementation-ready portions and reference the design note for context

## Classification discipline
- Agent Ops remains Phase 3B — this contract does not promote it to Phase 3A
- Agent Ops endpoints are operator-lane surfaces, not product-homepage surfaces
- The contract must state that these endpoints do not exist until PR-OPS-2 merges
- The HTML prototype (`operations.html`) is NOT a contract source — the schema doc and this contract are

## Relationship to existing docs
- `agent_operations_workspace.schema.refined.md` is the design-level source for response shapes
- `agent_operations_component_adapter_plan.refined.md` is the frontend implementation plan — not modified in this PR
- `UI_CONTRACT.md` gets a new extension section, not a rewrite
- `DESIGN_NOTES.md` §5 (Agent Ops governance decisions) is the authoritative framing — not modified in this PR
