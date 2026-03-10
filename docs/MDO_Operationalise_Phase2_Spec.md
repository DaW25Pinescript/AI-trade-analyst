# Market Data Officer — Operationalise Phase 2 Spec

## Repo-Aligned Implementation Target

This phase extends the completed APScheduler base from Operationalise Phase 1 into a more production-usable runtime by adding **market-hours awareness**, **alerting hooks**, and **remote deployment/runtime guidance**.

**Status:** ✅ Complete
**Depends on:** `docs/MDO_Operationalise_Spec.md` (Operationalise Phase 1 — complete)
**Completed:** 10 March 2026
**Final test count:** 644/644 (market_data_officer/tests)

---

## 1. Purpose

Operationalise Phase 1 proved that the feed pipeline can be driven by APScheduler and protected by deterministic tests. Phase 2 should make that scheduler practical for repeated runtime use by answering the operational questions that Phase 1 deliberately left open:

- What should happen when a market is closed?
- How should stale data be interpreted when closure is expected?
- How should failures become visible to an operator?
- What minimum deployment/runtime guidance is needed so the scheduler can run beyond a local dev shell?

This phase is **not** a redesign of the feed pipeline. It is an operational policy phase that sits on top of the working scheduler foundation.

---

## 2. Scope

### In scope

- Market-hours awareness policy for scheduled refresh jobs.
- Distinguishing expected inactivity from failure/staleness.
- Alerting hooks for repeated failures or stale artifacts.
- Remote deployment/runtime guidance for scheduler startup, environment variables, and health expectations.
- Tests for market-open vs market-closed behavior and alert-trigger conditions.
- Structured status/logging additions required to support the above.

### Out of scope

- Replacing APScheduler.
- Multi-worker/distributed scheduling.
- Cloud infrastructure provisioning.
- Full auth/security redesign for `/analyse` or other API routes.
- Rewiring the main `ai_analyst` runtime around MDO contracts.
- UI redesign work.

If implementation reveals that one of the out-of-scope items is required for correctness, that is a scope violation and must be flagged before coding continues.

---

## 3. Repo-Aligned Assumptions

### What is already true

- Operationalise Phase 1 is complete and green at **494/494 tests**.
- APScheduler is the accepted scheduler base.
- The scheduler is intended to preserve last-known-good artifacts rather than destroying useful state after a failed refresh.
- Current docs already identify Phase 2 as: **market-hours awareness, alerting, remote deployment**.

### What still needs to be defined explicitly

- Market-hours source of truth and how it is represented per instrument.
- Closed-market handling policy.
- Stale-data classification policy.
- Alert thresholds and alert transport abstraction.
- Deployment/runtime expectations for local vs remote execution.

---

## 4. Key Questions This Phase Must Close

1. **Market-hours truth:** What determines whether a refresh should run, skip, or downgrade severity?
2. **Staleness semantics:** When is old data acceptable, and when is it a fault?
3. **Alerting:** What events should produce alerts, and after how many failures?
4. **Operator usability:** What minimum runtime/deployment notes are required so the scheduler is runnable beyond a local ad hoc shell?
5. **Observability:** What status/log shape is required to tell “healthy, closed, stale, failing” apart?

---

## 5. Desired Runtime Behavior

### 5.1 Market-hours states

The scheduler/runtime should distinguish at least these states:

- `open` — market expected to refresh normally
- `closed` — market known to be closed; skipped refresh is expected behavior
- `holiday_or_off_session` — market not expected to move/update for a known reason
- `stale_but_expected` — stale artifacts exist, but closure/off-session explains them
- `stale_and_bad` — artifacts are stale when the market should be open
- `refresh_failed` — attempted refresh failed

### 5.2 Expected scheduler behavior by state

- `open` → run refresh on cadence, record success/failure.
- `closed` / `holiday_or_off_session` → do not treat lack of new artifacts as failure; preserve last-known-good.
- `stale_but_expected` → surface as informational or low-severity state, not as operational failure.
- `stale_and_bad` → mark unhealthy, increment failure/alert counters as defined.
- `refresh_failed` → preserve last-known-good, record failure, apply alert policy.

