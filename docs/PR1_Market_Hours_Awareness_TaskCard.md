# PR 1 — Market-Hours Awareness

**Status:** ⏳ Task card drafted — implementation pending  
**Branch:** `feat/mdo-operationalise-phase2-market-hours`  
**Base:** `main` (after docs-only baseline commit)  
**Spec source of truth:** `docs/MDO_Operationalise_Phase2_Spec.md` — Sections 4.1, 5.1, 5.2, 5.3  
**Regression gate:** 494+ (`market_data_officer/tests`)  
**Package scope:** `market_data_officer/` only

---

## 1. Purpose

Operationalise Phase 1 proved scheduled refresh execution.

Operationalise Phase 2 now needs runtime intelligence so the scheduler can distinguish between:
- expected market closure
- off-session inactivity
- genuine refresh failure
- stale-but-acceptable artifacts
- stale artifacts requiring operator action

This PR introduces **market-hours awareness**, the foundation needed before alerting hooks (PR 2) and deployment/runtime posture work (PR 3).

**Moves FROM → TO**
- **From:** all missing or old data effectively looks the same at runtime
- **To:** runtime behavior is market-aware, deterministic, and ready for alerting consumption

---

## 2. Scope

### In scope
- Define canonical market-hours state contract
- Define artifact freshness classification model with reason codes
- Integrate market-state evaluation into scheduler/runtime decisions
- Preserve last-known-good artifacts under skip/failure conditions
- Add deterministic tests for state evaluation and freshness classification
- Emit structured logging fields sufficient for later alerting/observability work
- Add a progress annotation to `docs/MDO_Operationalise_Phase2_Spec.md`

### Out of scope
- Pager / Slack / email alert delivery
- Remote deployment automation and environment docs
- Security/API hardening
- Full observability dashboard or metrics surface
- Pipeline contract redesign
- External market-calendar dependency
- Large scheduler architecture rewrite
- SQLite or database introduction
- Any new top-level module outside `market_data_officer/`

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Scheduler base | Operationalise Phase 1 added the scheduler/runtime entrypoint and refresh loop |
| Runtime health | Current behavior likely does not classify stale artifacts relative to market state |
| Instrument policy | Session/hours policy may live in registry or may need to be added there |
| Artifact age | Timestamp-based freshness is either present in partial form or must be formalized |
| Logging | Existing logging likely exists, but not yet with market-state/freshness semantics |

### Current likely state

The scheduler can already run, but it likely does not distinguish between expected inactivity and actual bad freshness states. The real constraint in this PR is to add a small, deterministic policy layer without changing the core pipeline contract.

### Core question

Can market-hours-aware freshness classification be added without breaking the current scheduler pipeline or broadening scope into alerting/deployment work?

---

## 4. Key File Paths

| Role | Path | Notes |
|------|------|-------|
| Read-only spec | `docs/MDO_Operationalise_Phase2_Spec.md` | controlling phase spec |
| Scheduler/runtime | `market_data_officer/scheduler.py` | expected change surface |
| Scheduler entrypoint | `market_data_officer/run_scheduler.py` | verify in diagnostic |
| Registry/config | `market_data_officer/instrument_registry.py` | verify whether hours/session metadata exists |
| New policy module | `market_data_officer/market_hours.py` | smallest focused addition if needed |
| Tests | `market_data_officer/tests/` | deterministic coverage required |

If the diagnostic reveals the actual paths differ, the repo wins. Record the correction in the PR description and spec progress annotation.

---

## 5. Pre-Code Diagnostic Protocol

Do not implement until this list is reviewed.

### D1 — Confirm scheduler base
**Run:** inspect Phase 1 scheduler files and entrypoint wiring.  
**Expected result:** confirm whether `run_scheduler.py` and `scheduler.py` exist, what classes/functions they expose, and where refresh decisions currently happen.  
**Report:** file paths, key functions/classes, and the likely hook point for market-hours logic.

### D2 — Search for existing session/market-hours logic
**Run:**
```bash
rg -rn "market.hours|session|is_open|is_closed|trading_hours|market_calendar" market_data_officer/ ai_analyst/
```
**Expected result:** identify any existing session/market-open logic or confirm it is absent.  
**Report:** file paths and whether any logic is reusable or stale.

### D3 — Audit registry/config for time/session fields
**Run:** inspect `instrument_registry.py` and related config.  
**Expected result:** confirm whether per-instrument schedule/session/hours metadata already exists.  
**Report:** exact field names found, or “not found”.

### D4 — Audit current stale-data detection
**Run:** inspect current artifact/status evaluation path.  
**Expected result:** determine whether staleness is already defined by timestamp, partially defined, or undefined.  
**Report:** current behavior and the likely minimal insertion point for freshness classification.

### D5 — Run regression baseline
**Run:** the current Phase 1 baseline suite.  
**Expected result:** 494/494 green before any code changes.  
**Report:** exact passing count and any anomalies.

### D6 — Propose smallest safe patch set
**Run:** after D1–D5, propose the minimal file set.  
**Expected result:** smallest correct implementation surface.  
**Report:** file list, one-line description per file, and estimated line delta.

