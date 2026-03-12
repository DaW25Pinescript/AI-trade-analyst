# UI Phase 1 — Backend Capability Audit (Repo-Grounded)

## 1) Summary

This audit maps the **actual** backend capabilities in `ai_analyst/api/` against the current frontend surfaces in `app/`.

High-level findings:
- The backend exposes a broad API surface (analysis, streaming, triage/journey, feeder ingest/health, usage, metrics, analytics export/dashboard, backtest, e2e, plugins), but the UI currently consumes only a subset.
- There are effectively **two frontend surfaces**:
  - a legacy workflow UI (`app/scripts/*`) that calls `/health`, `/analyse`, `/runs/{run_id}/usage`, `/feeder/*`.
  - a Journey UI (`app/lib/*`, `app/pages/*`) that calls `/watchlist/triage`, `/triage`, `/journey/*`, `/journal/decisions`, `/review/records`.
- The generated OpenAPI file in `docs/architecture/openapi.json` is stale and only documents `/health` and `/analyse`; it does not reflect the live route set.
- Long-running analysis is synchronous for `/analyse` (single response after graph completion), and streaming via SSE exists at `/analyse/stream` but is not currently used by the frontend.

---

## 2) Files reviewed

Backend/API contracts and lifecycle:
- `ai_analyst/api/main.py`
- `ai_analyst/api/routers/journey.py`
- `ai_analyst/models/ground_truth.py`
- `ai_analyst/models/arbiter_output.py`
- `ai_analyst/core/progress_store.py`
- `ai_analyst/core/run_paths.py`
- `ai_analyst/core/run_state_manager.py`

Frontend usage:
- `app/lib/services.js`
- `app/lib/adapters.js`
- `app/journey.js`
- `app/pages/DashboardPage.js`
- `app/pages/JourneyPage.js`
- `app/scripts/api_bridge.js`
- `app/scripts/main.js`
- `app/scripts/state/macro_state.js`

OpenAPI/documentation baseline:
- `docs/architecture/openapi.json`

---

## 3) Endpoint and schema inventory

### 3.1 Contract source reliability

- **Declared/generated OpenAPI**: `docs/architecture/openapi.json` contains only `GET /health` and `POST /analyse` (version `2.0.0`).
- **Actual route source of truth**: `ai_analyst/api/main.py` + `ai_analyst/api/routers/journey.py`.
- Therefore this inventory is based on Python route declarations and response code paths, with OpenAPI used only as limited validation for two routes.

### 3.2 Endpoint inventory (UI-relevant and adjacent)

> Legend for maturity: `active-used`, `active-unused`, `legacy`, `internal/non-UI`, `ambiguous`.

