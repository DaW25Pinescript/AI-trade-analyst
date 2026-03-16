# System Architecture (Repo-Grounded)

## Purpose

AI Trade Analyst is a multi-lane trading analysis system with a FastAPI + LangGraph analyst runtime, deterministic market data packaging, macro risk context generation, and a browser workflow layer for triage/journey/review. This document is a **current-state architecture view** for contributor onboarding and AI-agent orientation. It complements (does not replace) the repo map and canonical progress hub.

## Reality markers (read first)

- **Implemented (stable lanes):**
  - `market_data_officer/` feed + scheduler + packet builder lane
  - `macro_risk_officer/` macro context ingestion/reasoning lane
  - `ai_analyst/` FastAPI + LangGraph multi-analyst runtime lane
  - `app/` API-first UI workflow lane
- **Emerging convergence area:** direct, unified runtime coupling between the `ai_analyst` graph path and the MDO packet lane; concrete MDO coupling exists in legacy analyst paths and selected integrations.

> **Note:** Current phase, status, and sequencing live in [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md). This document describes enduring architecture, not execution progress.

## Major system lanes

### 1) Market/context data sources
- Price/timeframe market data is sourced via the MDO feed pipeline (`market_data_officer/feed/*`) and transformed into hot packages/structures.
- Macro/event context is sourced via MRO ingestion clients and feeder payloads (`macro_risk_officer/ingestion/*`, `macro_risk_officer/modal_macro_worker.py`).

### 2) Ingestion / feed pipeline
- MDO feed pipeline (`market_data_officer/feed/pipeline.py`) performs fetch, decode, validation, gap checks, resample/export.
- Scheduled refresh and market-hours/alert policy live in `market_data_officer/scheduler.py` and `market_data_officer/market_hours.py`.

### 3) Market Data Officer canonicalization (read-side packet layer)
- Canonical market packet assembly is centered in `market_data_officer/officer/service.py` (`build_market_packet` + structure/quality/feature synthesis).
- Contracts are defined in `market_data_officer/officer/contracts.py` (`MarketPacket`, `MarketPacketV2`, quality/structure blocks).

### 4) AI analysis engine / multi-analyst pipeline
- FastAPI entry and orchestration surface: `ai_analyst/api/main.py` (`/analyse`, `/analyse/stream`, triage/journey endpoints).
- Core analysis graph: `ai_analyst/graph/pipeline.py` (validate → macro context + chart setup fan-out → lenses → optional deliberation/overlay → arbiter).
- Dev-mode diagnostics layer (local-only): request-id anchored parse/lifecycle tracing and per-run diagnostics records for `/analyse` failure triage (gated by `AI_ANALYST_DEV_DIAGNOSTICS`/`DEBUG`).
- Prompting/model routing/config surfaces: `ai_analyst/prompt_library/*`, `ai_analyst/llm_router/*` (centralised via `ResolvedRoute` contract — single-source routing authority), `config/llm_routing.yaml`.

### 5) Arbiter / verdict / governance
- Current graph arbiter path runs in `ai_analyst/graph/arbiter_node.py` with verdict contracts under `ai_analyst/models/arbiter_output.py`.
- Legacy arbitration and deterministic scoring contracts remain present in `analyst/arbiter.py` and docs specs (`docs/specs/scoring/*`, `docs/architecture/senate_arbiter_schema.json`) and still inform governance semantics.

### 6) UI / workflow / review surfaces
- Browser workflow lives in `app/` (dashboard/journey/journal/review pages + store/components).
- API-first data access + snake_case↔camelCase boundary are handled in `app/lib/services.js` and `app/lib/adapters.js`.
- Journey persistence contracts are served by backend routes in `ai_analyst/api/routers/journey.py` writing to `app/data/journeys/*`.
- **Frontend:** The `ui/` directory contains the React + TypeScript + Tailwind frontend application (forward stack, introduced Phase 6). The legacy `app/` directory coexists but is not the forward UI surface.

### 7) Contracts / schemas / shared artifacts
- API and persistence contracts: `docs/architecture/CONTRACTS.md`, `docs/architecture/openapi.json`.
- Arbiter schema and scoring references: `docs/architecture/senate_arbiter_schema.json`, `docs/specs/scoring/*`.
- Prompt/report task schemas: `docs/specs/schemas/*.json`.

## End-to-end architecture diagram

```mermaid
flowchart LR
    subgraph Sources[Market & Context Sources]
        PR[Price providers / feed inputs]
        ME[Macro & event providers]
    end

    subgraph MDO[Market Data Officer lane]
        FP[feed.pipeline\nfetch→validate→resample→export]
        SCH[scheduler + market_hours + alert_policy]
        PKT[officer/service.py\nbuild_market_packet (canonical packet)]
    end

    subgraph MRO[Macro Risk Officer lane]
        MING[ingestion + feeder ingest]
        MCTX[reasoning engine\nMacroContext]
    end

    subgraph AI[AI Analyst lane (FastAPI + LangGraph)]
        API[api/main.py\n/analyse /stream /triage /journey]
        GRAPH[graph/pipeline.py\nchart+macro fan-out, lenses, deliberation]
        ARB[arbiter node\nfinal verdict + ticket draft]
    end

    subgraph UI[Workflow & Review Surfaces]
        APP[app/ pages + components + store]
        ADP[app/lib/services.js + adapters.js\nAPI boundary + casing translation]
        JDATA[app/data/journeys/*\ndrafts/decisions/results]
    end

    subgraph Contracts[Contracts & Schemas]
        C1[docs/architecture/CONTRACTS.md]
        C2[openapi.json + senate_arbiter_schema.json]
        C3[docs/specs/schemas/* + scoring refs]
    end

    PR --> FP --> SCH --> PKT
    ME --> MING --> MCTX

    PKT -. canonical market context (implemented, partial runtime coupling) .-> API
    MCTX --> GRAPH
    API --> GRAPH --> ARB

    ARB --> ADP --> APP
    API --> ADP
    API <--> JDATA

    C1 -. governs .-> API
    C1 -. governs .-> ADP
    C2 -. governs .-> ARB
    C3 -. shared artifacts .-> GRAPH
```

