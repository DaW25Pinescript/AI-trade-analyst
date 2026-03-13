# PR-OPS-2 Spec Package

This package defines **PR-OPS-2** for AI Trade Analyst.

## Scope
Implement the first two Agent Operations backend endpoints as **read-only projections**:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

## Out of scope

- No frontend/UI work
- No Agent Ops React wiring
- No `GET /runs/{run_id}/agent-trace`
- No `GET /ops/agent-detail/{entity_id}`
- No SSE / websocket / streaming
- No orchestration or control-plane behavior
- No prompt editing, config editing, or runtime mutation surfaces

## Expected output
A backend PR that adds deterministic FastAPI endpoints, projection/service logic, serializers, and tests that conform to the contract locked in `docs/ui/AGENT_OPS_CONTRACT.md` and the cross-reference in `docs/ui/UI_CONTRACT.md`.

## Files in this package

- `PR_OPS_2_PROMPT.md`
- `OBJECTIVE.md`
- `CONSTRAINTS.md`
- `CONTRACTS.md`
- `IMPLEMENTATION_PLAN.md`
- `ACCEPTANCE_TESTS.md`
- `README.md`