### 5.3 Last-known-good rule

This phase keeps the Phase 1 doctrine: **never destroy a last-known-good artifact just because a newer refresh failed or a market is closed.**

---

## 6. Alerting Design

### 6.1 Objective

Provide lightweight alerting hooks so repeated refresh failures or unexpected stale conditions become visible without requiring a full observability platform first.

### 6.2 Minimum alert-trigger candidates

- Repeated refresh failures for the same instrument/job.
- `stale_and_bad` detected while market is expected to be open.
- Scheduler startup failure.
- Optional: repeated skip/closed anomalies if market-hours policy itself becomes inconsistent.

### 6.3 Alert transport rule

This phase should define an **alert interface/hook**, not hard-code a heavy notification stack. Logging plus an injectable notifier abstraction is acceptable.

---

## 7. Remote Deployment / Runtime Guidance

This phase should document the minimum viable operational posture for running the scheduler outside a local interactive session.

### Minimum guidance to produce

- Required environment variables/config.
- Startup entrypoint and expected process shape.
- Health/status signals an operator should check.
- Log location/shape expectations.
- What “safe restart” means.
- What to do when a market is closed but stale artifacts are present.

This can live partly in code comments/startup docs, but the phase should leave behind enough written guidance that a contributor can run it consistently.

---

## 8. Acceptance Criteria

All acceptance criteria are met:

1. ✅ Done — Market-open vs market-closed behavior is deterministic and covered by tests. (PR 1 — 55 tests)
2. ✅ Done — The system distinguishes expected stale state from failure stale state. (PR 1 — FreshnessClassification enum + classify_freshness)
3. ✅ Done — Repeated refresh failures or unexpected stale conditions can trigger an alert hook. (PR 2 — 48 tests)
4. ✅ Done — Last-known-good artifacts are preserved under closed-market and failure scenarios. (PR 1 + Phase 1 doctrine, regression-tested)
5. ✅ Done — Remote/runtime guidance exists and matches the implemented startup path. (PR 3 — docs/MDO_Runtime_Guide.md)
6. ✅ Done — All existing tests remain green, and new tests cover the added operational semantics. (644/644 — 597 baseline + 47 new in PR 3)

---

## 9. Pre-Code Diagnostic Protocol

Before implementation, perform these checks and report findings briefly:

### Step 1 — Audit Phase 1 scheduler base

Confirm the actual scheduler files/classes/functions added in Operationalise Phase 1 and verify the runtime entrypoint shape.

### Step 2 — Audit current time/session knowledge in repo

Search for any existing session/market-hours helpers, calendars, or instrument schedule logic already present anywhere in the repo.

### Step 3 — Define market-hours source of truth

Decide whether market-hours behavior comes from static policy, provider metadata, or a repo-local helper. Document the choice before coding.

### Step 4 — Audit current stale-data handling

Identify how stale artifacts are currently detected, if at all, and whether open vs closed semantics already exist.

### Step 5 — Audit current logging/status surfaces

Find what operator-visible logs, dashboard endpoints, or status files already exist and reuse them where possible.

### Step 6 — Run regression baseline

Reconfirm the Phase 1 test baseline before touching behavior.

### Step 7 — Report smallest patch set

List the smallest file set needed to implement Phase 2 correctly.

---

## 10. Implementation Constraints

### 10.1 General rule

This phase should be **policy-first, not infrastructure-first**.

Do not introduce cloud services, deployment frameworks, or large dependency additions just to solve alerting or market-hours logic unless the existing repo surface truly cannot support the phase.

### 10.2 Scope discipline

Do not turn this phase into Security/API Hardening.

Security work discovered during implementation can be noted, but authn/authz, timeout policy for `/analyse`, and error-contract hardening belong to the next named phase unless required to make this phase functionally correct.

### 10.3 Code change surface

Expected likely file areas:

- existing scheduler/runtime files from Operationalise Phase 1
- scheduler config or runtime config module
- status/logging helpers
- optional notifier abstraction
- test files covering open/closed/stale/alert behavior
- operational runtime/deployment notes

