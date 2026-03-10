# AI Trade Analyst — Repo Review & Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 10 March 2026  
**Review date:** 10 March 2026  
**Current phase:** CI Seam Hardening — Gate missing Python integration seams in CI  
**Planning horizon:** Next 6–8 weeks

> This file is the canonical progress/status document for the repo. Audit notes, phase notes, and review outputs should feed into this file rather than compete with it.

---

## 1) Executive Snapshot

The repository is in a **strong implementation state**:

- Core architecture is present across UI (`app/`), analyst engine (`ai_analyst/`), market data lane (`market_data_officer/`), and macro context lane (`macro_risk_officer/`).
- The tracked Market Data Officer build phases through **Operationalise Phase 2** are complete.
- **Security/API Hardening** is complete and closed cleanly.
- Two high-impact analyst debt items have now been resolved:
  - **TD-1** — arbiter assert-based runtime contract enforcement
  - **TD-2** — `call_llm()` without timeout/retry safeguards
- **TD-10** (LLM failure modes under-tested) was also closed as a side-effect of the TD-2 resilience test work.
- Phase-gate test progression now reaches **677 tests green** at Security/API Hardening closure, with zero regressions reported.

### Current position (plain language)

You are no longer proving feasibility or building first-pass runtime behavior. You are in the **hardening, seam-gating, and change-safety** stage: making the system safer to operate, safer to refactor, and more trustworthy across its real runtime boundaries.

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
| TD-1 Micro-PR | Arbiter assert fix — explicit persona contract enforcement — 645 tests | ✅ Complete |
| Security/API Hardening | Auth gate, graph + LLM timeouts, error contracts, body limits, TD-2 closure — 677 tests | ✅ Complete |
| CI Seam Hardening | Gate missing Python integration seams in CI | ⏳ Active |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |

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

- `README_specs.md` should now identify **CI Seam Hardening** as the active phase, with Operationalise Phase 2 and Security/API Hardening recorded as complete.
- Security/API Hardening has now shipped four concrete hardening surfaces:
  - API auth gate
  - graph execution timeout
  - `call_llm()` timeout/retry/failure mapping
  - safer API error contracts and request-boundary enforcement
- The technical debt register is now live in this file and should be treated as a maintained section, not a one-off audit dump.
- Test suites run cleanly in the current merged state.

### Test count progression

Phase-closure counts should be read as **phase-gate numbers**, not as a single additive suite inventory.

| Phase | Tests | What it proved |
|------|------:|----------------|
| Phase 1A | 359 | EURUSD full relay spine |
| Phase 1B | 364 | XAUUSD spine |
| Phase E+ | 404 | Instrument registry |
| Provider Switchover | 404 | yFinance fallback + vendor provenance |
| Phase F | 419 | All 5 instruments trusted |
| Provider Routing | 468 | Per-instrument provider policy |
| Operationalise Phase 1 | 494 | APScheduler feed refresh |
| Operationalise Phase 2 — PR 1 | 549 | Market-hours awareness + freshness classification |
| Operationalise Phase 2 — PR 2 | 597 | Deterministic failure alerting + edge-triggered recovery |
| Operationalise Phase 2 — PR 3 | 644 | Runtime posture, startup validation, health-check, operator runbook |
| TD-1 | 645 | Arbiter assert fix |
| Security/API Hardening | 677 | Auth gate, graph + LLM timeouts, error contracts, body limits, TD-2 closure |

### Known gaps and debt themes

From repo docs and current structure, the meaningful remaining work is concentrated in:

1. **CI seam hardening / integration confidence**
   - Missing Python integration seams are not yet consistently gated in CI.
   - This is now the last major item in the production-readiness gate.
2. **Observability and seam visibility**
   - Important runtime paths need clearer pass/fail evidence, especially across orchestration boundaries.
3. **Cleanup and consistency**
   - Pending async-marker tidy and doc consolidation remain open.
4. **Developer/operator UX**
   - Easier bootstrap and less manual wiring for local/prod parity still matter.
5. **Future runtime-lane convergence**
   - The split between analyst, graph, MDO, and legacy lanes still shapes long-term architecture cleanup.

---

## 3) Where We Should Go Next

CI Seam Hardening is the **active implementation lane**. The priorities below reflect the current post-hardening state of the repo.

### Priority A — CI Seam Hardening (highest priority)

#### Objective
Move from “tests are broadly green” to “the important Python integration seams are actually gated in CI.”

