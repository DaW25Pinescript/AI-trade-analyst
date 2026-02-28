# AI Trade Analyst

AI Trade Analyst is a two-part system for discretionary trade planning and review:

1. **Static browser app** (`app/`) — a client-side workflow for structured ticket generation, gate evaluation, export/import, and after-action review (AAR).
2. **Python AI analyst** (`ai_analyst/`) — a multi-model, multi-persona analysis pipeline that accepts chart images and produces structured trade verdicts via CLI.

---

## Project purpose and current status

### Purpose

- Standardize trade planning with enum-driven, schema-backed form inputs.
- Generate consistent AI-ready prompts and human-readable reports from the same source state.
- Preserve an auditable lifecycle across ticket creation, gate evaluation, export/import backups, and post-trade review.
- Run multi-model AI analysis (manual, hybrid, or fully automated) with a structured Arbiter verdict.

### Current status

- The repository ships a runnable static app in `app/` plus milestone snapshots in `app/releases/`.
- The Python AI analyst (`ai_analyst/`) is at v1.2 and supports manual, hybrid, and automated execution modes.
- V3 of the browser app is being executed in phased milestones (G1–G12); planning documents indicate the direction is ship-ready with execution focused on sequencing and hardening.
- JSON schema definitions for ticket and AAR payloads are present and used for compatibility validation in import/export and local storage flows.

---

## Directory map

```text
.
├── ai_analyst/                     # Python multi-model AI analyst (v1.2)
│   ├── cli.py                      # CLI entrypoint (run, status, arbiter, history, replay)
│   ├── requirements.txt            # Python dependencies
│   ├── pytest.ini                  # Pytest config
│   ├── api/                        # FastAPI server (optional HTTP interface)
│   ├── core/                       # Execution router, prompt builders, API key manager
│   ├── graph/                      # LangGraph pipeline and node definitions
│   ├── models/                     # Pydantic models (ground truth, personas, output, config)
│   ├── output/                     # Generated run output (gitignored)
│   ├── prompt_library/             # Versioned lens and analyst prompt files
│   ├── data/                       # Sample chart images for testing
│   └── tests/                      # Pytest suite for analyst pipeline
├── app/
│   ├── index.html                  # Main static entrypoint
│   ├── scripts/
│   │   ├── exports/                # Export + import backup logic
│   │   ├── generators/             # Prompt/report generators
│   │   ├── schema/                 # Runtime validation helpers
│   │   ├── state/                  # State model, migration, local storage
│   │   └── ui/                     # UI logic (stepper, gates, bindings)
│   ├── styles/                     # Theme + print styles
│   └── releases/                   # Standalone milestone HTML snapshots
├── docs/
│   ├── schema/                     # Canonical JSON schemas (ticket + AAR)
│   ├── scoring/                    # Deterministic scoring references
│   └── V3_*.md                     # V3 planning and design notes
├── examples/                       # Example ticket/AAR/report artifacts
├── tests/                          # Node test suite + fixtures (browser app)
├── tooling/                        # Helper scripts and tooling notes
├── run_ai_trade_analyst_python.bat # Windows one-click launcher (static app)
├── LICENSE
└── README.md
```

---

## Static browser app

### Running locally

Because this is a static app, use any local static file server from the repository root.

**Option A: Python (no install required)**

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000/app/`

**Option B: Node**

```bash
npx serve .
```

Then navigate to `/app/` at the URL printed by `serve`.

**Option C: Windows launcher**

Double-click `run_ai_trade_analyst_python.bat` — it auto-detects Python, starts the server, and opens the browser.

### Option D: Docker Compose (app + API bridge)

```bash
docker compose up
```

Then open:
- Static app: `http://localhost:8080/app/`
- AI Analyst API health: `http://localhost:8000/health`

This is the fastest way to run the G11 bridge locally with both services up together.

### Testing (Node)

Run the Node test suite from the repo root:

```bash
node --test tests/*.js
```

This covers deterministic gate/scoring behavior, schema enum stability, and core metrics/calibration fixture expectations.

---

## Python AI analyst

### Setup

```bash
pip install -r ai_analyst/requirements.txt
```

