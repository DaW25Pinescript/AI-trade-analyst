# OBJECTIVE — PR-OPS-1

## Title
PR-OPS-1 — Agent Operations Endpoint Contract Spec

## Goal
Define the backend → UI contract for the first two Agent Operations endpoints (`/ops/agent-roster` and `/ops/agent-health`) before any implementation begins. This is a docs-only PR that locks response shapes, `data_state` semantics, transport error envelopes, degraded/empty behavior, and cross-endpoint join rules so that PR-OPS-2 (backend implementation) and PR-OPS-3 (React workspace) build against an explicit contract rather than ad hoc discovery.

This follows the same discipline the repo used for the core UI: audit → contract → workspace blueprint → implementation. Agent Ops gets a contract before it gets code.

## What success looks like
By the end of this PR:

1. A standalone contract extension document exists at `docs/ui/AGENT_OPS_CONTRACT.md` defining `/ops/agent-roster` and `/ops/agent-health` with locked response shapes.
2. `UI_CONTRACT.md` is updated with an Agent Ops extension section referencing the new contract document.
3. Every response field, `data_state` value, transport error envelope, and degraded behavior is specified before implementation.
4. The contract explicitly states that `/ops/agent-health` is poll-based snapshot only in MVP — no SSE, no WebSocket.
5. The contract references the existing Agent Ops schema (`agent_operations_workspace.schema.refined.md`) as the design source while being implementation-ready.
6. The two Phase 7 endpoints (`/runs/{run_id}/agent-trace` and `/ops/agent-detail/{entity_id}`) are acknowledged as future but NOT contracted in this PR.
7. The contract explicitly states how health items join to roster entities and what happens when health is missing for a known roster entry.

## Why this PR exists
The UI Re-Entry Phase Plan (Phase 4) requires the endpoint contract spec to be documented before backend implementation begins. The plan explicitly says: "Response shape locked before implementation."

The repo's existing Agent Ops schema (`agent_operations_workspace.schema.refined.md`) is a design-level document. PR-OPS-1 converts the relevant portions into an implementation-ready contract that the backend team (PR-OPS-2) and frontend team (PR-OPS-3) both build against.

## Not the goal of this PR
- No backend code changes
- No new Python endpoints
- No React/UI implementation
- No Phase 7 endpoint contracts (trace + detail — those come later)
- No changes to core UI workspaces
- No changes to existing triage/journey/analysis endpoint contracts
