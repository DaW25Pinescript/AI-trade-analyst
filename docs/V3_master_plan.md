# AI Trade Analyst — Master Development Plan
**Version:** 2.22
**Updated:** 2026-03-05
**Status:** Active — G12 complete (including Plotly dashboard integration), v2.0 complete, MRO fully complete (P1–P4), v2.0.1 complete, v2.0.2 complete (all 4 CRITICALs + HIGH-1/5/6 + MED-5/8 fixed), v2.1 complete (HIGH-2/3/4/7/8 + MED-1/2/3/4/6/7 + LOW-5/6 + TEST-9/10), LOW-2 closed, Plotly regression fix (dashboard.js), **C4 complete (Unified Export)**, **Phase 2a complete (live feeder bridge + float fix), stability hotfixes complete (asyncio + deterministic ingest tests)**, **Phase 2b complete (region display, mobile optimization, UI polish)**, **Phase 3 complete (monitoring & observability — correlation IDs, pipeline metrics, operator dashboard)**, **Phase 4 complete (performance — TTL cache, parallel pipeline fan-out, real IndexedDB adapter)**, **Phase 5 complete (operational tooling — CLI audit trail export, bulk AAR import, analytics CSV export)**, **Phase 6 complete (production hardening — CORS whitelist, Caddy reverse proxy, Docker non-root + read-only, secrets manager docs)**, **Phase 7 complete (AI/ML Enhancement — feedback loop, bias detection, fallback routing)**, **Phase 8 complete (Advanced Analytics, Backtesting, E2E Validation, Plugin Architecture)**

---

## Overview

This plan supersedes all prior V3 planning documents. The project has evolved into a
two-track architecture:

| Track | Directory | Runtime | Current Version |
|-------|-----------|---------|-----------------|
| **A — Browser App** | `app/` | Static HTML/JS, IndexedDB | G1–G12 complete |
| **B — AI Pipeline** | `ai_analyst/` | Python 3.11+, LangGraph | v2.0.2 complete, v2.1 complete |
| **C — Integration** | shared | schema + bridge | C1–C3 complete |
| **D — Macro Risk Officer** | `macro_risk_officer/` | Python 3.11+, standalone | **ALL COMPLETE (P1–P4)** |

The two tracks are **independent** but share conceptual schema (instrument, session, ticket
fields, regime, risk constraints). A formal integration bridge (Track C) is planned from
G6/v2.0 onwards.

### Current verification snapshot (2026-03-05)
- Browser regression suite: **PASS** (`node --test tests/*.js`) with **189/189 passing**.
  - +13 added (2026-03-05): `test_phase4_performance.js` — Phase 4 IndexedDB adapter logic, cursor pagination, asset extraction, parallel source fetch contract, dashboard storage integration. 189/189 passing.
  - +1 added (2026-03-03): `test_g11_bridge.js` — confirms `analyseViaBridge` uses a 3-minute timeout signal (guards CRITICAL-3).
  - +3 added (2026-03-04): `test_g11_bridge.js` — timeframes match uploaded charts (guards MED-5).
  - +8 added (2026-03-04): `test_v202_fixes.js` — m15Overlay shape validation replaces null-only guard (guards MED-8).
  - **Regression fix (2026-03-04):** Plotly PR (`b87de35`) introduced `buildAnalyticsReportHTML(exportOverrides, doc = document)` — the `document` default parameter threw `ReferenceError` in Node.js context, silently dropping test 27 to FAIL. Fixed: default changed to `doc = (typeof document !== 'undefined' ? document : null)`. 120/120 confirmed.
  - +13 added (2026-03-04): `test_c4_unified_export.js` — C4 unified export version constant, parseUnifiedPayload accept/reject cases, schema migration path, verdict + charts pass-through. 133/133 passing.
- AI analyst regression suite: **PASS** (`pytest -q ai_analyst/tests`) with **303/303 passing**.
  - +4 added (2026-03-03): `test_execution_router_arbiter.py` — guards CRITICAL-1 fix.
  - +1 added (2026-03-03): `test_macro_context_node.py` — guards CRITICAL-2 fix.
  - +13 added (2026-03-03): `test_overlay_delta_config_alignment.py` — guards CRITICAL-4 fix.
  - +2 added (2026-03-04): `test_v202_fixes.py` — HIGH-5 (Grok model string), HIGH-6 (cost ceiling), HIGH-1 (retry logic).
  - +23 added (2026-03-04): `test_v21_fixes.py` — TEST-9 (MacroScheduler thread safety), TEST-10 (FinalVerdict.final_bias Literal), HIGH-2 (timezone-aware datetimes), MED-7 (is_text_only list blocks), LOW-5 (ExecutionConfig.mode Literal).
- MRO regression suite: **PASS** (`pytest -q macro_risk_officer/tests`) with **153 passed, 16 skipped** (skips = live smoke tests requiring `MRO_SMOKE_TESTS=1` + real API keys — by design).
  - +15 added (2026-03-04): `test_phase2a_feeder_bridge.js` — Phase 2a feeder bridge helpers (postFeederPayload, getFeederHealth), float fix (formatConfidencePct, formatPrice), verdict card percentage display. 150/150 passing.
- AI analyst regression suite: **PASS** (`pytest -q ai_analyst/tests`) with **313/313 passing**.
  - +4 added (2026-03-03): `test_execution_router_arbiter.py` — guards CRITICAL-1 fix.
  - +1 added (2026-03-03): `test_macro_context_node.py` — guards CRITICAL-2 fix.
  - +13 added (2026-03-03): `test_overlay_delta_config_alignment.py` — guards CRITICAL-4 fix.
  - +2 added (2026-03-04): `test_v202_fixes.py` — HIGH-5 (Grok model string), HIGH-6 (cost ceiling), HIGH-1 (retry logic).
  - +23 added (2026-03-04): `test_v21_fixes.py` — TEST-9 (MacroScheduler thread safety), TEST-10 (FinalVerdict.final_bias Literal), HIGH-2 (timezone-aware datetimes), MED-7 (is_text_only list blocks), LOW-5 (ExecutionConfig.mode Literal).
  - +10 added (2026-03-04): `test_phase2a_feeder_bridge.py` — Phase 2a feeder ingest endpoint, feeder health endpoint, macro_context_node feeder priority, ticket_draft aiEdgeScorePct. 313/313 passing.
  - +1 stability fix (2026-03-05): `test_phase2a_feeder_bridge.py` now uses `asyncio.run(...)` for Python 3.10+ compatibility (avoids missing default-loop RuntimeError).
- MRO regression suite: **PASS** (`pytest -q macro_risk_officer/tests`) with **153 passed, 16 skipped** (skips = live smoke tests requiring `MRO_SMOKE_TESTS=1` + real API keys — by design).
  - +16 added (2026-03-05): `test_phase2b_completion.js` — Phase 2b region display on operator dashboard, mobile breakpoints, UI polish, session clock unit tests. 166/166 passing.
  - +10 added (2026-03-05): `test_phase3_monitoring.js` — Phase 3 metrics response shape, RunMetrics entry validation, decision distribution, correlation ID in audit log, cost/latency bounds, dashboard structure. 176/176 passing.
- AI analyst regression suite: **PASS** (`pytest -q ai_analyst/tests`) with **347/347 passing**.
  - +23 added (2026-03-05): `test_phase3_monitoring.py` — CorrelationContext (set/get/reset/filter/idempotent logging), RunMetrics (fields/roundtrip/serialization), MetricsStore (empty/record/aggregate/bounded/error_rate/instruments/thread_safety/recent_limit), global singleton, audit log correlation_id, MetricsSnapshot serialization. 336/336 passing.
  - +11 added (2026-03-05): `test_phase4_performance.py` — chart_setup_node partial dict, macro_context_node partial dict, scheduler ThreadPoolExecutor use, all-sources-fail graceful degradation, pipeline topology (chart_setup present, chart_base/auto_detect removed), parallel fan-in invariant. 347/347 passing.
- MRO regression suite: **PASS** (`pytest -q macro_risk_officer/tests`) with **234 passed, 16 skipped** (skips = live smoke tests requiring `MRO_SMOKE_TESTS=1` + real API keys — by design).
- **Total: 806 passing, 0 failing** across all three suites (plus 16 intentional MRO skips).
  - +1 fix (2026-03-05): `analytics_csv_export` endpoint now imports `OUTPUT_BASE` from `run_state_manager` instead of computing its own path, fixing CSV verdict column population.
- Operational call: Tracks A (G1–G12) and D (MRO P1–P4) are complete. Track B v2.0.2 complete, v2.1 complete. C4 complete (Unified Export). **Phase 2a complete (live feeder bridge + float fix), stability hotfixes complete (asyncio + deterministic ingest tests)**. **Phase 2b complete (region display on operator dashboard, mobile layout optimization, UI polish pass)**. **Phase 3 complete (monitoring & observability — structured logging with correlation IDs, pipeline metrics collection, operator health dashboard)**. **Phase 4 complete (performance — TTL cache, parallel pipeline fan-out, real IndexedDB adapter)**. **Phase 5 complete (operational tooling — CLI audit trail export, bulk AAR import, analytics CSV export)**. **Phase 6 complete (production hardening — CORS whitelist, Caddy reverse proxy, Docker hardening, secrets manager docs)**. **Phase 7 complete (AI/ML Enhancement — feedback loop, bias detection, fallback model routing)**. **Phase 8 complete (Advanced Analytics Dashboard, Strategy Backtesting Engine, E2E Validation, Plugin/Extension Architecture)**.

