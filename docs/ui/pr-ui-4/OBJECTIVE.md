# OBJECTIVE — PR-UI-4

## Primary objective

Implement **Journey Studio** as the first core product workflow workspace after Triage.

This PR should establish the beginning of the guided trade-construction path in the new React UI, using existing backend surfaces and the already-proven component foundation.

## Why this PR exists

The repo now has:
- a working React shell
- a live Triage Board
- a hardened shared component system
- a live Agent Operations MVP

What is still missing is the first real **decision workspace** in the main product lane.

Journey Studio should become the first place where a user moves from “interesting candidate” toward a structured trade-planning flow.

## Desired outcome

After PR-UI-4:
- `/journey` is a meaningful workspace, not a placeholder
- the React UI has both:
  - an operator workspace (`/ops`)
  - a product workflow workspace (`/journey`)
- the main workflow lane becomes tangible:
  - triage candidate
  - journey context
  - analysis handoff preparation

## Product role of Journey Studio

Journey Studio is **not yet** the full analysis execution surface.
It is the structured planning / staging workspace that sits between triage selection and analysis run execution.

It should answer questions like:
- What instrument am I working on?
- Why is it interesting?
- What is the current trade-planning context?
- What known structure, thesis, or setup information is already available?
- What is the next action toward a formal analysis run?

## Definition of success

PR-UI-4 succeeds if it delivers:
- a real Journey Studio route
- deterministic state handling
- a contract-first frontend implementation
- reuse of shared UI patterns
- no backend changes
- no speculative future workflow features smuggled in
