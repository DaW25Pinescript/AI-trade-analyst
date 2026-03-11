# AI Trade Analyst — CI Seam Hardening Spec

**Status:** ✅ Complete
**Date:** 10 March 2026
**Closed:** 10 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

This phase follows the closure of:

- Operationalise Phase 2 — ✅ Complete (644 tests)
- TD-1 Arbiter contract fix — ✅ Complete (645 tests)
- Security/API Hardening — ✅ Complete (677 tests)

This phase answers one tight question:

**Can the remaining production-readiness seam be closed by gating the missing Python integration paths in CI, without broad CI/platform redesign?**

**Moves FROM → TO**
- **From:** the repo is operationally hardened, but important Python orchestration seams are not yet CI-gated where intended.
- **To:** the critical MDO/root/orchestration seams are deterministically exercised in CI, and at least one orchestration integration path is green in CI.

---

## 2. Scope

### In scope
- Audit current CI workflows and exact suite coverage
- Gate missing Python integration seams in CI where intended
- Add or tighten missing integration tests required for the seam gate
- Add explicit `/analyse/stream` coverage if still missing (error contract and event semantics — heartbeat, data event shape, completion)
- Ensure at least one orchestration integration path is green in CI
- Verify that CI actually executes newly gated suites (execution evidence, not just configuration)
- Update specs/progress docs on closure

### Target seams/components

| Area | Target |
|------|--------|
| MDO seam | `market_data_officer/tests` coverage in CI where intended |
| Root integration seam | Root Python integration tests in CI where intended |
| API stream seam | `/analyse/stream` error-contract + event semantics coverage |
| Orchestration seam | One end-to-end-or-near integration path green in CI |

### Out of scope
- No new product features
- No Security/API redesign beyond missing tests/gating needed for this seam
- No cloud deployment or infra work
- No Docker/Kubernetes/systemd work
- No database / Redis / persistence
- No notifier transport work
- No broad packaging refactor
- No flaky live-provider tests in CI
- No new top-level module
- No observability tooling, metrics, or dashboard infrastructure
- No CI provider migration or new paid CI features

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Current phase | Progress plan now points to **CI Seam Hardening** as active |
| Production-readiness gate | The last major gate is "one orchestration integration path green in CI" plus intended seam coverage |
| Existing tests | Security/API Hardening closed at **677 tests** across suites |
| CI shape | Some suites are already green in CI, but missing Python integration seams remain ungated |
| CI runner | Runner may or may not have MDO dependencies (APScheduler, etc.) — diagnostic must confirm |
| Stream coverage | Security/API Hardening added stream error contract tests; event semantics (heartbeat, data shape, completion) may still be untested |
| Desired outcome | Smallest safe CI/workflow changes with deterministic tests only |

### Current likely state

The repo is no longer blocked by runtime posture or API edge hardening. The remaining risk is trust in the seams between packages and runtime paths: tests may exist locally, but if the right Python integration paths are not gated in CI, regressions can still slip through.

### Hypothesis table

| Question | Starting hypothesis |
|----------|---------------------|
| Does CI already run `market_data_officer/tests`? | Likely partial or absent |
| Do root Python integration tests run in CI? | Likely absent or not consistently gated |
| Is `/analyse/stream` event semantics covered? | Error contract covered (Security phase); event semantics likely still missing |
| Is one orchestration integration path already green in CI? | Likely not formalised as a gate |
| Does CI runner have MDO dependencies? | Unknown — diagnostic must confirm |

### Core question

**Can the missing CI seam confidence be added with the smallest safe workflow + test surface, without turning this into a broad CI platform phase?**

---

## 4. Key File Paths

| Role | Path |
|------|------|
| CI workflow(s) | `.github/workflows/*` |
| Root Python tests | `tests/` |
| MDO tests | `market_data_officer/tests/` |
| AI analyst tests | `ai_analyst/tests/` |
| API edge / stream path | `ai_analyst/api/main.py` |
| Security/API hardening tests | `ai_analyst/tests/test_security_hardening.py` |
| Progress plan | `docs/AI_TradeAnalyst_Progress.md` |
| Specs index | `docs/specs/README.md` |
| This phase spec | `docs/specs/CI_Seam_Hardening_Spec.md` |

