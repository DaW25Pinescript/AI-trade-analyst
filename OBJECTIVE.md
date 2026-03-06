# OBJECTIVE.md — Phase 1A: What Success Looks Like

## Strategic framing

The AI Trade Analyst system must reason over **structured market state**, not chart images.

Think of it this way: a chart is like a printed newspaper — useful for a human reader, but the wrong format for a machine that needs to compute. This pipeline is the equivalent of building a **live database feed** so the machine reads raw structured data directly, rather than trying to read the newspaper.

This pipeline is the **database feed**. The Market Data Officer is the **reader**. Everything downstream — analysts, arbiter, senate — depends on this feed being trustworthy.

---

## Phase 1A mission

Prove the ingestion spine works cleanly for one instrument before adding complexity.

EURUSD is chosen as the proving ground because:
- FX price scaling assumptions are well-documented
- No metals-specific parsing ambiguity
- Failures are clearly architectural, not instrument-specific
- It is the highest-liquidity FX pair with excellent Dukascopy coverage

---

## What Phase 1A must deliver

### 1. Dukascopy bi5 fetch

- Build correct hourly URLs per the Dukascopy datafeed schema
- Handle HTTP errors and empty responses gracefully (do not crash)
- Optionally cache raw bi5 files to disk for replay/debug

### 2. Tick decode → canonical UTC 1m OHLCV

- Decompress lzma bi5 payload
- Parse 20-byte tick structs: `time_ms | ask_raw | bid_raw | ask_vol | bid_vol`
- Derive `mid = (ask + bid) / 2`
- Apply `price_scale = 100000` for EURUSD
- Convert `time_ms` offset from hour start to absolute UTC timestamps
- Resample ticks → 1-minute OHLCV bars:
  - open = first mid
  - high = max mid
  - low = min mid
  - close = last mid
  - volume = sum of (ask_vol + bid_vol)

### 3. Canonical archive

- Schema: `timestamp_utc | open | high | low | close | volume | vendor | build_method | quality_flag`
- Format: Parquet with zstd compression
- Index: UTC-aware timestamp
- One file per instrument: `canonical/EURUSD_1m.parquet`

### 4. Validation layer

Must run before every write. See `CONSTRAINTS.md` for full rules.

### 5. Derived timeframes

Resample canonical 1m into: 5m, 15m, 1h, 4h, 1d

Rules:
- open = first
- high = max
- low = min
- close = last
- volume = sum

Save each as both `.parquet` (archival) and `.csv` (human-readable).

### 6. Hot package export

Rolling tail windows for agent consumption:

| Timeframe | Rows |
|-----------|------|
| 1m        | 3000 |
| 5m        | 1200 |
| 15m       | 600  |
| 1h        | 240  |
| 4h        | 120  |
| 1d        | 30   |

Each exported as a compact CSV. Plus a JSON manifest:

```json
{
  "instrument": "EURUSD",
  "as_of_utc": "2025-01-15T12:00:00Z",
  "schema": "timestamp_utc,open,high,low,close,volume",
  "windows": {
    "1m": {"count": 3000, "file": "EURUSD_1m_latest.csv"},
    "5m": {"count": 1200, "file": "EURUSD_5m_latest.csv"}
  }
}
```

### 7. Incremental update logic

- On re-run, detect the last canonical timestamp
- Only fetch data from that point forward
- Append new rows, do not re-download existing data
- Re-run is idempotent: running twice produces same result as running once
- Regenerate derived timeframes and hot packages after every successful append

---

## What Phase 1A explicitly does NOT include

| Out of scope          | Reason                                          |
|-----------------------|-------------------------------------------------|
| XAUUSD               | Instrument-specific parsing needs isolated verification |
| HistData seeding      | Premature — prove Dukascopy spine first         |
| Concurrency/async     | Complexity before correctness is wrong order    |
| Market Data Officer API | Feed must be trustworthy before wiring in     |
| Chart screenshots     | Permanently not the backend truth               |
| Deep multi-year bootstrap optimization | Phase 1E concern          |

---

## Definition of done

Phase 1A is complete when all acceptance criteria in `ACCEPTANCE_TESTS.md` pass on a clean run.

The output must be:
- **Deterministic**: same inputs → same outputs, every time
- **Trustworthy**: validation catches any corrupt bar before it reaches derived layers
- **Auditable**: vendor/build_method/quality_flag metadata tells you how every bar was built
- **Extensible**: adding XAUUSD in Phase 1B should require only instrument config, not architectural rewrites
