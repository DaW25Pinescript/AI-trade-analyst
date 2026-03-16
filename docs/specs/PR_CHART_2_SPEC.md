# AI Trade Analyst — PR-CHART-2: Run Context Overlay + Multi-Timeframe Charts Spec

**Status:** ✅ Complete  
**Date:** 16 March 2026  
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Branch:** `pr-chart-2-run-context`  
**Phase:** PR-CHART-2 (Phase 8)  
**Depends on:** PR-RUN-1 complete, PR-CHART-1 complete

---

## 1. Purpose

PR-CHART-2 adds **run-aware chart context** to the existing chart lane so the user can:

1. view OHLCV candles for the selected instrument,
2. switch between available chart timeframes for that instrument,
3. see a **run-time visual marker** for the selected run,
4. see a compact verdict annotation derived from the selected run,
5. degrade cleanly when the run timestamp cannot be aligned to the loaded candles.

This PR is **not** a review engine, replay engine, or indicator-overlay phase. It adds bounded run context to the chart workspace only.

---

## 2. Why this PR exists

PR-CHART-1 shipped the chart seam and a basic embedded candlestick chart. The current chart shows price context, but not **decision context**.

This phase answers:

- where in the chart the selected run happened,
- what the system decided at that point,
- how to inspect that run across available timeframes,
- how to do all of the above without introducing brittle coupling or broad backend expansion.

**From → To**

- **From:** chart shows candles for the selected instrument, typically at default timeframe, with no run-awareness.
- **To:** chart is run-aware: it can display a marker for the selected run, annotate the verdict, support instrument-specific timeframe selection, and degrade safely when the run cannot be placed.

**Chart placement (LOCKED):** embedded panel in Run mode context, not a standalone workspace.

---

## 3. Scope

### In scope

- Data-driven timeframe selection for the active instrument
- Run-time visual marker on the chart
- Compact verdict annotation near the run marker
- Deterministic fallback when the run cannot be shown in the loaded chart window
- Instrument/timeframe switching behavior for Run mode
- Targeted tests for UI state, normalization, fallback, malformed payload handling, and regression safety
- Bounded backend read-side additions **only if diagnostics prove required**

### Out of scope

- Trade quality scoring
- Reflect/review logic
- Replay mode, scrubber, or historical playback
- Indicator overlays (EMA, pivots, FVG, MACD, etc.)
- Chart drawing tools or annotation editing
- Backtesting or strategy features
- New persistence
- WebSocket / SSE / live-push
- Generic overlay/annotation framework
- Standalone chart workspace
- Any redesign of Agent Ops layout beyond what is necessary to wire the chart state cleanly

---

## 4. Locked contract decisions

These decisions are part of the spec and are **not optional implementation choices**.

### 4.1 Run-time visual marker abstraction

The chart must render a **run-time visual marker**.

This is an abstract requirement, not a hard requirement for a true geometric vertical line.

Acceptable implementations:

1. **Preferred:** a true vertical-style marker if the installed chart library supports it cleanly.
2. **Fallback:** a candle-aligned marker/annotation at the selected run timestamp.

All non-success states in this spec apply to the abstract **run-time visual marker** regardless of implementation method.

### 4.2 Timeframe discovery

Available chart timeframes must be **data-driven** per instrument.

Allowed sources, in priority order:

1. Existing backend response if diagnostics prove it already exposes valid selectable chart timeframes.
2. A bounded new read-side endpoint if diagnostics prove no existing source is suitable.

If a new endpoint is required, the contracts are locked:

**Success response:**

```json
{
  "instrument": "XAUUSD",
  "available_timeframes": ["15m", "1h", "4h", "1d"]
}
```

No alternate envelope is allowed.

**Error responses:**

| HTTP status | Error code | When |
|------------|------------|------|
| 404 | `INSTRUMENT_NOT_FOUND` | Instrument not in registry |
| 500 | `TIMEFRAME_DISCOVERY_FAILED` | Manifest could not be read |

Errors use `OpsErrorEnvelope` shape, consistent with all other endpoints.

### 4.3 Timeframe fallback on instrument change

