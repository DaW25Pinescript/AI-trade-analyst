# AI Trade Analyst — Observability Phase 2 Spec

## Header

- **Status:** ⏳ Spec drafted — implementation pending
- **Date:** 12 March 2026
- **Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
- **Spec file:** `docs/specs/observability_phase_2.md`
- **Owner lane:** Runtime hardening / seam confidence
- **Depends on:** Observability Phase 1 (closed, 668 tests), Security/API Hardening (closed, 677 tests), CI Seam Hardening (closed, 1743 tests)

---

## 1. Purpose

Observability Phase 2 exists to make the system's **real runtime boundaries** easier to understand and operate.

Observability Phase 1 gave the repo basic per-run visibility through `run_record.json` and concise stdout summaries. The next gap is not "more logs" in general — it is better **cross-lane failure visibility** and clearer status surfaces across the analyst lane, feeder lane, and adjacent runtime seams.

This phase should make it materially easier for operators and contributors to answer:

- what failed
- where it failed
- whether the failure was transient or structural
- whether the system recovered
- which runtime lane was affected

This phase is a hardening phase, not a product-surface phase.

---

## 2. Why Now

The repo is already past feasibility and first-pass runtime behavior. The current progress posture is post-hardening and post-UI-design: CI seam hardening is complete, Observability Phase 1 is complete, and the remaining backend risk is concentrated in seam visibility, cleanup, developer/operator UX, and longer-term runtime-lane convergence.

The current live runtime is also not a single unified lane: the active `ai_analyst` API/graph path is GroundTruth/LangGraph-based, concrete Market Data Officer coupling still exists in legacy paths and some root/test integrations, and the UI touches multiple API families including `/analyse`, `/triage`, `/watchlist/triage`, `/journey/*`, and `/feeder/*`. That means observability problems can hide at the seams even when individual modules look healthy in isolation.

The backend already exposes observability-adjacent surfaces such as `/metrics`, `/dashboard`, `/feeder/health`, `/analyse/stream`, and dev diagnostics artifacts, but the repo still lacks a tighter, explicit operating model for success/failure/recovery across these seams.

---

## 3. Objective

Move from:

> "we can inspect individual modules and some run artifacts"

To:

> "we can reliably see runtime health and failure boundaries across the real orchestration seams of the system"

This phase should improve **interpretability of runtime behavior**, not introduce a new observability stack.

---

## 4. Scope

### 4.1 In scope

1. **Structured seam event visibility** — Standardize high-signal structured event logging where still inconsistent across analysis requests, feeder ingest/health, MDO feed refresh, scheduler health, and seam-adjacent runtime paths. Prefer a small number of durable event categories over verbose raw logging.

2. **Status-surface tightening** — Make existing health/status surfaces more useful for diagnosing runtime posture. Ensure contributors can distinguish healthy, degraded, stale, unavailable, and failed states where those distinctions already exist conceptually.

3. **Failure and recovery clarity** — Clarify what counts as success, failure, partial failure, and recovery across: analysis request path, triage loopback path, feeder ingest/health path, MDO feed refresh path, scheduler/runtime posture where relevant.

4. **Cross-lane seam interpretation** — Make it easier to identify which lane failed: analyst/graph lane, MDO feed lane, feeder/macro-context lane, artifact/write/read lane, diagnostics/status lane.

5. **Existing observability endpoint audit** — Audit `/metrics`, `/dashboard`, `/e2e` content and accuracy. Document what they expose, note gaps, and tighten where trivially fixable. This is an alignment pass, not a redesign.

6. **Deterministic test coverage** — Add tests that prove observability outputs and status classification behavior are stable and intentional.

### 4.2 Target lanes