---

## Design Principles

1. **Enum-first inputs** — eliminate ambiguity at every data boundary.
2. **Immutable ground truth** — once a `GroundTruthPacket` is created, it never mutates.
3. **Analyst isolation** — each model runs in parallel with no shared prompt state.
4. **Arbiter text-only** — the Arbiter never sees chart images, only structured JSON.
5. **NO_TRADE is first-class** — enforced in code via Pydantic validators, not just prompts.
6. **Minimum quorum** — at least 2 valid analyst responses required to proceed.
7. **Full audit trail** — every run is logged to JSONL; every ticket has an AAR path.
8. **Horse & Cart compatibility** — the pipeline works with zero API keys via prompt packs.
9. **Macro context is advisory** — MRO never overrides price structure; bias is injected as
   contextual evidence into the Arbiter prompt, never as a post-hoc verdict modifier.

---

## Track A — Browser App (`app/`)

### Milestone Reference

```
G1 → G2 → G3 → G4 (A1+A4) → G5 → G6 → G7 → G8 → G9 → G10 → G11 → G12
```

### G1 — Baseline UI (COMPLETE)
- Dark-theme multi-step form with design token system
- Steps: Setup → Charts → Context → Checklist → Prompt → Review
- IndexedDB persistence via `storage_indexeddb.js`
- Ticket schema v1.0.0 (`docs/schema/ticket.schema.json`)
- Modular script loading in `app/index.html`

### G2 — Test/Prediction Mode Card (COMPLETE)
**Goal:** Add structured pre-trade prediction capture as a dedicated step.

Tasks:
- [x] Integrate G2 Test/Prediction Mode card into `app/index.html` (Step 6 insertion)
- [x] Add new ticket fields: `decisionMode`, `entryType`, `entryTrigger`, `confirmationTF`,
      `timeInForce`, `maxAttempts`, `checklist` (8 items), gate fields
- [x] Update `export_json_backup.js` — remove hardcoded G2 field stubs; read from live DOM
- [x] Wire `exportJSONBackup` / `importJSONBackup` to `window` in `main.js`
- [x] Add `schemaVersion` check in `migrations.js` (currently no version guard)
- [x] Add enum cross-check test for all select/radio values vs schema

**Debt carried from PR #11:** Resolved in current `work` branch; G2 checklist items are now implemented and covered by tests.

### G3 — After-Action Review (AAR) — COMPLETE
**Goal:** Close the feedback loop with a structured post-trade review step.

Tasks:
- [x] Add step 07 (AAR) to the 7-step form nav in `app/index.html`
- [x] AAR card with all schema v1.0.0 fields: `outcomeEnum`, `verdictEnum`, `actualEntry`, `actualExit`,
      `rAchieved`, `exitReasonEnum`, `firstTouch`, `wouldHaveWon`, `killSwitchTriggered`,
      `failureReasonCodes` (multi-select), `psychologicalTag`, `revisedConfidence`, `checklistDelta`, `notes`
- [x] `edgeScore` display: auto-calculated from `revisedConfidence × verdictMultiplier`
      (PLAN_FOLLOWED=1.0 / PROCESS_GOOD=0.8 / PROCESS_POOR=0.5 / PLAN_VIOLATION=0.2)
- [x] Conditional "Would Have Won" field (shown only for MISSED / SCRATCH outcomes)
- [x] Trade Journal Photo upload with canvas watermarking (Ticket ID + timestamp)
- [x] AAR prompt generator updated to auto-populate from DOM fields (`prompt_aar.js`)
- [x] `export_json_backup.js` reads actual AAR DOM values instead of hardcoded stub
- [x] "Export Full JSON (with AAR)" button in AAR step
- [x] "Export JSON" quick-export button added to Output step (section-5)
- [x] "After-Action Review →" navigation button in Output step
- [x] `aarState` added to `state/model.js` for radio button values (firstTouch, wouldHaveWon, killSwitch)

### G4 — Counter-Trend + Conviction Inputs (A1 + A4) — COMPLETE
- [x] Add "Allow counter-trend ideas?" toggle: Strict HTF-only / Mixed / Full OK (`counterTrendMode` select in Setup)
- [x] Add "Conviction level before AI": Very High / High / Medium / Low (Pre-Ticket step 7)
- [x] Add "Price now" live-updating field (`priceNow` in Setup)
- [x] When "Conditional" decision selected → reveal secondary mini-ticket block (`conditionalWrap`)

### G5 — Prompt Generation Enhancements — COMPLETE
- [x] Append to Chart Narrative: `Overall bias from charts only (before any user bias injected)` (STEP 1 of prompt)
- [x] Add Scoring Rules paragraph to system prompt persona (R:R assumptions, full confidence scale 1–5, counter-trend enforcement)
- [x] Store `rawAIReadBias` to ticket for AAR comparison (select in Output step, exported in JSON)
- [x] `TICKET_SCHEMA_VERSION` bumped to `1.2.0`; migration patch added for `1.1.0 → 1.2.0`

### G6 — Data Model v2 + Persistence Hardening
- [x] Add fields to ticket schema: `psychologicalLeakR`, `edgeScore` (rawAIReadBias already in schema v1.2.0)
- [x] Auto-save timestamped JSON backup to Downloads on every ticket generation:
  `AI_Trade_Journal_Backup_YYYYMMDD_HHMM.json`
- [x] Embed chart screenshots as base64 in self-contained HTML/PDF export
- [x] Implement `migrations.js` version gate with upgrade path for all prior schema versions

**Integration point:** From G6, the ticket schema is stable enough to serve as the
canonical data contract between Track A and Track B.

### G7 — Mini Dashboard
- Win rate, avg R, expectancy, trade frequency stats
- Heatmap: Setup Type × Session (4×4 grid, colour-coded)
- Psychological Leakage R metric: avg R lost on psychologically-tagged trades
- Dark-theme PDF reliability fix (`color-scheme: dark`, forced `!important` on print)

### G8 — Weekly Review Workflow
- Weekly Review Prompt generator (aggregate last 7 days tickets + AAR into single AI prompt)
- Revised Ticket button: create a child ticket linked to original with `revisedFromId`
- "AI Edge Score vs Actual Outcome" field per ticket

### G9 — Shadow Mode (COMPLETE)
- [x] Toggle on main form: runs full analysis → saves ticket → tracks shadow outcomes over 24h/48h
- [x] Zero capital risk flow: user records outcome price manually with target/stop hit inference
- [x] Schema + migration support (`3.0.0 → 4.0.0`) with dedicated validation and tests

### G10 — Performance Analytics v2 (COMPLETE)
- [x] Equity curve simulation based on closed trade history + R values
- [x] Monthly/quarterly breakdown tables (trades, win rate, avg R, net R)
- [x] Export analytics as PDF report
- [x] Plotly integration for dashboard charts (heatmap, equity curve, period tables) with legacy rendering fallback
- [x] Plotly export capture path (`capturePlotlyChartsForExport`) to preserve rendered chart artifacts in generated reports

### G11 — API Bridge (Track A → Track B) — COMPLETE
- [x] Additive Operator Dashboard Mode (Phase A): dashboard shell toggle + responsive card layout
      layered over existing 7-step V3 flow (no top-to-bottom rewrite)
- [x] Bridge transport hardening: `/analyse` now enforces request timeout + bounded retry on transient failures
- [x] Contract regression tests for bridge reliability: transient 5xx retry path and timeout error path
- [x] Docker Compose (`docker-compose.yml`): one-command local start for app + API together (C2)
- [x] OpenAPI spec committed (`docs/openapi.json`); `ticket_draft` in API response envelope
- [x] **"Run AI Analysis" button** — `app/` POSTs `GroundTruthPacket`-equivalent payload to
      the FastAPI `/analyse` endpoint.
- [x] **AI Multi-Model Verdict card** — response (`verdict` + `ticket_draft`) populates a
      structured results card in the UI; local server availability is surfaced to the user.

**Requires local Python server running (documented setup).**

### G12 — Polish + Public Release

**Comparison summary (existing plan vs Claude proposal):**
- Existing plan already captured the four high-level themes (a11y, print, docs, release packaging).
- Claude's proposal adds the missing implementation-level specifics required to execute and verify G12.
- This section now merges both into one prioritized execution list, with explicit Definition of Done.

**Prioritized G12 task list (merged):**

0. [x] **Gate check: complete remaining G11 UI verdict card/POST integration first.**
   - G12 work begins only after G11 is green end-to-end (button POST + verdict rendering + graceful offline UX).

