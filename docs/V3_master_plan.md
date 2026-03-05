# AI Trade Analyst — Master Development Plan
**Version:** 2.15
**Updated:** 2026-03-05
**Status:** Active — G12 complete (including Plotly dashboard integration), v2.0 complete, MRO fully complete (P1–P4), v2.0.1 complete, v2.0.2 complete (all 4 CRITICALs + HIGH-1/5/6 + MED-5/8 fixed), v2.1 complete (HIGH-2/3/4/7/8 + MED-1/2/3/4/6/7 + LOW-5/6 + TEST-9/10), LOW-2 closed, Plotly regression fix (dashboard.js), **C4 complete (Unified Export)**, **Phase 2a complete (live feeder bridge + float fix), stability hotfixes complete (asyncio + deterministic ingest tests)**

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
- Browser regression suite: **PASS** (`node --test tests/*.js`) with **150/150 passing**.
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
- **Total: 700 passing, 0 failing** across all three suites (plus 13 intentional MRO skips).
- Operational call: Tracks A (G1–G12) and D (MRO P1–P4) are complete. Track B v2.0.2 complete, v2.1 complete. C4 complete (Unified Export). **Phase 2a complete (live feeder bridge + float fix), stability hotfixes complete (asyncio + deterministic ingest tests)**. Phase 2b (UI polish, region display, mobile, next T.R.A.D.E. page) is next.

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
*Last updated 2026-03-04 (v2.12 — C4 complete). Severity from audit: 🔥 CRITICAL / ⚠️ HIGH / ℹ️ MEDIUM / 💡 LOW.*

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

> Last updated: 2026-03-05 (v2.15). G1–G12, v1.1–v2.1, MRO P1–P4, C1–C4, and Phase 2a are complete. This queue is the sequential execution plan from release verification through production hardening and AI/ML enhancements.

### Phase 1 — Release Verification (Immediate)
1. [ ] Verify app loads from static server
   - Confirm `/app/index.html` loads correctly via Python HTTP server or Docker at `http://localhost:8080/app/`.
2. [ ] Validate export/import roundtrip
   - Run a sample ticket through JSON export and re-import to confirm data integrity.
3. [ ] Validate Plotly-enabled export path
   - Confirm charts render in the analytics dashboard and are captured in HTML/PDF export artifacts.
4. [ ] Confirm schema parity
   - Cross-check `docs/schema/enums.json` against live form enum values in the browser app.

### Phase 2b — UI Polish & Mobile
5. [ ] Implement region display
   - Add geographic/session region visualization to the operator dashboard.
6. [ ] Mobile layout optimization
   - Audit and fix responsive breakpoints in `app/styles/` for small-screen usability.
7. [ ] UI polish pass
   - Refine spacing, typography, and component alignment per Phase 2b spec.

### Phase 3 — Monitoring & Observability
8. [ ] Add structured logging with correlation IDs
   - Thread a `run_id` through all LangGraph nodes and API responses for end-to-end traceability.
9. [ ] Add pipeline metrics collection
   - Instrument LLM cost per run, pipeline latency, and analyst agreement rate; emit to JSONL or a metrics endpoint.
10. [ ] Build operator health dashboard
   - Expose `/metrics` or a simple HTML dashboard showing API health, cost usage, and feeder staleness.

### Phase 4 — Performance
11. [ ] Cache macro context responses
   - Add TTL-based caching in `macro_risk_officer/` to avoid redundant data-source fetches.
12. [ ] Parallelize analyst image analysis
   - Refactor LangGraph nodes to fan out chart analysis steps concurrently where possible.
13. [ ] Audit browser IndexedDB query performance
   - Profile ticket history queries and add pagination or indexed lookups for large trade histories.

### Phase 5 — Operational Tooling
14. [ ] CLI: audit trail export
   - Add a `cli.py export-audit` command that dumps all runs, verdicts, and outcomes to CSV/JSON.
15. [ ] CLI: bulk AAR import
   - Add a `cli.py import-aar` command for batch after-action review updates from CSV.
16. [ ] Analytics CSV export
   - Wire the analytics dashboard export button to produce a CSV compatible with external tools.

### Phase 6 — Production Hardening
17. [ ] Configure CORS origin whitelist
   - Replace wildcard `*` with explicit allowed origins via `.env` `ALLOWED_ORIGINS`.
18. [ ] Set up reverse proxy (Caddy/nginx)
   - Add a `caddy/` or `nginx/` config for HTTPS termination in the Docker Compose setup.
19. [ ] Harden Docker runtime
   - Switch to a non-root user in Dockerfile, add `read_only: true` and `tmpfs: /tmp` in `docker-compose.yml`.
20. [ ] Secrets manager integration
   - Document (or implement) AWS/GCP/Vault secret injection as an alternative to `.env` files.

### Phase 7 — AI/ML Enhancement
21. [ ] Feedback loop: outcomes → prompt refinement
   - Build a script that reads AAR outcome data from SQLite and surfaces patterns for prompt improvement.
22. [ ] Bias detection in analyst outputs
   - Add a post-processing step to the arbiter that flags low-diversity consensus or single-persona dominance.
23. [ ] Fallback model routing
   - Add logic to `core/api_client.py` to retry with a secondary model if the primary API errors or exceeds a cost ceiling.

**Rationale for sequencing:** start with low-risk release verification, then UI fit-and-finish, then observability/performance/tooling, and finish with operational hardening and AI enhancements on top of a stable baseline.
