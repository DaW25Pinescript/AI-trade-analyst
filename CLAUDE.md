# CLAUDE.md — Structure Engine: Phase 3A

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Your job in this task is to build the **Phase 3A Structure Engine** — a deterministic, ICT-native computation layer that transforms trusted canonical OHLCV into explicit structural state objects.

Read this file first. Then read the supporting spec files in order before writing any code.

---

## One-paragraph contract

Phase 3A introduces a deterministic ICT-style Structure Engine that transforms trusted canonical OHLCV into explicit structural state objects — confirmed swings, BOS, MSS, liquidity references, EQH/EQL, sweeps, and regime summaries. Phase 3A is confirmed-only, excludes FVG/imbalance logic, and does not modify the Officer layer. Its purpose is to make market structure replayable, testable, and consumable by downstream agents as numeric state rather than visual inference.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**What already exists (do not touch):**
- `market_data_officer/feed/` — validated feed pipeline, EURUSD + XAUUSD
- `market_data_officer/officer/` — Market Data Officer, emitting trusted market packets
- `market_data/canonical/` — trusted 1m Parquet archives
- `market_data/derived/` — validated derived timeframe Parquet/CSV
- `market_data/packages/latest/` — hot package CSVs and JSON manifests

**What you are building:**
- `market_data_officer/structure/` — the Structure Engine
- `market_data_officer/run_structure.py` — Structure Engine CLI entry point

---

## File reading order

Before writing any code, read these files in order:

1. `CLAUDE.md` ← you are here
2. `OBJECTIVE.md` — what 3A must deliver, scope boundaries, non-goals
3. `CONSTRAINTS.md` — hard rules, logic contracts, implementation standards
4. `CONTRACTS.md` — canonical schemas for all structure objects and the packet
5. `ACCEPTANCE_TESTS.md` — exit criteria, 7 test groups, pass/fail required

---

## Repo placement

```
market_data_officer/
  feed/                        ← DO NOT TOUCH
  officer/                     ← DO NOT TOUCH
  structure/
    __init__.py
    schemas.py                 ← typed dataclasses for all structure objects
    engine.py                  ← top-level orchestration
    swings.py                  ← confirmed swing detection
    events.py                  ← BOS / MSS detection
    liquidity.py               ← prior highs/lows, EQH/EQL, sweeps
    regime.py                  ← objective regime summary
    io.py                      ← load bars, write JSON packets
    config.py                  ← engine configuration surface
  tests/
    test_structure_swings.py
    test_structure_events.py
    test_structure_liquidity.py
    test_structure_regime.py
    test_structure_replay.py
    test_structure_eurusd.py
    test_structure_xauusd.py
  run_structure.py             ← NEW: Structure Engine CLI
```

---

## Build order

Build modules in this sequence. Do not jump ahead:

1. `schemas.py` — stable primitives first
2. `config.py` — configuration surface
3. `swings.py` — confirmed swing detection
4. `events.py` — BOS / MSS using confirmed swings
5. `liquidity.py` — prior levels, EQH/EQL, sweeps
6. `regime.py` — objective summary from above
7. `io.py` + `engine.py` — orchestration and JSON output
8. Tests per module, then end-to-end

This order gives you stable, tested primitives before packaging. Never build the orchestrator before the primitives it depends on are tested.

---

## Active timeframes for 3A

Structure is computed on: **15m, 1h, 4h**

- 1m excluded: too noisy for confirmed structure
- 5m excluded: deferred to 3B
- 1d excluded: insufficient bars for meaningful swing confirmation in rolling windows

Each timeframe computes structure **independently** from its own derived bars. No cross-timeframe synthesis in 3A.

---

## Output

One JSON packet per instrument per timeframe written to:

```
market_data_officer/structure/output/
  eurusd_15m_structure.json
  eurusd_1h_structure.json
  eurusd_4h_structure.json
  xauusd_15m_structure.json
  xauusd_1h_structure.json
  xauusd_4h_structure.json
```

Parquet output is deferred to Phase 3D once the schema stabilizes across 3A/3B/3C.

---

## When you are done

Run every criterion in `ACCEPTANCE_TESTS.md` across all 7 test groups for both EURUSD and XAUUSD. Report pass/fail per group before declaring Phase 3A complete.

Do not implement FVG, imbalance, order blocks, or Officer integration. Do not modify any existing module outside `structure/`.