| Lane | Current observability (hypothesis — diagnostic will confirm) | Phase 2 target |
|------|-------------------------------------------------------------|----------------|
| Analyst pipeline | run_record.json, stdout summary (Obs P1), dev diagnostics tracing | Verify sufficient; extend if gaps found |
| MDO feed refresh | APScheduler logs, likely inconsistent format | Structured events for refresh start/success/fail/staleness |
| Feeder ingest | Unknown — audit required | Structured events for ingest lifecycle including recovery |
| Scheduler/APScheduler | Job execution logs, likely unstructured | Structured job lifecycle events (missed, overlap, duration) |
| Graph orchestration | Unknown — timeout/error handling from Security Hardening | Structured events for graph start/node transitions/completion/timeout |
| Triage loopback | Calls `/analyse` in loop — partial failure semantics | Explicit partial-failure classification and downstream-read staleness |
| Legacy surfaces | Unknown — likely print/basic logging | Document current state; do not refactor unless trivially improved |
| `/metrics` endpoint | JSON snapshot — content and accuracy unknown | Audit, document, note gaps |
| `/dashboard` endpoint | HTML — content and accuracy unknown | Audit, document, note gaps |
| `/e2e` endpoint | JSON checks — content and accuracy unknown | Audit, document, note gaps |

### 4.3 Out of scope

- No new cloud observability tooling (Prometheus, Grafana, OpenTelemetry, ELK, etc.)
- No third-party log aggregation
- No full distributed tracing platform
- No new alerting system or notification pipeline
- No new top-level module — work confined to existing packages
- No SQLite or database layer introduced
- No UI implementation work — existing endpoints are audited and documented, not redesigned
- No changes to API response shapes visible to `/app/` consumers (`UI_CONTRACT.md` unchanged)
- No changes to `MarketPacketV2` contract — officer layer unchanged
- No scheduling policy or cadence changes
- No runtime-lane convergence or major architecture rewrites
- No packaging/import-path cleanup (TD-3 — separate phase)
- No Chart Evidence or other UI extensions
- No replacement of existing logging with a grand unified framework unless diagnostic shows one is already nearly in place

---

## 5. Design Principles

### 5.1 Seam-first, not log-volume-first

The goal is not to emit more text. The goal is to make seam behavior legible.

### 5.2 Existing surfaces before new surfaces

Prefer improving existing runtime/status/diagnostics surfaces before adding brand-new endpoints.

### 5.3 Structured, deterministic, testable

Anything classified as status or seam outcome should be emitted in a machine-testable shape where practical.

### 5.4 Failure taxonomy over vague "error" buckets

Observability outputs should help distinguish:

- request validation failure
- runtime execution failure (graph, LLM, timeout)
- dependency/package unavailability
- stale-but-readable state
- artifact read/write failure
- recovery event after prior failure

### 5.5 Dual-consumer requirement

All structured events must be both locally readable (an operator tailing logs can understand what happened) and machine-parseable (a future monitoring system can consume the events as structured data). The simplest way to satisfy both is a JSON log line with a human-readable message field alongside structured fields — but the diagnostic should confirm whether this pattern already exists.

### 5.6 Narrow phase discipline

This phase should improve operational confidence without expanding into UI implementation, platform migration, or large architecture cleanup.

---

## 6. Repo-Aligned Assumptions

| Area | Assumption |
|------|-----------|
| Analyst pipeline | Obs P1 shipped run_record.json and stdout summary; structured logging likely already exists for this lane |
| MDO feed refresh | APScheduler integration is live (Operationalise P1); scheduler job logging exists but may be unstructured |
| Feeder ingest | `/feeder/ingest` is a FastAPI route; logging may be limited to FastAPI defaults |
| Graph orchestration | LangGraph-based; timeout/error handling added in Security/API Hardening; structured logging status unknown |
| Triage loopback | `/triage` loops back into `/analyse`; partial failure is possible; downstream `/watchlist/triage` has graceful empty/unavailable |
| `/metrics` | Endpoint exists and returns JSON; content shape and accuracy unverified |
| `/dashboard` | Endpoint exists and returns HTML; content and accuracy unverified |
| `/e2e` | Endpoint exists and returns JSON check results; scope and accuracy unverified |
| Logging infrastructure | Python stdlib `logging` is likely the baseline; unclear whether any lanes use structured JSON formatters |
| Dev diagnostics | Dev-gated request lifecycle tracing exists for `/analyse` and `/analyse/stream` with structured checkpoints — may provide a pattern to extend |