| Path | Method | Purpose | Request (key fields) | Response (key shape) | Error shape | Mode | Likely UI consumer | Maturity |
|---|---|---|---|---|---|---|---|---|
| `/health` | GET | API liveness/version | none | `{status, version}` | default FastAPI detail | synchronous | Legacy workflow UI bridge health check | active-used |
| `/analyse` | POST (multipart/form-data) | Main multi-analyst run + verdict generation | instrument, session, timeframes (JSON string), risk fields, context fields, lens toggles, chart uploads, optional overlay + claims, optional source_ticket_id, optional enable_deliberation, triage/smoke mode flags | `AnalysisResponse`: `{verdict: FinalVerdict, ticket_draft, run_id, source_ticket_id, usage_summary}` | Mostly `HTTPException(detail=...)` with mixed detail types (string/object), incl. 422/429/500/503/504 | synchronous (long-running) | Legacy workflow UI “Run AI analysis” | active-used |
| `/analyse/stream` | POST (multipart/form-data) | Streaming analysis progress via SSE | Same core form fields as `/analyse` | SSE events: `analyst_done`, `heartbeat`, `verdict`, `error` | Streamed error events in-band | streaming (SSE) | Potential live-progress analysis workspace | active-unused |
| `/runs/{run_id}/usage` | GET | Usage/cost token summary for run | path `run_id` | `{run_id, usage_summary}` | fallback empty usage on load failure | synchronous | Legacy workflow UI usage refresh after analysis | active-used |
| `/feeder/ingest` | POST (JSON) | Ingest feeder payload and cache macro context in app state | `FeederIngestPayload` (contract_version, generated_at, instrument_context, status, events, etc.) | `{status:"ok", macro_context, ingested_at}` | 422 (schema/validation), 503 (package unavailable), 500 | synchronous | Macro tooling / operator controls | active-used (bridge exposed) |
| `/feeder/health` | GET | Feeder staleness and last ingest metadata | none | `{status, ingested_at, age_seconds, stale, source_health, regime, vol_bias, confidence,...}` | default detail | synchronous | Macro/ops status widget | active-used (bridge exposed) |
| `/metrics` | GET | Aggregated pipeline metrics snapshot | none | `{status, server_started_at, metrics}` | default detail | synchronous | Operator dashboard workspace | active-unused |
| `/dashboard` | GET | Server-rendered operator health dashboard HTML | none | HTML page | n/a (HTML endpoint) | synchronous | Operator dashboard link/embed | active-unused |
| `/analytics/csv` | GET | Export historical run analytics as CSV | optional query not used | CSV streaming attachment | default detail | synchronous download | Export workspace | active-unused |
| `/analytics/dashboard` | GET | Server-rendered advanced analytics HTML | none | HTML page | n/a | synchronous | Analytics workspace | active-unused |
| `/backtest` | GET | Backtest report from historical outcomes | optional query: instrument, regime, min_confidence | `{status, backtest:{...}}` | default detail | synchronous | Quant/research workspace | active-unused |
| `/e2e` | GET | End-to-end validation checks | none | `{status, total_checks, passed, failed, duration_ms, checks[]}` | default detail | synchronous | Diagnostics workspace | active-unused |
| `/plugins` | GET | Registered persona/data-source/hook catalog | none | `{status, total_plugins, personas[], data_sources[], hooks[]}` | default detail | synchronous | Config/introspection workspace | active-unused |
| `/watchlist/triage` | GET | Read latest per-symbol triage artifacts from disk | none | `{data_state, generated_at, items[]}` | graceful empty/unavailable | synchronous | Journey Dashboard page | active-used |
| `/triage` | POST | Trigger batch triage (loopback calls into `/analyse`) and artifact writes | JSON body optional `symbols` | `{status, artifacts_written, symbols_processed, output_dir}` | 500 with `{message, partial}` when all fail | synchronous (multi-call, can be long) | Journey Dashboard “Run Triage” | active-used |
| `/triage/smoke` | POST | Diagnostic probe of triage→analyse chain | none | diagnostic JSON (`loopback_hop_succeeded`, `llm_env_key_present`, etc.) | in-body diagnostic error fields | synchronous | Engineering diagnostics only | internal/non-UI |
| `/journey/{asset}/bootstrap` | GET | Load bootstrap data for staged journey | path `asset` | `{data_state, instrument, generated_at, structure_digest, analyst_verdict, arbiter_decision, explanation, reasoning_summary}` | graceful unavailable payload | synchronous | Journey page initial load | active-used |
| `/journey/draft` | POST | Save journey draft snapshot | JSON body (free-form), optional journey_id | `{success, journey_id, saved_at, path}` | 400/500 with `{success:false,error}` | synchronous | Journey draft save action | active-used |
| `/journey/decision` | POST | Save immutable decision snapshot | JSON body requiring `snapshot_id` | `{success, snapshot_id, saved_at, path}` | 400 missing/invalid, 409 duplicate immutable, 500 write error | synchronous | Journey decision freeze action | active-used |
| `/journey/result` | POST | Save execution/result snapshot | JSON body requiring `snapshot_id` | `{success, snapshot_id, saved_at, path}` | 400/500 `{success:false,error}` | synchronous | Journey result capture | active-used |
| `/journal/decisions` | GET | List decision summaries | none | `{records:[{snapshot_id,instrument,saved_at,journey_status,verdict,user_decision}]}` | graceful empty | synchronous | Journal page | active-used |
| `/review/records` | GET | List decisions with result linkage | none | `{records:[...,has_result]}` | graceful empty | synchronous | Review page | active-used |

### 3.3 Key models used in UI-facing contracts

- `FinalVerdict` includes directional bias, decision enum, approved setups, no-trade conditions, confidence, agreement %, risk override, arbiter notes, and audit log metadata. This is the core analysis entity surfaced to UI.
- `GroundTruthPacket` validates chart/evidence architecture, risk constraints, context, and triage mode. `/analyse` and `/analyse/stream` form fields are transformed into this model.
- `AnalysisResponse` wraps `FinalVerdict` with `ticket_draft`, `run_id`, `source_ticket_id`, and `usage_summary`.

