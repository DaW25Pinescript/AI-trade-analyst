# UI_CONTRACT

> **Contract authority for UI behavior**, not a status/phase tracker. For current repo phase and progress, see [../AI_TradeAnalyst_Progress.md](../AI_TradeAnalyst_Progress.md).

AI Trade Analyst – UI Contract
File: `docs/ui/UI_CONTRACT.md`
Scope: Backend → UI Contract
Depends on: `docs/ui/UI_BACKEND_AUDIT.md`

---

## 1. Purpose

This document defines the UI-facing backend contract for AI Trade Analyst.

Its purpose is to give the frontend a stable, explicit handoff layer grounded in the actual repo behavior rather than assumptions, stale generated docs, or ad hoc endpoint usage.

It defines:

- which backend routes the UI may rely on
- which payload shapes matter to the UI
- how loading, empty, stale, unavailable, partial, and error states must be interpreted
- how long-running analysis behaves in synchronous vs streaming mode
- how run lifecycle state should be represented in the UI
- where compatibility quirks already exist and must be handled intentionally
- what timeout, retry, and failure boundaries the frontend must respect

This document is a frontend contract, not a backend implementation spec.
It describes what the UI can safely consume today and how the UI should normalize current backend behavior without inventing new endpoints.

---

## 2. Scope

Included:

- analysis endpoints used by the legacy workflow UI
- triage and journey endpoints used by the Journey UI
- feeder endpoints relevant to macro/context state
- observability, analytics, export, and diagnostics endpoints that already exist and may be surfaced by future UI work
- UI-facing domain objects required for rendering and persistence flows
- endpoint-family-specific failure handling
- shared UX state semantics
- canonical UI run lifecycle semantics inferred from current backend behavior

Excluded:

- internal-only backend implementation details not exposed to UI
- proposed future endpoints not yet present in the repo
- speculative frontend framework decisions
- chart-evidence future-state contracts
- backend refactors that are not required to safely consume the current API surface

---

## 3. Source-of-Truth Hierarchy

When this contract conflicts with other documentation, use this precedence order:

1. Python route declarations and response behavior in backend code
2. This `UI_CONTRACT.md`
3. Existing frontend consumers in `/app/`
4. Generated OpenAPI artifacts

Important:

The Phase 1 audit found that `docs/architecture/openapi.json` is stale and only reflects a subset of the live API surface. It must not be treated as the primary contract source for UI work.

### 3.1 Governance rule

Once this contract is adopted, frontend implementation should not infer UI contracts directly from ad hoc backend code paths, stale generated docs, or one-off payload observation.

Required governance rule:

- backend code remains the implementation source of truth
- `UI_CONTRACT.md` becomes the canonical frontend handoff and normalization layer
- any backend change that materially affects a documented UI-facing route, state, or payload must update this contract deliberately rather than relying on frontend rediscovery

This rule exists to stop contract drift and keep the frontend from silently re-coupling itself to implementation details.

---

## 4. Frontend Consumer Priority

AI Trade Analyst currently has two frontend surfaces:

- **Journey UI** — `app/lib/*`, `app/pages/*`
- **Legacy workflow UI** — `app/scripts/*`

For Phase 2 contract purposes:

- the **Journey UI is the primary canonical consumer** for forward UI design
- the **legacy workflow UI remains supported as a compatibility surface**
- no endpoint should be documented as “unused” merely because only one surface consumes it

This reflects current repo reality: Journey UI already consumes triage, bootstrap, journal, review, and journey persistence routes, while the legacy workflow owns `/analyse`, `/runs/{run_id}/usage`, and feeder controls.

---

## 5. Transport and Access Conventions

### 5.1 JSON

Most UI-facing endpoints use JSON request/response bodies.

Examples:

- `/watchlist/triage`
- `/triage`
- `/journey/*`
- `/journal/decisions`
- `/review/records`
- `/feeder/ingest`
- `/feeder/health`
- `/metrics`
- `/backtest`
- `/e2e`
- `/plugins`

### 5.2 Multipart Form Data

