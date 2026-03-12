# AI Trade Analyst — Repo Review & Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 12 March 2026
**Review date:** 10 March 2026
**Current phase:** Observability Phase 2 — cross-lane runtime visibility (UI implementation intentionally parked)
**Planning horizon:** Next 6–8 weeks

> This file is the canonical progress/status document for the repo. Audit notes, phase notes, and review outputs should feed into this file rather than compete with it.

**See also**
- Docs navigation index: `docs/README.md`
- Specs inventory: `docs/specs/README.md`
- Enduring architecture references: `docs/architecture/README.md`
- Runbooks: `docs/runbooks/README.md`
- Historical snapshots/audits: `docs/archive/README.md`
- UI documentation lane: `docs/ui/` — `UI_BACKEND_AUDIT.md`, `UI_CONTRACT.md`, `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, `VISUAL_APPENDIX.md`

---

## Phase Index (at-a-glance)

- **Completed named phases:** Phase A, B, C, D, 1A, 1B, E+, Instrument Promotion, Provider Routing, Operationalise P1/P2, TD-1 Micro-PR, Security/API Hardening, CI Seam Hardening, LLM Routing Centralisation, Observability Phase 1, UI Phase 1, UI Phase 2, UI Phase 3A.
- **Current phase:** Observability Phase 2 — cross-lane runtime visibility and failure surface clarification. UI Phase 3A design is complete and banked; UI implementation is intentionally parked while the repo shifts into a runtime-hardening lane.
- **Next actions:** Draft and execute Observability Phase 2 spec; then TD-3 packaging/import stability; then cleanup tranche (async markers, TD-5, TD-9, doc consolidation). UI implementation resumes after the backend-quality sequence is complete.
- **Active decision gate:** the production-readiness gate remains satisfied; the current execution gate is runtime hardening — strengthening observability, packaging stability, and seam confidence before resuming UI buildout or broader convergence work.

## 1) Executive Snapshot

The repository is in a **strong implementation state**:

- Core architecture is present across UI (`app/`), analyst engine (`ai_analyst/`), market data lane (`market_data_officer/`), and macro context lane (`macro_risk_officer/`).
- The tracked Market Data Officer build phases through **Operationalise Phase 2** are complete.
- **Security/API Hardening** is complete and closed cleanly.
- Two high-impact analyst debt items have now been resolved:
  - **TD-1** — arbiter assert-based runtime contract enforcement
  - **TD-2** — `call_llm()` without timeout/retry safeguards
- **TD-10** (LLM failure modes under-tested) was also closed as a side-effect of the TD-2 resilience test work.
- A formal UI documentation lane now exists under `docs/ui/`, with a completed backend capability audit, a canonical UI contract (Active), a workspace blueprint with visual design layer, written design decisions, and a visual appendix referencing all wireframes and the component system.
- Phase-gate test progression now reaches **677 tests green** at Security/API Hardening closure, with zero regressions reported.


### Latest increment — UI Phase 3A workspace blueprint + visual design (12 Mar 2026)

- Completed the full workspace blueprint and visual design layer for Phase 3A core product workspaces.
- Published `docs/ui/UI_WORKSPACES.md` — defines seven workspaces organized into Runtime, Review, and Operator lanes with a Triage Board → Journey Studio → Analysis Run → Journal & Review primary flow.
- Published `docs/ui/DESIGN_NOTES.md` — captures all visual and interaction decisions (per-row staleness derivation, freeze-locks-entire-flow, Save Result gating, tab persistence, data_state read-only rule, no-fake-detail-screen constraint) so implementation can proceed without reverse-engineering wireframes.
- Published `docs/ui/VISUAL_APPENDIX.md` — consolidated reference sheet linking all final wireframe and component system images.
- Wireframes produced and locked for: Triage Board (3 iterations), Journey Studio (2 iterations), Analysis Run (3 iterations with 4-state lifecycle grid).
- Component Design System produced with four columns (Trust/Freshness Indicators, Action Buttons, Information Panels, State Labels) plus four Composition Patterns (trust strip, execution stack, conditional rail, post-action lock).
- All design artifacts are contract-faithful — every element maps to `UI_CONTRACT.md` sections 6, 7, 9–12 and `UI_WORKSPACES.md` sections 5–7.
- Phased exposure plan defined: Phase 3A (Triage Board, Journey Studio, Journal & Review, Analysis Run cleanup), Phase 3B (Feeder, Ops, Analytics, optional streaming), Phase 3C (Chart Evidence, Run Artifact Inspector).

### Latest increment — UI Phase 2 UI contract (12 Mar 2026)

- Completed the canonical frontend handoff doc for the current repo surface: `docs/ui/UI_CONTRACT.md`.
- The contract locks source-of-truth rules (Python routes first, stale generated OpenAPI second), endpoint-family error behavior, shared `data_state` semantics, and a canonical UI run-state model.
- It also formalizes the Journey-vs-legacy split, timeout/retryability expectations, and the rule that frontend implementation should update the contract deliberately rather than rediscover backend behavior ad hoc.

### Latest increment — UI Phase 1 backend capability audit (12 Mar 2026)

- Completed a repo-grounded backend-to-UI capability audit and published `docs/ui/UI_BACKEND_AUDIT.md`.
- Inventory includes live FastAPI routes, request/response model shapes, runtime execution modes (sync vs SSE), artifact surfaces, and current `/app` usage coverage.
- Audit explicitly maps active-used vs active-unused capabilities to guide follow-on `UI_CONTRACT` and `UI_WORKSPACES` documentation phases.

### Latest increment — AI Analyst dev diagnostics (11 Mar 2026)

- Added dev-gated diagnostics for `/analyse` and `/analyse/stream` to improve local failure triage without external observability tooling.
- JSON-backed multipart fields now emit raw-value parse logs in dev mode and return structured 422 details (`field`, `raw_value`, `expected_shape`, parse error, `request_id`).
- Request lifecycle stage tracing now records high-signal checkpoints (request/auth/parse/graph/fan-out/arbiter/artifact/complete) and persists local diagnostics records per request.
- Added `AI_ANALYST_DEV_DIAGNOSTICS=true` / `DEBUG=true` gating so production behavior remains conservative by default.
- Multipart request parsing for string-array form fields (`timeframes`, `no_trade_windows`, `open_positions`, `overlay_indicator_claims`) now tolerates both JSON array strings and Swagger-style CSV input while preserving structured 422 diagnostics and request-id traceability.

### Current position (plain language)

You are no longer proving feasibility or building first-pass runtime behavior. The full UI documentation lane (audit → contract → workspace blueprint → wireframes → component system) is complete and banked. UI implementation is intentionally parked while the repo shifts into a **runtime-hardening lane**: the moving lanes (analyst, graph, MDO, legacy surfaces, feeder context) need stronger observability, packaging stability, and seam confidence before wider buildout. The sequence is Observability Phase 2, then TD-3 packaging, then a targeted cleanup tranche.

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
| CI Seam Hardening | CI-gate MDO + root Python seams, stream event semantics — 1743 tests across 5 CI jobs | ✅ Complete |
| LLM Routing Centralisation | Single-source routing via ResolvedRoute contract, 13 bypass removals, 27 new tests — 643 tests | ✅ Complete |
| Observability Phase 1 | Analyst pipeline run visibility — run_record.json + stdout summary — 668 tests | ✅ Complete |
| UI Phase 1 | Backend Capability Audit — `docs/ui/UI_BACKEND_AUDIT.md` | ✅ Complete |
| UI Phase 2 | UI Contract — canonical frontend handoff / run-state + error semantics | ✅ Complete |
| UI Phase 3A | Workspace Blueprint + Visual Design — wireframes, component system, design notes, visual appendix | ✅ Complete |
| UI Phase 3A Impl | First UI implementation slice — Triage Board + Journey Studio build | ⏸️ Parked |
| UI Phase 3B | Backend capability exposure — Feeder, Ops, Analytics, optional streaming | ⏸️ Parked |
| Observability Phase 2 | Cross-lane runtime visibility and failure surface clarification | ▶️ Next |
| TD-3 | Packaging/import-path stability (`sys.path.insert` cleanup) | ⏳ Pending (after Obs P2) |
| Cleanup Tranche | Async markers, doc consolidation, TD-5/TD-9 micro-PRs | ⏳ Pending (after TD-3) |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending (included in cleanup tranche) |
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

- `docs/specs/README.md` now serves as a specs inventory aligned to this canonical progress hub (not a competing status source).
- Security/API Hardening has now shipped four concrete hardening surfaces:
  - API auth gate
  - graph execution timeout
  - `call_llm()` timeout/retry/failure mapping
  - safer API error contracts and request-boundary enforcement
- The technical debt register summary in this file remains canonical for execution context; the enduring debt ledger is tracked in `docs/architecture/technical_debt.md`.
- The UI contract now serves as the intended anti-corruption layer between backend behavior and future `/app/` implementation work.
- The full UI documentation lane (`docs/ui/`) is complete with five artifacts: `UI_BACKEND_AUDIT.md`, `UI_CONTRACT.md`, `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, and `VISUAL_APPENDIX.md`.
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
| CI Seam Hardening | 1743 | MDO + root Python seams CI-gated, stream event semantics, 5 CI jobs |
| LLM Routing Centralisation | 643 | Single-source routing via ResolvedRoute; 13 bypass removals; 27 new deterministic route/bypass tests |
| Observability Phase 1 | 668 | Run record + stdout summary; per-analyst result/skip/fail visibility; 25 new deterministic tests |