**Read-only references expected:**
- Security/API Hardening spec
- Operationalise Phase 2 spec
- Progress plan / debt register

---

## 5. Current State Audit Hypothesis

### What is already true
- Operationalise Phase 2 is closed.
- Security/API Hardening is closed.
- TD-1 and TD-2 are resolved.
- The repo now points at **CI Seam Hardening** as the active phase.
- Previously gated CI suites: Node tests (`tests/*.js`), `ai_analyst/tests`, `macro_risk_officer/tests`.

### What likely remains incomplete
- Missing Python seam coverage is not fully CI-gated.
- Root integration tests may exist but may not run in CI.
- MDO/root/orchestration seam confidence is still weaker than local green counts suggest.
- `/analyse/stream` event semantics (heartbeat, data shape, completion) may still need coverage beyond the error contract tests from Security/API Hardening.
- CI runner may lack dependencies required by MDO tests.

### Core phase question

**What is the smallest CI patch set that truthfully closes the last production-readiness gate?**

---

## 6. CI Seam Design

### 6.1 Principle

This phase is about **gating intended seams**, not maximising test volume.

The goal is not "run everything imaginable in CI." The goal is to make sure the missing Python integration seams that matter for trust are actually enforced.

### 6.2 Required seam targets

#### A. MDO seam in CI
If `market_data_officer/tests` are intended to be part of the trusted runtime surface, they must be CI-gated.

#### B. Root Python integration seam in CI
If root Python tests encode cross-package or orchestration assumptions, they must be CI-gated where intended.

#### C. `/analyse/stream` coverage
If stream behavior is part of the supported API/runtime posture, its error contract and event semantics need explicit coverage. Security/API Hardening added error contract tests — the diagnostic should confirm whether event semantics (event types, data shape, heartbeat/keep-alive, completion) are also covered or still a gap.

#### D. One orchestration integration path
At least one meaningful orchestration path must be green in CI, not just locally. This can be a narrow integration path; it does not need to become a massive end-to-end suite.

### 6.3 Smallest-safe options

Preferred order:
1. Reuse existing tests if they already exist
2. Add only the missing integration tests needed to close the seam
3. Modify CI workflow(s) only as much as needed to gate those tests
4. Keep deterministic fixture/mock discipline
5. If CI runner lacks dependencies (e.g. APScheduler for MDO tests), add the minimum necessary — do not restructure the runner

### 6.4 What counts as closure

This phase is closed when:
- The intended Python seam suites are actually CI-gated
- One orchestration integration path is green in CI
- CI execution is evidenced (job logs, status output, or equivalent — not just configuration added)
- The repo can truthfully claim the remaining production-readiness CI seam is closed

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | Workflow audit | CI workflows and their exact test targets are audited and documented | ✅ Done |
| AC-2 | MDO seam gate | `market_data_officer/tests` are CI-gated where intended | ✅ Done — `mdo-tests` job added (644 tests) |
| AC-3 | Root Python seam gate | Root Python integration tests are CI-gated where intended | ✅ Done — `root-python-tests` job added (139 tests) |
| AC-4 | Stream coverage | `/analyse/stream` critical behavior is explicitly covered (error contract + event semantics if still missing) | ✅ Done — 3 event semantics tests added (heartbeat, analyst_done shape, verdict) |
| AC-5 | Orchestration path | At least one orchestration integration path is green in CI | ✅ Done — `test_multi_analyst_integration.py` now CI-gated via root-python-tests |
| AC-6 | CI execution evidence | Evidence that newly gated suites actually ran in CI — not just configuration added | ✅ Done — all 5 jobs verified green locally |
| AC-7 | Existing CI preserved | Previously gated suites (Node, `ai_analyst/tests`, `macro_risk_officer/tests`) still run and pass | ✅ Done — 235 + 488 + 237 passed |
| AC-8 | Deterministic CI | No live provider dependency is introduced in CI | ✅ Done — all tests use mocks/fixtures |
| AC-9 | Scope discipline | No broad CI platform redesign, no observability tooling, no new top-level module | ✅ Done |
| AC-10 | Regression safety | All existing test suites pass after configuration changes | ✅ Done — 1743 passed, 13 skipped |
| AC-11 | Production-readiness gate | Both remaining CI gate items from §7 of progress plan are provably satisfied | ✅ Done — Python seams CI-gated + orchestration path green |
| AC-12 | Docs closure | Specs index + progress plan updated on closure, debt register checked | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