## Short component notes

- **MDO (`market_data_officer/`)** — deterministic market-data preparation and canonical packet read model; operational scheduler behavior is implemented and documented in runbooks/specs.
- **MRO (`macro_risk_officer/`)** — advisory macro context lane that can fail gracefully without hard-blocking analysis; supports scheduler/context/audit flows.
- **AI runtime (`ai_analyst/`)** — active backend/API and graph orchestration lane; this is the primary live analysis surface for `/analyse` and streaming workflows.
- **Legacy analyst lane (`analyst/`)** — retained arbitration/orchestration assets and contracts; still relevant to integration seams and governance semantics.
- **UI (`app/`)** — API-first journey workflow with explicit adapter boundary and persisted review artifacts.
- **Frontend (`ui/`)** — React + TypeScript + Tailwind frontend application (forward stack, introduced Phase 6). Coexists with legacy `app/`. Contains workspace-specific code under `ui/src/workspaces/` and shared components/hooks/types under `ui/src/shared/`.
- **Docs/contracts (`docs/architecture`, `docs/specs`)** — contract and schema backbone for casing, API shapes, arbiter schema, and structured outputs.

### 8) Agent Operations — Operator Observability Layer

The Agent Ops subsystem exposes the multi-agent analysis engine's architecture, health, and run-level behavior as read-only projections for operator trust and explainability.

**Endpoints (all read-only):**
- `GET /ops/agent-roster` — static architecture and roster truth (config-derived)
- `GET /ops/agent-health` — current health snapshot (observability-derived)
- `GET /runs/{run_id}/agent-trace` — run-level participation and lineage projection
- `GET /ops/agent-detail/{entity_id}` — entity-level detail with discriminated union
- `GET /runs/` — paginated, filterable run browser index (directory scan, PR-RUN-1)
- `GET /market-data/{instrument}/ohlcv` — stored OHLCV candle data for chart rendering (PR-CHART-1)
- `GET /reflect/persona-performance` — per-persona participation/override/alignment/confidence aggregation
- `GET /reflect/pattern-summary` — instrument × session verdict distribution buckets
- `GET /reflect/run/{run_id}` — run artifact bundle (run_record required, usage artifacts optional)

**Backend components:**
- Routers: `ai_analyst/api/routers/ops.py`, `ai_analyst/api/routers/runs.py`, `ai_analyst/api/routers/market_data.py`, `ai_analyst/api/routers/reflect.py`
- Models: `ai_analyst/api/models/ops.py`, `ops_trace.py`, `ops_detail.py`, `ops_run_browser.py`, `market_data.py`, `reflect.py`
- Services: `ai_analyst/api/services/ops_roster.py`, `ops_health.py`, `ops_trace.py`, `ops_detail.py`, `ops_run_browser.py`, `market_data_read.py`, `reflect_aggregation.py`, `reflect_bundle.py`
- Profile registry: `ai_analyst/api/services/ops_profile_registry.py` (static entity profiles)

**Data sources (read-side only):**
- Roster/detail: static persona config, profile registry
- Health: observability events, scheduler lifecycle, feeder health
- Trace: `run_record.json` (primary) + audit log `logs/runs/{run_id}.jsonl` (secondary for stances/overrides)
- Market data: MDO hot package CSVs in `market_data/packages/latest/` (read via `loader.load_timeframe()`)

**Contract:** `docs/ui/AGENT_OPS_CONTRACT.md` (§4–§7)

### 9) Reflect — AI Decision Evaluation Workspace

The Reflect workspace is a read-only frontend surface consuming the three Reflect backend endpoints (PR-REFLECT-1). It provides cross-run persona performance analysis, pattern distribution summaries, and individual run deep-dives.

**Frontend components** (`ui/src/workspaces/reflect/`):
- `ReflectPage` — workspace orchestrator with two-tab navigation (Overview / Runs)
- `PersonaPerformanceTable` — per-persona stats table with flagged highlighting
- `PatternSummaryTable` — instrument × session verdict distribution table
- `RunDetailView` — full artifact bundle inspector
- `UsageSummaryCard` — token/model/cost display from usage data
- `reflectAdapter.ts` — view-model normalisation layer

**Route:** `#/reflect` (hash router, same level as `#/ops`, `#/journal`, etc.)

**Endpoints consumed:** `/reflect/persona-performance`, `/reflect/pattern-summary`, `/reflect/run/{run_id}`, `/runs/` (via shared `useRuns` hook)

**Contract:** `docs/specs/PR_REFLECT_2_SPEC.md`

## Known architecture ambiguity (explicit)

- The repository and progress doc indicate coherent lane-level architecture, but not yet a single fully unified runtime where active `ai_analyst` graph execution always consumes MDO packets directly. Treat this as **emerging/in-progress convergence**, not fully complete coupling.