If the current selected timeframe is invalid for the newly selected instrument, the UI must reset deterministically:

1. Use `4h` if present,
2. else use the first available timeframe in backend order,
3. else enter the "no timeframes available" state.

### 4.4 Verdict normalization

Run verdicts must be normalized before display.

| Raw input | Normalized verdict |
|-----------|-------------------|
| `BUY`, `LONG`, `ENTER_LONG` | `BUY` |
| `SELL`, `SHORT`, `ENTER_SHORT` | `SELL` |
| `NO_TRADE`, `FLAT`, `SKIP` | `NO_TRADE` |
| Unknown, `null`, missing, or malformed | `UNKNOWN` |

Display behavior:

| Normalized | Styling |
|-----------|---------|
| `BUY` | Bullish (green) |
| `SELL` | Bearish (red) |
| `NO_TRADE` | Neutral (amber) |
| `UNKNOWN` | Muted neutral with label "Unknown" |

### 4.5 Timestamp alignment rule

The selected run timestamp is the canonical run-time input.

**Marker placement rule:** Anchor to the candle whose timestamp is the **nearest candle at or before** the run timestamp within the loaded candle range.

If no candle exists at or before the run timestamp in the loaded range, treat the run as out of range.

### 4.6 Viewport rule

The target run candle does not need perfect centering.

**Success requirement:** The target candle must be **visible** in the loaded range when alignment is possible.

No stricter geometric centering rule is required.

### 4.7 Backend posture

This PR is **frontend-first**.

Backend changes are allowed only if diagnostics prove they are required:

- A read-only timeframe discovery endpoint with the exact response shape and error contract defined in §4.2.
- A bounded read-only OHLCV query enhancement if existing chart data loading cannot show the relevant run window.

If neither is required, this PR remains frontend-only.

If either is added:

- No existing endpoint contract may be broken.
- No write path may change.
- All additions are read-side only, additive, use `OpsErrorEnvelope` for errors.
- Docs must be updated accordingly.

---

## 5. UI contract

### 5.1 Parent state ownership

`AgentOpsPage` remains the parent controller for selected run and selected instrument.

Chart-local state may manage chart rendering details, but must not duplicate authoritative run selection state.

### 5.2 CandlestickChart props

The chart surface must support the following inputs, whether directly or through a thin wrapper:

```typescript
interface CandlestickChartProps {
  instrument: string | null;
  selectedRunTimestamp?: string | null;
  selectedRunVerdict?: string | null;
  availableTimeframes?: string[] | null;
  selectedTimeframe?: string | null;
  onTimeframeChange?: (tf: string) => void;
}
```

Exact prop names may differ in implementation, but these semantics must be present.

### 5.3 Chart UI states

The chart must support these explicit states:

**1. No run selected**
- Chart renders normally.
- No run-time visual marker.
- No verdict annotation.

**2. Loading timeframe discovery**
- Chart area remains stable.
- Timeframe controls show loading state.
- No crash or layout shift beyond ordinary loading affordance.

**3. Timeframes available**
- Tabs or selector render from discovered values.
- Current selection is visually indicated.

**4. No timeframes available**
- No timeframe tabs rendered.
- Chart fetch is withheld or disabled.
- Inline message shown: "No chart timeframes available for this instrument."

**5. Timeframe discovery failed**
- No timeframe tabs rendered.
- Chart fetch is withheld or disabled.
- Inline message shown: "Unable to load chart timeframes."

**6. Chart fetch failed for selected timeframe**
- Previously rendered chart may remain visible if available, or empty chart state may show.
- Inline message shown: "Unable to load chart data for this timeframe."
- **Other timeframe tabs remain functional** — failure is per-tab, not global.

**7. Run aligned successfully**
- Run-time visual marker shown.
- Compact verdict annotation shown.

**8. Run out of range**
- No run-time marker rendered.
- Subtle inline indicator shown: "Selected run is outside the loaded chart range."

**9. Run timestamp invalid**
- No run-time marker rendered.
- Subtle inline indicator shown: "Selected run timestamp is invalid."

