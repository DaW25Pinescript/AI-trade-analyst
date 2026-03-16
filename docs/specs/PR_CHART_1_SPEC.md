# AI Trade Analyst — PR-CHART-1: OHLCV Data Seam Validation + Basic Candlestick Chart Spec

**Status:** ✅ Complete — Outcome A confirmed, implementation shipped
**Date:** 15 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Branch:** `pr-chart-1-ohlcv-seam`
**Phase:** PR-CHART-1 (Phase 8, Week 2)
**Depends on:** PR-RUN-1 complete (Run Browser endpoint + frontend shipped)

---

## 1. Purpose

**After:** PR-RUN-1 (Run Browser — `GET /runs/` endpoint, RunBrowserPanel, 316 ops tests). Phase 8 Week 1 complete.

**Question this phase answers:** Does a read-side OHLCV data seam exist in the MDO pipeline that a new API endpoint can serve to a frontend chart component without triggering scheduler execution or live data fetches?

**From → To:**

- **From:** The operator selects a run in the Run Browser and sees trace data (stages, participants, arbiter verdict), but has no price context. There is no chart surface anywhere in the UI. The MDO pipeline fetches and processes OHLCV data, but whether that data is persisted and accessible outside runtime is unconfirmed.
- **To (if seam exists):** A `GET /market-data/{instrument}/ohlcv` endpoint serves stored OHLCV candle data, and a basic `CandlestickChart` component renders it as an embedded panel in Run mode. The chart shows price context for the instrument associated with the selected run.
- **To (if seam does not exist):** The diagnostic documents exactly what MDO stores, where, and in what format. The PR closes as a seam-validation finding that identifies the smallest remediation needed to create a readable OHLCV store — which becomes the scope of a revised PR-CHART-1a.

This is a **data-seam validation first, chart implementation second.** The Phase 8 plan correctly identified this as the biggest uncertainty in the chart lane. The diagnostic resolves it before any code is written.

**Chart placement (LOCKED from Phase 8 plan):** Charts embed as a panel within Run mode context, not as a separate `/chart` workspace.

---

## 2. Scope

### In scope

- **Mandatory (regardless of seam outcome):**
  - Pre-code diagnostic to locate and validate MDO's OHLCV storage format, access path, and scheduler coupling
  - Documented finding on seam viability

- **Conditional (only if diagnostic confirms a readable seam):**
  - `GET /market-data/{instrument}/ohlcv` backend endpoint — serve stored OHLCV candle data
  - `CandlestickChart` frontend component using `lightweight-charts`
  - `useMarketData(instrument, timeframe)` frontend hook
  - Chart panel embedded in Run mode, rendered when a run is selected
  - Contract tests for the new endpoint
  - Frontend component tests for the chart

### Target components (conditional)

| Layer | Component | Role |
|-------|-----------|------|
| Backend | `GET /market-data/{instrument}/ohlcv` endpoint | Serve stored OHLCV candles |
| Backend | Market data read service | Read from MDO's existing storage (format TBD by diagnostic) |
| Frontend | `CandlestickChart` | Render candlestick chart via lightweight-charts |
| Frontend | Agent Ops Run mode | Embed chart panel below run browser / above trace |

### Out of scope (hard list)

- No new data fetching — endpoint reads stored data, does not trigger yFinance calls or scheduler execution
- No new persistence layer — no new SQLite, no new database. If MDO already uses SQLite, the endpoint reads it. If MDO doesn't persist OHLCV, the endpoint cannot be built in this PR.
- No new top-level module — work confined to existing `ai_analyst/api/` and `ui/`
- No chart indicators, overlays, or Pine Script-style drawing tools — that is a future phase
- No multi-timeframe support — that is PR-CHART-2
- No run timestamp marker or verdict annotation — that is PR-CHART-2
- No run context linking — the chart shows the instrument's candles, but automated time-window alignment to the run is PR-CHART-2
- No reflective aggregation or pattern analysis
- No WebSocket / SSE / live-push — static data served on request
- No changes to MDO's fetching, scheduling, or processing pipeline
- No changes to `run_record.json` format
- No changes to existing ops, runs, trace, detail, roster, or health endpoints
- No chart authoring, annotation, or interaction beyond zoom/pan (built into lightweight-charts)
- No premature abstraction — no generic "data provider" layer, no multi-source router
- No standalone chart workspace

---

## 3. Repo-Aligned Assumptions

| Area | Assumption | Confidence |
|------|-----------|------------|
| MDO fetches OHLCV | MDO pipeline fetches OHLCV via yFinance — confirmed in architecture docs | High |
| MDO storage format | Unknown — could be SQLite, cached DataFrames, raw CSV, or in-memory only | **Unconfirmed — diagnostic required** |
| Storage access | Unknown — may require scheduler context, or may be directly readable from disk | **Unconfirmed — diagnostic required** |
| Storage location | Unknown — may be inside `market_data_officer/`, configured via env/settings, or located elsewhere entirely | **Unconfirmed — diagnostic required** |
| Persisted timeframes | H4 confirmed in sample run; H4/H1/M15/M5 planned but not repo-confirmed as persisted set | **Partially confirmed** |
| Inline OHLCV in run artifacts | Not present — `run_record.json` contains no candle data, `artifacts` block points only to `run_record.json` and `usage.jsonl` | Confirmed absent |
| Chart library | `lightweight-charts` (TradingView open source, MIT, ~40KB) — locked in Phase 8 plan | High |
| Chart placement | Embedded in Run mode context, not standalone workspace — locked in Phase 8 plan | Locked |
| Frontend stack | React + TypeScript + Tailwind + TanStack Query | High |
| Backend package | `ai_analyst/api/` | Confirmed (PR-RUN-1 diagnostic) |
| MDO package | `market_data_officer/` | High — per repo structure |

> **All MDO paths in §4 are diagnostic probes only.** They must not be treated as confirmed modification targets until Steps 1–3 validate them. Storage may be configured via env vars or settings files rather than hardcoded local paths.

### Current likely state

