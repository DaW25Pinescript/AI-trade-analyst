# PR-UI-2 Spec Package

This package defines **PR-UI-2 — Triage Board MVP (real data)** for the AI Trade Analyst repo.

Contents:
- `PR_UI_2_PROMPT.md` — paste-ready implementation prompt for Codex/Claude
- `OBJECTIVE.md` — what this PR must accomplish
- `CONSTRAINTS.md` — hard scope boundaries and non-goals
- `CONTRACTS.md` — backend/UI contract assumptions and handling rules
- `IMPLEMENTATION_PLAN.md` — suggested repo changes and build order
- `ACCEPTANCE_TESTS.md` — required verification and merge bar

This PR follows the locked UI re-entry sequence:
1. PR-UI-0 — governance unlock
2. PR-UI-1 — React shell + routing + typed API scaffolding
3. **PR-UI-2 — Triage Board MVP on real endpoints**
4. PR-UI-3 — shared component extraction / hardening
5. PR-OPS-1+ — Agent Ops contract and backend work
