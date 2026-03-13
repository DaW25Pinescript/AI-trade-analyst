# PR-UI-0 — UI Re-Entry Governance Unlock

**PR title:** `docs: reopen UI implementation lane with React stack decision and phase plan`
**Branch:** `ui/reentry-governance`
**Type:** Documentation / governance
**Risk:** None (docs only, zero code changes)
**Phase:** Phase 0 of UI Re-Entry Phase Plan

---

## Summary

Reopens the UI implementation lane after the completed runtime-hardening sequence (Observability Phase 2, TD-3 packaging, cleanup tranche). Records the forward frontend stack decision, the Triage-first build sequence, the Agent Operations classification as a fenced Phase 3B extension, and the Agent Ops product framing and negative scope.

This PR is documentation only. No code changes.

## What changed

- Updated `docs/AI_TradeAnalyst_Progress.md` with UI re-entry decisions
- Committed `docs/specs/ui_reentry_phase_plan.md` as the controlling execution plan
- Added design governance notes for Agent Operations classification, product framing, and HTML prototype status
- Recorded React + TypeScript + Tailwind as the forward frontend stack

## Why

- The runtime-hardening sequence is complete — the backend is in its strongest state
- UI Phase 3A design has been banked since the design session (contract, wireframes, component system, design notes, visual appendix)
- The framework decision and build sequence need to be recorded before any implementation PR
- Agent Operations needs explicit classification, product framing, and negative scope before anyone builds against undocumented `/ops/*` endpoints

## Out of scope

- No code changes
- No React setup
- No component work
- No backend changes

## Suggested commit message

`docs(ui): reopen UI implementation lane — React stack, Triage-first sequence, Agent Ops fenced as 3B`

---

## Claude Code Implementation Prompt

```
You are working in the GitHub repo for AI Trade Analyst.

Task: implement PR-UI-0 — UI re-entry governance unlock. This is a
documentation-only PR. Zero code changes.

PR title: docs: reopen UI implementation lane with React stack decision and phase plan

Objective:
Reopen the parked UI implementation lane with explicit governance
documentation so that subsequent PRs (React shell, Triage Board, etc.)
have a clear mandate and classification.

Required deliverables:

1. Commit docs/specs/ui_reentry_phase_plan.md
   - This file should already exist in the repo or be provided.
   - If it does not exist, flag immediately — do not improvise a plan.

2. Update docs/AI_TradeAnalyst_Progress.md
   Make the following changes to the progress hub:

   a) Update the header:
      - Current phase: "UI Phase 3A Implementation — Triage Board first
        (React + TypeScript + Tailwind)"

   b) Update the Phase Index:
      - Add: "UI implementation resumes with Triage Board as the first
        React workspace and component-system seed"
      - Record: "React + TypeScript + Tailwind is the forward frontend stack"
      - Record: "Agent Operations is classified as Phase 3B extension —
        an operator observability / explainability / trust workspace on
        new read-only projection endpoints"

   c) Update the Phase Status table:
      - Change "UI Phase 3A Impl" from Parked to Active
      - Add row: "Phase 0 — UI Re-Entry Governance | Complete"
      - Add row: "Phase 1 — React App Shell + Triage Route | Next"

   d) Update the next actions section:
      - Record that the runtime-hardening sequence (Obs P2, TD-3,
        cleanup tranche) is complete
      - Record that UI implementation is now the active lane
      - First PR after governance: PR-UI-1 (React app shell)
      - Agent Ops backend endpoints are Phase 4 (after Triage Board
        and component extraction)

   e) Update the weekly plan if present:
      - Weeks 1-2: PR-UI-1 (React shell) + PR-UI-2 (Triage Board MVP)
      - Weeks 3-4: PR-UI-3 (component extraction) + PR-OPS-1 (Agent Ops
        contract spec)

   f) Add a latest increment entry:
      "UI Re-Entry Governance (13 Mar 2026) — Reopened UI implementation
      lane. Locked React + TypeScript + Tailwind as forward stack. Triage
      Board is the first React workspace and component-system seed. Agent
      Operations classified as Phase 3B extension: an operator observability,
      explainability, and trust workspace built on new read-only projection
      endpoints. Agent Ops north-star question: 'Why should I trust this
      system right now?' Agent Ops MVP is not config, prompt editing,
      manual orchestration, model-switching, or chat-with-agents. HTML
      prototype is visual reference only. Execution plan committed as
      docs/specs/ui_reentry_phase_plan.md."

3. Add governance design note
   Either as a section in the phase plan or as a brief addition to
   docs/ui/DESIGN_NOTES.md, record these governance decisions:

   a) Agent Operations product framing (locked):
      - Agent Operations is an operator observability, explainability,
        and trust workspace for the multi-agent analysis engine
      - North-star question: "Why should I trust this system right now?"
      - It exists to answer five operator questions:
        1. Who participated?
        2. What happened in this run?
        3. Why did the system reach this verdict?
        4. Where is trust weakened?
        5. What needs attention?

   b) Agent Operations negative scope (locked):
      - Agent Ops MVP is NOT a configuration interface
      - It is NOT a prompt editor
      - It is NOT a manual orchestration panel
      - It is NOT a model-switching console
      - It is NOT a chat-with-agents surface

   c) Agent Operations classification:
      - Phase 3B extension, not Phase 3A
      - No production contract for /ops/* until backend PRs merge and
        UI_CONTRACT.md is updated
      - Phase 5 = roster-first observability MVP
      - Phase 7 = run-scoped forensic explainability

   d) HTML prototype status:
      - operations.html is visual reference only for hierarchy, tone,
        and interaction intent — not implementation debt

   e) Frontend migration rule:
      - React app coexists with existing app/ during workspace-by-workspace
        migration — no big-bang legacy replacement

   f) Agent health polling rule:
      - /ops/agent-health is poll-based snapshot only in MVP — no SSE,
        no WebSocket, no live-push semantics

4. Update docs/specs/README.md
   - Add link to ui_reentry_phase_plan.md with status

Constraints:
- Zero code changes
- Do not create any React files, components, or build configuration
- Do not modify any Python files
- Do not modify UI_CONTRACT.md (no new contract surfaces in this PR)
- Do not modify UI_WORKSPACES.md beyond a minimal backlink if needed
- Do not create or modify any test files
- Keep edits factual and bounded — record decisions, do not expand them

Validation:
- All modified docs are internally consistent
- Progress hub reflects the correct current phase
- Phase plan is committed and linked from specs index
- Agent Ops product framing and negative scope are explicitly recorded
- No code changes in the diff

Return:
- summary
- files changed
- what was recorded in each file
- suggested commit message
- suggested PR description
```