API keys go in `ai_analyst/.env`:

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GEMINI_API_KEY=...
```

Any key that is absent causes that analyst to fall back to manual mode.

### Execution modes

| Mode | Behavior |
|---|---|
| `manual` | Generates prompt packs for all analysts; you paste prompts into any AI and paste responses back |
| `hybrid` | Uses available API keys for automated analysts; remaining analysts run manually |
| `automated` | All analysts run via API — requires all keys to be set |

### CLI commands

**Check API key status and recommended mode**

```bash
python ai_analyst/cli.py status
```

**Start a new analysis run**

```bash
python ai_analyst/cli.py run \
  --instrument XAUUSD \
  --session NY \
  --mode hybrid \
  --d1 charts/d1.png \
  --h4 charts/h4.png \
  --h1 charts/h1.png \
  --m15 charts/m15.png
```

Key options:

| Flag | Default | Description |
|---|---|---|
| `--instrument` | required | e.g. `XAUUSD`, `EURUSD` |
| `--session` | required | `NY`, `London`, `Asia` |
| `--mode` | `hybrid` | `manual`, `hybrid`, `automated` |
| `--d1/--h4/--h1/--m15/--m5` | — | Chart image paths |
| `--balance` | `10000` | Account balance |
| `--min-rr` | `2.0` | Minimum R:R threshold |
| `--max-risk` | `0.5` | Max risk per trade (%) |
| `--regime` | `unknown` | `trending`, `ranging`, `unknown` |
| `--news-risk` | `none_noted` | `none_noted`, `elevated`, `critical` |

**Lens toggles** (all default off except ICT and Market Structure):

```
--lens-ict / --no-ict
--lens-ms / --no-ms
--lens-orderflow / --no-orderflow
--lens-trendlines / --no-trendlines
--lens-smt / --no-smt
```

**After filling in manual response files, run the Arbiter**

```bash
python ai_analyst/cli.py arbiter --run-id <run-id>
```

**List all past runs**

```bash
python ai_analyst/cli.py history
```

**Replay a past run (re-runs Arbiter with same analyst outputs)**

```bash
python ai_analyst/cli.py replay --run-id <run-id>
```

Useful for testing prompt changes without re-running analysts.

### Analyst personas

Each run dispatches four analyst personas:

- `DEFAULT_ANALYST` — balanced multi-timeframe assessment
- `RISK_OFFICER` — risk and invalidation focus
- `PROSECUTOR` — adversarial bias, looks for reasons not to trade
- `ICT_PURIST` — ICT/SMC methodology specialist

An Arbiter node synthesizes all analyst outputs into a `FinalVerdict` with a trade decision, approved setups, confidence score, and no-trade conditions.

### Testing (pytest)

```bash
cd ai_analyst
pytest
```

Covers arbiter rules, lens contracts, prompt builder contracts, and Pydantic schema validation.

---

## V3 browser app phase plan (G1–G12)

Primary build order:

`G1 → G2 → G3 → G4 (A1 + A4) → G5 → G6 → G7 → G8 → G9 → G10 → G11 → G12`

Milestone summary:

| Group | Scope |
|---|---|
| G1 | Baseline redesign — multi-step V3 UI foundation |
| G2 | Test/prediction mode, richer ticket enums, conditional scenario flow |
| G3–G4 | Core model/logic consolidation + enhancement set A1/A4 |
| G5–G8 | Persistence hardening, export robustness, operational workflow refinement |
| G9–G10 | Dashboard/reporting depth and calibration loops |
| G11–G12 | Final polish, release hardening, production-readiness checks |

Reference planning docs:

- `docs/V3_master_plan.md`
- `docs/V3_G1_draft.md`
- `docs/V3_G2_notes.md`
- `docs/V3_G3_notes.md`

---

## Import/export compatibility and schema versioning

### Compatibility guarantees

- Ticket and AAR payloads are treated as schema-governed contracts (`docs/schema/*.schema.json`).
- Exported backup JSON is validated before download.
- Imported backup JSON is validated before migration/application.
- Local storage load/save paths also validate payload shape compatibility.

### Schema versioning notes

- Both ticket and AAR contracts include `schemaVersion` metadata (currently `1.0.0`).
- Backward-compatible changes should be additive and preserve required enum/value semantics where possible.
- Breaking changes require:
  1. a schema version bump,
  2. migration logic updates in `app/scripts/state/migrations.js`, and
  3. fixture/test updates in `tests/` to lock expected behavior.

---

## Release checklist references

- `app/releases/README.md` — snapshot inventory and version-to-version deltas.
- `docs/V3_master_plan.md` — planned milestone ordering and scope.
- `tests/` Node suite — minimum regression gate before snapshot updates.
- `ai_analyst/tests/` pytest suite — minimum regression gate for the AI pipeline.
