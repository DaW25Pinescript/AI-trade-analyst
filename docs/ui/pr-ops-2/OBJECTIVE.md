# OBJECTIVE — PR-OPS-2

Implement the first two Agent Operations backend endpoints as deterministic, read-only projection surfaces:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

This PR is the first runtime implementation step after PR-OPS-1 locked the docs contract. The goal is to expose trustworthy operator-facing observability data without creating a new control plane, changing orchestration behavior, or introducing speculative backend infrastructure.

## What success looks like

1. Both endpoints exist and return payloads conforming to `docs/ui/AGENT_OPS_CONTRACT.md`.
2. The endpoints are backed by existing repo truth wherever possible:
   - roster derived from canonical role/config/project truth
   - health derived from current observability/runtime evidence
3. The endpoints are read-only and deterministic.
4. Error responses use the contracted `OpsErrorEnvelope`.
5. Tests cover happy path, degraded path, empty/initial path where valid, and contract-shape invariants.
6. No UI files change.
7. No trace/detail endpoints are introduced.

## Product framing

These endpoints exist to support the future Agent Operations workspace as an **observability / explainability / trust** surface. They do not exist to provide orchestration, agent control, prompt editing, or runtime mutation.
