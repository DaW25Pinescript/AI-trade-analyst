# ROADMAP.md — Phase Plan (Do Not Build Beyond 1A)

This file exists so Claude Code understands the full arc without being tempted to jump ahead.

**Current task: Phase 1A only.**

---

## Phase 1A — EURUSD baseline spine ← YOU ARE HERE

Goal: one instrument, fully working, fully validated.

Scope:
- EURUSD Dukascopy fetch/decode
- Canonical 1m OHLCV archive
- Validation layer
- Derived 5m/15m/1h/4h/1d
- Hot package export
- Incremental update

Exit gate: all `ACCEPTANCE_TESTS.md` criteria pass on a clean 3-day run.

---

## Phase 1B — XAUUSD extension

**Do not start until Phase 1A is signed off.**

Goal: extend the proven spine to metals.

Scope:
- Independently verify XAUUSD Dukascopy price scale (do not assume 1000)
- Independently verify volume interpretation — compare decoded output vs a trusted external reference (e.g. TradingView, CMC)
- Populate `InstrumentMeta` for XAUUSD only after verification
- Run same acceptance criteria as Phase 1A, instrument-substituted

Exit gate: XAUUSD candles are independently validated against a known external reference for at least 5 bars.

Risk note: if Phase 1B is rushed, scale or volume errors will be silent. A 10x price scaling error on gold produces plausible-looking but completely wrong bars. This must be caught before the Market Data Officer consumes it.

---

## Phase 1C — Incremental updater hardening

Goal: make daily/hourly updates robust.

Scope:
- Detect affected derived windows (only regenerate what changed, not full rewrite)
- Idempotent gap detection with gap report output
- Optional: hot package refresh on schedule

---

## Phase 1D — Raw cache and diagnostics

Goal: improve debugging trust and replay capability.

Scope:
- Structured raw payload cache with vendor metadata
- Gap report (which hours are missing and why)
- Source/vendor audit trail per bar
- Parser diagnostics to verify decode assumptions

---

## Phase 1E — Bootstrap optimization

Goal: practical multi-year deep history ingestion.

Scope:
- Optional HistData seeding for long M1 archives (10+ years)
- Dukascopy used for incremental update, gap fill, and validation cross-check
- Do not combine both sources into undifferentiated canonical truth — one must be primary

---

## Phase 2 — Market Data Officer integration

Goal: expose the feed to downstream AI analyst agents.

Scope:
- Structured read API layer (the Officer reads hot packages, not raw Parquet)
- Rolling feature windows (ATR, volatility, momentum, swing structure)
- Officer-facing JSON state package per instrument
- Analysts consume numeric market state directly

This is when chart screenshots become fully optional for the backend — an adjunct for human review, not the system's truth.

---

## What this feed replaces

| Old approach | New approach |
|---|---|
| Screenshot → OCR → guessed OHLC | Canonical 1m OHLCV from tick data |
| Chart image sent to analyst agent | Structured hot package JSON/CSV |
| Visual interpretation of highs/lows | Explicit OHLCV series with derived features |
| Undetermined timeframe consistency | All TFs derived from single canonical 1m |
| No audit trail | vendor/build_method/quality_flag per bar |