### Current likely state

The analyst pipeline has the strongest observability after Obs P1. The MDO lane has APScheduler job execution but likely lacks structured event emission for feed-level outcomes. The feeder and graph lanes are probably the weakest — they were built for correctness, not visibility. The triage loopback is a classic partial-failure seam that needs explicit attention. The existing observability endpoints (`/metrics`, `/dashboard`, `/e2e`) were never wired into any consumer and their accuracy is unknown.

### Core question

**Can structured seam visibility be added across all lanes without changing runtime behavior or API contracts? What is the smallest surface that gives an operator cross-lane failure and recovery visibility?**

---

## 7. Key File Paths

| Role | Path | Notes |
|------|------|-------|
| Analyst API routes | `ai_analyst/api/main.py` | `/analyse`, `/analyse/stream`, `/metrics`, `/dashboard`, `/e2e`, `/plugins` |
| Journey routes | `ai_analyst/api/routers/journey.py` | `/triage`, `/watchlist/triage`, `/journey/*`, `/journal/*`, `/review/*`, `/feeder/*` |
| Run record (Obs P1) | `ai_analyst/core/run_record.py` (hypothesis) | Existing structured output — verify location |
| Progress store | `ai_analyst/core/progress_store.py` | SSE progress tracking — may already emit structured events |
| Run state manager | `ai_analyst/core/run_state_manager.py` | Internal run state transitions — logging status unknown |
| MDO scheduler | `market_data_officer/` scheduler integration | APScheduler job wiring — logging format unknown |
| MDO service | `market_data_officer/officer/service.py` | `build_market_packet()` — feed refresh lifecycle |
| Feeder ingest | Route handler in journey router | Ingest + cache lifecycle |
| Graph execution | `ai_analyst/` graph path | LangGraph orchestration — timeout/error logging |
| Dev diagnostics | `/analyse` dev tracing (11 Mar 2026) | Existing pattern for structured lifecycle events |
| Metrics endpoint | `/metrics` handler in `main.py` | JSON snapshot — audit content |
| Dashboard endpoint | `/dashboard` handler in `main.py` | HTML — audit content |
| E2E endpoint | `/e2e` handler in `main.py` | JSON checks — audit content |

Read-only references:
- `docs/AI_TradeAnalyst_Progress.md` — canonical progress hub
- `docs/ui/UI_CONTRACT.md` — API surface contract (must not change)
- `docs/ui/UI_BACKEND_AUDIT.md` — endpoint inventory (reference for baseline)

---

## 8. Proposed Deliverables

### 8.1 Structured seam event model

Introduce or tighten a small structured event vocabulary for runtime-significant events, such as:

- request accepted / validation failed
- graph execution started / completed / failed / timed out
- triage batch started / completed / partially failed
- feeder ingest accepted / completed / failed
- feeder health stale / unavailable / recovered
- MDO feed refresh started / per-instrument success/fail / job completed
- scheduler job missed / overlap / duration anomaly
- artifact persisted / artifact read failed
- runtime degraded / runtime recovered

Exact names may vary, but the phase must produce a **documented and testable event shape**, not ad hoc string-only logging. The implementation approach (stdlib JSON logging, extending dev diagnostics pattern, or thin custom emitter) is deferred to the diagnostic — the diagnostic must determine what already exists before prescribing a solution.

### 8.2 Analysis-path observability tightening

For `/analyse` and `/analyse/stream`, make sure the runtime path exposes enough signal to answer:

- did the request parse successfully
- did graph execution begin
- did it complete, fail, or time out
- was a final artifact/verdict produced
- was usage/artifact persistence successful
- was the failure transport-level, graph-level, or artifact-level

This should build on the existing dev diagnostics rather than replacing them.

### 8.3 Triage seam visibility

`/triage` currently loops back into `/analyse` and writes triage artifacts; this is a classic seam where partial failure can become hard to interpret. The phase should make it clearer when triage is:

- fully successful
- partially successful (some symbols failed, others succeeded)
- structurally failed (all symbols failed)
- completed but producing stale/unavailable downstream reads via `/watchlist/triage`

