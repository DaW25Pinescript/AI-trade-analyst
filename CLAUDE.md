# CLAUDE.md — Market Data Officer Feed: Phase 1A

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Your job in this task is to build **Phase 1A** of the Market Data Officer feed pipeline — a clean, validated, production-lean ingestion spine for **EURUSD only**.

Read this file first. Then read the supporting spec files in order before writing any code.

---

## Repo context

This task lives inside the AI Trade Analyst repo:
`https://github.com/DaW25Pinescript/AI-trade-analyst`

The repo already contains:
- A static frontend surface
- A Python analyst engine (early stage)
- Macro Risk Officer module
- Arbiter/Senate governance scaffold

This pipeline feeds **upstream** of all those layers. It is the **data-source / feed lane**. Nothing else in the system should be touched in this task.

---

## Task scope — Phase 1A only

**Do not** broaden this task beyond Phase 1A.

Phase 1A deliverable = a fully working ingestion spine for EURUSD:

1. Dukascopy bi5 fetch
2. Tick decode → UTC canonical 1m OHLCV
3. Validation layer (before every write)
4. Derived timeframes: 5m, 15m, 1h, 4h, 1d
5. Hot package export (rolling CSV windows + JSON manifest)
6. Incremental update logic (append-safe, idempotent)
7. Clear TODO/defect notes for XAUUSD extension (do not implement it yet)

XAUUSD is **not** in scope. Do not guess at its scale/volume parsing. Leave explicit verification stubs instead.

Market Data Officer integration is **not** in scope. The feed must prove itself trustworthy first.

---

## Architecture principle

> Charts are a human interface. The AI backend should consume canonical numeric market state — not screenshots, not OCR, not visual guessing.

This pipeline is the mechanism that makes that principle real. It provides downstream AI agents with:

- Explicit OHLCV series
- Clean UTC timestamps  
- Rolling hot windows per timeframe
- Deterministic derived features
- Vendor/quality metadata

**Canonical truth = UTC 1-minute OHLCV per instrument.**  
Higher timeframes are always derived from canonical 1m — never fetched independently.

---

## File reading order

Before writing any code, read these files:

1. `CLAUDE.md` ← you are here
2. `OBJECTIVE.md` — what success looks like and why
3. `CONSTRAINTS.md` — hard rules, known defects, engineering standards
4. `ACCEPTANCE_TESTS.md` — the exit criteria you must pass

Then implement.

---

## Repo placement

Place all new code under:

```
market_data_officer/
  feed/
    __init__.py
    config.py
    fetch.py
    decode.py
    aggregate.py
    validate.py
    resample.py
    export.py
    pipeline.py
  tests/
    test_validate.py
    test_resample.py
    test_decode.py
  run_feed.py
```

Do not place code in the analyst engine, frontend, or arbiter modules.

---

## Output data layout

```
market_data/
  raw/dukascopy/EURUSD/          ← optional raw bi5 cache
  canonical/EURUSD_1m.parquet    ← canonical truth
  derived/
    EURUSD_5m.parquet / .csv
    EURUSD_15m.parquet / .csv
    EURUSD_1h.parquet / .csv
    EURUSD_4h.parquet / .csv
    EURUSD_1d.parquet / .csv
  packages/latest/
    EURUSD_1m_latest.csv
    EURUSD_5m_latest.csv
    EURUSD_15m_latest.csv
    EURUSD_1h_latest.csv
    EURUSD_4h_latest.csv
    EURUSD_1d_latest.csv
    EURUSD_hot.json
```

---

## When you are done

Run the acceptance tests in `ACCEPTANCE_TESTS.md` and confirm each exit criterion passes before declaring Phase 1A complete.

Leave Phase 1B (XAUUSD), Phase 1C (incremental optimizer), and Phase 2 (Market Data Officer integration) fully untouched — documented as next steps only.