`/analyse` and `/analyse/stream` accept multipart form-data because they support chart uploads plus structured form fields.

The UI must treat these as form submission endpoints, not JSON POST endpoints.

### 5.3 SSE Streaming

`/analyse/stream` is a Server-Sent Events endpoint.

Implications:

- the UI must consume it as a stream, not a regular JSON response
- success and failure may both appear in-band as events
- partial progress is event-driven
- no separate polling endpoint exists today for public run-state retrieval

### 5.4 HTML Endpoints

Some existing backend surfaces return HTML, not JSON:

- `/dashboard`
- `/analytics/dashboard`

These should be treated as link-out or embed-style operator surfaces, not normal JSON API endpoints.

### 5.5 Download Endpoints

`/analytics/csv` returns a CSV attachment/download stream.

The UI must treat this as an export/download action, not a normal in-app JSON data fetch.

### 5.6 Auth and Environment Assumptions

The current Phase 1 audit did not establish a formal frontend auth contract such as bearer tokens, session cookies, or role-based UI gates.

Therefore, for Phase 2 purposes:

- this contract assumes current same-origin/local-dev style access patterns
- no endpoint in this document is documented as requiring a frontend-managed auth header unless backend code explicitly establishes one
- if authentication or authorization is introduced later, it must be documented as a cross-cutting access layer and must not silently alter payload semantics

UI implication:

A transport failure caused by future auth changes must be treated as an access-layer problem, not misclassified as payload incompatibility.

---

## 6. Shared UI State Semantics

These semantics apply across all workspaces and should be represented explicitly in UI state management.

| State | Meaning | UI expectation |
|---|---|---|
| `loading` | Request has started and no usable payload exists yet | show spinner, skeleton, or progress state |
| `partial` | Some meaningful progress or partial data exists, but terminal result is not complete | show incremental progress and preserve context |
| `ready` | Valid payload received and usable | normal render |
| `empty` | Valid response returned but with no records/items | show empty state, not error |
| `stale` | Data exists but freshness is degraded | render with stale warning |
| `unavailable` | Data source/artifact not currently available | show unavailable state, not fatal crash |
| `demo-fallback` | UI is showing local/demo fallback data rather than live backend payload | show explicit demo badge or internal flag |
| `error` | Request failed or payload unusable | show error state with endpoint-specific message |

Important:

The audit found that triage and journey reads already use graceful empty/unavailable responses, and the usage endpoint can return an empty usage summary fallback rather than hard-failing. That means “empty-but-valid” and `data_state` are first-class states, not edge cases.

### 6.1 `data_state`

Where endpoints expose `data_state`, the UI must not collapse it into generic success/failure.

Minimum expected meanings:

- `live` or equivalent freshness state → preferred display
- `stale` → usable with warning
- `unavailable` → graceful unavailable state
- empty records with valid response → empty state

If endpoint-specific values evolve, the UI should preserve unknown values rather than silently normalizing them away.

### 6.2 Boundary between `data_state` and run state

`data_state` applies to read-oriented surfaces that return existing artifacts or freshness-qualified data, such as triage boards, journey bootstrap, review lists, or feeder health.

The canonical run state model in Section 7 applies to active execution workflows such as analysis submission and any future UI that represents an in-flight backend operation.

They are related but not interchangeable:

- `data_state` answers whether returned data is live, stale, unavailable, or empty-but-valid
- run state answers where an execution attempt is in its lifecycle

A UI may need to display both dimensions at the same time.

---

## 7. Canonical UI Run State Model

This is a **UI-canonical lifecycle model** for analysis execution.
It is one of the most important additions in Phase 2.

This section governs active execution workflows. It does not replace `data_state` for read-oriented artifact and freshness endpoints.

Important:

- this model is grounded in current backend behavior
- it is **not** a claim that the backend currently exposes every state directly
- several states are inferred from request lifecycle, SSE events, and follow-up artifact reads
- because no public run-status endpoint exists today, the frontend must sometimes derive state indirectly

### 7.1 Primary lifecycle states