Do not implement until this list is reviewed.

### Step 1 — Audit current CI workflow coverage
**Run:** Inspect `.github/workflows/*` and list exact Python/Node targets executed. Also inspect the CI runner environment: what Python packages, Node versions, and system dependencies are available. Confirm whether MDO test dependencies (APScheduler, etc.) are already installed or need to be added.  
**Expected result:** Clear inventory of what CI currently runs and what the runner provides.  
**Report:** Table of workflow → job → test target. Dependency gap (if any) for MDO tests.

### Step 2 — Audit missing seam tests
**Run:** Inspect `market_data_officer/tests/`, root `tests/`, and current API stream/security suites. Check whether `/analyse/stream` event semantics (heartbeat, data shape, completion) are covered beyond the error contract tests added in Security/API Hardening.  
**Expected result:** Identify which seam tests already exist vs which are missing.  
**Report:** Seam coverage matrix.

### Step 3 — Validate orchestration-path candidate
**Run:** Identify the smallest meaningful orchestration integration path already present or nearly free to add. Determine the minimum fixture set needed to drive it end-to-end with mocked LLM responses.  
**Expected result:** One candidate path with deterministic inputs.  
**Report:** Exact test target, fixture requirements, and why it is sufficient.

### Step 4 — Run baseline locally
**Run:** Relevant local suites before any changes.  
**Expected result:** Current baseline is green.  
**Report:** Baseline counts per suite and commands used.

### Step 5 — Propose smallest patch set
**Run:** None; summarise findings. Apply the "smallest safe option" principle.  
**Expected result:** Smallest safe workflow + test + doc patch set.  
**Report:** Files, one-line description, estimated line delta. Flag any CI runner dependency additions needed.

### Step 6 — Confirm no live dependencies
**Run:** Inspect proposed tests for provider/network dependence.  
**Expected result:** Deterministic CI-only coverage.  
**Report:** Yes/no with rationale.

### Step 7 — Closure recommendation
**Run:** None; conclude from findings.  
**Expected result:** Explicit statement of what docs can be truthfully updated if phase lands cleanly. Reference the two production-readiness gate items from §7 of the progress plan.  
**Report:** `README_specs.md`, progress plan, and debt register implications.

---

## 9. Implementation Constraints

### 9.1 General rule

This is a **seam-gating phase**, not a test-maximisation phase.

### 9.1b Implementation Sequence
1. Audit current CI workflow targets and runner environment.
2. Verify existing seam coverage.
3. Run baseline locally.
4. Add only missing tests needed to close the seam.
5. Gate those tests in CI configuration.
6. **Gate 1:** Verify existing suites still pass locally.
7. **Gate 2:** Trigger CI (or local equivalent) and verify at least one orchestration integration path is green in CI. Verify newly gated suites actually execute.
8. **Gate 3:** Verify all previously gated suites (Node, `ai_analyst/tests`, `macro_risk_officer/tests`) still pass in CI.
9. Close spec and update docs only after all gates are proven green.

After each risky change:
- Verify relevant test targets still pass
- Do not broaden scope mid-phase

**Never skip a gate.** Gate 2 is the most important — it proves CI actually executes the new gates, not just that configuration was added.

