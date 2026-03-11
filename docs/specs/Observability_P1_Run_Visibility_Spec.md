# AI Trade Analyst — Observability Phase 1: Analyst Pipeline Run Visibility Spec

**Status:** ✅ Complete — implemented 11 March 2026
**Date:** 11 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

This phase follows the closure of:

- Security/API Hardening — ✅ Complete (677 tests)
- CI Seam Hardening — ✅ Complete (1743 tests across 5 CI jobs)

This phase answers one tight question:

**When the analyst pipeline runs, can a developer see exactly what happened — which stages executed, which analysts ran or skipped, what the arbiter decided, and where artifacts landed — without reading source code or guessing?**

**Moves FROM → TO**
- **From:** the pipeline runs end-to-end and returns a valid response, but the path between request-in and response-out is opaque. Developers must infer pipeline behavior from the final response shape or read code to understand what happened internally.
- **To:** every analyst pipeline run produces a deterministic, structured run record (JSON on disk) and a concise operator summary (stdout), giving stage-by-stage visibility into what ran, what was skipped, what failed, and what was produced.

---

## 2. Scope

### In scope
- Instrument the analyst pipeline graph to emit stage-level trace events
- Produce a structured JSON run record on disk per run (canonical machine-readable artifact)
- Produce a concise structured stdout summary per run (operator-facing)
- Surface analyst-level result visibility: which analysts ran, skipped, succeeded, failed, and why
- Surface arbiter decision visibility: verdict, confidence, skip/rejection reasons
- Surface artifact provenance: what was written to disk and where
- Extend or connect existing metering infrastructure (`usage.jsonl`, `summarize_usage()`, `logging_node`) rather than building parallel tracking
- Add deterministic tests proving run records are produced and shaped correctly

### Target components

| Area | Target |
|------|--------|
| Graph pipeline | `ai_analyst/graph/pipeline.py` — stage trace emission |
| Analyst node | `ai_analyst/graph/parallel_analyst_node.py` — per-analyst result/skip/fail records |
| Arbiter node | `ai_analyst/graph/arbiter_node.py` — verdict/confidence/reason records |
| Logging node | `ai_analyst/graph/logging_node.py` — run record assembly and stdout summary |
| Usage metering | `ai_analyst/usage_meter.py` — existing JSONL metering path |
| Run directory | `app/data/journeys/` or run-specific directory — run record persistence |
| API response | `ai_analyst/api/main.py` — surface run_record or summary in response if appropriate |

### Out of scope
- No cross-lane observability (MDO, MRO, UI) — analyst pipeline only this phase
- No dashboards, UI surfaces, or browser-based run viewers
- No distributed tracing infrastructure (OpenTelemetry, Jaeger, etc.)
- No alerting integrations or notification transport
- No error taxonomy or classification ontology beyond what the pipeline naturally produces
- No database / Redis / persistence layer changes
- No new top-level module
- No changes to MDO runtime, scheduler, or market-hours logic
- No changes to API auth, timeout, or security hardening behavior
- No broad logging framework migration (no replacing Python logging with a third-party library)

---

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|------|------------|
| Smoke test result | Pipeline runs end-to-end successfully (confirmed 11 March 2026 smoke test) |
| Existing metering | `acompletion_metered()` → `usage.jsonl` → `summarize_usage()` path exists and works |
| Logging node | `logging_node` already calls `summarize_usage(get_run_dir(run_id))` as part of graph lifecycle |
| Run directory | Run artifacts are written to a run-specific directory under `app/data/journeys/` or equivalent |
| Graph state | LangGraph state object is passed through pipeline stages and can carry trace/event data |
| Analyst roster | `ANALYST_CONFIGS` defines the full analyst roster; `smoke_mode` slices to `[:1]` |
| Smoke/triage modes | `smoke_mode` = one analyst + bypass quorum; `triage_mode` = charts optional |
| Usage summary in response | `usage_summary` is already assembled and returned in API response |
| debug_analyst_counts | Already present in response — suggests a debug output path exists |