**10. Malformed response**
- No crash.
- Degrade to the nearest safe empty/error state for that surface.

---

## 6. Derived behavior rules

### 6.1 Timeframe selection

User selects instrument → available timeframes are discovered.

- If current timeframe remains valid, preserve it.
- If invalid, apply deterministic fallback per §4.3.
- If no timeframes, show no-timeframes state.
- If discovery fails, show discovery-failure state.
- If discovery payload is malformed, treat as discovery failure.
- **On instrument change:** TF tabs must refresh to show the new instrument's available timeframes (not stale tabs from the previous instrument).

### 6.2 Run overlay behavior

- If no run selected → no marker.
- If selected run timestamp is valid and within loaded range → show marker + annotation.
- If timestamp invalid → show invalid-timestamp indicator only.
- If timestamp valid but not alignable within loaded range → show out-of-range indicator only.

### 6.3 Verdict annotation content

The compact annotation must display the normalized verdict label.

Confidence display is optional — include only if already available from the existing run-browser/read model without additional backend contract work.

### 6.4 Malformed data behavior

| Malformed input | Behavior |
|----------------|----------|
| Malformed timeframe discovery payload | Treat as discovery failure |
| Malformed OHLCV payload | Treat as chart fetch failure |
| Malformed verdict | Normalize to `UNKNOWN` |
| Malformed timestamp | Invalid-timestamp state |

---

## 7. Pre-code diagnostic protocol

**Do not implement until this diagnostic is reviewed.**

### 7.1 Confirm run-browser payload shape

Capture at least one real `GET /runs/` payload example (or equivalent dev response) and record:

- timestamp field name,
- timestamp example value,
- final decision field name,
- actual final decision sample values,
- instrument field name.

**Fixture inspection alone is insufficient.** Verify against actual endpoint output or confirmed test mocks.

### 7.2 Confirm timestamp semantics

Verify:

- Run timestamp timezone/format (expect: ISO 8601 UTC).
- Candle timestamp timezone/format (expect: epoch seconds UTC).
- Conversion compatibility.
- Whether chart timestamps and run timestamps can be compared deterministically.

### 7.3 Audit timeframe availability source

Inspect current backend/chart data responses and determine:

- Whether a valid per-instrument timeframe list already exists in any response.
- Whether those values exactly match legal chart timeframe request values.

If not, justify the new endpoint.

### 7.4 Audit useMarketData consumers

Enumerate all current call sites and record whether this PR changes behavior for any surface besides the intended chart lane.

### 7.5 Confirm marker feasibility with installed chart library

Use the installed `lightweight-charts` version and confirm:

- Whether a clean vertical-style marker is possible.
- Whether fallback candle marker is required.

**Type-file grep alone is insufficient** — use runtime/dev verification if needed. A minimal proof-of-concept marker on the existing chart is the gold standard.

### 7.6 Confirm existing chart data window behavior

Determine whether the current OHLCV fetch window is sufficient to show the selected run in normal cases.

If not, document the minimum bounded backend enhancement required.

### 7.7 Confirm malformed-payload handling seam

Identify where response validation or defensive guards should live so malformed timeframe data or OHLCV payloads degrade safely without crashing the page.

### 7.8 Baseline regression check

Record:

- Existing frontend test count.
- Existing chart-related test count.
- All current `useMarketData` consumers.
- Whether any existing chart behavior depends on implicit defaults that this PR could disrupt.

### 7.9 Diagnostic output must explicitly state

At the top of the diagnostic report, prominently record:

1. **Marker method:** vertical-style or candle-marker fallback.
2. **Timeframe discovery path:** existing source or new endpoint.
3. **Time-window alignment path:** frontend-only or bounded OHLCV enhancement.
4. **Backend additions used:** none, timeframe discovery, OHLCV window enhancement, or both.

---

## 8. Acceptance criteria