| State | Meaning | Entry trigger | Exit trigger | Notes |
|---|---|---|---|---|
| `idle` | No analysis submission in progress | initial view or after reset | user starts validation/submission | default workspace state |
| `validating` | Client is validating form fields/files before submission | local submit attempt begins | submit blocked or request dispatched | purely client-side |
| `submitting` | Request has been dispatched but no execution confirmation is visible yet | HTTP request sent | first meaningful response/progress, or transport failure | useful for button locking and duplicate-submit prevention |
| `running` | Analysis execution is active | `/analyse` request in-flight or `/analyse/stream` connected | terminal verdict, error, or disconnect failure | primary active run state |
| `partial` | Meaningful progress exists but no terminal verdict yet | SSE heartbeat/analyst progress received | more progress, terminal verdict, or terminal error | only applicable to streaming mode |
| `completed` | Terminal verdict received and usable | final JSON response or streamed verdict received | view reset or new run begins | terminal success |
| `failed` | Terminal failure occurred | HTTP error, streamed error event, or abnormal terminal condition | user retry or reset | terminal failure |

### 7.2 Reserved lifecycle states

These states are useful in the canonical model but are **not currently guaranteed by backend exposure**.
They should not be shown unless a concrete trigger is implemented.

| State | Current status | Intended future meaning |
|---|---|---|
| `queued` | reserved only | accepted for execution but not yet actively running |
| `cancelled` | reserved only | run intentionally aborted by user or backend control |

### 7.3 Artifact and consistency modifiers

These are not primary run lifecycle states. They are modifiers that may apply after or around a run.

| Modifier | Meaning | Typical source |
|---|---|---|
| `artifact-missing` | primary run completed, but an expected secondary artifact could not be read | usage fetch, derived artifact read, future chart evidence, missing adjunct record |
| `stale` | related data is present but freshness is degraded | feeder health, triage age, cached journey bootstrap |
| `inconsistent` | payloads disagree or expected linked artifacts do not reconcile | verdict present but usage/readback missing in an unexpected way |
| `demo-fallback` | UI is rendering fallback content instead of live backend output | journey bootstrap/triage adapters |

### 7.4 State transition rules

Baseline synchronous flow:

`idle -> validating -> submitting -> running -> completed | failed`

Streaming flow:

`idle -> validating -> submitting -> running -> partial -> completed | failed`

Post-completion modifiers:

- `completed + artifact-missing`
- `completed + stale`
- `completed + inconsistent`

### 7.5 UI rules for the state model

- do not present `queued` or `cancelled` unless the backend actually supports them in that workspace
- do not collapse `partial` into generic loading when meaningful streamed progress exists
- do not collapse `artifact-missing` into full run failure if the primary verdict is already usable
- keep lifecycle state separate from data freshness state where possible

---

## 8. Execution Semantics

### 8.1 Synchronous Analysis

`POST /analyse` is long-running synchronous HTTP.

Behavior:

- request blocks until pipeline completion or terminal error
- no partial analyst progress is delivered
- response is terminal: either final JSON payload or HTTP error

UI implications:

- show `running` state after submission
- support long waits and user-visible timeout messaging
- do not expect resumable polling from backend
- do not assume progress percentages exist

### 8.2 Streaming Analysis

`POST /analyse/stream` supports progressive UX via SSE.

Behavior:

- emits heartbeat and analyst completion events
- emits final verdict event
- emits streamed error events in-band
- no public resume endpoint exists

UI implications:

- streaming UX is optional, not required for baseline contract adoption
- if adopted, the UI must treat stream disconnects and error events as endpoint-specific terminal conditions
- `partial` state should be used only when meaningful streamed progress has been observed

### 8.3 No Public Run-State Endpoint

Backend run state exists internally (`state.json` and run transition utilities), but no public run-status retrieval endpoint is currently exposed for the UI.
That means resumability is backend-internal today and should not be assumed by the frontend.

---

## 9. UI-Facing Domain Model

Only UI-relevant fields are defined here.
This is intentionally not a full backend schema dump.

### 9.1 Run

Represents a single analysis execution.

Minimum UI fields:

