# AI Trade Analyst — Repo Review & Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 10 March 2026
**Review date:** 10 March 2026
**Current phase:** Security/API Hardening — authn/authz, timeout policy, error contracts  
**Planning horizon:** Next 6–8 weeks

> This file is the canonical progress/status document for the repo. Audit notes, phase notes, and review outputs should feed into this file rather than compete with it.

---

## 1) Executive Snapshot

The repository is in a **strong implementation state**:

- Core architecture is present across UI (`app/`), analyst engine (`ai_analyst/`), market data lane (`market_data_officer/`), and macro context lane (`macro_risk_officer/`).
- The tracked Market Data Officer build phases through **Operationalise Phase 1** are complete.
- Automated test coverage is broad and currently green in this environment:
  - **470 Python tests passing** (`ai_analyst/tests`)
  - **644 Python tests passing** (`market_data_officer/tests`)
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
| Operationalise Phase 2 | Market-hours awareness, alerting, runtime posture — 644/644 tests | ✅ Complete |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |
| Security/API Hardening | API edge protection, timeout policy, error contracts | ⏳ Active |
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
- `market_data_officer/tests` → **644**
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

---

## 8) Technical Debt Register

Findings from the senior architect audit conducted after Operationalise Phase 2 closure (644 tests, 10 March 2026). Items are severity-ranked and tagged with recommended resolution timing.

### Critical — resolve in next named phase or as micro-PR

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-1 | `assert` used for runtime contract enforcement | `analyst/arbiter.py` | Silent contract violation under `-O` flag; invalid state reaches downstream decision logic | **✅ Resolved — 10 March 2026** |
| TD-2 | `call_llm()` lacks timeout, retry, circuit-breaker | `analyst/analyst.py`, LLM call path | Stalled upstream call blocks processing; unstable tail latency; failure amplification | **Fold into Security/API Hardening** — same risk surface as `/analyse` timeout policy |
| TD-3 | `sys.path.insert` used as dependency wiring | Multiple core modules | Environment-dependent import resolution; deployment instability; shadowing risk | **Named micro-PR** — prerequisite for multi-environment config profiles; requires proper packaging (`pyproject.toml` / editable install) |

### Maintenance — resolve opportunistically or as named cleanup

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-4 | Orchestration duplication (single vs multi-analyst) | `analyst/service.py`, `analyst/multi_analyst_service.py` | Parallel pipelines with drift risk; lifecycle changes must be made in two places | **Named cleanup** — extract shared orchestration steps into common helper; pick up between phases |
| TD-5 | Magic-string enum duplication | `analyst/analyst.py`, `analyst/personas.py`, `analyst/arbiter.py` | Verdict/confidence/alignment enums hand-maintained in multiple modules; drift and inconsistent validation | **Micro-PR** — centralise into shared contracts module; low risk, high leverage |
| TD-6 | `build_market_packet()` God-function | `market_data_officer/officer/service.py` | Trust policy, quality, feature extraction, serialization, and logging in one function; hard to test in isolation | **Future cleanup** — decompose when packet assembly needs to evolve; not blocking current work |
| TD-7 | `build_market_packet()` eager loading + `iterrows()` | `market_data_officer/officer/service.py` | O(total_rows) Python loop per request; CPU/memory pressure scales with instrument count | **Future optimisation** — current scale (5 instruments, 4–6 TFs) is within tolerance; revisit when concurrency or instrument count grows |
| TD-8 | Mixed data-shape handling in `classify_fvg_context` | `analyst/pre_filter.py` | `hasattr`/`get` branches for object vs dict payloads; weak upstream contracts | **Resolves with runtime lane convergence** — architectural, not a standalone cleanup |
| TD-9 | Unused variables in `build_market_packet()` | `market_data_officer/officer/service.py` | `is_provisional`, `quality_label`, `quality_flags`, `struct_kwargs` assigned but unused; misleading intent | **Micro-PR** — remove or document intent; very small |

### Documentation / testing gaps — address as part of related phases

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-10 | LLM failure modes under-tested | Test suites for analyst path | Tests mock `call_llm` but don't exercise timeout, malformed response, or retry behavior | **Addressed by TD-2 resolution** — when safeguards are added, tests follow |
| TD-11 | No import-path stability tests | No coverage for `sys.path.insert` patterns | Path mutation normalised in tests; packaging regressions not actively caught | **Addressed by TD-3 resolution** — when packaging is fixed, add environment-matrix tests |
| TD-12 | Cross-module architecture contracts undocumented | Core service boundaries | Ownership of policy decisions, fallback semantics, scaling expectations embedded in code flow | **Future documentation** — address when runtime lanes converge or during next architecture review |

### Resolution sequence

1. **Now:** TD-1 arbiter assert fix (micro-PR, already drafted)
2. **Next phase:** TD-2 folds into Security/API Hardening spec
3. **Between phases:** TD-3 (sys.path.insert), TD-5 (enum centralisation), TD-9 (unused vars) as opportunistic micro-PRs
4. **Future:** TD-4 (orchestration duplication), TD-6/TD-7 (packet assembly), TD-8 (data-shape convergence), TD-12 (architecture docs)
5. **Follows from above:** TD-10, TD-11 resolve as side-effects of their parent items
