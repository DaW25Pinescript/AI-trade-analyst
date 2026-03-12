# AI Trade Analyst — TD-3: Packaging / Import Stability Spec

## Header

- **Status:** ⏳ Spec drafted — implementation pending
- **Date:** 12 March 2026
- **Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
- **Spec file:** `docs/specs/td3_packaging_import_stability.md`
- **Owner lane:** Runtime hardening / packaging stability / environment reproducibility
- **Depends on:** CI Seam Hardening (closed), Observability Phase 1 (closed), Observability Phase 2 (closed, 1236 tests)
- **Resolves:** TD-3 (packaging/import fragility)
- **Enables:** TD-11 (import-path stability tests)

---

## 1. Purpose

TD-3 exists to reduce the repository's **environment sensitivity** by replacing ad hoc import-path mutation with a more deliberate packaging and import discipline.

The repo is already functionally strong, but the remaining packaging/import fragility still acts like a deployment and contributor footgun. The problem is not "imports are broken everywhere." The problem is that the repo can still succeed in one execution context and fail in another because path resolution is being normalised by environment-specific behavior rather than by a stable package model.

This phase should make it materially easier to answer:

- what Python import roots are official
- which execution modes are supported
- whether modules can be imported without `sys.path.insert`-style rescue logic
- whether tests are proving real packaging stability instead of accidental path luck
- whether local, CI, and future multi-environment runs resolve the same code the same way

This is a hardening phase, not an architecture rewrite.

---

## 2. Why Now

The progress hub still identifies packaging/import fragility as the next significant debt item after the current seam-confidence work, and explicitly ties TD-11 ("no import-path stability tests") to TD-3 completion. The repo is now beyond feasibility and initial hardening; the next backend-quality gain is reducing environment-sensitive wiring so future cleanup and runtime-lane work can happen against a more stable execution model.

The repo also has a real runtime split: `ai_analyst`, `market_data_officer`, `macro_risk_officer`, legacy analyst paths, root/test integrations, and multiple launch modes. That makes import fragility more dangerous than in a single-package app: path mutation can hide broken boundaries, mask packaging drift, and produce false confidence in tests that pass only because the runner already has the repo root on `sys.path`.

This phase is therefore about **execution consistency**, not style purity.

---

## 3. Objective

Move from:

> "the repo usually imports correctly in the environments we happen to run most often"

To:

> "the repo has an explicit, testable import model with minimal path mutation and stable package resolution across supported execution modes"

This phase should improve **reproducibility and change safety**, not introduce a monorepo packaging platform.

### 3.1 Success lens

A successful TD-3 implementation means:

- supported entrypoints import without ad hoc `sys.path.insert` rescue code
- local runs and CI resolve imports using the same intended roots
- test coverage proves import stability intentionally
- contributors can identify the supported package/install model without reading multiple unrelated files
- remaining edge cases are documented deliberately rather than hidden by path hacks
- `pip install -e .` (or equivalent) in a clean venv produces a working environment

---

## 4. Scope

### 4.1 In scope

1. **Import-path audit** — identify all current `sys.path.insert`, `sys.path.append`, cwd-dependent imports, relative-import workarounds, and test-only path normalisation patterns across the repo.

2. **Cross-package dependency graph** — map the full directed dependency graph between the three main packages (who imports what from where, with specific modules). Identify any circular dependencies.

3. **Packaging model clarification** — define the intended supported import model for the repo. This may be a single root installable project, a workspace-style model, or a minimal editable-install discipline, but it must be explicit and consistent with the current codebase. Decision deferred to diagnostic.

4. **Path-mutation reduction** — remove or reduce path mutation where safe, replacing it with proper package-relative imports, install-time resolution, or clearly bounded compatibility shims only where still necessary.

5. **Entrypoint stabilization** — verify the import behavior of the real entry surfaces used by contributors and CI (API startup, scheduler/runtime entry, CLI/dev flows, tests, and batch/bootstrap scripts where relevant).

