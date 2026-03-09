# Market Data Officer — Operationalise Phase 1 Spec

## Repo-Aligned Implementation Target

**Project:** AI Trade Analyst  
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Date:** 8 March 2026  
**Status:** ⏳ Spec drafted — implementation pending

> **Context:** All five trusted instruments have proven relay spines, explicit provider policy, and 468/468 green tests. Every phase so far has answered "does one run work?" This phase answers "does the system stay fresh over time?" It introduces scheduled feed refresh using APScheduler — local/dev-friendly first, no cloud deployment, no service rewrite, no UI changes.

---

## 1. Purpose

Move from *"run the feed manually when needed"* to *"the feed refreshes on a schedule, automatically, with defined failure behavior."*

This phase answers six questions the current codebase leaves open:

1. **What is being scheduled?** Feed refresh and hot-package rebuild for all five trusted instruments.
2. **For which instruments?** All five trusted instruments — EURUSD, GBPUSD, XAUUSD, XAGUSD, XPTUSD.
3. **How often?** Per-family cadence — FX instruments refresh more frequently than metals. Market-hours awareness is deferred.
4. **What happens on failure?** Log and keep last known good artifacts. Retry on next scheduled interval. Do not crash the scheduler on a single instrument failure.
5. **What is the runtime shape?** One in-process APScheduler instance, one scheduler module inside `market_data_officer/`, one CLI entrypoint to start/stop.
6. **What is explicitly out of scope?** Cloud deployment, distributed jobs, UI scheduler management, multi-service framework, market-hours gating.

The diagnostic must answer each of these sub-questions independently before the patch set is proposed — see Section 8.

---

## 2. Scope

### In scope

- APScheduler integration inside `market_data_officer/`
- per-family refresh cadence defined in config
- scheduled invocation of the existing feed pipeline (no pipeline changes)
- failure isolation — one instrument failure does not stop other instruments or crash the scheduler
- last-known-good artifact preservation on failure
- structured schedule logging (instrument, run time, outcome, vendor used)
- one CLI entrypoint to start the scheduler (`run_scheduler.py` or equivalent)
- deterministic tests for schedule config, job isolation, and failure handling

### Out of scope

- no cloud deployment or remote orchestration
- no distributed job queues
- no UI scheduler management or dashboard
- no market-hours awareness (deferred — schedule runs regardless of market session)
- no alert/notification system (log only in this phase)
- no `MarketPacketV2` contract changes
- no new top-level module — work inside `market_data_officer/` only
- no SQLite or database layer
- no change to the existing feed pipeline or artifact contracts

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Runtime artifacts | remain under `market_data/` |
| Storage model | file-based spine — artifact shape unchanged |
| Officer contract | `build_market_packet()` / `refresh_from_latest_exports()` unchanged |
| Trusted instruments | EURUSD, GBPUSD, XAUUSD, XAGUSD, XPTUSD (all 5) |
| Provider policy | explicit per-instrument policy already in registry |
| Fallback | yFinance fallback already wired and tested |
| Test philosophy | deterministic fixture/mock tests remain the required acceptance backbone |
| Live checks | optional manual smoke only — not a CI gate |
| Deployment target | local / dev environment first |

### Refresh cadence hypothesis

Starting hypothesis — diagnostic and config should confirm or revise:

| Family | Instruments | Cadence | Rationale |
|--------|-------------|---------|-----------|
| FX | EURUSD, GBPUSD | Every 1 hour | FX data updates frequently; bi5 archive lags ~1h |
| Metals | XAUUSD, XAGUSD, XPTUSD | Every 4 hours | Metals move less intraday; reduce unnecessary Dukascopy calls |

> Cadence is config-driven — not hardcoded in the scheduler. Changing it should require only a config edit, not a code change.

### Failure behavior hypothesis

| Scenario | Expected behavior |
|----------|-----------------|
| Dukascopy empty (weekend, off-hours) | yFinance fallback attempted per policy; if also empty, log and keep last known good |
| Provider transport exception | Same as above — fallback, then keep last known good |
| Decode/validation failure | Log error, keep last known good, do not crash scheduler |
| Unhandled exception in job | Catch at job boundary, log, continue scheduling other instruments |

### Failure behavior hypothesis

| Scenario | Expected behavior |
|----------|-----------------|
| Dukascopy empty (weekend / off-hours) | yFinance fallback attempted per policy; if also empty, log and keep last known good |
| Provider transport exception | Same — fallback, then keep last known good |
| Decode / validation failure | Log error, keep last known good, do not crash scheduler |
| Unhandled exception in job | Catch at job boundary, log, continue scheduling other instruments |