- `run_id: string`
- `instrument?: string`
- `session?: string`
- `request_id?: string`
- `status?: string` (only if explicitly surfaced by endpoint)
- `usage_summary?: UsageSummary`

Relations:

- has one terminal verdict
- may have usage and diagnostics artifacts

### 9.2 FinalVerdict

Represents the arbiter’s terminal decision object.

Minimum UI fields:

- `final_bias`
- `decision`
- `approved_setups`
- `no_trade_conditions`
- `overall_confidence`
- `analyst_agreement_pct`
- `arbiter_notes`
- audit metadata if present

This is the core decision object returned by `/analyse` and terminally by `/analyse/stream`.

### 9.3 AnalysisResponse

Represents the terminal response from `/analyse`.

Minimum UI fields:

- `verdict: FinalVerdict`
- `ticket_draft`
- `run_id`
- `source_ticket_id?`
- `usage_summary?`

Compatibility note:

Legacy UI has a known mismatch where it expects `response.usage` while backend returns `usage_summary`; later refresh from `/runs/{run_id}/usage` masks this in practice.

### 9.4 UsageSummary

Represents token/cost/call summary for a run.

Minimum UI fields:

- token counts if present
- cost totals if present
- provider/model breakdown if present
- safe empty fallback object

The UI must tolerate empty-but-valid usage results.

### 9.5 TriageItem

Represents one symbol-level watchlist opportunity summary.

Minimum UI fields:

- `symbol`
- `triage_status`
- `bias`
- `confidence`
- `why_interesting?`
- `rationale?`
- `verdict_at?`

Container-level fields:

- `data_state`
- `generated_at`
- `items: TriageItem[]`

### 9.6 JourneyBootstrap

Represents preloaded staged decision context for one asset.

Minimum UI fields:

- `data_state`
- `instrument`
- `generated_at`
- `structure_digest`
- `analyst_verdict`
- `arbiter_decision`
- `explanation`
- `reasoning_summary`

### 9.7 DecisionSnapshot

Represents an immutable stored decision record.

Minimum UI fields:

- `snapshot_id`
- `instrument`
- `saved_at`
- `journey_status`
- `verdict`
- `user_decision`

### 9.8 ReviewRecord

Represents a decision record with result linkage.

Relationship to `DecisionSnapshot`:

- `ReviewRecord` should be treated as `DecisionSnapshot` plus review/result linkage fields such as `has_result`
- frontend adapters should extend the decision shape rather than model these as two unrelated contracts unless backend divergence requires it later

Minimum UI fields:

- `snapshot_id`
- `instrument`
- `saved_at`
- `journey_status`
- `verdict`
- `user_decision`
- `has_result`

### 9.9 FeederHealth

Represents macro/context ingestion freshness.

Minimum UI fields:

- `status`
- `ingested_at`
- `age_seconds`
- `stale`
- `source_health`
- `regime?`
- `vol_bias?`
- `confidence?`

### 9.10 DiagnosticsSnapshot

Represents operator/observability state from already-existing backend surfaces.

Minimum UI fields:

- high-level status
- metrics aggregates
- check counts or statuses
- plugin inventories

---

## 10. Endpoint Contracts by Workspace

## 10.1 Analysis Workspace

### `GET /health`

Purpose:

- API liveness/version check for legacy workflow bridge

Success shape:

- `{ status, version }`

Failure shape:

- default FastAPI `detail`

UI notes:

- should drive connectivity/bridge state only
- not a rich application-status endpoint
- safe to refresh/retry

### `POST /analyse`

Purpose:

- primary multi-analyst analysis run with final verdict generation

Transport:

- multipart/form-data

Request shape:

- instrument/session/context/risk fields
- chart uploads
- optional source ticket reference
- optional deliberation/triage flags

Success shape:

- `AnalysisResponse`

Failure shape:

- HTTP errors with mixed `detail` patterns
- may be string or structured object
- may include `request_id` and `run_id`
- observed terminal statuses include `422`, `429`, `500`, `503`, `504`

Timeout and retryability:

- long-running request; UI must support long wait semantics
- do not auto-retry on timeout or network interruption
- if a failure payload includes `run_id` or `request_id`, preserve it for operator/debug context
- user-driven retry is allowed, but should be explicit because duplicate execution cannot be ruled out from the UI side

UI rules:

- treat as long-running terminal request
- do not expect partial progress
- preserve `run_id` if returned
- preserve structured error fields if present
- enter `failed` on terminal error, not generic `idle`

### `POST /analyse/stream`

Purpose:

- streaming analysis progress and terminal verdict via SSE

Transport:

- multipart/form-data request + SSE response

Success/event shapes:

- `analyst_done`
- `heartbeat`
- `verdict`

Failure/event shapes:

- `error` event in-band
- abnormal disconnect without terminal verdict must be treated as failure unless later explicitly reconciled

Timeout and retryability:

- no auto-resume protocol exists
- do not auto-retry on disconnect
- explicit user restart is allowed
- inactivity timeout should be handled separately from hard terminal error so UX can explain whether the stream died versus the analysis rejected

UI rules:

- parse as stream, not JSON
- keep progress UI separate from terminal verdict UI
- use `partial` when meaningful progress events have been received
- treat stream termination without terminal verdict as failure unless explicitly handled

### `GET /runs/{run_id}/usage`

Purpose:

- retrieve usage summary after run completion

Success shape:

- `{ run_id, usage_summary }`

Failure shape:

- may degrade to safe empty usage fallback rather than hard error

Timeout and retryability:

- safe to manually retry or background refresh
- this is a secondary artifact read, not a primary run execution

UI rules:

- usage panel must support empty-but-valid state
- this endpoint is not a run-status endpoint
- if verdict is present but usage is unavailable, use `artifact-missing` rather than full run failure

---

## 10.2 Triage Workspace

### `GET /watchlist/triage`

Purpose:

- read latest triage artifact summaries for watchlist/dashboard use

Success shape:

- `{ data_state, generated_at, items[] }`

Failure/empty behavior:

- may return graceful empty/unavailable state rather than hard error

Timeout and retryability:

- safe to refresh/retry

UI rules:

- render `data_state` explicitly
- support empty and stale board states
- do not treat no-items as failure

### `POST /triage`

Purpose:

- trigger symbol triage batch and write artifacts

Run-state relationship:

- `POST /triage` is a long-running execution, but it does **not** currently use the full canonical run state model in a user-visible way
- for current UI purposes, treat it as a trigger-and-refresh workflow: `idle -> submitting -> running -> completed | failed`, followed by a separate read of `GET /watchlist/triage`
- `partial` should only be used if the backend later exposes meaningful incremental triage progress; it should not be inferred today from eventual artifact refresh alone

Request shape:

- optional `symbols` JSON body

Success shape:

- `{ status, artifacts_written, symbols_processed, output_dir }`

Failure shape:

- `500` may return `{ message, partial }` when all fail

Timeout and retryability:

- may be long-running
- do not auto-retry blindly because artifact writes may already have occurred partially
- allow explicit user rerun

UI rules:

- after success, board refresh is a separate read action
- partial failure should be surfaced, not collapsed into generic error

### `POST /triage/smoke`

Purpose:

- engineering diagnostic probe of triage→analyse chain

Contract status:

- internal/non-UI
- not part of standard user-facing workspace contract

---

## 10.3 Journey Workspace

### `GET /journey/{asset}/bootstrap`

Purpose:

- load asset-specific staged decision bootstrap

Success shape:

- `{ data_state, instrument, generated_at, structure_digest, analyst_verdict, arbiter_decision, explanation, reasoning_summary }`

Failure/empty behavior:

- graceful unavailable payload rather than hard failure is possible

Timeout and retryability:

- safe to retry/refresh

UI rules:

- render unavailable bootstrap gracefully
- allow adapters/placeholders without treating missing optional sections as endpoint failure
- preserve `demo-fallback` when local fallback data is used instead of backend data

### `POST /journey/draft`

Purpose:

- save mutable draft snapshot

Request shape:

- free-form draft JSON
- optional `journey_id`

Success shape:

