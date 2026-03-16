# Repository Map

Quick orientation for contributors and coding agents.

## Top-level areas

- `app/` — legacy browser/UI workflow layer (journey flow, triage/review surfaces, client-side state + schema wiring). Coexists with `ui/` but is not the forward UI surface.
- `ui/` — React + TypeScript + Tailwind frontend (forward stack, introduced Phase 6). See [ui/ detail](#ui--react-frontend-phase-6) below.
- `ai_analyst/` — analysis pipeline, service/API lane, and Agent Ops backend (prompting/orchestration, analyst personas, arbiter-facing output contracts, operator observability endpoints).
- `market_data_officer/` — deterministic market-data lane (feed ingestion, packet assembly, quality/provenance handling).
- `macro_risk_officer/` — macro context and risk regime lane consumed by analysis/runtime flows.
- `tests/` — repo-level test coverage for integration and cross-surface contracts.
- `docs/` — documentation system:
  - canonical status hub in `AI_TradeAnalyst_Progress.md`
  - supporting specs in `specs/`
  - enduring architecture in `architecture/`
  - operator procedures in `runbooks/`
  - rationale/history in `design-notes/`
  - superseded snapshots in `archive/`

## How this fits together

1. **Market/context ingestion:** `market_data_officer/` and `macro_risk_officer/` produce deterministic context and packet inputs.
2. **Analysis pipeline:** `ai_analyst/` consumes context, runs analyst/persona orchestration, and produces structured outputs.
3. **Arbiter/verdict layer:** arbiter logic consolidates analyst outputs into final decision artifacts with contract-aware semantics.
4. **UI/workflow surfaces:** `ui/` (forward React stack) and `app/` (legacy) expose triage/analyse/review workflow interfaces over the API/runtime outputs.
5. **Operator observability:** `ai_analyst/api/` serves Agent Ops read-only projection endpoints (roster, health, trace, detail, market data) consumed by the `ui/src/workspaces/ops/` workspace.
6. **Reflective intelligence backend:** `ai_analyst/api/` now also serves `/reflect` aggregation and run bundle endpoints for cross-run analysis (PR-REFLECT-1).

## ui/ — React Frontend (Phase 6+)

Forward frontend stack: React + TypeScript + Tailwind.

- `ui/src/shared/` — cross-workspace code (API client, hooks, types, components)
- `ui/src/shared/api/ops.ts` — Agent Ops typed API layer
- `ui/src/shared/api/marketData.ts` — Market Data typed API layer (PR-CHART-1)
- `ui/src/shared/hooks/useMarketData.ts` — Market Data TanStack Query hook (PR-CHART-1)
- `ui/src/workspaces/ops/components/CandlestickChart.tsx` — Candlestick chart component (PR-CHART-1)
- `ui/src/workspaces/triage/` — Triage Board workspace
- `ui/src/workspaces/journey/` — Journey Studio workspace
- `ui/src/workspaces/analysis/` — Analysis Run workspace
- `ui/src/workspaces/journal/` — Journal & Review workspace
- `ui/src/workspaces/ops/` — Agent Ops workspace (Org/Health/Run modes + detail sidebar)
- `ui/src/workspaces/reflect/` — Reflect workspace (Overview/Runs tabs, PR-REFLECT-2)
- `ui/src/shared/api/reflect.ts` — Reflect typed API layer (PR-REFLECT-2)
- `ui/src/shared/hooks/useReflect.ts` — Reflect TanStack Query hooks (PR-REFLECT-2)
- `ui/tests/reflect.test.tsx` — Reflect workspace tests (+55 tests, PR-REFLECT-2)

## Agent Ops backend (`ai_analyst/api/`)

- `ai_analyst/api/routers/ops.py` — Agent Ops router (roster, health, trace, detail)
- `ai_analyst/api/routers/runs.py` — Run Browser router (`GET /runs/`, PR-RUN-1)
- `ai_analyst/api/models/ops.py` — roster + health response models
- `ai_analyst/api/models/ops_trace.py` — trace response models
- `ai_analyst/api/models/ops_detail.py` — detail response models (discriminated union)
- `ai_analyst/api/models/ops_run_browser.py` — run browser response models (PR-RUN-1)
- `ai_analyst/api/services/ops_roster.py` — roster projection (static config)
- `ai_analyst/api/services/ops_health.py` — health projection (observability)
- `ai_analyst/api/services/ops_trace.py` — trace projection (run_record.json + audit log)
- `ai_analyst/api/services/ops_detail.py` — detail projection (roster + health + profile registry)
- `ai_analyst/api/services/ops_profile_registry.py` — static entity profiles
- `ai_analyst/api/services/ops_run_browser.py` — run browser projection (directory scan, PR-RUN-1)
- `ai_analyst/api/routers/market_data.py` — Market Data router (`GET /market-data/{instrument}/ohlcv`, PR-CHART-1)
- `ai_analyst/api/models/market_data.py` — OHLCV response models (Candle, OHLCVResponse, PR-CHART-1)
- `ai_analyst/api/services/market_data_read.py` — market data read service (hot package CSV projection, PR-CHART-1)
- `ai_analyst/api/routers/reflect.py` — Reflect router (`/reflect/persona-performance`, `/reflect/pattern-summary`, `/reflect/run/{run_id}`)
- `ai_analyst/api/models/reflect.py` — Reflect response models (persona stats, pattern buckets, run bundle)
- `ai_analyst/api/services/reflect_aggregation.py` — bounded run scan + optional audit-log enrichment aggregation
- `ai_analyst/api/services/reflect_bundle.py` — run bundle loader with graceful artifact degradation

## Agent Ops tests

- `tests/test_ops_endpoints.py` — roster + health endpoint tests (54 tests)
- `tests/test_ops_trace_endpoints.py` — trace endpoint tests (70 tests)
- `tests/test_ops_detail_endpoints.py` — detail endpoint tests (72 tests)
- `tests/test_run_browser_endpoints.py` — run browser endpoint tests (42 tests, PR-RUN-1)
- `tests/test_market_data_endpoints.py` — market data endpoint tests (39 tests, PR-CHART-1)
- `tests/test_reflect_endpoints.py` — reflect endpoint tests (11 tests, PR-REFLECT-1)
- `tests/fixtures/sample_run_record.json` — trace + run browser test fixture
- `tests/fixtures/sample_audit_log.jsonl` — trace test fixture

## Practical navigation tips

- Start with [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md) for current phase + next actions.
- Use [README.md](README.md) for enduring architecture references.
- Use [../specs/README.md](../specs/README.md) for implementation acceptance packages.
