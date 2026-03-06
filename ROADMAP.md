# ROADMAP.md — Phase Plan (Do Not Build Beyond 1D)

This file exists so Claude Code understands the full arc without being tempted to jump ahead.

**Current task: Phase 1D only.**

---

## Phase 1A — EURUSD baseline spine ✅ COMPLETE

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

## Phase 1B — XAUUSD extension ✅ COMPLETE

Goal: extend the proven spine to metals.

Scope:
- ✅ Independently verify XAUUSD Dukascopy price scale (confirmed: 1000)
- ✅ Populate `InstrumentMeta` for XAUUSD with verified price_scale
- ✅ Run same acceptance criteria as Phase 1A, instrument-substituted
- ⚠️ Volume units not cross-checked against external reference (e.g. CME) — ingested as raw lots

Verification performed: Dukascopy bi5 2025-01-16 14:00 UTC, raw ask=2715695 / 1000 = $2715.695,
consistent with known gold spot ~$2702-2720 mid-January 2025.

Exit gate: XAUUSD candles independently validated against known external reference for at least 5 bars.

Risk note: volume interpretation is unverified against an external volume source.
If a volume_divisor is later found to be needed, the XAUUSD canonical archive will need rebuilding.

---

## Phase 1C — Incremental updater hardening ✅ COMPLETE

Goal: make daily/hourly updates robust.

Scope:
- ✅ Selective derived regeneration (only resample affected window, not full rewrite)
- ✅ Idempotent gap detection with gap report output (JSON)
- ✅ Hot-only refresh mode (--hot-only flag)
- ✅ Gap report CLI flag (--gap-report)

Implementation:
- `gaps.py`: gap detection, FX trading-hour classification, JSON report generation
- `pipeline.py`: selective derived regeneration via `_derive_affected_window()`,
  `_find_resample_boundary()` computes the first affected derived bar
- `run_feed.py`: `--gap-report` and `--hot-only` CLI flags

---

## Phase 1D — Raw cache and diagnostics ✅ COMPLETE

Goal: improve debugging trust and replay capability.

Scope:
- ✅ Structured raw payload cache with vendor metadata (FetchRecord with sha256, status, URL)
- ✅ Gap report enhanced: per-hour fetch diagnostics explain why gaps exist (404, empty, decode error)
- ✅ Source/vendor audit trail per bar (DiagnosticsCollector, per-hour fetch/decode records)
- ✅ Parser diagnostics to verify decode assumptions (verify_decode_assumptions: price range, tick density, empty decode)

Implementation:
- `diagnostics.py`: DiagnosticsCollector, FetchRecord, DecodeRecord, cache inventory,
  verify_decode_assumptions (anomaly detection: empty_decode, price_range_outlier,
  low/high_tick_density)
- `fetch.py`: FetchResult dataclass, fetch_bi5_detailed() returning metadata
- `decode.py`: DecodeStats dataclass, decode_with_diagnostics() returning stats
- `pipeline.py`: diagnostics=True path collects per-hour records, saves report +
  anomaly verification + optional cache inventory
- `run_feed.py`: --diagnostics CLI flag
- Tests: test_diagnostics.py (28+ tests)

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
