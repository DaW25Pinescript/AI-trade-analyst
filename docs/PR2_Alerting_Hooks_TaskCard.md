# PR 2 — Deterministic Failure Alerting

**Status:** ⏳ Task card drafted — implementation pending  
**Branch:** `feat/mdo-operationalise-phase2-alerting`  
**Base:** `main` (after PR 1 merge)  
**Spec source of truth:** `docs/MDO_Operationalise_Phase2_Spec.md` — Sections 4.3, 5.3, 5.4, 6, 8  
**Regression gate:** 549+ (`market_data_officer/tests`)  
**Package scope:** `market_data_officer/` only  
**Depends on:** PR 1 — Market-Hours Awareness (complete, 549/549)

---

## 1. Purpose

PR 1 taught the scheduler/runtime to distinguish expected inactivity from genuinely bad freshness states.

PR 2 adds the next operational layer: **deterministic alerting policy** for materially bad live-market conditions.

This PR should answer:
- when a bad live-market condition becomes alert-worthy
- how repeated stale/failure states escalate
- how recovery clears alert state
- how to emit structured alert/recovery logs without introducing external notification infrastructure

**Moves FROM → TO**
- **From:** runtime knows something is bad, but operator visibility is ad hoc / incomplete
- **To:** runtime emits deterministic, edge-triggered alert/recovery signals for genuinely actionable conditions

---

## 2. Scope

### In scope
- New pure alert policy module
- Deterministic alert levels and decision contract
- Minimal in-memory per-instrument alert state in scheduler
- Edge-triggered structured logging for alert and recovery events
- Deterministic unit tests for alert policy
- Deterministic scheduler/integration tests for escalation, suppression, and reset behavior
- Progress annotation in `docs/MDO_Operationalise_Phase2_Spec.md`

### Out of scope
- Email / Slack / Discord / PagerDuty / webhook delivery
- Notifier interface/protocol abstraction (premature — structured logging is the alert transport for Phase 2)
- Persistent alert history
- SQLite / Redis / DB state
- External market-hours or holiday APIs
- Broad scheduler refactor
- Health endpoint / readiness probe redesign
- Security/API hardening
- Remote deployment/runtime docs (belongs to PR 3)
- Any pipeline contract change
- Any MarketPacket/officer contract change
- Any new top-level module outside `market_data_officer/`

If implementation reveals an out-of-scope item is required for correctness, stop and flag it before coding continues.

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| PR 1 output | Market state + freshness classification already exist and are deterministic |
| Scheduler runtime | Scheduler already knows when it skipped, ran, or failed |
| Logging | Structured logging fields exist at baseline and can be extended |
| Alert transport | No external notifier exists yet and none should be added in this PR |
| Runtime state | Process-local in-memory state is sufficient for first-pass alerting |

### Current likely state

The scheduler can now classify runtime conditions, but it likely does not yet decide whether a bad state should escalate into a warning or critical operator-visible event. The real constraint is to add alerting semantics without introducing persistence, infrastructure, or notifier complexity.

### Core question

Can deterministic alerting be added as a pure policy layer plus minimal scheduler state, without changing the pipeline or broadening into deployment/security work?

---

## 4. Key File Paths

| Role | Path | Notes |
|------|------|-------|
| Read-only spec | `docs/MDO_Operationalise_Phase2_Spec.md` | Controlling phase spec |
| Scheduler/runtime | `market_data_officer/scheduler.py` | Expected change surface |
| Market-hours policy | `market_data_officer/market_hours.py` | Consumed, not modified |
| New alert policy module | `market_data_officer/alert_policy.py` | Smallest focused addition |
| Tests | `market_data_officer/tests/` | Deterministic coverage required |

If the diagnostic reveals the actual paths differ, the repo wins. Record the correction in the PR description.

---

## 5. Current State Audit Hypothesis

### What is already true
- PR 1 implemented market-hours awareness and freshness classification.
- The scheduler can distinguish expected closure from bad live-market freshness.
- Structured runtime logging now exists in some form for scheduler decisions.

### What likely remains incomplete
- No explicit alert-decision contract exists yet.
- No deterministic per-instrument alert state/counters likely exist.
- Recovery behavior may be implicit rather than explicit.
- Edge-triggered alert suppression is probably absent.

### Core PR 2 question
Can we convert bad runtime classifications into deterministic alert/recovery decisions without creating noisy repeated logs or adding infrastructure?

---

## 6. Design Requirements

### 6.1 Core policy model

Create a new pure module: `market_data_officer/alert_policy.py`

