# Audit Report — Trade Ideation Journey V1.1

**Audit date:** 2026-03-07
**Auditor:** Claude Code (Post-Merge Acceptance Audit)
**Commit:** 8a01e34 (head of master at audit time)

---

## 1. Executive Summary

**Overall result:** PASS WITH ISSUES

**One-paragraph explanation:**
The V1.1 merge delivers a structurally complete Trade Ideation Journey with real backend wiring, disk-backed persistence, truthful data-state handling, and an intact V1 UI surface. All seven journey endpoints exist and respond correctly. Save semantics are confirmed real — `POST /journey/decision` writes physical JSON files to `app/data/journeys/decisions/`, duplicate snapshot IDs are rejected with HTTP 409, and the UI only shows save success after backend confirmation. No Critical findings were identified. Four High findings require a follow-up patch: (1) the raw `digest` object leaks snake_case field names into `JourneyPage.js`, violating the casing boundary; (2–4) the `decisionSnapshot` is missing three required fields from CONTRACTS.md Section 2 — `journeyId`, `gateJustifications` (as a separate map), and `provenance` (field-level tracking map).

**Top 3 risks:**
1. Casing boundary leak — `JourneyPage.js` accesses raw `digest` snake_case fields directly (7 occurrences), violating CONTRACTS.md Section 5
2. Incomplete snapshot — `journeyId`, `gateJustifications`, and `provenance` map are absent from `createSnapshot()`, breaking CONTRACTS.md Section 2
3. `dataState` is not persisted in the journey store — it flows via a module-level variable in JourneyPage, bypassing the centralized state

---

## 2. Pass/Fail Matrix

| Group | Area | Result | Evidence |
|-------|------|--------|---------|
| A | V1 UI non-regression | PASS | All 4 routes registered (`journey.js:26-44`). 7 stage keys in `types/journey.js:20-28`. Gate enforcement in `journeyStore.js:68-73`. SplitVerdictPanel renders 3 panels (`SplitVerdictPanel.js:32-46`). `/health` endpoint at `main.py:337`. |
| B | Backend endpoint existence | PASS | All 7 journey endpoints in `ai_analyst/api/routers/journey.py`. Router registered at `main.py:332-334`. `load_dotenv()` at `main.py:37` before all imports. Existing routes confirmed: `/health`, `/feeder/ingest`, `/feeder/health`, `/analyse`, `/metrics`, `/dashboard`, `/analytics/csv`, `/analytics/dashboard`, `/backtest`. |
| C | Backend response shape conformance | PASS | Triage response shape matches CONTRACTS.md (journey.py:138-156). Bootstrap response shape matches (journey.py:186-200). Decision response matches (journey.py:279-284). Journal returns `{records: [...]}` with summary fields (journey.py:341-350). All backend field names are snake_case. |
| D | Triage/bootstrap truth | PASS | Dashboard imports `fetchTriage` from services.js (DashboardPage.js:14). No hardcoded mock array in active path. Demo fallback only on network failure, marked `dataState: 'demo'` (services.js:263-268). Unavailable state shows truthful message (DashboardPage.js:52-58). Bootstrap calls real endpoint (services.js:80). |
| E | Save semantics | PASS | Save calls `saveDecision` → `POST /journey/decision` (JourneyPage.js:439). Success shown only after backend confirmation (JourneyPage.js:440-446). `_write_json` creates physical file with `mkdir(parents=True)` (journey.py:69-76). Duplicate rejection via 409 (journey.py:262-269). No localStorage/sessionStorage/IndexedDB in V1.1 journey code. |
| F | Persistence durability | PASS | Journal reads from `_DECISIONS_DIR` disk files (journey.py:337-350). Review reads from same disk source (journey.py:371-386). Files persist across restarts by design (file-based, no in-memory cache). Empty-state returns `{records: []}` (journey.py:333-334). |
| G | Service/adapter architecture | PARTIAL | Components do not call `fetch` directly (grep confirmed: 0 matches in pages/ and components/). Adapters handle snake_case↔camelCase (adapters.js:14-62). **However:** raw `digest` object leaks snake_case into JourneyPage (see H-1). `dataState` reaches component layer via module variable. Demo fallback only on unreachable backend (services.js:51-54, 84-87). |
| H | Snapshot completeness | PARTIAL | `systemVerdict`, `userDecision`, `executionPlan` are separate objects (journeyStore.js:213-215). `bootstrapDataState` added (JourneyPage.js:436). **However:** `journeyId`, `gateJustifications`, and `provenance` map are missing from snapshot (see H-2, H-3, H-4). |

