# Post-Phase-8 Repair — Diagnostic Report & Patch Plan

**Date:** 17 March 2026
**Scope:** Bounded repair/stabilisation pass, not feature expansion

---

## Part 1 — Diagnostic Report

### D-1. Issue 1 (Vite Proxy) — VERIFIED CLOSED

`ui/vite.config.ts` now contains 18 proxy entries. Cross-reference:

| Backend prefix | Proxy present | Frontend calls it |
|---|---|---|
| `/journey` | ✓ | ✓ |
| `/market-data` | ✓ (added this session) | ✓ |
| `/ops` | ✓ | ✓ |
| `/reflect` | ✓ (added this session) | ✓ |
| `/runs` | ✓ | ✓ |
| `/triage` | ✓ | ✓ |
| `/watchlist` | ✓ | ✓ |

Two frontend-only prefixes (`/journal`, `/review`) are proxied but currently 404 on the backend — that's Issue 2.

Two more frontend-only prefixes (`/analyse`, `/feeder`) are proxied and appear to have matching backend routes registered in `main.py`.

**Verdict: Issue 1 remains closed. No additional proxy gaps.**

---

### D-2. Journal / Review Contract Audit

#### Freeze Decision Write Path

| Aspect | Frontend | Backend | Match? |
|---|---|---|---|
| Request path | `POST /journey/decision` | `POST /journey/decision` | ✓ |
| ID field sent | `snapshot_id` | reads `journey_id` | **✗ MISMATCH** |
| ID fallback | — | none | — |
| Response shape | `{ success, snapshot_id?, journey_id?, saved_at, path }` | `{ success, journey_id, saved_at }` | partial |
| Storage dir | expects `_DECISIONS_DIR` | writes to `_DECISIONS_DIR` | ✓ (but never reached) |

**Bug confirmed:** Backend line 703 does `payload.get("journey_id")` — always returns `None` because the frontend sends `snapshot_id`. The guard returns `{"success": False, "error": "Missing journey_id"}` on every call. No decision file is ever written.

#### Journal Read Path

| Aspect | Frontend | Backend | Match? |
|---|---|---|---|
| Fetch path | `GET /journal/decisions` | **does not exist** | **✗ MISSING** |
| Nearest route | — | `GET /journey/journal` | different path |
| Expected response | `{ records: DecisionSnapshot[] }` | raw array of draft files | **✗ WRONG SHAPE + WRONG SOURCE** |
| Source directory | expects `_DECISIONS_DIR` | reads `_DRAFTS_DIR` | **✗ WRONG DIR** |

**Bug confirmed:** Route doesn't exist → 404. Even if it did exist, the existing `/journey/journal` reads drafts (not decisions) and returns a raw array (not an envelope).

#### Review Read Path

| Aspect | Frontend | Backend | Match? |
|---|---|---|---|
| Fetch path | `GET /review/records` | **does not exist** | **✗ MISSING** |
| Nearest route | — | `GET /journey/review` | different path |
| Expected response | `{ records: ReviewRecord[] }` where `ReviewRecord` includes `has_result` | raw array of result files | **✗ WRONG SHAPE + WRONG SOURCE** |
| Source directory | expects decisions + result linkage | reads `_RESULTS_DIR` only | **✗ WRONG DIR** |

**Bug confirmed:** Route doesn't exist → 404. The existing `/journey/review` reads results, not decision-linked review records.

#### Frontend expected field shapes (from `journalApi.ts` + test fixtures)

```
DecisionSnapshot: { snapshot_id, instrument, saved_at, journey_status, verdict, user_decision }
ReviewRecord: extends DecisionSnapshot + { has_result: boolean }
```

---

### D-3. Canonical Identifier Decision

**Locked: `snapshot_id` is the canonical public identifier.**

- Frontend already uses `snapshot_id` everywhere (payload, types, test fixtures)
- `JourneyWriteSuccess` already has `snapshot_id?` as an optional response field
- Backend `save_journey_decision` will accept `snapshot_id` as primary, `journey_id` as fallback
- Backend responses will return `snapshot_id` (not `journey_id`)
- No frontend changes required for this decision

---

### D-4. Data Source Audit