Keep the patch surface intentionally narrow.

---

## 11. Success Definition

Operationalise Phase 2 succeeds when a contributor can truthfully say:

- “The scheduler knows the difference between a closed market and a broken refresh.”
- “Unexpected stale state becomes visible.”
- “Repeated failures can trigger alerts.”
- “We know how to run this beyond an ad hoc local shell.”

---

## 12. Why This Phase Matters

Without this phase, the repo has a scheduler but not yet a trustworthy operational posture.

That creates several risks:

- false alarms during normal market closures
- silent failures hidden inside expected inactivity
- confusing stale-data states
- unclear deployment expectations

Phase 2 turns the scheduler from “it runs” into “it behaves intelligibly under real operating conditions.”

---

## 13. Phase Roadmap

- **Operationalise Phase 1** — APScheduler feed refresh base — ✅ Complete
- **Operationalise Phase 2** — market-hours awareness, alerting, remote deployment — ✅ Complete
  - **PR 1 — Market-Hours Awareness** — ✅ Complete (9 Mar 2026)
    - Added `market_hours.py`: `MarketState` enum (`OPEN`, `CLOSED_EXPECTED`, `OFF_SESSION_EXPECTED`, `UNKNOWN`), `FreshnessClassification` enum, stable `ReasonCode` enum, `INSTRUMENT_FAMILY` dict, `FAMILY_SESSION_POLICY`, `get_market_state()`, `classify_freshness()` — all pure functions, deterministic, no external dependencies.
    - Wired `scheduler.py:refresh_instrument()` to skip pipeline on `CLOSED_EXPECTED`/`OFF_SESSION_EXPECTED`, classify freshness on success/failure, emit structured log fields (`market_state`, `freshness`, `reason_code`, `evaluation_ts`).
    - 55 new deterministic tests (total 549). Full test matrix: market state, freshness classification, reason codes, UNKNOWN conservative path, scheduler skip/proceed integration, structured log fields, artifact preservation.
    - Known simplification: Metals session hours use FX window (Sun 22:00–Fri 22:00 UTC) as starting estimate. Refine if instrument-specific session data becomes available.
    - Pipeline contract unchanged. `MarketPacketV2` unchanged. No SQLite. No external calendar. Work confined to `market_data_officer/`.
  - **PR 2 — Alerting Hooks** — ✅ Complete (10 Mar 2026)
    - Added `alert_policy.py`: `RefreshOutcome` enum (`SUCCESS`, `SKIPPED`, `FAILED`, `NOT_ATTEMPTED`), `AlertLevel` enum (`NONE`, `WARN`, `CRITICAL`), frozen `AlertDecision` dataclass (`level`, `reason_code`, `should_emit`, `should_reset`), threshold constants (`WARN_STALE_LIVE_THRESHOLD=2`, `CRITICAL_STALE_LIVE_THRESHOLD=4`, `CRITICAL_FAILURE_THRESHOLD=2`), `derive_alert_decision()` — pure stateless function, deterministic, no logging, no I/O.
    - Wired `scheduler.py:refresh_instrument()` with per-instrument alert state dict (`_alert_state`), outcome-to-enum mapping (`_map_outcome`), counter update logic per §6.3 (hold during closure, reset on recovery, increment on live stale/failure), `_evaluate_alert()` with edge-triggered structured log emission and try/except isolation (AC-11).
    - 48 new deterministic tests (total 597). Full test matrix: closed suppression, stale-live WARN/CRITICAL escalation, failure escalation, recovery with structured fields, edge-trigger suppression, reason-change re-emit, counter hold through closure, per-instrument isolation, alert eval crash isolation, PR 1 behavior intact.
    - `market_hours.py` unchanged. Pipeline contract unchanged. `MarketPacketV2` unchanged. No SQLite. No notifier transport. No new top-level module. Work confined to `market_data_officer/`.
  - **PR 3 — Remote Deployment/Runtime Guidance** — ✅ Complete (10 Mar 2026)
    - Added `runtime_config.py`: frozen `RuntimeConfig` dataclass, `validate_runtime_config()` with 7-point validation, `load_runtime_config()`. Defaults match all hardcoded values exactly.
    - Wired `run_scheduler.py` with config validation (fail-fast on bad config), structured startup posture banner, signal-name shutdown logging, clean exit logging.
    - Added `get_scheduler_health()` to `scheduler.py` — read-only snapshot of per-instrument alert state. No side effects, no refactoring needed.
    - Added `docs/MDO_Runtime_Guide.md` — operator runbook covering startup, shutdown, steady-state logs, alert escalation/recovery, weekends, health-check, config, troubleshooting. Describes implemented behavior only.
    - 47 new deterministic tests (total 644). Test matrix: config validation (valid/invalid/cross-ref), startup fail-fast, startup posture logging, shutdown signal handling, health-check shape/read-only/state reflection, PR 1 + PR 2 regression safety.
    - `market_hours.py` unchanged. `alert_policy.py` unchanged. Pipeline contract unchanged. `MarketPacketV2` unchanged. No SQLite. No new top-level module. Work confined to `market_data_officer/` and `docs/`.