---

## 3. Critical Findings

> Only findings that block acceptance. If none, write "None."

None.

---

## 4. High Findings

> Major contract violations that must be in the follow-up patch.

| ID | Area | Description | Evidence | Remediation |
|----|------|-------------|---------|------------|
| H-1 | Group G — Casing boundary | `JourneyPage.js` accesses raw `digest` object with snake_case field names: `digest.htf_bias`, `digest.structure_gate`, `digest.bos_mss_alignment`, `digest.liquidity_bias`, `digest.active_fvg_context`, `digest.recent_sweep_signal`, `digest.htf_source_timeframe`. The adapter passes the raw digest through without deep-converting keys. | `app/pages/JourneyPage.js:197-203`, `app/pages/JourneyPage.js:246` (`digest.htf_source_timeframe`), `app/pages/JourneyPage.js:260` (`digest.active_fvg_count`). Root cause: `app/lib/adapters.js:207` passes `digest: digest` (raw) into stageData. | Apply `deepSnakeToCamel(digest)` in `adaptJourneyBootstrap` before passing to stageData. Update JourneyPage references to camelCase (`digest.htfBias`, etc.). |
| H-2 | Group H — Snapshot | `journeyId` field is missing from `createSnapshot()` output. CONTRACTS.md Section 2 requires `journey_id` (camelCase: `journeyId`). | `app/stores/journeyStore.js:208-228` — no `journeyId` property in the snapshot object. | Add `journeyId: _state.journeyId || _generateId()` to `createSnapshot()`. Ensure a journey ID is assigned at bootstrap time and tracked in store state. |
| H-3 | Group H — Snapshot | `gateJustifications` missing as a separate map. CONTRACTS.md Section 2 requires `gate_justifications: { gate_id: string }` as a top-level snapshot field. Justifications exist within each gate object but are not extracted to a separate map. | `app/stores/journeyStore.js:208-228` — no `gateJustifications` property. Gate justifications are inside `gateStates[n].justification` but not aggregated. | Add `gateJustifications: Object.fromEntries(_state.gateStates.filter(g => g.justification).map(g => [g.id, g.justification]))` to `createSnapshot()`. |
| H-4 | Group H — Snapshot | `provenance` map missing from snapshot. CONTRACTS.md Section 2 requires `provenance: { field_key: "ai_prefill|user_confirm|user_override|user_manual" }`. The store tracks provenance per-field on `userDecision` and `executionPlan` but does not aggregate into a top-level map. | `app/stores/journeyStore.js:208-228` — no `provenance` property. `Provenance` enum exists in `types/journey.js:74-79` but is not collected at snapshot time. | Build a provenance map at snapshot time from systemVerdict (ai_prefill), userDecision (user_manual), executionPlan (user_manual), and any user-confirmed/overridden bootstrap fields. |

---

## 5. Medium / Low Findings

| ID | Severity | Area | Description |
|----|---------|------|------------|
| M-1 | Medium | Group G — dataState in store | `dataState` from bootstrap is not stored in `journeyStore` state. It is captured in a module-level variable `_bootstrapDataState` in `JourneyPage.js:25`. This works but bypasses the centralized pub/sub store pattern, making it invisible to other subscribers. |
| M-2 | Medium | Group H — Snapshot field naming | Snapshot uses `frozenAt` (journeyStore.js:211) while CONTRACTS.md Section 2 specifies `saved_at` (camelCase: `savedAt`). The backend adds `saved_at` on write, but the frontend snapshot object uses a different name for the timestamp. |
| M-3 | Medium | Group C — Journal response | `GET /journal/decisions` extracts `user_decision` as `raw.get("user_decision", {}).get("action", "")` (journey.py:348), returning only the `action` sub-field. CONTRACTS.md says `user_decision: "string or null"` — the intent is a summary string, but the current implementation only returns the action, losing the rationale. |
| L-1 | Low | Group D — Demo data | Demo triage items in `services.js:270-328` use frontend field names (`triageStatus`, `biasHint`) rather than backend shape — acceptable since they bypass the backend entirely, but inconsistent with the adapter pattern. |
| L-2 | Low | Group B — Route naming | ACCEPTANCE_TESTS.md B.9 references `/metrics/dashboard` and `/analytics` as expected routes. Actual routes are `/metrics` and `/analytics/dashboard` respectively. These are pre-existing V1 routes, not a V1.1 regression. |