### Current likely state

The pipeline is functional end-to-end. Per-call LLM metering exists and works. What is missing is the layer between individual LLM call metering and the final API response: stage-level tracing, per-analyst result records, skip/failure reasons, and a consolidated run record that answers "what happened in this run?" without inspecting code or raw JSONL.

### Hypothesis table

| Question | Starting hypothesis |
|----------|---------------------|
| Does `logging_node` already assemble anything beyond usage summary? | Likely minimal — TBC from diagnostic |
| Is there already a run record JSON artifact on disk per run? | Likely no — `usage.jsonl` exists but not a consolidated run record |
| Does graph state carry per-analyst result metadata? | Likely partial — analyst outputs exist but skip/fail reasons may not be tracked |
| Can stage timing be derived from existing data? | Possibly from `usage.jsonl` timestamps per call, but not per graph stage |
| Is `debug_analyst_counts` computed from actual stage results or from config? | TBC from diagnostic |

### Core question

**Can meaningful run visibility be achieved by extending existing metering/logging infrastructure, without introducing new frameworks or persistence layers?**

---

## 4. Key File Paths

| Role | Path |
|------|------|
| Graph pipeline | `ai_analyst/graph/pipeline.py` |
| Parallel analyst node | `ai_analyst/graph/parallel_analyst_node.py` |
| Arbiter node | `ai_analyst/graph/arbiter_node.py` |
| Logging node | `ai_analyst/graph/logging_node.py` |
| Usage metering | `ai_analyst/usage_meter.py` |
| API main | `ai_analyst/api/main.py` |
| Graph state model | `ai_analyst/models/` (TBC — wherever AnalysisState is defined) |
| Run artifact directory | `app/data/journeys/` or run-dir equivalent |
| Existing tests | `ai_analyst/tests/` |
| Progress plan | `docs/AI_TradeAnalyst_Progress.md` |
| This phase spec | `docs/specs/Observability_P1_Run_Visibility_Spec.md` |

**Read-only references:**
- CI Seam Hardening spec (closed)
- Security/API Hardening spec (closed)
- Smoke test record (11 March 2026)

---

## 5. Current State Audit Hypothesis

### What is already true
- Pipeline runs end-to-end (smoke test proven)
- Per-LLM-call metering exists (`acompletion_metered()` → `usage.jsonl`)
- `summarize_usage()` aggregates call counts, stages, models, providers, tokens, cost
- `logging_node` participates in the graph lifecycle and calls `summarize_usage()`
- `usage_summary` and `debug_analyst_counts` are surfaced in the API response
- `run_id` exists as a correlation key

### What likely remains incomplete
- No consolidated structured run record (JSON) persisted per run
- No stage trace (intake → validation → analyst execution → arbiter → completion)
- No per-analyst result records with skip/fail reasons
- No arbiter decision record with reasoning visibility
- No artifact provenance record (what was written where)
- No concise structured stdout summary for operator use
- No timing per stage or per analyst (beyond what can be inferred from JSONL timestamps)

### Core phase question

**What is the smallest instrumentation patch that produces a useful run record and operator summary, by extending existing metering/logging paths rather than introducing new infrastructure?**

---

## 6. Run Visibility Design

### 6.1 Run record structure (JSON on disk)

Each pipeline run produces a single `run_record.json` in the run directory. This is the canonical machine-readable artifact for "what happened in this run."

**Illustrative shape (hypothesis — diagnostic may refine):**