### 3.4 Standardized error shape status

Error envelopes are **not globally standardized**:
- Some endpoints use `HTTPException(detail="...")` (string detail).
- Some use structured detail objects (`{"message":..., "code":...}` or with `request_id`/`run_id`).
- Journey persistence endpoints return `{success:false,error:"..."}` with non-2xx.
- SSE endpoint emits `{"type":"error", ...}` as stream events.

Inference: UI contract docs should document **per-endpoint error shape**, not a single global envelope.

---

## 4) Pipeline/workflow map

### 4.1 Analyse flow (`POST /analyse`)

Trigger:
- Legacy UI invokes `analyseViaBridge()` from `app/scripts/main.js`.

Main steps (repo-grounded):
1. API key dependency + rate limiting.
2. Parse JSON-like form fields (`timeframes`, `no_trade_windows`, `open_positions`, `overlay_indicator_claims`).
3. Sanitise instrument/session/context fields.
4. Read chart uploads with size+magic checks.
5. Build `GroundTruthPacket` (or chartless in triage mode).
6. Build graph + invoke pipeline (timeout-guarded).
7. Extract `final_verdict`, build `ticket_draft`, load usage summary.
8. Persist dev diagnostics optionally.
9. Return `AnalysisResponse` JSON.

User-visible outputs:
- Final verdict card, ticket prefill, run_id, usage summary.

Delivery behavior:
- Immediate response only at completion (no polling API exposed for run status).

### 4.2 Streaming analyse flow (`POST /analyse/stream`)

Trigger:
- Not currently wired in frontend.

Main steps:
- Same validation/build path as `/analyse`, but registers progress queue and streams SSE events until final verdict/error.

User-visible outputs:
- Potential analyst-by-analyst progress, heartbeat, final verdict, in-stream error.

Delivery behavior:
- Streaming (SSE), no explicit resume protocol.

### 4.3 Triage flow (`POST /triage` + `GET /watchlist/triage`)

Trigger:
- Journey Dashboard “Run Triage”.

Main steps:
1. `/triage` loops symbols and calls loopback `/analyse` in `triage_mode=true`.
2. Normalises and writes `multi_analyst_output_{symbol}_{ts}.json` to disk.
3. `/watchlist/triage` reads latest files, derives status/bias/confidence fields, and returns list with `data_state` freshness.

User-visible outputs:
- Ranked triage cards and status banners (`live/stale/unavailable/demo` fallback in UI).

Delivery behavior:
- Trigger call is synchronous; board refresh is explicit subsequent GET.

### 4.4 Journey bootstrap + decision capture flow

Trigger:
- Entering `#/journey/:asset`, plus Save actions.

Main steps:
1. Bootstrap loads multi-analyst output (+ optional explainability file).
2. UI adapts to staged journey state.
3. Save draft -> `/journey/draft`.
4. Freeze decision -> `/journey/decision` (immutable on snapshot_id).
5. Save outcome -> `/journey/result`.
6. Journal and review lists read from decision/result directories.

User-visible outputs:
- Prefilled stage data, persisted draft/decision/result records, journal/review tables.

Delivery behavior:
- Synchronous request/response per action.

### 4.5 Feeder ingest/health flow

Trigger:
- Legacy bridge helpers or external producer.

Main steps:
1. Validate feeder payload schema.
2. Convert into macro context (thread offload).
3. Cache context/meta timestamps in `app.state`.
4. `/feeder/health` reports freshness and source metadata.

User-visible outputs:
- Feeder status and macro context availability for analysis context.

Delivery behavior:
- Synchronous ingestion and health reads.

### 4.6 Observability/analytics/diagnostics flows

Supported backend-only flows:
- `/metrics` JSON snapshot.
- `/dashboard` operator HTML.
- `/analytics/csv` export stream.
- `/analytics/dashboard` HTML analytics.
- `/backtest`, `/e2e`, `/plugins` JSON diagnostics/introspection.

Current `/app` usage:
- No direct consumer found in current UI code.

---

## 5) Artifact inventory