Include:

```python
from dataclasses import dataclass
from enum import Enum

class RefreshOutcome(Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"

class AlertLevel(Enum):
    NONE = "none"
    WARN = "warn"
    CRITICAL = "critical"

@dataclass(frozen=True)
class AlertDecision:
    level: AlertLevel
    reason_code: str
    should_emit: bool
    should_reset: bool
```

Primary entrypoint:

```python
derive_alert_decision(
    *,
    instrument: str,
    market_state,
    freshness,
    refresh_outcome: RefreshOutcome,
    eval_ts,
    last_success_ts,
    consecutive_stale_live: int,
    consecutive_failures: int,
    previous_level: AlertLevel,
    previous_reason_code: str,
) -> AlertDecision
```

This module must remain: pure, deterministic, free of logging, free of scheduler mutation, free of I/O.

### 6.2 Minimal scheduler state

Maintain process-local per-instrument state only:

```python
{
    "consecutive_stale_live": 0,
    "consecutive_failures": 0,
    "last_alert_level": AlertLevel.NONE,
    "last_alert_reason": "",
    "last_success_ts": datetime | None,
}
```

No disk, database, Redis, or cross-process coordination in this PR.

### 6.3 Counter behavior by classification

The counter behavior must be explicit and deterministic for every possible evaluation outcome.

| Evaluation outcome | `consecutive_stale_live` | `consecutive_failures` | `last_alert_level` |
|-------------------|--------------------------|------------------------|---------------------|
| `FRESH` + success | Reset to 0 | Reset to 0 | Reset to `NONE` (emit recovery if previously non-NONE) |
| `STALE_BAD` | Increment | No change | Evaluate threshold |
| `MISSING_BAD` | Increment | No change | Evaluate threshold |
| Refresh failure (live / unknown market state) | No change | Increment | Evaluate threshold |
| Refresh failure (closed / off-session) | **Hold** (no change) | **Hold** (no change) | **Hold** (no change) |
| `STALE_EXPECTED` (closed/off-session) | **Hold** (no change) | **Hold** (no change) | **Hold** (no change) |
| `MISSING_EXPECTED` (closed/off-session) | **Hold** (no change) | **Hold** (no change) | **Hold** (no change) |
| `UNKNOWN` conservative path | Increment (treat as live) | No change | Evaluate threshold |