**Current state of `app/data/journeys/`:** Empty. The directories `decisions/`, `results/`, `drafts/` do not exist yet in the cloned repo (they're created at runtime on first write via `_write_json` → `path.parent.mkdir()`).

**Because Bug 2a means no decisions have ever been saved**, there is no existing data to migrate. This simplifies the fix — we're building the write path correctly from scratch, not patching existing records.

**Can current data construct the required shapes without migration?** Yes — the decision payload from the frontend already contains all fields needed to construct `DecisionSnapshot`. The `journey_status` can be hardcoded to `"frozen"` (decisions are by definition frozen). The `verdict` and `user_decision` map to `decision` and `bootstrap_summary.arbiter_decision` in the payload. `saved_at` comes from the `decided_at` timestamp.

---

### D-5. Chart Failure Diagnostic

#### 5a — Routing / fetch correctness
**Fixed.** `/market-data` proxy now exists. Requests will reach FastAPI.

#### 5b — Run-context completeness
`RunBrowserItem.instrument` is `Optional[str]`. When instrument is `null`, `CandlestickChart` receives `null` and shows "Select a run to view its chart" — that's correct guard behaviour.

The `AgentOpsPage` gates chart rendering on `selectedRunId && selectedInstrument`, so null-instrument runs correctly hide the chart. The screenshot showing `instrument: —` in the run footer confirms some runs lack instrument metadata (likely pre-instrument-dropdown triage runs).

#### 5c — Market data availability
**Instrument registry contains:** EURUSD, GBPUSD, XAGUSD, XAUUSD, XPTUSD (5 instruments, all FX/metals via Dukascopy).

**Instruments in run history from screenshots:** US30, NAS100, EURUSD, XAUUSD.

**US30 and NAS100 are NOT in the instrument registry.** Any `/market-data/US30/timeframes` or `/market-data/NAS100/timeframes` call returns 404 `INSTRUMENT_NOT_FOUND`. This is the primary chart failure cause — not a code bug, but a registry/data coverage gap.

EURUSD and XAUUSD ARE registered but still require MDO to have fetched and stored hot package CSVs. If MDO hasn't run, the backend returns `TimeframeNotFound` even for registered instruments.

#### 5d — Final classification

**No code defect.** Chart failure is caused by:
1. **Registry gap:** US30, NAS100 not in instrument registry (index instruments vs FX/metals — different data provider needed)
2. **Data availability:** Even registered instruments need MDO to have populated hot packages

No chart code changes justified. The chart pipeline (proxy → timeframe discovery → OHLCV read → render) is structurally correct.

**Deferred:** Adding US30/NAS100 to the instrument registry requires a provider that supplies index CFD data. This is a Phase 9+ scope item, not a repair.

---

### D-6. Expected-State Validation

#### Ops Health — "Health data unavailable"
**Validated as correct.** Health snapshots are written per-run. With no full analysis runs completed (all are triage-only NO_TRADE at 0.0 confidence), no health data exists. The roster structure (13 entities across Governance, Officer, Technical Analysis layers) renders independently and correctly. Banner wording is appropriate.

#### Reflect — "Some run records could not be parsed"
**Validated as correct.** 18 of 32 runs are skipped — these correspond to triage-only runs that lack the full `run_record.json` structure Reflect expects. The warning is accurate. As full-context runs accumulate, the skipped ratio decreases. Not a bug.

#### Sparse dashboard values
**Validated as correct.** Missing stance alignment (`—`), low confidence values (0.04–0.05), and null fields all trace back to triage-only runs with no chart data → no real analyst reasoning → no stance/confidence to aggregate.

---

### D-7. Test Baseline (from session handoff)

| Suite | Count | Pre-existing failures |
|---|---|---|
| Backend (`analyst-tests`) | 1061 | 0 (resolved in CI) |
| Frontend (`vitest`) | 401 | 5 (journey tests, pre-Phase 8) |

---

### D-8. Smallest Patch Set

| # | File | Action | Lines (est.) | Risk |
|---|---|---|---|---|
| 1 | `ai_analyst/api/routers/journey.py` | Fix `save_journey_decision` to accept `snapshot_id` | ~15 changed | low |
| 2 | `ai_analyst/api/routers/journey.py` | Add `GET /journal/decisions` endpoint | ~30 new | low |
| 3 | `ai_analyst/api/routers/journey.py` | Add `GET /review/records` endpoint | ~35 new | low |
| 4 | `tests/test_journal_review_endpoints.py` | New test file for 3 endpoints | ~120 new | none |
| — | `ui/vite.config.ts` | Already fixed (verify only) | 0 | — |
| — | Chart code | No changes | 0 | — |

**Total:** ~200 lines, all backend, one file modified + one test file created. Zero frontend changes needed (frontend contract is already correct — the backend is wrong).

---

## Part 2 — Patch Plan

Ordered easiest → hardest. Each step is independently testable.

### Step 1 — Fix decision save identifier (5 min)

**File:** `ai_analyst/api/routers/journey.py`, `save_journey_decision` function (line 700)

**Change:**
- Accept `snapshot_id` as primary identifier, `journey_id` as fallback
- File saved as `{snapshot_id}.json`
- Add `saved_at` / `decided_at` timestamp
- Map frontend payload fields to `DecisionSnapshot`-compatible stored shape:
  - `snapshot_id` → from payload
  - `instrument` → from payload
  - `saved_at` → computed via `_now_iso()`
  - `journey_status` → hardcode `"frozen"`
  - `verdict` → extract from `bootstrap_summary.arbiter_decision` or `bootstrap_summary.arbiter_bias` 
  - `user_decision` → from `payload["decision"]`
- Return `{ success: True, snapshot_id, saved_at }` (not `journey_id`)

**Backwards compat:** If `snapshot_id` is absent but `journey_id` is present, use `journey_id`. Both absent → error unchanged.

**Verify:** POST returns `{ success: true, snapshot_id: "...", saved_at: "..." }`. File appears in `app/data/journeys/decisions/`.

---

### Step 2 — Add `GET /journal/decisions` endpoint (10 min)

**File:** `ai_analyst/api/routers/journey.py`

**Route:** `GET /journal/decisions`

**Behaviour:**
1. Read all `.json` files from `_DECISIONS_DIR`
2. For each file, extract the `DecisionSnapshot` fields:
   - `snapshot_id`, `instrument`, `saved_at`, `journey_status`, `verdict`, `user_decision`
3. Sort by `saved_at` descending
4. Return `{ records: [...] }`

**Empty state:** If directory doesn't exist or is empty, return `{ records: [] }` (not error — matches UI_CONTRACT §11.4 graceful empty pattern).

**Verify:** GET returns `{ records: [] }` when empty, `{ records: [DecisionSnapshot, ...] }` when populated.

---

### Step 3 — Add `GET /review/records` endpoint (15 min)

**File:** `ai_analyst/api/routers/journey.py`

**Route:** `GET /review/records`

**Behaviour:**
1. Read all `.json` files from `_DECISIONS_DIR` (same source as Journal)
2. For each decision, check if `_RESULTS_DIR / {snapshot_id}.json` exists → set `has_result`
3. Build `ReviewRecord` = `DecisionSnapshot` fields + `has_result: bool`
4. Sort by `saved_at` descending
5. Return `{ records: [...] }`

**Empty state:** Same graceful empty pattern: `{ records: [] }`.

**Verify:** GET returns records with correct `has_result` linkage.

---

### Step 4 — Backend tests (20 min)

**File:** `tests/test_journal_review_endpoints.py` (new)

Tests to write:

| # | Test | What it covers |
|---|---|---|
| 1 | `test_save_decision_with_snapshot_id` | Primary ID path works, file written, response correct |
| 2 | `test_save_decision_with_journey_id_fallback` | Legacy fallback works |
| 3 | `test_save_decision_missing_both_ids` | Error response unchanged |
| 4 | `test_save_decision_duplicate_409` | Idempotency guard if decision already exists |
| 5 | `test_get_journal_decisions_empty` | Returns `{ records: [] }` when no decisions |
| 6 | `test_get_journal_decisions_populated` | Returns correct DecisionSnapshot shape |
| 7 | `test_get_journal_decisions_sorted` | Most recent first |
| 8 | `test_get_review_records_empty` | Returns `{ records: [] }` when no decisions |
| 9 | `test_get_review_records_with_result` | `has_result: true` when result file exists |
| 10 | `test_get_review_records_without_result` | `has_result: false` when result file absent |
| 11 | `test_existing_journey_endpoints_unchanged` | Regression: `/journey/journal`, `/journey/review`, `/journey/draft` still work |

Use `tmp_path` fixture for isolated directory testing. Mock `_DECISIONS_DIR` / `_RESULTS_DIR` via dependency injection or monkeypatch.

---

### Step 5 — Smoke test and expected-state sign-off (5 min)

This is a manual verification step (David does this locally after applying patches):

- [ ] Freeze a decision in Journey Studio → confirm file written to `decisions/`
- [ ] Open Journal tab → decisions load
- [ ] Open Review tab → records load with `has_result` correctly reflecting result presence
- [ ] Ops Health → still shows "Health data unavailable" (expected)
- [ ] Reflect → still shows parse warning with skipped count (expected)
- [ ] Chart in Ops Run for XAUUSD → test if timeframes load (depends on MDO data)
- [ ] Chart in Ops Run for US30 → confirm graceful "instrument not found" (expected, not in registry)

---

### Step 6 — Doc closure (5 min)

Update:
- `docs/AI_TradeAnalyst_Progress.md` — record repair pass completion
- `docs/technical_debt.md` — add TD entry for US30/NAS100 instrument registry gap

---

## Part 3 — Deferred / Not-This-Pass Items

| Item | Why deferred | Suggested phase |
|---|---|---|
| US30 / NAS100 in instrument registry | Needs index CFD data provider (not Dukascopy) | Phase 9 |
| Ops Health snapshots | Requires real analysis runs, not a code fix | Operational — build run volume |
| Reflect skipped-run ratio | Resolves naturally with full-context runs | Operational |
| 5 pre-existing frontend journey test failures | Pre-date Phase 8, out of repair scope | Micro-PR |
| Existing `/journey/journal` and `/journey/review` cleanup | Still functional for internal/debug use, don't break | Optional future cleanup |

---

## Contract Summary (for copy into locked decisions)

```
CANONICAL ID:      snapshot_id (journey_id = backend fallback only)
WRITE:             POST /journey/decision  → accepts snapshot_id, writes to _DECISIONS_DIR
JOURNAL READ:      GET  /journal/decisions → { records: DecisionSnapshot[] }
REVIEW READ:       GET  /review/records    → { records: ReviewRecord[] }
DECISION SHAPE:    { snapshot_id, instrument, saved_at, journey_status, verdict, user_decision }
REVIEW SHAPE:      DecisionSnapshot + { has_result: boolean }
EMPTY STATE:       { records: [] } — not error
EXISTING ROUTES:   /journey/journal and /journey/review PRESERVED (no breaking changes)
CHART:             No code changes — registry/data gap, not code defect
```
