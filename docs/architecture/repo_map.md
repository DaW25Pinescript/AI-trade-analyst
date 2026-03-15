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
5. **Operator observability:** `ai_analyst/api/` serves Agent Ops read-only projection endpoints (roster, health, trace, detail) consumed by the `ui/src/workspaces/ops/` workspace.

## ui/ — React Frontend (Phase 6+)

Forward frontend stack: React + TypeScript + Tailwind.

- `ui/src/shared/` — cross-workspace code (API client, hooks, types, components)
- `ui/src/shared/api/ops.ts` — Agent Ops typed API layer
- `ui/src/workspaces/triage/` — Triage Board workspace
- `ui/src/workspaces/journey/` — Journey Studio workspace
- `ui/src/workspaces/analysis/` — Analysis Run workspace
- `ui/src/workspaces/journal/` — Journal & Review workspace
- `ui/src/workspaces/ops/` — Agent Ops workspace (Org/Health/Run modes + detail sidebar)

## Agent Ops backend (`ai_analyst/api/`)

- `ai_analyst/api/routers/ops.py` — Agent Ops router (roster, health, trace, detail)
- `ai_analyst/api/models/ops.py` — roster + health response models
- `ai_analyst/api/models/ops_trace.py` — trace response models
- `ai_analyst/api/models/ops_detail.py` — detail response models (discriminated union)
- `ai_analyst/api/services/ops_roster.py` — roster projection (static config)
- `ai_analyst/api/services/ops_health.py` — health projection (observability)
- `ai_analyst/api/services/ops_trace.py` — trace projection (run_record.json + audit log)
- `ai_analyst/api/services/ops_detail.py` — detail projection (roster + health + profile registry)
- `ai_analyst/api/services/ops_profile_registry.py` — static entity profiles

## Agent Ops tests

- `tests/test_ops_endpoints.py` — roster + health endpoint tests (54 tests)
- `tests/test_ops_trace_endpoints.py` — trace endpoint tests (70 tests)
- `tests/test_ops_detail_endpoints.py` — detail endpoint tests (72 tests)
- `tests/fixtures/sample_run_record.json` — trace test fixture
- `tests/fixtures/sample_audit_log.jsonl` — trace test fixture

## Practical navigation tips

- Start with [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md) for current phase + next actions.
- Use [README.md](README.md) for enduring architecture references.
- Use [../specs/README.md](../specs/README.md) for implementation acceptance packages.
