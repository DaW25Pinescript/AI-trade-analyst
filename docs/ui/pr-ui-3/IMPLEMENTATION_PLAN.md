# IMPLEMENTATION PLAN — PR-UI-3

## Recommended execution order

### Step 1 — Audit the current Triage Board frontend surfaces
Before moving files, inspect what PR-UI-2 produced:
- which components are truly generic
- which hooks are endpoint/workspace-specific
- which props or names are too triage-shaped for `shared/`
- where tests are thin or too page-level only

Deliverable: a short internal classification list.

### Step 2 — Tighten layer ownership
Refine file placement so `app/`, `shared/`, and `workspaces/triage/` each own the right concerns.

Typical outcomes may include:
- keeping generic feedback/layout/state primitives in `shared/`
- moving triage-owned row/card logic under `workspaces/triage/`
- retaining feeder-level health surfaces in `shared/` if their semantics are cross-workspace

### Step 3 — Normalize shared interfaces
Harden component props and naming.

Look for:
- overly specific prop names
- inconsistent empty/error/loading component signatures
- inconsistent timestamp/freshness display inputs
- repeated className/layout patterns that can be safely normalized

### Step 4 — Harden hooks and API boundaries
Ensure that:
- API wrappers stay typed and explicit
- hooks are in the right ownership layer
- query keys are named consistently
- mutation invalidation behavior is easy to follow

Do not introduce a broad data framework rewrite.

### Step 5 — Strengthen tests
Add or refine tests for:
- shared component branching
- hook behavior if practical and stable
- file/ownership refactors that could quietly break Triage Board behavior
- import path stability where appropriate

### Step 6 — Documentation closure
Update:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`
- `ui/README.md` if structure or ownership guidance changed meaningfully

## Suggested concrete deliverables
A strong PR-UI-3 will usually include most of the following:
- refined `shared/` directory ownership
- possibly relocating `EntityRowCard` or splitting it into shared + triage-owned pieces
- shared index/export cleanup where justified
- common type definitions for UI state surfaces if needed
- stronger tests around shared components and Triage composition
- light docs clarifying how future workspaces should consume shared primitives

## Things to resist
Do not:
- build a giant generic card system
- introduce Storybook or another new tool unless explicitly required later
- redesign the Triage page visually just to make extraction feel more dramatic
- implement future workspaces under the excuse of proving reuse