- `{ success, journey_id, saved_at, path }`

Failure shape:

- non-2xx with `{ success:false, error }`

Timeout and retryability:

- user retry is acceptable
- because this is mutable state, repeated submission overwrites or supersedes rather than representing immutable duplication

UI rules:

- endpoint family uses explicit success envelope pattern
- preserve error string verbatim unless mapped to UX copy layer

### `POST /journey/decision`

Purpose:

- freeze immutable decision snapshot

Request shape:

- JSON body requiring `snapshot_id`

Success shape:

- `{ success, snapshot_id, saved_at, path }`

Failure shape:

- `400`, `409`, `500`
- `{ success:false, error }`

Timeout and retryability:

- do not auto-retry blindly after timeout because the immutable write may already have succeeded
- on ambiguous failure, the UI should reconcile against journal/review/read surfaces before offering a second submit

UI rules:

- duplicate immutable decision is a meaningful conflict state, not a generic save failure
- `409` should map to conflict UX, not fatal crash

### `POST /journey/result`

Purpose:

- save execution/result snapshot linked to a decision snapshot

Request shape:

- JSON body requiring `snapshot_id`

Success shape:

- `{ success, snapshot_id, saved_at, path }`

Failure shape:

- `{ success:false, error }`
- current audit did not confirm an explicit `409` contract for duplicate result writes

Timeout and retryability:

- same caution as immutable or linked writes: reconcile before resubmitting when outcome is ambiguous
- the UI must not assume duplicate result submissions are harmless just because a documented `409` is not yet confirmed

UI rules:

- treat result persistence as snapshot-linked and potentially conflict-prone
- if backend later exposes explicit duplicate-result conflict behavior, map it the same way as decision conflict UX
- until then, ambiguous failures should be resolved via journal/review readback before allowing repeated submit

### `GET /journal/decisions`

Purpose:

- list decision summaries

Success shape:

- `{ records:[...] }`

Failure/empty behavior:

- graceful empty list supported

Timeout and retryability:

- safe to refresh/retry

### `GET /review/records`

Purpose:

- list decision summaries with result linkage

Success shape:

- `{ records:[..., has_result] }`

Failure/empty behavior:

- graceful empty list supported

Timeout and retryability:

- safe to refresh/retry

---

## 10.4 Feeder and Macro Context Workspace

### `POST /feeder/ingest`

Purpose:

- ingest feeder payload and cache macro context

Request shape:

- `FeederIngestPayload`

Success shape:

- `{ status:"ok", macro_context, ingested_at }`

Failure shape:

- `422`, `503`, `500`

Timeout and retryability:

- should be treated as operator/admin style action
- no blind auto-retry from general UI

UI rules:

- primarily operator/admin style action
- useful for bridge tooling and future macro context visibility

### `GET /feeder/health`

Purpose:

- expose freshness and health of feeder state

Success shape:

- `{ status, ingested_at, age_seconds, stale, source_health, regime, vol_bias, confidence, ... }`

Failure shape:

- default FastAPI detail

Timeout and retryability:

- safe to refresh/retry

UI rules:

- should drive stale/freshness visibility if surfaced in Journey or ops UI

---

## 10.5 Observability, Analytics, and Diagnostics Workspace

These endpoints exist and are valid UI-facing surfaces, but are not currently consumed by `/app/`. They should remain documented because they are available for later exposure.

### `GET /metrics`

- JSON metrics snapshot
- supports operator/diagnostics workspace
- safe to refresh

### `GET /dashboard`

- server-rendered operator dashboard HTML
- supports linkout/embed workflow

### `GET /analytics/csv`

- CSV export stream
- supports export workflow
- explicit user action preferred; do not background poll

### `GET /analytics/dashboard`

- server-rendered analytics dashboard HTML
- supports advanced analytics workspace

### `GET /backtest`

- JSON backtest report
- supports quant/research workspace
- safe to refresh manually

### `GET /e2e`

- JSON end-to-end diagnostic checks
- supports health diagnostics workspace
- safe to refresh manually

### `GET /plugins`

