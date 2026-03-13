# Codex Prompt — Add Reflective Intelligence Layer Design Note

You are working in the `AI-trade-analyst` repo.

Your task is to add a new future-facing design note for the **Reflective Intelligence Layer** and update the repo's roadmap/progress surfaces so this idea is recorded properly **without** changing the currently locked UI re-entry implementation sequence.

## Critical context — current repo state

The repo has completed:
- Observability Phase 2 (structured events across all lanes, 1236 tests)
- TD-3 packaging/import stability (proper `pyproject.toml`, `pip install -e .`, 1603 tests)
- Cleanup tranche (TD-5 enum centralisation, TD-9 unused vars, async markers, doc consolidation)
- UI Re-Entry Governance (PR-UI-0 — React + TS + Tailwind locked, Triage-first sequence, Agent Ops classified as Phase 3B)
- React App Shell (PR-UI-1 — `ui/` directory, Vite, routing, typed API client, TanStack Query)
- Triage Board MVP (PR-UI-2 — live data rendering, shared components, trust strip, feeder health chip)

The currently locked forward sequence is:
- Phase 3: Shared Component Extraction (next)
- Phase 4: Agent Ops Contract + Backend MVP
- Phase 5: Agent Ops React MVP
- Phase 6: Journey Studio + Analysis Run + Journal & Review
- Phase 7: Agent Ops Trace + Detail

The Reflective Intelligence Layer is **future roadmap direction only**. It must **not** be written as an active phase, dependency, or blocker for any current work.

## Primary objective

Add a refined design note at:

`docs/design-notes/reflective_intelligence_layer.md`

Use the supplied content file as the canonical source. Make minor path/reference adjustments only if needed to fit the repo's actual markdown structure.

## Source content

Use the file `docs/design-notes/reflective_intelligence_layer.md` that I am supplying. Treat it as canonical.

## Required repo updates

### 1. Add the design note file

Create `docs/design-notes/reflective_intelligence_layer.md` using the supplied content.

If the `docs/design-notes/` directory does not exist, create it. If a README or index file would be expected based on the repo's conventions in other `docs/` subdirectories (e.g. `docs/specs/README.md`, `docs/architecture/README.md`), create a minimal one. Otherwise, do not invent a new index convention.

The note must be clearly classified as:
- future design direction
- post-UI-reentry / post-Agent-Ops-foundation architecture
- human-governed review / policy-refinement layer
- not part of any current PR or phase scope

### 2. Update the progress hub

Update `docs/AI_TradeAnalyst_Progress.md`.

The progress hub has been significantly updated through the UI re-entry sequence. It now includes Phase 0–2 completion entries and the full UI re-entry phase roadmap.

Add a short entry in the appropriate location. The progress hub likely has one or more of these sections where future direction belongs:
- a "Future Design Direction" or "Roadmap" subsection
- a "Later" or "Post-foundation" section
- the bottom of the "Where We Should Go Next" priorities

If no explicit future-direction section exists, add a compact subsection (e.g. "Future Architecture Direction") that does not disturb the current active-phase narrative.

**Required wording (adapt to fit the section style):**

> **Future Design Direction — Reflective Intelligence Layer:** Human-governed review and policy-refinement architecture built on run-record audit trails. Intended to use Agent Ops observability and Journal & Review artifacts to surface recurring weaknesses, generate bounded hypotheses, and propose reversible policy changes for human approval. Becomes viable once the repo has stable run artifacts, Agent Ops observability surfaces, Journal & Review readback, and sufficient historical run volume. Not part of current UI re-entry implementation scope. Design note: `docs/design-notes/reflective_intelligence_layer.md`.

**Rules for the progress hub update:**
- Must clearly say this is future direction, not current implementation
- Must state it depends on run-record audit trails, Agent Ops observability, and Journal & Review maturity
- Must say it is about recurring weakness detection, bounded hypotheses, and reversible policy proposals for human approval
- Must explicitly say it does not alter current UI re-entry scope
- Must link to the design note file
- Do NOT rewrite the current active-phase sequencing
- Do NOT insert this as a current-phase blocker
- Do NOT imply it starts before Agent Ops or before Journal & Review exist
- Do NOT change any phase status or test count entries

### 3. Update the specs/design-notes inventory if appropriate

Inspect whether the repo has an index/README for specs or design notes:
- `docs/specs/README.md` (likely exists)
- a design-notes index file (may not exist yet)

If `docs/specs/README.md` exists and includes references to design notes or future-direction documents, add a concise reference to the new design note.

If `docs/design-notes/` is new and the repo's other `docs/` subdirectories have README files, create a minimal `docs/design-notes/README.md` that indexes the new note.

Only update inventory files that already exist or that clearly follow the repo's established conventions. Do not invent new index structures.

## Constraints

- **No code changes**
- **No backend contract changes**
- **No endpoint additions**
- **No UI scope expansion**
- **No changes to any PR target (PR-UI-3 or any subsequent PR)**
- **Do not move Agent Ops earlier in the roadmap**
- **Do not reclassify Agent Ops**
- **Do not imply autonomous self-modifying AI**
- **Do not alter any phase status entries in the progress hub**
- **Do not change test count rows**

## The design note must preserve these ideas

- AI Trade Analyst should evolve toward a **self-reviewing analytical desk**, not a black-box autonomous trader
- The foundation is the run-record / audit-trail architecture (already exists post-Obs P2)
- The reflective layer sits conceptually behind and after current UI/Agent Ops work
- Agent Ops handles current-state trust/observability; the reflective layer handles historical review and policy proposals
- Journal & Review is an important evidence source for this future layer
- The system may recommend, but the human authorises
- All future policy proposals must be reversible, evidence-backed, and sandbox-testable

## Deliverables

When done, provide:

1. Summary of files created/changed
2. Exact wording added to the progress hub
3. Whether `docs/design-notes/` was newly created
4. Whether any index/README files were created or updated
5. Confirmation that no current phase sequencing was altered
6. Confirmation that no code files were changed
7. Suggested commit message

## Suggested commit message

`docs: add reflective intelligence layer design note and future roadmap entry`
