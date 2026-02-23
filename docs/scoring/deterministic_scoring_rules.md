# Deterministic Scoring Rules

This document defines the **current deterministic scoring/gating logic** used by the V3 prompt flow and JSON backup pipeline.

## 1) Pre-ticket completeness gate

A pre-ticket checklist is considered complete when all 8 checklist fields are non-empty:

- `htfState`
- `htfLocation`
- `ltfAlignment`
- `liquidityContext`
- `volRisk`
- `execQuality`
- `conviction`
- `edgeTag`

Formula:

```text
ptcComplete = every(checklistField != '')
```

If `ptcComplete == false`, gate status is `INCOMPLETE`.

## 2) Gate decision formula (ordered precedence)

Gate flags:

```text
isChopOrMessy = (execQuality == 'Chop' || execQuality == 'Messy')
isConflict    = (ltfAlignment == 'Counter-trend' || ltfAlignment == 'Mixed')
isElevatedVol = (volRisk == 'Elevated')
noTradeOK     = (noTradeToggle == true)
```

Final decision is evaluated in this exact order:

1. If `ptcComplete == false` → `INCOMPLETE`
2. Else if `(isChopOrMessy && noTradeOK)` → `WAIT`
3. Else if `(isConflict && isElevatedVol)` → `CAUTION`
4. Else if `(isConflict || isElevatedVol)` → `CAUTION`
5. Else → `PROCEED`

### Tie-breakers / conflict resolution

Because evaluation is ordered, ties are resolved by first match:

- `WAIT` outranks `CAUTION` and `PROCEED` when `isChopOrMessy && noTradeOK` is true.
- Dual-risk `CAUTION` (`isConflict && isElevatedVol`) outranks single-risk `CAUTION` branch, but both persist as the same stored enum: `CAUTION`.
- If none of the risk rules match, status is deterministically `PROCEED`.

## 3) Export snapshot deterministic defaults

When exporting backup JSON, fields not captured from a structured ticket UI are filled by deterministic defaults.

### 3.1 Decision mode

```text
decisionMode = (waitReason is non-empty) ? 'WAIT' : 'CONDITIONAL'
```

### 3.2 Checklist fallbacks

If a checklist value is missing at export time, fallback defaults are applied:

- `htfState`: `Transition`
- `htfLocation`: `Mid-range`
- `ltfAlignment`: `Mixed`
- `liquidityContext`: `None identified`
- `volRisk`: `Normal`
- `execQuality`: `Messy`
- `conviction`: `Medium`
- `edgeTag`: `Other`

### 3.3 Confluence score

```text
confluenceScore = parseInt(input, 10) || 7
```

- Accepted schema domain: integer `1..10`
- Export fallback is `7` if parse fails/returns falsy.

### 3.4 Gate status persistence

UI class → stored enum mapping during export:

- `#gateStatus.wait` → `WAIT`
- `#gateStatus.caution` → `CAUTION`
- `#gateStatus.proceed` → `PROCEED`
- no status class → `INCOMPLETE`

## 4) Metric-related deterministic constraints (validation)

No weighted edge-score formula is implemented yet in runtime scripts. Instead, deterministic constraints are enforced through schema-aligned validators used by import/export.

Current enforced numeric constraints relevant to metrics:

- `ticket.maxAttempts`: integer `1..3`
- `ticket.checklist.confluenceScore`: integer `1..10`
- `aar.revisedConfidence`: integer `1..5`
- `aar.rAchieved`: finite number
- `aar.actualEntry`, `aar.actualExit`: finite numbers

## 5) Stability contract for tests/import-export

To keep imports/exports and tests stable:

1. Treat this file + `enums_reference.md` as canonical behavior docs.
2. If gate logic order changes, update tests and this precedence list in the same PR.
3. If defaults/fallbacks change, update snapshot fixtures that assert exported JSON.
4. If any enum is added/removed/renamed, update:
   - `docs/schema/*.schema.json`
   - runtime validators
   - UI label-to-value mappings
   - import/export fixtures.
