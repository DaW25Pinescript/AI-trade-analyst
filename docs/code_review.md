# Code Review — AI Trade Analyst

**Branch:** `claude/review-repo-structure-Semef`
**Date:** 2026-02-23
**Scope:** Full repository review (all JS modules, schemas, tests, documentation)

---

## Repository Overview

53 files total across a static browser-only application. No build tools, no npm dependencies. The architecture is modular ES6 with explicit `import`/`export`, state persisted via IndexedDB (localStorage fallback), and schema-governed JSON payloads for trade tickets and AARs.

The Codex-assisted reorganisation has produced a clean directory layout and a well-documented roadmap. The structure is solid. The issues below are implementation-level findings, not structural complaints.

---

## Critical Issues (fix before next milestone)

### 1. Import name mismatch — `storage_indexeddb.js`

**File:** `app/scripts/state/storage_indexeddb.js` line 5

```js
import { loadState, saveState } from './storage_local.js';
```

`storage_local.js` exports `loadLocalState` and `saveLocalState`. The names don't match. This module will throw a runtime error on load, silently breaking IndexedDB persistence for every user.

**Fix:** Change the import to match the actual export names:

```js
import { loadLocalState, saveLocalState } from './storage_local.js';
```

---

### 2. `syncOutput` called without import — `form_bindings.js`

**File:** `app/scripts/ui/form_bindings.js` lines 6, 16, 23, 72, 78

`syncOutput()` is called five times but is never imported. It is only defined in `main.js` and attached to `window` there. This works in the browser because `main.js` executes first, but it is a hidden runtime dependency that will break:
- any test that imports `form_bindings.js` in isolation
- any future module bundler that removes globals

**Fix:** Add an explicit import at the top of `form_bindings.js`:

```js
import { syncOutput } from './main.js';
```

Or, if circular imports need to be avoided, pass `syncOutput` as a parameter when initialising form bindings.

---

### 3. `buildTicketSnapshot()` uses hardcoded placeholder values — `export_json_backup.js`

**File:** `app/scripts/exports/export_json_backup.js` lines 17–65

The function that serialises the trade ticket to JSON reads a handful of values from the DOM but hardcodes the rest:

| Field | Hardcoded Value |
|---|---|
| `entryType` | `'Limit'` |
| `entryTrigger` | `'Pullback to zone'` |
| `confirmationTF` | `'15m'` |
| `timeInForce` | `'This session'` |
| `maxAttempts` | `2` |
| `stop.logic` | `'Below swing low / above swing high'` |
| `ticketType` | `'Zone ticket'` |
| `entry.priceMin` & `entry.priceMax` | Both equal to `priceNow` |
| `stop.price`, `targets[].price` | All equal to `priceNow` |

Every exported JSON backup will contain wrong field values regardless of what the user entered. Schema validation will pass because the values are valid enum members, making this a silent data corruption bug.

**Fix:** Read each of these fields from the corresponding DOM input, the same way `asset` and `priceNow` are already read.

---

### 4. `decisionMode` derivation is incomplete — `export_json_backup.js`

**File:** `app/scripts/exports/export_json_backup.js` line 25

`decisionMode` is derived only from `waitReason`. This means the field will never be set to `'LONG'` or `'SHORT'`, which are the two most common trade modes.

**Fix:** Read `decisionMode` from the bias radio buttons, the same pattern used elsewhere in `form_bindings.js`.

---

## High Severity Issues

### 5. Stub functions exported but non-functional

Three exported functions are stubs that do nothing useful:

| File | Function | Actual Behaviour |
|---|---|---|
| `app/scripts/generators/prompt_aar.js` | `buildAARPrompt()` | Returns a placeholder string |
| `app/scripts/generators/prompt_weekly.js` | `buildWeeklyPrompt()` | Returns a placeholder string |
| `app/scripts/exports/export_csv.js` | `exportCSV()` | Shows an alert, no CSV produced |

These are also not imported or exposed to `window` in `main.js`, so they are currently unreachable from the UI. They should either be implemented for G2 or removed until then to avoid confusion.

---

### 6. Five functions not exposed to `window` — `main.js`

**File:** `app/scripts/main.js`

The following modules are imported nowhere and never assigned to `window`, making them dead code from the UI's perspective:

- `exportCSV` (export_csv.js)
- `exportJSONBackup` (export_json_backup.js)
- `importJSONBackup` (import_json_backup.js)
- `buildAARPrompt` (prompt_aar.js)
- `buildWeeklyPrompt` (prompt_weekly.js)

If any of these are wired to HTML button `onclick` attributes, they will throw `ReferenceError`. If they are not yet wired, they should be added to the `window` block alongside the existing assignments or explicitly deferred to a later generation.

---

### 7. `noTradeToggle` accessed without null-safety — `prompt_ticket.js`

**File:** `app/scripts/generators/prompt_ticket.js` line 18

```js
const noTradeOK = document.getElementById('noTradeToggle').checked;
```

If the element does not exist in the DOM (wrong page, different HTML version), this throws `TypeError: Cannot read properties of null`. The rest of the file uses the safe `get()` helper for this exact reason.

**Fix:**

```js
const noTradeOK = document.getElementById('noTradeToggle')?.checked ?? false;
```

---

## Medium Severity Issues

### 8. `migrations.js` is a no-op

**File:** `app/scripts/state/migrations.js`

