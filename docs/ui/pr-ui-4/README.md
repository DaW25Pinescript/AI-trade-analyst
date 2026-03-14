# PR-UI-4 Spec Package — Journey Studio

This package defines **PR-UI-4**, the next frontend phase after:
- PR-UI-1 — React shell
- PR-UI-2 — Triage Board MVP
- PR-UI-3 — shared component hardening
- PR-OPS-3 — Agent Operations React MVP

## Purpose

Implement the first **core product workflow workspace** after Triage:
**Journey Studio**.

This PR should reopen the primary user path of the product:

**Triage Board → Journey Studio → Analysis Run → Journal & Review**

## Package contents

- `PR_UI_4_PROMPT.md` — paste-ready implementation prompt
- `OBJECTIVE.md`
- `CONSTRAINTS.md`
- `CONTRACTS.md`
- `IMPLEMENTATION_PLAN.md`
- `ACCEPTANCE_TESTS.md`

## Scope summary

PR-UI-4 is a **frontend-only workspace implementation** that should:

- add the first real **Journey Studio** page
- use **existing backend endpoints only**
- reuse the shared component system already proven in Triage and Agent Ops
- preserve the contract-first approach
- avoid speculative workflow expansion

## Explicitly out of scope

- no backend endpoint creation
- no Agent Ops expansion
- no trace/detail work
- no SSE/WebSocket/live streaming
- no Journal & Review implementation
- no broad redesign of Triage or Ops
- no Phase 7 forensic features