### 8.4 MDO feed refresh visibility

Structured events for the MDO feed refresh lifecycle:

- scheduler job trigger
- per-instrument/per-timeframe refresh outcome (success, failure with cause, staleness classification)
- job completion summary (instruments refreshed, instruments failed, duration)

Failure events must include instrument, timeframe, provider, and error type.

### 8.5 Feeder/runtime posture tightening

Improve the interpretability of feeder/runtime status by tightening the meaning and visibility of:

- feeder ingest success/failure
- freshness / staleness
- last known good context
- unavailable vs stale distinction
- recovery after prior stale/failure periods

This should leverage the existing `/feeder/health` and related runtime posture work rather than inventing a separate monitoring lane.

### 8.6 Metrics/dashboard/e2e alignment pass

Review existing `/metrics`, `/dashboard`, and `/e2e` outputs and:

- Document what they currently return (field inventory for JSON, content summary for HTML)
- Note whether values are accurate or stale
- Note whether coverage spans all lanes or only a subset
- Tighten where trivially fixable (e.g. a counter that never increments)
- Identify gaps for future improvement (documented, not fixed in this phase unless trivial)

This is an alignment pass, not a redesign.

### 8.7 Operator interpretation notes

If this phase changes how contributors should interpret status surfaces, add or update concise operator guidance in the relevant runbook/docs location.

### 8.8 Deterministic tests

Add tests that prove:

- seam event emission/classification is stable
- failure events are emitted when a lane operation fails (not just that success events work)
- degraded vs failed vs recovered states are distinguished intentionally
- partial triage failures are surfaced consistently
- feeder health/status semantics match implementation reality
- analysis-path observability does not silently regress
- where machine-testable, status snapshots from `/metrics` or `/e2e` reflect the hardened classification rules

---

## 9. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | Logging audit | Every runtime lane has been audited for current logging state; findings recorded in §14 | ⏳ Pending |
| AC-2 | Endpoint audit | `/metrics`, `/dashboard`, `/e2e` content and accuracy documented; gaps noted | ⏳ Pending |
| AC-3 | Event format | A consistent structured event format is defined and implemented (or an existing format is adopted and extended) | ⏳ Pending |
| AC-4 | Analyst lane | Analyst pipeline emits structured events at key lifecycle boundaries (or Obs P1 coverage confirmed sufficient) | ⏳ Pending |
| AC-5 | MDO lane | MDO feed refresh emits structured events for job + per-instrument outcomes including failures | ⏳ Pending |
| AC-6 | Feeder lane | Feeder ingest emits structured events for ingest lifecycle including recovery | ⏳ Pending |
| AC-7 | Graph lane | Graph orchestration emits structured events for execution lifecycle including timeout/failure | ⏳ Pending |
| AC-8 | Scheduler lane | Scheduler health events emitted for job lifecycle anomalies (missed, overlap, duration) | ⏳ Pending |
| AC-9 | Triage seam | Triage partial-failure behavior is observable and intentionally classified (full success, partial, structural failure, stale downstream) | ⏳ Pending |
| AC-10 | Cross-lane traceability | A simulated cross-lane failure (e.g. MDO feed fail → stale context → degraded analysis) is traceable from structured events alone | ⏳ Pending |
| AC-11 | Recovery visibility | At least one recovery event (e.g. feeder stale → recovered) is emitted and testable | ⏳ Pending |
| AC-12 | Negative test | At least one test proves a failure event is emitted when a lane operation fails — not just that success events work | ⏳ Pending |
| AC-13 | Dual-consumer | Structured events are both locally readable (human-friendly in terminal) and machine-parseable (consistent JSON) | ⏳ Pending |
| AC-14 | No contract breakage | `UI_CONTRACT.md` API surface unchanged; no response shape changes visible to `/app/` consumers | ⏳ Pending |
| AC-15 | Regression safety | Baseline test count maintained or improved; zero regressions | ⏳ Pending |

---

## 10. Pre-Code Diagnostic Protocol

**Do not implement until this list is reviewed.**

