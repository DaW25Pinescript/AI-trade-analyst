# Repo Audit — AI Trade Analyst

**Branch:** `claude/audit-repo-branches-Y2rjV`
**Date:** 2026-02-24
**Scope:** Full repository health check — branches, code state, outstanding issues, readiness for next milestone.

---

## Branch Status

| Branch | State |
|---|---|
| `origin/main` | Up to date — all PRs merged, latest commit `374f254` |
| `claude/audit-repo-branches-Y2rjV` | Aligned with `origin/main` (current working branch) |
| `master` (local only) | **6 commits behind `origin/main`** — stale, needs updating |

### Action required: update local `master`

Local `master` has not been fast-forwarded since PR #9 (`3448deb`). It is missing:

- PR #10 — `claude/review-repo-structure-Semef` (docs: code review findings)
- PR #11 — `codex/review-repo-changes-and-fixes` (runtime sync/output + persistence fixes)
- PR #6 — `codex/create-app/releases-and-move-milestone-files` (milestone reorganisation)

**Fix:**

```bash
git checkout master
git pull origin main
```

No feature branches remain open. All prior development branches were merged via PRs and can be considered clean.

---

## Test Suite

All 6 tests pass against current `origin/main` HEAD:

```
# pass 6
# fail 0
# duration_ms ~157ms
```

Tests cover: enum stability, metrics engine, calibration inputs, deterministic gate scoring, confluence score parsing.

---

## Issues Fixed Since Previous Review (PR #11)

The previous code review (`docs/code_review.md`, `claude/review-repo-structure-Semef`) identified 16 issues. PR #11 resolved 5 of them:

| # | Issue | Status |
|---|---|---|
| 1 | Import name mismatch in `storage_indexeddb.js` | ✅ Fixed — now uses `loadLocalState`/`saveLocalState` |
| 2 | `syncOutput` implicit global dependency | ✅ Fixed — extracted to `ui/sync_output.js` module with `setSyncOutputHandler` pattern |
| 6 | Null-unsafe `noTradeToggle` access in `prompt_ticket.js` | ✅ Fixed — uses `?.checked ?? false` |
| 11 | FileReader missing `onerror` handler in `form_bindings.js` | ✅ Fixed — alert on read failure |
| 13 | PDF export `setTimeout(300)` race condition | ✅ Fixed — uses `w.onload` callback |

---

## Outstanding Issues (from previous review, not yet addressed)

These are still present in the codebase as of this audit.

### Critical

**Issue 3 & 4 — `export_json_backup.js`: hardcoded ticket fields + incomplete `decisionMode`**

`buildTicketSnapshot()` hardcodes `entryType`, `entryTrigger`, `confirmationTF`, `timeInForce`, `maxAttempts`, `stop.logic`, `ticketType`, and all price fields. `decisionMode` is only ever `'WAIT'` or `'CONDITIONAL'` — never `'LONG'` or `'SHORT'`.

These fields are planned as UI controls in the G2 Test/Prediction Mode step (see `docs/V3_G2_notes.md`). Once the G2 HTML is integrated into the modular app, `export_json_backup.js` must be updated to read from those DOM elements (`#decisionMode`, `#entryType`, `#entryTrigger`, `#confTF`, `#stopLogic`, `#timeInForce`, `#maxAttempts`).

**Current impact:** Every JSON export silently contains wrong field values. Schema validation passes because the hardcoded values are valid enum members.

---

### High

**Issue 5 & 6 — Stub functions not wired to `window`**

Three modules export stub functions that are never exposed to the UI:

| Module | Function | State |
|---|---|---|
| `generators/prompt_aar.js` | `buildAARPrompt()` | Returns placeholder string |
| `generators/prompt_weekly.js` | `buildWeeklyPrompt()` | Returns placeholder string |
| `exports/export_csv.js` | `exportCSV()` | `alert()` only |

Additionally, `exportJSONBackup` and `importJSONBackup` from `export_json_backup.js` and `import_json_backup.js` are imported nowhere in `main.js` and not assigned to `window`. If any HTML button `onclick` attributes reference these by name, they will throw `ReferenceError` at runtime.

**Recommendation:** Either wire to `window` in `main.js` for G2, or add a comment in each stub noting the target milestone. Do not leave them silently unreachable.

