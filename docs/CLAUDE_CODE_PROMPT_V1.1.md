# Claude Code Prompt — Trade Ideation Journey V1.1

## Context

V1 UI is accepted visually and runs at `http://localhost:8080/journey.html`. All data is currently placeholder/demo. The FastAPI backend runs at port 8000. A local Claude proxy runs at port 8317.

This phase makes the system real: real data reads, real disk persistence, real saves.

Do not redesign the UI. Do not touch stage order, gate logic, or visual language.

---

## Read these files before writing any code

In this order:

1. `OBJECTIVE.md` — what V1.1 is and is not
2. `CONTRACTS.md` — all endpoint shapes, snapshot shape, data_state values, adapter rules
3. `CONSTRAINTS.md` — hard rules: no redesign, no invented data, no browser-only persistence
4. `ACCEPTANCE_TESTS.md` — exit criteria per group; a phase is done only when its tests pass
5. `CLAUDE.md` — implementation working agreement (audit-before-build, transport constraint, visual language)

---

## Stack (confirmed)

| Port | Service |
|------|---------|
| 8080 | UI — vanilla ES modules, `python -m http.server` |
| 8000 | FastAPI backend — `ai_analyst/api/main.py` |
| 8317 | Local Claude proxy — OpenAI-compatible |

---

## What already exists — do not rebuild

**Backend (existing routes — do not modify):**
- `/health`, `/feeder`, `/analyse`, `/analyse-stream`, `/metrics/dashboard`, `/analytics`, `/backtest`, `/plugins`

**Frontend (existing — extend, do not redesign):**
- `app/lib/services.js` — service layer, Pattern A + demo fallback
- `app/lib/adapters.js` — adapter layer
- `app/stores/journeyStore.js` — pub/sub store, in-memory snapshot
- `app/lib/router.js` — hash-based routing
- All component files under `app/components/`

---

## Casing convention (locked)

| Layer | Convention |
|-------|-----------|
| Backend — FastAPI models, API responses, disk JSON | `snake_case` |
| Frontend — JS store, component props, domain state | `camelCase` |
| Adapters — `app/lib/adapters.js` | Explicit translation boundary, converts both ways |

- Adapters convert `snake_case` → `camelCase` on every read from the backend
- Adapters convert `camelCase` → `snake_case` on every save payload before POST
- Components never reference `snake_case` field names directly
- See CONTRACTS.md Section 5 for the full mapping table

---

## Required work

### Backend — add Journey router

Create `ai_analyst/api/routers/journey.py` with these endpoints:

```
GET  /watchlist/triage
GET  /journey/{asset}/bootstrap
POST /journey/draft
POST /journey/decision
POST /journey/result
GET  /journal/decisions
GET  /review/records
```

Register it in `ai_analyst/api/main.py`. Do not modify existing routes.

**Data sources:**
- Triage and bootstrap: read from `analyst/output/` JSON files
- Saves: write to `app/data/journeys/drafts/`, `decisions/`, `results/`
- Directories created automatically on first write

**Rules:**
- If `analyst/output/` is empty, return `data_state: "unavailable"` — not an error, not fake data
- Decision snapshots are immutable — reject duplicate `snapshot_id`
- Return `success: false` with an `error` field if any write fails

Also confirm `load_dotenv()` is called early in `ai_analyst/api/main.py` — before any config or client init.

### Frontend — wire service layer

Update `app/lib/services.js`:
- `fetchTriage()` → calls `GET /watchlist/triage`
- `fetchBootstrap(asset)` → calls `GET /journey/{asset}/bootstrap`
- `saveDraft(state)` → calls `POST /journey/draft`
- `saveDecision(snapshot)` → calls `POST /journey/decision`
- `saveResult(snapshot)` → calls `POST /journey/result`
- `fetchJournalDecisions()` → calls `GET /journal/decisions`
- `fetchReviewRecords()` → calls `GET /review/records`

Demo fallback only when backend is unreachable — set `data_state: "demo"` on returned shape. Never silently substitute demo data for missing real data.

Update `app/lib/adapters.js`:
- Accept sparse/partial payloads without throwing
- Pass `data_state` through to the UI shape — never drop it
- Do not invent analysis text for missing fields

### Frontend — data state UX

Add visible states for each `data_state` value:
- `unavailable` → empty state (dashboard) or blocking state (journey)
- `partial` → amber banner, journey may continue
- `stale` → staleness indicator on cards / amber banner in stage
- `demo` → "Demo data" badge on each affected card or panel
- `error` → error state, block progression

### Frontend — real save behavior

Update save/freeze action:
1. Call `saveDecision(snapshot)` via service layer
2. Await confirmed `{ success: true }` from backend
3. Only then show success state
4. Show explicit error if backend returns `success: false`
5. Remove any path that shows "Saved successfully" on in-memory mutation alone

Update journal and review pages to call `fetchJournalDecisions()` and `fetchReviewRecords()` on mount.

---

## Persistence layout (locked)

```
app/data/journeys/
  drafts/     journey_<journeyId>.json
  decisions/  decision_<snapshotId>.json
  results/    result_<snapshotId>.json
```

---

## Recommended sequence

**PR 1 — Real triage/bootstrap wiring**
- Add backend Journey router with read endpoints
- Wire frontend service layer to triage and bootstrap
- Add data state UX (loading / unavailable / partial / stale / demo)
- Pass: Group 0, Group 1 (T1.1–T1.2), Group 2 (T2.1–T2.4), Group 3 (T3.1–T3.3), Group 4

**PR 2 — Local disk persistence**
- Add backend write endpoints (draft, decision, result)
- Add backend read endpoints (journal, review)
- Wire frontend save action to backend POST
- Wire journal + review pages to backend GET
- Pass: Group 2 (T2.5–T2.7), Group 3 (T3.4–T3.6), Group 5

**PR 3 — Hardening**
- Save/load validation
- Partial data handling improvements
- Persistence error clarity
- Refresh/reopen verification
- Pass: Group 6 (all)

---

## Done criteria

Report pass/fail per acceptance test group before declaring any PR complete.

A PR is complete only when:
- Its test groups pass
- No Group 0 regressions introduced
- No unintended style or routing changes
- No fake data paths remain active without `data_state: "demo"` marker
- No `success: true` returned for in-memory-only operations

---

## Hard constraints (summary)

- No UI redesign
- No invented payload fields
- No browser-only persistence (no localStorage, sessionStorage, IndexedDB as source of truth)
- No direct Python calls from browser
- No collapse of `systemVerdict` / `userDecision` / `executionPlan`
- No new product surfaces outside defined scope
- Do not modify existing FastAPI routes