6. **Import-path stability tests** — add deterministic tests that prove supported execution contexts no longer rely on accidental path state. These tests are the TD-11 follow-on that becomes possible once TD-3 has a stable target model.

7. **Clean venv verification** — prove that `pip install -e .` (or equivalent) in a fresh venv produces a working environment with all imports resolving through packaging, not path hacks.

8. **Documentation closure** — document the supported package/import discipline clearly enough that a contributor can bootstrap the repo without rediscovering path rules from trial and error. Include a `setup.md` or contributor quickstart if one doesn't exist.

### 4.2 Target surfaces

| Surface | Current state (hypothesis — diagnostic will confirm) | TD-3 target |
|--------|--------------------------------------------------------|-------------|
| Root Python execution | May rely on repo-root path presence | Explicit import root behavior |
| `ai_analyst` runtime | Likely partly package-safe, partly runner-dependent | Stable imports without ad hoc path mutation |
| `market_data_officer` runtime | May contain path assumptions in direct execution or tests | Stable imports under supported execution modes |
| `macro_risk_officer` runtime | Similar mixed-state risk | Stable imports under supported execution modes |
| Test suite | Some paths may be normalised by test runner / repo root | Intentional import stability tests |
| Local bootstrap scripts | May depend on cwd or shell location | Documented and stable launch assumptions |
| CI jobs | Currently green but may benefit from implicit path state | Explicit, reproducible import/install model |

### 4.3 Out of scope

- No runtime-lane convergence or service-boundary redesign
- No dependency-manager migration purely for fashion
- No full build/release/distribution pipeline redesign
- No Docker/cloud packaging program
- No broad module re-architecture beyond what import stability requires
- No UI work
- No API contract changes
- No new top-level subsystem
- No opportunistic cleanup of unrelated debt unless directly required by import stability
- No mass renaming of packages/modules without demonstrated need
- No "grand unification" of all repo tooling if a smaller package/install discipline is sufficient
- No monorepo tooling (pants, bazel, nx)
- No dependency version upgrades unless required to fix a packaging conflict
- No runtime behavior changes — imports resolve the same way, just through packaging instead of path hacks
- `MarketPacketV2` contract locked — officer layer unchanged

---

## 5. Design Principles

### 5.1 Import-truth-first, not path-hack-first

The goal is not to make every environment limp along. The goal is to make the intended import model explicit and correct.

### 5.2 Supported execution modes before edge modes

First stabilise the execution surfaces the repo actually uses: CI, local backend startup, tests, and documented developer flows. Edge cases can be documented or deferred if they are not real supported modes.

### 5.3 Smallest packaging move that removes fragility

Prefer the smallest disciplined packaging/install change that eliminates environment-sensitive behavior. Do not turn TD-3 into a packaging-platform project.

### 5.4 Test the import model directly

Do not assume import stability because functional tests happen to pass. Add tests that explicitly prove supported import resolution behavior — including negative tests that confirm packaging is load-bearing, not decorative.

### 5.5 No hidden compatibility magic

If a compatibility shim is temporarily required, it must be documented and bounded. Do not replace one hidden import rescue with another.

### 5.6 Imports must resolve the same way

After the packaging change, every existing import statement in the repo must resolve to the same module it resolved to before. The change is in *how* the resolution happens (packaging vs path hacking), not *what* gets imported. If any import changes its target, that's a bug.

### 5.7 Diagnostic-first, then code

The repo may already contain a partially coherent packaging story. Confirm what exists before prescribing a solution.

---

## 6. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| TD-3 definition | The active debt is packaging/import fragility centered on `sys.path.insert`-style wiring |
| TD-11 dependency | Import-path stability tests follow TD-3 rather than preceding it |
| CI posture | CI seam hardening is already complete; TD-3 must preserve current seam confidence |
| Runtime split | `ai_analyst`, `market_data_officer`, `macro_risk_officer`, legacy paths, and root/test integrations all matter |
| Test reliability | Some tests may currently pass because the runner starts from repo root or normalises path state |
| Launch surfaces | There are multiple local/dev launch paths; not all of them may be equally formalized |
| Packaging files | Root packaging/config files may exist, but the diagnostic must confirm which are real sources of truth |
| Scripts | Bootstrap scripts and OS-specific launch helpers may encode path assumptions |
| Python version | 3.14 (per environment notes) |
| Cross-package coupling | The analyst lane likely imports from MDO and/or MRO; direction and depth unknown until diagnostic |