### Discovery / timeframe behavior

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-1 | When an instrument with available timeframes is selected, the UI renders timeframe controls from data-driven values | ✅ Done |
| AC-2 | When the selected instrument changes and the previous timeframe is still valid, the timeframe selection is preserved | ✅ Done |
| AC-3 | When the selected instrument changes and the previous timeframe is invalid, the UI falls back to `4h` if available | ✅ Done |
| AC-4 | If `4h` is unavailable, the UI falls back to the first available timeframe | ✅ Done |
| AC-5 | If timeframe discovery returns an empty list, no tabs are shown and "No chart timeframes available for this instrument." is displayed | ✅ Done |
| AC-6 | If timeframe discovery fails, no tabs are shown and "Unable to load chart timeframes." is displayed | ✅ Done |
| AC-7 | If timeframe discovery payload is malformed, the UI degrades safely to the same state as AC-6 | ✅ Done |
| AC-8 | If chart fetch for a selected timeframe fails, the UI shows "Unable to load chart data for this timeframe." — **other tabs remain functional** | ✅ Done |
| AC-9 | When the selected instrument changes, TF tabs visually refresh to show the new instrument's available timeframes | ✅ Done |

### Run overlay behavior

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-10 | If no run is selected, no run-time marker or verdict annotation is shown | ✅ Done |
| AC-11 | If a selected run has a valid timestamp within the loaded candle range, a run-time visual marker is shown | ✅ Done |
| AC-12 | If a selected run has a valid timestamp within the loaded candle range, a compact verdict annotation is shown using normalized verdict values | ✅ Done |
| AC-13 | If the selected run timestamp is invalid or unparsable, no marker is shown and "Selected run timestamp is invalid." is displayed | ✅ Done |
| AC-14 | If the selected run timestamp is valid but outside the loaded chart range, no marker is shown and "Selected run is outside the loaded chart range." is displayed | ✅ Done |
| AC-15 | If no candle exists at or before the run timestamp in the loaded range, the UI behaves as AC-14 | ✅ Done |

### Verdict normalization

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-16 | `BUY`, `LONG`, and `ENTER_LONG` display as `BUY` with bullish styling | ✅ Done |
| AC-17 | `SELL`, `SHORT`, and `ENTER_SHORT` display as `SELL` with bearish styling | ✅ Done |
| AC-18 | `NO_TRADE`, `FLAT`, and `SKIP` display as `NO_TRADE` with neutral styling | ✅ Done |
| AC-19 | Unknown, null, or malformed verdict values display as "Unknown" with muted neutral styling | ✅ Done |

### Timestamp compatibility

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-20 | Valid UTC ISO run timestamps align deterministically against candle timestamps without timezone drift | ✅ Done |
| AC-21 | If timestamp conversion fails, the UI degrades safely to AC-13 | ✅ Done |

### Regression / isolation

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-22 | Existing non-run chart behavior continues to work without requiring a selected run | ✅ Done |
| AC-23 | Existing `useMarketData` consumers outside the intended chart lane do not change behavior unexpectedly | ✅ Done |
| AC-24 | Any backend seam added for this PR is read-only, additive, and does not break existing endpoint contracts | ✅ Done |
| AC-25 | Chart failure (overlays, TF fetch, marker error) does NOT block trace panel rendering | ✅ Done |

### Defensive handling

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-26 | Malformed OHLCV payloads do not crash the page and degrade to chart-fetch failure state | ✅ Done |
| AC-27 | Malformed timeframe payloads do not crash the page and degrade to discovery-failure state | ✅ Done |
| AC-28 | Null or missing selected run values do not crash the page | ✅ Done |
| AC-29 | Missing verdict values do not crash the page and normalize to `UNKNOWN` | ✅ Done |
| AC-30 | Missing timestamp values do not crash the page and degrade to invalid-timestamp state | ✅ Done |

### Diagnostics / closure

| # | Acceptance Condition | Status |
|---|---------------------|--------|
| AC-31 | The implementation report records the chosen timeframe-discovery path: existing source vs new endpoint | ✅ Done |
| AC-32 | The implementation report records the chosen marker implementation: vertical-style vs candle-marker fallback | ✅ Done |
| AC-33 | The implementation report records the backend additions used: none, timeframe discovery, OHLCV window enhancement, or both | ✅ Done |

---

