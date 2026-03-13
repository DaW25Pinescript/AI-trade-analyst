# PR-4 Prep Audit — Targeted Documentation Consolidation (2026-03-13)

## 1) Audit summary

This was a scoped audit of the highest-risk documentation surfaces for status/progress overlap against the canonical hub:
`docs/AI_TradeAnalyst_Progress.md`.

Overall finding: doctrine is mostly in place in index files, but a few high-visibility docs still carry active-phase language, status snapshots, or dated metrics that can be read as competing trackers. The highest risk is **root `README.md`** (stale test/status section) and **`docs/architecture/system_architecture.md`** (phase-status statements in an enduring architecture doc).

No structural reorganization is required. A bounded PR-4 can reduce overlap with small edits: trim status-heavy sections, add/strengthen backlinks, and explicitly frame historical audit docs as historical where needed.

## 2) Files reviewed

Scoped surfaces reviewed:

- `README.md`
- `docs/README.md`
- `docs/specs/README.md`
- `docs/architecture/README.md`
- `docs/architecture/OBJECTIVE.md`
- `docs/architecture/CONSTRAINTS.md`
- `docs/architecture/repo_map.md`
- `docs/architecture/system_architecture.md`
- `docs/architecture/technical_debt.md`
- `docs/runbooks/README.md`
- `docs/archive/README.md`
- `docs/ui/UI_BACKEND_AUDIT.md`
- `docs/ui/UI_CONTRACT.md`
- `docs/ui/UI_WORKSPACES.md`
- `docs/ui/DESIGN_NOTES.md`
- `docs/ui/VISUAL_APPENDIX.md`

## 3) Competing-status risks found

### High risk

1. **Root README carries stale, date-bound repo status and test counts.**
   - Competes with canonical progress hub by presenting a separate status snapshot and hard numbers likely to drift.
   - Risk: contributor confusion about current state and readiness.

2. **`docs/architecture/system_architecture.md` includes active/current phase and planned sequencing language.**
   - Blurs enduring architecture vs execution tracking.
   - Risk: architecture doc becoming a second roadmap/status surface.

### Medium risk

3. **`docs/ui/UI_WORKSPACES.md` and `docs/ui/UI_CONTRACT.md` retain phase labels that can age (`Phase: UI Phase 2/3`, `Status: Commit-ready`).**
   - These are primarily contract/product docs, not status trackers, but metadata can read like live progress claims.

4. **`docs/ui/UI_BACKEND_AUDIT.md` is an audit snapshot but currently sits in active UI lane without a historical framing banner.**
   - Content is useful and referenced, but framing can imply current status authority.

5. **`docs/architecture/OBJECTIVE.md` and `docs/architecture/CONSTRAINTS.md` are post-merge audit artifacts under architecture.**
   - They read as run-specific acceptance/audit docs rather than enduring architecture references.

## 4) Recommended actions by file (classification)

- `docs/README.md` — **KEEP as-is**
  - Already enforces canonical-source doctrine and routing.

- `docs/specs/README.md` — **KEEP as-is**
  - Includes explicit status-authority backlink and remains inventory-focused.

- `docs/architecture/README.md` — **KEEP but add backlink to progress hub**
  - Backlink exists in "See also"; recommend one additional top-level note clarifying architecture docs are non-authoritative for phase/status.

- `docs/architecture/system_architecture.md` — **TRIM duplicated status language**
  - Keep structural "implemented lanes" as architecture context.
  - Trim/neutralize "Active/current phase" and forward sequencing language; replace with timeless wording + link to progress hub.

- `docs/architecture/technical_debt.md` — **LEAVE untouched (supporting doc, not competing)**
  - Properly framed as enduring ledger with explicit handoff of sequencing to progress hub.

- `docs/architecture/repo_map.md` — **LEAVE untouched (supporting doc, not competing)**
  - Navigation/supporting architecture map, already links to progress hub.

