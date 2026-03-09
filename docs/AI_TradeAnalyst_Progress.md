# AI Trade Analyst — Repo Review & Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Review date:** 9 March 2026  
**Planning horizon:** Next 6–8 weeks

---

## 1) Executive Snapshot

The repository is in a **strong implementation state**:

- Core architecture is present and coherent across UI (`app/`), analyst engine (`ai_analyst/`), and market data lane (`market_data_officer/`).
- The previously tracked MDO build phases (1A, 1B, E+, promotion, provider routing) are marked complete in the specs index.
- Automated test coverage is broad and currently green in this environment:
  - **470 Python tests passing** (`ai_analyst/tests`)
  - **235 Node tests passing** (`tests/*.js`)

### Current position (plain language)

You are no longer proving basic feasibility. You are in the **operationalisation + hardening** stage: making the system safer, easier to run repeatedly, and more production-ready.

---

## 2) Where We Are Now (Grounded Status)

## Architecture and product posture

- Project doctrine is clearly data-first (market packets first, screenshots as optional supporting evidence).
- The product surface includes:
  - static browser workflow + gate logic
  - Python analyst API/CLI pipeline
  - MDO feed/packet generation
  - Macro Risk Officer context lane

## Delivery maturity indicators

- `README_specs.md` shows the major MDO implementation phases complete and identifies **Operationalise (scheduler/APScheduler)** as the current phase.
- `Makefile` defines a practical quality bar (`test-web`, `test-ai`, `test-all`) and reflects current CI/test workflows.
- Test suites run cleanly in this environment (no red tests observed).

## Known gaps and debt themes

From repo docs and current structure, the meaningful remaining work is concentrated in:

1. **Operational automation**
   - Scheduled market-data feed runs and lifecycle monitoring.
2. **Runtime hardening**
   - Security and API operational safeguards.
3. **Cleanup and consistency**
   - Pending async-marker tidy and doc consolidation.
4. **Developer/operator UX**
   - Easier bootstrap and less manual wiring for local/prod parity.

---

## 3) Where We Should Go Next

## Priority A — Operationalise the data pipeline (highest priority)

### Objective
Turn manual/fixture-supported feed workflows into a reliable scheduled service.

### Deliverables
- Draft and approve an **Operationalise spec** (scheduler scope, cadence, failure policy).
- Add APScheduler-driven jobs for feed refresh with deterministic logging.
- Add health/status visibility (last successful run, next run, failure count).
- Define stale-data thresholds per instrument/timeframe.

### Done criteria
- Scheduled runs produce artifacts without manual intervention for multiple consecutive cycles.
- Failures are visible and recoverable (retry/backoff + alerting hook).
- Analyst packet consumers can detect stale/missing artifacts deterministically.

---

## Priority B — Security and production hardening (high priority)

### Objective
Close known operational risk items before broader live usage.

### Deliverables
- Enforce upload-size and input guardrails consistently on `/analyse` path.
- Ensure error surfaces do not leak sensitive runtime internals.
- Document required production defaults (TLS, strict origin policy, key rotation, spend limits).

### Done criteria
- Critical API abuse paths are capped with explicit tests.
- Security checklist items are mapped to concrete config and startup docs.

---

## Priority C — Observability and reliability confidence (medium/high)

### Objective
Move from “tests pass” to “system behavior is observable and debuggable under failure”.

### Deliverables
- Add one end-to-end integration test chain (validated input → analyst graph → arbiter verdict).
- Standardize structured event logging for feed runs and analysis requests.
- Add basic service-level metrics (success rate, latency bands, timeout counts).

### Done criteria
- A single dashboard/log query can answer: “Is the system healthy right now?”
- Integration test catches broken orchestration, not only unit regressions.

---

## Priority D — Cleanup and source-of-truth simplification (medium)

### Objective
Reduce drift between multiple progress/audit docs and remove stale planning artifacts.

### Deliverables
- Keep one canonical progress plan (this file) and treat others as historical snapshots.
- Resolve pending async-marker cleanup items.
- Reconcile duplicate phase summaries across docs.

### Done criteria
- New contributors can identify current phase and next implementation target in <5 minutes.

---

## 4) Proposed 6–8 Week Plan

## Weeks 1–2
- Approve Operationalise spec.
- Implement scheduler skeleton + config + logging.
- Add tests for schedule trigger and stale-data detection.

## Weeks 3–4
- Harden API guardrails and error handling.
- Add/expand targeted integration test for orchestration pipeline.
- Document runtime operations checklist.

## Weeks 5–6
- Add reliability metrics and basic run-status surface.
- Complete async-marker tidy.
- Consolidate planning docs.

## Stretch (Weeks 7–8)
- Pilot multi-environment config profiles (local/staging/prod).
- Optional distributed rate-limit/cache groundwork if deployment topology requires multi-worker scaling.

---

## 5) Risks to Manage

- **Doc drift risk:** multiple progress artifacts can diverge and confuse execution priority.
- **Operational blind spots:** scheduler without visibility/alerts can fail silently.
- **Confidence gap:** broad unit coverage may still miss cross-module orchestration regressions.
- **Security lag risk:** known hardening items left open too long increase deployment risk.

---

## 6) Immediate Next Actions (Concrete)

1. Create `docs/MDO_Operationalise_Spec.md` as active implementation spec if not already finalized.
2. Define scheduler job contract (inputs, artifact location, success/failure semantics).
3. Add one integration test that proves analyst verdict generation from a deterministic packet under mocked LLM response.
4. Update `README_specs.md` after each milestone to keep phase tracking accurate.

---

## 7) Decision Gate Before “Production-Ready” Claim

Before claiming full production readiness, require all of the following:

- Operational scheduler running with observable health.
- Critical API guardrails tested and enforced.
- One orchestration integration path green in CI.
- Security and deployment checklist completed with explicit config evidence.
- Single canonical progress/status document maintained.