### Step 1 — Audit current logging infrastructure

Identify across all lanes:
- What logging library/pattern is in use (stdlib `logging`, print, custom, structured JSON, etc.)
- Whether any JSON formatter or structured emitter already exists
- Whether the dev diagnostics tracing (11 Mar 2026) provides an extensible pattern
- **Report:** logging infrastructure inventory table (lane → library → format → structured Y/N)

### Step 2 — Audit analyst pipeline coverage (Obs P1 baseline)

- Confirm run_record.json and stdout summary are still functional
- Identify any lifecycle boundaries not covered by Obs P1
- Determine overlap with dev diagnostics tracing
- **Report:** gap list or "sufficient — no changes needed"

### Step 3 — Audit MDO feed refresh logging

- Trace a feed refresh from APScheduler job trigger through per-instrument outcome
- Identify what is logged, at what level, and in what format
- **Report:** current coverage vs target coverage gap

### Step 4 — Audit feeder ingest logging

- Trace a `/feeder/ingest` request through validation, macro context build, and cache update
- Identify what is logged and whether recovery after staleness is traceable
- **Report:** current coverage vs target coverage gap

### Step 5 — Audit graph orchestration logging

- Trace a graph execution from start through node transitions to completion/timeout
- Identify whether LangGraph provides built-in tracing hooks that could be used
- **Report:** current coverage vs target coverage gap

### Step 6 — Audit triage loopback logging

- Trace a `/triage` call through the loopback into `/analyse` for multiple symbols
- Identify how partial failure (some symbols succeed, some fail) is logged
- Identify whether downstream `/watchlist/triage` reads reflect staleness from partial failure
- **Report:** current coverage vs target, with specific attention to partial-failure semantics

### Step 7 — Audit scheduler health logging

- Identify whether APScheduler emits job lifecycle events (missed, overlap, duration)
- Identify whether these are structured or unstructured
- **Report:** current coverage vs target coverage gap

### Step 8 — Audit `/metrics`, `/dashboard`, `/e2e` endpoints

- Call each endpoint and document the response (field inventory for JSON, content summary for HTML)
- Note accuracy: do counters increment? Do health checks run? Is data real-time or stale?
- **Report:** per-endpoint content inventory + accuracy assessment + gap notes

### Step 9 — Run baseline test suite

- Run full test suite and confirm green
- **Report:** test count and pass rate

### Step 10 — Propose implementation approach

Based on Steps 1–8, propose:
- Whether to extend existing infrastructure or introduce a thin new layer
- The recommended event format (confirmed from what already exists, not hypothetical)
- The failure taxonomy mapped to actual code paths found in the audit
- The smallest patch set: files, one-line description per file, estimated line delta
- Any AC adjustments based on diagnostic findings
- Which lane has the largest gap and should be instrumented first

**"Do not implement until this list is reviewed."**

---

## 11. Implementation Constraints

### 11.1 General rule

This phase is **additive observability only**. It adds structured event emission and documents existing endpoints. It does not change runtime behavior, API response shapes, scheduling policy, or analysis pipeline logic. If any change to runtime behavior is required to emit an event, flag before proceeding.

### 11.1b Implementation sequence

1. Establish structured event format (or adopt existing) — verify no import/dependency issues
2. Add events to the lane with the largest gap first (diagnostic will confirm — likely MDO or triage)
3. Verify baseline tests still pass: [N]/[N] after first lane instrumentation
4. Add events to remaining lanes in priority order
5. Verify full test suite: [N]/[N] still pass after all lane instrumentation
6. Add failure-event and recovery-event tests (deterministic, mocked failures)
7. Verify full test suite: [N]+/[N] after new tests
8. Document `/metrics`, `/dashboard`, `/e2e` audit findings in §14
9. Update operator notes/runbook if interpretation changed
10. Final regression gate: all tests green, zero regressions

**Rule: never skip a gate.**

### 11.2 Code change surface (hypothesis — diagnostic will confirm)