### Current likely state

The repo likely works in the most common dev/CI flows because the current working directory and test runner behavior are doing more import work than the code admits. The sharpest risk is not "everything is broken now." The risk is that a future cleanup, environment change, alternate runner, or contributor setup exposes import assumptions that were previously hidden.

### Core question

**What is the smallest explicit package/import discipline that removes `sys.path.insert` fragility and lets the repo prove import stability intentionally?**

---

## 7. Key File Paths

| Role | Path | Notes |
|------|------|-------|
| Canonical progress hub | `docs/AI_TradeAnalyst_Progress.md` | Confirms TD-3 priority and TD-11 dependency |
| Observability exemplar spec | `docs/specs/observability_phase_2.md` | Structure/template reference only |
| Root packaging file(s) | `pyproject.toml`, `setup.cfg`, `setup.py` *(if present)* | Diagnostic must confirm what is real |
| Root dependency files | `requirements*.txt`, lock files *(if present)* | Input to supported install model |
| Root launch helpers | `RUN.bat`, `RUN.local.bat`, shell helpers *(if present)* | May encode cwd/path assumptions |
| API entrypoints | `ai_analyst/api/main.py` and related startup helpers | Supported runtime import path must remain stable |
| Journey / router surfaces | `ai_analyst/api/routers/` | Verify package-safe imports |
| Graph/core modules | `ai_analyst/core/`, `ai_analyst/graph/`, `analyst/` | Audit for path mutation or ambiguous imports |
| MDO modules | `market_data_officer/` | Audit runtime/test import discipline |
| MRO modules | `macro_risk_officer/` | Audit runtime/test import discipline |
| Test suites | `ai_analyst/tests/`, `market_data_officer/tests/`, root tests | Confirm whether tests are masking fragility |
| CI workflows | `.github/workflows/` *(if present)* | Confirm install/run assumptions in CI |

Read-only references:
- `docs/ui/UI_CONTRACT.md` — API surface must remain untouched
- `docs/architecture/technical_debt.md` *(if present)* — sync long-lived debt references only if TD-3 changes debt state
- `docs/specs/README.md` — specs inventory should be updated at phase close

---

## 8. Proposed Deliverables

### 8.1 Packaging/import diagnostic report

A concrete inventory of:

- every `sys.path.insert` / `append` usage
- every path-mutation helper or cwd-sensitive import workaround
- the full cross-package dependency graph (directed: package → imports from → specific modules)
- every entrypoint that depends on implicit root path resolution
- every test surface that may be masking packaging fragility
- the currently effective import model in CI versus local runs
- any circular dependencies between packages

### 8.2 Supported import model decision

A short, explicit packaging decision that answers:

- what should be installable/importable
- how contributors and CI should run the code
- whether editable install is required/recommended
- which package roots are official
- what remains intentionally unsupported or transitional

This decision must be documented in the spec after diagnostic confirmation, not assumed up front.

### 8.3 Narrow code patch set

A smallest-possible implementation that removes fragile path mutation and stabilizes supported entrypoints without broad architecture movement.

Expected categories may include:

- new `pyproject.toml` (or equivalent packaging configuration)
- new or updated `__init__.py` files where missing
- import statement cleanup
- package-relative import normalization
- launch-script/install instruction cleanup
- removal of ad hoc `sys.path` hacks
- explicit bootstrap/install assumptions in CI/dev docs

### 8.4 Import stability test layer

Deterministic tests proving the chosen import model, such as:

- package import works under supported runner
- API startup/import surfaces resolve without path hacks
- representative MDO/MRO modules import cleanly
- at least one negative test proving that importing a cross-package module *without* the editable install fails — confirming packaging is load-bearing, not decorative
- CI install/run sequence matches local supported sequence

Exact test shape is diagnostic-dependent.

### 8.5 Contributor/operator bootstrap clarity

A compact documented explanation of how to run/install the repo without relying on shell-location luck. This should be a `setup.md` or contributor quickstart documenting: clone → create venv → install → verify.

---

## 9. Acceptance Criteria

| ID | Acceptance Criterion | Status |
|----|----------------------|--------|
| AC-1 | All current `sys.path.insert` / `append` / equivalent path mutations are inventoried and classified as required, removable, or transitional | ⏳ Pending |
| AC-2 | Cross-package dependency graph is mapped (directed: package → imports from → specific modules); any circular dependencies identified | ⏳ Pending |
| AC-3 | The repo has one explicit supported package/import model documented in this spec | ⏳ Pending |
| AC-4 | Supported runtime entrypoints import correctly without ad hoc path mutation in normal use | ⏳ Pending |
| AC-5 | Supported test entrypoints no longer rely on accidental repo-root path state | ⏳ Pending |
| AC-6 | `pip install -e .` (or equivalent) in a fresh venv produces a working environment with all imports resolving | ⏳ Pending |
| AC-7 | All existing imports resolve to the same modules they did before — no silent target changes | ⏳ Pending |
| AC-8 | CI install/run assumptions are documented and aligned with the supported import model; all CI jobs pass | ⏳ Pending |
| AC-9 | No API/UI contract-visible behavior changes are introduced | ⏳ Pending |
| AC-10 | Code changes remain narrow and packaging-focused; no architecture convergence work is smuggled in | ⏳ Pending |
| AC-11 | Deterministic import-stability tests are added (TD-11 follow-on) with at least one test per major lane: analyst, MDO, MRO, and root/test integration | ⏳ Pending |
| AC-12 | At least one negative test proves that importing a cross-package module without the editable install fails — confirming packaging is load-bearing | ⏳ Pending |
| AC-13 | Unsupported execution modes or remaining transitional shims are explicitly documented rather than hidden | ⏳ Pending |
| AC-14 | A contributor quickstart (`setup.md` or equivalent) exists documenting: clone → create venv → install → verify | ⏳ Pending |
| AC-15 | Full regression suite remains at least as green as baseline (1236 passed), with any pre-existing failures unchanged or explained | ⏳ Pending |

---

## 10. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1 — Inventory path mutation

- Search the repo for:
  - `sys.path.insert`
  - `sys.path.append`
  - direct `PYTHONPATH` mutation in scripts
  - cwd-dependent bootstrap logic
- **Report:** file → exact pattern → likely reason → required/removable/transitional hypothesis

### Step 2 — Map cross-package dependency graph

- Trace all import statements that cross package boundaries (`ai_analyst` ↔ `market_data_officer` ↔ `macro_risk_officer` ↔ root scripts/tests)
- Identify the direction and depth of coupling between packages
- Identify any circular dependencies
- **Report:** directed dependency graph (package → imports from → specific modules/classes)

### Step 3 — Inventory packaging/config files

- Confirm which of the following exist and are active:
  - `pyproject.toml`
  - `setup.cfg`
  - `setup.py`
  - `requirements*.txt`
  - lock files
  - `__init__.py` files in all packages and subpackages
- Determine whether the repo already has an installable package story or is relying on implicit source-tree execution.
- **Report:** active packaging files + effective install model + missing `__init__.py` gaps

### Step 4 — Trace supported local execution modes

- Audit documented or de facto local execution paths:
  - backend/API startup
  - test execution
  - scheduler/runtime startup
  - any run/bootstrap scripts (`RUN.bat`, `RUN.local.bat`, shell helpers)
- For each, identify:
  - required cwd
  - whether editable install is assumed
  - whether imports break outside repo root