1. [x] **Form accessibility foundations (highest impact).**
   - Ensure stable `id` on every `input`, `textarea`, and `select`.
   - Ensure each `<label>` uses `for="<matching-id>"`.
   - For grouped checkboxes/radios, use semantic `fieldset`/`legend` where appropriate.

2. [x] **Prevent accidental form submissions.**
   - Add explicit `type="button"` to every non-submit UI/navigation button.

3. [x] **Keyboard visibility and operability polish.**
   - Add robust `:focus-visible` styles for buttons, links, form controls, and custom interactive elements.
   - Ensure focus indicator is obvious in both dark and light contexts (not color-only).

4. [x] **Dynamic announcement semantics.**
   - Add `aria-live` regions for dynamic status/verdict/pipeline/validation updates.
   - Default to `aria-live="polite"`; reserve `assertive`/`role="alert"` for genuinely critical updates.
   - Avoid repetitive re-announcement noise.

5. [x] **Readable contrast tuning for secondary text token(s).**
   - Adjust `--muted` (or equivalent) to meet WCAG AA while preserving hierarchy.

6. [x] **Print output correctness and readability.**
   - Resolve any `color-scheme: dark` bleed in print styles.
   - Force high-contrast print defaults (white background, readable text).
   - Add print page-break controls to keep key blocks together (ticket header/summary, verdict/gates) and improve long-table behavior.

7. [x] **Release artifact + release log updates.**
   - Create G12 snapshot in `app/releases/` following prior milestone format.
   - Update `app/releases/README.md` with the new G12 entry.

8. [x] **User-facing documentation updates.**
   - Create or expand a practical user guide covering ticket entry, section navigation, dynamic status/verdict behavior, print/export flow, and keyboard-accessibility expectations.

9. [x] **QA pass + evidence collection.**
   - Manual keyboard tab pass across interactive controls.
   - Manual scan for unlabeled inputs.
   - Print preview validation (no dark bleed, intentional page breaks).
   - Capture concise QA notes and changed-file list in the G12 release snapshot.

**Definition of Done (G12):**
- [x] No obvious unlabeled form controls in primary UI flow; labels are programmatically associated.
- [x] Non-submit buttons no longer trigger unintended form submissions.
- [x] Keyboard focus indicator is consistently visible across interactive controls.
- [x] Dynamic status/verdict updates are announced appropriately by assistive tech.
- [x] Muted/secondary text contrast is improved to WCAG AA-friendly levels.
- [x] Print preview is readable, high-contrast, and free from dark-theme bleed; key blocks avoid awkward splits.
- [x] G12 release snapshot exists in `app/releases/` and `app/releases/README.md` has a matching entry.
- [x] User guide is present/updated with workflow and accessibility notes.
- [x] Regression checks remain green (`node --test tests/*.js`; plus any relevant Python checks if touched).

---

## Track B — AI Pipeline (`ai_analyst/`)

### Version Reference

```
v1.0 → v1.1 → v1.2 → v1.3 → v1.4 → v2.0 → v2.1 → v2.x
```

### v1.1 — Core Pipeline (COMPLETE)
- `GroundTruthPacket` (immutable, frozen Pydantic model)
- 8 Lens contracts loaded from `prompt_library/v1.1/lenses/`
- 5 Persona templates from `prompt_library/v1.1/personas/`
- LangGraph pipeline: validate → fan_out_analysts → run_arbiter → log_and_emit
- 4 analyst models: GPT-4o, Claude Sonnet, Gemini 1.5 Pro, Grok-4-Vision
- Arbiter: text-only, 6 non-negotiable rules enforced in template + code
- FastAPI endpoint: `POST /analyse`, `GET /health`
- JSONL audit log to `logs/runs/{run_id}.jsonl`
- Test suite: lens contracts, Pydantic schemas, arbiter rules

### v1.2 — Manual / Hybrid Execution (COMPLETE)
- Three execution modes: Manual, Hybrid, Automated
- `ExecutionConfig` with per-analyst `AnalystDelivery` (API / MANUAL)
- Prompt pack generator: self-contained directory with README, analyst prompts, response stubs
- Run state machine: CREATED → PROMPTS_GENERATED → AWAITING_RESPONSES →
  RESPONSES_COLLECTED → VALIDATION_PASSED → ARBITER_COMPLETE → VERDICT_ISSUED
- Typer CLI: `run`, `status`, `arbiter`, `history`, `replay` commands
- `api_key_manager.py`: auto-detects available keys, suggests mode
- `json_extractor.py`: robust extraction from prose/markdown AI responses
- `.env.example` for all four providers

**Code fixes applied 2026-02-24:**
- `execution_config.py`: Added `from .persona import PersonaType` (was a broken forward ref)
- `execution_router.py`: Fixed `..core.xxx` double-hop imports → `.xxx`
- `cli.py`: Removed stray unused `import uuid` inside `arbiter` command

### v1.3 — Integration Tests + Real Chart Packs (COMPLETE)
**Goal:** Validate the full pipeline end-to-end with real chart images.

Tasks:
- [x] Integration test: `run` CLI with 4 real chart PNGs in manual mode → verify prompt pack structure
- [x] Integration test: `arbiter` CLI with pre-filled stub responses → verify FinalVerdict structure
- [x] API key setup guide (`docs/api_key_setup.md`)
- [x] Test that `replay` command re-runs Arbiter correctly on saved outputs
- [x] Add `pytest-asyncio` integration test fixtures for LangGraph pipeline
- [x] Verify `json_extractor.py` handles known AI response wrapper patterns

### v1.4 — Prompt Library v1.2 + Lens Tuning — COMPLETE
**Goal:** Iterate on prompt quality from real-run feedback.

Tasks:
- [x] Review first batch of real analyst outputs vs expected lens contract fields
- [x] Tighten FORBIDDEN TERMINOLOGY sections based on observed violations
- [x] Add `EXAMPLES` section to each lens (positive and negative examples)
- [x] Add `minimum_confidence_threshold` metadata to each lens file
- [x] Versioned prompt library directory: `prompt_library/v1.2/`
- [x] Lens loader supports version selection: `load_active_lens_contracts(version="v1.2")`
- [x] Fix forbidden-term body violations in `ict_icc.txt` and `volume_profile.txt` (v1.2)
- [x] 177/177 pytest passing with full v1.2 lens contract coverage

### v2.0 — Ticket Schema Integration + Bridge API — COMPLETE
**Goal:** Align `ai_analyst` output with `app/` ticket schema v2.

Tasks:
- [x] Map `FinalVerdict` fields to `ticket.schema.json` v2 fields (`ai_analyst/output/ticket_draft.py`)
- [x] `POST /analyse` response includes a `ticket_draft` block ready to import into `app/`
- [x] `GroundTruthPacket` accepts a `source_ticket_id` for traceability
- [x] `AnalysisResponse` envelope model (`verdict + ticket_draft + run_id + source_ticket_id`)
- [x] OpenAPI spec generated from FastAPI and committed to `docs/openapi.json`
- [x] `app/scripts/main.js` unpacks `response.verdict` from the v2.0 envelope
- [x] 48 new contract tests for ticket_draft mapping (225/225 pytest passing)
- [ ] Webhook/callback support for async pipeline completion (deferred to v2.1+)

### v2.0.1 — Run Observability Foundation (COMPLETE)
**Goal:** Promote run metering + API service boundary to first-class architecture for production operations.

Architecture components:
- **Token/Call Meter (`ai_analyst/core/usage_meter.py`)**
  - Append-only `usage.jsonl` per run (`run_id` scoped).
  - Per-call capture: stage/node, model/provider, attempts, latency, token usage where available, and failure metadata.
  - Run summary API for operations: total/success/failed calls, token totals, provider/model/stage/node rollups, token-availability coverage, and aggregated cost.
  - Fail-soft invariant: metering never blocks analysis; missing usage metadata is recorded as null/unknown and execution continues.
- **FastAPI Wrapper (`ai_analyst/api/main.py`)**
  - `POST /analyse` is the canonical service-layer entrypoint for one analysis run.
  - Request lifecycle creates immutable `GroundTruthPacket` (includes unique `run_id`) and executes one pipeline run.
  - Response envelope carries both analysis outputs and run-level usage summary so API consumers can correlate decision output with resource footprint.
  - Wrapper remains backward compatible with current manual/hybrid workflow while serving as the future integration surface for UI, automations, and external tooling.

### v2.0.2 — CRITICAL Debt Remediation (COMPLETE)
**Goal:** Close the four CRITICAL correctness and reliability issues identified in the 2026-03-03 audit, plus HIGH-1/5/6 and MED-5/8, before v2.1.

Issues addressed by priority:

- [x] **CRITICAL-1 — ExecutionRouter drops `macro_context` + `overlay_delta_reports`** *(FIXED 2026-03-03)*
  - `_run_arbiter_and_finalise()` now passes `macro_context`, `overlay_was_provided`, and `overlay_delta_reports=[]` to `build_arbiter_prompt()` in all CLI/hybrid/manual paths.
  - Added fail-silent `_try_fetch_macro_context()` helper (same pattern as `macro_context_node.py`) so the router self-fetches when no context is injected.
  - Added optional `macro_context=None` constructor parameter for test injection.
  - 4 new regression tests added in `tests/test_execution_router_arbiter.py`.