Expected changes:
- Logging configuration or formatter (likely one file)
- Analyst pipeline event emission (may be minimal if Obs P1 is sufficient)
- MDO service / scheduler integration (feed refresh events)
- Triage orchestration path (partial-failure classification)
- Feeder ingest handler (ingest lifecycle events including recovery)
- Graph orchestration entry point (graph lifecycle events)
- Scheduler health hooks (job lifecycle events)
- Metrics/dashboard/e2e alignment fixes (if trivial accuracy issues found)
- New test file(s) for failure-event and recovery-event assertions
- Runbook/operator notes update

No changes expected to:
- `UI_CONTRACT.md` or any `docs/ui/` artifact
- API response shapes visible to `/app/` consumers
- `MarketPacketV2` contract
- Scheduling policy or cadence
- Analysis pipeline logic
- Authentication or rate limiting

**Scope flag:** If instrumenting a lane requires changes to its core logic (not just adding log/event lines), flag before proceeding.

### 11.3 Out of scope (hard constraints)

- No SQLite or database layer introduced
- No new top-level module — work confined to existing packages
- No new monitoring infrastructure (Prometheus, Grafana, OpenTelemetry, ELK, etc.)
- No alerting system
- No UI changes
- No API response shape changes
- No scheduling or cadence changes
- `MarketPacketV2` contract locked — officer layer unchanged
- Deterministic fixture/mock tests are the required acceptance backbone — no live provider dependency in CI
- If this work resolves or partially addresses any Technical Debt Register items (§8 of progress plan), update their status

---

## 12. Success Definition

Observability Phase 2 is done when: the repo can answer the operational question **"what failed, where, why — and has it recovered?"** without requiring contributors to manually stitch together multiple unrelated code paths for common runtime failures.

Specifically: every runtime lane (analyst, MDO, feeder, scheduler, graph, triage) emits structured events at key lifecycle and failure boundaries; an operator can trace a cross-lane failure from event output alone; existing observability endpoints (`/metrics`, `/dashboard`, `/e2e`) are audited and documented with accuracy notes; at least one negative test proves failure events are emitted correctly; at least one recovery event is testable; the event format serves both local readability and future machine consumption; and no API contracts, scheduling behavior, or runtime logic have changed. No SQLite. No new top-level module. No monitoring infrastructure.

---

## 13. Why This Phase Matters

| Without | With |
|---------|------|
| MDO feed failure is invisible unless you read APScheduler logs and trace per-instrument code paths | MDO feed failure emits a structured event with instrument, error type, and duration — visible in any log consumer |
| Triage partial failure collapses into an opaque generic error | Triage emits per-symbol outcome classification: full success, partial, structural failure, stale downstream |
| Feeder staleness affects analysis quality but the connection is not traceable | Cross-lane event correlation shows feeder stale → degraded macro context → analysis with incomplete input |
| Recovery after a failure period is invisible — operators don't know if the system self-healed | Recovery events (feeder recovered, feed refresh resumed) are explicit and testable |
| `/metrics` and `/dashboard` exist but nobody knows what they contain or whether they're accurate | Endpoint audit documents exactly what is exposed, what is stale, and what gaps exist |
| New contributor debugging a failure must read multiple source files to understand what happened | Structured event stream answers "what failed, where, and why?" directly |
| Future monitoring tooling would need to parse inconsistent log formats across lanes | Consistent structured events provide a stable foundation for Prometheus, alerting, or dashboarding later |

---

## 14. Diagnostic Findings

*To be populated after running the pre-code diagnostic protocol (Section 10).*

Expected subsections:
- Logging infrastructure inventory (lane → library → format → structured Y/N)
- Per-lane coverage audit results (analyst, MDO, feeder, graph, triage, scheduler)
- `/metrics`, `/dashboard`, `/e2e` endpoint content inventories
- AC gap table (pre-implementation status for AC-1 through AC-15)
- Recommended event format and failure taxonomy (based on what already exists)
- Final patch set (files + one-line descriptions + estimated line delta)
- Any surprises or change-surface adjustments

---

