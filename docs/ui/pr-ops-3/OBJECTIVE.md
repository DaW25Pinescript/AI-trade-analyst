# OBJECTIVE — PR-OPS-3

## Title
PR-OPS-3 — Agent Operations React Workspace MVP

## Goal
Implement the first live React workspace for **Agent Operations** in `ui/`, using the existing Agent Ops backend endpoints from PR-OPS-2.

This PR should render a trustworthy operator-facing view of the system's current structure and health by consuming:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

## Product framing
Agent Operations is an **operator observability / explainability / trust workspace**.

Its north-star question is:

> **Why should I trust this system right now?**

The MVP should answer that question through a clean structural view of the current agent roster, the current health snapshot, and explicit degraded / unavailable conditions.

## MVP scope
Implement **Org / Structure mode only**:

- workspace route renders real roster and health data
- hierarchy is visible:
  - governance layer
  - officer layer
  - department groupings
- each entity displays current health state
- relationships can be inspected visually or through a selected-node detail panel
- degraded conditions are surfaced clearly
- selection state is supported for detail inspection
- route is feature-flagged or clearly operator-only if the repo already uses that convention

## Non-goals
This PR does **not** implement:

- run-level forensics
- trace timelines
- entity drilldown endpoint consumption
- activity/event stream backed by new endpoints
- orchestration controls
- prompt editing
- model switching
- SSE / WebSocket / streaming
- backend changes to the Agent Ops contracts

## Success criteria
PR-OPS-3 succeeds if:

1. The Agent Operations route renders real data from the shipped backend endpoints.
2. The workspace can represent healthy, degraded, unavailable, loading, and error states honestly.
3. The layout clearly shows governance, officers, departments, and relationships.
4. The UI reuses the existing shared component foundation where appropriate.
5. No trace/detail or control-plane features leak into the MVP.