- [x] **CRITICAL-3 — Browser API bridge 12 s timeout breaks G11 for all users** ✅ FIXED 2026-03-03
  - `postAnalyseWithOptions` default raised from `12_000` → `180_000` ms.
  - `analyseViaBridge()` now explicitly passes `timeoutMs: 180_000` instead of `{}`.
  - New JS test verifies the AbortSignal is not immediately aborted (guards 3-minute budget).

- [x] **CRITICAL-2 — Synchronous HTTP in async MRO pipeline blocks event loop** ✅ FIXED 2026-03-03
  - `macro_context_node.py`: `scheduler.get_context()` now invoked via `await asyncio.to_thread(...)`.
  - Event loop is no longer blocked during cold-cache TTL miss (was up to 30 s stall under load).
  - Fix uses the recommended bridge approach — no changes to sync clients or CLI callers.
  - New test: `test_scheduler_called_via_asyncio_to_thread` verifies the delegation pattern.

- [x] **CRITICAL-4 — Overlay delta node assigns wrong model after Phase 1 partial failure** ✅ FIXED 2026-03-03
  - `analyst_nodes.py` re-indexed by position, not by original config slot.
  - Fix: added `analyst_configs_used` to `GraphState`; `parallel_analyst_node` tracks configs alongside outputs; `overlay_delta_node` uses tracked configs.
  - Regression test: `test_overlay_delta_config_alignment.py` (TEST-2).

- [x] **HIGH-5 — Grok model string `grok/grok-4-vision` does not exist** ✅ FIXED 2026-03-04
  - `analyst_nodes.py` and `api_key_manager.py` updated: `grok/grok-4-vision` → `xai/grok-vision-beta`.
  - `grok/grok-3` → `xai/grok-3` in `api_key_manager.py` (consistent provider prefix).

- [x] **HIGH-1 — Retry logic retries non-retriable exceptions with too-short backoff** ✅ FIXED 2026-03-04
  - `llm_client.py`: added `_is_retriable()` — `AuthenticationError`, `BadRequestError`, etc. fail immediately.
  - Backoff replaced: was linear 0.4 s; now exponential with full jitter (`uniform(0, min(60, base*2^n))`).
  - Legacy `retry_backoff_s` param kept for backwards compatibility with existing tests.

### v2.1 — HIGH Debt Remediation + Quality Hardening (COMPLETE)
**Goal:** Close all remaining HIGH-priority debt items from the 2026-03-03 audit, plus MED/LOW items.

Issues addressed:

- [x] **HIGH-2 + LOW-4**: `datetime.utcnow()` → `datetime.now(timezone.utc)` in `ground_truth.py`, `execution_config.py`, `run_state_manager.py` ✅ FIXED 2026-03-04
- [x] **HIGH-3 + TEST-10**: `FinalVerdict.final_bias` str → `Literal["bullish","bearish","neutral","ranging"]`; invalid values now raise `ValidationError` instead of silently producing empty `rawAIReadBias` ✅ FIXED 2026-03-04
- [x] **HIGH-4 + TEST-9**: `MacroScheduler` double-checked locking with `threading.Lock` prevents thundering herd under multi-worker uvicorn ✅ FIXED 2026-03-04
- [x] **HIGH-7**: In-process sliding-window rate limiter on `/analyse` (default 10 req/60s per IP; configurable via `RATE_LIMIT_REQUESTS` + `RATE_LIMIT_WINDOW_S` env vars) ✅ FIXED 2026-03-04
- [x] **HIGH-8**: `_graph` moved from module import to FastAPI `lifespan` startup handler — safe across uvicorn worker restarts; `TestClient` tests updated to context-manager pattern ✅ FIXED 2026-03-04
- [x] **MED-1**: FRED timestamps now use actual FRED observation date (`obs["date"]`) instead of first-of-month anchor (up to 28-day error eliminated) ✅ FIXED 2026-03-04
- [x] **MED-2**: GDELT `actual` scaled from tone magnitude (capped at 1.0) instead of binary `1.0/0.0` — surprise calculation now reflects signal strength ✅ FIXED 2026-03-04
- [x] **MED-3**: `print()` → `logging.warning/info` in `analyst_nodes.py`; `capsys`-based test updated to `caplog` ✅ FIXED 2026-03-04
- [x] **MED-4**: `append_usage` now logs `logging.warning` on failure instead of swallowing exceptions silently ✅ FIXED 2026-03-04
- [x] **MED-6**: `build_ticket_draft()` now sets `_draft: True` marker so importers can distinguish partial from complete tickets ✅ FIXED 2026-03-04
- [x] **MED-7**: `is_text_only()` now handles list-format content blocks — messages with only `{"type":"text"}` blocks correctly route to `claude_code_api` backend ✅ FIXED 2026-03-04
- [x] **LOW-5**: `ExecutionConfig.mode` → `Literal["manual","hybrid","automated"]` — invalid mode strings now raise `ValidationError` ✅ FIXED 2026-03-04
- [x] **LOW-6**: `api_bridge.js` now sends `source_ticket_id` field when a `ticketId` is present in the form — traceability link populated ✅ FIXED 2026-03-04

### v2.1b — Multi-Round Deliberation (NOT STARTED)
**Goal:** Allow analysts to see a summary of other analysts' verdicts and update.

Tasks:
- [ ] Add optional second-round fan-out after initial results
- [ ] Arbiter receives both Round 1 and Round 2 outputs, weighted by round
- [ ] Config flag: `enable_deliberation: bool = False` (off by default)
- [ ] Measure: does deliberation reduce NO_TRADE rate or improve confidence?

### v2.2 — Streaming + Real-Time UI
- Server-Sent Events from FastAPI as analysts complete
- CLI live progress display
- Browser app subscribes to SSE stream (G11+)

### v2.x — Future Enhancements (Backlog)
- **Shadow Mode server-side**: automated outcome capture via price API
- **Fine-tuned arbiter**: train a smaller model as Arbiter on historical runs
- **Lens versioning UI**: select active lens set via CLI flag or config file
- **Confidence calibration**: track predicted vs actual outcome to calibrate confidence thresholds
- **Additional models**: o3, Claude Opus, Mistral, Perplexity as optional analyst slots
- **Webhook integrations**: Slack/Discord verdict delivery

---

## Track D — Macro Risk Officer (`macro_risk_officer/`)

The MRO is a **parallel, advisory-only context engine** that answers:
*"What kind of market environment are we in right now?"*

It is consumed exclusively by the Arbiter prompt builder as structured contextual evidence.
Price action from analysts remains the sole authority for entries and exits.

### Hard Constraints (non-negotiable, enforced in code)
- MRO never generates trading signals
- MRO never overrides price structure
- MRO output is injected into the **Arbiter prompt**, not applied post-hoc to `FinalVerdict`
- Rule-based heuristics only in MRO-P1 and MRO-P2; no ML until MRO-P3
- All reasoning is fully explainable and auditable

### Arbiter Output Contract

MRO produces a single `MacroContext` object stored in `GraphState`. The Arbiter prompt
builder injects it as a `macro_section` block (identical pattern to `overlay_section`).
The LLM arbiter weighs it as contextual evidence — it does not modify `FinalVerdict` fields
directly. The `apply_macro_context()` post-processing pattern from the RFC is **not used**;
prompt injection is the correct integration point for this architecture.

```json
{
  "regime": "risk_off",
  "vol_bias": "expanding",
  "asset_pressure": { "USD": 0.85, "GOLD": 0.65, "SPX": -0.75, "NQ": -0.80, "OIL": 0.40 },
  "conflict_score": -0.62,
  "confidence": 0.72,
  "time_horizon_days": 45,
  "explanation": ["Tier-1 hawkish Fed surprise → tighter liquidity → USD supported, equities pressured"],
  "active_event_ids": ["fed-rate-2025-03-19", "cpi-mar-2025"]
}
```

### Repository Structure

```
macro_risk_officer/
├── config/
│   ├── thresholds.yaml
│   └── weights.yaml
├── core/
│   ├── models.py           # MacroEvent, AssetPressure, MacroContext (Pydantic)
│   ├── sensitivity_matrix.py
│   ├── decay_manager.py
│   └── reasoning_engine.py
├── ingestion/
│   ├── clients/
│   │   ├── finnhub_client.py
│   │   ├── fred_client.py
│   │   └── gdelt_client.py
│   ├── normalizer.py
│   └── scheduler.py
├── history/
│   └── tracker.py
├── utils/
│   └── explanations.py
├── main.py                 # CLI: python -m macro_risk_officer status
└── tests/
```

### Approved Data Sources (V1 only — listed order is priority)

| Source | Purpose |
|--------|---------|
| Finnhub | Economic calendar (actual vs forecast) |
| FRED | Historical macro time series |
| Financial Modeling Prep | Consensus macro releases |
| EODHD | Macro indicators + events |
| GDELT | Structured geopolitical events |