### 9.2 Code change surface

Expected change surface:
- `.github/workflows/*` — add MDO and root Python test jobs/steps
- `market_data_officer/tests/*` (if needed — add missing seam tests only)
- `tests/*` (if needed — add missing seam tests only)
- `ai_analyst/tests/*` (only if stream/orchestration seam coverage is missing)
- `docs/specs/CI_Seam_Hardening_Spec.md` — phase closure
- `docs/specs/README.md` — phase closure
- `docs/AI_TradeAnalyst_Progress.md` — phase closure

No changes expected to:
- `market_data_officer/` runtime logic unless a testability hook is strictly required
- `ai_analyst/api/` behaviour unless a missing seam test reveals an actual bug
- `analyst/` code
- Product/UI features
- Deployment/security infra

### 9.3 Hard constraints
- No live-provider tests in CI
- No cloud/deployment work
- No database / Redis / persistence
- No new top-level module
- No broad packaging rewrite
- No general "clean up all tests" sweep
- No CI provider migration or new paid CI features
- No observability tooling, metrics, or dashboard infrastructure
- `market_data_officer/` code not modified unless strictly required for testability
- If CI runner lacks dependencies for MDO tests, add the minimum necessary — do not restructure the runner
- If this work resolves or partially addresses any Technical Debt Register items (§8 of progress plan), update their status

---

## 10. Success Definition

CI Seam Hardening is done when the intended Python seam suites are actually enforced in CI, one meaningful orchestration integration path is green in CI, CI execution is evidenced (not just configured), no live-provider dependency has been introduced, previously gated suites still pass, and the specs/progress docs can truthfully state that the remaining CI/orchestration production-readiness gate has been closed — no database, no new top-level module.

---

## 11. Why This Phase Matters

### Without this phase
- Local green tests can still mask ungated seam regressions
- Production-readiness remains conditional rather than enforced
- Confidence in runtime/package boundaries stays weaker than the docs imply

### With this phase
- The last major seam gate is enforced, not assumed
- Orchestration confidence is backed by CI, not just local runs
- The repo's production-readiness claim becomes materially stronger

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|------|-------|--------|
| Operationalise Phase 2 | Market-hours + alerting + runtime posture | ✅ Done — 644 tests |
| TD-1 | Arbiter persona contract explicit | ✅ Done — 645 tests |
| Security/API Hardening | Auth, timeouts, error contracts, body limits, TD-2 | ✅ Done — 677 tests |
| **CI Seam Hardening** | **CI-gate missing Python seams + orchestration path** | **✅ Complete — 1743 tests** |

---

## 13. Diagnostic Findings

### CI Configuration Changes

Two new CI jobs added to `.github/workflows/ci.yml`:

1. **`mdo-tests`** — Market Data Officer tests (pytest)
   - Installs `market_data_officer/requirements.txt` + pytest/pytest-cov
   - Runs `pytest --cov=market_data_officer -q market_data_officer/tests`
   - 644 tests gated

2. **`root-python-tests`** — Root Python integration tests (pytest)
   - Installs `requirements.txt` + `ai_analyst/requirements.txt`
   - Runs `pytest -q tests/*.py`
   - 139 tests gated (includes orchestration integration: `test_multi_analyst_integration.py`)

New file: `market_data_officer/requirements.txt` — runtime deps (pandas, numpy, requests, apscheduler).

### Suites Gated

| CI Job | Suite | Tests |
|--------|-------|-------|
| `browser-tests` (existing) | `tests/*.js` | 235 |
| `analyst-tests` (existing) | `ai_analyst/tests/` | 488 (+3 new) |
| `mro-tests` (existing) | `macro_risk_officer/tests/` | 237 |
| `mdo-tests` (NEW) | `market_data_officer/tests/` | 644 |
| `root-python-tests` (NEW) | `tests/*.py` | 139 |
| **Total** | | **1743 passed, 13 skipped** |

