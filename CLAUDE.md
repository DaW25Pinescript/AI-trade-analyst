# AI Trade Analyst — Claude Code Context

## Project Overview
Multi-agent trading analysis platform. FastAPI backend + LangGraph pipeline + React/TypeScript/Tailwind frontend.
Repo: github.com/DaW25Pinescript/AI-trade-analyst

## Current Status (as of 21 Mar 2026)
- **Phase 8:** Complete. All 6 PRs shipped (PR-RUN-1, PR-CHART-1/2, PR-REFLECT-1/2/3).
- **Analysis Engine v1:** Active initiative. PRs AE-1 through AE-5 merged, Gate 2 CLOSED.
  Evidence-first pipeline: 3 lenses → snapshot → v2.0 persona prompts → engine runner → AnalysisEngineOutput + validators.
- **Next:** PR-AE-6 (Governance Layer P3). MacroLens scoped as fourth lens after Gate 2.
- **Backend tests:** 489 passed, 1 pre-existing failure (MDO scheduler import).
- **Frontend tests:** 406 total (401 passing, 5 pre-existing journey failures).

## Stack
- **Backend:** Python/FastAPI, LangGraph, `ai_analyst/` package
- **Frontend:** React + TypeScript + Tailwind, Vite, TanStack Query, hash-based routing
- **Market Data:** MDO (yFinance primary, Finnhub stub), APScheduler, instrument registry
- **LLM:** Claude Sonnet 4.6 for personas, Claude Opus 4.6 for arbiter, via CLIProxyAPI
- **Config:** `llm_routing.yaml` — single source of truth for model routing

## Key Architecture Rules
- **NEVER modify `AnalystOutput`** — it has 100+ references across 18 files. New engine work uses `AnalysisEngineOutput`.
- **Evidence Snapshot stays as plain dict** — not a typed model.
- **`run_validators()` returns results only** — no mutation of output.
- **All v1 validators are soft-level** — no hard failures.
- **Lens registry lives at** `ai_analyst/lenses/registry.py`.
- **`GraphState`** already has `macro_context: Optional[MacroContext]` wired in.
- **`ResolvedRoute` frozen dataclass** — use `resolve_task_route()` / `resolve_profile_route()` helpers. No bypass points.

## Test Commands
```bash
# Backend
cd backend && pytest

# Backend with coverage
cd backend && pytest --cov=ai_analyst

# Frontend
cd frontend && npm test

# Frontend watch mode
cd frontend && npm run test:watch
```

## Run the App
```
RUN.bat   # Full bootstrapper — prerequisite checks, first-run key setup
```
- Backend: http://127.0.0.1:8000
- Frontend: http://127.0.0.1:8080
- LLM Proxy: http://127.0.0.1:8317/v1

## Active Personas
`default_analyst`, `risk_officer`, `prosecutor`, `ict_purist`, `skeptical_quant`
Arbiter: `arbiter_node.py`

## PR Size Rule
Max ~1,200 lines before splitting into separate PRs.

## Workflow
- David drafts governance/design, Claude drafts specifics.
- Diagnostic-first before any code changes.
- Always run full test suite after changes — report backend + frontend counts.
- Never relitigate locked decisions (see progress doc).

## Key Files
- `docs/AI_TradeAnalyst_Progress.md` — canonical status hub
- `docs/SESSION_HANDOFF.md` — session handoff (read this first in new sessions)
- `ai_analyst/lenses/registry.py` — lens registry
- `ai_analyst/analyst_nodes.py` — persona node implementations
- `llm_routing.yaml` — LLM routing config
- `market_data_officer/instrument_registry.py` — instrument registry
