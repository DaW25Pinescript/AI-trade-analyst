# PR 3 — Remote Deployment / Runtime Posture

**Status:** ⏳ Task card drafted — implementation pending  
**Branch:** `feat/mdo-operationalise-phase2-runtime-posture`  
**Base:** `main` (after PR 2 merge)  
**Spec source of truth:** `docs/MDO_Operationalise_Phase2_Spec.md` — Section 7, Section 8 (phase-level ACs), Section 11  
**Regression gate:** 597+ (`market_data_officer/tests`)  
**Package scope:** `market_data_officer/` + narrow runtime docs only  
**Depends on:** PR 1 (549/549), PR 2 (597/597)  
**Phase closure:** This PR closes Operationalise Phase 2.

---

## 1. Purpose

PR 1 added market-hours awareness.  
PR 2 added deterministic failure alerting and recovery logs.

PR 3 closes Operationalise Phase 2 by making the scheduler/runtime **safe and understandable to run outside local dev**, without turning this into a full deployment platform project.

This PR should answer:

- how the runtime is configured for non-local execution
- what startup validation happens before the scheduler begins
- what shutdown behavior is guaranteed
- what operator-facing signals/logs should be expected in steady state and failure state
- what minimum runtime/runbook guidance exists so deployment is reproducible

**Moves FROM → TO**
- **From:** scheduler/runtime works, but "how to run this safely" is partly implicit
- **To:** scheduler/runtime has a clear runtime posture, startup/shutdown behavior, config validation, and minimal operator guidance

---

## 2. Scope

### In scope
- Runtime config surface for scheduler operation
- Startup validation / fail-fast checks
- Graceful shutdown behavior
- Deterministic runtime-mode/logging posture
- Minimal operator-facing run instructions / runbook notes
- Health-check function (read-only per-instrument status snapshot — recommended, not required if diagnostic reveals it is premature)
- Narrow tests for config validation and runtime lifecycle behavior
- Close Operationalise Phase 2 docs if all phase slices are complete

### Out of scope
- Cloud/IaC provisioning
- Docker/Kubernetes buildout
- Health endpoint redesign outside current scheduler/runtime scope
- Process supervisor configuration (systemd, supervisord) — document the expectation, don't implement the supervisor
- Auth/security/API hardening
- Notifier transport integrations
- Persistence/database/Redis
- Distributed scheduler / multi-worker coordination
- Broad packaging refactor
- CI overhaul beyond what is strictly required for this PR
- Any new top-level module outside `market_data_officer/`

If implementation reveals true deployment blockers outside this scope, stop and flag them instead of absorbing them into PR 3.

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| PR 1 output | Market-hours policy exists and is stable |
| PR 2 output | Alert policy and alert/recovery logging exist and are stable |
| Scheduler runtime | APScheduler refresh loop already works |
| Current gap | Runtime posture is more implicit than operator-safe |
| Goal | Make operation predictable without broad architecture change |

### Current likely state

The runtime can now classify market state and emit deterministic alert/recovery signals, but it likely still relies on implicit assumptions about environment variables, startup sequence, and shutdown behavior.

### Core question

Can we make the scheduler safe and predictable for remote/non-local operation with a small runtime-posture layer, without drifting into infrastructure engineering?

---

## 4. Key File Paths

| Role | Path | Notes |
|------|------|-------|
| Controlling spec | `docs/MDO_Operationalise_Phase2_Spec.md` | Read-only until completion note |
| Scheduler runtime | `market_data_officer/scheduler.py` | Expected primary change surface |
| Scheduler entrypoint | `market_data_officer/run_scheduler.py` | Startup/shutdown surface |
| Market-hours policy | `market_data_officer/market_hours.py` | Consumed, not modified |
| Alert policy | `market_data_officer/alert_policy.py` | Consumed, not modified |
| Runtime config/settings | Existing config surface or small new module under `market_data_officer/` | Smallest safe option |
| Runtime docs | Narrow doc/update in existing MDO docs or new `docs/MDO_Runtime_Guide.md` | Keep minimal |
| Tests | `market_data_officer/tests/` | Deterministic lifecycle/config tests |

---

## 5. Current State Audit Hypothesis

