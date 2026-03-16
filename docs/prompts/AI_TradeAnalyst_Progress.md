---
project: "AI Trade Analyst"
repo: "github.com/your-org/ai-trade-analyst"
status: "Active"
horizon: "Next 5–7 weeks"
last_updated: 2026-03-16
test_suites:
  backend: 1811
  frontend: 361
---

# Project Progress Plan

## Phase Status Overview

| Phase | Description | Status | Tests |
|:---|:---|:---|:---|
| Phase 1A | EURUSD full relay spine | complete | 359 |
| Phase 1B | XAUUSD spine | complete | 364 |
| Phase E+ | Instrument registry | complete | 404 |
| Provider Switchover | yFinance fallback + vendor provenance | complete | 404 |
| Phase F | All 5 instruments trusted | complete | 419 |
| Provider Routing | Per-instrument provider policy | complete | 468 |
| Operationalise Phase 1 | APScheduler feed refresh | complete | 494 |
| Operationalise Phase 2 — PR 1 | Market-hours awareness | complete | 549 |
| Operationalise Phase 2 — PR 2 | Deterministic failure alerting | complete | 597 |
| Operationalise Phase 2 — PR 3 | Runtime posture + health-check | complete | 644 |
| TD-1 | Arbiter assert fix | complete | 645 |
| Security/API Hardening | Auth gate + timeouts + TD-2 closure | complete | 677 |
| CI Seam Hardening | MDO + root seams CI-gated | complete | 1743 |
| LLM Routing Centralisation | ResolvedRoute + 27 new tests | complete | 643 |
| Observability Phase 1 | Run record + per-analyst visibility | complete | 668 |
| Phase 7 (Agent Ops) | Agent Ops read-side stack + Run Browser | complete | +197 backend, +63 frontend |
| PR-RUN-1 | Run Browser endpoint + RunBrowserPanel | complete | +42 |
| PR-CHART-1 | OHLCV data-seam + candlestick chart | complete | +39 backend, +9 frontend |
| PR-REFLECT-1 | Persona performance + pattern summary endpoints | complete | +11 |
| PR-REFLECT-2 | Reflective dashboard frontend | complete | +55 frontend |
| PR-CHART-2 | Run context overlay + multi-timeframe | next | 0 |
| PR-REFLECT-3 | Integration + rules-based suggestions v0 | planned | 0 |

## Recent Activity

| Date | Phase | Activity | PR/Issue |
|:---|:---|:---|:---|
| 16 Mar 2026 | PR-REFLECT-2 | Reflect workspace frontend — Overview + Runs tabs, +55 frontend tests (361 total) | PR-REFLECT-2 |
| 16 Mar 2026 | PR-REFLECT-1 | Backend reflect aggregation — 3 endpoints, +11 backend tests | PR-REFLECT-1 |
| 16 Mar 2026 | PR-CHART-1 | OHLCV data-seam + CandlestickChart in Run mode, +39 backend / +9 frontend tests | PR-CHART-1 |
| 15 Mar 2026 | PR-RUN-1 | Run Browser endpoint + RunBrowserPanel — +42 backend tests | PR-RUN-1 |
| 15 Mar 2026 | PR-OPS-5b | Frontend Run mode + Detail sidebar — Phase 7 complete | PR-OPS-5b |
| 15 Mar 2026 | PR-OPS-5a | Frontend types + Health mode | PR-OPS-5a |
| 14 Mar 2026 | PR-OPS-4b | Backend agent-detail endpoint | PR-OPS-4b |
| 14 Mar 2026 | PR-UI-6 | Journal & Review workspace MVP — Phase 6 complete | PR-UI-6 |

## Roadmap

| Priority | Phase | Description | Status | Depends On |
|:---|:---|:---|:---|:---|
| 1 | PR-RUN-1 | Run Browser endpoint + frontend | complete | Phase 7 complete |
| 2 | PR-CHART-1 | OHLCV data-seam + basic candlestick chart | complete | PR-RUN-1 |
| 3 | PR-REFLECT-1 | Persona performance aggregation endpoints | complete | PR-RUN-1 |
| 4 | PR-REFLECT-2 | Reflective dashboard frontend | complete | PR-REFLECT-1 |
| 5 | PR-CHART-2 | Run context overlay + multi-timeframe | next | PR-CHART-1 |
| 6 | PR-REFLECT-3 | Integration + rules-based parameter suggestions v0 | planned | PR-CHART-2 + PR-REFLECT-2 |

## Technical Debt Register

| ID | Item | Location | Status | Severity |
|:---|:---|:---|:---|:---|
| TD-1 | assert used for runtime contract enforcement | analyst/arbiter.py | resolved | critical |
| TD-2 | call_llm() lacks timeout/retry | analyst/analyst.py | resolved | critical |
| TD-3 | sys.path.insert dependency wiring | pyproject.toml | resolved | critical |
| TD-4 | Orchestration duplication | analyst/service.py | open | maintenance |
| TD-5 | Magic-string enum duplication | analyst/enums.py (canonical) | resolved | maintenance |
| TD-6 | build_market_packet() God-function | market_data_officer/officer/service.py | open | maintenance |
| TD-9 | Unused variables in build_market_packet() | market_data_officer/officer/service.py | resolved | maintenance |
| TD-12 | Cross-module architecture contracts undocumented | Core service boundaries | open | maintenance |
| TD-13 | Agent Ops run selector paste-field only | ui/src/workspaces/ops/ | resolved | maintenance |
| TD-14 | Reflect artifact richness gap — audit-log dependent metrics | ai_analyst/api/services/reflect_aggregation.py | open | maintenance |

## Risk Register

| Name | Detail |
|:---|:---|
| UI split risk | Journey and legacy workflow surfaces diverge if compatibility boundaries are not documented clearly. |
| Seam blind-spot | Broad unit coverage may still miss cross-module orchestration regressions. |
| Scope-creep risk | Future extensions (Chart Evidence, Run Artifact Inspector) could jump ahead of prioritisation. |
| MDO collection errors | 3 MDO scheduler test files fail collection due to missing apscheduler dependency in CI — does not block development but masks ~250 tests. |
| Pre-existing test failures | 61 backend failures (code-vs-test drift) and 5 frontend failures (journey freeze-error) are pre-existing and unchanged across Phase 8. |

## Test History

| Phase | Count | Description |
|:---|:---|:---|
| Phase 1A | 359 | EURUSD full relay spine |
| Phase 1B | 364 | XAUUSD spine |
| Phase E+ | 404 | Instrument registry |
| Provider Routing | 468 | Per-instrument provider policy |
| Operationalise Phase 1 | 494 | APScheduler feed refresh |
| Operationalise Phase 2 — PR 2 | 597 | Deterministic failure alerting |
| Operationalise Phase 2 — PR 3 | 644 | Runtime posture + health-check |
| Security/API Hardening | 677 | Auth gate + timeouts + TD-2 closure |
| CI Seam Hardening | 1743 | MDO + root Python seams CI-gated |
| Observability Phase 1 | 668 | Run record + per-analyst visibility |
| PR-RUN-1 | +42 | Run Browser endpoint + RunBrowserPanel |
| PR-CHART-1 | +39 backend, +9 frontend | OHLCV data-seam + CandlestickChart |
| PR-REFLECT-1 | +11 | Persona performance + pattern summary endpoints |
| PR-REFLECT-2 | +55 frontend | Reflect workspace frontend (361 frontend total) |
