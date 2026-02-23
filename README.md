# AI trade analyst

AI prompt generator for chart analysis.

## Repository layout

- `app/` — runnable HTML app prototypes.
- `docs/` — planning/specification material and reference brief.
- `examples/` — sample output/export artifacts.
- `tooling/` — scripts/tooling workspace.

## Data schemas

- `docs/schema/ticket.schema.json` defines the canonical trade ticket payload, including:
  - `schemaVersion` metadata (`1.0.0`)
  - decision/mode enums (`LONG`, `SHORT`, `WAIT`, `CONDITIONAL`)
  - entry/stop/target object structure
  - checklist + gate outcome enums
- `docs/schema/aar.schema.json` defines post-trade AAR payloads, including:
  - `schemaVersion` metadata (`1.0.0`)
  - required outcome/verdict enums
  - review metrics (`rAchieved`, `exitReasonEnum`, `failureReasonCodes`, `psychologicalTag`)
  - checklist delta and review notes

## Backup validation behavior

- `app/scripts/exports/export_json_backup.js` validates generated `ticket` and `aar` objects against schema-aligned validators before download.
- `app/scripts/exports/import_json_backup.js` validates imported backup files before migration.
- `app/scripts/state/storage_local.js` validates payloads before local save/load operations.