- **Report:** execution mode → import assumptions → stable/fragile

### Step 5 — Trace CI import/install assumptions

- Inspect CI workflow steps for Python install/run behavior.
- Determine whether CI uses editable install, repo-root execution, or implicit path state.
- **Report:** workflow/job → install steps → import assumptions → alignment gap with local flows

### Step 6 — Audit tests for masked fragility

- Identify tests or fixtures that normalise path state.
- Determine whether current test success could hide broken packaging/import behavior.
- **Report:** file/fixture → masking behavior → keep/remove after TD-3

### Step 7 — Identify package boundary hazards

- Audit for ambiguous imports across:
  - `ai_analyst`
  - `market_data_officer`
  - `macro_risk_officer`
  - root-level modules/tests
  - legacy analyst path
- Look for:
  - shadow-prone module names
  - mixed absolute/relative imports
  - import cycles that path hacks may be hiding
- **Report:** boundary hazard inventory

### Step 8 — Run baseline test suite

- Run the current deterministic baseline.
- **Report:** baseline count (target: 1236 passed, 70 pre-existing failures), and whether any path-related failures already appear

### Step 9 — Propose import model and patch surface

Based on Steps 1–8, propose:

- the supported package/import model (single `pyproject.toml` vs per-package vs hybrid)
- whether editable install is the intended default
- the smallest patch set (files + one-line purpose + estimated line delta)
- which path mutations can be removed immediately
- which shims, if any, must remain transitional (with documented reason)
- what import-stability tests should be added first
- recommended implementation order

### Step 10 — Review against hard constraints

Before implementation, explicitly confirm:

- no API/UI contract changes
- no runtime-lane convergence work
- no dependency-manager migration unless strictly required
- no broad module relocation unless diagnostic proves it is necessary
- no hidden shell/cwd assumptions left undocumented in supported flows
- all existing imports will resolve to the same modules as before
- `MarketPacketV2` contract unchanged

### Step 11 — Return diagnostic report for approval

**Do not implement until the diagnostic report is reviewed.**

---

## 11. Implementation Constraints

### 11.1 General rule

This phase is **packaging/import stability only**. It removes environment-sensitive import fragility and adds tests/documentation for the supported import model. It does not redesign service boundaries, change API behavior, or open unrelated cleanup lanes.

### 11.2 Implementation sequence

1. Create packaging configuration (`pyproject.toml` and any required `__init__.py` files) based on diagnostic-confirmed model
2. Verify `pip install -e .` works in a clean venv
3. Remove `sys.path.insert` calls from the lowest-risk files first (likely test files and scripts)
4. Verify baseline tests still pass: [N]/[N] after first batch of removals
5. Remove `sys.path.insert` calls from core module files
6. Verify full test suite: [N]/[N] still pass after all removals
7. Verify all CI jobs still pass with the new packaging
8. Add import-stability tests for analyst, MDO, MRO, and root/test surfaces (TD-11 closure)
9. Add negative test proving packaging is load-bearing (AC-12)
10. Verify full suite: [N]+/[N] after new tests
11. Create `setup.md` contributor quickstart
12. Document any remaining transitional shims with explicit reason
13. Final regression gate: all tests green, zero new regressions, CI green

**Rule: never skip a gate.**

### 11.3 Hard constraints

- No runtime behavior changes — imports resolve the same way, just through packaging
- No API response shape changes
- No `UI_CONTRACT.md` changes
- `MarketPacketV2` contract locked — officer layer unchanged
- No runtime-lane convergence or orchestration redesign
- No packaging-platform sprawl or monorepo tooling
- No dependency version upgrades unless required to fix a packaging conflict
- No cloud/deployment program
- No path hacks reintroduced under a different name
- No deterministic-test regression accepted without explicit justification
- Deterministic fixture/mock tests are the required acceptance backbone — no live provider dependency in CI
- If removing a `sys.path.insert` reveals a circular dependency, flag before proceeding
- If any import changes its resolution target, that is a bug — flag immediately
- If this work resolves or partially addresses any Technical Debt Register items (§8 of progress plan), update their status