### Known gaps and debt themes

From repo docs and current structure, the meaningful remaining work is concentrated in:

1. **Observability and seam visibility** (highest non-UI priority)
   - Important runtime paths still benefit from clearer pass/fail evidence, especially across orchestration boundaries.
   - Observability Phase 1 shipped run records and stdout summaries; Phase 2 should standardize structured event logging across all lanes and tighten failure surfaces.
2. **Packaging and import stability** (next after observability)
   - `sys.path.insert` wiring (TD-3) remains an environment-sensitive deployment footgun.
   - Prerequisite for stronger multi-environment stability and contributor onboarding.
3. **Cleanup and consistency**
   - Pending async-marker tidy and doc consolidation remain open.
   - TD-5 (enum centralisation) and TD-9 (unused vars) are ready as micro-PRs.
4. **UI implementation** (parked, fully designed)
   - ✅ UI Phase 1, UI Phase 2, and UI Phase 3A (design) are complete and banked.
   - Implementation resumes after the runtime-hardening sequence.
   - Phase 3B (Feeder, Ops, Analytics, streaming) and Phase 3C (Chart Evidence, Run Artifact Inspector) remain fenced.
5. **Future runtime-lane convergence**
   - The split between analyst, graph, MDO, and legacy lanes still shapes long-term architecture cleanup.
   - Revisit only after observability, packaging, and cleanup are stronger.

