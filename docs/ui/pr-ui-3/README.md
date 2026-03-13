# PR-UI-3 Spec Package

This package defines **PR-UI-3 — Shared Component Extraction and Hardening** for the AI Trade Analyst repo.

## Intent
PR-UI-3 follows the completed PR-UI-2 Triage Board MVP. Its job is to turn the first real React workspace into a **reusable, disciplined component system** without smuggling in new workspaces, new backend endpoints, or Agent Ops work.

## Files
- `PR_UI_3_PROMPT.md` — paste-ready implementation prompt for Codex/Claude
- `OBJECTIVE.md` — exact purpose and success definition
- `CONSTRAINTS.md` — hard scope boundaries and non-goals
- `CONTRACTS.md` — frontend architectural contracts and extraction rules
- `IMPLEMENTATION_PLAN.md` — suggested execution sequence and repo-shape decisions
- `ACCEPTANCE_TESTS.md` — merge criteria and validation checklist

## Scope Summary
This PR should:
- harden the shared UI layer created during PR-UI-2
- extract reusable primitives, hooks, adapters, and conventions where justified by current code
- keep the Triage Board working with no behavior regression
- prepare the codebase for PR-OPS-1 and later React workspaces

This PR should **not**:
- add new backend endpoints
- implement Agent Ops UI
- implement Journey / Analysis / Journal / Review workspaces
- add SSE/WebSocket/live-stream behavior
- perform a design-system vanity refactor disconnected from current code