- `docs/architecture/OBJECTIVE.md` — **MOVE historical material to archive**
  - This is a run-specific audit objective, not enduring architecture.
  - Minimal approach: copy to `docs/archive/` and leave a short pointer stub in architecture (or keep file with "historical snapshot" banner if avoiding moves in PR-4).

- `docs/architecture/CONSTRAINTS.md` — **MOVE historical material to archive**
  - Same rationale as OBJECTIVE; run-specific audit constraints are historical artifacts.

- `docs/runbooks/README.md` — **KEEP as-is**
  - Operational index with proper canonical backlink.

- `docs/archive/README.md` — **KEEP as-is**
  - Correctly states non-authoritative historical role.

- `docs/ui/UI_BACKEND_AUDIT.md` — **KEEP but add backlink to progress hub**
  - Add a brief top note: historical/baseline audit; current repo status lives in progress hub.

- `docs/ui/UI_CONTRACT.md` — **KEEP but add backlink to progress hub**
  - Add short note near header that this file is contract authority for UI behavior, not status/phase tracker.

- `docs/ui/UI_WORKSPACES.md` — **TRIM duplicated status language**
  - Keep workspace blueprint content.
  - Remove or neutralize volatile header metadata (`Status: Commit-ready`, `Phase: UI Phase 3`) to avoid timeline drift.

- `docs/ui/DESIGN_NOTES.md` — **LEAVE untouched (supporting doc, not competing)**
  - Design decision log; not functioning as current status hub.

- `docs/ui/VISUAL_APPENDIX.md` — **LEAVE untouched (supporting doc, not competing)**
  - Artifact index only; no competing roadmap/progress behavior.

- `README.md` — **TRIM duplicated status language**
  - Remove/condense "Current Status" and date-bound "Test Suite Status" snapshot into timeless capability summary.
  - Add explicit link: "Current phase/progress: docs/AI_TradeAnalyst_Progress.md".

## 5) Proposed PR-4 change list (bounded)

1. **Root README de-conflict**
   - Replace stale status/test snapshot with concise, non-date-bound capability language.
   - Add explicit canonical-progress backlink.

2. **Architecture de-conflict**
   - In `docs/architecture/system_architecture.md`, remove active-phase phrasing and sequencing claims.
   - Keep architecture reality markers that are structural and enduring.

3. **UI lane framing**
   - Add one-line non-authoritative status disclaimers/backlinks in `docs/ui/UI_BACKEND_AUDIT.md` and `docs/ui/UI_CONTRACT.md`.
   - Neutralize volatile phase/status header metadata in `docs/ui/UI_WORKSPACES.md`.

4. **Historical placement hygiene (minimal move set)**
   - Move (or duplicate-then-stub) `docs/architecture/OBJECTIVE.md` and `docs/architecture/CONSTRAINTS.md` into `docs/archive/` with clear historical labels.
   - Keep links stable by leaving short stubs if needed.

5. **No broad rewrites**
   - Do not alter contract semantics, endpoint matrices, or architecture substance.
   - Keep edits localized to headers/intros/status sections.

## 6) Ambiguous items to leave alone (for now)

1. **`docs/architecture/technical_debt.md`**
   - Could be interpreted as progress-adjacent, but current framing already delegates sequencing to the canonical hub.

2. **UI phase naming inside content (`Phase 1/2/3A`)**
   - Some phase references are historically informative and tied to artifact provenance.
   - Only remove clearly volatile "current/active" claims; keep provenance references.

3. **`docs/ui/UI_BACKEND_AUDIT.md` location**
   - Could be moved to archive, but it is still a foundational reference for contract/workspaces.
   - Prefer keeping in `docs/ui/` with explicit historical framing rather than relocating in PR-4.

4. **`docs/specs/*` completed spec markers (e.g., ✅ Complete)**
   - These are spec lifecycle annotations, not full status trackers; safe to keep if canonical backlink remains clear.