```json
{
  "run_id": "2026-03-11-001",
  "timestamp_start": "2026-03-11T10:30:00Z",
  "timestamp_end": "2026-03-11T10:30:14Z",
  "duration_seconds": 14.2,
  "request": {
    "instrument": "XAUUSD",
    "session": "London",
    "timeframes": ["H4"],
    "smoke_mode": true,
    "triage_mode": true,
    "source_ticket_id": "P123"
  },
  "stages": [
    { "stage": "validate_input", "status": "ok", "duration_ms": 12 },
    { "stage": "macro_context", "status": "ok", "duration_ms": 230 },
    { "stage": "chart_setup", "status": "skipped", "reason": "triage_mode, no charts" },
    { "stage": "analyst_execution", "status": "ok", "duration_ms": 5200 },
    { "stage": "arbiter", "status": "ok", "duration_ms": 3100 },
    { "stage": "logging", "status": "ok", "duration_ms": 45 }
  ],
  "analysts": [
    {
      "persona": "default_analyst",
      "status": "success",
      "model": "claude-sonnet-4-6",
      "provider": "openai",
      "duration_ms": 5100
    }
  ],
  "analysts_skipped": [
    { "persona": "macro_analyst", "reason": "smoke_mode — roster sliced to 1" },
    { "persona": "structure_analyst", "reason": "smoke_mode — roster sliced to 1" }
  ],
  "arbiter": {
    "ran": true,
    "verdict": "NO_TRADE",
    "confidence": 0.0,
    "model": "claude-opus-4-6",
    "provider": "openai",
    "duration_ms": 3050
  },
  "artifacts": {
    "run_record": "app/data/journeys/{run_id}/run_record.json",
    "usage_jsonl": "app/data/journeys/{run_id}/usage.jsonl"
  },
  "usage_summary": {
    "total_calls": 2,
    "successful_calls": 2,
    "failed_calls": 0,
    "calls_by_stage": { "phase1_analyst": 1, "arbiter": 1 },
    "calls_by_model": { "claude-sonnet-4-6": 1, "claude-opus-4-6": 1 }
  },
  "warnings": [],
  "errors": []
}
```

**Design notes:**
- `usage_summary` is included by reference from existing `summarize_usage()` output — not duplicated
- `stages` is the new contribution: ordered trace of pipeline stages with status and timing
- `analysts` and `analysts_skipped` give per-persona visibility with skip reasons
- `warnings` and `errors` collect any non-fatal or fatal issues surfaced during the run
- This shape is a starting hypothesis — the diagnostic should confirm which fields are cheap vs expensive to populate

### 6.2 Stdout operator summary

A concise structured summary emitted to stdout at run completion. Not a log framework — just structured print output for developer visibility.

**Illustrative format:**

```
═══ Run Complete ═══════════════════════════════════════
  run_id:      2026-03-11-001
  instrument:  XAUUSD | session: London | timeframes: H4
  mode:        smoke=true triage=true
  duration:    14.2s
─── Pipeline ───────────────────────────────────────────
  validate_input:    ok
  macro_context:     ok        230ms
  chart_setup:       skipped   (triage_mode, no charts)
  analyst_execution: ok        5.2s   [1 ran, 2 skipped]
  arbiter:           ok        3.1s
  logging:           ok
─── Verdict ────────────────────────────────────────────
  decision:    NO_TRADE
  confidence:  0.0
─── Models ─────────────────────────────────────────────
  claude-sonnet-4-6 (openai) × 1
  claude-opus-4-6 (openai)   × 1
─── Artifacts ──────────────────────────────────────────
  run_record:  app/data/journeys/{run_id}/run_record.json
  usage:       app/data/journeys/{run_id}/usage.jsonl
════════════════════════════════════════════════════════
```

**Design notes:**
- This is assembled from the same data as the run record — no separate tracking path
- Format is human-scannable and paste-friendly (for sharing with AI collaborators)
- Timing is optional per stage — include where cheap, omit where expensive to instrument
- This replaces ad hoc print/log statements, not the Python logging module

### 6.3 Integration with existing infrastructure

The implementation principle is **extend, don't replace:**

| Existing | Extension |
|----------|-----------|
| `acompletion_metered()` → `usage.jsonl` | No change — continue as-is |
| `summarize_usage()` | No change — output consumed by run record assembly |
| `logging_node` | **Primary extension point** — assemble run record here, emit stdout summary here |
| Graph state | **Carry stage trace data** — append stage results as pipeline progresses |
| API response | Include `run_record_path` in response so developer knows where to look |

