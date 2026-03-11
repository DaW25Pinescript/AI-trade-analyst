# Repository audit status (2026-02-26)

## Scope
- Validate baseline health for both shipped surfaces described in the README:
  - Static browser app test suite (`node --test tests/*.js`)
  - Python AI analyst test suite (`cd ai_analyst && pytest`)

## Results summary

### 1) Browser app checks
- **PASS**: `node --test tests/*.js`
- 24/24 tests passed.
- Coverage includes deterministic gate behavior, schema enum stability, and migration/metrics fixtures.

### 2) Python AI analyst checks
- **FAIL**: `cd ai_analyst && pytest`
- 111 tests passed, 2 tests failed (`ai_analyst/tests/test_cli_integration_v13.py`):
  1. `test_run_manual_mode_generates_prompt_pack_with_real_chart_files`
     - Expected `manual_prompts/README.txt` to exist, but assertion failed.
  2. `test_arbiter_and_replay_end_to_end_with_manual_responses`
     - Arbiter reported `Only 0 valid analyst response(s) collected. Minimum required: 2.`

## Assessment
- The project is **mostly on track**, but **not fully green** because the Python suite is failing in CLI manual-mode integration tests.
- This blocks declaring the repo fully ready for the next implementation phase if that phase depends on manual-mode CLI reliability.

## Recommended next step
1. Reconcile the manual prompt-pack contract between implementation and integration tests:
   - Verify current prompt-pack generator output structure/files for manual mode.
   - Either restore expected artifacts (`README.txt`, response stubs path) or update tests if behavior intentionally changed.
2. Re-run:
   - `cd ai_analyst && pytest`
   - `node --test tests/*.js`
3. Mark next phase as ready only once both suites are green.

## Readiness call
- **Ready for next step?** **Not yet** for full-phase progression.
- **Ready for targeted next step?** **Yes** — immediate focus should be fixing the two failing Python CLI integration tests.

---

## Follow-up verification (2026-02-28)

### Re-run results
- **PASS**: `cd ai_analyst && pytest -q`
  - 117 passed, 0 failed.
  - Integration tests in `test_cli_integration_v13.py` now pass.
- **PASS**: `node --test tests/*.js`
  - 74/74 tests passed.

### Additional cleanup completed
- Updated `ai_analyst/pytest.ini` test discovery path from `ai_analyst/tests` to `tests`.
- Result: pytest no longer emits the `No files were found in testpaths` warning when run from the `ai_analyst/` directory.

### Updated readiness call
- **Ready for next step?** **Yes** — both shipped surfaces are green.
- **Best next development option:** proceed with the next planned feature increment (V3 roadmap execution), while keeping both suites as required pre-merge checks.

---

## Audit refresh (2026-03-01)

### Re-run results
- **PASS**: `node --test tests/*.js`
  - 77 passed, 0 failed.
  - Coverage includes deterministic gate logic, migrations, G11 bridge reliability, dashboard/operator metrics, and schema enum stability.
- **PASS**: `pytest -q ai_analyst/tests`
  - 119 passed, 0 failed.
  - Coverage includes CLI integration, prompt builder contracts, extractor robustness, LangGraph async integration, and arbiter rule enforcement.

### Error review outcome
- No active test regressions were found in either shipped runtime.
- No blocking implementation errors were detected during this audit pass.

### Updated progress call
- **Where we are now:** repository baseline is green across both app and AI analyst surfaces.
- **Immediate next step:** execute the next planned roadmap increment (G12 polish/release hardening for the browser track, and v1.4 prompt-library tuning for the AI pipeline) while preserving dual-suite green checks as a merge gate.

---

## Audit refresh (2026-03-02)

### Scope
- All three test suites validated (browser app, AI analyst, MRO).
- Environment issue identified and fixed: `pytest-asyncio` was installed into the system
  Python but not into the uv-isolated pytest environment; resolved via `uv tool install pytest --with "pytest-asyncio==0.23.8"`.
- Verified that 8 async tests (`test_macro_context_node.py`, `test_llm_client_retry.py`)
  were silently failing due to this environment mismatch; they now pass.

### Re-run results
- **PASS**: `node --test tests/*.js` — **105 passed, 0 failed**
  - Coverage includes deterministic gate logic, G11 bridge reliability, dashboard/operator
    metrics, schema enum stability, AAR flow, and shadow mode.
- **PASS**: `pytest -q ai_analyst/tests` — **256 passed, 0 failed**
  - Includes full async integration tests, macro context node, LLM retry paths, and all
    v2.0 ticket_draft contract coverage.
- **PASS**: `pytest -q macro_risk_officer/tests` — **153 passed, 16 skipped**
  - 16 skips = live-source smoke tests requiring `MRO_SMOKE_TESTS=1` + real API keys
    (by design; controlled by env flag).
- **Total: 514 passing, 0 failing** across all three suites.

### MRO track status
- MRO-P4 merged (PR #67): KPI telemetry, price outcome tracking, regime accuracy metrics,
  runbook, and expanded instruments — Track D fully complete.

### Updated progress call
- **Where we are now:** all four tracks green; Track D (MRO) fully complete.
- **Single remaining blocker for G12:** G11 UI verdict card — the "Run AI Analysis" button
  POST and response population in the browser app.
- **Immediate next step:** implement G11 UI card (wire POST + populate verdict/ticket_draft
  in browser app), then proceed to G12 polish and v2.1 deliberation.

---

## Audit refresh (2026-03-02)

### Scope
Full three-suite audit following MRO Phase 4 merge (PR #67). Includes MRO suite for first time.

### Re-run results
- **PASS**: `node --test tests/*.js`
  - **105 passed, 0 failed**
  - Coverage includes G11 bridge reliability, dashboard/operator metrics, gate logic, schema enum stability, and shadow/calibration fixtures.
- **PASS**: `pytest -q ai_analyst/tests`
  - **256 passed, 0 failed**
  - All async tests now correctly running under `pytest-asyncio` (env isolation fix applied).
  - Coverage includes CLI integration, prompt builder contracts, extractor robustness, LangGraph async integration, arbiter rule enforcement, macro context node, and ticket_draft mapping.
- **PASS**: `pytest -q macro_risk_officer/tests`
  - **153 passed, 16 skipped**
  - Skips are intentional live smoke tests (require `MRO_SMOKE_TESTS=1` + real API keys).
  - Coverage includes decay, models, sensitivity matrix, reasoning engine, CLI, FRED converter, outcome tracker, KPI reporter.
- **Total: 514 passed, 0 failed, 16 skipped (by design)**

### Environment note
The `pytest` binary runs in a uv-isolated virtual environment (`/root/.local/share/uv/tools/pytest/`). `pytest-asyncio` must be installed into that environment via `uv tool install pytest --with "pytest-asyncio==0.23.8"`, not via system `pip`. This is now done.

### Track completion as of this audit
| Track | Status |
|-------|--------|
| Track A (Browser) | G1–G10 complete, G11 partially complete (UI card pending), G12 not started |
| Track B (AI Pipeline) | v1.1–v2.0 complete, v2.1 not started |
| Track C (Integration) | C1 complete, C2 complete, C3 partial (UI card is the remaining piece) |
| Track D (MRO) | **ALL COMPLETE — P1, P2, P3, P4** |

### Readiness call
- **Ready for next step?** **Yes.**
- **Single remaining blocker:** G11 UI card — "Run AI Analysis" button POST + verdict card population in the browser app.
- Once G11 is closed, the path to G12 (release) is clear.
