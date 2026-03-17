# Phase 8 Forward Plan — Charts + Reflective Intelligence

**Date:** 15 March 2026
**Planning horizon:** 6 weeks (mid-March to end of April 2026)
**Prerequisite:** Phase 7 complete — Agent Ops read-side stack fully wired

---

## Strategic Direction

**Prerequisite gate:** Phase 8 does not start until PR-OPS-5 is merged and the Phase 7 Agent Ops read-side stack is fully wired. This gate is satisfied as of 15 March 2026 (PR-OPS-5b shipped, 63 frontend tests, all 28 ACs verified).

Two high-value capabilities, sequenced by dependency:

1. **Live charts in the UI** — candlestick charts rendered in the browser, tied to analysis run context, with market data served from the existing MDO pipeline
2. **Reflective Intelligence Layer** — progressive improvement engine that surfaces persona performance, pattern weaknesses, and parameter tuning suggestions by aggregating run history

Both need **run volume** to deliver value. The first week focuses on run browser (making it easy to generate and find runs) before building either feature.

---

## Week-by-Week Plan

### Week 1: Run Browser + Live Activation (PR-RUN-1)

**Goal:** Make it easy to generate runs and find them in the UI.

**Scope:**
- `GET /runs/` — backend endpoint listing available runs (paginated, sorted by date, filterable by instrument/session)
- Source: scan `ai_analyst/output/runs/` directories, read `run_record.json` and project compact run summaries from the real artifact shape (run_id, timestamp, request.instrument, request.session, arbiter.verdict, derived run_status)
- Response: compact run summaries — no analyst detail, no arbiter detail, no artifact content
- Bounded: default page size 20, max 50, no unbounded directory walking
- Frontend: `RunBrowserPanel` replacing the paste-field run selector in Agent Ops Run mode
- Run browser becomes the entry point for Run mode — click a run to load its trace

**Scope lock:** This is a run index, not an artifact browser. Do not return analyst results, arbiter metadata, or artifact content in v1. The trace endpoint already handles that — the browser just helps you find the run_id.

**Why first:** Every feature after this depends on being able to find and inspect runs. The paste field is a blocker for real usage. This also gives you a natural workflow: run an analysis → see it appear in the browser → inspect it.

**Estimated scope:** ~800 lines (1 backend endpoint + service + tests, 1 frontend component + tests)

---

### Weeks 2–3: Live Candlestick Charts (PR-CHART-1, PR-CHART-2)

**Goal:** Render live OHLCV candlestick charts in the UI, tied to run context.

**PR-CHART-1 (Week 2): Data-seam validation + basic chart component**

This PR is primarily a **data access proof** — confirming that OHLCV data can be served from the MDO pipeline to a frontend chart without scheduler coupling. The chart component is secondary to proving the seam.

Backend:
- `GET /market-data/{instrument}/ohlcv` — serve OHLCV candle data from MDO's existing data pipeline
- Parameters: instrument, timeframe, period (e.g. last 100 candles)
- Source: read from MDO's existing data store (yFinance-backed SQLite or cached DataFrames — diagnostic to confirm)
- Response: array of `{ timestamp, open, high, low, close, volume }` — lightweight, frontend-ready
- **Data-seam validation:** If the OHLCV data is scheduler-bound or requires pipeline execution to access, this becomes the real blocker — flag immediately. The endpoint must read stored data, not trigger new fetches.