### What is already true
- Scheduler can refresh deterministically.
- Market-hours logic exists.
- Alerting/recovery logs exist.
- Tests are already strong in policy and runtime behavior.
- Signal handling (SIGINT/SIGTERM) exists in `run_scheduler.py`.
- Last-known-good preservation is proven under failure and closure.

### What likely remains incomplete
- No explicit startup validation contract.
- No explicit "required runtime config" validation surface.
- Shutdown semantics may be under-specified or untested.
- Operator expectations for logs and runtime states may not yet be documented.
- No health-check or status summary function.

### Core PR 3 question
Can runtime posture be made explicit and testable with minimal code and docs, so the phase can close cleanly?

---

## 6. Runtime Posture Design

### 6.1 Runtime config contract

Define a small explicit runtime configuration surface for scheduler operation.

Examples of the kinds of settings this PR may need to validate:
- scheduler enabled/disabled
- refresh cadence / polling interval
- log level / runtime mode
- artifact/output location
- alerting enabled/disabled as a log-only behavior flag
- dry-run or local-vs-runtime mode, only if already nearly free

Do **not** invent a huge config system. Prefer:
- existing env/config surfaces, or
- a very small new runtime config helper under `market_data_officer/`

### 6.2 Startup validation

Before scheduler start, validate that the runtime is correctly configured. Startup must fail **loudly and early** when the runtime is misconfigured.

Minimum validation candidates (diagnostic will confirm which are relevant):
- Required runtime config is present and non-empty
- Numeric intervals/cadences are sane (positive, within reasonable bounds)
- All configured instruments exist in `INSTRUMENT_FAMILY`
- All families referenced by configured instruments are covered by `FAMILY_SESSION_POLICY`
- Alert threshold constants are positive integers
- Output/artifact paths are writable, or fail fast
- Incompatible runtime modes are rejected explicitly

Startup logs should clearly state the runtime posture: what mode is running, what cadence is active, whether market-hours policy and alert logging are active.

### 6.3 Shutdown behavior

Implement or clarify graceful shutdown behavior:
- Scheduler stops cleanly on signal
- Partial state is not left ambiguous
- Shutdown is logged
- Runtime exits deterministically

No complex process supervisor logic in this PR.

### 6.4 Operator-visible runtime posture

On startup, logs should make it easy to answer:
- What mode is running
- What cadence is active
- Where artifacts/logs are going
- Whether market-hours policy is active
- Whether alert logging is active

On shutdown, logs should make it clear that the runtime stopped intentionally.

### 6.5 Minimal runbook / operator notes

Add concise documentation covering at minimum:

- Required config/env for startup
- Exact command to start the scheduler
- How to stop the scheduler safely
- What "healthy" logs look like (example: successful refresh cycle)
- What a market-closed skip looks like (expected, not a fault)
- What alert escalation and recovery logs from PR 2 mean at a high level
- What to expect during weekends/holidays (stale artifacts are normal, alert counters hold)
- What "safe restart" means (artifacts preserved, alert state resets, cadence resumes)
- Basic troubleshooting: scheduler won't start, repeated alerts, repeated failures

This should be enough for a contributor/operator to run the scheduler without guessing. Keep it concise — this is a runbook, not a manual.

**Constraint: no aspirational documentation.** The runbook must describe what the system actually does after PR 3 lands, not what it should do in future phases.

### 6.6 Health-check function (recommended)

If the diagnostic confirms that per-instrument state (`_alert_state` dict, last refresh results) is accessible, add a read-only function (e.g. `get_scheduler_health()`) that returns a snapshot of current scheduler status.

This is **not** an HTTP endpoint — it is a callable that future phases can expose as an endpoint, CLI tool, or monitoring surface. If the diagnostic reveals this is premature or requires more refactoring than expected, it can be deferred. Document the decision either way.

---

## 7. Acceptance Criteria

