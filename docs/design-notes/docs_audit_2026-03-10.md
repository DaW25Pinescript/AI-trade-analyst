# Docs Audit & Restructure Summary (2026-03-10)

## Canonical active
- `docs/AI_TradeAnalyst_Progress.md` (single source of truth for status/progress)
- `docs/README.md` (top-level docs navigation)

## Active reference (reorganized)
- `docs/specs/` for implementation specs, acceptance packages, schemas, prompt templates, and scoring references.
- `docs/architecture/` for enduring constraints/contracts/system definitions.
- `docs/runbooks/` for setup and operational procedures.
- `docs/design-notes/` for design iteration notes and working context.

## Historical/archive
Moved superseded status/planning and audit snapshots to `docs/archive/`, including:
- Prior competing progress docs (`Progress_Plan.md`, MRO progress snapshot)
- Prior audit runs (`repo_audit_*`, `audit_*`, `AUDIT_*`)
- Superseded debt-focused docs now represented in the canonical progress debt register
- Historical PDF brief

## Merge decisions
- `docs/archive/Technical_Debt_Register.md` and `docs/archive/TD1_Arbiter_Fix_And_Debt_Register.md` were not deleted; they were archived because debt tracking now lives in `docs/AI_TradeAnalyst_Progress.md`.
- `docs/archive/Progress_Plan.md` was archived because phase/status ownership moved to the canonical progress hub.

## Removal decisions
- No substantive historical docs were deleted in this pass.
- Net approach: archive over delete, preserving traceability.

## Link normalization
- Added doc indexes for each new subfolder (`README.md` files).
- Updated internal links to moved docs (`docs/specs/*`, `docs/runbooks/*`, `docs/architecture/*`).
- Added outward “See also” links in the canonical progress doc.
