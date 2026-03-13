# OBJECTIVE — PR-UI-2

## Title
**PR-UI-2 — Triage Board MVP on real endpoints**

## Purpose
Convert the placeholder Triage route introduced in PR-UI-1 into a working **Triage Board MVP** rendered from real backend data.

This PR is the first proof that the React lane can consume the existing backend contract and render a trustworthy operator-facing workspace with correct loading, empty, stale, unavailable, demo-fallback, and error handling.

## Backend basis
Use only existing endpoints:
- `GET /watchlist/triage`
- `POST /triage`

No new backend endpoints. No backend schema changes.

## What this PR must deliver
- Render live triage data from `/watchlist/triage`
- Support a **Run Triage** action using `/triage`
- Display a board-level trust/freshness surface
- Show ranked triage rows/cards with click affordance
- Route row click to Journey placeholder route for now
- Handle all core UI states deterministically
- Introduce the first shared primitives needed by Triage, but only those genuinely required

## Why this PR exists
PR-UI-1 proved the frontend foundation. PR-UI-2 proves the stack against real backend data and becomes the real start of the shared component system.

## Definition of done
This PR is done when the Triage Board renders real backend data in the React app, the Run Triage action works, all major UI states are handled correctly, and the implementation remains contract-faithful without inventing backend semantics.