| Artifact | What it is | Origin | Availability | Surfaced by current UI? | Workspace relevance |
|---|---|---|---|---|---|
| `run_id` | Unique analysis run identity | `GroundTruthPacket` default UUID; returned by `/analyse` | On analysis completion | Yes (legacy workflow) | Run detail, traceability |
| `final_verdict.json` | Persisted verdict payload per run | Pipeline run dir (`output/runs/{run_id}`) | After run complete | Indirectly (via API response), not browsable | Run detail / artifact inspector |
| `usage_summary` | Token/cost/call summary | usage meter files under run dir; `/runs/{run_id}/usage` | After usage logs written | Yes (legacy workflow refresh) | Cost/usage panel |
| `ticket_draft` | Prefill object for ticket form | built in `/analyse` response | Immediate in response | Yes | Ticket workspace |
| `dev_diagnostics.json` / `_dev_diagnostics.jsonl` | Request lifecycle diagnostics (dev gated) | `/analyse` and `/analyse/stream` tracing | During/after request when env enabled | No | Diagnostics workspace |
| `state.json` | Run state persistence for resumability (backend) | run_state_manager | During run transitions | No direct endpoint | Future run history/resume |
| `multi_analyst_output_*.json` | Triage records per symbol/time | `/triage` write | After triage | Yes (`/watchlist/triage`) | Triage dashboard |
| `{asset}_multi_analyst_output.json` + explainability | Bootstrap payload for journey | analyst output producer | Pre-existing files | Yes (`/journey/{asset}/bootstrap`) | Journey stage prefill |
| `app/data/journeys/drafts/*.json` | Draft journey snapshots | `/journey/draft` | On save | Partially (save confirmation) | Journey drafting |
| `app/data/journeys/decisions/*.json` | Immutable frozen decision snapshots | `/journey/decision` | On save | Yes via journal/review lists | Journal/review |
| `app/data/journeys/results/*.json` | Outcome/result snapshots | `/journey/result` | On save | Yes indirectly (`has_result`) | Review/performance |
| CSV analytics export stream | Consolidated run+usage+AAR export | `/analytics/csv` | On request | No | Export workspace |
| Operator/analytics HTML | Server-rendered observability dashboards | `/dashboard`, `/analytics/dashboard` | On request | No | Ops/analytics |

---

## 6) Current UI usage summary

### 6.1 Endpoints currently used by `/app`

Journey UI (`app/lib/services.js`):
- GET `/watchlist/triage`
- POST `/triage`
- GET `/journey/{asset}/bootstrap`
- POST `/journey/draft`
- POST `/journey/decision`
- POST `/journey/result`
- GET `/journal/decisions`
- GET `/review/records`

Legacy workflow UI (`app/scripts/api_bridge.js`, `app/scripts/main.js`):
- GET `/health`
- POST `/analyse`
- GET `/runs/{run_id}/usage`
- POST `/feeder/ingest`
- GET `/feeder/health`

### 6.2 Workflows exposed today

Exposed:
- Triage board + run triage trigger.
- Asset journey bootstrap and staged decision capture.
- Journal and review list surfaces.
- Single-run analysis and verdict/ticket prefill.
- Bridge health + per-run usage fetch.

Not exposed in UI despite backend support:
- `/analyse/stream` live progress.
- `/metrics`, `/dashboard` operator observability.
- `/analytics/csv` export endpoint.
- `/analytics/dashboard` advanced analytics HTML.
- `/backtest`, `/e2e`, `/plugins` diagnostics/introspection.
- `/triage/smoke` diagnostic probe.

### 6.3 Hardcoded/mock/static usage in frontend

- Journey services intentionally fall back to demo data when API fails (`fetchTriage`, `fetchBootstrap`).
- Macro state loader currently fetches local static JSON (`./data/macro_snapshot.json`), not backend feeder health/context endpoints.
- Several journey visual sections are adapter-driven from bootstrap payload but include presentational placeholders (chart annotation layer).

### 6.4 Thin/partial/disconnected areas

- Legacy UI expects `response.usage` while backend returns `usage_summary`; refresh from `/runs/{run_id}/usage` masks mismatch in practice.
- No unified run history/detail page despite run_id and persisted artifacts.
- No frontend support for SSE stream or partial-progress UX.
- No first-class UI for analytics/ops endpoints already available.

---

## 7) Hidden capability summary (backend present, UI mostly absent)