### PR-level acceptance criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | Runtime config | Runtime has an explicit validated config surface | ⏳ Pending |
| AC-2 | Startup validation | Misconfiguration fails fast with deterministic error — proven by test | ⏳ Pending |
| AC-3 | Startup logging | Startup logs clearly state runtime posture (mode, cadence, active policies) | ⏳ Pending |
| AC-4 | Shutdown behavior | Scheduler/runtime shuts down cleanly and logs it — proven by test | ⏳ Pending |
| AC-5 | Alert continuity | PR 1/PR 2 behavior remains intact under runtime posture changes | ⏳ Pending |
| AC-6 | Deterministic tests | Config/lifecycle behavior is covered by deterministic tests | ⏳ Pending |
| AC-7 | Operator clarity | Minimal run instructions / runtime expectations are documented with no aspirational content | ⏳ Pending |
| AC-8 | Scope discipline | No infrastructure sprawl, no API/security work, no notifier transport, no new top-level module | ⏳ Pending |
| AC-9 | PR 1 + PR 2 contracts unchanged | `market_hours.py` and `alert_policy.py` not modified | ⏳ Pending |
| AC-10 | Pipeline unchanged | No pipeline contract changes | ⏳ Pending |
| AC-11 | Regression safety | Baseline holds at 597+ plus all new tests green | ⏳ Pending |

### Phase-closure criteria (Workflow E)

These are tracked separately because phase closure is a distinct obligation from PR deliverables. Only execute if all PR-level ACs pass.

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| PC-1 | Phase spec closed | `MDO_Operationalise_Phase2_Spec.md` status flipped to ✅ Complete, all phase ACs marked done, §Diagnostic Findings populated with PR 1/PR 2/PR 3 summary, final test count, naming/scope decisions, and any change surface surprises | ⏳ Pending |
| PC-2 | Specs index updated | `README_specs.md` — Op Phase 2 moved to Completed table with test count, current phase updated to next candidate | ⏳ Pending |
| PC-3 | Progress plan updated | `AI_TradeAnalyst_Progress.md` — Op Phase 2 row marked complete with final test count, current phase updated | ⏳ Pending |
| PC-4 | Phase success definition met | All four statements from spec §11 are provably true: (1) scheduler knows closed vs broken, (2) unexpected stale visible, (3) repeated failures trigger alerts, (4) we know how to run this beyond ad hoc local shell | ⏳ Pending |

---

## 8. Pre-Code Diagnostic Protocol

Do not change code until this diagnostic is reviewed.

### D1 — Audit current runtime entry/startup shape
**Run:** Inspect `run_scheduler.py` and `scheduler.py` to confirm the exact startup sequence, signal handling, and whether any validation already exists.  
**Expected result:** Confirm startup shape, identify the insertion point for validation.  
**Report:** Current startup steps, any existing validation, and the proposed validation location.

### D2 — Audit existing config surface
**Run:** List current env vars, settings helpers, constants, or implicit assumptions that affect runtime operation. Check `SCHEDULE_CONFIG`, `INSTRUMENT_FAMILY`, `FAMILY_SESSION_POLICY`, alert threshold constants.  
**Expected result:** Complete list of config surfaces and their locations.  
**Report:** Config map with source file and whether each is hardcoded, configurable, or env-driven.

### D3 — Audit shutdown behavior
**Run:** Confirm whether graceful shutdown already exists (signal handling, scheduler stop, logging), partially exists, or is absent.  
**Expected result:** Current shutdown behavior documented.  
**Report:** What happens on SIGINT/SIGTERM, whether it's logged, whether it's tested.

### D4 — Audit operator visibility and state surfaces
**Run:** Identify what startup, steady-state, warning, critical, and shutdown logs currently exist. Also inspect `_alert_state` dict and any other per-instrument state to assess health-check feasibility.  
**Expected result:** Current log inventory and state accessibility.  
**Report:** Log entries found, state surfaces available for health-check, and whether a health-check function is feasible in this PR.

### D5 — Audit existing documentation
**Run:** Check for any existing operator/runtime docs in `docs/`, `README.md`, or code comments that overlap with the runbook scope.  
**Expected result:** Identify anything reusable or contradictory.  
**Report:** Existing docs found, relevance, and any conflicts.

### D6 — Run regression baseline
**Run:** Full test suite.  
**Expected result:** 597/597 green before any code changes.  
**Report:** Exact passing count and any anomalies.

### D7 — Report smallest patch set and closure conditions
**Run:** After D1–D6, propose the minimal file set. Also state exactly what doc updates are justified if PR 3 lands cleanly.  
**Expected result:** Smallest correct implementation surface + explicit phase-closure justification.  
**Report:** File list, one-line description per file, estimated line delta. Plus: which phase ACs from the spec are already satisfied by PR 1 + PR 2, and which PR 3 must close.

