# AI Trade Analyst — Master Development Plan
**Version:** 2.4
**Updated:** 2026-03-02
**Status:** Active — G11 infrastructure complete (UI verdict card pending), v2.0 complete, MRO fully complete (P1–P4)

---

## Overview

This plan supersedes all prior V3 planning documents. The project has evolved into a
two-track architecture:

| Track | Directory | Runtime | Current Version |
|-------|-----------|---------|-----------------|
| **A — Browser App** | `app/` | Static HTML/JS, IndexedDB | G1–G10 complete, G11 partial, G12 next |
| **B — AI Pipeline** | `ai_analyst/` | Python 3.11+, LangGraph | v2.0 complete, v2.1 next |
| **C — Integration** | shared | schema + bridge | C1 complete, C2 complete, C3 partial |
| **D — Macro Risk Officer** | `macro_risk_officer/` | Python 3.11+, standalone | **ALL COMPLETE (P1–P4)** |

The two tracks are **independent** but share conceptual schema (instrument, session, ticket
fields, regime, risk constraints). A formal integration bridge (Track C) is planned from
G6/v2.0 onwards.

### Current verification snapshot (2026-03-02)
- Browser regression suite: **PASS** (`node --test tests/*.js`) with **105/105 passing**.
- AI analyst regression suite: **PASS** (`pytest -q ai_analyst/tests`) with **256/256 passing**.
- MRO regression suite: **PASS** (`pytest -q macro_risk_officer/tests`) with **153 passed, 16 skipped** (skips = live smoke tests requiring `MRO_SMOKE_TESTS=1` + real API keys — by design).
- **Total: 514 passing, 0 failing** across all three suites.
- Operational call: Track D fully complete; G11 UI card is the single remaining blocker before G12.

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

### v2.1 — Multi-Round Deliberation
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

### C3 — Browser ↔ Pipeline Bridge (PARTIAL — G11 UI card remaining)
- [x] Bridge transport hardened (timeout, retry, 5xx paths tested)
- [x] `app/scripts/main.js` envelope unpacking (`response.verdict`)
- [ ] "Run AI Analysis" button POST wired in browser app
- [ ] Verdict card populated from API response in UI
- [ ] Graceful degradation UX when server unreachable

### C4 — Unified Export
- Single export from `app/` includes both ticket data and full analyst JSON logs
- Importable back into either system

---

## Known Technical Debt

### Track A (`app/`)
| Issue | Priority | Target |
|-------|----------|--------|
| G11 "Run AI Analysis" button not yet wired to POST | High | G11 |
| AI Multi-Model Verdict card not populated from response | High | G11 |
| All G2 debt items | Resolved | G2 |

### Track B (`ai_analyst/`)
| Issue | Priority | Target |
|-------|----------|--------|
| `harmonic.txt` / `volume_profile.txt` lenses are stubs | Medium | v2.x |
| Arbiter model hardcoded to `claude-haiku-4-5-20251001` | Low | v2.1 |
| Webhook/callback for async pipeline completion | Low | v2.1+ |
| All v1.3 debt items | Resolved | v1.3 |

### Track D (`macro_risk_officer/`)
| Issue | Priority | Target |
|-------|----------|--------|
| Live smoke tests require manual env var + real API keys | Low | by design |
| Price outcome accuracy requires real trade data to be meaningful | Low | ongoing |

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

> Last updated: 2026-03-02. All MRO phases complete. Test suite: 514 passing, 0 failing.

1. **G11 completion — "Run AI Analysis" button + verdict card (Track A + C3)**
   The single remaining G11 item. Wire the POST from the browser app to `/analyse`,
   unpack the `AnalysisResponse` envelope, and populate the AI Multi-Model Verdict card
   in the UI. Add graceful degradation UX for when the Python server is unreachable.
   **This unblocks G12.**

2. **G12 — Polish + Public Release (Track A)**
   Full accessibility audit, print stylesheet finalisation, user guide update, and
   release packaging in `releases/`. Only starts once G11 is fully green.

3. **v2.1 — Multi-Round Deliberation (Track B)**
   Optional second-round analyst fan-out after initial results, with Arbiter weighting
   both rounds. Config flag `enable_deliberation: bool = False` (off by default).
   Independent of G11/G12 — can be developed in parallel.

4. **C4 — Unified Export (Track C)**
   Single `app/` export that includes ticket data + full analyst JSON logs from the
   pipeline, importable back into either system.

5. **v2.2 — Streaming + Real-Time UI (Track B)**
   Server-Sent Events from FastAPI as analysts complete; CLI live progress; browser
   app SSE subscription (requires G11 complete first).

**Completed:** G1–G10, G3 (AAR), v1.1–v2.0, MRO-P1/P2/P3/P4, C1, C2, G11 infrastructure
**In progress:** G11 UI card (C3 final leg)
**Not started:** G12, v2.1, C4, v2.2