---

## 12. Success Definition

TD-3 is done when: the repo has an explicit, documented package/import model; every `sys.path.insert` hack has been removed or replaced with proper packaging; `pip install -e .` in a clean venv produces a working environment; all existing imports resolve to the same modules they did before; import-path stability is proven by automated tests including at least one negative test (closing TD-11); all CI jobs pass without implicit path wiring; any remaining transitional shims are documented and bounded; and a contributor quickstart exists. No runtime behavior changes, no API contract changes, no architecture rewrites. No SQLite. No monorepo tooling. No hidden compatibility magic.

---

## 13. Why This Phase Matters

| Without | With |
|---------|------|
| A new contributor clones the repo and discovers import failures that don't exist on the original developer's machine | Clone → venv → `pip install -e .` → working environment |
| CI passes because the runner's working directory happens to compensate for missing packaging | CI passes because imports are properly declared and resolved |
| Cross-package dependencies are implicit in `sys.path.insert` calls scattered across the codebase | Cross-package dependencies are explicit in packaging metadata and a documented dependency graph |
| Removing or moving a module might silently break imports in a different package with no test catching it | Import-path stability tests catch broken cross-package imports immediately |
| Future deployment to a different environment is a debugging adventure | Deployment uses standard Python packaging — `pip install` and go |
| Remaining compatibility shims hide silently in the codebase | Transitional shims are documented with reasons and boundaries |
| TD-11 (import-path stability tests) remains blocked | TD-11 closes as a direct follow-on |

---

## 14. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Observability Phase 1 | Analyst pipeline run visibility | ✅ Done — 668 tests |
| Observability Phase 2 | Cross-lane runtime visibility | ✅ Done — 1236 tests |
| **TD-3** | **Packaging/import-path stability + import tests** | **⏳ Spec drafted — implementation pending** |
| Cleanup Tranche | Async markers, TD-5, TD-9, doc consolidation | ⏳ Pending (after TD-3) |
| UI Phase 3A Impl | Triage Board + Journey Studio build | ⏸️ Parked |

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| TD-3 expands into a repo-wide architecture rewrite | Keep the phase restricted to import discipline and supported entrypoints |
| Tests still pass while packaging remains fragile | Add direct import-stability tests including a negative test proving packaging is load-bearing |
| CI and local flows diverge further | Audit both explicitly and document one supported model |
| A too-ambitious packaging move breaks working flows | Use the smallest model that removes fragility; verify after each gate |
| Circular dependency discovered when path hacks removed | Treat as diagnostic finding; flag before proceeding; may require structural decision beyond this phase |
| Hidden import cycles appear when path hacks are removed | Treat them as diagnostic findings; fix only what is necessary for supported flows |
| Contributors lose bootstrap clarity during transition | Update docs in the same phase closure; contributor quickstart is an explicit AC |
| Transitional shims become permanent | AC-13 requires explicit documentation of any remaining shim and a reason it still exists |
| Import resolution targets silently change after packaging switch | AC-7 requires all imports resolve to the same modules; §5.6 design principle enforces this |

---

## 16. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 10).*

