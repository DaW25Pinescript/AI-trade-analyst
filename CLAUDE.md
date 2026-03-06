# CLAUDE.md — Market Data Officer: Phase 2

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Your job in this task is to build the **Market Data Officer (MDO)** — the read-and-state layer that sits on top of the validated feed pipeline built in Phases 1A–1D.

Read this file first. Then read the supporting spec files in order before writing any code.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**What already exists (do not touch):**
- `market_data_officer/feed/` — Phase 1A–1D feed pipeline (fetch, decode, validate, archive, resample, export)
- `market_data/canonical/` — validated 1m Parquet archives per instrument
- `market_data/derived/` — validated derived timeframe Parquet/CSV
- `market_data/packages/latest/` — hot package CSVs and JSON manifests

**What you are building:**
- `market_data_officer/officer/` — the MDO read/state layer
- `market_data_officer/run_officer.py` — Officer entry point

---

## Doctrine

> The Market Data Officer is the read-and-state layer of AI Trade Analyst's data-first architecture. The feed establishes canonical 1-minute market truth from vendor ticks. The Officer transforms that validated truth into compact, auditable, AI-readable market packets for downstream reasoning. Screenshots are optional supporting evidence, not backend truth.

The Officer does **not** fetch, decode, or write canonical data. That belongs to the feed.

The Officer **reads** validated outputs and **builds** structured reasoning context for downstream agents.

---

## File reading order

Before writing any code, read these files in order:

1. `CLAUDE.md` ← you are here
2. `OBJECTIVE.md` — what the Officer must do and why
3. `CONSTRAINTS.md` — hard rules, module boundaries, failure handling
4. `CONTRACTS.md` — the Market Packet v1 JSON schema (most important file)
5. `ACCEPTANCE_TESTS.md` — exit criteria you must pass

---

## Repo placement

```
market_data_officer/
  feed/                        ← DO NOT TOUCH
    ...
  officer/
    __init__.py
    contracts.py               ← MarketPacket, StateSummary dataclasses
    loader.py                  ← reads hot packages and manifests
    features.py                ← core feature computation
    summarizer.py              ← state summary builder
    quality.py                 ← read-side sanity checks
    service.py                 ← top-level Officer orchestrator
    structure/                 ← advanced feature stubs only
      __init__.py
      bos_detector.py          ← stub, returns None
      fvg_detector.py          ← stub, returns None
      compression_detector.py  ← stub, returns None
      imbalance_detector.py    ← stub, returns None
  tests/
    test_loader.py
    test_features.py
    test_summarizer.py
    test_quality.py
    test_contracts.py
  run_feed.py                  ← DO NOT TOUCH
  run_officer.py               ← NEW: Officer entry point
```

---

## When you are done

Run every criterion in `ACCEPTANCE_TESTS.md` and report pass/fail per test group before declaring Phase 2 complete.

Do not implement advanced structure features (BOS, FVG, compression, imbalance). Stub them only. Those are Phase 3 and Phase 4 concerns.