---


## 3) Where We Should Go Next

The production-readiness gate is **already satisfied**. The UI documentation lane is complete and banked. The current value lane is runtime hardening: strengthening observability, packaging stability, and seam confidence before resuming UI buildout or broader convergence.

### Priority A — Observability Phase 2: Cross-Lane Runtime Visibility (highest priority)

#### Objective
Standardize structured event logging across all runtime lanes and make it easy to answer "what failed, where, and why?" without manually tracing code paths.

#### Context
The repo has multiple moving lanes (analyst pipeline, graph orchestration, MDO feed refresh, feeder context, legacy surfaces). Observability Phase 1 shipped run records and stdout summaries for the analyst pipeline. Phase 2 should extend visibility across orchestration boundaries and tighten failure surfaces for operators and contributors.

#### Deliverables
- Standardize structured event logging for feed runs and analysis requests where still inconsistent.
- Tighten status surfaces around scheduler/runtime health and analysis-path failures.
- Clarify what success/failure/recovery looks like across MDO and analyst runtime lanes.
- Make cross-lane failures visible without requiring manual code-path tracing.

#### Done criteria
- Operators and contributors can answer "what failed, where, and why?" from logs and status surfaces alone.
- Seam behavior across orchestration boundaries is visible, not inferred.
- Structured logging is consistent enough that future monitoring/alerting can be built on top of it.

---