## 15. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Observability Phase 1 | Analyst pipeline run records + stdout summary | ✅ Done — 668 tests |
| **Observability Phase 2** | **Cross-lane runtime visibility + endpoint audit** | **⏳ Spec drafted — implementation pending** |
| TD-3 | Packaging/import-path stability | ⏳ Pending (after Obs P2) |
| Cleanup Tranche | Async markers, TD-5, TD-9, doc consolidation | ⏳ Pending (after TD-3) |
| UI Phase 3A Impl | Triage Board, Journey Studio, Journal & Review, Analysis Run | ⏸️ Parked |

---

## 16. Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Scope expands into a platform rewrite | Keep phase restricted to seam visibility and existing surfaces |
| Logging becomes verbose but not useful | Use a small event taxonomy and require tests around classifications |
| Observability semantics drift from real code paths | Derive status/event meaning from actual runtime branches and assert them in tests |
| UI/design work distracts the phase | Keep this phase backend- and operator-facing only |
| Hidden runtime split causes false confidence | Explicitly include triage, feeder, MDO, and analysis seams rather than focusing on only one lane |
| Grand unified logging framework temptation | Extend what already exists; do not introduce a new framework unless diagnostic shows current infrastructure is fundamentally inadequate |

---

## 17. Documentation Closure

At phase close, update:

- `docs/specs/observability_phase_2.md` — mark complete, flip all ACs, populate §14
- `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row, update next actions and debt register
- Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`, `AI_ORIENTATION.md` — update only if this phase changed architecture, structure, or debt state
- If implementation reveals enduring seam/event contracts worth preserving, add a compact reference under `docs/architecture/` or `docs/runbooks/`
- Cross-document sanity check: no contradictions, no stale phase refs
- Do **not** create competing progress plans

---

## 18. Appendix — Recommended Agent Prompt

```
Read `docs/specs/observability_phase_2.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 10 and report findings
before changing any code:

1. Audit current logging infrastructure across all runtime lanes
   (analyst, MDO, feeder, scheduler, graph, triage).
   Report: lane → library → format → structured Y/N.
2. Audit Obs P1 analyst pipeline coverage — confirm sufficient or identify gaps.
3. Audit MDO feed refresh logging — trace from APScheduler trigger to per-instrument outcome.
4. Audit feeder ingest logging — trace from /feeder/ingest to cache update,
   including recovery-after-staleness traceability.
5. Audit graph orchestration logging — trace from graph start to completion/timeout.
6. Audit triage loopback logging — trace /triage through loopback into /analyse
   for multiple symbols. Specific attention to partial-failure classification.
7. Audit scheduler health logging — identify whether APScheduler job lifecycle
   events are structured.
8. Audit /metrics, /dashboard, /e2e — call each endpoint, document content,
   note accuracy/gaps.
9. Run baseline test suite — confirm green, report count.
10. Propose: event format (based on what already exists), failure taxonomy
    mapped to actual code paths, smallest patch set (files, one-line description,
    estimated line delta), which lane to instrument first, any AC adjustments.

Hard constraints:
- This is additive observability only — no runtime behavior changes
- UI_CONTRACT.md API surface must not change
- No new monitoring infrastructure, alerting, or UI changes
- MarketPacketV2 contract locked — officer layer unchanged
- No SQLite, no new top-level module
- Deterministic tests only — no live provider dependency in CI
- If instrumenting a lane requires core logic changes (not just event/log lines),
  flag before proceeding

Do not change any code until the diagnostic report is reviewed and the
patch set is approved.

On completion, close the spec and update docs per §17:
1. `docs/specs/observability_phase_2.md` — mark ✅ Complete, flip all AC cells,
   populate §14 with: logging infrastructure inventory, per-lane audit results,
   endpoint content inventories, event format decision, failure taxonomy,
   patch set, surprises.
2. `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row,
   update next actions and debt register if applicable.
3. Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`,
   `AI_ORIENTATION.md` — update only if this phase changed architecture,
   structure, or debt state.
4. Cross-document sanity check: no contradictions, no stale phase refs.
5. Return Phase Completion Report (see Workflow E.8 in phase-spec-writer skill).

Commit all doc changes on the same branch as the implementation.
```