- **Next likely phase** — Security/API Hardening — authn/authz, timeout policy, error contract tightening — 🔜 Candidate

---

## 15. Diagnostic Findings

### PR 1 — Market-Hours Awareness (9 Mar 2026)
- Market-hours policy implemented as pure functions in `market_hours.py`
- `MarketState` enum with 4 states, `FreshnessClassification` with 5 states, `ReasonCode` with 12 stable codes
- Scheduler wired to skip on closure, classify freshness on all outcomes
- 55 new tests, baseline moved from 494 to 549

### PR 2 — Alerting Hooks (10 Mar 2026)
- Alert policy implemented as pure stateless function in `alert_policy.py`
- Edge-triggered structured log emission with counter hold/reset/escalation semantics
- Alert evaluation isolated by try/except — never crashes scheduler
- 48 new tests, baseline moved from 549 to 597

### PR 3 — Remote Deployment/Runtime Guidance (10 Mar 2026)
- Runtime config validation surface added as `runtime_config.py`
- Startup fail-fast proven by deterministic tests
- Shutdown signal handling proven by deterministic tests
- Health-check function added (read-only, no side effects)
- Operator runbook added — describes implemented behavior only
- 47 new tests, baseline moved from 597 to 644

### Final test count
- **644/644** in `market_data_officer/tests/`
- Phase 2 total: +150 tests across 3 PRs (55 + 48 + 47)

### Naming and scope decisions
- **Metals hours:** FX session window (Sun 22:00–Fri 22:00 UTC) used as starting estimate for all metals. Correct for XAUUSD. Refinement deferred until instrument-specific session data is available.
- **Pure policy modules:** `market_hours.py` and `alert_policy.py` are stateless pure-function modules with no I/O or logging. State management lives in `scheduler.py`.
- **No notifier transport:** Alert visibility is log-based only. Injectable notifier abstraction deferred to future phases.
- **Health-check as callable:** `get_scheduler_health()` is a function, not an HTTP endpoint. Future phases can expose it.

### Change surface surprises
- None. All changes confined to expected surfaces. No pipeline modifications. No PR 1/PR 2 contract changes. No scope violations.

---

## 14. Recommended Agent Prompt

Use this prompt for implementation work:

> Implement Operationalise Phase 2 for Market Data Officer using `docs/MDO_Operationalise_Phase2_Spec.md` as the source of truth.
> 
> Rules:
> - diagnostic-first
> - smallest correct patch set
> - no unrelated architecture changes
> - preserve last-known-good artifacts
> - keep APScheduler as the scheduler base
> - add deterministic tests for open/closed/stale/alert behavior
> - document runtime/deployment expectations as part of the phase
> 
> First, report:
> 1. existing scheduler/runtime files from Phase 1
> 2. any existing session/market-hours helpers already in repo
> 3. stale-data logic already present
> 4. proposed smallest patch set
> 
> Only then implement.
