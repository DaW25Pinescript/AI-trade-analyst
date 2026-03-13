# PR-OPS-3 Spec Package

This package defines **PR-OPS-3 — Agent Operations React Workspace MVP**.

PR-OPS-3 is the first frontend implementation of the Agent Operations workspace. It is a **React UI-only** PR that consumes the real backend endpoints delivered in PR-OPS-2:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

The MVP is intentionally limited to **Org / Structure mode**. It should render the system architecture, health status, relationships, and degraded trust conditions using the shared component system proven in the Triage lane.

It must **not** implement:

- run trace views
- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`
- prompt editing
- orchestration / control actions
- SSE / WebSocket / live stream behavior

Files:

- `PR_OPS_3_PROMPT.md` — paste-ready implementation prompt
- `OBJECTIVE.md`
- `CONSTRAINTS.md`
- `CONTRACTS.md`
- `IMPLEMENTATION_PLAN.md`
- `ACCEPTANCE_TESTS.md`