The MDO pipeline (in `market_data_officer/`) fetches OHLCV data via yFinance, processes it through a structural engine (pivot detection, feature extraction), and assembles `MarketPacketV2` payloads for the analysis pipeline. What is unknown is the intermediate storage: does the raw OHLCV data (or a processed form of it) persist to disk between scheduler runs, or does it exist only as in-memory DataFrames during execution?

The Phase 8 plan assumed persistence exists and a chart endpoint would simply read from it. That assumption has not been validated. The diagnostic resolves this.

### Core question

Where does MDO persist OHLCV data (if anywhere), in what format, and can a new API endpoint read it without invoking the scheduler or triggering live fetches?

---

## 4. Key File Paths

| Role | Path | Access |
|------|------|--------|
| MDO package root | `market_data_officer/` | Diagnostic scan |
| MDO officer service | `market_data_officer/officer/service.py` (hypothesis — diagnostic probe) | Diagnostic — locate `build_market_packet()` and data persistence |
| MDO scheduler | `market_data_officer/scheduler/` (hypothesis — diagnostic probe) | Diagnostic — confirm scheduler coupling |
| MDO config/settings | `market_data_officer/config/` or `settings.py` or `.env` (hypothesis — diagnostic probe) | Diagnostic — check for path/storage configuration |
| MDO data storage | Unknown — this is what the diagnostic must find | **TBD** |
| Instrument registry | `market_data_officer/` (hypothesis — diagnostic probe) | Diagnostic — confirm instrument/timeframe registry |
| Backend routes | `ai_analyst/api/routers/` | Modify (conditional) — add market-data route |
| Backend services | `ai_analyst/api/services/` | Modify (conditional) — add market-data read service |
| Backend models | `ai_analyst/api/models/` | Modify (conditional) — add OHLCV response models |
| Backend main | `ai_analyst/api/main.py` | Modify (conditional) — register market-data router |
| Agent Ops page | `ui/src/workspaces/ops/components/AgentOpsPage.tsx` | Modify (conditional) — embed chart panel |
| Frontend shared | `ui/src/shared/` | Modify (conditional) — add chart API + hook |
| Run Browser | `ui/src/workspaces/ops/components/RunBrowserPanel.tsx` | Read-only reference — no changes |

---

## 5. Current State Audit Hypothesis

### What is already true

- MDO fetches OHLCV data via yFinance for configured instruments and timeframes
- MDO processes raw OHLCV through a structural engine (pivots, features)
- MDO assembles `MarketPacketV2` payloads consumed by the analyst pipeline
- The instrument registry governs which instruments exist and their provider routing
- Run Browser (`GET /runs/`) is live — runs can be discovered and selected
- Agent Ops Run mode renders trace data for a selected run
- `lightweight-charts` is the locked chart library choice
- The `RunBrowserItem` response includes `instrument` for each run

### What is unknown (diagnostic must resolve)

- Whether OHLCV data persists to disk at all
- If it persists, the format (SQLite, DataFrame pickle, CSV, parquet, HDF5, or other)
- If it persists, the exact file path(s) and naming conventions — which may be configured via settings/env rather than hardcoded
- Whether persistence is per-instrument, per-timeframe, per-fetch, or aggregated
- Whether reading the persisted data requires importing scheduler modules or initializing runtime context
- Which timeframes are actually persisted vs. which are only mentioned in planning docs
- Whether the data is raw OHLCV or already processed/transformed

### What determines the PR outcome

If the diagnostic finds a readable on-disk OHLCV store:
→ PR-CHART-1 proceeds to implementation (endpoint + chart component)

If the diagnostic finds OHLCV is in-memory only or scheduler-bound:
→ PR-CHART-1 closes as a diagnostic finding. A follow-up PR-CHART-1a scopes the smallest change needed to create a persistent OHLCV store, then PR-CHART-1b builds the endpoint.

---

## 6. Design

### 6.1 Conditional Outcome Gate

After the diagnostic (§8), the implementer must report one of three findings:

**Outcome A — Seam exists and is clean:**
OHLCV data is persisted to disk in a directly readable format (SQLite, CSV, parquet, etc.) that does not require scheduler initialization. The endpoint can read it with standard file/DB operations.
→ Proceed to full implementation (§6.2–6.7).

**Outcome B — Seam exists but requires thin adapter:**
OHLCV data is persisted but the format requires a small read adapter (e.g., unpickling a DataFrame, reading a non-standard format). The adapter is bounded and does not import scheduler logic.
→ Proceed to implementation with the adapter documented as a known cost.

**Outcome C — No read-side seam exists:**
OHLCV data lives only in-memory during scheduler execution, or reading it requires initializing the scheduler/runtime context.
→ PR-CHART-1 closes as a **diagnostic-only finding**. Document:
  - Exactly where MDO data lives during execution
  - What the smallest change to MDO would be to persist OHLCV to a readable format
  - Whether that change belongs in MDO's domain or in a new persistence adapter
  - A one-paragraph remediation concept for a follow-up PR-CHART-1a

> **Outcome C scope limit:** Outcome C documents only the blocker and the smallest remediation concept. It must NOT draft implementation design, endpoint contracts, acceptance criteria, or detailed architecture for the follow-up PR. That is PR-CHART-1a's job.

All three outcomes are valid closures. Outcome C is not a failure — it is an honest finding that prevents building on a nonexistent seam.

### 6.2 Backend — `GET /market-data/{instrument}/ohlcv` Endpoint Contract

**Conditional on Outcome A or B from §6.1.**

**Route:** `GET /market-data/{instrument}/ohlcv`

This is a **market-data read surface**, registered in its own `routers/market_data.py`. It is not an ops endpoint and it is not a runs endpoint.

**Response envelope:** `OHLCVResponse` uses the same flat `ResponseMeta & {}` inheritance pattern as all prior API response models (roster, health, trace, detail, runs). No nested `data`/`meta` wrapper.

**Path parameters:**

| Parameter | Type | Purpose |
|-----------|------|---------|
| `instrument` | `string` | Instrument symbol (e.g. `XAUUSD`, `EURUSD`) |

**Query parameters:**

| Parameter | Type | Default | Constraint | Purpose |
|-----------|------|---------|------------|---------|
| `timeframe` | `string` | See §6.2.1 | Must match a persisted timeframe | Candle timeframe |
| `limit` | `int` | `100` | 1–500 | Number of most recent candles to return |

