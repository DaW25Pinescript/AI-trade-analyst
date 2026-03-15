# Phase 8 Forward Plan — Charts + Reflective Intelligence

**Date:** 15 March 2026
**Planning horizon:** 6 weeks (mid-March to end of April 2026)
**Prerequisite:** Phase 7 complete — Agent Ops read-side stack fully wired

---

## Strategic Direction

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
- Source: scan `ai_analyst/output/runs/` directories, read `run_record.json` headers
- Response: compact run summaries (run_id, instrument, session, status, timestamp, final_decision)
- Frontend: `RunBrowserPanel` replacing the paste-field run selector in Agent Ops Run mode
- Run browser becomes the entry point for Run mode — click a run to load its trace

**Why first:** Every feature after this depends on being able to find and inspect runs. The paste field is a blocker for real usage. This also gives you a natural workflow: run an analysis → see it appear in the browser → inspect it.

**Estimated scope:** ~800 lines (1 backend endpoint + service + tests, 1 frontend component + tests)

---

### Weeks 2–3: Live Candlestick Charts (PR-CHART-1, PR-CHART-2)

**Goal:** Render live OHLCV candlestick charts in the UI, tied to run context.

**PR-CHART-1 (Week 2): Chart data endpoint + basic chart component**

Backend:
- `GET /market-data/{instrument}/ohlcv` — serve OHLCV candle data from MDO's existing data pipeline
- Parameters: instrument, timeframe, period (e.g. last 100 candles)
- Source: read from MDO's existing data store (yFinance-backed SQLite or cached DataFrames — diagnostic to confirm)
- Response: array of `{ timestamp, open, high, low, close, volume }` — lightweight, frontend-ready

Frontend:
- Install `lightweight-charts` (TradingView's open-source charting library — MIT licensed, ~40KB, purpose-built for financial charts)
- `CandlestickChart` component rendering OHLCV data
- `useMarketData(instrument, timeframe)` hook
- Chart appears in a new **Chart workspace** or as a panel within Analysis Run / Journey Studio (diagnostic to decide placement)

**PR-CHART-2 (Week 3): Run context overlay + multi-timeframe**

- Link chart to run context: when viewing a run for XAUUSD, chart shows XAUUSD candles for the relevant time window
- Multi-timeframe support: tabs or selector for H4/H1/M15/M5 (matching the analysis timeframes)
- Run timestamp marker on the chart (vertical line showing when the analysis was done)
- Analyst verdict overlay: simple annotations showing the final bias / decision at the run timestamp
- Stage: do NOT attempt full indicator overlays yet — that's a future phase

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

**PR-REFLECT-2 (Week 5): Reflective dashboard in the UI**

Frontend:
- New **Reflect workspace** (or tab within Agent Ops) showing:
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

- Chart ↔ Run integration: viewing a run in Agent Ops shows the chart for that instrument/session
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
| 1 | PR-RUN-1 | Run Browser endpoint + frontend | 📋 Planned | Phase 7 complete | Week 1 |
| 2 | PR-CHART-1 | OHLCV data endpoint + candlestick chart component | 📋 Planned | PR-RUN-1 | Week 2 |
| 3 | PR-CHART-2 | Run context overlay + multi-timeframe charts | 📋 Planned | PR-CHART-1 | Week 3 |
| 4 | PR-REFLECT-1 | Persona performance + pattern summary endpoints | 📋 Planned | PR-RUN-1 (needs run history) | Week 4 |
| 5 | PR-REFLECT-2 | Reflective dashboard frontend | 📋 Planned | PR-REFLECT-1 | Week 5 |
| 6 | PR-REFLECT-3 | Integration + rules-based parameter suggestions v0 | 📋 Planned | PR-CHART-2, PR-REFLECT-2 | Week 6 |
| — | Chart indicators overlay | Pine Script-style indicators on candlestick charts | 💭 Concept | PR-CHART-2 | Future |
| — | ML-based pattern detection | Statistical models replacing rules-based suggestions | 💭 Concept | PR-REFLECT-2 + run volume | Future |
| — | Control-Plane Actions | Agent start/stop/retry in Ops workspace | 💭 Concept | Phase 7 complete | Future |
| — | Live Push Updates | SSE/WebSocket for real-time updates | 💭 Concept | Phase 7 complete | Future |

---

## Architecture Notes

### Chart data source
The MDO pipeline already fetches and stores OHLCV data via yFinance. The chart endpoint reads from this existing data — no new data fetching infrastructure needed. The diagnostic must confirm the exact storage format (SQLite, cached DataFrames, or raw CSV) and whether the data is accessible outside the MDO scheduling context.

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
Week 4-5: Observe (aggregation, statistics, tables)
    ↓
Week 6: Suggest (rules-based, human-approved)
    ↓
Future: Adapt (statistical models, bounded hypothesis generation)
    ↓
Future: Refine (reversible policy changes with human approval gate)
```

Each step builds on the previous and requires human governance. The system never auto-modifies its own behavior.

---

## Open Questions for Diagnostic

1. **MDO data access:** How is OHLCV data stored? Can a new endpoint read it without going through the scheduler?
2. **Chart placement:** New `/chart` workspace, or embedded panel within Analysis Run / Journey Studio / Agent Ops?
3. **Reflect placement:** New `/reflect` workspace, or tab within Agent Ops?
4. **Run volume needed:** How many runs before reflective aggregation becomes meaningful? (Suggest: minimum 10 runs per instrument before showing performance stats)
5. **Suggestion governance:** Should parameter suggestions require explicit "accept" before any config change, or are they always advisory-only in v1?