Excluded in V1: social media, raw headlines, retail sentiment feeds.

### Pipeline Integration Points (Track B)

Three files in `ai_analyst/` require changes when MRO-P2 is implemented:

| File | Change |
|------|--------|
| `ai_analyst/graph/state.py` | Add `macro_context: Optional[MacroContext] = None` to `GraphState` |
| `ai_analyst/graph/pipeline.py` | Insert `fetch_macro_context` node before `run_arbiter`; gated by `enable_macro_context` flag |
| `ai_analyst/core/arbiter_prompt_builder.py` | Add `macro_section` parameter; inject when present (same pattern as `overlay_section`) |
| `ai_analyst/api/main.py` | Add `enable_macro_context: bool = Form(False)` parameter |

### Known Integration Gaps (resolve before MRO-P2)

1. **`technical_exposures` source**: `ReasoningEngine.generate_context()` requires a dict
   mapping assets to directional exposures. Solution: derive from `ground_truth.instrument`
   via a static lookup table (e.g. `XAUUSD → {"GOLD": 1.0, "USD": -0.3}`).

2. **Latency**: External API calls (Finnhub/FRED) must not block `/analyse`. Solution:
   TTL-cached context (15–30 min refresh via background scheduler); pipeline reads from cache.

3. **Persistence for Phase 3**: `history/tracker.py` needs a storage backend. SQLite is
   sufficient. This is a Phase 3 concern — do not add until MRO-P2 is stable.

### MRO-P1 — Standalone Read-Only Context (COMPLETE)

**Deliverable:** `python -m macro_risk_officer status` prints `MacroContext` JSON to stdout.

```bash
# Text output (human-readable arbiter block)
python -m macro_risk_officer status --instrument XAUUSD

# JSON output (pipe-friendly)
python -m macro_risk_officer status --instrument XAUUSD --json
```

Tasks:
- [x] `core/models.py` — `MacroEvent`, `AssetPressure`, `MacroContext` Pydantic models
- [x] `core/sensitivity_matrix.py` — full 12-entry asset × event-type × direction matrix
- [x] `core/decay_manager.py` — exponential time-decay per tier (7d/3d/1d half-lives)
- [x] `core/reasoning_engine.py` — aggregate events → `MacroContext` (weighted, normalised)
- [x] `ingestion/clients/finnhub_client.py` — economic calendar with tier/category classification
- [x] `ingestion/clients/fred_client.py` — DFF, T10Y2Y, CPI, UNRATE, WTI with `to_macro_events()`
- [x] `ingestion/normalizer.py` — deduplication + sign correction across sources
- [x] `ingestion/scheduler.py` — TTL cache (30 min), Finnhub + FRED merged, per-instrument exposures
- [x] `config/thresholds.yaml` + `config/weights.yaml` — all tunable parameters externalised
- [x] `__main__.py` — enables `python -m macro_risk_officer`
- [x] `main.py` — `status` + `audit` CLI commands
- [x] `utils/explanations.py` — human-readable explanation builder
- [x] `requirements.txt` — `httpx`, `pyyaml`, `pydantic`
- [x] `.env.example` — `FINNHUB_API_KEY`, `FRED_API_KEY` documented
- [x] **55 unit + integration tests passing** (decay, models, matrix, engine, CLI, FRED converter)

### MRO-P2 — Arbiter Prompt Injection (COMPLETE)

Tasks:
- [x] `ai_analyst/graph/state.py` — `macro_context` field added
- [x] `ai_analyst/graph/pipeline.py` — `macro_context_node` added before analyst/arbiter execution
- [x] `ai_analyst/core/arbiter_prompt_builder.py` — `macro_section` injection block
- [x] `ai_analyst/api/main.py` — `enable_macro_context` form parameter
- [x] Conflict scoring wired into arbiter notes (LLM interprets `conflict_score` in prompt)
- [x] Integration tests: MRO context present vs absent, conflict paths

### MRO-P3 — Outcome Tracking (COMPLETE)

Tasks:
- [x] `history/tracker.py` — SQLite outcome log for MacroContext + verdict snapshots
- [x] Confidence audit baseline (distribution + confidence/conflict summaries by regime)
- [x] Auditable outcome report: `python -m macro_risk_officer audit`

### MRO-P4 — Progress Audit + Hardening Gate (COMPLETE)

Tasks:
- [x] Verify MRO unit/integration suite health (`pytest -q macro_risk_officer/tests`)
- [x] Verify pipeline integration behavior for macro-aware arbiter paths
- [x] Publish progress audit report with readiness call and next-step actions
- [x] Add non-flaky live-source smoke checks for scheduler clients (behind `MRO_SMOKE_TESTS=1` flag)
- [x] Define release gate KPIs: cache hit ratio, macro availability %, context freshness
      — `SchedulerMetrics` (in-process), `FetchLog` (SQLite-backed), `KpiReport` formatter
      — `stale_threshold_seconds` added to `thresholds.yaml`
      — `python -m macro_risk_officer kpi` CLI command
- [x] Add runbook for degraded macro mode (`docs/MRO_RUNBOOK.md`)

---

## Track C — Integration (app/ ↔ ai_analyst/)

This track begins at G6/v2.0 when both schema and API are stable.

### C1 — Shared Schema Contract (COMPLETE)
- [x] `docs/openapi.json` committed (FastAPI-generated); `ticket_draft` contract stable
- [x] `ai_analyst` output validated against schema before any `app/` import

### C2 — Local Server Setup (COMPLETE)
- [x] `docker-compose.yml` for one-command local start (FastAPI + static file server)
- [x] `GET /health` endpoint — used by `app/` to detect pipeline availability

### C3 — Browser ↔ Pipeline Bridge (COMPLETE)
- [x] Bridge transport hardened (timeout, retry, 5xx paths tested)
- [x] `app/scripts/main.js` envelope unpacking (`response.verdict`)
- [x] "Run AI Analysis" button POST wired in browser app
- [x] Verdict card populated from API response in UI
- [x] Graceful degradation UX when server unreachable

### C4 — Unified Export (COMPLETE)
- [x] `app/scripts/exports/export_unified.js` — `buildUnifiedPayload()` + `exportUnified()` (async; Plotly chart capture best-effort)
- [x] `app/scripts/exports/import_unified.js` — `parseUnifiedPayload()` (pure validation, testable) + `importUnified(file)` (restores verdict state)
- [x] `app/scripts/exports/export_json_backup.js` — `buildBackupPayload()` exported for reuse
- [x] `app/scripts/state/model.js` — `bridgeVerdict` field added; populated by `runBridgeAnalyse()` after every successful analysis
- [x] `app/scripts/main.js` — verdict persisted in state; `exportUnified` + `handleImportUnified` wired to `window`
- [x] `app/index.html` — "Export Unified (C4)" button added to Output step and AAR step; import card with file chooser
- [x] `tests/test_c4_unified_export.js` — 13 tests: version constant, reject/accept cases, migration, verdict/charts pass-through

**Unified format `v1`:**
```json
{
  "exportVersion": 1,
  "exportFormat": "unified",
  "exportedAt": "<ISO>",
  "ticket": { /* ticket v4.0.0 */ },
  "aar":    { /* AAR v1.0.0 */ },
  "verdict": { "run_id", "analysedAt", "source_ticket_id", "verdict", "usage" } | null,
  "dashboardCharts": { "<elementId>": "data:image/png;base64,..." } | null
}
```

---

## Technical Debt Register
*Last updated 2026-03-05 (v2.20 — audit hardening). Severity from audit: 🔥 CRITICAL / ⚠️ HIGH / ℹ️ MEDIUM / 💡 LOW.*

### 🔥 CRITICAL

| ID | Issue | Status | File | Target |
|----|-------|--------|------|--------|
| CRITICAL-1 | `ExecutionRouter` drops `macro_context` + `overlay_delta_reports` — CLI/hybrid arbiter weaker than API arbiter | ✅ **FIXED 2026-03-03** | `execution_router.py` | v2.0.2 |
| CRITICAL-2 | Sync `httpx.get()` in async MRO pipeline blocks event loop (up to 30 s on cold miss) | ✅ **FIXED 2026-03-03** | `macro_context_node.py` (asyncio.to_thread) | v2.0.2 |
| CRITICAL-3 | Browser bridge default timeout 12 s — G11 always times out before multi-model pipeline completes | ✅ **FIXED 2026-03-03** | `api_bridge.js` (180 s default) | v2.0.2 |
| CRITICAL-4 | Overlay delta node re-indexes by position after Phase 1 partial failure — wrong model assigned to surviving analyst | ✅ **FIXED 2026-03-03** | `analyst_nodes.py`, `state.py` | v2.0.2 |

### ⚠️ HIGH

