# AI Trade Analyst — Master Development Plan
**Version:** 2.0
**Updated:** 2026-02-24
**Status:** Active — both tracks in parallel development

---

## Overview

This plan supersedes all prior V3 planning documents. The project has evolved into a
two-track architecture:

| Track | Directory | Runtime | Current Version |
|-------|-----------|---------|-----------------|
| **A — Browser App** | `app/` | Static HTML/JS, IndexedDB | G3 in progress |
| **B — AI Pipeline** | `ai_analyst/` | Python 3.11+, LangGraph | v1.2 complete, v1.3 next |

The two tracks are **independent** but share conceptual schema (instrument, session, ticket
fields, regime, risk constraints). A formal integration bridge (Track C) is planned from
G6/v2.0 onwards.

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

### G3 — After-Action Review (AAR) — IN PROGRESS
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

### G10 — Performance Analytics v2 (IN PROGRESS)
- [x] Equity curve simulation based on closed trade history + R values
- [x] Monthly/quarterly breakdown tables (trades, win rate, avg R, net R)
- [ ] Export analytics as PDF report

### G11 — API Bridge (Track A → Track B)
- "Run AI Analysis" button in the app POSTs `GroundTruthPacket`-equivalent payload to
  `ai_analyst` FastAPI endpoint
- Response populates a new "AI Multi-Model Verdict" card in the UI
- Requires local Python server running (documented setup)

### G12 — Polish + Public Release
- Full accessibility audit
- Print stylesheet finalisation
- README / user guide
- Release packaging (`releases/` directory)

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

### v1.3 — Integration Tests + Real Chart Packs (IN PROGRESS)
**Goal:** Validate the full pipeline end-to-end with real chart images.

Tasks:
- [x] Integration test: `run` CLI with 4 real chart PNGs in manual mode → verify prompt pack structure
- [x] Integration test: `arbiter` CLI with pre-filled stub responses → verify FinalVerdict structure
- [ ] API key setup guide (`docs/api_key_setup.md`)
- [x] Test that `replay` command re-runs Arbiter correctly on saved outputs
- [ ] Add `pytest-asyncio` integration test fixtures for LangGraph pipeline
- [x] Verify `json_extractor.py` handles known AI response wrapper patterns

### v1.4 — Prompt Library v1.2 + Lens Tuning
**Goal:** Iterate on prompt quality from real-run feedback.

Tasks:
- [ ] Review first batch of real analyst outputs vs expected lens contract fields
- [ ] Tighten FORBIDDEN TERMINOLOGY sections based on observed violations
- [ ] Add `EXAMPLES` section to each lens (positive and negative examples)
- [ ] Add `minimum_confidence_threshold` metadata to each lens file
- [ ] Versioned prompt library directory: `prompt_library/v1.2/`
- [ ] Lens loader supports version selection: `load_active_lens_contracts(version="v1.2")`

### v2.0 — Ticket Schema Integration + Bridge API
**Goal:** Align `ai_analyst` output with `app/` ticket schema v2.

Tasks:
- [ ] Map `FinalVerdict` fields to `ticket.schema.json` v2 fields
- [ ] `POST /analyse` response includes a `ticket_draft` block ready to import into `app/`
- [ ] `GroundTruthPacket` accepts a `source_ticket_id` for traceability
- [ ] Webhook/callback support for async pipeline completion
- [ ] OpenAPI spec generated from FastAPI and committed to `docs/`

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

## Track C — Integration (app/ ↔ ai_analyst/)

This track begins at G6/v2.0 when both schema and API are stable.

### C1 — Shared Schema Contract
- Formalise ticket schema as a shared JSON Schema file referenced by both tracks
- `ai_analyst` output validated against this schema before any `app/` import

### C2 — Local Server Setup
- `docker-compose.yml` for one-command local start (FastAPI + static file server)
- Health check endpoint used by `app/` to detect if pipeline is available

### C3 — Browser ↔ Pipeline Bridge
- `app/` POSTs `GroundTruthPacket` to local `ai_analyst` server
- Response populates AI verdict card (G11)
- Graceful degradation if server is unavailable

### C4 — Unified Export
- Single export from `app/` includes both ticket data and full analyst JSON logs
- Importable back into either system

---

## Known Technical Debt

### Track A (`app/`)
| Issue | Priority | Target |
|-------|----------|--------|
| `export_json_backup.js` hardcodes G2 fields | High | G2 |
| `exportJSONBackup`/`importJSONBackup` not on `window` | High | G2 |
| `migrations.js` has no `schemaVersion` check | High | G2 |
| Enum cross-check test missing | Medium | G2 |
| No integration test for full G1 flow | Medium | G3 |

### Track B (`ai_analyst/`)
| Issue | Priority | Target |
|-------|----------|--------|
| No end-to-end integration test with real images | High | v1.3 |
| `replay` command not covered by tests | Medium | v1.3 |
| `harmonic.txt` / `volume_profile.txt` lenses are stubs | Medium | v1.4 |
| Arbiter model hardcoded to `claude-haiku-4-5-20251001` | Low | v2.0 |
| No timeout/retry on individual analyst API calls | Medium | v1.3 |

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
| `main` | Stable, reviewed code only |
| `claude/audit-repo-branches-Y2rjV` | Current development session |
| Feature branches | Per-milestone (`feature/g2-prediction-mode`, etc.) |

All Claude-assisted development occurs on session branches and is merged via PR.

---

## Next Immediate Steps (Priority Order)

1. **G6 (Track A)** — Data Model v2 hardening: IndexedDB AAR persistence, auto-save JSON backup
   on ticket generation, `edgeScore` and `psychologicalLeakR` fields in schema v2.0, base64
   chart screenshot embed in HTML export
2. **v1.3 (Track B)** — Run end-to-end integration tests in parallel (real chart pack run,
   arbiter verification, replay coverage, extractor robustness)
3. **Track B debt** — Add timeout/retry wrapper around individual analyst LiteLLM calls
4. **Docs** — Write `docs/api_key_setup.md` guide for Track B configuration
5. **G7 (Track A)** — Mini Dashboard: win rate, avg R, expectancy, heatmap, Psychological Leakage R
   (start after G6 persisted-data reliability hardening)

**Completed in prior sessions:** G1, G2, G3, G4, G5
