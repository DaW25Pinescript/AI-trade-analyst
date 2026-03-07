# ACCEPTANCE_TESTS.md — Post-Merge Audit, Trade Ideation Journey V1.1

Each check must be marked PASS / FAIL / PARTIAL with evidence. A check marked PASS without evidence is invalid.

---

## Group A — V1 UI non-regression

Run these first. If any fail, the audit result is FAIL regardless of other findings.

**A.1** — UI loads at `http://127.0.0.1:8080/journey.html` with no blocking console errors  
**A.2** — Dashboard route (`#/dashboard`) renders without errors  
**A.3** — Journal route (`#/journal`) renders without errors  
**A.4** — Review route (`#/review`) renders without errors  
**A.5** — At least one asset journey route opens (`#/journey/XAUUSD` or equivalent)  
**A.6** — All seven stage keys are present: `market_overview`, `asset_context`, `structure_liquidity`, `macro_alignment`, `gate_checks`, `verdict_plan`, `journal_capture`  
**A.7** — Gate enforcement: setting any gate to `blocked` prevents forward navigation past `gate_checks`  
**A.8** — `SplitVerdictPanel` renders three visually distinct panels: System Verdict / User Decision / Execution Plan  
**A.9** — No unintended visual drift — component names from ARCHITECTURE.md are intact  
**A.10** — FastAPI backend responds at `http://127.0.0.1:8000/health`  

Evidence required: route screenshots or console output, OpenAPI health confirmation.

---

## Group B — Backend endpoint existence

**B.1** — `GET /watchlist/triage` exists and returns HTTP 200  
**B.2** — `GET /journey/{asset}/bootstrap` exists and returns HTTP 200  
**B.3** — `POST /journey/draft` exists and accepts a JSON body  
**B.4** — `POST /journey/decision` exists and accepts a JSON body  
**B.5** — `POST /journey/result` exists and accepts a JSON body  
**B.6** — `GET /journal/decisions` exists and returns HTTP 200  
**B.7** — `GET /review/records` exists and returns HTTP 200  
**B.8** — Journey router is a separate file (e.g. `ai_analyst/api/routers/journey.py`) registered in `main.py`  
**B.9** — Existing routes still respond — verify exact route names from live OpenAPI docs at `http://127.0.0.1:8000/docs`, do not assume from memory. Expected at minimum: `/health`, `/feeder`, `/analyse`, `/metrics/dashboard`, `/analytics`, `/backtest` — but confirm actual paths from the running server.  
**B.10** — `load_dotenv()` is called before any config or client init in `ai_analyst/api/main.py`  

Evidence required: OpenAPI route listing (`/docs`), file path confirmation.

---

## Group C — Backend response shape conformance

Each endpoint response is checked against CONTRACTS.md Section 1.

**C.1** — `GET /watchlist/triage` response includes `data_state`, `generated_at`, and `items` array  
**C.2** — Each triage item includes `symbol`, `triage_status`, `bias`, `confidence`, `why_interesting`, `rationale`, `verdict_at`  
**C.3** — `GET /journey/{asset}/bootstrap` response includes `data_state`, `instrument`, `generated_at`, `analyst_verdict`  
**C.4** — `POST /journey/decision` response includes `success`, `snapshot_id`, `saved_at`, `path`  
**C.5** — `GET /journal/decisions` response returns `{ records: [...] }` with summary fields only — not full snapshot body  
**C.6** — All backend response field names are `snake_case`  
**C.7** — All persisted JSON files on disk use `snake_case` field names  

Evidence required: actual response JSON samples or file contents.

---

## Group D — Triage and bootstrap truth

**D.1** — Dashboard no longer imports or references a hardcoded mock triage array in the active code path  
**D.2** — Service layer calls `GET /watchlist/triage` on dashboard load — confirmed via network inspection or code trace  
**D.3** — When `analyst/output/` is empty, dashboard shows a truthful unavailable/empty state — not placeholder cards  
**D.4** — Begin Journey triggers a real bootstrap read via `GET /journey/{asset}/bootstrap`  
**D.5** — When `analyst/output/{asset}_multi_analyst_output.json` does not exist, journey opens with a visible unavailable state — not fabricated content  
**D.6** — When output file exists but explainability file is missing, bootstrap shows `partial` data state visibly  
**D.7** — Demo mode fallback shows a visible "Demo data" indicator — not silent substitution  
**D.8** — No analyst reasoning text is fabricated when the upstream source is absent  

Evidence required: code path trace, UI screenshot or console evidence, response JSON.

---

## Group E — Save semantics

This group is highest priority. A single FAIL here blocks the entire audit.

**E.1** — Save action calls `POST /journey/decision` through the service layer — not only `store.createSnapshot()`  
**E.2** — Save success state is only shown after backend returns `{ success: true }` — not on store mutation alone  
**E.3** — `POST /journey/decision` with a valid body creates a physical file at `app/data/journeys/decisions/decision_<id>.json`  
**E.4** — `POST /journey/draft` creates a file at `app/data/journeys/drafts/journey_<id>.json`  
**E.5** — A duplicate `snapshot_id` POST returns an error — the existing file is not overwritten  
**E.6** — If backend POST returns `success: false`, UI shows an explicit error — no silent fallback to "saved"  
**E.7** — `localStorage`, `sessionStorage`, and `IndexedDB` are not used as the source of truth for saved records  
**E.8** — `app/data/journeys/` directories are created automatically if they do not exist — no manual setup required  

Evidence required: file existence on disk post-save, code path showing POST before success state, duplicate rejection test.

---

## Group F — Persistence durability

**F.1** — Saved decision record appears in `GET /journal/decisions` immediately after POST  
**F.2** — Record is still returned after full browser refresh  
**F.3** — Record is still returned after stopping and restarting the FastAPI server  
**F.4** — Review page reads the same record from `GET /review/records`  
**F.5** — Empty-state behavior is truthful when `app/data/journeys/decisions/` is empty — no fake records  

Evidence required: actual GET response JSON after each durability test.

---

## Group G — Service and adapter architecture

**G.1** — Components do not call `fetch` directly — all transport goes through `app/lib/services.js`  
**G.2** — `app/lib/adapters.js` is the only file that maps `snake_case` backend fields to `camelCase` UI shapes  
**G.3** — `app/lib/adapters.js` is the only file that converts `camelCase` store objects to `snake_case` before POST  
**G.4** — `data_state` is present in adapter output and reaches component render layer  
**G.5** — No component directly references a `snake_case` field name  
**G.6** — Service layer uses demo fallback only when backend is unreachable — not as a cover for missing data  

Evidence required: code trace through service → adapter → store → component for at least one data flow.

---

## Group H — Snapshot completeness

**H.1** — `decisionSnapshot` contains all required fields: `snapshot_id`, `journey_id`, `instrument`, `saved_at`, `journey_status`, `stage_data`, `gate_states`, `gate_justifications`, `system_verdict`, `user_decision`, `execution_plan`, `provenance`, `bootstrap_data_state`  
**H.2** — `systemVerdict`, `userDecision`, and `executionPlan` are separate objects — not merged  
**H.3** — `provenance` map is present with at least one field marked  

Evidence required: saved JSON file contents showing field structure.

---

## Acceptance gate

| Result | Condition |
|--------|-----------|
| **PASS** | Groups A–H all pass, no Critical or High findings |
| **PASS WITH ISSUES** | No Critical findings, all High findings have a scoped follow-up patch |
| **FAIL** | Any Critical finding, OR Group A fails, OR Group E fails |

The merge is not called accepted unless it meets PASS or PASS WITH ISSUES criteria.