| ID | Issue | Status | File | Target |
|----|-------|--------|------|--------|
| HIGH-1 | Retry catches all exceptions incl. non-retriable (AuthError, ValueError); backoff 0.4 s too short for rate limits | ✅ **FIXED 2026-03-04** | `llm_client.py` (non-retriable guard + exp backoff) | v2.0.2 |
| HIGH-2 | `datetime.utcnow()` deprecated — will break on Python 3.12+; returns naive datetime | ✅ **FIXED 2026-03-04** | `ground_truth.py`, `execution_config.py`, `run_state_manager.py` (→ `datetime.now(timezone.utc)`) | v2.1 |
| HIGH-3 | `FinalVerdict.final_bias` is unvalidated `str` — any freeform value silently produces empty `rawAIReadBias` in ticket draft | ✅ **FIXED 2026-03-04** | `arbiter_output.py` (→ `Literal["bullish","bearish","neutral","ranging"]`) | v2.1 |
| HIGH-4 | `MacroScheduler` not thread-safe — thundering herd on cache miss under multi-worker uvicorn | ✅ **FIXED 2026-03-04** | `scheduler.py` (double-checked locking with `threading.Lock`) | v2.1 |
| HIGH-5 | Grok model name `grok/grok-4-vision` does not exist — ICT_PURIST persona always fails | ✅ **FIXED 2026-03-04** | `analyst_nodes.py`, `api_key_manager.py` (→ `xai/grok-vision-beta`) | v2.0.2 |
| HIGH-6 | No budget guard — oversized chart inputs can cost $5–$20+ per request; no per-run token cap | ✅ **FIXED 2026-03-04** | `api/main.py` (image size 422), `usage_meter.py` (`check_run_cost_ceiling`) | v2.0.2 |
| HIGH-7 | No rate limiting on `/analyse` endpoint — open abuse surface | ✅ **FIXED 2026-03-04** | `api/main.py` (sliding-window rate limiter, `RATE_LIMIT_REQUESTS`/`RATE_LIMIT_WINDOW_S` env vars) | v2.1 |
| HIGH-8 | `_graph` built at module import time — not safe across uvicorn worker restarts; MRO TTL cache is per-process | ✅ **FIXED 2026-03-04** | `api/main.py` (→ FastAPI `lifespan` startup handler; `app.state.graph`) | v2.1 |

### ℹ️ MEDIUM

| ID | Issue | Status | File | Target |
|----|-------|--------|------|--------|
| MED-1 | FRED timestamps anchored to first of month — up to 28-day decay error | ✅ **FIXED 2026-03-04** | `fred_client.py` (→ uses actual FRED `obs["date"]` field; fallback to `now` on parse error) | v2.1 |
| MED-2 | GDELT artificial `actual=1.0 / forecast=0.0` — removes tone magnitude from surprise calc; always tier-2 | ✅ **FIXED 2026-03-04** | `gdelt_client.py` (→ `actual` scaled from `abs(avg_tone)/10`, clipped to `[0.1, 1.0]`) | v2.1 |
| MED-3 | `print()` instead of structured logging in graph nodes | ✅ **FIXED 2026-03-04** | `analyst_nodes.py` (→ `logging.warning` / `logging.info`; `caplog`-based tests) | v2.1 |
| MED-4 | `usage_meter.append_usage` swallows all exceptions silently | ✅ **FIXED 2026-03-04** | `usage_meter.py` (→ `logging.warning` on failure — fail-soft but visible) | v2.1 |
| MED-5 | `api_bridge.js` timeframes list hardcoded `['H4','M15','M5']` regardless of uploaded charts | ✅ **FIXED 2026-03-04** | `api_bridge.js` (built from uploaded files; fallback to defaults) | v2.0.2 |
| MED-6 | `build_ticket_draft()` missing required ticket fields — non-schema-compliant without `_draft: true` marker | ✅ **FIXED 2026-03-04** | `ticket_draft.py` (→ `draft["_draft"] = True` added at end of build) | v2.1 |
| MED-7 | `is_text_only` routing gap — list-format content with only text blocks incorrectly flagged as multimodal | ✅ **FIXED 2026-03-04** | `is_text_only.py` (→ handles list content; only non-text blocks block routing) | v2.1 |
| MED-8 | `backup_validation.js` requires `m15Overlay: null` — G11 overlay feature blocked at schema validation level | ✅ **FIXED 2026-03-04** | `backup_validation.js` (null-only guard → typed object shape validation) | v2.0.2 |
| MED-9 | Subprocess stderr leaked to HTTP client in `claude_code_api` — exposes internal paths and error details | ✅ **FIXED 2026-03-05** | `services/claude_code_api/app.py` (stderr logged internally, removed from HTTP response) | v2.20 |

### 💡 LOW

| ID | Issue | Status | File | Target |
|----|-------|--------|------|--------|
| LOW-1 | Docker runs as root | ⬜ pending | `Dockerfile` | v2.x |
| LOW-2 | CI does not install or test `macro_risk_officer/requirements.txt` | ✅ **FIXED 2026-03-04** | `.github/workflows/ci.yml` (`mro-tests` job installs `macro_risk_officer/requirements.txt` and runs pytest with CVE scan — was already implemented but not tracked) | v2.1 |
| LOW-3 | `MINIMUM_VALID_ANALYSTS = 2` hardcoded — 50% failure rate appears healthy | ⬜ pending | `analyst_nodes.py:37` | v2.x |
| LOW-4 | `run_state_manager.py` uses `datetime.utcnow()` outside Pydantic (missed by HIGH-2 sweep) | ✅ **FIXED 2026-03-04** | `run_state_manager.py` (→ `datetime.now(timezone.utc)`) | v2.1 |
| LOW-5 | `ExecutionConfig.mode` field is `str` not `Literal["manual","hybrid","automated"]` | ✅ **FIXED 2026-03-04** | `execution_config.py` (→ `Literal["manual","hybrid","automated"]`) | v2.1 |
| LOW-6 | `api_bridge.js` never sends `source_ticket_id` — traceability link always null | ✅ **FIXED 2026-03-04** | `api_bridge.js` (→ reads `ticketId` from form and appends to `FormData`) | v2.1 |
| LOW-7 | `storage_indexeddb.js` is a localStorage stub — 5–10 MB ceiling as journal grows | ⬜ pending | `storage_indexeddb.js` | v2.x |
| LOW-8 | CORS `allow_headers=["*"]` overly permissive | ⬜ pending | `api/main.py:108` | v2.x |

### Testing Gaps (from audit TEST-1 through TEST-11)

| ID | Test needed | Status | Target |
|----|------------|--------|--------|
| TEST-1 | Hybrid mode arbiter receives macro_context + overlay (CRITICAL-1 regression) | ✅ **ADDED 2026-03-03** (`test_execution_router_arbiter.py`) | v2.0.2 |
| TEST-2 | Overlay delta node — correct config after Phase 1 partial failure (CRITICAL-4) | ✅ **ADDED 2026-03-03** (`test_overlay_delta_config_alignment.py`) | v2.0.2 |
| TEST-3 | Full FastAPI `/analyse` integration test via TestClient | ✅ **UPDATED 2026-03-04** (`test_api_wrapper_usage.py` — updated to lifespan context manager; guards HIGH-8) | v2.1 |
| TEST-4 | Browser bridge: slow backend → user-visible timeout error (not silent hang) | ✅ **ADDED 2026-03-03** (`test_g11_bridge.js`) | v2.0.2 |
| TEST-5 | MRO degraded mode end-to-end — all sources fail → valid FinalVerdict | ⬜ pending | v2.x |
| TEST-6 | Schema migration chain: v1.1.0 → v4.0.0 in one call | ⬜ pending | v2.x |
| TEST-7 | Document JS/Python analyst schema divergence as a known-failing spec test | ⬜ pending | v2.x |
| TEST-8 | `buildAnalyseFormData` — timeframes match uploaded charts (guards MED-5) | ✅ **ADDED 2026-03-04** (`test_g11_bridge.js` — 3 new tests) | v2.0.2 |
| TEST-9 | Concurrent `/analyse` cache misses call `_refresh()` once with lock (guards HIGH-4) | ✅ **ADDED 2026-03-04** (`test_v21_fixes.py` — 2 tests) | v2.1 |
| TEST-10 | Unexpected `final_bias` value → ticket draft `rawAIReadBias` empty (guards HIGH-3) | ✅ **ADDED 2026-03-04** (`test_v21_fixes.py` — 4 tests; ValidationError now raised) | v2.1 |
| TEST-11 | Flaky strict-equality determinism check in feeder ingest due to time-decay micro-drift | ✅ **FIXED 2026-03-05** (`test_modal_worker.py` — field-level assertions + `pytest.approx` for asset pressure floats) | v2.1 |

### Architectural Debt (long-term, no immediate target)

