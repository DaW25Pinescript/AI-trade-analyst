# CONSTRAINTS.md

# AI Trade Analyst – Constraints
Version: 1.0

## 1. Core Constraints

### 1.1 No guessed payloads
The frontend must not invent backend payload shapes. All serious UI work must follow the interface audit and contract freeze.

### 1.2 No broad unrelated rewrites
This initiative is a journey/UI architecture upgrade, not permission to refactor unrelated repo areas.

### 1.3 No fake production logic in v1 scaffolding
Component and route scaffolds may use typed placeholders, but they must not masquerade as real backend behavior.

### 1.4 No premature chart-tool complexity
Initial implementation may use placeholder chart containers and annotation regions. Heavy charting logic is out of scope for the first pass.

### 1.5 No multi-persona workflow expansion in v1 UI
The multi-analyst/persona backend may exist, but the first-pass UI should not attempt to expose a full multi-persona orchestration surface.

### 1.6 No collapse of recommendation and commitment
`systemVerdict`, `userDecision`, and `executionPlan` must remain distinct.

### 1.7 No black-box learning claims
The review/refinement loop must be framed as transparent review and policy refinement, not mysterious self-learning.

---

## 2. UX Constraints

### 2.1 No blank-page landing
The landing surface must be triage-oriented, not a blank ticket form.

### 2.2 No decorative gate checks
Gate checks must act as a real control boundary with severe visual treatment and policy-aware progression.

### 2.3 No stage chaos
The journey must keep strong inter-stage structure even if local stage fields remain flexible.

### 2.4 No ambiguity about who said what
AI-prefilled vs user-confirmed vs user-overridden vs manual fields must be distinguishable through provenance.

### 2.5 Visual treatment must follow the style guide
The dark institutional workspace aesthetic, semantic color roles, surface system, and severity model defined in `UI_STYLE_GUIDE.md` are not optional style preferences — they are part of the product contract.

Specifically:
- Gate Checks must use `SeverityCard` treatment, not standard card styling
- `SplitVerdictPanel` must keep System Verdict, User Decision, and Execution Plan visually distinct
- Provenance markers must distinguish AI content from user action on every surface where both appear
- Color usage must follow the semantic roles in Section 5 — emerald/amber/rose/indigo are state signals, not decoration

---

## 3. Technical Constraints

### 3.1 Typed modular structure
Types, stores, components, routes, and service interfaces should remain separated.

### 3.2 Thin service layer
Future API calls should sit behind explicit service functions rather than being scattered inside components.

### 3.3 Snapshot persistence
The system must persist a save-time decision snapshot instead of relying on future reconstruction from mutable live state.

### 3.4 Adapter visibility
If a frontend need depends on an unstable or missing backend producer, it must be surfaced as an explicit adapter/gap rather than hidden in component logic.

### 3.5 No direct Python execution from the browser
The UI must not import Python modules, call subprocess, or invoke the analyst pipeline from browser context. The UI consumes backend output through one of two permitted patterns: (A) reading saved JSON artifacts via a file-based service layer, or (B) calling a thin API layer that wraps the Python services. Establish which pattern is in use during the interface audit. This is a hard constraint — it determines how every service call in the frontend is shaped.

---

## 4. Scope Constraints for Initial Upgrade

Out of scope for the first major UI pass:
- advanced mobile-first redesign
- collaborative workflows
- excessive settings/configuration surfaces
- full chart drawing tool suite
- auto-learning claims or optimization engines
- any build sequence that skips the interface audit gate

---

## 5. Process Constraints

### 5.1 Audit before build
The interface audit is a hard gating phase before serious UI implementation.

### 5.2 Staged delivery only
Implementation should follow staged milestones rather than a big-bang rewrite.

### 5.3 Reviewable increments
Each phase must leave behind files and structures that are reviewable, testable, and ready for the next pass.

### 5.4 Preserve repo realism
All documentation and scaffolding should reflect the repo as it exists, with uncertainty marked explicitly rather than smoothed over.