## 9. Test expectations

Minimum required test coverage:

### Frontend

- Timeframe discovery success
- Timeframe discovery empty list
- Timeframe discovery failure
- Malformed timeframe payload
- Instrument switch preserving valid timeframe
- Instrument switch deterministic fallback
- Instrument switch refreshes TF tabs
- Run selected / no run selected
- Valid timestamp aligned
- Invalid timestamp
- Out-of-range timestamp
- Verdict normalization including unknown/malformed values
- Chart fetch failure (per-tab — other tabs still work)
- Malformed OHLCV payload
- Regression safety for non-run chart usage
- Chart isolation: overlay failure does not block trace

### Backend (only if backend changes are added)

- Exact discovery response envelope
- Unknown instrument → 404 with `OpsErrorEnvelope`
- No contract break for existing consumers
- Bounded query behavior for any new OHLCV window parameter
- Negative case handling for invalid params

---

## 10. Implementation constraints

- Do not broaden this PR into review/reflection logic.
- Do not add persistence.
- Do not redesign unrelated Agent Ops panels.
- Do not assume undocumented backend fields.
- Do not silently normalize unknown verdicts into `NO_TRADE`; use `UNKNOWN`.
- Do not crash on malformed payloads.
- Do not introduce breaking changes to existing chart consumers.
- Keep backend changes read-only and minimal if diagnostics require them.
- Do not add indicator overlays, drawing tools, replay controls, or generic abstraction layers.
- PR-CHART-2 is strictly limited to: timeframe tabs, run marker, and verdict annotation.

---

## 11. Success definition

PR-CHART-2 is done when:

- the chart supports data-driven timeframe selection,
- the selected run can be visually contextualized on the chart,
- invalid / out-of-range / malformed states degrade safely,
- per-timeframe failures do not break other tabs,
- chart failure does not block trace panel rendering,
- regression risk to existing chart consumers is covered,
- docs reflect the actual chosen implementation path,
- no hidden scope expansion occurred.

---

## 12. Diagnostic findings

### Marker implementation chosen

**Candle-marker via `createSeriesMarkers`** (lightweight-charts v5.1.0 native plugin). No native vertical-line API exists in lightweight-charts v5. Series markers support `position` (aboveBar/belowBar), `shape` (arrowUp/arrowDown/circle), `color`, `text`, and `size`. Failure-tolerant — if markers fail to render, candlestick rendering continues unaffected.

### Timeframe discovery path chosen

**New endpoint: `GET /market-data/{instrument}/timeframes`** — reads from `INSTRUMENT_REGISTRY` (the canonical per-instrument metadata source). No existing API exposed per-instrument available timeframes. The `KNOWN_TIMEFRAMES` constant in `market_data_read.py` is incorrect for metals (assumes all 6 TFs) and was NOT used.

Response shape: `{ "instrument": "XAUUSD", "available_timeframes": ["15m", "1h", "4h", "1d"] }`
Error contract: 404 `INSTRUMENT_NOT_FOUND`, 500 `TIMEFRAME_DISCOVERY_FAILED` (OpsErrorEnvelope).

### Time-window alignment path chosen

**Frontend-only** — no OHLCV backend enhancement required. The default `limit=100` at 4h covers ~16.7 days of history, sufficient for recent runs. The existing `limit` query param (1–500) can be increased if needed. Out-of-range runs degrade gracefully to the "outside loaded chart range" UI state.

### Timestamp compatibility confirmation

- Run timestamps: ISO 8601 UTC strings (Z suffix, e.g. `"2026-03-14T11:02:18Z"`)
- Candle timestamps: Unix epoch seconds (integer)
- Conversion: `Math.floor(new Date(isoString).getTime() / 1000)` — deterministic, lossless, both UTC
- Invalid timestamps caught with NaN guard and degrade to "timestamp invalid" UI state

### useMarketData backward-compatibility assessment

**Confirmed backward-compatible.** One active consumer (`CandlestickChart.tsx`). Hook signature unchanged — no new required params. The hook's return type `UseQueryResult<OHLCVResponse, Error>` is preserved. All existing query keys, stale times, and cache behavior unchanged.