| Issue | Impact | Effort |
|-------|--------|--------|
| Browser ↔ Python analyst schema divergence (JS: 0–100, Long/Short/Wait; Python: 0.0–1.0, LONG/SHORT/NO_TRADE) | Blocks unified replay, dashboard, telemetry parity | XL |
| Model strings duplicated across `analyst_nodes.py`, `api_key_manager.py`, `execution_router.py` | Adding a model requires 3+ consistent edits | S — centralize in `MODEL_REGISTRY` |
| MRO scheduler as module-level singleton — not injectable, not per-worker-safe | Limits testability and multi-worker deployment | M — move to `app.state` + FastAPI `lifespan` startup (pattern now established by HIGH-8) |
| `storage_indexeddb.js` is a stub — localStorage growth ceiling | Long-term journal retention at risk | L — implement real IndexedDB adapter |
| No shared `analyst_output.schema.json` canonical spec | JS and Python output shapes drift silently | M — define in `docs/schema/`, validate both sides |

---

## Flexibility & Upgrade Guidelines

### Adding a New Analyst Model
1. Add entry to `ANALYST_CONFIGS` in `graph/analyst_nodes.py`
2. Add `SUPPORTED_MODELS` entry in `core/api_key_manager.py`
3. No changes needed to graph, arbiter, or schema

### Adding a New Lens
1. Create `prompt_library/vX.X/lenses/new_lens.txt` (follow existing format)
2. Add field to `models/lens_config.py`
3. Add entry to `LENS_FILE_MAP` in `core/lens_loader.py`
4. No other changes needed

### Switching Prompt Library Versions
- All prompt paths are resolved at runtime from `PROMPT_LIBRARY_VERSION` constant
- To roll back: change the version constant; to add: create a new versioned directory
- Old versions are never deleted — full history preserved

### Changing Execution Modes Mid-Run
- Run state is persisted between CLI invocations
- A run started as `hybrid` can resume as `manual` if API keys become unavailable
- State transitions are append-only; no state is ever overwritten

### Schema Migrations (app/)
- Every ticket carries `schemaVersion`
- `migrations.js` applies upgrade patches in version order
- New fields should always have safe defaults to avoid breaking existing exports

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable, reviewed code only — all MRO phases and G1–G10 merged |
| Feature branches | Per-milestone, prefixed `claude/` for AI-assisted sessions |

All Claude-assisted development occurs on session branches and is merged via PR.
The orphaned `codex/create-spa-shell-with-extracted-assets` branch has no common merge
base with `main` (predates current repo structure) and can be safely deleted.

---

## Next Immediate Steps (Priority Order)

> Last updated: 2026-03-05 (v2.20). G1–G12, v1.1–v2.1, MRO P1–P4, C1–C4, and Phase 2a are complete. Audit hardening pass: HIGH-1 (streaming image size enforcement), MEDIUM-2 (subprocess stderr sanitized — no longer leaked to client), MEDIUM-3 (pipeline integration test), LOW-3 (feeder polling interval documented in runbook). This queue is the sequential execution plan from release verification through production hardening and AI/ML enhancements.

### Phase 1 — Release Verification (Immediate)
1. [x] Verify app loads from static server ✅ VERIFIED 2026-03-05
   - Confirmed `/app/index.html` returns `HTTP/1.0 200 OK` via `python -m http.server 8080` + `curl -I http://127.0.0.1:8080/app/index.html`.
2. [x] Validate export/import roundtrip ✅ VERIFIED 2026-03-05
   - Verified with `node --test tests/test_c4_unified_export.js` (valid unified export payload parses, imports, and migrates correctly).
3. [x] Validate Plotly-enabled export path ✅ VERIFIED 2026-03-05
   - Verified with `node --test tests/test_g10_export_pdf.js tests/test_c4_unified_export.js` (analytics report includes chart sections; unified export accepts `dashboardCharts` payload).
4. [x] Confirm schema parity ✅ VERIFIED 2026-03-05
   - Verified with `node --test tests/test_schema_bridge.js tests/test_g2_form_contract.js tests/test_enums.js`.

### Phase 2b — UI Polish & Mobile ✅
5. [x] Implement region display
   - Added Market Sessions card with live session clock (Sydney, Tokyo, London, New York) to the operator dashboard, reusing session renderer from T.R.A.D.E. page.
6. [x] Mobile layout optimization
   - Added responsive breakpoints at 620px/480px for operator dashboard (plan grid, card padding, chart stage, toolbar).
   - Enhanced macro/scout mobile styles: asset table column hiding, touch-friendly radio/bias controls, output panel compaction.
   - Touch-friendly form controls at 480px: larger tap targets for radio-opt, bias-btn, checkboxes, and buttons.
7. [x] UI polish pass
   - Updated version pill from G9 to G12 and subtitle to match current generation.
   - Added hover transitions to macro cards and dashboard cards for visual feedback.
   - Refined macro grid gap (14px → 16px) for consistent spacing.
   - Added consistent typography for dashboard metric rows (IBM Plex Mono, 11px labels).
   - Added macro card padding refinements at mobile breakpoints.

### Phase 3 — Monitoring & Observability (COMPLETE)
8. [x] Add structured logging with correlation IDs
   - `ai_analyst/core/correlation.py`: `ContextVar`-based `correlation_ctx` propagated through all async pipeline nodes.
   - `CorrelationFilter` injects `run_id` into every Python log record; `setup_structured_logging()` wires it at server startup.
   - `validate_input_node` sets the correlation context at pipeline entry; `/analyse` endpoint sets/resets it around invocation.
   - Audit log (`core/logger.py`) now emits `correlation_id` field in every JSONL entry.
9. [x] Add pipeline metrics collection
   - `ai_analyst/core/pipeline_metrics.py`: `RunMetrics` dataclass capturing per-run cost, latency, analyst agreement, decision, overlay/deliberation/macro flags.
   - `MetricsStore`: thread-safe, bounded in-memory store (default 500 entries) with `record_run()` and `snapshot()`.
   - `logging_node` records `RunMetrics` after every pipeline completion (fail-silent, never blocks the pipeline).
   - Pipeline wall-clock timing via `_pipeline_start_ts` / `_node_timings` fields in `GraphState`.
10. [x] Build operator health dashboard
   - `GET /metrics`: JSON endpoint returning aggregated `MetricsSnapshot` (total runs, cost, latency, agreement, decision/instrument distributions, error rate, recent runs).
   - `GET /dashboard`: Self-contained dark-theme HTML operator dashboard with auto-refresh (30s), metric cards, decision distribution bars, recent runs table, feeder status, API health.
   - API version bumped to v2.3.0.

### Phase 4 — Performance
11. [x] Cache macro context responses
   - TTL-based caching already implemented in `MacroScheduler` with thread-safe double-checked locking, SchedulerMetrics, and FetchLog (SQLite KPI store).
   - Phase 4 addition: `_refresh()` now fans out all three data-source fetches (Finnhub, FRED, GDELT) in parallel via `ThreadPoolExecutor`, cutting cold-start latency to ~1× the slowest source (was 3× sequential).
12. [x] Parallelize analyst image analysis
   - Analyst fan-out already used `asyncio.gather` within each node (Phase 1–3).
   - Phase 4 addition: `macro_context_node` and `chart_setup_node` (combined base+auto_detect) now run as a **parallel LangGraph fan-out** after `validate_input`. Both write to different state keys (no merge conflict). Eliminates MRO I/O wait from the pipeline hot path.
13. [x] Audit browser IndexedDB query performance
   - `storage_indexeddb.js` upgraded from a localStorage stub to a **real IndexedDB adapter** with a `trades` object store, `createdAt` and `asset` indexes, and cursor-based pagination (`loadTradeHistoryPage`).
   - `exportJSONBackup` auto-saves each trade to IndexedDB so the dashboard can load history without re-uploading files.
   - `initDashboard` wires a new "Load from storage" button to `loadDashboardFromStorage()` (reads all IndexedDB entries, passes to `computeMetrics`).

### Phase 5 — Operational Tooling (COMPLETE)
14. [x] CLI: audit trail export
   - Added `cli.py export-audit` command that dumps all runs, verdicts, and usage to CSV or JSON.
   - Supports `--format csv|json` and `--output <path>` flags.
   - Exports run metadata, verdict fields (decision, bias, confidence, agreement), and usage metrics (cost, tokens, call counts).
15. [x] CLI: bulk AAR import
   - Added `cli.py import-aar` command for batch after-action review imports from JSON or CSV.
   - Supports `--dry-run` flag for validation-only mode.
   - CSV format supports pipe-delimited `failureReasonCodes` and automatic type coercion for numeric/boolean fields.
   - Validates required fields (`ticketId`, `outcomeEnum`, `reviewedAt`); skips invalid records with clear error reporting.
   - AARs stored in `output/aars/{ticketId}/aar.json`.
16. [x] Analytics CSV export
   - Added `cli.py export-analytics` command producing CSV with verdict, usage, setup, and AAR columns.
   - Added `GET /analytics/csv` API endpoint returning a downloadable CSV attachment.
   - Added `exportAnalyticsCSV()` browser function in `dashboard.js` — builds CSV from loaded dashboard entries with ticket + AAR fields.
   - Added "Export Analytics CSV" button to `index.html` alongside existing PDF export.
   - Wired through `main.js` to `window` for global access.