---

## 9. Implementation Constraints

### 9.1 General rule
This PR is **runtime posture and operator clarity**, not infrastructure expansion.

### 9.1b Implementation sequence
1. Run D1–D7 and report findings. No code changes yet.
2. Add or tighten runtime config validation in the startup path.
3. **Gate 1:** verify 597/597 still pass — validation added, no behavior change for valid config.
4. Add startup posture logging and shutdown behavior/logging if gaps found.
5. **Gate 2:** verify 597/597 still pass.
6. Add health-check function if diagnostic confirmed feasibility (otherwise document deferral).
7. **Gate 3:** verify 597/597 still pass — health-check is read-only, no behavior change.
8. Write operator runbook/docs.
9. Add deterministic config/lifecycle tests.
10. **Final gate:** 597+ total tests pass with all new tests green.
11. Perform phase closure (Workflow E) — only if all PR-level ACs pass:
    - Flip `MDO_Operationalise_Phase2_Spec.md` to ✅ Complete, flip all phase ACs, populate §Diagnostic Findings
    - Update `README_specs.md` — move Op Phase 2 to Completed, update current phase
    - Update `AI_TradeAnalyst_Progress.md` — mark Op Phase 2 complete with final test count, update current phase
12. Commit all doc changes on the same branch as the implementation.

Never skip a regression gate.

### 9.2 Code change surface
Expected change surface:
- `market_data_officer/run_scheduler.py` — startup validation, posture logging
- `market_data_officer/scheduler.py` — health-check function if feasible, shutdown logging if gaps
- Small existing/new runtime config helper under `market_data_officer/` — only if diagnostic justifies it
- `market_data_officer/tests/test_scheduler.py` — startup validation + lifecycle + health-check tests
- `docs/MDO_Runtime_Guide.md` (or equivalent) — operator runbook
- `docs/MDO_Operationalise_Phase2_Spec.md` — phase closure (Workflow E)
- `docs/README_specs.md` — phase closure
- `docs/AI_TradeAnalyst_Progress.md` — phase closure

No changes expected to:
- `market_data_officer/market_hours.py` — consumed, not modified
- `market_data_officer/alert_policy.py` — consumed, not modified
- `market_data_officer/feed/pipeline.py` — pipeline unchanged
- `market_data_officer/officer/` — officer layer unchanged
- `ai_analyst/`, `app/`, API/security paths
- External infra configs

If a broader change surface is required, flag before proceeding.

### 9.3 Hard constraints
- `MarketPacketV2` contract locked — officer layer unchanged
- PR 1 and PR 2 contracts consumed as-is — `market_hours.py` and `alert_policy.py` not modified
- Scheduler calls existing pipeline — if a pipeline change is required, flag before proceeding
- Deterministic fixture/mock tests are the required acceptance backbone — no live provider dependency in CI
- No SQLite or database layer introduced
- Work confined to `market_data_officer/` and `docs/` only — no new top-level module
- No cloud infrastructure, Docker, systemd, or deployment automation
- No security/API hardening in this PR
- No notifier transport integration in this PR
- No external market-calendar dependency
- Fail-fast startup must be proven by deterministic tests — not assumed
- Graceful shutdown behavior must be proven by deterministic tests — not assumed
- Runtime guide must describe implemented behavior only — no aspirational documentation
- Phase closure must follow Workflow E exactly: spec flipped, specs index updated, progress plan updated, all on the same branch

---

## 10. Required Test Matrix

All tests must be deterministic — no live provider calls, no real clock dependency.

### Runtime config / startup
- [ ] Valid runtime config passes validation — scheduler proceeds to start
- [ ] Missing or invalid config fails fast with deterministic, clear error
- [ ] Startup logs include runtime posture fields (mode, cadence, active policies)

### Shutdown / lifecycle
- [ ] Scheduler stops cleanly on signal
- [ ] Shutdown is logged deterministically
- [ ] No ambiguous partial-state behavior on stop path

