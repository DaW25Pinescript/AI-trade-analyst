# AI Trade Analyst — Repo Review & Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 9 March 2026  
**Review date:** 9 March 2026  
**Current phase:** Operationalise Phase 2 — market-hours awareness, alerting, remote deployment  
**Planning horizon:** Next 6–8 weeks

> This file is the canonical progress/status document for the repo. Audit notes, phase notes, and review outputs should feed into this file rather than compete with it.

---

## 1) Executive Snapshot

The repository is in a **strong implementation state**:

- Core architecture is present and coherent across UI (`app/`), analyst engine (`ai_analyst/`), and market data lane (`market_data_officer/`).
- The previously tracked MDO build phases (1A, 1B, E+, promotion, provider routing, Operationalise Phase 1) are complete.
- Automated test coverage is broad and currently green in this environment:
  - **470 Python tests passing** (`ai_analyst/tests`)
  - **494 Python tests passing** (`market_data_officer/tests`)
  - **235 Node tests passing** (`tests/*.js`)

### Current position (plain language)

You are no longer proving basic feasibility. You are in the **operationalisation + hardening** stage: making the system safer, easier to run repeatedly, and more production-ready.

### Phase Status Overview

| Phase | Description | Status |
|-------|-------------|--------|
| Phase A | Single analyst smoke path | ✅ Complete |
| Phase B | Central provider/model config | ✅ Complete |
| Phase C | Quorum/degraded failure handling | ✅ Complete |
| Phase D | V1.1 snapshot integrity patch (H-1 → H-4) | ✅ Complete |
| Phase 1A | Market Data Officer — EURUSD baseline spine | ✅ Complete |
| Phase 1B | Market Data Officer — XAUUSD spine (15m, 1h, 4h, 1d) | ✅ Complete |
| Phase E+ | Additional instruments, provider abstraction | ✅ Complete |
| Instrument Promotion | GBPUSD/XAGUSD/XPTUSD → trusted — 419/419 tests | ✅ Complete |
| Per-Instrument Provider Routing | Explicit per-instrument provider policy — 468/468 tests | ✅ Complete |
| Operationalise Phase 1 | APScheduler feed refresh — 494/494 tests | ✅ Complete |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |
| Operationalise Phase 2 | Market-hours awareness, alerting, remote deployment | ⏳ Pending |

---

## 2) Where We Are Now (Grounded Status)

### Architecture and product posture

- Project doctrine is clearly data-first (market packets first, screenshots as optional supporting evidence).
- The product surface includes:
  - static browser workflow + gate logic
  - Python analyst API/CLI pipeline
  - MDO feed/packet generation
  - Macro Risk Officer context lane

### Delivery maturity indicators

- `README_specs.md` shows the major implementation phases complete and identifies **Operationalise** as the active hardening lane.
- `Makefile` defines a practical quality bar (`test-web`, `test-ai`, `test-all`) and reflects current CI/test workflows.
- Test suites run cleanly in this environment (no red tests observed).

### Cross-repo test inventory

The project now has multiple important test counts that should be tracked separately:

- `ai_analyst/tests` → **470**
- `market_data_officer/tests` → **494**
- `tests/*.js` → **235**

This progress plan should continue to distinguish these suites rather than treating “Python tests” as a single bucket.

### Known gaps and debt themes

From repo docs and current structure, the meaningful remaining work is concentrated in:

1. **Operational automation**
   - Market-hours awareness, scheduled runs, alerting, and deployment lifecycle confidence.
2. **Runtime hardening**
   - Security and API operational safeguards.
3. **Cleanup and consistency**
   - Pending async-marker tidy and doc consolidation.
4. **Developer/operator UX**
   - Easier bootstrap and less manual wiring for local/prod parity.

---

## 3) Where We Should Go Next

Operationalise Phase 2 is the **active implementation lane**. The other priorities below are the next cross-repo hardening candidates once current operationalisation work closes, or earlier if repo evidence justifies pulling them forward.

### Priority A — Operationalise Phase 2 (highest priority)

#### Objective
Extend the scheduler foundation into a more production-usable runtime with market-hours awareness, alerting hooks, and clearer deployment posture.

#### Deliverables
- Define and implement market-hours awareness behavior per instrument/provider.
- Add alerting hooks for refresh failures, stale artifacts, or repeated job faults.
- Document remote deployment/runtime expectations.
- Clarify stale-data semantics for market-closed vs market-open conditions.

#### Done criteria
- Off-hours behavior is deterministic and tested.
- Failures are visible and can trigger alerts rather than failing silently.
- Operators can run the service repeatedly with a documented deployment path.

---

### Priority B — Security and production hardening (high priority)

#### Objective
Close known operational risk items before broader live usage.

#### Deliverables
- Enforce upload-size and input guardrails consistently on `/analyse` path.
- Ensure error surfaces do not leak sensitive runtime internals.
- Document required production defaults (TLS, strict origin policy, key rotation, spend limits).

#### Done criteria
- Critical API abuse paths are capped with explicit tests.
- Security checklist items are mapped to concrete config and startup docs.

---

### Priority C — Observability and reliability confidence (medium/high)

#### Objective
Move from “tests pass” to “system behavior is observable and debuggable under failure”.

#### Deliverables
- Add one end-to-end integration test chain (validated input → analyst graph → arbiter verdict).
- Standardize structured event logging for feed runs and analysis requests.
- Add basic service-level metrics (success rate, latency bands, timeout counts).

#### Done criteria
- A single dashboard or log view can answer: “Is the system healthy right now?”
- Integration testing catches broken orchestration, not only unit regressions.

---

### Priority D — Cleanup and source-of-truth simplification (medium)

#### Objective
Reduce drift between progress/audit docs and remove stale planning artifacts.

#### Deliverables
- Keep one canonical progress plan (this file) and treat others as supporting or historical snapshots.
- Resolve pending async-marker cleanup items.
- Reconcile duplicate phase summaries across docs.

#### Done criteria
- New contributors can identify current phase and next implementation target in under 5 minutes.
- There is no ambiguity about which progress document is authoritative.

---

## 4) Proposed 6–8 Week Plan

### Weeks 1–2
- Finalize and implement Operationalise Phase 2 behavior.
- Add market-hours awareness rules and stale-data/open-market semantics tests.
- Add alerting hooks and basic deployment/runtime notes.

### Weeks 3–4
- Harden API guardrails and error handling.
- Add or expand targeted integration test for orchestration pipeline.
- Document runtime operations and security checklist.

### Weeks 5–6
- Add reliability metrics and basic run-status surface.
- Complete async-marker tidy.
- Consolidate planning docs and confirm this file as the canonical source of truth.

### Stretch (Weeks 7–8)
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

1. Confirm that the active Operationalise Phase 2 spec covers market-hours awareness, alerting, and remote deployment clearly enough to implement against.
2. Define market-hours contract semantics (open, closed, holiday/off-session, stale-but-expected, stale-and-bad).
3. Add one integration test that proves analyst verdict generation from a deterministic packet under mocked LLM response.
4. Update `README_specs.md` after each milestone to keep phase tracking accurate.
5. Decide explicitly whether **Security/API Hardening** becomes the next named phase after Operationalise Phase 2 closes.

---

## 7) Decision Gate Before “Production-Ready” Claim

Before claiming full production readiness, require all of the following:

- Operational scheduler running with observable health.
- Market-hours behavior and stale-data handling tested and deterministic.
- Critical API guardrails tested and enforced.
- One orchestration integration path green in CI.
- Security and deployment checklist completed with explicit config evidence.
- Single canonical progress/status document maintained.