---

## 6. Design Requirements

### 6.1 Market state contract

Define a small explicit state model. Names must be stable and readable in logs/tests.

| State | Meaning |
|-------|---------|
| `OPEN` | Market expected to be active; refresh on cadence |
| `CLOSED_EXPECTED` | Market known to be closed; skip is expected, not a fault |
| `OFF_SESSION_EXPECTED` | Known non-trading period (weekend, public holiday, inter-session gap) |
| `UNKNOWN` | State cannot be confidently determined; fail conservatively |

Expose a function such as:
```python
get_market_state(instrument, timestamp) -> MarketState
```

**Policy source of truth:** registry extension or dedicated config module inside `market_data_officer/`. No external calendar API dependency.

### 6.2 Artifact freshness classification

Artifact health is a function of:
- current market state
- last successful refresh timestamp
- expected cadence
- grace/tolerance buffer

| Market state | Artifact present + fresh | Artifact present + overdue | Artifact missing |
|-------------|-------------------------|---------------------------|-----------------|
| `OPEN` | `FRESH` | `STALE_BAD` | `MISSING_BAD` |
| `CLOSED_EXPECTED` / `OFF_SESSION_EXPECTED` | `FRESH` | `STALE_EXPECTED` | `MISSING_EXPECTED` |
| `UNKNOWN` | `FRESH` | `STALE_BAD` (conservative) | `MISSING_BAD` (conservative) |

Expose a function such as:
```python
classify_freshness(instrument, last_artifact_ts, now, market_state, cadence, grace) -> FreshnessResult
```

The result must include classification, reason code, age, threshold used, and the evaluated market state.

### 6.3 Reason codes

Every classification path must produce a short stable reason code. Examples:
- `open_and_fresh`
- `open_and_overdue`
- `closed_stale_expected`
- `closed_missing_expected`
- `unknown_conservative_stale`
- `refresh_failed_artifact_preserved`

The exact names may vary, but they must be readable enough that future alerting can consume them without re-deriving logic.

### 6.4 Conservative behavior

- `OPEN` + overdue/missing → bad
- `CLOSED_EXPECTED` / `OFF_SESSION_EXPECTED` + overdue/missing → expected, not bad
- `UNKNOWN` → treat as open for classification purposes
- skipped or failed refresh must never delete or overwrite a valid existing artifact

### 6.5 Deterministic semantics

The same inputs must always yield the same outputs. No live provider calls. No real clock dependency in tests.

### 6.6 Structured logging

Minimum fields per evaluation:
- `instrument`
- `provider`
- `evaluated_market_state`
- `freshness_classification`
- `reason_code`
- `last_successful_refresh_ts`
- `expected_cadence`
- `grace_threshold_used`
- `evaluation_timestamp`

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | State contract | Named market-state model exists with `OPEN`, `CLOSED_EXPECTED`, `OFF_SESSION_EXPECTED`, `UNKNOWN` | ⏳ Pending |
| AC-2 | Freshness contract | Named freshness model exists with `FRESH`, `STALE_BAD`, `STALE_EXPECTED`, `MISSING_BAD`, `MISSING_EXPECTED` | ⏳ Pending |
| AC-3 | Reason codes | Every classification path emits a stable reason code | ⏳ Pending |
| AC-4 | Open/closed semantics | Runtime classifies stale/missing artifacts differently when market is open vs expected closed | ⏳ Pending |
| AC-5 | Unknown handling | `UNKNOWN` path behaves conservatively and is explicitly tested | ⏳ Pending |
| AC-6 | Last-known-good preservation | Skipped or failed refresh never destroys a valid artifact | ⏳ Pending |
| AC-7 | Logging | Structured logging includes market-state and freshness context fields | ⏳ Pending |
| AC-8 | Deterministic tests | All added tests are deterministic, with no live provider dependency and no real clock dependency | ⏳ Pending |
| AC-9 | Pipeline unchanged | Scheduler calls existing pipeline; if pipeline change is required, it is flagged before proceeding | ⏳ Pending |
| AC-10 | Scope discipline | No SQLite or database layer introduced; work confined to `market_data_officer/` only — no new top-level module | ⏳ Pending |
| AC-11 | Negative case | Closed/off-session path proves refresh is skipped rather than silently treated as success/failure | ⏳ Pending |
| AC-12 | Regression safety | Baseline gate holds at 494+ plus all new market-hours tests green | ⏳ Pending |

---

## 8. Implementation Constraints

### 8.1 General rule

Choose the smallest safe policy layer that makes market-hours semantics explicit without redesigning the scheduler.

### 8.1b Implementation sequence

1. Run D1–D6 and report findings. No code changes yet.
2. Add the focused market-hours policy module or registry extension.
3. Verify **494/494** still pass after the contract/model layer lands.
4. Wire scheduler/runtime to consume the policy results.
5. Verify **494/494** still pass after scheduler wiring.
6. Add deterministic tests for state evaluation, freshness classification, and runtime behavior.
7. Verify **494+** total tests pass with all new tests green.
8. Add spec progress annotation only after tests are green.

Never skip a regression gate.

### 8.2 Code change surface