---

### Medium

**Issue 8 — `migrations.js` has no version check**

`migrateState()` validates that the payload is an object then returns it unchanged. There is no `schemaVersion` inspection. When the schema changes (planned for later milestones), old backups will pass through without migration and fail downstream validation.

**Recommendation:** Add a `payload.ticket?.schemaVersion` check now, even if the only action for v1.0.0 is a no-op. This makes future migration additions a one-line addition rather than a structural change.

---

**Issue 9 — Test suite tests reimplemented gate logic, not `gates.js`**

`tests/test_scoring.js` reimplements the gate evaluation as a pure function and tests that. The actual `gates.js` `evaluateGate()` function mutates DOM elements and returns nothing — it is untestable in Node. The tests pass but do not verify the live app's behaviour.

**Recommendation (G3 or later):** Extract the decision logic from `gates.js` into a pure exported function `computeGateDecision(ptcState, noTradeOK) -> 'WAIT' | 'CAUTION' | 'PROCEED'`. The UI function calls the pure function and applies the result to the DOM. Tests import the pure function directly.

---

**Issue 10 — Enum definitions duplicated, no cross-check test**

Enum arrays exist in both `docs/schema/*.schema.json` and `app/scripts/schema/backup_validation.js`. They can drift silently. `test_enums.js` tests only the JS-side enums.

**Recommendation:** Add a test in `test_enums.js` that reads `docs/schema/ticket.schema.json` and `docs/schema/aar.schema.json` via `fs.readFileSync` and asserts the enum arrays match the JS-side constants.

---

**Issue 12 — `buildAARStub()` hardcodes AAR outcome fields**

The AAR stub in `export_json_backup.js` hardcodes `outcomeEnum: 'MISSED'`, `verdictEnum: 'PROCESS_GOOD'`, all prices at `0`, and `notes: 'AAR not completed yet.'`. These are exported into backup JSON and re-imported as if they were real data.

This is acceptable as a placeholder until the AAR form is built, but should be clearly marked in the exported JSON as a draft/stub (e.g., a `stubAAR: true` flag) so downstream tooling or future migrations can identify and skip it.

---

**Issue 15 — `report_html.js` reads DOM directly**

`_buildReportHTML()` reads from `#outputText` rather than taking the prompt as a parameter. This couples the report generator to a specific DOM element and blocks testing in Node or headless environments.

---

## Documentation Quality Note

`docs/V3_G2_notes.md` contains a raw LLM conversation log rather than structured design documentation. The G2 feature description (Test/Prediction Mode card) is embedded in a chat response with meta-commentary ("Your move, captain"). This is fine as a working note, but the actual G2 HTML structure it describes has not yet been integrated into the modular `app/` codebase — the current `app/index.html` is still G1.

The G2 milestone is the next development priority.

---

## Readiness Summary

| Area | Status |
|---|---|
| Test suite | Green — 6/6 pass |
| Core import graph | Clean — no broken imports |
| `main.js` `window` bindings | Complete for current G1 UI |
| `storage_indexeddb.js` | Fixed and stable |
| `form_bindings.js` | Fixed and stable |
| `export_json_backup.js` | Partially broken (hardcoded fields — see above) |
| `migrations.js` | Stub — acceptable for v1.0.0, needs version check before G2 schema changes |
| Local `master` branch | Stale — needs fast-forward to `origin/main` |
| Open feature branches | None — all merged |

**The repo is ready for G2 development.** The primary outstanding action before starting G2 is to update `export_json_backup.js` to read from the new G2 form fields once the G2 Test Mode card is integrated into `app/index.html`.

---

## Recommended Next Steps

1. Fast-forward local `master` to `origin/main`.
2. Integrate the G2 Test/Prediction Mode card into `app/index.html` (and modular scripts as needed).
3. Update `export_json_backup.js` to read `decisionMode`, `entryType`, `entryTrigger`, `confirmationTF`, `timeInForce`, `maxAttempts`, `stop.logic`, `ticketType` from the new G2 DOM elements.
4. Wire `exportJSONBackup` and `importJSONBackup` to `window` in `main.js`.
5. Add `schemaVersion` check to `migrations.js`.
6. Add enum cross-check test (JS enums vs JSON schema) to `test_enums.js`.