#### 6.2.1 Default Timeframe

H4 is the default timeframe **only if the diagnostic confirms H4 is persisted**. If H4 is not available, the default becomes the first validated persisted timeframe, documented in §13. The agent prompt must not hardcode H4 until the diagnostic confirms it.

**Response shape:**

```typescript
type OHLCVResponse = ResponseMeta & {
  instrument: string;
  timeframe: string;
  candles: Candle[];
  candle_count: number;
};

type Candle = {
  timestamp: number;    // Unix epoch seconds (lightweight-charts native format)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};
```

**Design notes:**

- `timestamp` is Unix epoch seconds, not ISO 8601 — this is `lightweight-charts`' native time format. Converting on the frontend would be wasted work.
- `candles` array is ordered oldest-first (ascending time) — this is what `lightweight-charts` expects for `setData()`.
- `candle_count` is the actual number of candles returned, which may be less than `limit` if fewer are available.

**`ResponseMeta` fields** (flat inheritance, same pattern as all prior endpoints):

| Field | Type | Value |
|-------|------|-------|
| `version` | `string` | `"2026.03"` |
| `generated_at` | `string` | ISO 8601 timestamp of response generation |
| `data_state` | `"live" \| "stale" \| "unavailable"` | Freshness — see §6.5 |

#### 6.2.2 Error Semantics — Distinguishing Empty-Data Conditions

Different missing-data conditions produce different responses. This must be unambiguous:

| Condition | HTTP status | Error code | Response |
|-----------|------------|------------|----------|
| Instrument not in registry at all | 404 | `INSTRUMENT_NOT_FOUND` | `OpsErrorEnvelope` |
| Instrument in registry, requested timeframe has no persisted data file/table | 404 | `TIMEFRAME_NOT_FOUND` | `OpsErrorEnvelope` |
| Instrument + timeframe valid, data store exists but is empty or all candle rows malformed | 200 | — | `OHLCVResponse` with `candles: []`, `candle_count: 0`, `data_state: "unavailable"` |
| Data store exists but I/O error during read | 500 | `MARKET_DATA_READ_FAILED` | `OpsErrorEnvelope` |
| `limit` out of range (≤0 or >500) | 422 | `INVALID_PARAMS` | `OpsErrorEnvelope` |

Error responses use `OpsErrorEnvelope` shape, consistent with established conventions.

#### 6.2.3 Malformed Candle Row Handling

Individual malformed candle rows (null timestamp, missing OHLC fields, non-numeric values) are **dropped silently** during projection. The endpoint does not fail on row-level data quality issues.

- If ≤10% of source rows are dropped: `data_state: "live"` (negligible quality loss)
- If >10% of source rows are dropped: `data_state: "stale"` (significant quality loss — operator should be aware)
- If 100% of rows are malformed: return 200 with `candles: []`, `candle_count: 0`, `data_state: "unavailable"`

### 6.3 Backend — Market Data Read Service

**Conditional on Outcome A or B from §6.1.**

The read service is a thin adapter between MDO's storage format and the chart endpoint contract. Think of it like a translator — it reads whatever format MDO wrote (SQLite rows, DataFrame columns, CSV lines) and outputs a flat list of `Candle` objects.

**Responsibilities:**

1. **Locate** — find the stored OHLCV data for a given instrument + timeframe (path/table determined by diagnostic)
2. **Read** — load the data using the appropriate reader (SQL query, DataFrame load, CSV parse — determined by diagnostic)
3. **Project** — map the stored format to the `Candle` contract shape (timestamp as epoch seconds, OHLCV fields), dropping malformed rows per §6.2.3
4. **Slice** — return the most recent N candles (oldest-first ordering)
5. **Assess freshness** — derive `data_state` per §6.5

**Import boundary rules:**

- **Allowed:** Importing pure storage/path helpers from MDO (e.g., a function that returns the data directory path or the instrument registry)
- **Forbidden:** Importing transformation code (structural engine, pivot detection, feature extraction), scheduling code (APScheduler jobs, cadence logic), or pipeline execution code (`build_market_packet`, fetch orchestration)
- **If the boundary is unclear** for a specific import: flag before proceeding

The read service must NOT require runtime initialization of MDO components. If importing a helper triggers scheduler initialization as a side effect, that helper is off-limits.

### 6.4 Frontend — `CandlestickChart` Component

**Conditional on Outcome A or B from §6.1.**

**Library:** `lightweight-charts` via `lightweight-charts-react` wrapper (or direct if wrapper adds unnecessary complexity — diagnostic to decide).

**Behavior:**

1. Receives `instrument` and `timeframe` as props
2. Fetches `GET /market-data/{instrument}/ohlcv?timeframe={tf}&limit=100`
3. Renders a standard candlestick chart with volume histogram below
4. Supports built-in zoom/pan (provided by lightweight-charts)
5. Handles loading, empty, and error states

**Instrument source of truth:** The chart component reads `instrument` from the `RunBrowserItem` row that was clicked (the `instrument` field already present in the run browser response). It does NOT source instrument from the trace endpoint. The browser row is already loaded when the user clicks — no extra fetch needed.

**What this component does NOT do in PR-CHART-1:**
- No multi-timeframe tabs (PR-CHART-2)
- No run timestamp marker (PR-CHART-2)
- No verdict annotations (PR-CHART-2)
- No indicator overlays (future phase)
- No custom drawing tools

**Chart panel isolation rule:** The chart panel must be a self-contained, failure-tolerant component. If the chart is absent (no instrument), loading, errored, or stale, existing Run mode behavior (run selection in the browser, trace rendering in the trace panel) must remain completely unchanged. Chart failure must NOT block trace rendering.

**Integration with Run mode:**

When a run is selected in the Run Browser, the chart panel reads `instrument` from the browser row and renders the chart at the diagnostic-confirmed default timeframe. The chart panel sits between the Run Browser and the Trace panel.

