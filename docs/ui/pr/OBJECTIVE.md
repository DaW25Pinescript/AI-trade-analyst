# OBJECTIVE — PR-UI-1

## Title
PR-UI-1 — React App Shell + Triage Board Route

## Goal
Establish the **React + TypeScript + Tailwind** frontend foundation for the AI Trade Analyst UI re-entry lane and prove that it can coexist with the current legacy `app/` surface.

This PR is intentionally **foundation-only**. It should not attempt to deliver the real Triage Board yet. It exists to create the stable shell that PR-UI-2 will build upon.

## What success looks like
By the end of this PR:

1. A React application exists in the repo in a clearly defined location.
2. The filesystem/repo-shape decision is locked and documented.
3. The React app builds and serves successfully.
4. The React app can coexist with the current `app/` during migration.
5. Routing exists and at minimum supports a Triage route.
6. A typed API client layer exists and can call existing backend endpoints.
7. A basic workspace shell/layout exists.
8. There is a placeholder Triage route, but **no real data rendering yet**.
9. Build/typecheck/test scripts exist for the new frontend lane.
10. Documentation closure for PR-UI-1 is completed.

## Why this PR exists
The UI phase plan explicitly defines Phase 1 as:
- base React/TS/Tailwind setup
- build tooling
- routing framework
- typed API client layer
- state management scaffolding
- Triage Board route placeholder

It also requires the **frontend repo-shape** decision to be locked in this PR and not revisited per workspace.

## Not the goal of this PR
This PR does **not** aim to:
- render live Triage Board data
- implement shared component extraction
- implement Agent Operations
- add new backend endpoints
- add streaming/SSE/WebSocket behavior
- migrate the full legacy UI
