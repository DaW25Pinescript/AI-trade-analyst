# ACCEPTANCE_TESTS.md — Trade Ideation Journey V1.1

A phase is only complete when all tests in its group pass. Report pass/fail per group before declaring done.

---

## Group 0 — Regression (run first, before any new work)

**T0.1** — UI loads at `http://localhost:8080/journey.html` with no console errors  
**T0.2** — All seven journey stages navigate correctly  
**T0.3** — Gate enforcement still blocks forward navigation when a gate is `blocked`  
**T0.4** — `SplitVerdictPanel` renders three visually distinct panels  
**T0.5** — FastAPI backend responds at `http://localhost:8000/health`  

If any Group 0 test fails, stop and report before proceeding.

---

## Group 1 — Backend endpoint existence

**T1.1** — `GET /watchlist/triage` returns HTTP 200 with a valid JSON response  
**T1.2** — `GET /journey/XAUUSD/bootstrap` returns HTTP 200 with a valid JSON response  
**T1.3** — `POST /journey/draft` accepts a JSON body and returns `{ success, journey_id, saved_at, path }`  
**T1.4** — `POST /journey/decision` accepts a JSON body and returns `{ success, snapshot_id, saved_at, path }`  
**T1.5** — `POST /journey/result` accepts a JSON body and returns `{ success, snapshot_id, saved_at, path }`  
**T1.6** — `GET /journal/decisions` returns `{ records: [...] }`  
**T1.7** — `GET /review/records` returns `{ records: [...] }`  

---

## Group 2 — Backend data state correctness

**T2.1** — When `analyst/output/` is empty, `GET /watchlist/triage` returns `{ data_state: "unavailable", items: [] }` — not an error, not fake items  
**T2.2** — When `analyst/output/XAUUSD_multi_analyst_output.json` does not exist, `GET /journey/XAUUSD/bootstrap` returns `{ data_state: "unavailable", instrument: "XAUUSD" }`  
**T2.3** — When output file exists but explainability file is missing, bootstrap returns `data_state: "partial"`  
**T2.4** — When output files exist, bootstrap returns `data_state: "live"` and populates real fields  
**T2.5** — `POST /journey/decision` with valid body creates a file at `app/data/journeys/decisions/decision_<id>.json`  
**T2.6** — File created by T2.5 survives a server restart and is returned by `GET /journal/decisions`  
**T2.7** — `POST /journey/decision` with same `snapshot_id` twice returns an error on the second call (immutability rule)  

---

## Group 3 — Frontend service layer wiring

**T3.1** — Dashboard no longer imports or calls hardcoded mock array — data flows through service layer  
**T3.2** — Service layer calls `GET /watchlist/triage` on dashboard load  
**T3.3** — Service layer calls `GET /journey/{asset}/bootstrap` when Begin Journey is triggered  
**T3.4** — Save action calls `POST /journey/decision` — not only `store.createSnapshot()`  
**T3.5** — Save success message only appears after backend returns `{ success: true }`  
**T3.6** — If backend POST returns `success: false`, UI shows explicit error — no silent fallback  

---

## Group 4 — Data state UX

**T4.1** — When triage returns `unavailable`, dashboard shows a truthful empty state — not placeholder cards  
**T4.2** — When bootstrap returns `unavailable`, Begin Journey shows a blocking unavailable state  
**T4.3** — When bootstrap returns `partial`, journey opens with a visible partial-data banner  
**T4.4** — When service layer falls back to demo mode, every affected card/panel shows a visible "Demo data" indicator  
**T4.5** — `data_state` is never dropped between backend response and component render  

---

## Group 5 — Persistence integrity

**T5.1** — Saved decision record appears in `GET /journal/decisions` immediately after POST  
**T5.2** — Journal page lists that record after a full browser refresh  
**T5.3** — Journal page lists that record after stopping and restarting the FastAPI server  
**T5.4** — Review page reads the same saved record  
**T5.5** — `app/data/journeys/` directories are created automatically on first write — no manual setup required  
**T5.6** — `decisionSnapshot` contains all required fields: ids, instrument, timestamps, stage_data, gate_states, system_verdict, user_decision, execution_plan, provenance, bootstrap_data_state  

---

## Group 6 — Integrity and non-regression

**T6.1** — V1 visual design is unchanged — no unintended style drift  
**T6.2** — No blocking console errors introduced  
**T6.3** — `systemVerdict`, `userDecision`, and `executionPlan` remain separate objects in saved snapshot — not merged  
**T6.4** — Existing FastAPI routes (`/health`, `/feeder`, `/analyse`, `/metrics`, `/analytics`, `/backtest`) still respond correctly  
**T6.5** — New Journey router is a separate file registered in `main.py` — existing routes are unmodified  
**T6.6** — `load_dotenv()` is called before any config init in `ai_analyst/api/main.py`  

---

## Recommended PR sequence

| PR | Groups to pass |
|----|---------------|
| PR 1 — Real triage/bootstrap wiring | 0, 1, 2 (T2.1–T2.4), 3 (T3.1–T3.3), 4 |
| PR 2 — Local disk persistence | 2 (T2.5–T2.7), 3 (T3.4–T3.6), 5 |
| PR 3 — Hardening | 6 (all) |