Frontend:
- Install `lightweight-charts` (TradingView's open-source charting library — MIT licensed, ~40KB, purpose-built for financial charts)
- `CandlestickChart` component rendering OHLCV data
- `useMarketData(instrument, timeframe)` hook
- Chart renders as an **embedded panel in Run context** (not a separate workspace — see Chart Placement below)

**PR-CHART-2 (Week 3): Run context overlay + multi-timeframe**

- Link chart to run context: when viewing a run for XAUUSD, chart shows XAUUSD candles for the relevant time window
- Multi-timeframe support: tabs or selector for H4/H1/M15/M5 (matching the analysis timeframes)
- Run timestamp marker on the chart (vertical line showing when the analysis was done)
- Analyst verdict overlay: simple annotations showing the final bias / decision at the run timestamp
- Stage: do NOT attempt full indicator overlays yet — that's a future phase

**Chart Placement Decision (LOCKED)**

Charts embed as a panel within Run mode context — not as a separate `/chart` workspace. Rationale: charts are valuable when tied to a specific run's instrument, session, and timestamp. A standalone chart workspace would be disconnected from the run context that gives charts meaning. If a standalone chart surface is needed later, it can be extracted — but v1 embeds in run context.

**Why this library:** lightweight-charts is maintained by TradingView, renders candlesticks natively, handles time-axis correctly, supports overlays and markers, and looks exactly like what a discretionary trader expects. It's 40KB, not a full TradingView embed.

**Estimated scope:** ~1,200 lines across both PRs

---

### Weeks 4–5: Reflective Intelligence Layer v1 (PR-REFLECT-1, PR-REFLECT-2)

**Goal:** Surface persona performance and pattern insights from run history.

**PR-REFLECT-1 (Week 4): Run history aggregation endpoint**

Backend:
- `GET /reflect/persona-performance` — aggregate persona performance across recent runs
- Scans run artifacts (run_record.json + audit logs) for the last N runs (bounded, like agent-detail scan)
- Per persona: participation count, override count, stance accuracy (vs final verdict), confidence calibration
- Returns a compact performance summary table

Backend:
- `GET /reflect/pattern-summary` — aggregate setup/pattern outcomes
- Groups runs by instrument + final_decision
- Surfaces: which instruments produce the most NO_TRADE verdicts, which sessions have higher conviction, recurring arbiter overrides

**Design principle:** This is **aggregation, not ML.** The first slice computes statistics over existing structured artifacts. No model training, no embeddings, no inference. Pure read-side projection — same philosophy as Phase 7.

**Reflective Layer Operating Rules (LOCKED for v1):**

1. **Aggregation only.** v1 computes statistics (counts, percentages, distributions) over existing run artifacts. No ML models, no statistical inference, no embeddings.
2. **Advisory only.** All suggestions are presented as operator guidance. No config mutation path exists in v1. The system never auto-modifies its own behavior.
3. **Minimum threshold: 10 runs per instrument/session bucket** before surfacing any persona performance or pattern statistics. Below this threshold, show "insufficient run history" instead of potentially misleading stats. This threshold is a default — diagnostics may adjust it if 10 proves too high or too low, but the principle of "don't show stats from too-small samples" is locked.

**PR-REFLECT-2 (Week 5): Reflective dashboard in the UI**

Frontend:
- New top-level **`/reflect` workspace** showing:
  - Persona performance table: analyst name, participation %, override %, stance alignment %, avg confidence
  - Pattern summary: instrument × session heatmap or table showing verdict distribution
  - Highlighted anomalies: personas with >50% override rate, instruments with >80% NO_TRADE rate
- Simple, table-driven, operator-readable — no fancy visualizations in v1
- Read-only — no parameter tweaking yet (that's v2)

**Why aggregation first:** You need to see the patterns before you can act on them. Persona performance is directly computable from existing trace data. This builds the observation foundation that future "suggested parameter tweaks" will build on — you can't suggest what to change until you've measured what's happening.

**Estimated scope:** ~1,500 lines across both PRs

---

### Week 6: Integration + Polish + Parameter Suggestions v0 (PR-REFLECT-3)

**Goal:** Connect the pieces and add the first suggestion capability.

- Chart ↔ Run integration: chart panel already embedded in Run mode (from PR-CHART-1/2) — ensure trace participant highlighting syncs with chart annotations
- Reflect ↔ Agent Ops integration: persona performance cards link to Agent Ops entity detail
- **Parameter suggestions v0:** simple rules-based suggestions derived from the aggregated data:
  - "Persona X was overridden in 7 of last 10 runs — consider reviewing its analysis focus"
  - "XAUUSD NY session produced NO_TRADE in 8 of last 10 runs — confidence threshold may be too high"
  - These are presented as **operator suggestions, not automatic changes** — the human decides
- Polish pass: loading states, empty states, error handling across new surfaces

**Why rules-based first:** The suggestion engine should start with explicit, auditable rules ("if override rate > 70%, flag it") rather than opaque ML. This matches your "let the market come to you" philosophy — observe first, then act deliberately. The rules can be upgraded to statistical models later when you have enough history to justify it.

**Estimated scope:** ~800 lines

---

## Updated Roadmap

| Priority | Phase | Description | Status | Depends On | Target |
|----------|-------|-------------|--------|------------|--------|
| 1 | PR-RUN-1 | Run Browser endpoint + frontend | ✅ Done | Phase 7 complete | Week 1 |
| 2 | PR-CHART-1 | OHLCV data endpoint + candlestick chart component | ✅ Done | PR-RUN-1 | Week 2 |
| 3 | PR-CHART-2 | Run context overlay + multi-timeframe charts | ✅ Done | PR-CHART-1 ✅ | Week 3 |
| 4 | PR-REFLECT-1 | Persona performance + pattern summary endpoints | ✅ Done | PR-RUN-1 (needs run history) | Week 4 |
| 5 | PR-REFLECT-2 | Reflective dashboard frontend | ✅ Done | PR-REFLECT-1 ✅ | Week 5 |
| 6 | PR-REFLECT-3 | Integration + rules-based suggestions v0 (two rules, advisory only) | ✅ Done | PR-CHART-2, PR-REFLECT-2 | Week 6 |
| — | Chart indicators overlay | Pine Script-style indicators on candlestick charts | 💭 Concept | PR-CHART-2 | Future |
| — | ML-based pattern detection | Statistical models replacing rules-based suggestions | 💭 Concept | PR-REFLECT-2 + run volume | Future |
| — | Control-Plane Actions | Agent start/stop/retry in Ops workspace | 💭 Concept | Phase 7 complete | Future |
| — | Live Push Updates | SSE/WebSocket for real-time updates | 💭 Concept | Phase 7 complete | Future |

---

## Architecture Notes

### Chart data source
The MDO pipeline fetches and stores OHLCV data as CSV files in `market_data/packages/latest/` (hot packages). The chart endpoint reads from this existing storage via `market_data_officer.officer.loader.load_timeframe()` — confirmed clean read path with zero scheduler coupling. Storage format: CSV with `timestamp_utc,open,high,low,close,volume` schema. Confirmed by PR-CHART-1 diagnostic (Outcome A).

### Reflective data source
Same philosophy as Phase 7 trace endpoints: read-side projection over existing run artifacts. No new persistence. The aggregation endpoint scans bounded recent history (same pattern as agent-detail's recent participation scan: max N directories or M days).

### Chart library choice
`lightweight-charts` (TradingView open source):
- MIT licensed, actively maintained
- ~40KB gzipped, renders to canvas
- Native candlestick, line, area, histogram series
- Time-axis handles financial market gaps correctly
- Markers and price lines for annotation overlays
- React wrapper available (`lightweight-charts-react`)

### Progressive improvement path
```
Week 4-5: Observe    (aggregation only, minimum 10-run threshold)
    ↓
Week 6:   Suggest    (rules-based, advisory-only, human-governed)
    ↓
Future:   Adapt      (statistical models, bounded hypothesis generation)
    ↓
Future:   Refine     (reversible policy changes with human approval gate)
```

Each step builds on the previous and requires human governance. The system never auto-modifies its own behavior. The jump from Suggest → Adapt requires sufficient run volume and a deliberate decision to introduce statistical methods.

---

## Locked Decisions

| Decision | Resolution |
|----------|-----------|
| Prerequisite gate | Phase 8 does not start until PR-OPS-5 merged and Phase 7 fully wired (satisfied 15 March 2026) |
| Run Browser scope | Header-only run index, not artifact browser. Paginated, bounded, default 20 / max 50 |
| Chart placement | Embedded panel in Run mode context, not a separate workspace |
| Chart data access | Read-side only — endpoint reads stored OHLCV data, does not trigger new fetches |
| Reflective layer approach | Aggregation only in v1 — no ML, no inference, no embeddings |
| Suggestion governance | Advisory only in v1 — no config mutation path, human decides |
| Minimum run threshold | 10 runs per instrument/session bucket before showing reflective stats |

## Remaining Diagnostic Questions

1. ~~**MDO data access format:**~~ **Resolved** — OHLCV data stored as CSV files in `market_data/packages/latest/`. Readable via `market_data_officer.officer.loader.load_timeframe()` with zero scheduler coupling. Confirmed by PR-CHART-1 diagnostic (Outcome A).
2. ~~**Reflect placement:**~~ **Resolved** — New top-level `/reflect` workspace. Locked decision per PR-RUN-1 spec §12.
3. ~~**Run directory structure:**~~ **Resolved** — `ai_analyst/output/runs/` directory scan implemented in PR-RUN-1 with bounded walking (max 20 dirs or 7 days).