### Backend additions used

**TF discovery endpoint only** (1 addition). No OHLCV window enhancement needed. The new endpoint is:
- Read-only, additive, uses `OpsErrorEnvelope` for errors
- Reads from `INSTRUMENT_REGISTRY` (already imported in `market_data_read.py`)
- No existing endpoint contracts broken
- No write paths changed

### Test count delta

- **Backend:** 454 passing (was 443) — +11 new TF discovery tests
- **Frontend:** 376 passing (was 356) — +20 new PR-CHART-2 tests (timeframe tabs, run markers, verdict normalization, chart isolation, defensive handling)
- **Pre-existing failures unchanged:** 5 journey.test.tsx (frontend), 1 MDO scheduler import (backend)

### Deferred issues

- **True vertical line marker:** deferred to a future phase if needed. Custom `ISeriesPrimitive` implementation would be required. Series markers are sufficient for PR-CHART-2 scope.
- **lightweight-charts v5 API migration:** The existing chart code used deprecated v4 APIs (`addCandlestickSeries`, `addHistogramSeries`). Fixed to v5 API (`addSeries(CandlestickSeries, ...)`) as part of this PR.
- **Confidence display:** not included — `RunBrowserItem` does not expose confidence data, and adding it would require backend work outside scope.

---

## 13. Documentation closure

This PR must update:

### Always

- `docs/AI_TradeAnalyst_Progress.md` — header, Recent Activity, Phase Index, Roadmap (PR-CHART-2 → ✅ Done), test count, §6 Next Actions
- `docs/specs/PR_CHART_2_SPEC.md` — mark ✅ Complete and populate §12
- `docs/PHASE_8_Roadmap_Spec.md` — update PR-CHART-2 status
- Relevant chart/UI workspace documentation (`docs/ui/UI_WORKSPACES.md` or equivalent chart lane design note)
- `docs/architecture/repo_map.md` if file structure changes

### If backend seams were added

- Relevant API/backend contract documentation
- `docs/architecture/system_architecture.md` if the read-side seam meaningfully changes architecture documentation
- `docs/architecture/technical_debt.md` if any known compromises were accepted

### Completion report must explicitly record

- Timeframe discovery path chosen
- Marker implementation chosen
- Backend additions used: none, timeframe discovery, OHLCV window enhancement, or both
- Any deferred issues

---

## 14. Recommended implementation prompt

```
Read `docs/specs/PR_CHART_2_SPEC.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only: run the diagnostic protocol in Section 7 and report
findings before changing any code.

Report these prominently at the top of the diagnostic:
1. Marker method: vertical-style or candle-marker fallback?
2. Timeframe discovery path: existing source or new endpoint?
3. Time-window alignment: frontend-only or bounded OHLCV enhancement?
4. Backend additions needed: none / TF discovery / OHLCV window / both?

Hard constraints:
- No indicator overlays
- No drawing tools
- No standalone chart workspace
- Chart isolation: overlay/marker failure must not block candlestick
  or trace rendering
- Overlays degrade gracefully per §5.3 and §6.4
- Verdict normalization must follow §4.4 — unknown → UNKNOWN, not NO_TRADE
- Nearest-candle rule must follow §4.5
- Instrument change fallback must follow §4.3
- Instrument change must refresh TF tabs (not show stale tabs)
- Per-TF fetch failure: that tab degrades, other tabs still work (§5.3 state 6)
- TF discovery endpoint error contract: 404 INSTRUMENT_NOT_FOUND,
  500 TIMEFRAME_DISCOVERY_FAILED (§4.2)
- Backend additions are bounded, additive, read-only, OpsErrorEnvelope,
  and only allowed if diagnostics prove required (§4.7)
- useMarketData changes must remain backward-compatible
- No premature abstraction
- CHART-1 baseline behavior must be preserved
- Deterministic tests only

Do not change any code until the diagnostic is reviewed and approved.

On completion:
- Close the spec and update docs per Section 13
- Record all chosen implementation paths in Section 12
- Return a Phase Completion Report
```