The diagnostic must confirm whether graph state can carry accumulating trace data (list of stage results) through the pipeline without breaking existing behavior.

### 6.4 What is schema-only this phase

- `warnings` and `errors` arrays in the run record exist for future use. This phase populates them only with naturally-occurring exceptions or skip reasons. No error classification ontology is introduced.
- Timing fields (`duration_ms`) are best-effort this phase. If per-stage timing is expensive to instrument for certain stages, mark those as `null` rather than blocking the phase.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | Run record produced | A `run_record.json` is written to the run directory on every pipeline completion | ✅ Done |
| AC-2 | Run record shape | Run record contains: run_id, timestamps, request summary, stages trace, analysts results, arbiter result, artifacts paths, usage_summary | ✅ Done |
| AC-3 | Stage trace | Stage trace records at minimum: validate_input, analyst_execution, arbiter, logging — each with status (ok/skipped/failed) | ✅ Done |
| AC-4 | Analyst visibility | Each analyst that ran has a result record (persona, status, model, provider). Each analyst skipped has a skip record with reason | ✅ Done |
| AC-5 | Arbiter visibility | Arbiter record includes: ran (bool), verdict, confidence, model, provider | ✅ Done |
| AC-6 | Stdout summary | A concise structured summary is emitted to stdout on run completion | ✅ Done |
| AC-7 | Existing metering preserved | `usage.jsonl` and `summarize_usage()` behavior unchanged | ✅ Done |
| AC-8 | Run record test | At least one deterministic test proves run record is produced and contains required fields | ✅ Done — 10 tests in TestRunRecordShape |
| AC-9 | Stdout test | At least one deterministic test proves stdout summary is emitted (captured output check) | ✅ Done — 6 tests in TestStdoutSummary |
| AC-10 | Smoke mode visibility | Run record correctly reflects smoke_mode behavior (roster sliced, skipped analysts listed with reason) | ✅ Done — 3 tests in TestSmokeVisibility |
| AC-11 | Failure visibility | If an analyst call fails, the run record captures the failure (stage status=failed, error info) rather than silently swallowing it | ✅ Done — 2 tests in TestFailureVisibility |
| AC-12 | No silent swallowing | Run record is produced even on partial pipeline failure (as far as the pipeline got) | ✅ Done — 3 tests in TestPartialPipeline |
| AC-13 | Regression safety | All existing test suites pass after changes | ✅ Done — 668 passed (643 baseline + 25 new), same 20 pre-existing failures |
| AC-14 | Scope discipline | No new top-level module, no database, no external tracing framework, no MDO/MRO changes | ✅ Done |
| AC-15 | Docs closure | Progress plan, spec, and debt register updated on closure per Workflow E | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

Do not implement until this list is reviewed.

### Step 1 — Audit existing logging_node and run directory structure
**Run:** Inspect `ai_analyst/graph/logging_node.py` and identify: what it currently does, what data it receives from graph state, what it writes to disk, what it emits to stdout.
**Expected result:** Clear picture of current logging_node behavior and data available to it.
**Report:** Current logging_node capabilities and data sources.

### Step 2 — Audit graph state shape
**Run:** Inspect the graph state model (likely in `ai_analyst/models/`) and determine: what fields are carried through the pipeline, whether per-stage result data is already accumulated, whether the state can carry a growing list of stage trace entries without breaking existing behavior.
**Expected result:** Confirm whether graph state can be the carrier for stage trace data.
**Report:** State model fields, extensibility assessment, risk of breaking existing consumers.

### Step 3 — Audit parallel_analyst_node output shape
**Run:** Inspect `ai_analyst/graph/parallel_analyst_node.py` and determine: what per-analyst result data is currently produced, whether skip/fail reasons are captured, how smoke_mode slicing is recorded.
**Expected result:** Understand what analyst-level metadata is already available vs needs adding.
**Report:** Current analyst output shape, gap to AC-4 and AC-10.