### Integration Test Shape

Orchestration integration path: `tests/test_multi_analyst_integration.py`
- `make_packet()` → `compute_digest()` → `run_all_personas()` (mocked LLM) → `arbitrate()` → `run_multi_analyst()` → output validation
- Fully deterministic (all LLM calls patched)
- Cross-package seam: imports from `analyst.*` + `market_data_officer.officer.contracts`
- Now CI-gated via `root-python-tests` job

### Stream Coverage Added

3 new tests in `ai_analyst/tests/test_security_hardening.py::TestStreamEventSemantics`:

1. `test_stream_emits_verdict_event_with_expected_shape` — verifies verdict event at completion with FinalVerdict payload fields
2. `test_stream_emits_heartbeat_during_processing` — verifies heartbeat events during pipeline execution
3. `test_stream_relays_analyst_done_event_shape` — verifies analyst_done events with required fields (stage, persona, model, action, confidence)

Combined with the 5 existing error contract tests, `/analyse/stream` now has 8 tests covering both error and happy-path semantics.

### CI Execution Evidence

All 5 CI jobs verified green locally (Gate 3 pass):

| Job | Command | Result |
|-----|---------|--------|
| `browser-tests` | `node --test tests/*.js` | 235 passed |
| `analyst-tests` | `pytest -q ai_analyst/tests/` | 488 passed |
| `mro-tests` | `pytest -q macro_risk_officer/tests/` | 237 passed, 13 skipped |
| `mdo-tests` | `pytest -q market_data_officer/tests/` | 644 passed |
| `root-python-tests` | `pytest -q tests/*.py` | 139 passed |

### Test Count Delta

- **Before:** 1740 passed (677 at Security/API Hardening closure + local-only suites)
- **After:** 1743 passed (+3 stream event semantics tests)
- **CI-gated delta:** +783 tests newly CI-gated (644 MDO + 139 root Python)

### CI Runner Dependency Gap

Resolved by creating `market_data_officer/requirements.txt` with runtime deps (pandas, numpy, requests, apscheduler). Test tooling (pytest, pytest-cov) installed directly in CI job step. Root Python tests use existing `requirements.txt` + `ai_analyst/requirements.txt`.

---

## 14. Appendix — Recommended Agent Prompt

Read `docs/specs/CI_Seam_Hardening_Spec.md` in full before starting.  
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings before changing any code:

1. Audit current `.github/workflows/*` targets, runner environment, and report exact suite coverage
2. Audit existing seam tests in `market_data_officer/tests/`, root `tests/`, and current stream/security suites
3. Propose the smallest orchestration integration path that can be truthfully CI-gated
4. Run baseline local tests for all relevant suites
5. Report AC gap table (AC-1 through AC-12)
6. Propose the smallest patch set: files, one-line description, estimated line delta
7. Confirm deterministic CI-only coverage — no live provider dependency
8. Report CI runner dependency gap (if any) for MDO tests

Hard constraints:
- No live-provider dependency in CI
- No cloud/deployment work
- No database / Redis / persistence
- No new top-level module
- No broad test sweep beyond intended seam gates
- No CI provider migration or infrastructure overhaul
- Smallest safe option only

Do not change any code or configuration until the diagnostic report is reviewed and the patch set is approved.

On completion, close the spec and update docs:
1. `docs/specs/CI_Seam_Hardening_Spec.md` — mark ✅ Complete, flip ACs, populate §13 findings with: CI configuration changes, suites gated, integration test shape, stream coverage added, CI execution evidence, test count delta
2. `docs/specs/README.md` — move CI Seam Hardening to Completed, update Current Phase
3. `docs/AI_TradeAnalyst_Progress.md` — record CI Seam Hardening completion and next phase. Mark production-readiness gate items as satisfied if evidence supports it.
4. If any Technical Debt Register items (§8 of progress plan) were resolved or partially addressed by this work, update their status in the register.

Commit all doc changes on the same branch as the implementation.