- JSON plugin/persona registry surface
- supports introspection/config workspace
- safe to refresh manually

---

## 10.6 Agent Operations Endpoints (Implemented — Phase 7)

The Agent Operations endpoint contracts are defined in a dedicated document:

**Contract document:** [`AGENT_OPS_CONTRACT.md`](AGENT_OPS_CONTRACT.md)

**Classification:** Phase 3B — operator observability / explainability / trust workspace. Operator-lane, not runtime-lane.

### Contracted endpoints (PR-OPS-1)

| Method | Route | Purpose | Contract status |
|--------|-------|---------|----------------|
| `GET` | `/ops/agent-roster` | Static architecture and roster truth | Implemented (PR-OPS-2) |
| `GET` | `/ops/agent-health` | Current health snapshot (poll-based) | Implemented (PR-OPS-2) |

These endpoints are implemented and available. Frontend code may call these endpoints. See `AGENT_OPS_CONTRACT.md` for response shapes and behavioral rules.

### Trace and detail endpoints (Phase 7 — implemented)

| Method | Route | Purpose | Contract status |
|--------|-------|---------|----------------|
| `GET` | `/runs/{run_id}/agent-trace` | Run-specific participation and lineage | Implemented (PR-OPS-4a) |
| `GET` | `/ops/agent-detail/{entity_id}` | Full detail for selected entity | Implemented (PR-OPS-4b) |

Implemented and contracted in `AGENT_OPS_CONTRACT.md` §6 (trace) and §7 (detail). Delivered in PR-OPS-4a/4b (15 March 2026). 197 backend tests.

---

## 11. Error Contract Rules

There is **no single global error envelope** across the backend.
The contract must therefore preserve endpoint-family-specific handling.

### 11.1 FastAPI `detail` style

Used by several backend routes.

Patterns include:

- `detail: string`
- `detail: object`
- structured objects that may include `message`, `code`, `request_id`, `run_id`

UI rule:

- if `detail` is string, show or log the string
- if `detail` is object, preserve the object and extract display text conservatively
- never assume `detail` is always a string

### 11.2 Journey write envelope style

Used by:

- `/journey/draft`
- `/journey/decision`
- `/journey/result`

Pattern:

- non-2xx with `{ success:false, error }`

UI rule:

- parse as explicit failed operation envelope
- keep error text stable for save/freeze/result workflows

### 11.3 SSE error event style

Used by:

- `/analyse/stream`

Pattern:

- streamed event with `type:"error"`

UI rule:

- treat as terminal stream failure unless terminal verdict already processed
- preserve any included identifiers or messages

### 11.4 Graceful empty/unavailable style

Used by read-oriented triage/journey/review style endpoints.

Pattern:

- valid response with `data_state: unavailable` or empty `records/items`

UI rule:

- do not show generic API error
- show unavailable or empty state

### 11.5 Failure boundary rules

The UI must distinguish between these failure boundaries:

- **transport failure** — request did not complete or stream disconnected
- **contract failure** — payload shape is materially incompatible with expected UI handling
- **domain failure** — backend intentionally rejected or failed the operation
- **artifact absence** — primary object is usable, but a secondary artifact is unavailable
- **freshness degradation** — data exists but is stale

These must not be collapsed into one generic “something went wrong” state.

---

## 12. Timeout and Retryability Rules

### 12.1 General rules

- safe GET reads may be retried or refreshed
- long-running POST execution endpoints must not be blindly auto-retried
- immutable or ambiguity-prone writes must be reconciled before resubmission where possible
- timeout messaging should distinguish “still running but UI stopped waiting” from “backend returned terminal failure” where the protocol allows it

### 12.2 Endpoint classes

| Endpoint class | Timeout posture | Retry posture |
|---|---|---|
| simple reads (`GET /health`, `GET /watchlist/triage`, `GET /journal/decisions`, `GET /review/records`, `GET /feeder/health`, diagnostics reads) | short to moderate | safe refresh/retry |
| long-running analysis (`POST /analyse`) | extended wait | explicit user retry only |
| streaming analysis (`POST /analyse/stream`) | inactivity-aware and disconnect-aware | explicit user restart only |
| triage generation (`POST /triage`) | extended wait | explicit rerun only |
| mutable draft save (`POST /journey/draft`) | moderate | user retry acceptable |
| immutable/linked writes (`POST /journey/decision`, `POST /journey/result`) | moderate | reconcile before retry if ambiguous |
| export/download (`GET /analytics/csv`) | user-driven | re-trigger manually |