The function validates the payload exists then returns it unchanged. This is fine for schema v1.0.0, but there is no version check. When the schema changes, old backups will pass through unmigrated and likely fail validation downstream.

**Recommendation:** Add a version field check now, even if the only action is to log a warning. This makes future migration additions much easier.

---

### 9. Tests do not test the actual `gates.js` implementation

**File:** `tests/test_scoring.js`

The test file reimplements gate logic as a standalone pure function and tests that. The actual `gates.js` implementation mutates DOM elements directly and returns nothing. The tests pass, but they do not verify what the app actually does.

**Recommendation:** Extract the decision logic from `gates.js` into a pure function (e.g., `evaluateGate(inputs) -> 'WAIT' | 'CAUTION' | 'PROCEED'`) that both the UI code and the tests can call. The UI layer then only handles DOM updates.

---

### 10. Enum definitions duplicated between schema JSON and validation JS

**Files:** `docs/schema/ticket.schema.json`, `docs/schema/aar.schema.json`, `app/scripts/schema/backup_validation.js`

Enum arrays are written twice: once in the JSON schemas and once in the validation module. They can drift silently. The `test_enums.js` suite tests the JS-side enums but does not cross-check them against the JSON schemas.

**Recommendation:** Either have the validation module read and parse the JSON schema files at runtime (straightforward with `fetch` in browser or `require` in Node), or add a test that compares the two sources of truth.

---

### 11. FileReader has no error handler — `form_bindings.js`

**File:** `app/scripts/ui/form_bindings.js` lines 38–43

```js
const reader = new FileReader();
reader.onload = e => { ... };
reader.readAsDataURL(file);
```

No `reader.onerror` handler. If a file read fails, state is partially updated (the filename is set) but the preview image never loads. The user receives no feedback.

**Fix:** Add `reader.onerror = () => alert('Failed to read image file.');` or a more graceful in-page error message.

---

### 12. `buildAARStub()` hardcodes AAR outcome fields — `export_json_backup.js`

**File:** `app/scripts/exports/export_json_backup.js` lines 67–94

The stub AAR record hardcodes:
- `outcomeEnum: 'MISSED'`
- `verdictEnum: 'PROCESS_GOOD'`
- `notes: 'AAR not completed yet.'`
- All price fields to `0`

These will be exported into backups and re-imported as if they were real data. The `notes` string satisfies the `minLength: 1` requirement in the schema, so validation passes, making this a silent data issue.

---

### 13. `export_pdf_print.js` uses a hardcoded 300ms timeout

**File:** `app/scripts/exports/export_pdf_print.js` line 12

`setTimeout(() => w.print(), 300)` is a race condition. On slow devices the page may not be rendered; on fast devices the timeout is wasteful.

**Fix:** Use `w.onload = () => w.print()` instead of `setTimeout`.

---

## Low Severity / Observations

### 14. `createdAt` format not validated

**File:** `app/scripts/schema/backup_validation.js` line 58

The ticket schema specifies `"format": "date-time"` for `createdAt`. The validation only checks `typeof value === 'string'`. An invalid date like `'not-a-date'` passes validation.

---

### 15. `report_html.js` reads prompt text from DOM

**File:** `app/scripts/generators/report_html.js` line 8

The function reads the prompt text from `#outputText` instead of receiving it as a parameter. This couples the HTML report generator to a specific DOM element and makes it impossible to call from tests or a headless context.

---

### 16. Gate logic edge case (documentation gap, not a bug)

**File:** `app/scripts/ui/gates.js` lines 29–49

The WAIT state only triggers when `isChopOrMessy && noTradeToggle` are both true. If a user marks the session as chop/messy but does not toggle "no-trade OK", the gate falls through to CAUTION or PROCEED. This is correct per the scoring rules, but it is not obvious from the UI and may surprise users.

**Recommendation:** Add a tooltip or helper text explaining the noTradeToggle dependency.

---

## Test Coverage Summary

| Module | Test Coverage |
|---|---|
| `metrics_engine.js` | Covered (test_metrics.js) |
| `calibrations.js` | Covered (test_metrics.js) |
| `gates.js` (logic) | Covered via reimplementation (see issue 9) |
| `backup_validation.js` enums | Covered (test_enums.js) |
| `form_bindings.js` | Not covered |
| `migrations.js` | Not covered |
| `export_json_backup.js` | Not covered |
| `import_json_backup.js` | Not covered |
| `prompt_ticket.js` | Not covered |
| `storage_indexeddb.js` | Not covered |

---

## Recommended Fix Order

| Priority | Issue | File |
|---|---|---|
| 1 | Import name mismatch (breaks IndexedDB) | storage_indexeddb.js |
| 2 | `syncOutput` implicit global dependency | form_bindings.js |
| 3 | Hardcoded values in `buildTicketSnapshot()` | export_json_backup.js |
| 4 | Incomplete `decisionMode` derivation | export_json_backup.js |
| 5 | Stub functions and missing `window` exposure | prompt_aar.js, prompt_weekly.js, export_csv.js, main.js |
| 6 | Null-unsafe DOM access in prompt_ticket.js | prompt_ticket.js |
| 7 | `migrations.js` version check | migrations.js |
| 8 | Extract pure gate logic for testability | gates.js, test_scoring.js |
| 9 | Deduplicate enum definitions | backup_validation.js |
| 10 | FileReader error handler | form_bindings.js |
| 11 | PDF export race condition | export_pdf_print.js |
