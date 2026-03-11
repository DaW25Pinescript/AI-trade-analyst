# Repository Map

Quick orientation for contributors and coding agents.

## Top-level areas

- `app/` — browser/UI workflow layer (journey flow, triage/review surfaces, client-side state + schema wiring).
- `ai_analyst/` — analysis pipeline and service/API lane (prompting/orchestration, analyst personas, arbiter-facing output contracts).
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
4. **UI/workflow surfaces:** `app/` exposes triage/analyse/review workflow interfaces over the API/runtime outputs.

## Practical navigation tips

- Start with [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md) for current phase + next actions.
- Use [README.md](README.md) for enduring architecture references.
- Use [../specs/README.md](../specs/README.md) for implementation acceptance packages.