### Health-check (if implemented)
- [ ] Health-check returns correct shape with all configured instruments
- [ ] Health-check reflects current alert level and market state per instrument
- [ ] Health-check is read-only — calling it does not trigger refresh or alert evaluation

### Regression safety
- [ ] PR 1 market-hours behavior remains intact
- [ ] PR 2 alert/recovery behavior remains intact
- [ ] Runtime posture changes do not alter pipeline contract

---

## 11. Success Definition

PR 3 is done when the scheduler/runtime has an explicit validated runtime posture, fails fast on bad configuration, starts with clear operator-facing logs, shuts down cleanly, preserves PR 1/PR 2 behavior, has operator-facing runbook documentation that matches implemented behavior, is covered by deterministic lifecycle/config tests, the regression gate holds at 597+, and the docs can truthfully mark Operationalise Phase 2 complete — with no pipeline contract changes, no PR 1 or PR 2 contract modifications, no SQLite, no infrastructure dependencies, and no new top-level module.

---

## 12. Why This PR Matters

### Without this PR
- The scheduler may be technically working but operationally under-specified
- Startup/shutdown expectations remain implicit
- Remote/non-local execution is more fragile than it needs to be
- Only the person who built it knows how to run it
- Operationalise Phase 2 cannot close cleanly

### With this PR
- Runtime operation becomes predictable
- Failures happen earlier and more clearly
- Operators know what "healthy" looks like and what to expect during market closure
- Any contributor can start, monitor, and safely restart the scheduler
- Operationalise Phase 2 closes as a coherent phase — the repo can move to Security/API Hardening

---

## 13. Merge Criteria

This PR is mergeable when:

1. D1–D7 are answered and recorded in the PR description.
2. AC-1 through AC-11 (PR-level) are evidenced by code/tests/docs.
3. PC-1 through PC-4 (phase-level closure) are completed on the same branch.
4. All required test matrix cases are green.
5. Regression gate holds at 597+ existing tests plus all new tests green.
6. No PR 1 or PR 2 contracts modified.
7. No pipeline contract changes.
8. No new external or infrastructure dependencies added.
9. Runtime guide matches implemented behavior — no aspirational content.

---

## 14. Appendix — Recommended Agent Prompt

Read `docs/MDO_Operationalise_Phase2_Spec.md` in full before starting.  
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in this task card (D1–D7) and report findings before changing any code.

Required report format:
1. D1–D7 findings
2. AC gap table (AC-1 through AC-11 for PR-level, PC-1 through PC-4 for phase closure)
3. Smallest patch set: files, one-line description, estimated line delta
4. Runtime config recommendation: reuse existing config surface vs tiny helper module
5. Health-check recommendation: feasible in this PR or defer, with rationale
6. Phase-close recommendation: which phase ACs are already satisfied by PR 1 + PR 2, and which PR 3 must close

Hard constraints:
- `MarketPacketV2` contract locked — officer layer unchanged
- PR 1 and PR 2 contracts consumed as-is — `market_hours.py` and `alert_policy.py` not modified
- Scheduler calls existing pipeline — if a pipeline change is required, flag before proceeding
- Deterministic tests only — no live provider dependency in CI, no real clock dependency
- No SQLite or database layer introduced
- Work confined to `market_data_officer/` and `docs/` only — no new top-level module
- No cloud infrastructure, Docker, systemd, or deployment automation
- No security/API hardening in this PR
- No notifier transport integration in this PR
- Fail-fast startup must be proven by deterministic tests — not assumed
- Graceful shutdown must be proven by deterministic tests — not assumed
- Runtime guide must describe implemented behavior only — no aspirational documentation

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion — this PR closes Operationalise Phase 2. Perform full Workflow E closure:
1. `docs/MDO_Operationalise_Phase2_Spec.md` — mark ✅ Complete, flip all phase-level ACs to ✅ Done, populate §Diagnostic Findings with: PR 1/PR 2/PR 3 summary, final test count, naming/scope decisions, and any change surface surprises.
2. `docs/README_specs.md` — move Operationalise Phase 2 to Completed table with test count. Update Current Phase to next candidate (Security/API Hardening).
3. `docs/AI_TradeAnalyst_Progress.md` — mark Operationalise Phase 2 complete with final test count. Update current phase.
4. Commit all doc changes on the same branch as the implementation.