#### Deliverables
- Gate `market_data_officer/tests` in CI where intended.
- Gate root Python integration tests in CI where intended.
- Add or strengthen direct coverage for `/analyse/stream` semantics if still shallow.
- Add one deterministic orchestration-path integration test that proves a real end-to-end contract across a meaningful seam.
- Make CI failure surfaces easier to interpret for contributors.

#### Done criteria
- Important Python seam regressions cannot slip through while CI remains green.
- The repo has at least one deterministic integration-path test covering a real orchestration chain.
- Missing seam coverage is explicitly closed or documented as an intentional defer.
- The final open item in the production-readiness gate is closed.

---

### Priority B — Observability and seam confidence (high priority)

#### Objective
Make it easier to tell whether the system is healthy across its real runtime boundaries, not just within isolated modules.

#### Deliverables
- Standardize structured event logging for feed runs and analysis requests where still inconsistent.
- Tighten status surfaces around scheduler/runtime health and analysis-path failures.
- Clarify what success/failure/recovery looks like across MDO and analyst runtime lanes.

#### Done criteria
- Operators and contributors can answer “what failed, where, and why?” without tracing multiple code paths manually.
- Seam behavior is visible, not inferred.

---

### Priority C — Cleanup and source-of-truth simplification (medium)

#### Objective
Reduce drift between progress/audit docs and remove stale planning artifacts.

#### Deliverables
- Keep one canonical progress plan (this file) and treat others as supporting or historical snapshots.
- Resolve pending async-marker cleanup items.
- Reconcile duplicate phase summaries across docs.
- Keep the technical debt register current as debt items are closed.

#### Done criteria
- New contributors can identify current phase and next implementation target in under 5 minutes.
- There is no ambiguity about which progress document is authoritative.

---

### Priority D — Future runtime-lane convergence and packaging stability (medium / later)

#### Objective
Reduce the architectural split between runtime lanes and address the packaging/import fragility that still sits behind TD-3.

#### Deliverables
- Address `sys.path.insert` usage with proper packaging/install discipline.
- Add import-path stability tests once packaging is fixed.
- Revisit duplicated orchestration and mixed data-shape handling when seam confidence is stronger.

#### Done criteria
- The repo is less environment-sensitive.
- Future cleanup can happen against stronger contracts and better CI coverage.

---

## 4) Proposed 6–8 Week Plan

### Weeks 1–2
- Execute CI Seam Hardening.
- Gate missing Python integration seams in CI.
- Add one deterministic orchestration-path integration test.
- Tighten `/analyse/stream` seam coverage if still shallow.

### Weeks 3–4
- Improve seam observability and failure visibility.
- Clarify runtime/logging surfaces where integration failures are still hard to interpret.
- Confirm status surfaces and operator-facing signals remain aligned with actual code paths.

### Weeks 5–6
- Complete async-marker tidy.
- Consolidate planning docs and keep the technical debt register synchronized with implementation reality.
- Prepare the next named cleanup lane around packaging/import stability and runtime-lane convergence.

### Stretch (Weeks 7–8)
- Pilot multi-environment config/profile cleanup once import-path stability work is ready.
- Revisit TD-5 / TD-9 micro-PRs if the active seam work closes cleanly.

---

## 5) Risks to Manage

- **Doc drift risk:** multiple progress artifacts can diverge and confuse execution priority.
- **Seam blind-spot risk:** broad unit coverage may still miss cross-module orchestration and integration regressions.
- **Architecture split risk:** parallel runtime lanes can create false confidence if only one path is being hardened.
- **Packaging fragility risk:** `sys.path.insert`-style wiring remains a deployment and reproducibility footgun until TD-3 is addressed.
- **Cleanup drift risk:** low-level debt can expand into architecture work if not kept tightly scoped.

---

## 6) Immediate Next Actions (Concrete)

1. Implement against the active **CI Seam Hardening** phase/spec once confirmed in `README_specs.md`.
2. Gate `market_data_officer/tests` and root Python integration seams in CI where intended.
3. Add or strengthen direct `/analyse/stream` coverage if the current seam remains under-tested.
4. Add one deterministic orchestration-path integration test that proves a real Python seam end-to-end.
5. Update `README_specs.md` after each milestone to keep phase tracking accurate.
6. Keep the technical debt register current as micro-PRs and named cleanup items close.

---

## 7) Decision Gate Before “Production-Ready” Claim

Most of the earlier production-readiness gate has now been satisfied.

**Already satisfied:**
- Operational scheduler running with observable health.
- Market-hours behavior and stale-data handling tested and deterministic.
- Critical API guardrails tested and enforced.
- `call_llm()` safeguards and resilience coverage shipped.
- Single canonical progress/status document maintained.