> The pipeline only writes artifacts on successful completion. The scheduler must not bypass this — last-known-good preservation is a pipeline property, not a scheduler responsibility. The job boundary catch ensures a failed job does not interfere with this behavior.

---

## 4. Key File Paths

| Role | Path |
|------|------|
| Instrument registry | `market_data_officer/instrument_registry.py` |
| Feed pipeline | `market_data_officer/feed/pipeline.py` |
| Feed config | `market_data_officer/feed/config.py` |
| Scheduler module (new) | `market_data_officer/scheduler.py` |
| Scheduler CLI (new) | `market_data_officer/run_scheduler.py` |
| Tests | `market_data_officer/tests/` |
| Provider Routing tests (reference) | `market_data_officer/tests/test_provider_routing.py` |

---

## 5. Current State Audit Hypothesis

### What is already true

- feed pipeline is fully functional for all five trusted instruments
- provider policy is explicit and registry-driven
- fallback behavior is tested and proven
- artifact contracts are stable
- `run_feed.py` provides a working manual entrypoint

### What likely remains

- no APScheduler dependency in `pyproject.toml`
- no scheduler module in `market_data_officer/`
- no per-family cadence config
- no scheduled CLI entrypoint
- no failure isolation at the job boundary — an unhandled exception in the feed pipeline could propagate uncaught
- no schedule logging

### Core Operationalise question

Can APScheduler be added inside `market_data_officer/` as a thin scheduling layer over the existing pipeline — with per-family cadence, job isolation, and last-known-good preservation — without changing any existing contracts?

---

## 6. Scheduler Design

### 6.1 Runtime shape

One APScheduler `BackgroundScheduler` instance, started by `run_scheduler.py`. Each instrument gets its own scheduled job. Jobs call the existing feed pipeline directly — no new pipeline abstraction.

```
run_scheduler.py
  └── scheduler.py
        ├── BackgroundScheduler (APScheduler)
        ├── job: refresh_instrument("EURUSD")   ← every 1h
        ├── job: refresh_instrument("GBPUSD")   ← every 1h
        ├── job: refresh_instrument("XAUUSD")   ← every 4h
        ├── job: refresh_instrument("XAGUSD")   ← every 4h
        └── job: refresh_instrument("XPTUSD")   ← every 4h
```

### 6.2 No-overlap policy

The scheduler must define what happens if a run is still active when the next trigger arrives. Minimum acceptable behavior:

- do not allow overlapping refreshes for the same instrument
- either skip or coalesce overlapping triggers — APScheduler's `max_instances=1` per job is the natural mechanism
- log when a trigger is skipped due to active job

### 6.3 Job isolation

Each job must be wrapped in a try/except at the job boundary. A failure in one instrument's job must not affect other instruments or crash the scheduler. This is the most important design constraint.

```python
def refresh_instrument(instrument: str) -> None:
    try:
        # call existing pipeline
        ...
        log_run(instrument, outcome="success", vendor=...)
    except Exception as e:
        log_run(instrument, outcome="failure", error=str(e))
        # keep last known good artifacts — do not delete on failure
```

### 6.4 Cadence config

Cadence should be driven by config, not hardcoded. Starting shape — diagnostic may revise:

```python
SCHEDULE_CONFIG = {
    "EURUSD": {"interval_hours": 1},
    "GBPUSD": {"interval_hours": 1},
    "XAUUSD": {"interval_hours": 4},
    "XAGUSD": {"interval_hours": 4},
    "XPTUSD": {"interval_hours": 4},
}
```

### 6.5 Last-known-good preservation

On any failure, the existing artifacts in `market_data/packages/latest/` must not be deleted or overwritten with partial/empty data. The pipeline only writes artifacts on successful completion — the scheduler must not bypass this.

### 6.6 Schedule logging

Structured log entry per run:

```
[2026-03-08 15:00:01] EURUSD  SUCCESS  vendor=dukascopy  duration=4.2s
[2026-03-08 15:00:03] GBPUSD  SUCCESS  vendor=dukascopy  duration=3.8s
[2026-03-08 15:01:12] XAUUSD  FAILURE  error="requests.RequestException: ..."
```

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | APScheduler installed | `import apscheduler` succeeds in the MDO environment | ⏳ Pending |
| AC-2 | Scheduler module exists | `market_data_officer/scheduler.py` with `BackgroundScheduler` and per-instrument jobs | ⏳ Pending |
| AC-3 | No-overlap policy enforced | Overlapping refreshes for the same instrument are prevented — skip or coalesce, not stack | ⏳ Pending |
| AC-4 | Per-family cadence configured | FX instruments on 1h interval, Metals on 4h — driven by config, not hardcoded | ⏳ Pending |
| AC-5 | Job isolation proven | A failure in one instrument's job does not crash the scheduler or affect other jobs | ⏳ Pending |
| AC-6 | Last-known-good preserved | Artifacts are not overwritten with partial/empty data on failure | ⏳ Pending |
| AC-7 | Schedule logging | Each run produces a structured log entry: instrument, outcome, vendor, duration | ⏳ Pending |
| AC-8 | CLI entrypoint works | `python market_data_officer/run_scheduler.py` starts the scheduler without error | ⏳ Pending |
| AC-9 | Pipeline unchanged — manual path preserved | Existing `run_feed.py` manual entrypoint still works; no pipeline contract changes | ⏳ Pending |
| AC-10 | Artifact contracts unchanged | Hot-package shape, manifest schema, `MarketPacketV2` contract all unchanged | ⏳ Pending |
| AC-11 | Provider policy and provenance preserved in scheduled runs | Scheduled runs still obey registry-driven provider policy; correct vendor/source in artifacts | ⏳ Pending |
| AC-12 | Deterministic tests | Schedule config, job isolation, and failure handling proven by mock-driven tests — no live scheduler in CI | ⏳ Pending |
| AC-13 | Regression safety | 468/468 existing tests remain green | ⏳ Pending |
| AC-14 | No SQLite | No DB layer introduced | ⏳ Pending |
| AC-15 | No new top-level module | Scheduler module inside `market_data_officer/` only | ⏳ Pending |

---

## 8. Pre-Code Diagnostic Protocol

Run these steps before changing any code. Report findings against AC-1 through AC-13.

### Step 1 — Verify APScheduler is available

```bash
python -c "import apscheduler; print(apscheduler.__version__)"
```

If not installed:
```bash
pip install apscheduler --break-system-packages
```

Confirm it is added to `pyproject.toml` as a dependency (not just installed locally).

### Step 2 — Audit existing pipeline entrypoint

```bash
grep -n "def run\|def main\|argparse\|__main__" market_data_officer/run_feed.py
```

Report: what is the callable interface on `run_feed.py`? The scheduler needs to call the pipeline programmatically — confirm whether there is a clean function to call or whether the entrypoint is CLI-only.

### Step 3 — Audit failure behavior in the existing pipeline

```bash
grep -n "except\|raise\|try\|log\|logger" market_data_officer/feed/pipeline.py
```

Report: what exceptions currently propagate out of the pipeline? Are there unhandled paths that would crash a scheduler job? This determines the try/except shape needed at the job boundary.

### Step 4 — Check for existing logging infrastructure

```bash
grep -rn "import logging\|logger\|LOG" market_data_officer/ --include="*.py"
```

Report: does a logging pattern already exist in MDO? The scheduler log should use the same pattern rather than introducing a new one.

### Step 5 — Run baseline

```bash
python -m pytest market_data_officer/tests/ -q --tb=short
```

Expected: 468/468 green.

### Step 5b — Recommend startup/shutdown shape

Based on Steps 1–5, report which runtime shape is smallest:
- CLI entrypoint (`run_scheduler.py`) that starts a `BackgroundScheduler` and blocks
- in-process helper invoked by an existing entrypoint
- other minimal shape

Preferred answer: the shape that fits current repo conventions without introducing a new service pattern.

### Step 6 — Report smallest patch set

Based on Steps 1–5:
- confirm APScheduler is installable and dependency added
- identify the callable pipeline interface the scheduler will use
- identify what needs wrapping at the job boundary
- propose file list, one-line description per file, estimated line delta

Do not implement until this list is reviewed.

---

## 9. Implementation Constraints

### 9.1 General rule

This is a **scheduling layer phase**, not a pipeline redesign phase.

The scheduler calls the existing pipeline. The pipeline does not know it is being called by a scheduler. No pipeline changes should be needed — if a pipeline change is required, that is a scope violation and must be flagged before proceeding.

### 9.1b Implementation Sequence

1. Install APScheduler, add to `pyproject.toml`, confirm importable
2. Verify **468/468** still pass
3. Create `scheduler.py` — `BackgroundScheduler`, per-instrument jobs, job isolation, cadence config, schedule logging
4. Create `run_scheduler.py` — CLI entrypoint to start/stop
5. Verify **468/468** still pass — scheduler exists but tests don't run it live
6. Add deterministic tests: schedule config correct, job isolation proven, failure handling correct (mock pipeline failure)
7. Verify **468+** pass — final gate

### 9.2 Testing strategy

**No APScheduler instance should be started in any test.** Test the job function directly, not the scheduler loop — starting the scheduler in tests introduces timing dependencies and flakiness.

Tests should:
- verify schedule config (correct instruments, correct intervals, correct family assignment)
- mock a pipeline failure and prove the job catches it, logs it, and does not propagate
- mock a successful run and prove the log entry is correct
- prove the scheduler does not modify artifacts on failure (last-known-good)