### Priority B — TD-3: Packaging and Import-Path Stability (high priority, after Obs P2)

#### Objective
Remove the `sys.path.insert` wiring footgun and establish proper packaging discipline.

#### Context
The technical debt register flags TD-3 as the main prerequisite for multi-environment stability and contributor onboarding. This is the structural wiring fix that makes everything downstream safer.

#### Deliverables
- Replace `sys.path.insert` usage with proper packaging (`pyproject.toml` / editable install).
- Add import-path stability tests (TD-11 resolves as a follow-on).
- Validate that the repo works cleanly in fresh environments without manual path manipulation.

#### Done criteria
- The repo is less environment-sensitive.
- New contributors can set up and run without discovering import-path quirks.
- TD-11 (import-path stability tests) can be closed as a follow-on.

---

### Priority C — Cleanup Tranche (medium, after TD-3)

#### Objective
Close small friction items that reduce drift and improve contributor experience, without expanding into architecture surgery.

#### Deliverables
- Resolve pending async-marker cleanup (4 files).
- Execute TD-5 (enum centralisation) and TD-9 (unused vars) as micro-PRs.
- Reconcile duplicate phase summaries across docs.
- Update `docs/specs/README.md` and docs indexes.
- Keep the technical debt register current.

#### Done criteria
- New contributors can identify current phase and next implementation target in under 5 minutes.
- There is no ambiguity about which progress document is authoritative.
- TD-5 and TD-9 are closed.

---

### Priority D — UI Phase 3A Implementation (parked — resume after runtime hardening)

#### Objective
Build the Phase 3A core product workspaces using the locked design artifacts.

#### Status
The design phase is **complete and banked**. All workspace blueprints, wireframes, component system, and design decisions are locked and documented. Implementation can proceed as component assembly when this lane resumes.

#### Banked deliverables (ready for pickup)
- ✅ `docs/ui/UI_WORKSPACES.md`, `DESIGN_NOTES.md`, `VISUAL_APPENDIX.md`
- ✅ Wireframes: Triage Board, Journey Studio, Analysis Run (4-state lifecycle)
- ✅ Component Design System with Composition Patterns
- ✅ `UI_CONTRACT.md` governance rule (§3.1) prevents ad hoc contract drift while parked.

#### Implementation targets (when resumed)
- Build Triage Board, Journey Studio, Journal & Review, Analysis Run cleanup.
- The Triage → Journey → Freeze → Journal flow end-to-end.
- Phase 3B (Feeder, Ops, Analytics, streaming) and Phase 3C (Chart Evidence, Run Artifact Inspector) remain fenced.

---

### Priority E — Future Runtime-Lane Convergence and Extensions (later)

#### Objective
Reduce the architectural split between runtime lanes and address broader convergence only after observability, packaging, and cleanup are stronger.

#### Deliverables
- Revisit duplicated orchestration (TD-4) and mixed data-shape handling (TD-8) when seam confidence is stronger.
- Treat Chart Evidence and Run Artifact Inspector as Phase 3C post-foundation UI extensions.
- Address runtime-lane convergence (analyst, graph, MDO, legacy) as a deliberate architecture phase, not a side-effect of other work.

#### Done criteria
- Future cleanup and UI extension work can happen against stronger contracts and better CI coverage.

---

## 4) Proposed 6–8 Week Plan

### Weeks 1–2
- Draft and begin executing **Observability Phase 2** spec: cross-lane runtime visibility and failure surface clarification.
- Audit current structured logging coverage across analyst, MDO, feeder, and scheduler lanes.
- Identify the highest-value seam visibility gaps and standardize event formats.

### Weeks 3–4
- Complete Observability Phase 2 execution and close with test/coverage evidence.
- Begin **TD-3 packaging/import-path stability**: replace `sys.path.insert` with proper packaging.
- Validate clean-environment setup without manual path manipulation.

### Weeks 5–6
- Complete TD-3 and close TD-11 (import-path stability tests) as follow-on.
- Execute **cleanup tranche**: async-marker tidy, TD-5 enum centralisation, TD-9 unused vars, doc index reconciliation.