**Hold rule:** During expected closure, counters freeze. They do not increment (the market being closed is not a fault) and they do not reset (the closure didn't fix whatever was wrong before). If an instrument has 2 consecutive `STALE_BAD` evaluations, then the market closes for the weekend, then reopens and immediately produces another `STALE_BAD` — the counter resumes at 3, not 1.

### 6.4 Refresh outcome must be explicit

Do not infer every failure from freshness alone.

The scheduler must pass an explicit `RefreshOutcome` into alert policy, so the system can distinguish:
- `SUCCESS` — pipeline ran and succeeded
- `SKIPPED` — policy skip due to market-hours
- `FAILED` — pipeline ran and raised an exception
- `NOT_ATTEMPTED` — refresh not invoked for other reasons

This prevents ambiguous alert reasons.

### 6.5 Alert rules

**Always NONE:** If `market_state` is a non-live expected state (closed/off-session), alert level must be `NONE`. No escalation during expected closure — including refresh failures that occur during closure. Counters hold; they do not increment.

**Healthy live state:** If market is live and refresh succeeds with `FRESH` classification, reset all counters and clear alert level. If previous level was non-NONE, emit recovery.

**Stale live escalation:** If market is live and stale-live persists:
- `WARN` at warn threshold
- `CRITICAL` at critical threshold

**Refresh failure escalation:** If market is live and refresh fails:
- Increment failure counter
- Escalate faster than stale-live (failures are more urgent than stale data)
- Failure reason dominates stale-live reason where both apply

**Recovery:** If previous level was `WARN` or `CRITICAL` and the instrument becomes healthy again:
- Emit one recovery log
- Reset all counters
- Return to `NONE`

### 6.6 Deterministic threshold constants

Use named constants in `alert_policy.py` for this PR, not environment config:

```python
WARN_STALE_LIVE_THRESHOLD = 2
CRITICAL_STALE_LIVE_THRESHOLD = 4
CRITICAL_FAILURE_THRESHOLD = 2
```

If implementation reveals the exact values need minor adjustment, keep them as explicit constants and document the choice. Configurable thresholds can be added in a future PR or phase.

### 6.7 Edge-triggered logging only

Emit alert/recovery logs only when:
- Level increases (NONE → WARN, WARN → CRITICAL)
- Reason materially changes at the same level
- Recovery occurs (WARN/CRITICAL → NONE)

Do **not** log the same WARN or CRITICAL every cycle. The `should_emit` field on `AlertDecision` controls this — the scheduler only logs when `should_emit is True`.

### 6.8 Structured log fields

Alert/recovery logs must include at minimum:

- `instrument`
- `alert_level`
- `reason_code`
- `market_state`
- `freshness`
- `refresh_outcome`
- `consecutive_stale_live`
- `consecutive_failures`
- `last_success_ts`
- `eval_ts`

Recovery logs should also include:
- `recovered_from_level`
- `recovered_from_reason`

### 6.9 Alert isolation

Alert evaluation failure (unexpected exception in policy function or logging) must **not** crash the scheduler or prevent the next refresh cycle. The scheduler should catch exceptions from alert evaluation, log the alerting error, and continue. Alert logic is supplementary — it must never block pipeline execution.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | Policy contract | `alert_policy.py` exists with deterministic pure decision logic | ⏳ Pending |
| AC-2 | Explicit refresh outcome | Refresh outcome is modeled explicitly as an enum, not inferred only from freshness | ⏳ Pending |
| AC-3 | Minimal state | Scheduler maintains only process-local per-instrument alert state | ⏳ Pending |
| AC-4 | Closed suppression | No alerts emitted during expected closed/off-session states — proven by test | ⏳ Pending |
| AC-5 | Counter hold during closure | Counters freeze during expected closure (no increment, no reset) — proven by test | ⏳ Pending |
| AC-6 | Stale escalation | Persistent stale-live conditions escalate deterministically through WARN → CRITICAL | ⏳ Pending |
| AC-7 | Failure escalation | Repeated live-market refresh failures escalate deterministically | ⏳ Pending |
| AC-8 | Recovery reset | Successful healthy refresh fully resets alert state and emits one recovery log | ⏳ Pending |
| AC-9 | Edge triggering | Alert emission is edge-triggered — duplicate level/reason does not re-emit — proven by test | ⏳ Pending |
| AC-10 | Structured logs | Alert/recovery logs include all required context fields from §6.8 | ⏳ Pending |
| AC-11 | Alert isolation | Alert evaluation failure does not crash the scheduler or block the next refresh — proven by test | ⏳ Pending |
| AC-12 | PR 1 contracts unchanged | `market_hours.py` not modified; `MarketState`, `FreshnessClassification`, `ReasonCode` consumed as-is | ⏳ Pending |
| AC-13 | Pipeline safety | No pipeline contract changes | ⏳ Pending |
| AC-14 | Deterministic tests | Full unit + integration tests are deterministic — no live provider, no real clock | ⏳ Pending |
| AC-15 | Scope discipline | No SQLite, no notifier transport, no new top-level module | ⏳ Pending |
| AC-16 | Regression safety | Baseline holds at 549+ plus all new alerting tests green | ⏳ Pending |

---

## 8. Pre-Code Diagnostic Protocol

Do not change code until this diagnostic is reviewed.

### D1 — Audit PR 1 output surface
**Run:** Inspect `market_hours.py` and `scheduler.py` to confirm exact enum/function names, return types, and how the scheduler currently records refresh outcomes.  
**Expected result:** Confirm `classify_freshness()` return shape and `refresh_instrument()` return shape.  
**Report:** Exact signatures, return types, and the hook point where alert evaluation should be inserted.

### D2 — Audit current scheduler logging/state shape
**Run:** Inspect `scheduler.py` for any existing in-memory counters, last-success timestamps, or log helpers that should be reused.  
**Expected result:** Confirm whether any accumulation logic or per-instrument state exists.  
**Report:** Anything found, or "no per-instrument alert state exists."

### D3 — Search for existing alert-ish logic
**Run:**
```bash
rg -rn "alert\|warn\|critical\|consecutive\|failure_count\|stale_count\|notify" market_data_officer/
```
**Expected result:** Identify any existing alert or counter logic.  
**Report:** File paths and whether anything is reusable or stale.

### D4 — Define smallest alert-state shape
**Run:** Based on D1–D3, confirm the minimum per-instrument state needed in the scheduler and whether a small helper object is cleaner than ad hoc dicts.  
**Expected result:** Recommended state shape with rationale.  
**Report:** Proposed structure and field list.

### D5 — Audit current success/failure/skip outcomes
**Run:** Confirm how the scheduler currently distinguishes: refresh succeeded, refresh failed, refresh skipped due to market-hours policy, refresh not attempted.  
**Expected result:** Confirm whether `RefreshOutcome` can be derived from existing return values or needs explicit modeling.  
**Report:** Current outcome shape and recommendation.

### D6 — Run regression baseline
**Run:** Full test suite.  
**Expected result:** 549/549 green before any code changes.  
**Report:** Exact passing count and any anomalies.

### D7 — Report smallest patch set
**Run:** After D1–D6, propose the minimal file set.  
**Expected result:** Smallest correct implementation surface.  
**Report:** File list, one-line description per file, estimated line delta, and any ambiguity to resolve before coding.

---

## 9. Implementation Constraints

### 9.1 General rule

This PR is policy-first and log-first, not infrastructure-first.

### 9.1b Implementation sequence

1. Run D1–D7 and report findings. No code changes yet.
2. Add `alert_policy.py` with enums, dataclass, constants, and `derive_alert_decision()` function only.
3. **Gate 1:** verify 549/549 still pass — new module added, nothing consumes it yet.
4. Add minimal scheduler in-memory alert state. Wire scheduler to compute refresh outcome, call alert policy, and emit edge-triggered structured logs.
5. **Gate 2:** verify 549/549 still pass — scheduler now consumes alerting layer.
6. Add deterministic policy tests in `test_alert_policy.py` and integration tests in `test_scheduler.py`.
7. **Final gate:** 549+ total tests pass with all new tests green.
8. Add spec progress annotation only after tests are green.

Never skip a regression gate.

### 9.2 Code change surface

Expected change surface:
- `market_data_officer/alert_policy.py` — new focused module
- `market_data_officer/scheduler.py` — wire alert evaluation after refresh
- `market_data_officer/tests/test_alert_policy.py` — new test suite
- `market_data_officer/tests/test_scheduler.py` — additional integration tests
- `docs/MDO_Operationalise_Phase2_Spec.md` — progress annotation only

No changes expected to:
- `market_data_officer/market_hours.py` — consumed, not modified
- `market_data_officer/feed/pipeline.py` — pipeline unchanged
- `market_data_officer/officer/` — officer layer unchanged
- `market_data_officer/run_scheduler.py` — entrypoint unchanged unless D1 reveals startup alerting needs it
- `ai_analyst/`, `app/`, API/security paths
- External notifier integrations
- MarketPacketV2 / officer contracts

If the diagnostic reveals a wider change surface is required, flag it before proceeding.

### 9.3 Hard constraints

- `MarketPacketV2` contract locked — officer layer unchanged
- PR 1 contracts consumed as-is — `market_hours.py` not modified
- Scheduler calls existing pipeline — if a pipeline change is required, flag before proceeding
- Deterministic fixture/mock tests are the required acceptance backbone — no live provider dependency in CI
- No SQLite or database layer introduced
- Work confined to `market_data_officer/` only — no new top-level module
- No external market-calendar dependency
- No notifier transport implementation in this PR
- No remote deployment/runtime docs in this PR
- Alert evaluation failure must not crash the scheduler
- Recovery behavior must be proven by deterministic tests — not assumed
- Duplicate alert spam must be prevented by deterministic tests — not assumed

---

## 10. Required Test Matrix

All tests must be deterministic — no live provider calls, no real clock dependency.

### Alert policy unit tests
- [ ] Closed/off-session state always returns `NONE`
- [ ] Fresh live success returns `NONE` with `should_reset=True`
- [ ] Repeated `STALE_BAD` crosses warn threshold → `WARN` with `should_emit=True`
- [ ] Repeated `STALE_BAD` crosses critical threshold → `CRITICAL` with `should_emit=True`
- [ ] Repeated refresh failure escalates faster than stale-live
- [ ] Failure reason dominates stale-live reason where both apply
- [ ] Recovery decision: prior non-NONE state becomes healthy → `should_emit=True`, `should_reset=True`
- [ ] No duplicate emit: same level + same reason as previous → `should_emit=False`
- [ ] Reason change at same level: same level + different reason as previous → `should_emit=True`
- [ ] `UNKNOWN` conservative path increments stale counter (consistent with PR 1 treat-as-OPEN)

### Counter behavior tests
- [ ] `FRESH` + success resets both counters to zero
- [ ] `STALE_BAD` increments `consecutive_stale_live`, does not change `consecutive_failures`
- [ ] `MISSING_BAD` increments `consecutive_stale_live`, does not change `consecutive_failures`
- [ ] Refresh failure during live/unknown increments `consecutive_failures`, does not change `consecutive_stale_live`
- [ ] Refresh failure during closed/off-session holds both counters (no increment, no reset)
- [ ] `STALE_EXPECTED` holds both counters (no increment, no reset)
- [ ] `MISSING_EXPECTED` holds both counters (no increment, no reset)
- [ ] Counters are per-instrument: instrument A's failures do not affect instrument B's counters
- [ ] Hold-through-closure: counter at 2 before weekend, resumes at 3 on Monday `STALE_BAD`

### Scheduler integration tests
- [ ] Live + stale-live sequence emits `WARN` at threshold
- [ ] Live + repeated stale-live emits `CRITICAL` at threshold
- [ ] Live + repeated refresh failures emits `CRITICAL`
- [ ] Closed/off-session path emits no alert even after many consecutive evaluations
- [ ] Recovery emits one structured recovery log with `recovered_from_level` and `recovered_from_reason`
- [ ] Structured log fields include all required alert context from §6.8
- [ ] Scheduler state resets correctly after success
- [ ] Alert evaluation failure (mocked exception in policy) does not crash scheduler
- [ ] Existing PR 1 runtime behavior remains intact

---

## 11. Success Definition

PR 2 is done when deterministic alert policy exists as a small pure module, the scheduler maintains only minimal in-memory alert state, genuinely bad live-market conditions escalate in a stable and non-spammy way, recovery is logged and resets state, counters hold during expected closure and resume on market reopen, alert evaluation failure cannot crash the scheduler, all new tests are deterministic and green, and the regression gate holds with no pipeline contract changes, no PR 1 contract modifications, no SQLite, and no new top-level module.

---

## 12. Why This PR Matters

### Without this PR
- The runtime may know something is wrong but not surface it cleanly
- Operators still rely on ad hoc inspection
- Repeated stale/failing conditions can remain invisible or noisy
- PR 3 deployment/runtime work would lack trustworthy operational signals

### With this PR
- Bad live-market conditions become visible and actionable
- Expected closures remain quiet
- Recovery is explicit
- Remote/runtime work in PR 3 can build on clean alert semantics

---

## 13. Merge Criteria

This PR is mergeable when:

1. D1–D7 are answered and recorded in the PR description.
2. AC-1 through AC-16 are evidenced by code/tests.
3. All required test matrix cases are green.
4. Regression gate holds at 549+ existing tests plus all new alerting tests green.
5. No PR 1 contracts modified (`market_hours.py` unchanged).
6. No pipeline contract changes.
7. No new external dependencies added.
8. `README_specs.md` remains unchanged — phase status still active.
9. `docs/MDO_Operationalise_Phase2_Spec.md` has a progress annotation for PR 2 completion.

---

## 14. Appendix — Recommended Agent Prompt

Read `docs/MDO_Operationalise_Phase2_Spec.md` in full before starting.  
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in this task card (D1–D7) and report findings before changing any code.

Required report format:
1. D1–D7 findings
2. AC gap table (AC-1 through AC-16)
3. Smallest patch set: files, one-line description, estimated line delta
4. Alert-state storage recommendation: plain dict vs tiny helper object, with rationale
5. Refresh-outcome recommendation: confirm exact success/skipped/failed/not-attempted shape

Hard constraints:
- `MarketPacketV2` contract locked — officer layer unchanged
- PR 1 contracts consumed as-is — `market_hours.py` not modified
- Scheduler calls existing pipeline — if a pipeline change is required, flag before proceeding
- Deterministic tests only — no live provider dependency in CI and no real clock dependency
- No SQLite or database layer introduced
- Work confined to `market_data_officer/` only — no new top-level module
- No external market-calendar dependency
- No notifier transport implementation in this PR
- No remote deployment/runtime docs in this PR
- Recovery behavior must be proven by deterministic tests — not assumed
- Duplicate alert spam must be prevented by deterministic tests — not assumed
- Alert evaluation failure must not crash the scheduler — proven by test

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion:
1. Update `docs/MDO_Operationalise_Phase2_Spec.md` — add PR 2 progress annotation noting alerting hooks implemented and tested. Do **not** mark the overall phase as complete (PR 3 remains).
2. Do **not** advance `docs/README_specs.md` — Operationalise Phase 2 remains active.
3. Do **not** change `AI_TradeAnalyst_Progress.md` unless implementation reveals a material scope correction.
4. Commit all doc changes on the same branch as the implementation.