### 12.3 UX guidance

- when timeout occurs on `/analyse`, preserve any known `run_id` or `request_id`
- when timeout or disconnect occurs on `/analyse/stream`, preserve the last known progress event
- when immutable write outcome is ambiguous, route user toward review/journal confirmation before allowing duplicate submission

---

## 13. Compatibility Notes

### 13.1 OpenAPI Drift

`docs/architecture/openapi.json` is not sufficient for UI contract generation because it only documents `/health` and `/analyse`, while the repo exposes a wider live route set.

### 13.2 Legacy Usage Field Mismatch

Legacy UI expects `response.usage` while backend returns `usage_summary`. Later refresh from `/runs/{run_id}/usage` masks the mismatch in practice, but the contract should standardize on **`usage_summary`**.

### 13.3 Demo Fallback Behavior

Journey services intentionally fall back to demo data when API requests fail for triage/bootstrap. This is valid current behavior, but the UI should mark this state explicitly rather than silently presenting demo data as live data.

### 13.4 Macro Context Split

Current macro state in the frontend is partly sourced from local static JSON rather than backend feeder health/context routes. Any future workspace should resolve this intentionally, but this contract only records the current split.

---

## 14. Non-Goals

This contract does not:

- define new backend endpoints
- redesign backend payloads for theoretical cleanliness
- require immediate adoption of streaming
- require a new run-history or run-status endpoint
- formalize future chart-evidence payloads
- replace deeper backend schemas or model classes
- imply that reserved UI lifecycle states already exist as public backend states

---

## 15. Recommended Follow-On Actions

1. Use this contract as the sole input for `docs/ui/UI_WORKSPACES.md`.
2. Standardize frontend adapters around `usage_summary`, endpoint-family error handling, and `data_state` semantics.
3. Decide whether the stale OpenAPI artifact will be regenerated or explicitly treated as archival.
4. Decide whether `/analyse/stream` remains dormant or becomes part of a later Analysis Run workspace.
5. Add contract tests for mixed error shapes, empty-but-valid responses, run state normalization, and Journey save/freeze/result flows.

---

## 16. Appendix — Contract Test Priorities

Minimum contract tests to add or verify:

- `/analyse` success response includes `verdict`, `ticket_draft`, `run_id`, `usage_summary`
- `/analyse` error handling tolerates both string and object `detail`
- `/analyse/stream` emits terminal verdict and error event shapes correctly
- run UI adapter correctly maps synchronous and streaming flows into the canonical run state model
- triage UI adapter uses trigger-and-refresh lifecycle rules without falsely inventing `partial` state
- `/runs/{run_id}/usage` tolerates empty usage fallback
- `/watchlist/triage` supports `data_state` plus empty `items`
- `/journey/{asset}/bootstrap` supports unavailable bootstrap shape
- `/journey/draft` returns `{success:false,error}` on failed save
- `/journey/decision` preserves `409` duplicate immutable behavior
- `/journey/result` ambiguous write outcomes reconcile through readback before duplicate submit
- failure boundary mapping distinguishes transport vs contract vs domain vs artifact absence vs freshness degradation
- timeout/retryability adapter enforces different policies for reads, long-running execution, streaming, triage generation, mutable draft saves, and immutable/linked writes
- `/journal/decisions` and `/review/records` treat empty `records` as valid success
- `/review/records` adapter extends the `DecisionSnapshot` shape rather than duplicating a separate incompatible model
- `/feeder/health` exposes freshness fields needed for stale-state UI

---

## Summary

`UI_CONTRACT.md` is the anti-corruption layer between the real backend and the evolving frontend.

Its job is not to idealize the API. Its job is to make the current system safe to build against.
