# V3 — G3 After-Action Review (AAR)
**Status:** Complete
**Date:** 2026-02-25

---

## What Was Built

G3 adds a dedicated **After-Action Review** step (Step 07) to close the feedback loop after a trade.
The AAR is linked to the pre-trade ticket by `ticketId` and captures structured outcome data.

---

## New Step: 07 — AAR

Located at `#section-6` in `app/index.html`.

### Fields

| Field | Type | Values |
|-------|------|--------|
| `outcomeEnum` | select | WIN / LOSS / BREAKEVEN / MISSED / SCRATCH |
| `verdictEnum` | select | PLAN_FOLLOWED / PROCESS_GOOD / PROCESS_POOR / PLAN_VIOLATION |
| `actualEntry` | number | Price at entry |
| `actualExit` | number | Price at exit |
| `rAchieved` | number | e.g. 1.5, -1.0, 0 |
| `exitReasonEnum` | select | NO_FILL / TP_HIT / SL_HIT / TIME_EXIT / MANUAL_EXIT / INVALIDATION |
| `firstTouch` | radio | Yes / No |
| `wouldHaveWon` | radio (conditional) | Yes / No — shown only for MISSED / SCRATCH |
| `killSwitchTriggered` | radio | No / Yes |
| `failureReasonCodes` | checkbox multi-select | LATE_ENTRY / OVERSIZED_RISK / IGNORED_GATE / MISREAD_STRUCTURE / NEWS_BLINDSPOT / EMOTIONAL_EXECUTION / NO_EDGE |
| `psychologicalTag` | select | CALM / DISCIPLINED / FOMO / HESITATION / REVENGE / OVERCONFIDENCE / FATIGUE |
| `revisedConfidence` | range 1–5 | Post-trade process confidence |
| `edgeScore` | calculated display | `revisedConfidence × verdictMultiplier` |
| `checklistDelta` | 4 text + 1 textarea | What changed vs pre-trade read |
| Journal Photo | file upload | Canvas-watermarked with Ticket ID + timestamp |
| `notes` | textarea (required) | Free-form post-trade summary |

### Edge Score Calculation

```
verdictMultiplier:
  PLAN_FOLLOWED  → 1.0
  PROCESS_GOOD   → 0.8
  PROCESS_POOR   → 0.5
  PLAN_VIOLATION → 0.2

edgeScore = revisedConfidence (1–5) × verdictMultiplier
```

Displayed with colour coding:
- `≥ 4.0` → green (high edge, disciplined process)
- `≥ 2.5` → amber (moderate)
- `< 2.5` → red (poor process or low conviction)

`edgeScore` is a computed display field only in G3. It will be added to the JSON schema in G6.

---

## Trade Journal Photo — Canvas Watermarking

- User uploads any screenshot (outcome chart, trade confirmation, etc.)
- A semi-transparent gold banner is drawn at the bottom of the image
- Watermark text: `{TICKET_ID} · {YYYY-MM-DD HH:MM}Z`
- Font size scales with image height (2.5% of height, min 14px)
- Watermarked JPEG (90% quality) stored as `state.aarState.photoDataUrl`
- Preview shown inline; included in HTML export (not yet in JSON schema — G6)

---

## AAR Prompt Generator

`app/scripts/generators/prompt_aar.js` now auto-populates the ACTUAL OUTCOME block from
the AAR form fields when available. Fields fall back to placeholder text if not filled.

The prompt template includes:
1. Original ticket parameters
2. Pre-ticket read (checklist state)
3. Actual outcome (from AAR form)
4. AI coaching persona (ruthless prop trader — zero comfort)

---

## Export Behaviour

`exportJSONBackup()` now reads actual AAR DOM values:

- If `aarNotes` is empty → exports `notes: "AAR not completed yet."` (valid stub)
- If `aarNotes` is filled → exports actual notes + all other DOM values
- Schema validation still runs before export; fails loudly if schema violated
- `failureReasonCodes` read from the multi-select checkbox grid

---

## Navigation

- Step 06 Output has a new **"After-Action Review →"** button
- Step 07 AAR has:
  - **"← Back to Output"** (goTo 5)
  - **"Generate AAR Prompt"** — calls `buildAARPrompt()`, shows output inline
  - **"Export Full JSON (with AAR)"** — calls `exportJSONBackup()` with live AAR values

---

## Files Changed

| File | Change |
|------|--------|
| `app/index.html` | Added step 07 nav tab, `#section-6` AAR card, JSON export button in step 06, version pill updated to G3 |
| `app/styles/theme.css` | Added `.edge-score-display`, `.edge-high`, `.edge-mid`, `.edge-low` |
| `app/scripts/state/model.js` | Added `aarState: { firstTouch, wouldHaveWon, killSwitch, photoDataUrl }` |
| `app/scripts/ui/form_bindings.js` | Added `selectAARRadio`, `onAAROutcomeChange`, `onAARSlider`, `updateEdgeScore`, `handleAARPhotoUpload` |
| `app/scripts/ui/stepper.js` | Populates `#aarTicketIdLabel` on nav to step 6 |
| `app/scripts/exports/export_json_backup.js` | Replaced `buildAARStub()` with `buildAARPayload()` reading from DOM |
| `app/scripts/generators/prompt_aar.js` | Updated ACTUAL OUTCOME block to read from AAR DOM fields |
| `app/scripts/main.js` | Imported and wired all new AAR functions; added `showAARPrompt`, `copyAARPrompt` |
| `docs/V3_master_plan.md` | Marked G3 in progress, updated Next Steps |

---

## What G3 Does NOT Include (Deferred)

- IndexedDB persistence of AAR state (deferred to G6 along with full data model v2)
- `edgeScore` in JSON export schema (deferred to G6 when schema v2 is formalised)
- Journal photo in JSON export (deferred; photo stored in memory only per session)
- Multi-select `psychologicalTag` (schema is single-value; multi-select deferred to G7+)