### Stretch (Weeks 7–8)
- Revisit broader runtime-lane convergence readiness based on observability and packaging improvements.
- Evaluate whether to resume UI Phase 3A implementation or continue with TD-4/TD-8 architecture cleanup.
- Keep Chart Evidence and Run Artifact Inspector fenced as Phase 3C.

---

## 5) Risks to Manage

- **Observability gap risk:** cross-lane failures remain invisible without structured logging; operators cannot diagnose issues without manual code tracing.
- **Packaging fragility risk:** `sys.path.insert`-style wiring remains a deployment and reproducibility footgun until TD-3 is addressed.
- **Contract drift risk:** frontend implementation (when resumed) bypasses `UI_CONTRACT.md` and rediscovers backend behavior ad hoc. Mitigated by Section 3.1 governance rule in the contract.
- **Design-implementation drift risk:** UI implementation (when resumed) diverges from locked wireframes and component system. Mitigated by `DESIGN_NOTES.md` and `VISUAL_APPENDIX.md` as written references.
- **UI split risk:** Journey and legacy workflow surfaces diverge further if compatibility boundaries are not documented clearly.
- **Seam blind-spot risk:** broad unit coverage may still miss cross-module orchestration and integration regressions.
- **Cleanup drift risk:** low-level debt can expand into architecture work if not kept tightly scoped.
- **Scope-creep risk:** future extensions such as Chart Evidence or Run Artifact Inspector could jump ahead of the runtime-hardening sequence.

---

## 6) Immediate Next Actions (Concrete)

1. ~~CI Seam Hardening~~ — ✅ Complete (10 March 2026).
2. ~~LLM Routing Centralisation~~ — ✅ Complete (11 March 2026).
3. ~~Observability Phase 1~~ — ✅ Complete (11 March 2026). Run record + stdout summary shipped. 668 tests.
4. ~~UI Phase 1 — Backend Capability Audit~~ — ✅ Complete (12 March 2026). `docs/ui/UI_BACKEND_AUDIT.md`.
5. ~~UI Phase 2 — UI Contract~~ — ✅ Complete (12 March 2026). `docs/ui/UI_CONTRACT.md` promoted to **Active**.
6. ~~UI Phase 3A — Workspace Blueprint + Visual Design~~ — ✅ Complete (12 March 2026). `UI_WORKSPACES.md`, `DESIGN_NOTES.md`, `VISUAL_APPENDIX.md`, wireframes, and component design system all locked.
7. Draft and execute **Observability Phase 2** — cross-lane runtime visibility and failure surface clarification. This is the highest-value non-UI work remaining.
8. After Obs P2 closes, execute **TD-3** — packaging/import-path stability (`sys.path.insert` → proper packaging).
9. After TD-3, execute **cleanup tranche** — async markers, TD-5 (enum centralisation), TD-9 (unused vars), doc index reconciliation.
10. **UI Phase 3A implementation** remains parked and ready for pickup after the runtime-hardening sequence.
11. Keep **Chart Evidence Workspace** and **Run Artifact Inspector** in the post-foundation extension lane (Phase 3C).

---

## 7) Decision Gate Before "Production-Ready" Claim

Most of the earlier production-readiness gate has now been satisfied.

**Already satisfied:**
- Operational scheduler running with observable health.
- Market-hours behavior and stale-data handling tested and deterministic.
- Critical API guardrails tested and enforced.
- `call_llm()` safeguards and resilience coverage shipped.
- Single canonical progress/status document maintained.

**Remaining gate — now closed (CI Seam Hardening, 10 March 2026):**
- ✅ Important Python integration seams are CI-gated where intended — `mdo-tests` (644 tests) and `root-python-tests` (139 tests) jobs added.
- ✅ At least one orchestration integration path is green in CI — `test_multi_analyst_integration.py` (make_packet → digest → personas → arbitrate → output) runs in `root-python-tests`.

**The production-readiness gate is now satisfied.**

The current execution gate is no longer production-readiness; it is runtime hardening — strengthening observability across orchestration seams, packaging stability, and developer/operator confidence before resuming UI buildout.

---

## 8) Technical Debt Register

Findings from the senior architect audit conducted after Operationalise Phase 2 closure (644 tests, 10 March 2026). Items are severity-ranked and tagged with recommended resolution timing.