No APScheduler instance should be started in any test. Test the job function directly, not the scheduler loop.

### 9.3 Code change surface

```
market_data_officer/scheduler.py          # new — BackgroundScheduler + jobs + cadence config
market_data_officer/run_scheduler.py      # new — CLI entrypoint
market_data_officer/tests/test_scheduler.py  # new — deterministic scheduler tests
pyproject.toml                            # add apscheduler dependency
```

No changes expected to: `feed/pipeline.py`, `feed/export.py`, `officer/service.py`, `officer/contracts.py`, `instrument_registry.py`.

> If the diagnostic reveals a pipeline change is required to support scheduling, that is a scope flag — stop and report before proceeding.

---

## 10. Success Definition

> **Operationalise Phase 1 is done when:**  
> APScheduler is installed and declared as a dependency → `scheduler.py` runs per-instrument jobs on per-family cadence → job isolation proven: one failure does not crash the scheduler or affect other instruments → last-known-good artifacts preserved on failure → schedule logging produces structured entries → `run_scheduler.py` starts cleanly → existing pipeline and manual entrypoint unchanged → 468+ tests green → no SQLite → no new top-level module.

The feed no longer requires a human to trigger it. It runs, fails safely, and stays fresh.

---

## 11. Why This Phase Matters

Without Operationalise Phase 1:
- the feed only refreshes when someone manually runs it
- there are no freshness guarantees for the analyst layer
- the provider policy and fallback behavior are proven but never exercised automatically
- the system is a well-tested prototype, not an operational tool

With Operationalise Phase 1:
- artifacts stay fresh automatically within the cadence window
- failure is isolated, logged, and self-recovering on the next interval
- the registry-driven provider policy is exercised continuously, not just in tests
- the foundation for market-hours awareness, alerting, and remote deployment is in place

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 1A | EURUSD baseline spine | ✅ Done — 359/359 |
| Phase 1B | XAUUSD spine | ✅ Done — 364/364 |
| Phase E+ | Instrument registry + GBPUSD/XAGUSD/XPTUSD | ✅ Done — 404/404 |
| Provider Switchover | yFinance fallback + vendor provenance | ✅ Done — 404/404 |
| Phase F | Instrument Promotion — all 5 trusted | ✅ Done — 419/419 |
| Per-Instrument Provider Routing | Explicit policy per instrument | ✅ Done — 468/468 |
| Operationalise Phase 1 | APScheduler feed refresh (this spec) | ⏳ Spec drafted — implementation pending |
| Operationalise Phase 2 | Market-hours awareness, alerting, remote deployment | ⏳ Pending |

---

## 13. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 8).*

---

## 14. Appendix — Recommended Agent Prompt

```
Read `docs/MDO_Operationalise_Spec.md` in full before starting. Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings before changing any code:

1. Confirm APScheduler is importable — if not, install and add to pyproject.toml
2. Audit run_feed.py — confirm the callable pipeline interface the scheduler will use
3. Audit feed/pipeline.py exception paths — identify what needs wrapping at the job boundary
4. Check existing logging infrastructure — confirm pattern to use for schedule logs
5. Run 468/468 baseline
6. Report AC gap table (AC-1 through AC-13)
7. Propose smallest patch set: files, one-line description, estimated line delta
8. Propose cadence config for all five instruments — justify any deviation from the family default (FX=1h, Metals=4h)

Hard constraints:
- No pipeline changes — the scheduler calls the existing pipeline; if a pipeline change is needed, flag it before proceeding
- Job isolation is the most important design constraint — one instrument failure must not affect others or crash the scheduler
- Last-known-good artifacts must be preserved on failure — do not overwrite with partial/empty data
- Cadence must be config-driven, not hardcoded
- No live scheduler in CI — test job functions directly, not the scheduler loop
- No SQLite, no new top-level module
- MarketPacketV2 contract locked, artifact shape unchanged
- Deterministic tests only

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion, close the spec and update docs:
1. `docs/MDO_Operationalise_Spec.md` — mark ✅ Complete, flip all AC cells, populate §13 Diagnostic Findings with: APScheduler version, callable pipeline interface found, exception paths identified, cadence config chosen, AC gap table (pre-impl), patch set (files + line delta), regression gate results
2. `docs/README_specs.md` — move to Completed, update Current Phase to Operationalise Phase 2
3. `docs/AI_TradeAnalyst_Progress.md` — update current phase, add completed row with test count

Commit all doc changes on the same branch as the implementation.
```

---

*Drafted from closed Per-Instrument Provider Routing spec, README_specs, and progress plan baseline on 8 March 2026.*
