# Repository Audit Report — 2026-03-04 (Session B)

## Scope

Full audit of the repository as of the end of the prior session (v2.11 checkpoint).
Verified test suite health, identified a silent regression introduced by the Plotly
integration PR, corrected an untracked CI improvement (LOW-2), and updated the
master plan to reflect the true project state.

---

## Findings

### 1. Browser test regression — `test_g10_export_pdf.js` FAIL (FIXED)

**Severity:** HIGH (silent — test count reported as 120 but 1 was secretly failing)

**Root cause:**

Commit `b87de35` ("Harden Plotly dashboard compatibility and rerender safety")
changed the signature of `buildAnalyticsReportHTML` in `app/scripts/ui/dashboard.js`
from:

```js
// original
export function buildAnalyticsReportHTML(doc = document) {
```

to:

```js
// after Plotly PR
export function buildAnalyticsReportHTML(exportOverrides = null, doc = document) {
```

The existing test calls the function as `buildAnalyticsReportHTML(doc)` (legacy
single-argument convention). The Plotly PR added a backward-compatibility check
inside the function body to handle this case, but JavaScript evaluates **default
parameter expressions before the function body executes**. The default `doc =
document` references the browser global `document`, which does not exist in the
Node.js test runtime — throwing `ReferenceError: document is not defined` before
the compat logic could run.

This caused test 27 (`buildAnalyticsReportHTML includes key analytics values and
sections`) to fail silently, while prior audit reports claimed 120/120 passing.

**Fix applied:**

```js
// app/scripts/ui/dashboard.js line 14
// Before:
export function buildAnalyticsReportHTML(exportOverrides = null, doc = document) {

// After:
export function buildAnalyticsReportHTML(exportOverrides = null, doc = (typeof document !== 'undefined' ? document : null)) {
```

The `typeof` guard is safe in both environments: browsers get the global `document`,
Node.js gets `null` (the backward-compat check then reassigns `safeDoc` correctly).

**Verification:**

```
node --test tests/test_g10_export_pdf.js
# pass 1 / fail 0

node --test tests/*.js
# tests 120 / pass 120 / fail 0
```

---

### 2. LOW-2 already fixed — tracking entry corrected

**Severity:** Documentation only (no code change required)

**Issue:** The master plan debt table listed LOW-2 as `⬜ pending`:

> LOW-2 | CI does not install or test `macro_risk_officer/requirements.txt`

**Reality:** The `mro-tests` CI job in `.github/workflows/ci.yml` already installs
MRO dependencies, runs `pip-audit` for CVE scanning, and runs pytest with a 70%
coverage gate. The implementation was complete but the debt table was never updated.

**Fix:** Marked LOW-2 as `✅ FIXED 2026-03-04` in the master plan with the
explanatory note that it was already implemented but not tracked.

---

## Files Changed

| File | Change |
|------|--------|
| `app/scripts/ui/dashboard.js` | Default param `doc = document` → `doc = (typeof document !== 'undefined' ? document : null)` |
| `docs/V3_master_plan.md` | Version 2.10 → 2.11; Track B table corrected; verification snapshot updated; LOW-2 closed; Next Steps items 13–14 added; numbering corrected |
| `docs/repo_audit_2026-03-04b.md` | This report |

---

## Test Suite State After Fixes

| Suite | Command | Result |
|-------|---------|--------|
| Browser | `node --test tests/*.js` | **120/120 pass** |
| AI Analyst | `pytest -q ai_analyst/tests` | 303/303 (not re-run locally — no changes to Python code) |
| MRO | `pytest -q macro_risk_officer/tests` | 153/153 (not re-run locally — no changes) |

---

## Remaining Open Items (unchanged from prior audit)

| Priority | Item | Target |
|----------|------|--------|
| Low | Structured JSON logging in Python pipeline | Open |
| Low | Evaluate TypeScript migration for browser app | Open |
| Low | Expose API timeout (12 s) as configurable UI setting | Open |
| Low | LOW-1: Docker runs as root | v2.x |
| Low | LOW-3: `MINIMUM_VALID_ANALYSTS = 2` hardcoded | v2.x |
| Low | LOW-7: `storage_indexeddb.js` is a localStorage stub | v2.x |
| Low | LOW-8: CORS `allow_headers=["*"]` overly permissive | v2.x |
| Test | TEST-5: MRO degraded mode end-to-end | v2.x |
| Test | TEST-6: Schema migration chain v1.1.0 → v4.0.0 | v2.x |
| Test | TEST-7: Document JS/Python analyst schema divergence | v2.x |

---

## What Is Next

Priority order for the next session:

1. **C4 — Unified Export (Track C)** ← highest architectural value, enables full
   round-trip replay and audit of any analysis run.
2. **v2.1b — Multi-Round Deliberation** ← adds depth to the consensus model.
3. **v2.2 — Streaming + Real-Time UI** ← UX enhancement for long-running runs.