### Step 4 — Audit arbiter_node output shape
**Run:** Inspect `ai_analyst/graph/arbiter_node.py` and determine: what verdict metadata is currently produced, whether model/provider/timing are tracked.
**Expected result:** Understand what arbiter metadata is already available vs needs adding.
**Report:** Current arbiter output shape, gap to AC-5.

### Step 5 — Run baseline test suite
**Run:** `pytest -q ai_analyst/tests/` and `pytest -q tests/*.py`
**Expected result:** Baseline green before any changes.
**Report:** Test counts and any pre-existing failures.

### Step 6 — Propose smallest patch set
**Run:** None; summarise from Steps 1–5.
**Expected result:** Smallest safe instrumentation patch.
**Report:** Files, one-line description, estimated line delta. Flag any graph state shape changes that could affect existing consumers.

---

## 9. Implementation Constraints

### 9.1 General rule

This is a **visibility phase**, not an observability platform phase. The goal is the simplest instrumentation that makes runs legible, by extending existing metering/logging infrastructure.

### 9.1b Implementation Sequence

1. Extend graph state to carry stage trace accumulator (if diagnostic confirms this is safe).
2. Instrument pipeline stages to append trace entries to state.
3. Instrument `parallel_analyst_node` to record per-analyst results with skip/fail reasons.
4. Instrument `arbiter_node` to record verdict metadata.
5. **Gate 1:** Verify existing tests still pass after state/node changes.
6. Extend `logging_node` to assemble `run_record.json` from accumulated trace + existing usage summary.
7. Extend `logging_node` to emit stdout operator summary.
8. **Gate 2:** Verify existing tests still pass after logging_node changes.
9. Add deterministic tests for run record shape (AC-8) and stdout emission (AC-9).
10. Add test for smoke_mode visibility (AC-10) and failure capture (AC-11, AC-12).
11. **Gate 3:** Full suite pass — `ai_analyst/tests/` + `tests/*.py`.
12. Close spec and update docs per Workflow E.

After each risky change, verify relevant test targets still pass. **Never skip a gate.**

### 9.2 Code change surface

Expected change surface:
- `ai_analyst/graph/pipeline.py` — stage trace emission at pipeline level (if needed)
- `ai_analyst/graph/parallel_analyst_node.py` — per-analyst result/skip records
- `ai_analyst/graph/arbiter_node.py` — verdict metadata record
- `ai_analyst/graph/logging_node.py` — run record assembly + stdout summary (primary change)
- `ai_analyst/models/` — graph state extension (if trace accumulator is added to state)
- `ai_analyst/tests/` — new test files for run record and stdout
- `docs/specs/Observability_P1_Run_Visibility_Spec.md` — phase closure
- `docs/AI_TradeAnalyst_Progress.md` — phase closure

No changes expected to:
- `ai_analyst/usage_meter.py` (existing metering preserved as-is)
- `ai_analyst/api/main.py` (unless run_record_path exposure is trivial)
- `market_data_officer/` — no MDO changes
- `macro_risk_officer/` — no MRO changes
- `app/` — no UI changes
- CI workflows — no CI changes this phase
- Security/auth behavior

**Scope flag:** If graph state extension requires changes to consumers outside `ai_analyst/graph/`, flag before proceeding.

### 9.3 Hard constraints
- No external tracing/observability framework (no OpenTelemetry, no Jaeger, no Datadog)
- No database / Redis / persistence layer changes
- No new top-level module
- No MDO or MRO code changes
- No UI changes
- No CI workflow changes
- No broad Python logging framework migration
- Existing `usage.jsonl` and `summarize_usage()` behavior must be preserved unchanged
- Deterministic tests only — no live provider dependency
- If graph state changes affect consumers outside `ai_analyst/graph/`, flag before proceeding
- If this work resolves or partially addresses any Technical Debt Register items (§8 of progress plan), update their status

---

## 10. Success Definition