Expected subsections:
- Path mutation inventory (file → pattern → reason → required/removable/transitional)
- Cross-package dependency graph (directed: package → imports from → modules)
- Packaging/config file inventory (what exists, what's missing)
- Supported local execution mode audit (mode → import assumptions → stable/fragile)
- CI import/install audit (job → install steps → assumptions → alignment gaps)
- Test masking audit (file/fixture → masking behavior → keep/remove)
- Package boundary hazard inventory (shadow-prone names, mixed styles, cycles)
- Baseline test report
- Proposed import model and packaging structure with rationale
- Proposed patch set (files + one-line descriptions + estimated line delta)
- AC gap table (pre-implementation status for AC-1 through AC-15)
- Any surprises or scope adjustments

---

## 17. Documentation Closure

At phase close, update:

- `docs/specs/td3_packaging_import_stability.md` — mark complete, flip all AC cells, populate §16
- `docs/AI_TradeAnalyst_Progress.md` — update phase status, test count row, next actions, and mark TD-3 resolved and TD-11 resolved in debt register
- `docs/specs/README.md` — add/update spec link and status
- Review `docs/architecture/technical_debt.md`, `docs/architecture/system_architecture.md`, `docs/README.md`, `AI_ORIENTATION.md` — update only if import model, repo structure, or debt posture changed
- Cross-document sanity check: no stale phase references, no competing progress source, no outdated bootstrap guidance

---

## 18. Appendix — Recommended Agent Prompt

```text
Read `docs/specs/td3_packaging_import_stability.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 10 and report findings
before changing any code.

Required diagnostic outputs:

1. Inventory all sys.path.insert / append / equivalent path mutations.
   Report: file → pattern → reason → required/removable/transitional.
2. Map the full cross-package dependency graph (directed: package → imports
   from → specific modules). Flag any circular dependencies.
3. Confirm active packaging/config files, __init__.py coverage, and effective
   install model.
4. Audit supported local execution modes (API startup, tests, scheduler,
   run scripts) and their import assumptions. Report: stable/fragile per mode.
5. Audit CI install/run assumptions and compare with local flows.
6. Identify tests/fixtures masking import fragility.
7. Inventory package-boundary hazards (shadow-prone names, mixed import
   styles, cycles).
8. Run baseline deterministic tests — confirm 1236 passed, 70 pre-existing
   failures.
9. Propose the smallest supported import model and patch surface: packaging
   structure, removal plan per sys.path.insert call, import stability test
   plan, transitional shims with reasons, implementation order.
10. Re-confirm all hard constraints before implementation.
11. Return the diagnostic report for approval.

Hard constraints:
- This is packaging/import stability only — no runtime behavior changes
- All existing imports must resolve to the same modules they did before
- No API/UI contract changes
- MarketPacketV2 contract locked — officer layer unchanged
- No runtime-lane convergence or architecture rewrite
- No dependency-manager migration unless strictly required
- No broad module relocation unless the diagnostic proves it necessary
- No monorepo tooling, no Docker/cloud packaging
- No hidden path hacks under a new name
- Deterministic tests only — no live provider dependency in CI
- If removing a sys.path.insert reveals a circular dependency, flag before
  proceeding
- If any import changes its resolution target, that is a bug — flag immediately

Do not implement until the diagnostic report is reviewed and approved.

On completion, close the spec and update docs per §17:
1. `docs/specs/td3_packaging_import_stability.md` — mark ✅ Complete, flip
   all AC cells (AC-1 through AC-15), populate §16 with: path mutation
   inventory, dependency graph, packaging structure decision, removal log,
   import stability test results, CI verification, shim documentation,
   surprises.
2. `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count
   row, update next actions, mark TD-3 resolved and TD-11 resolved in debt
   register.
3. `docs/specs/README.md` — update spec inventory.
4. Review `docs/architecture/technical_debt.md`, `system_architecture.md`,
   `docs/README.md`, `AI_ORIENTATION.md` — update only if needed.
5. Cross-document sanity check: remove stale phase refs, keep one canonical
   progress source.
6. Return Phase Completion Report:
   Phase:          TD-3 Packaging/Import-Path Stability
   Branch:         [branch name]
   Test delta:     [before] → [after] (+[N])
   Code changes:   [files touched, one-line each]
   Docs updated:   [which docs were touched]
   Debt introduced: [none / description]
   Debt resolved:  TD-3 (sys.path.insert wiring), TD-11 (import-path stability tests)
   Packaging:      [confirm structure chosen and working]
   Clean venv:     [confirm pip install -e . works in fresh venv]
   Import targets: [confirm all imports resolve to same modules as before]
   Shims:          [none remaining / list with documented reasons]

Commit all doc changes on the same branch as the implementation.
```