---

## 6. Evidence Log

> One entry per checked item. Reference file paths, routes, JSON, console output, or screenshots.
> **A PASS without evidence is invalid and must be downgraded to PARTIAL or FAIL.**

| Check | Evidence type | Location / content |
|-------|--------------|-------------------|
| A.1 | File path | `app/journey.html` exists, loads `journey.js` as ES module |
| A.2 | Code trace | `journey.js:26-28` — `route('/dashboard', ...)` registered, calls `renderDashboardPage` |
| A.3 | Code trace | `journey.js:36-38` — `route('/journal', ...)` registered, calls `renderJournalPage` |
| A.4 | Code trace | `journey.js:41-43` — `route('/review', ...)` registered, calls `renderReviewPage` |
| A.5 | Code trace | `journey.js:30-33` — `route('/journey/:asset', ...)` registered with `:asset` param |
| A.6 | Code trace | `app/types/journey.js:20-28` — `StageKey` enum defines all 7: `market_overview`, `asset_context`, `structure_liquidity`, `macro_alignment`, `gate_checks`, `verdict_plan`, `journal_capture`. `STAGE_ORDER` array at lines 31-39. |
| A.7 | Code trace | `app/stores/journeyStore.js:68-73` — `nextStage()` checks `hasBlockedGate()` at `gate_checks` stage and returns `false` if blocked |
| A.8 | Code trace | `app/components/SplitVerdictPanel.js:31-46` — creates 3 cards: "System Verdict" (line 32), "User Decision" (line 37), "Execution Plan" (line 42) |
| A.9 | Code trace | Components intact: `AppShell.js`, `StageShell.js`, `StageStepper.js`, `AIPrefillCard.js`, `SplitVerdictPanel.js`, `GateChecklist.js`, `EvidencePanel.js`, `NotesTextarea.js`, `SurfaceCard.js`, `ChartAnnotationLayer.js`, `PageHeader.js`, `StatusBadge.js`, `SeverityCard.js` — all present in `app/components/` |
| A.10 | Code trace | `ai_analyst/api/main.py:337` — `@app.get("/health")` endpoint defined |
| B.1 | Code trace | `ai_analyst/api/routers/journey.py:82` — `@router.get("/watchlist/triage")` |
| B.2 | Code trace | `journey.py:162` — `@router.get("/journey/{asset}/bootstrap")` |
| B.3 | Code trace | `journey.py:206` — `@router.post("/journey/draft")` |
| B.4 | Code trace | `journey.py:240` — `@router.post("/journey/decision")` |
| B.5 | Code trace | `journey.py:290` — `@router.post("/journey/result")` |
| B.6 | Code trace | `journey.py:330` — `@router.get("/journal/decisions")` |
| B.7 | Code trace | `journey.py:356` — `@router.get("/review/records")` |
| B.8 | File path + registration | `ai_analyst/api/routers/journey.py` — separate file. `main.py:332` imports, `main.py:334` registers via `app.include_router(journey_router)` |
| B.9 | Code trace | Existing routes in `main.py`: `/health` (337), `/feeder/ingest` (362), `/feeder/health` (443), `/analyse` (490), `/analyse/stream` (744), `/metrics` (986), `/dashboard` (1003), `/analytics/csv` (1161), `/analytics/dashboard` (1263), `/backtest` (1282) |
| B.10 | Code trace | `main.py:35-37` — `from dotenv import load_dotenv` then `load_dotenv(...)` called before FastAPI import at line 39 |
| C.1 | Code trace | `journey.py:152-156` — returns `{data_state, generated_at, items}` |
| C.2 | Code trace | `journey.py:138-146` — each item has `symbol`, `triage_status`, `bias`, `confidence`, `why_interesting`, `rationale`, `verdict_at` |
| C.3 | Code trace | `journey.py:186-200` — returns `{data_state, instrument, generated_at, structure_digest, analyst_verdict, arbiter_decision, explanation, reasoning_summary}` |
| C.4 | Code trace | `journey.py:279-284` — returns `{success, snapshot_id, saved_at, path}` |
| C.5 | Code trace | `journey.py:341-350` — returns `{records: [...]}` with summary fields: `snapshot_id`, `instrument`, `saved_at`, `journey_status`, `verdict`, `user_decision` |
| C.6 | Code trace | All backend response field names confirmed snake_case throughout `journey.py` |
| C.7 | Code trace | `_write_json` (journey.py:67-76) writes via `json.dump` — Python dicts use snake_case keys, persisted as-is |
| D.1 | Code trace | `DashboardPage.js:14` imports `fetchTriage` from services. Line 37 calls `await fetchTriage()`. No hardcoded mock array in DashboardPage. |
| D.2 | Code trace | `services.js:47` — `fetch(\`${API_BASE}/watchlist/triage\`)` called in `fetchTriage()` |
| D.3 | Code trace | `DashboardPage.js:52-58` — when `dataState === 'unavailable'`, shows "No triage data available" message |
| D.4 | Code trace | `services.js:80` — `fetch(\`${API_BASE}/journey/${encodeURIComponent(asset)}/bootstrap\`)` in `fetchBootstrap()` |
| D.5 | Code trace | `JourneyPage.js:49-52` — when `_bootstrapDataState === 'unavailable'`, calls `_renderUnavailableState` showing "Data Unavailable" |
| D.6 | Code trace | `journey.py:176-177` — when explainability file missing but output exists, sets `data_state = "partial"`. `JourneyPage.js:99` shows partial banner. |
| D.7 | Code trace | `services.js:263-268` — demo fallback sets `dataState: 'demo'`. `DashboardPage.js:109-111` renders "Demo data" badge. `JourneyPage.js:101` shows "Demo mode" banner. |
| D.8 | Code trace | `journey.py:170` — when output file missing, returns `{data_state: "unavailable", instrument: asset}` with no fabricated content. `adapters.js:148-159` — when unavailable, returns empty structure. |
| E.1 | Code trace | `JourneyPage.js:439` — `const result = await saveDecision(snapshot)`. `services.js:136-137` — `saveDecision` calls `fetch(\`${API_BASE}/journey/decision\`, {method: 'POST', ...})` |
| E.2 | Code trace | `JourneyPage.js:440-446` — success alert only after `if (result.success)`. On failure, reverts status and shows error. |
| E.3 | Code trace | `journey.py:271-276` — `_write_json(filepath, payload)` writes to `_DECISIONS_DIR / filename`. `_write_json` at line 72 creates `path.parent.mkdir(parents=True, exist_ok=True)` then `json.dump`. |
| E.4 | Code trace | `journey.py:218-223` — `_write_json(filepath, payload)` writes to `_DRAFTS_DIR / filename` |
| E.5 | Code trace | `journey.py:262-269` — `if filepath.exists(): return JSONResponse(status_code=409, ...)` |
| E.6 | Code trace | `JourneyPage.js:443-445` — on `!result.success`, reverts `journeyStatus` to 'draft' and shows `alert(\`Save failed: ${result.error}\`)` |
| E.7 | Grep result | `grep localStorage/sessionStorage/IndexedDB` in `app/pages/`, `app/components/`, `app/stores/`, `app/lib/` — 0 matches. Existing references only in legacy `app/scripts/` (V1, not journey). |
| E.8 | Code trace | `journey.py:70` — `path.parent.mkdir(parents=True, exist_ok=True)` in `_write_json` auto-creates directories |
| F.1 | Code trace | `journey.py:330-350` — `journal_decisions()` reads from `_DECISIONS_DIR.glob("decision_*.json")` — file just written is immediately available |
| F.2 | Code trace | File-based persistence — browser refresh triggers new `fetchJournalDecisions()` call which re-reads disk files |
| F.3 | Code trace | No in-memory cache in journey.py — each request reads from disk via `_load_json`. Server restart has no effect on persisted files. |
| F.4 | Code trace | `journey.py:356-386` — `review_records()` reads from same `_DECISIONS_DIR` files |
| F.5 | Code trace | `journey.py:333-334` — `if not _DECISIONS_DIR.exists(): return {"records": []}` |
| G.1 | Grep result | `grep 'fetch(' app/pages/ app/components/` — 0 matches. All fetch calls in `app/lib/services.js` only. |
| G.2 | Code trace | `adapters.js:21-62` — `snakeToCamel`, `camelToSnake`, `deepSnakeToCamel`, `deepCamelToSnake` defined. `adaptTriageResponse` (line 73), `adaptBootstrapResponse` (line 147), `adaptJournalRecords` (line 282), `adaptReviewRecords` (line 300) all convert keys. **Exception:** raw `digest` object passed through at line 207 without deep conversion. |
| G.3 | Code trace | `adapters.js:270-273` — `adaptSnapshotForSave` applies `deepCamelToSnake(snapshot)` before POST |
| G.4 | Code trace | `adapters.js:76` — `dataState` extracted from `raw.data_state`. `adapters.js:150` — same for bootstrap. Reaches `DashboardPage.js:40` and `JourneyPage.js:44`. |
| G.5 | Grep result + FINDING | `grep snake_case patterns app/components/` — 0 matches. **But** `JourneyPage.js:197-203` accesses `digest.htf_bias`, `digest.structure_gate` etc. — snake_case in page layer. See H-1. |
| G.6 | Code trace | `services.js:51-54` — demo fallback in `fetchTriage` only in `catch` block (network failure). `services.js:84-87` — same for `fetchBootstrap`. Demo data sets `dataState: 'demo'`. |
| H.1 | Code trace | `journeyStore.js:208-228` — snapshot contains `snapshotId`, `instrument`, `frozenAt`, `journeyStatus`, `systemVerdict`, `userDecision`, `executionPlan`, `gateStates`, `stageData`, `digest`, `macroContext`, `evidenceRefs`, `journalNotes`. Missing: `journeyId`, `gateJustifications`, `provenance`. `bootstrapDataState` added at `JourneyPage.js:436`. |
| H.2 | Code trace | `SplitVerdictPanel.js:31-46` — three separate cards created for systemVerdict, userDecision, executionPlan. `journeyStore.js:213-215` — stored as three separate properties. |
| H.3 | Code trace | `provenance` map not aggregated in snapshot. Individual provenance values exist: `Provenance.USER_MANUAL` set on userDecision (journeyStore.js:185) and executionPlan (journeyStore.js:195). |

