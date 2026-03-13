# OBJECTIVE — PR-UI-3

## Title
PR-UI-3 — Shared Component Extraction and Hardening

## Why this PR exists
PR-UI-2 delivered the first real React workspace: a working Triage Board on live backend data with state handling, trust strip, feeder health, typed hooks, and shared components.

That was the right move for proving the stack. The next move is **not** another workspace yet. The next move is to convert the initial success into a stable frontend foundation that future workspaces can reuse without copy-paste drift.

PR-UI-3 exists to:
- formalize the shared frontend layer created during PR-UI-2
- separate truly reusable primitives from triage-specific implementation details
- stabilize naming, prop contracts, and directory ownership
- improve test coverage around the shared surfaces
- preserve the working Triage Board while making the shared layer safe for reuse

## Success definition
PR-UI-3 is successful if:
1. The Triage Board still works with no functional regression.
2. Shared components/hooks/utilities are easier to locate, reason about, and reuse.
3. Triage-specific logic stays in the triage workspace unless reuse is justified.
4. Future workspaces have a clearer set of primitives to build on.
5. The PR introduces **no new backend surface area** and does not drift into Agent Ops or other workspace implementation.

## What this PR prepares for
- PR-OPS-1 — Agent Ops contract docs
- later React workspaces (Journey Studio, Analysis Run, Journal & Review)
- cleaner reuse of state badges, trust surfaces, layout shells, feedback states, and query conventions