### Critical — resolve in next named phase or as micro-PR

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-1 | `assert` used for runtime contract enforcement | `analyst/arbiter.py` | Silent contract violation under `-O` flag; invalid state reaches downstream decision logic | **✅ Resolved — 10 March 2026** |
| TD-2 | `call_llm()` lacks timeout, retry, circuit-breaker | `analyst/analyst.py`, LLM call path | Stalled upstream call blocks processing; unstable tail latency; failure amplification | **✅ Resolved — 10 March 2026** — timeout (60s), retry (2 max, exponential backoff), failure mapping to `RuntimeError`. |
| TD-3 | `sys.path.insert` used as dependency wiring | Multiple core modules | Environment-dependent import resolution; deployment instability; shadowing risk | **Priority B — scheduled after Observability Phase 2** — requires proper packaging (`pyproject.toml` / editable install) |

### Maintenance — resolve opportunistically or as named cleanup

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-4 | Orchestration duplication (single vs multi-analyst) | `analyst/service.py`, `analyst/multi_analyst_service.py` | Parallel pipelines with drift risk; lifecycle changes must be made in two places | **Named cleanup** — extract shared orchestration steps into common helper; pick up after seam confidence improves |
| TD-5 | Magic-string enum duplication | `analyst/analyst.py`, `analyst/personas.py`, `analyst/arbiter.py` | Verdict/confidence/alignment enums hand-maintained in multiple modules; drift and inconsistent validation | **Cleanup tranche** — centralise into shared contracts module; low risk, high leverage |
| TD-6 | `build_market_packet()` God-function | `market_data_officer/officer/service.py` | Trust policy, quality, feature extraction, serialization, and logging in one function; hard to test in isolation | **Future cleanup** — decompose when packet assembly needs to evolve; not blocking current work |
| TD-7 | `build_market_packet()` eager loading + `iterrows()` | `market_data_officer/officer/service.py` | O(total_rows) Python loop per request; CPU/memory pressure scales with instrument count | **Future optimisation** — current scale (5 instruments, 4–6 TFs) is within tolerance; revisit when concurrency or instrument count grows |
| TD-8 | Mixed data-shape handling in `classify_fvg_context` | `analyst/pre_filter.py` | `hasattr`/`get` branches for object vs dict payloads; weak upstream contracts | **Resolves with runtime lane convergence** — architectural, not a standalone cleanup |
| TD-9 | Unused variables in `build_market_packet()` | `market_data_officer/officer/service.py` | `is_provisional`, `quality_label`, `quality_flags`, `struct_kwargs` assigned but unused; misleading intent | **Cleanup tranche** — remove or document intent; very small |

### Documentation / testing gaps — address as part of related phases

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-10 | LLM failure modes under-tested | Test suites for analyst path | Tests previously mocked `call_llm` but did not exercise timeout, malformed response, or retry behavior | **✅ Resolved — 10 March 2026** — resilience coverage landed alongside TD-2 closure |
| TD-11 | No import-path stability tests | No coverage for `sys.path.insert` patterns | Path mutation normalised in tests; packaging regressions not actively caught | **Follows TD-3** — when packaging is fixed, add environment-matrix tests |
| TD-12 | Cross-module architecture contracts undocumented | Core service boundaries | Ownership of policy decisions, fallback semantics, scaling expectations embedded in code flow | **Future documentation** — address when runtime lanes converge or during next architecture review |

### Resolution sequence

1. **Resolved:** TD-1, TD-2, and TD-10 are closed.
2. **Completed:** CI Seam Hardening (10 March 2026) — production-readiness gate satisfied.
3. **Next:** Observability Phase 2 (cross-lane runtime visibility).
4. **Then:** TD-3 (packaging/import stability).
5. **Then:** Cleanup tranche — TD-5 (enum centralisation), TD-9 (unused vars), async markers.
6. **Later named cleanup work:** TD-4 (orchestration duplication), TD-6/TD-7 (packet assembly), TD-8 (data-shape convergence), TD-12 (architecture docs).
7. **Dependent follow-on:** TD-11 resolves when TD-3 is completed.