**Remaining gate to close:**
- Important Python integration seams are CI-gated where intended.
- At least one orchestration integration path is green in CI.

This is why **CI Seam Hardening** is the active phase.

---

## 8) Technical Debt Register

Findings from the senior architect audit conducted after Operationalise Phase 2 closure (644 tests, 10 March 2026). Items are severity-ranked and tagged with recommended resolution timing.

### Critical — resolve in next named phase or as micro-PR

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-1 | `assert` used for runtime contract enforcement | `analyst/arbiter.py` | Silent contract violation under `-O` flag; invalid state reaches downstream decision logic | **✅ Resolved — 10 March 2026** |
| TD-2 | `call_llm()` lacks timeout, retry, circuit-breaker | `analyst/analyst.py`, LLM call path | Stalled upstream call blocks processing; unstable tail latency; failure amplification | **✅ Resolved — 10 March 2026** — timeout (60s), retry (2 max, exponential backoff), failure mapping to `RuntimeError`. |
| TD-3 | `sys.path.insert` used as dependency wiring | Multiple core modules | Environment-dependent import resolution; deployment instability; shadowing risk | **Named micro-PR / later phase** — prerequisite for multi-environment config profiles; requires proper packaging (`pyproject.toml` / editable install) |

### Maintenance — resolve opportunistically or as named cleanup

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-4 | Orchestration duplication (single vs multi-analyst) | `analyst/service.py`, `analyst/multi_analyst_service.py` | Parallel pipelines with drift risk; lifecycle changes must be made in two places | **Named cleanup** — extract shared orchestration steps into common helper; pick up after seam confidence improves |
| TD-5 | Magic-string enum duplication | `analyst/analyst.py`, `analyst/personas.py`, `analyst/arbiter.py` | Verdict/confidence/alignment enums hand-maintained in multiple modules; drift and inconsistent validation | **Micro-PR** — centralise into shared contracts module; low risk, high leverage |
| TD-6 | `build_market_packet()` God-function | `market_data_officer/officer/service.py` | Trust policy, quality, feature extraction, serialization, and logging in one function; hard to test in isolation | **Future cleanup** — decompose when packet assembly needs to evolve; not blocking current work |
| TD-7 | `build_market_packet()` eager loading + `iterrows()` | `market_data_officer/officer/service.py` | O(total_rows) Python loop per request; CPU/memory pressure scales with instrument count | **Future optimisation** — current scale (5 instruments, 4–6 TFs) is within tolerance; revisit when concurrency or instrument count grows |
| TD-8 | Mixed data-shape handling in `classify_fvg_context` | `analyst/pre_filter.py` | `hasattr`/`get` branches for object vs dict payloads; weak upstream contracts | **Resolves with runtime lane convergence** — architectural, not a standalone cleanup |
| TD-9 | Unused variables in `build_market_packet()` | `market_data_officer/officer/service.py` | `is_provisional`, `quality_label`, `quality_flags`, `struct_kwargs` assigned but unused; misleading intent | **Micro-PR** — remove or document intent; very small |

### Documentation / testing gaps — address as part of related phases

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-10 | LLM failure modes under-tested | Test suites for analyst path | Tests previously mocked `call_llm` but did not exercise timeout, malformed response, or retry behavior | **✅ Resolved — 10 March 2026** — resilience coverage landed alongside TD-2 closure |
| TD-11 | No import-path stability tests | No coverage for `sys.path.insert` patterns | Path mutation normalised in tests; packaging regressions not actively caught | **Follows TD-3** — when packaging is fixed, add environment-matrix tests |
| TD-12 | Cross-module architecture contracts undocumented | Core service boundaries | Ownership of policy decisions, fallback semantics, scaling expectations embedded in code flow | **Future documentation** — address when runtime lanes converge or during next architecture review |

### Resolution sequence

1. **Resolved:** TD-1, TD-2, and TD-10 are closed.
2. **Active implementation lane:** CI Seam Hardening.
3. **Next significant debt item after seam work:** TD-3 (packaging/import stability).
4. **Opportunistic micro-PRs:** TD-5 (enum centralisation) and TD-9 (unused vars).
5. **Later named cleanup work:** TD-4 (orchestration duplication), TD-6/TD-7 (packet assembly), TD-8 (data-shape convergence), TD-12 (architecture docs).
6. **Dependent follow-on:** TD-11 resolves when TD-3 is completed.