Expected change surface:
- `market_data_officer/market_hours.py` or equivalent focused module
- `market_data_officer/scheduler.py`
- `market_data_officer/instrument_registry.py` or config equivalent
- `market_data_officer/tests/...`
- `docs/MDO_Operationalise_Phase2_Spec.md` (progress annotation only)

No changes expected to:
- `ai_analyst/`
- `app/`
- API/security paths
- feeder/provider contracts unless diagnostic proves it is necessary

If the diagnostic reveals a wider change surface is required, flag it before proceeding.

### 8.3 Hard constraints

- `MarketPacketV2` contract locked — officer layer unchanged
- Registry is source of truth — no hardcoded provider/instrument strings in runtime code
- Scheduler calls existing pipeline — if a pipeline change is required, flag before proceeding
- Deterministic fixture/mock tests are the required acceptance backbone — no live provider dependency in CI
- No SQLite or database layer introduced
- Work confined to `market_data_officer/` only — no new top-level module
- No external market-calendar dependency

---

## 9. Required Test Matrix

All tests must be deterministic — no live provider calls, no real clock dependency.

### Market state tests
- [ ] Open market: mocked Tuesday 14:00 UTC for EURUSD → `OPEN`
- [ ] Closed market: mocked Saturday 03:00 UTC for EURUSD → `CLOSED_EXPECTED`
- [ ] Off-session path: explicit off-session input or equivalent deterministic case → `OFF_SESSION_EXPECTED`
- [ ] Unknown state: unsupported or ambiguous instrument/timestamp → `UNKNOWN`
- [ ] Instrument-aware hours: same timestamp, different instruments (e.g. EURUSD vs XAUUSD) produce different states where policy requires it

### Freshness classification tests
- [ ] `OPEN` + fresh artifact → `FRESH`
- [ ] `OPEN` + overdue artifact → `STALE_BAD`
- [ ] `OPEN` + missing artifact → `MISSING_BAD`
- [ ] `CLOSED_EXPECTED` + stale artifact → `STALE_EXPECTED`
- [ ] `CLOSED_EXPECTED` + missing artifact → `MISSING_EXPECTED`
- [ ] `UNKNOWN` + stale artifact → `STALE_BAD`
- [ ] `UNKNOWN` + missing artifact → `MISSING_BAD`

### Runtime/integration tests
- [ ] Open market → scheduler calls `run_pipeline`
- [ ] Closed market → scheduler skips `run_pipeline`
- [ ] Refresh failure preserves last-known-good artifact
- [ ] Structured log fields include market state + freshness classification

---

## 10. Success Definition

PR 1 is done when market-hours awareness is implemented as a small deterministic policy layer, the scheduler/runtime uses it to distinguish expected inactivity from genuine stale/bad states, last-known-good artifacts are preserved, structured logging is ready for later alerting work, all new tests are deterministic and green, and the regression gate holds with no SQLite or database layer introduced and no new top-level module.

---

## 11. Why This PR Matters

### Without this PR
- weekend silence and Tuesday failure can look identical
- alerting work in PR 2 would be built on ambiguous runtime semantics
- operators cannot tell expected inactivity from bad freshness states

### With this PR
- scheduler behavior becomes market-aware and deterministic
- stale/missing classification becomes explicit and testable
- alerting and deployment work can build on clean runtime semantics

---

## 12. Merge Criteria

This PR is mergeable when:
1. D1–D6 are answered and recorded in the PR description
2. AC-1 through AC-12 are evidenced by code/tests
3. Regression gate holds at 494+ existing tests plus all new tests green
4. No pipeline contract changes were required, or any required deviation was flagged before implementation
5. `README_specs.md` remains unchanged because phase status is still active
6. `docs/MDO_Operationalise_Phase2_Spec.md` has a progress annotation for PR 1 completion

---

## 13. Appendix — Recommended Agent Prompt

Read `docs/MDO_Operationalise_Phase2_Spec.md` in full before starting.  
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in this task card (D1–D6) and report findings before changing any code.

Required report format:
1. D1–D6 findings
2. AC gap table (AC-1 through AC-12)
3. Smallest patch set: files, one-line description, estimated line delta
4. Policy source-of-truth recommendation: registry extension vs dedicated config module, with rationale

Hard constraints:
- `MarketPacketV2` contract locked — officer layer unchanged
- Scheduler calls existing pipeline — if a pipeline change is required, flag before proceeding
- Registry is source of truth — no hardcoded provider/instrument strings in runtime code
- Closed/off-session behavior must be proven by deterministic tests — not assumed
- Deterministic tests only — no live provider dependency in CI and no real clock dependency
- No SQLite or database layer introduced
- Work confined to `market_data_officer/` only — no new top-level module
- No external market-calendar dependency

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion:
1. Update `docs/MDO_Operationalise_Phase2_Spec.md` with PR 1 completion/progress notes
2. Do **not** advance `docs/README_specs.md` yet — Operationalise Phase 2 remains active
3. Do **not** change `AI_TradeAnalyst_Progress.md` unless the implementation reveals a material scope correction
4. Commit all doc changes on the same branch as the implementation