Repo-grounded opportunities:
1. **Streaming progress + partial analyst events** via `/analyse/stream`.
2. **Operational metrics visibility** via `/metrics` and `/dashboard`.
3. **Export workflow** via `/analytics/csv`.
4. **Advanced analytics page linkage/embedding** via `/analytics/dashboard`.
5. **Backtest access** via `/backtest` filters.
6. **Health diagnostics surface** via `/e2e`.
7. **Plugin registry introspection** via `/plugins`.
8. **Feeder health observability integration** in journey/legacy dashboards (currently mostly disconnected).
9. **Dev diagnostics artifacts** for request failure triage in dev mode.

All above are existing backend capabilities; no new endpoints are proposed.

---

## 8) UI-facing domain model

### 8.1 Run
- Represents one analysis execution.
- Origin: `/analyse` (run_id) + backend run directory/state.
- Key fields for UI: `run_id`, `instrument`, `session`, `status` (if exposed), created/updated, error/request IDs, usage summary.
- Relations: has one verdict; has usage and diagnostics artifacts.

### 8.2 Verdict
- Represents arbiter final decision contract.
- Origin: `FinalVerdict` in `/analyse` and `/analyse/stream` final event.
- Key fields: `final_bias`, `decision`, `approved_setups`, `no_trade_conditions`, `overall_confidence`, `analyst_agreement_pct`, `arbiter_notes`, audit metadata.
- Relations: belongs to run; can prefill ticket draft.

### 8.3 TicketDraft
- UI prefill payload derived from verdict + ground truth.
- Origin: `/analyse` response `ticket_draft`.
- Key fields: entry/risk/context fields used by ticket form.
- Relations: attached to run and optional `source_ticket_id`.

### 8.4 TriageItem
- Represents symbol-level watchlist opportunity summary.
- Origin: `/watchlist/triage` from `multi_analyst_output_*.json` artifacts.
- Key fields: `symbol`, `triage_status`, `bias`, `confidence`, `why_interesting`, `rationale`, `verdict_at` + top-level `data_state`.
- Relations: links to Journey bootstrap by asset.

### 8.5 JourneyBootstrap
- Represents preloaded evidence/decision context for one asset.
- Origin: `/journey/{asset}/bootstrap`.
- Key fields: `data_state`, `structure_digest`, `analyst_verdict`, `arbiter_decision`, `explanation`, `reasoning_summary`.
- Relations: seeds staged journey state and gate checklist.

### 8.6 DecisionSnapshot / ResultSnapshot
- Represents persisted user decision and execution outcome records.
- Origin: `/journey/decision`, `/journey/result`, listed by journal/review endpoints.
- Key fields: `snapshot_id`, `instrument`, `saved_at`, `journey_status`, `verdict`, `user_decision`, `has_result`.
- Relations: decision may have result; review joins both.

### 8.7 FeederContextSnapshot
- Represents macro context ingestion state.
- Origin: `/feeder/ingest` and `/feeder/health`.
- Key fields: `status`, `ingested_at`, `stale`, `age_seconds`, `source_health`, `regime`, `vol_bias`, `confidence`.
- Relations: informs analysis macro context and dashboard observability.

### 8.8 Diagnostics/Observability Snapshot
- Represents runtime/system health and test signals.
- Origin: `/metrics`, `/e2e`, `/plugins`, dev diagnostics artifacts.
- Key fields: metrics aggregates, check statuses, plugin inventories, request lifecycle traces.
- Relations: operational overlays on run/journey workflows.

---

## 9) Run-state / UX behavior implications

### 9.1 Long-running behavior
- `/analyse` is long-running synchronous HTTP; client waits until graph completion or timeout/error.
- `/analyse/stream` supports progressive UX via SSE and final verdict event.

### 9.2 Polling vs streaming
- No dedicated run-status polling endpoint found.
- Only post-run usage polling-like fetch exists (`/runs/{run_id}/usage`).
- Streaming exists but frontend does not consume it yet.

### 9.3 Partial results
- Non-streaming `/analyse` returns only terminal payload.
- Streaming endpoint emits partial analyst completion events (`analyst_done`) and heartbeat.

### 9.4 Resumable states
- Backend has persisted run state files (`state.json`) and transition utilities, but no public run-state retrieval endpoint surfaced for UI.
- Therefore resumability is backend-internal from UI perspective today.

### 9.5 Failure exposure
- `/analyse` can return structured HTTP errors (422, 429, 500, 503, 504) with varying `detail` shape; often includes `request_id` and `run_id` for pipeline failures.
- Journey write endpoints return explicit `{success:false,error}` contracts.
- Streaming reports failures in-band with `type:"error"` events.