Observability Phase 1 is done when every analyst pipeline run produces a structured `run_record.json` on disk containing stage trace, per-analyst results (including skips with reasons), arbiter verdict metadata, and artifact paths; a concise operator summary is emitted to stdout; existing metering behavior is preserved; deterministic tests prove run record shape, stdout emission, smoke-mode visibility, and failure capture; all existing test suites pass with zero regressions — no database, no new top-level module, no external tracing framework.

---

## 11. Why This Phase Matters

### Without this phase
- Developers must read code to understand what the pipeline did
- Analyst skips and failures are invisible unless you know where to look
- Arbiter decisions have no audit trail beyond the final verdict value
- Debugging requires reconstructing the run from scattered clues
- The system works but cannot explain itself

### With this phase
- Every run is self-documenting
- Developers can see exactly what happened by reading one file
- Failures are captured at the point they occur, not discovered downstream
- The run record becomes the foundation for future review, journaling, and quality tracking
- AI collaborators can inspect run records to ground their analysis in evidence

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Security/API Hardening | Auth, timeouts, error contracts, body limits, TD-2 | ✅ Done — 677 tests |
| CI Seam Hardening | CI-gate missing Python seams + orchestration path | ✅ Done — 1743 tests |
| **Observability Phase 1** | **Analyst pipeline run visibility — run record + stdout summary** | **✅ Done — 668 tests (643 baseline + 25 new)** |

---

## 13. Diagnostic Findings & Implementation Record

### State model extension

Added 3 fields to `GraphState` (TypedDict in `ai_analyst/graph/state.py`):
- `_stage_trace: Optional[list]` — ordered list of stage trace dicts (reserved for future per-stage append; currently assembled at logging_node from `_node_timings`)
- `_analyst_results: Optional[list]` — per-analyst result/skip/fail records (populated by `parallel_analyst_node`)
- `_arbiter_meta: Optional[dict]` — arbiter model/provider/duration_ms (populated by `arbiter_node`)

All fields use `_` prefix convention for internal/transient state. Initialized to `[]`/`None` in both `initial_state` dicts in `main.py`.

### `_analyst_results` shape

Each entry in the list is one of:
```json
{"persona": "default_analyst", "status": "success", "model": "claude-sonnet-4-6", "provider": "openai"}
{"persona": "macro_analyst", "status": "skipped", "reason": "smoke_mode — roster sliced to 1"}
{"persona": "structure_analyst", "status": "failed", "model": "m1", "provider": "p1", "reason": "RuntimeError: provider returned 500"}
```

### `run_record.json` shape (actual)

```json
{
  "run_id": "...",
  "timestamp": "2026-03-11T...",
  "duration_ms": 5000,
  "request": {
    "instrument": "XAUUSD",
    "session": "London",
    "timeframes": ["H4"],
    "smoke_mode": false
  },
  "stages": [
    {"stage": "validate_input", "status": "ok", "duration_ms": 5},
    {"stage": "macro_context", "status": "ok", "duration_ms": 120},
    {"stage": "chart_setup", "status": "ok", "duration_ms": 30},
    {"stage": "analyst_execution", "status": "ok", "duration_ms": 3000},
    {"stage": "arbiter", "status": "ok", "duration_ms": 2000},
    {"stage": "logging", "status": "ok", "duration_ms": 10}
  ],
  "analysts": [
    {"persona": "default_analyst", "status": "success", "model": "...", "provider": "..."}
  ],
  "analysts_skipped": [],
  "analysts_failed": [],
  "arbiter": {
    "ran": true,
    "verdict": "NO_TRADE",
    "confidence": 0.0,
    "model": "claude-opus-4-6",
    "provider": "openai",
    "duration_ms": 2500
  },
  "artifacts": {
    "run_record": "ai_analyst/output/runs/{run_id}/run_record.json",
    "usage_jsonl": "ai_analyst/output/runs/{run_id}/usage.jsonl"
  },
  "usage_summary": { "...consumed from summarize_usage()..." },
  "warnings": [],
  "errors": []
}
```

### Stdout summary format (actual)