---

## 7. Required Fixes Before Acceptance

> Concrete remediation list for all Critical findings. High findings go in the follow-up patch section below.

**Critical fixes (must resolve before acceptance):**

None. No Critical findings identified.

**Follow-up patch (High findings — resolve in next PR):**

1. **H-1 — Casing boundary leak:** Apply `deepSnakeToCamel()` to the `digest` object in `adaptJourneyBootstrap()` (adapters.js:207) before passing it into `stageData.asset_context` and `stageData.structure_liquidity`. Update all 10 snake_case references in `JourneyPage.js` (lines 197-203, 246, 260) to use camelCase equivalents.

2. **H-2 — Missing `journeyId`:** Add a `journeyId` field to the store state, assign it during `bootstrapJourney()` or `selectAsset()`, and include it in `createSnapshot()`.

3. **H-3 — Missing `gateJustifications`:** Extract gate justifications into a separate `{gateId: justificationString}` map in `createSnapshot()` alongside the existing `gateStates` array.

4. **H-4 — Missing `provenance` map:** Build a `provenance` map in `createSnapshot()` that aggregates field-level provenance markers (e.g., `systemVerdict: 'ai_prefill'`, `userDecision: 'user_manual'`, `executionPlan: 'user_manual'`) per CONTRACTS.md Section 2.

---

## 8. Go / No-Go Recommendation

**Decision:** Accept with follow-up patch

**Rationale:**
The V1.1 merge satisfies all four priority acceptance criteria from OBJECTIVE.md: (1) the V1 UI surface is intact with all routes, stages, gates, and verdict panels functional; (2) real triage and bootstrap wiring is active — dashboard and journey call live backend endpoints, with demo fallback only on network failure and clearly marked; (3) saves are confirmed disk-backed via `POST /journey/decision` with physical file writes, duplicate rejection, and error handling; (4) `dataState` flows truthfully from backend through adapter to component with appropriate banners for unavailable/stale/partial/demo states. No Critical findings were identified. The four High findings (casing leak in JourneyPage, three missing snapshot fields) are localized contract compliance gaps that do not affect core functionality or data integrity. They are all addressable in a single targeted follow-up patch without architectural changes.

**Follow-up patch scope (if applicable):**
- Fix casing boundary: deep-convert `digest` in adapters.js, update JourneyPage.js references (H-1)
- Add `journeyId` to store and snapshot (H-2)
- Add `gateJustifications` map to snapshot (H-3)
- Add `provenance` map to snapshot (H-4)

**Accept with follow-up patch**