### 9.6 “Artifact not ready” behavior
- Explicit readiness protocol is limited.
- Triage/journey read endpoints return graceful empty/unavailable states (`data_state: unavailable`, empty records).
- Usage endpoint returns empty usage summary fallback instead of hard failure on some read errors.

Implication: UI contract should model `data_state` and “empty-but-valid” responses as first-class states.

---

## 10) Recommended structure for `docs/ui/UI_CONTRACT.md`

Proposed sections (grounded to this repo):

1. **Purpose and scope**
   - UI-facing backend contract (actual routes used + routes intentionally out of scope).
2. **Source-of-truth hierarchy**
   - Python route files over stale generated OpenAPI.
3. **Transport conventions**
   - JSON vs multipart vs SSE, auth dependency expectations, content-type requirements.
4. **Endpoint contracts (by workspace)**
   - Analysis (`/analyse`, `/analyse/stream`, `/runs/{run_id}/usage`)
   - Triage & Journey (`/watchlist/triage`, `/triage`, `/journey/*`, `/journal/decisions`, `/review/records`)
   - Feeder (`/feeder/ingest`, `/feeder/health`)
   - Observability/analytics/diagnostics (`/metrics`, `/dashboard`, `/analytics/*`, `/backtest`, `/e2e`, `/plugins`)
5. **Model definitions (UI-required fields only)**
   - `FinalVerdict`, `AnalysisResponse`, `TriageItem`, `JourneyBootstrap`, `DecisionRecord`, `ReviewRecord`, `FeederHealth`, `UsageSummary`.
6. **Error contracts per endpoint**
   - Include examples for mixed `detail`/`success:false`/SSE error event patterns.
7. **State semantics**
   - `data_state` meanings, stale vs unavailable, empty records semantics.
8. **Execution semantics**
   - synchronous vs streaming; timeout/failure handling guidance.
9. **Compatibility notes**
   - known mismatches (e.g., `usage_summary` naming in legacy UI), OpenAPI drift note.
10. **Contract test matrix (appendix)**
   - map endpoints to existing tests and missing contract tests.

---

## 11) Recommended structure for `docs/ui/UI_WORKSPACES.md`

Proposed sections (derived from actual capabilities):

1. **Workspace map overview**
   - Current and target workspace boundaries grounded in backend endpoints.
2. **Workspace A: Analysis Run**
   - Trigger analysis, view verdict, ticket prefill, usage by run_id.
   - Optional live mode using `/analyse/stream`.
3. **Workspace B: Triage Board**
   - Watchlist triage list, run triage, freshness/data_state handling.
4. **Workspace C: Journey Studio**
   - Asset bootstrap, staged review, draft/decision/result persistence.
5. **Workspace D: Journal & Review**
   - Decision ledger, result linkage, follow-up loops.
6. **Workspace E: Feeder & Macro Context**
   - Ingest state, source health, staleness visibility.
7. **Workspace F: Operations & Diagnostics**
   - Metrics, operator dashboard linkout, e2e checks, plugin registry.
8. **Workspace G: Analytics & Export**
   - CSV export and analytics dashboard linkage.
9. **Shared UX state model**
   - loading, stale, unavailable, demo-fallback, partial, error.
10. **URL/navigation plan (non-framework-specific)**
   - map existing routes/pages to capabilities without inventing new architecture.
11. **Phased exposure plan (no backend invention)**
   - prioritize already-implemented endpoints not yet surfaced.

---

## 12) Ambiguities / follow-up questions

1. **OpenAPI drift**: Should `docs/architecture/openapi.json` be regenerated now as part of UI contract hardening, or treated as archival only?
2. **Primary frontend direction**: Should `UI_CONTRACT` optimize first for Journey UI (`app/lib/services.js`) or legacy workflow UI (`app/scripts/*`) as canonical consumer?
3. **Error contract normalization**: Is there appetite for a non-breaking standard error envelope layer, or should UI keep endpoint-specific parsing indefinitely?
4. **Run-state exposure**: Backend persists `state.json` but no read endpoint exists—should follow-on phases stay artifact-only or introduce a read-only run-status endpoint (if approved in future scope)?
5. **SSE adoption target**: Is streaming intended for the existing legacy analysis surface, Journey surface, or a separate operator-focused panel?

