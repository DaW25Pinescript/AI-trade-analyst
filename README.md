# AI Trade Analyst

AI Trade Analyst is a static, browser-run workflow app for discretionary trade planning and review. It guides users from chart/context intake to structured ticket generation, then into after-action review (AAR) and exportable artifacts.

## Project purpose and current status

### Purpose

- Standardize trade planning with enum-driven, schema-backed form inputs.
- Generate consistent AI-ready prompts and human-readable reports from the same source state.
- Preserve an auditable lifecycle across ticket creation, gate evaluation, export/import backups, and post-trade review.

### Current status

- The repository currently ships a runnable static app in `app/` plus milestone snapshots in `app/releases/`.
- V3 is being executed in phased milestones; planning documents indicate the direction is ship-ready with execution focused on sequencing and hardening.
- JSON schema definitions for ticket and AAR payloads are present and used for compatibility validation in import/export and local storage flows.

## Directory map (current layout)

```text
.
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
├── tests/                          # Node test suite + fixtures
├── tooling/                        # Reserved for helper scripts/tooling
├── LICENSE
└── README.md
```

## V3 phase plan (G1-G12)

Primary build order in planning docs:

`G1 -> G2 -> G3 -> G4 (A1 + A4) -> G5 -> G6 -> G7 -> G8 -> G9 -> G10 -> G11 -> G12`

Suggested milestone interpretation for delivery tracking:

- **G1:** Baseline redesign (multi-step V3 UI foundation).
- **G2:** Test/prediction mode + richer ticket enums + conditional scenario flow.
- **G3-G4:** Core model/logic consolidation and selected enhancement set (A1/A4).
- **G5-G8:** Persistence hardening, export robustness, and operational workflow refinement.
- **G9-G10:** Dashboard/reporting depth and calibration loops.
- **G11-G12:** Final polish, release hardening, and production-readiness checks.

Reference planning docs:

- `docs/V3_master_plan.md`
- `docs/V3_G1_draft.md`
- `docs/V3_G2_notes.md`

## Local run instructions (static app development)

Because this is a static app, use any local static file server from the repository root.

### Option A: Python (no dependency install)

```bash
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000/app/`

### Option B: Node (if you prefer)

```bash
npx serve .
```

Then open the URL printed by `serve` and navigate to `/app/`.

## Testing commands

Run the Node test suite from the repo root:

```bash
node --test tests/*.js
```

This covers:

- deterministic gate/scoring behavior,
- schema enum stability, and
- core metrics/calibration fixture expectations.

## Release checklist references

Use these references when cutting or validating milestones:

- `app/releases/README.md` for snapshot inventory and version-to-version deltas.
- `docs/V3_master_plan.md` for planned milestone ordering and scope.
- `tests/` suite as a minimum regression gate before snapshot updates.

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