### Phase 6 — Production Hardening (COMPLETE)
17. [x] Configure CORS origin whitelist
   - Tightened `allow_headers` from wildcard `["*"]` to explicit `["Content-Type", "Authorization", "X-API-Key"]`.
   - Added startup warning when `ALLOWED_ORIGINS` is not set (alerts operators to configure for production).
   - Added `ALLOWED_ORIGINS` to `.env.example` with documentation.
18. [x] Set up reverse proxy (Caddy)
   - Added `caddy/Caddyfile` with automatic HTTPS, security headers (`X-Content-Type-Options`, `X-Frame-Options`, `HSTS`, `Referrer-Policy`), and rate limiting on `/analyse` endpoints.
   - Added `docker-compose.prod.yml` production overlay: Caddy service as the only internet-facing container, internal Docker network isolation, loopback-only ports for backend services, `app-static` disabled via profile.
19. [x] Harden Docker runtime
   - Dockerfile: added non-root `appuser` with `USER appuser` directive.
   - `docker-compose.prod.yml`: `security_opt: no-new-privileges:true`, `read_only: true`, `tmpfs: /tmp:size=100M`, `PYTHONDONTWRITEBYTECODE=1`.
20. [x] Secrets manager integration
   - Added `docs/secrets_manager.md` with detailed setup for AWS Secrets Manager (ECS task definition + entrypoint injection), GCP Secret Manager (Cloud Run + GKE), and HashiCorp Vault (Agent sidecar + entrypoint injection).
   - Added key rotation guide and injection verification steps.
   - Updated `.env.example` header with quick-reference injection commands for all three platforms.

### Phase 7 — AI/ML Enhancement ✅
21. [x] Feedback loop: outcomes → prompt refinement
   - Built `core/feedback_loop.py`: reads AAR outcome data from SQLite, computes regime accuracy, confidence calibration, persona dominance, and generates actionable recommendations for prompt improvement.
   - Added `feedback` CLI command for interactive report generation.
22. [x] Bias detection in analyst outputs
   - Built `core/bias_detector.py`: post-processing step that flags unanimous high-confidence consensus (groupthink), low HTF-bias diversity, confidence clustering, and single-dissenter patterns.
   - Integrated into arbiter prompt builder — `{bias_section}` is injected into every arbiter prompt with mitigation rules.
23. [x] Fallback model routing
   - Added `acompletion_with_fallback()` to `core/llm_client.py`: tries primary model, then iterates through configurable fallback models on failure.
   - Default fallback map covers Claude, GPT-4o, and Grok models. Override via `FALLBACK_MODEL_MAP` env var (JSON).
   - Integrated into `usage_meter.py` — enabled via `ENABLE_FALLBACK_ROUTING=1` env var.
   - 25 new tests in `tests/test_phase7_ai_ml.py` — all passing.

### Phase 8 — Advanced Analytics, Backtesting, E2E Validation & Plugin Architecture ✅
24. [x] Advanced Analytics Dashboard (Phase 8a)
   - Built `core/analytics_dashboard.py`: rich HTML dashboard with Chart.js visualizations.
   - Regime accuracy bar chart, confidence calibration curve, persona dominance heatmap, outcome trends (cumulative P&L + rolling win rate), decision distribution donut, instrument breakdown.
   - API endpoint: `GET /analytics/dashboard` — self-contained HTML page with auto-refresh.
25. [x] Strategy Backtesting Engine (Phase 8b)
   - Built `core/backtester.py`: replays historical outcomes, computes strategy-level metrics.
   - Sharpe ratio (annualized), max drawdown, win rate, profit factor, consecutive streaks.
   - Per-regime performance breakdown. Equity curve generation.
   - CLI command: `python cli.py backtest [--instrument X] [--regime R] [--min-confidence C] [--output FILE]`.
   - API endpoint: `GET /backtest?instrument=&regime=&min_confidence=` — JSON metrics.
26. [x] E2E Integration Validation (Phase 8c)
   - Built `core/e2e_validator.py`: 7-check smoke-test framework (GroundTruth, Arbiter, Feedback, Bias, Backtester, Dashboard, Plugins).
   - Runs deterministically without API keys using in-memory test DB.
   - CLI command: `python cli.py e2e` — prints structured validation report, exits 1 on failure.
   - API endpoint: `GET /e2e` — JSON validation report.
27. [x] Plugin/Extension Architecture (Phase 8d)
   - Built `core/plugin_registry.py`: central registry for Personas, Data Sources, and Hooks.
   - Built-in discovery: 4 personas (default_analyst, risk_officer, prosecutor, ict_purist) + 3 data sources (Finnhub, FRED, GDELT).
   - JSON manifest discovery from `plugins/` directory and `AI_ANALYST_PLUGINS_DIR` env var.
   - Hook events: `post_verdict`, `post_aar`, `post_backtest`, `pipeline_error`.
   - CLI command: `python cli.py plugins` — lists all registered plugins.
   - API endpoint: `GET /plugins` — JSON plugin registry.
   - 56 new tests in `tests/test_phase8_advanced.py` — all passing.

**Rationale for sequencing:** start with low-risk release verification, then UI fit-and-finish, then observability/performance/tooling, and finish with operational hardening and AI enhancements on top of a stable baseline. Phase 8 leverages the feedback loop and outcome data from Phase 7 to provide actionable analytics and backtesting capabilities.

---

## Stage 1 — Audit Program Backlog (Masterplan / TODO only)

> Added per request: Stage 1 planning update only (no code-change scope, no execution yet).

### Audit execution order (recommended)
1. [ ] **Audit 0 — Repo Orientation + Risk Map (no code changes)**
2. [ ] **Audit 2 — G11 Bridge → G12 UI Integration Readiness**
3. [ ] **Audit 1 — Schema + Contract Governance**
4. [ ] **Audit 3 — LLM Execution Correctness + Observability**
5. [ ] **Audit 4 — Security + Secrets + Supply Chain**

### Audit 0 — Repo Orientation + Risk Map
- [ ] Read/summary targets: `README.md`, `app/`, `ai_analyst/`, `macro_risk_officer/`, `docs/schema/`, `tests/`, `.github/workflows/`.
- [ ] Deliverable: 1-page architecture sketch (`app ↔ bridge ↔ ai_analyst ↔ MRO`).
- [ ] Deliverable: top-12 risk map grouped by Correctness / Security / DX / Maintainability / Release.
- [ ] Deliverable: concrete audit sequence for Audits 1–4 with file-level rationale.
- [ ] Constraint: **no code modifications**.

### Audit 2 — G11 Bridge → G12 UI Integration Readiness
- [ ] Trace full path: UI click → request envelope → FastAPI handler → analyst run → response → verdict card render.
- [ ] Validate failure modes: API down, timeout, malformed/partial envelope, missing keys.
- [ ] Deliver integration map with exact files/functions.
- [ ] Add at least 3 integration-style tests:
  - [ ] happy-path verdict render
  - [ ] API unreachable degraded UX
  - [ ] schema mismatch / invalid envelope handling
- [ ] Acceptance: `make test-all` or (`node --test tests/*.js` + `pytest -q ai_analyst/tests`) passes; no manual/hybrid regression.

### Audit 1 — Schema + Contract Governance
- [ ] Scope: `docs/schema/*.schema.json`, `app/scripts/schema/`, `app/scripts/state/`, `app/scripts/exports/`, `ai_analyst/models/`.
- [ ] Verify end-to-end contract enforcement for ticket + AAR:
  - [ ] export validates before download
  - [ ] import validates before migration/application
  - [ ] local load/save validates shape compatibility
  - [ ] enum stability guarantees respected
- [ ] Deliver contract matrix (artifact, producer, consumer, validation points, migration/version rules).
- [ ] If issues found: apply smallest-safe patch + tests; avoid schema bumps unless bug-forced.
- [ ] Acceptance: `node --test tests/*.js` and `pytest -q ai_analyst/tests` both pass.

### Audit 3 — LLM Execution Correctness + Observability
- [ ] Confirm sequence contracts: base → auto_detect → selected lenses → arbiter.
- [ ] Validate LangGraph node parity (`chart_base`, `chart_auto_detect`, `chart_lenses`, `run_arbiter`, optional bridge).
- [ ] Audit retries (single ownership, no double-retry), idempotency/replay correctness, run-level logging/usage accounting, and mode determinism (manual/hybrid/auto).
- [ ] Deliver execution truth table per mode (inputs, nodes, outputs).
- [ ] Add/adjust tests that lock sequencing + mode behavior.
- [ ] Acceptance: `pytest -q ai_analyst/tests` passes and outputs remain schema-valid.

### Audit 4 — Security + Secrets + Supply Chain
- [ ] Scope: `ai_analyst/api/`, logging surfaces, env key handling, `Dockerfile`, `docker-compose*.yml`, `services/*`, GitHub workflows.
- [ ] Validate: secrets not logged/persisted, safe prompt/image path handling, sane CORS/network defaults, dependency risk posture.
- [ ] Deliver threat model (trust boundaries + attacker goals) and severity-ranked findings with exact remediation.
- [ ] Apply minimal safe-default patches only if needed.
- [ ] Acceptance: `make test-all` passes and local dev workflow remains intact.
