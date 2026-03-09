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

- Core architecture is present across UI (`app/`), analyst engine (`ai_analyst/`), market data lane (`market_data_officer/`), and macro context lane (`macro_risk_officer/`).
- The tracked Market Data Officer build phases through **Operationalise Phase 1** are complete.
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
| Operationalise Phase 2 | Market-hours awareness, alerting, remote deployment | ⏳ Active |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |
| Security/API Hardening | API edge protection, timeout policy, error contracts | 🔜 Next candidate |
| CI Seam Hardening | Gate missing Python integration seams in CI | 🔜 Next candidate |

---

## 2) Where We Are Now (Grounded Status)

### Architecture and product posture

- Project doctrine is clearly data-first (market packets first, screenshots as optional supporting evidence).
- The product surface includes:
  - static browser workflow + gate logic
  - Python analyst API/CLI pipeline
  - MDO feed/packet generation
  - Macro Risk Officer context lane

### Runtime integration reality

The repo architecture is coherent, but the live runtime is **not yet a single fully unified lane**.

- The active `ai_analyst` API/graph path is GroundTruth/LangGraph-based.
- Direct `ai_analyst` → `market_data_officer` runtime coupling was **not** established in the audit.
- Concrete MDO coupling is present in the **legacy analyst lane** and in some root/test integrations.
- UI integration is API-first through FastAPI routes such as `/analyse`, `/triage`, `/watchlist/triage`, `/journey/*`, and `/feeder/*`.

This means Market Data Officer progress is strategically important, but it should not be overstated as the sole live runtime backbone of the current analysis path.

### Delivery maturity indicators

- `README_specs.md` identifies **Operationalise Phase 2** as the active phase and points to a dedicated phase spec.
- `Makefile` defines a practical quality bar (`test-web`, `test-ai`, `test-all`) and reflects current CI/test workflows.
- Test suites run cleanly in this environment (no red tests observed).

### Cross-repo test inventory

The project has multiple important test counts that should be tracked separately:

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
3. **Observability and seam confidence**
   - CI gating, integration-path confidence, and failure visibility.
4. **Cleanup and consistency**
   - Pending async-marker tidy and doc consolidation.
5. **Developer/operator UX**
   - Easier bootstrap and less manual wiring for local/prod parity.

---

## 3) Where We Should Go Next

Operationalise Phase 2 is the **active implementation lane**. The priorities below describe the next cross-repo hardening candidates once current operationalisation work closes, or earlier if repo evidence justifies pulling them forward.

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

### Priority B — Security/API Hardening (high priority)

#### Objective
Close known operational risk items on the production-facing API edge before broader live usage.

#### Deliverables
- Add explicit authn/authz policy for `/analyse` and related production routes.
- Add server-side timeout policy for graph execution.
- Tighten error contracts so runtime internals do not leak to clients.
- Enforce explicit request/body limits beyond file-upload bounds.
- Document required production defaults (TLS, strict origin policy, key rotation, spend limits).

#### Done criteria
- Critical API abuse and edge-failure paths are capped with explicit tests.
- Security checklist items are mapped to concrete config and startup docs.
- `/analyse` has a documented and testable edge-protection policy.

---

### Priority C — CI Seam Hardening and Observability (medium/high)

#### Objective
Move from “tests pass” to “important runtime seams are CI-gated, observable, and debuggable under failure”.

#### Deliverables
- Add one end-to-end integration test chain (validated input → analyst graph → arbiter verdict).
- Gate `market_data_officer/tests` in CI.
- Gate root Python integration tests in CI where practical.
- Add direct coverage for `/analyse/stream` semantics.
- Standardize structured event logging for feed runs and analysis requests.
- Add basic service-level metrics (success rate, latency bands, timeout counts).

#### Done criteria
- A single dashboard or log view can answer: “Is the system healthy right now?”
- Integration testing catches broken orchestration and seam regressions, not only unit regressions.

---

### Priority D — Cleanup and source-of-truth simplification (medium)

#### Objective
Reduce drift between progress/audit docs and remove stale planning artifacts.

#### Deliverables
- Keep one canonical progress plan (this file) and treat others as supporting or historical snapshots.
- Resolve pending async-marker cleanup items.
- Reconcile duplicate phase summaries across docs.
- Remove stale statements such as “spec TBD” once phase specs exist.

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
- Open and execute Security/API Hardening.
- Add or expand targeted integration test for orchestration pipeline.
- Document runtime operations and security checklist.

### Weeks 5–6
- Add CI seam gates and basic run-status surface.
- Complete async-marker tidy.
- Consolidate planning docs and confirm this file as the canonical source of truth.

### Stretch (Weeks 7–8)
- Pilot multi-environment config profiles (local/staging/prod).
- Optional distributed rate-limit/cache groundwork if deployment topology requires multi-worker scaling.

---

## 5) Risks to Manage

- **Doc drift risk:** multiple progress artifacts can diverge and confuse execution priority.
- **Operational blind spots:** scheduler without visibility/alerts can fail silently.
- **Confidence gap:** broad unit coverage may still miss cross-module orchestration and seam regressions.
- **Security lag risk:** known API edge hardening items left open too long increase deployment risk.
- **Architecture split risk:** parallel runtime lanes can create false confidence if only one path is being hardened.

---

## 6) Immediate Next Actions (Concrete)

1. Implement against `docs/MDO_Operationalise_Phase2_Spec.md` as the active phase spec.
2. Define market-hours contract semantics (`open`, `closed`, `holiday/off-session`, `stale-but-expected`, `stale-and-bad`).
3. Add one integration test that proves analyst verdict generation from a deterministic packet under mocked LLM response.
4. Update `README_specs.md` after each milestone to keep phase tracking accurate.
5. Prepare `Security_API_Hardening.md` as the next named phase spec so there is no handoff gap when Phase 2 closes.

---

## 7) Decision Gate Before “Production-Ready” Claim

Before claiming full production readiness, require all of the following:

- Operational scheduler running with observable health.
- Market-hours behavior and stale-data handling tested and deterministic.
- Critical API guardrails tested and enforced.
- One orchestration integration path green in CI.
- MDO/root seam coverage is CI-gated where intended.
- Security and deployment checklist completed with explicit config evidence.
- Single canonical progress/status document maintained.
