# PR-OPS-1 Spec Package — Refined

This package defines **PR-OPS-1 — Agent Operations Endpoint Contract Spec** for the AI Trade Analyst repo.

Contents:
- `PR_OPS_1_PROMPT.md` — paste-ready implementation prompt for Claude/Codex
- `OBJECTIVE.md` — what this PR must achieve
- `CONSTRAINTS.md` — hard boundaries and non-goals
- `CONTRACTS.md` — endpoint contract specifications to be documented
- `IMPLEMENTATION_PLAN.md` — recommended document creation sequence
- `ACCEPTANCE_TESTS.md` — merge criteria and verification checklist

This refined version locks five contract decisions up front:
1. `docs/ui/AGENT_OPS_CONTRACT.md` is the required extension document path
2. HTTP error payloads use `OpsErrorEnvelope = { detail: OpsError }`
3. department typing uses a canonical `DepartmentKey` union, not freeform `string`
4. governance/officer layers are arrays, with current expected counts documented in prose rather than tuple syntax
5. roster ↔ health join behavior is explicit

This PR follows the locked UI re-entry sequence:
1. PR-UI-0 — governance unlock ✅
2. PR-UI-1 — React shell ✅
3. PR-UI-2 — Triage Board MVP ✅
4. PR-UI-3 — shared component extraction ✅
5. **PR-OPS-1 — Agent Ops contract spec (this PR)**
6. PR-OPS-2 — Agent Ops backend (roster + health endpoints)
7. PR-OPS-3 — Agent Ops React workspace MVP

PR-OPS-1 is **docs only** — zero code changes. It defines the endpoint contracts that PR-OPS-2 implements and PR-OPS-3 consumes.

Use this package together with:
- `docs/ui/agent_operations_workspace.schema.refined.md` (design-level source)
- `docs/ui/agent_operations_component_adapter_plan.refined.md` (frontend plan)
- `docs/ui/DESIGN_NOTES.md` §5 (Agent Ops governance decisions)
- `docs/ui/UI_CONTRACT.md` (shared conventions)
- `docs/specs/ui_reentry_phase_plan.md` Phase 4