```
═══ Run Complete ═══════════════════════════════════════
  run_id:      {run_id}
  instrument:  XAUUSD | session: London | timeframes: H4
  mode:        smoke=false
  duration:    5.0s
─── Pipeline ───────────────────────────────────────────
  validate_input         ok        5ms
  macro_context          ok        120ms
  chart_setup            ok        30ms
  analyst_execution      ok        3000ms  [1 ran, 0 skipped, 0 failed]
  arbiter                ok        2000ms
  logging                ok        10ms
─── Verdict ────────────────────────────────────────────
  decision:    NO_TRADE
  confidence:  0.0
─── Models ─────────────────────────────────────────────
  claude-sonnet-4-6 × 1
  claude-opus-4-6 × 1
─── Artifacts ──────────────────────────────────────────
  run_record     ai_analyst/output/runs/{run_id}/run_record.json
  usage          ai_analyst/output/runs/{run_id}/usage.jsonl
════════════════════════════════════════════════════════
```

### `logging_node` changes

- Added `_build_run_record()` — assembles canonical run record from accumulated state + usage summary
- Added `_emit_stdout_summary()` — builds and prints operator summary
- Extended `logging_node()` — calls both after existing metrics recording (fail-silent, never blocks pipeline)
- Existing behavior (log_run, MRO OutcomeTracker, RunMetrics) is untouched

### Test additions

New file: `ai_analyst/tests/test_run_record.py` — 25 deterministic tests across 7 test classes:
- `TestRunRecordShape` (10 tests) — AC-2, AC-3, AC-5, AC-7, AC-8
- `TestStdoutSummary` (6 tests) — AC-6, AC-9
- `TestSmokeVisibility` (3 tests) — AC-10
- `TestFailureVisibility` (2 tests) — AC-11
- `TestPartialPipeline` (3 tests) — AC-12
- `TestAnalystResultShape` (2 tests) — AC-4 (ran + skipped shapes)

### Test count delta

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| `ai_analyst/tests/` | 504 passed, 12 failed, 8 errors | 529 passed, 12 failed, 8 errors | +25 |
| `tests/*.py` | 139 passed | 139 passed | +0 |
| **Total passed** | **643** | **668** | **+25** |

Pre-existing failures (not introduced by this phase): 12 FAILED in `test_security_hardening.py` (environment-dependent FastAPI integration) + 8 ERROR in `test_schema_round_trip.py` (missing fixture file).

---

## 14. Appendix — Recommended Agent Prompt

Read `docs/specs/Observability_P1_Run_Visibility_Spec.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings before changing any code:

1. Audit `logging_node` — what it does now, what data it has access to, what it writes/emits
2. Audit graph state model — can it carry a stage trace accumulator safely?
3. Audit `parallel_analyst_node` — what per-analyst result data exists, what's missing for skip/fail visibility
4. Audit `arbiter_node` — what verdict metadata exists, what's missing
5. Run baseline: `pytest -q ai_analyst/tests/` and `pytest -q tests/*.py`
6. Report AC gap table (AC-1 through AC-15)
7. Propose smallest patch set: files, one-line description, estimated line delta
8. Flag any graph state changes that could affect consumers outside `ai_analyst/graph/`

Hard constraints:
- No external tracing/observability framework
- No database / Redis / persistence
- No new top-level module
- No MDO, MRO, or UI changes
- Existing `usage.jsonl` and `summarize_usage()` preserved unchanged
- Deterministic tests only — no live provider dependency
- Smallest safe option only

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/Observability_P1_Run_Visibility_Spec.md` — mark ✅ Complete, flip all AC cells,
   populate §13 with: logging_node changes, state model extension, run record shape, stdout format, test additions, test count delta
2. `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row,
   update next actions and debt register if applicable
3. Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`,
   `AI_ORIENTATION.md` — update only if this phase changed architecture,
   structure, or debt state
4. Cross-document sanity check: no contradictions, no stale phase refs
5. Return Phase Completion Report (see Workflow E.8)

Commit all doc changes on the same branch as the implementation.