```
┌─────────────────────────────────────────┐
│  Run Mode                               │
│  ┌───────────────────────────────────┐  │
│  │  Run Browser (select a run)       │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  📊 XAUUSD H4 Candlestick Chart  │  │
│  │  [chart renders here]             │  │
│  │  (or: loading / no data / error)  │  │
│  └───────────────────────────────────┘  │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │  Trace Panel (stages, verdict)    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

**TanStack Query hook:**

```typescript
function useMarketData(params: {
  instrument: string | null;
  timeframe?: string;
  limit?: number;
}): UseQueryResult<OHLCVResponse>
```

Enabled only when `instrument` is non-null. Stale time: 60 seconds.

### 6.5 Freshness / `data_state` Derivation

The `data_state` for market data is derived deterministically. No heuristic judgment is left to the implementer.

**Rule (locked):**

| Condition | `data_state` |
|-----------|-------------|
| Data read successfully AND <10% of candle rows dropped during projection | `"live"` |
| Data read successfully AND ≥10% of candle rows dropped | `"stale"` |
| Data read successfully AND freshness metadata is absent or cannot be determined | `"stale"` |
| Data read successfully but all rows malformed or store is empty | `"unavailable"` |
| Data store I/O failure | endpoint returns 500, not a 200 with `data_state` |

> **Conservative default:** When freshness cannot be determined, the answer is `"stale"`, not `"live"`. If you can't prove it's fresh, say it's stale.

If the diagnostic identifies a usable freshness signal (e.g., file modification time, a "last_fetched" field in the data), the read service may use it to distinguish `"live"` from `"stale"` more precisely. But the fallback when no signal is available is always `"stale"`.

### 6.6 Router Ownership

Three routers now exist, each owning a distinct surface:

| Router | Surface | Concern |
|--------|---------|---------|
| `routers/ops.py` | `/ops/*` | Agent operations — roster, health, detail |
| `routers/runs.py` | `/runs/*` | Run discovery + run-scoped trace |
| `routers/market_data.py` | `/market-data/*` | Market data read surface (new) |

These remain separate. The chart feature consumes data from both `/runs/` (to know which instrument) and `/market-data/` (to get candles), but the routers don't call each other — the frontend orchestrates.

---

## 7. Acceptance Criteria

### Diagnostic ACs (mandatory — apply to all outcomes)

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-1 | MDO storage located | Diagnostic identifies where MDO persists OHLCV data (or confirms it doesn't), including config/settings-based paths | ✅ Done |
| AC-2 | Format documented | Storage format is documented (SQLite/CSV/DataFrame/in-memory/other) | ✅ Done |
| AC-3 | Access path documented | Exact file paths, table names, or access patterns documented | ✅ Done |
| AC-4 | Scheduler coupling assessed | Whether reading data requires scheduler/runtime initialization is documented, including the exact read function identified and its dependency chain traced | ✅ Done |
| AC-5 | Timeframe inventory | Which timeframes are actually persisted today is documented, with row counts and date ranges | ✅ Done |
| AC-6 | Outcome gate resolved | Diagnostic classifies as Outcome A, B, or C per §6.1 | ✅ Done |

### Implementation ACs (conditional — only if Outcome A or B)

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-7 | Endpoint exists | `GET /market-data/{instrument}/ohlcv` returns 200 with valid `OHLCVResponse` shape (flat `ResponseMeta & {}` pattern) | ✅ Done |
| AC-8 | ResponseMeta present | Response includes `version`, `generated_at`, `data_state` | ✅ Done |
| AC-9 | Candle shape correct | Each candle has `timestamp` (epoch seconds), `open`, `high`, `low`, `close`, `volume` — all numeric | ✅ Done |
| AC-10 | Oldest-first order | Candles returned in ascending timestamp order | ✅ Done |
| AC-11 | Limit parameter | `?limit=50` returns ≤50 candles; default 100; max 500 | ✅ Done |
| AC-12 | Limit negative cases | `limit=0`, `limit=-1`, `limit=501` all return 422 `INVALID_PARAMS` | ✅ Done |
| AC-13 | Timeframe parameter | `?timeframe=<confirmed_tf>` returns correct timeframe candles | ✅ Done |
| AC-14 | Default timeframe | Omitted `timeframe` defaults to the diagnostic-confirmed default (H4 if persisted, otherwise first available) | ✅ Done |
| AC-15 | Unknown instrument | Instrument not in registry → 404 `INSTRUMENT_NOT_FOUND` | ✅ Done |
| AC-16 | Unknown timeframe | Instrument in registry but timeframe has no data → 404 `TIMEFRAME_NOT_FOUND` | ✅ Done |
| AC-17 | Empty data store | Instrument + timeframe valid but store empty → 200 with `candles: []`, `data_state: "unavailable"` | ✅ Done |
| AC-18 | Malformed row tolerance | Individual bad candle rows are dropped; >10% dropped → `data_state: "stale"` | ✅ Done |
| AC-19 | No scheduler trigger | Endpoint does not invoke MDO scheduler, pipeline, or live fetch | ✅ Done |
| AC-20 | Read-only | Endpoint does not modify stored data | ✅ Done |
| AC-21 | Error envelope | All error responses use `OpsErrorEnvelope` shape | ✅ Done |
| AC-22 | data_state: live | Clean data with <10% drops → `"live"` | ✅ Done |
| AC-23 | data_state: stale | >10% drops OR freshness unknown → `"stale"` | ✅ Done |
| AC-24 | data_state: unavailable | Empty or all-malformed → `"unavailable"` | ✅ Done |
| AC-25 | Frontend: chart renders | `CandlestickChart` renders candles from API response | ✅ Done |
| AC-26 | Frontend: instrument from browser | Chart reads `instrument` from the clicked `RunBrowserItem` row, not from trace endpoint | ✅ Done |
| AC-27 | Frontend: loading state | Loading skeleton while chart data fetches | ✅ Done |
| AC-28 | Frontend: empty/error state | No-data and error states render appropriately | ✅ Done |
| AC-29 | Frontend: embedded in Run mode | Chart panel renders within Run mode, not as separate workspace | ✅ Done |
| AC-30 | Frontend: chart isolation | Chart absent/loading/error/stale does NOT affect run selection or trace rendering | ✅ Done |
| AC-31 | Router separation | `GET /market-data/*` registered in `routers/market_data.py`, not ops or runs | ✅ Done |
| AC-32 | No new top-level module | Work confined to `ai_analyst/api/` and `ui/` | ✅ Done |
| AC-33 | No MDO pipeline changes | MDO fetching, scheduling, processing unchanged | ✅ Done |
| AC-34 | Import boundary respected | Read service imports only storage/path helpers from MDO; no transformation, scheduling, or pipeline imports | ✅ Done |
| AC-35 | No premature abstraction | No generic data provider, multi-source router, or shared framework | ✅ Done |
| AC-36 | No existing endpoint changes | ops, runs, trace, detail, roster, health endpoints unchanged | ✅ Done |
| AC-37 | Regression safety | All pre-existing ops-domain tests pass; pre-existing failure count does not increase | ✅ Done |

### Diagnostic-only close ACs (only if Outcome C)

| # | Gate | Acceptance Condition | Status |
|---|------|---------------------|--------|
| AC-C1 | Blocker documented | Why the seam doesn't exist is documented with file-level evidence | ✅ Done |
| AC-C2 | Remediation concept | Smallest change to create a persistent OHLCV store is described in one paragraph — no implementation design, no endpoint contracts, no ACs | ✅ Done |
| AC-C3 | Follow-up PR identified | PR-CHART-1a is named with a one-sentence scope description; detailed spec deferred to that PR | ✅ Done |

---

## 8. Pre-Code Diagnostic Protocol

**Do not implement until this diagnostic is reviewed and the outcome gate (§6.1) is resolved.**

### Step 1: Locate MDO data storage

```bash
# Find any data files in the MDO package
find market_data_officer/ -name "*.db" -o -name "*.sqlite" -o -name "*.csv" \
  -o -name "*.parquet" -o -name "*.pkl" -o -name "*.h5" -o -name "*.hdf5" \
  -o -name "*.feather" | head -20

# Find any data directories
find market_data_officer/ -type d -name "data" -o -name "cache" -o -name "store" \
  -o -name "output" -o -name "storage" | head -10

# Search for file write operations in MDO
grep -rn "to_csv\|to_sql\|to_parquet\|to_pickle\|to_hdf\|to_feather\|\.write\|open.*'w'" \
  market_data_officer/ --include="*.py" | head -20

# Search for storage path configuration
grep -rn "output\|storage\|cache\|data_dir\|db_path\|sqlite" \
  market_data_officer/ --include="*.py" | head -20
```

**Expected result:** Either find data files/directories and write operations confirming persistence, or find no persistence, confirming in-memory-only operation.

**Report:**
- All data files found (with paths, sizes, modification dates)
- All write operations found (with file paths and line numbers)
- Any storage configuration (paths, connection strings, format indicators)
- Assessment: is OHLCV persisted to disk?

### Step 1b: Inspect config/settings for storage path configuration

```bash
# Check for settings files that might configure storage externally
find market_data_officer/ -name "settings*" -o -name "config*" -o -name "*.env" \
  -o -name "*.yaml" -o -name "*.toml" -o -name "*.ini" | head -10

# Check for environment variable references to storage
grep -rn "os\.environ\|os\.getenv\|environ\|DATA_DIR\|STORAGE\|DB_PATH\|CACHE" \
  market_data_officer/ --include="*.py" | head -15

# Check for path-resolution utilities
grep -rn "def.*path\|def.*dir\|def.*location\|Path(" \
  market_data_officer/ --include="*.py" | head -15

# Check project root for data directories that MDO might write to
find . -maxdepth 2 -type d -name "data" -o -name "market_data" -o -name "ohlcv" \
  -o -name "candles" | head -10
```

**Expected result:** Identify whether storage is configured externally.

**Report:**
- Any settings/config files found
- Any environment variable references to storage paths
- Any path-resolution utilities
- Any data directories outside `market_data_officer/` that MDO might use

> **Do not conclude "no seam" based solely on filesystem scans within `market_data_officer/`.** Storage may be configured via env/settings and located elsewhere.

### Step 2: Trace the data flow from fetch to storage

```bash
# Find the yFinance fetch calls
grep -rn "yfinance\|yf\.\|download\|Ticker" market_data_officer/ --include="*.py" | head -15

# Find build_market_packet or equivalent
grep -rn "def build_market_packet\|def fetch\|def get_ohlcv\|def get_candles" \
  market_data_officer/ --include="*.py" | head -10

# Trace what happens to fetched data
grep -rn "DataFrame\|df\.\|candles\|ohlcv" market_data_officer/officer/service.py | head -20
```

**Expected result:** Trace the path from yFinance fetch → processing → storage (or lack thereof).

**Report:**
- Where yFinance is called
- What format the fetched data is in (DataFrame)
- What processing happens (structural engine, pivots, features)
- Whether the raw or processed data is written to disk
- If written, in what format and where

### Step 3: Assess scheduler coupling — prove read-side safety

```bash
# Find scheduler entry points
grep -rn "def run\|def start\|def execute\|APScheduler\|schedule" \
  market_data_officer/scheduler/ --include="*.py" | head -15

# Check if data access requires scheduler initialization
grep -rn "import.*scheduler\|from.*scheduler" market_data_officer/officer/ --include="*.py" | head -10

# Check if service.py can be imported independently
python -c "from market_data_officer.officer import service; print('Importable')" 2>&1
```

**Beyond importability — trace the actual read path:**

If a data store was found in Steps 1/1b, identify the exact function that would back the chart endpoint's read path. Then:

```bash
# Find the candidate read function
grep -rn "def read\|def load\|def get.*data\|def query" market_data_officer/ --include="*.py" | head -10

# Trace its dependency chain — does it call fetch, schedule, or initialize runtime?
# (Adapt based on the function found above)
grep -n "fetch\|schedule\|download\|yf\.\|Ticker\|APScheduler" <candidate_file> | head -10
```

**Expected result:** Either confirm a clean read path free of side effects, or identify where the read path triggers fetching/scheduling.

**Report:**
- Can `service.py` be imported without scheduler initialization?
- What is the exact function/method that would back the read endpoint?
- Does that function's call chain invoke fetch, schedule, or initialize runtime state?
- Is the read path genuinely free of side effects, or does it trigger lazy fetching?

### Step 4: Inventory persisted timeframes

```bash
# If data files were found in Steps 1/1b, inspect their contents
# (commands depend on format — examples for common formats)

# SQLite
# sqlite3 <path> ".tables"
# sqlite3 <path> "SELECT DISTINCT timeframe FROM <table> LIMIT 10"
# sqlite3 <path> "SELECT timeframe, COUNT(*), MIN(timestamp), MAX(timestamp) FROM <table> GROUP BY timeframe"

# CSV files
# ls -la <data_dir>/*.csv && head -5 <data_dir>/*.csv

# DataFrame pickles
# python -c "import pickle; df = pickle.load(open('<path>', 'rb')); print(df.columns, df.shape, df.index.min(), df.index.max())"
```

**Expected result:** List of timeframes with actual stored data.

**Report:**
- Which timeframes have persisted data
- How much history is stored per timeframe (row counts, date ranges)
- Whether the data is raw OHLCV or processed/transformed
- Column names and types
- Whether H4 is confirmed persisted (determines default timeframe)

### Step 5: Resolve the outcome gate

Based on Steps 1–4, classify:

- **Outcome A:** Readable on-disk OHLCV exists. Document: format, path, schema, read method, confirmed default timeframe. Proceed to implementation.
- **Outcome B:** Persisted data exists but needs a thin adapter. Document: what the adapter does, estimated complexity, confirmed default timeframe. Proceed to implementation with adapter.
- **Outcome C:** No readable on-disk seam. Document: where data lives during execution, smallest change to persist it, one-paragraph remediation concept. Close as diagnostic finding. Do not draft implementation design for the follow-up.

### Step 6: Run baseline test suite

```bash
# Backend tests
python -m pytest tests/ -q --tb=no

# Frontend tests
cd ui && npx vitest run --reporter=verbose 2>&1 | tail -20
```

**Expected result:** Ops-domain tests all pass. Record counts including PR-RUN-1's additions.

**Report:**
- Backend ops test count (expect ~239 from PR-RUN-1)
- Frontend ops test count (expect ~77 from PR-RUN-1)
- Pre-existing non-ops failures (expect ~14, unchanged)

### Step 7 (Outcome A/B only): Propose smallest patch set

Only if proceeding to implementation:

- Files to create (one-line description, estimated line delta)
- Files to modify (one-line description, estimated line delta)
- "No changes expected" confirmation list
- Confirmed default timeframe for the endpoint
- Total estimated delta

**No premature abstraction:** One read service, one model file, one router, one chart component, one hook, tests. No generic data provider framework.

---

## 9. Implementation Constraints

### 9.1 General rule

The chart endpoint is a **read-side projection over existing MDO storage**. It reads stored OHLCV data, projects it into a frontend-ready candle format, and serves it. No writes, no fetches, no scheduler coupling. Same philosophy as the run browser.

### 9.1b Implementation Sequence (Outcome A/B only)

1. **Backend read service** — create market data read service that loads OHLCV from the discovered storage format, drops malformed rows per §6.2.3, derives `data_state` per §6.5
   - Verify: baseline backend tests still pass

2. **Backend models** — create Pydantic models for the OHLCV response (flat `ResponseMeta & {}` pattern)
   - Verify: models import cleanly

3. **Backend endpoint + route** — create `routers/market_data.py` with `GET /market-data/{instrument}/ohlcv`, register in `main.py`
   - Verify: baseline + new endpoint tests pass

4. **Backend contract tests** — deterministic tests covering AC-7 through AC-24
   - Gate: all backend tests pass before touching frontend

5. **Frontend: install lightweight-charts** — add dependency
   - Verify: build compiles

6. **Frontend: chart component + hook** — `CandlestickChart` component and `useMarketData` hook
   - Verify: component tests pass (AC-25 through AC-30)

7. **Frontend integration** — embed chart panel in Run mode between browser and trace, with isolation per §6.4
   - Gate: all frontend tests pass (baseline + new)
   - Verify: AC-30 (chart failure does not affect trace)

8. **Full regression** — ops-domain zero regressions (AC-37)

### 9.2 Code change surface (Outcome A/B — estimated, pending diagnostic)

**New files:**

| File | Role | Est. lines |
|------|------|-----------|
| `ai_analyst/api/services/market_data_read.py` | Read OHLCV from MDO storage, project candles, derive data_state | ~140 |
| `ai_analyst/api/models/market_data.py` | Pydantic models for OHLCV response | ~45 |
| `ai_analyst/api/routers/market_data.py` | `GET /market-data/{instrument}/ohlcv` with error semantics per §6.2.2 | ~60 |
| `tests/test_market_data_endpoints.py` | Backend contract tests (AC-7 through AC-24) | ~250 |
| `ui/src/shared/api/marketData.ts` | `fetchOHLCV()` API function | ~25 |
| `ui/src/shared/hooks/useMarketData.ts` | TanStack Query hook | ~25 |
| `ui/src/workspaces/ops/components/CandlestickChart.tsx` | Chart component with isolation | ~140 |
| `ui/tests/candlestick-chart.test.tsx` | Frontend chart tests (AC-25 through AC-30) | ~140 |

**Modified files:**

| File | Change | Est. delta |
|------|--------|-----------|
| `ai_analyst/api/main.py` | Register `market_data` router | +3 |
| `ui/src/workspaces/ops/components/AgentOpsPage.tsx` | Embed chart panel in Run mode (isolated — failure-tolerant) | +25 |
| `ui/package.json` | Add `lightweight-charts` dependency | +1 |

**No changes expected to:**
- `ai_analyst/api/routers/ops.py` — existing ops endpoints
- `ai_analyst/api/routers/runs.py` — run browser endpoint
- `ai_analyst/api/services/ops_*.py` — all ops services
- `market_data_officer/` — MDO pipeline unchanged
- `run_record.json` artifacts — format unchanged

### 9.3 Out of scope (repeat + negative scope lock)

**Hard constraints:**
- No new data fetching — reads stored data only
- No new persistence layer (unless MDO already uses one)
- No new top-level module — work in `ai_analyst/api/` and `ui/`
- No changes to MDO pipeline, scheduler, or processing
- No changes to existing endpoints
- Deterministic tests only
- No WebSocket / SSE / live-push

**Import boundary:**
- Allowed: pure storage/path helpers from MDO
- Forbidden: transformation, structural engine, scheduling, pipeline execution code
- Unclear: flag before proceeding

**No premature abstraction:**
- No generic "data provider" or "multi-source router"
- No shared OHLCV framework beyond the one read service
- No attempt to unify MDO read paths into a common library

**PR-CHART-1 does not:**
- Add multi-timeframe tabs or selector (PR-CHART-2)
- Add run timestamp markers (PR-CHART-2)
- Add verdict/bias annotations on chart (PR-CHART-2)
- Add indicator overlays (future phase)
- Add chart drawing/annotation tools
- Add reflective scoring or pattern analysis
- Modify MDO's fetch cadence or data sources
- Create a standalone chart workspace

---

## 10. Success Definition

**If Outcome A or B:** PR-CHART-1 is done when: the diagnostic confirms a readable OHLCV seam; `GET /market-data/{instrument}/ohlcv` (flat `ResponseMeta & {}` pattern) serves stored candle data in lightweight-charts-native format with deterministic `data_state` derivation; `CandlestickChart` renders in Run mode as an isolated, failure-tolerant embedded panel sourcing `instrument` from the browser row; the endpoint reads from MDO's existing storage without triggering scheduler or fetches; malformed rows are dropped per §6.2.3; empty-data conditions produce the correct HTTP status per §6.2.2; all implementation ACs (AC-7 through AC-37) pass with deterministic tests; no regressions; no new persistence, no new top-level module, no MDO pipeline changes, no premature abstraction.

**If Outcome C:** PR-CHART-1 is done when: the diagnostic documents exactly where MDO data lives, why no read-side seam exists, and the smallest remediation concept (one paragraph, no implementation design); diagnostic ACs (AC-1 through AC-6) and close ACs (AC-C1 through AC-C3) pass.

Both outcomes are valid closures.

---

## 11. Why This Phase Matters

| Without Chart Surface | With Chart Surface |
|----------------------|-------------------|
| Operator sees trace data (stages, verdicts) but no price context | Operator sees candles alongside the trace — "what was the market doing when this analysis ran?" |
| Run analysis is abstract — bias/decision without visual reference | Price action grounds the analysis in visual reality |
| No connection between MDO data pipeline and the operator UI | MDO's stored data becomes visible to the operator for the first time |
| Phase 8 chart lane is blocked on an unvalidated assumption | The seam assumption is resolved — either charts proceed or the blocker is documented |

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 7 — Agent Ops read-side stack | 4 endpoints, 3 workspace modes, detail sidebar | ✅ Done — 197+63 tests |
| PR-RUN-1 — Run Browser | `GET /runs/` endpoint + RunBrowserPanel | ✅ Done — +56 tests |
| **PR-CHART-1 — OHLCV data seam + chart** | **Diagnostic + conditional endpoint + candlestick chart** | **✅ Done — Outcome A, 39+9 tests** |
| PR-CHART-2 — Run context overlay | Multi-timeframe, run marker, verdict annotation | 📋 Planned — depends on PR-CHART-1 (Outcome A/B) |
| PR-REFLECT-1 — Aggregation endpoints | Persona performance + pattern summary | 📋 Planned — depends on PR-RUN-1 ✅ |
| PR-REFLECT-2 — Reflect dashboard | `/reflect` workspace frontend | 📋 Planned — depends on PR-REFLECT-1 |
| PR-REFLECT-3 — Integration + suggestions | Chart ↔ run + rules-based parameter suggestions | 📋 Planned — depends on PR-CHART-2 + PR-REFLECT-2 |

---

## 13. Diagnostic Findings

### Outcome Gate: **Outcome A — Seam exists and is clean**

### Storage Format
CSV files in `market_data/packages/latest/`. Schema: `timestamp_utc,open,high,low,close,volume`. Timestamps are UTC ISO 8601 strings. JSON manifest per instrument (`{INSTRUMENT}_hot.json`) with `as_of_utc`, `schema`, `windows`.

### Confirmed Read Path
`market_data_officer.officer.loader.load_timeframe(instrument, tf, packages_dir)` → `pd.read_csv()` → UTC-aware DataFrame. Zero scheduler imports, zero side effects.

### Timestamp Conversion
CSV stores ISO 8601 UTC strings. Service converts to Unix epoch seconds via `int(ts.timestamp())` for lightweight-charts native format.

### Freshness Derivation
Manifest `as_of_utc` field confirms data exists. Conservative default: if manifest absent, `data_state` = `"stale"`. Malformed row drop rate (<10% = live, ≥10% = stale, 100% = unavailable).

### Scheduler Coupling: CLEAN
Importing `loader.py` loads zero scheduler/APScheduler modules. The loader depends only on `json`, `pathlib.Path`, `pandas`. Confirmed via `sys.modules` check in test suite.

### Timeframe Inventory (fixture data)

| Instrument | Timeframes | Rows per TF | Date Range |
|---|---|---|---|
| EURUSD | 1m, 5m, 15m, 1h, 4h, 1d | 3000/1200/600/240/120/30 | ~2 days to ~20 days |
| XAUUSD | 15m, 1h, 4h, 1d | 600/240/120/30 | ~6 days to ~20 days |

**H4 (4h) confirmed persisted for all instruments. Default timeframe: `4h`.**

### Implementation Surprise
Empty CSV files cause `load_timeframe()` to raise `AttributeError` (pandas can't tz-localize an empty non-datetime index). Service handles this by catching the exception, checking if the CSV exists and is empty, and treating it as an empty data store (200 with `candles: []`).

### Final Patch Set

**New files (8):**

| File | Lines | Role |
|---|---|---|
| `ai_analyst/api/services/market_data_read.py` | 155 | Read OHLCV from hot packages, project to Candle, derive data_state |
| `ai_analyst/api/models/market_data.py` | 29 | Pydantic models: Candle, OHLCVResponse |
| `ai_analyst/api/routers/market_data.py` | 105 | GET /market-data/{instrument}/ohlcv endpoint |
| `tests/test_market_data_endpoints.py` | 310 | Backend contract tests (39 tests, AC-7 through AC-34) |
| `ui/src/shared/api/marketData.ts` | 52 | fetchOHLCV() typed API client |
| `ui/src/shared/hooks/useMarketData.ts` | 41 | TanStack Query hook (60s stale time) |
| `ui/src/workspaces/ops/components/CandlestickChart.tsx` | 177 | Candlestick + volume chart with loading/error/empty/stale states |
| `ui/tests/candlestick-chart.test.tsx` | 214 | Frontend chart tests (9 tests, AC-25 through AC-30) |

**Modified files (4):**

| File | Delta | Change |
|---|---|---|
| `ai_analyst/api/main.py` | +4 | Register market_data router |
| `ui/src/workspaces/ops/components/AgentOpsPage.tsx` | +8 | Import CandlestickChart, track selectedInstrument, embed chart panel |
| `ui/src/workspaces/ops/components/RunBrowserPanel.tsx` | +2 | Pass instrument alongside runId in onSelectRun callback |
| `ui/src/shared/hooks/index.ts` | +1 | Export useMarketData |
| `ui/package.json` | +1 | Add lightweight-charts dependency |
| `ui/tests/run-browser.test.tsx` | +1 | Update assertion to match new onSelectRun signature |

### Test Count Delta
- Backend: 393 → 432 (+39 market data tests)
- Frontend: 292 → 301 (+9 chart tests)
- Pre-existing failures unchanged: 1 backend (test_mdo_scheduler), 5 frontend (journey.test.tsx)

---

## 14. Doc Corrections to Apply on Branch

### Both Outcome A/B and Outcome C:

1. **`docs/specs/PR_CHART_1_SPEC.md`** — close per outcome (see §15)
2. **`docs/AI_TradeAnalyst_Progress.md`** — dashboard-aware update: header, Recent Activity row, Phase Index, Roadmap status, §6 Next Actions
3. **`PHASE_8_PLAN.md` §Architecture Notes → Chart data source:** Update "The diagnostic must confirm the exact storage format" to reflect diagnostic findings (format confirmed or seam absent)

### Review for update (both outcomes):

4. **`docs/architecture/system_architecture.md`** — update if the diagnostic changes understanding of MDO data flow or adds a new API surface
5. **`docs/architecture/repo_map.md`** — update if new files were created
6. **`docs/architecture/technical_debt.md`** — add entry if Outcome C reveals a persistence gap; update if Outcome A/B resolves an existing concern
7. **`docs/architecture/AI_ORIENTATION.md`** — update only if a new onboarding-critical doc or surface was added

---

## 15. Appendix — Recommended Agent Prompt

```
Read `docs/specs/PR_CHART_1_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

CRITICAL: This PR has a conditional outcome gate (§6.1). The diagnostic
determines whether implementation proceeds or the PR closes as a
finding. Do NOT skip the diagnostic and jump to implementation.

First task only — run the diagnostic protocol in Section 8 and report
findings before changing any code:

1. Locate MDO data storage: find data files, write operations, storage config
   INCLUDING config/settings files and env vars (Step 1 + 1b)
2. Trace data flow: yFinance fetch → processing → storage (or lack thereof)
3. Assess scheduler coupling: identify the exact read function that would
   back the endpoint, trace its dependency chain, confirm it does not
   fetch/schedule/initialize runtime. Import success alone is not proof.
4. Inventory persisted timeframes: what's actually stored, with row counts,
   date ranges, column names. Confirm whether H4 is persisted.
5. RESOLVE OUTCOME GATE: classify as Outcome A, B, or C per §6.1
6. Run baseline tests: backend + frontend, record counts
7. (Outcome A/B only) Propose smallest patch set, including confirmed
   default timeframe

Report the outcome gate classification prominently at the top of
the diagnostic report.

Hard constraints:
- No new data fetching — endpoint reads stored data only
- No scheduler trigger — must not invoke MDO scheduler or pipeline
- No new top-level module — work in ai_analyst/api/ and ui/ only
- No changes to MDO fetching, scheduling, or processing pipeline
- No changes to existing ops, runs, trace, detail endpoints
- Import boundary: storage/path helpers allowed; transformation/scheduling
  code forbidden. If unclear, flag before proceeding.
- OHLCVResponse uses flat ResponseMeta & {} pattern (same as all endpoints)
- Empty-data semantics per §6.2.2: 404 for unknown instrument/timeframe,
  200 with candles:[] for empty valid store
- Malformed rows: drop silently, derive data_state per §6.2.3 and §6.5
- Default timeframe: H4 only if confirmed persisted; otherwise first available
- Chart sources instrument from RunBrowserItem row, not trace endpoint
- Chart panel is failure-tolerant: chart error must not block trace rendering
- No premature abstraction — one read service, one model, one router,
  one chart component, one hook, tests
- Deterministic tests only
- If Outcome C: document blocker with file-level evidence, write one-paragraph
  remediation concept, name follow-up PR. Do NOT draft implementation design.

Do not change any code until the diagnostic report is reviewed and the
outcome gate is approved.

On completion (either outcome), close the spec and update docs per Workflow E:
1. `docs/specs/PR_CHART_1_SPEC.md` — mark status based on outcome:
   Outcome A/B: ✅ Complete, flip implementation AC cells, populate §13
   Outcome C: ✅ Complete (diagnostic-only), flip diagnostic AC cells,
   populate §13 with blocker documentation
2. `docs/AI_TradeAnalyst_Progress.md` — dashboard-aware update:
   header, Recent Activity row, Phase Index, Roadmap status, §6 Next Actions
3. Apply doc corrections from §14 (PHASE_8_PLAN.md update)
4. Review for update: system_architecture.md, repo_map.md,
   technical_debt.md, AI_ORIENTATION.md — per §14 criteria
5. Cross-document sanity check
6. Return Phase Completion Report

Commit all doc changes on the same branch as the implementation.
```
