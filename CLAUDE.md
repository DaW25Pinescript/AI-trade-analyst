# CLAUDE.md — Structure Engine: Phase 3B

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Your job in this task is to extend the Phase 3A Structure Engine with liquidity refinement. Phase 3A is complete and merged. You are extending it narrowly — not rewriting it.

Read this file first. Then read the supporting spec files in order before writing any code.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**Already complete — do not touch:**
- `market_data_officer/feed/` — Phase 1A–1D feed pipeline
- `market_data_officer/officer/` — Phase 2 Market Data Officer
- `market_data_officer/structure/schemas.py` — SwingPoint, StructureEvent, LiquidityLevel, SweepEvent, RegimeSummary, StructurePacket
- `market_data_officer/structure/config.py` — StructureConfig
- `market_data_officer/structure/swings.py` — fixed L/R pivot confirmation
- `market_data_officer/structure/events.py` — BOS/MSS close-confirmed
- `market_data_officer/structure/liquidity.py` — prior H/L, EQH/EQL, sweep detection
- `market_data_officer/structure/regime.py` — bias, trend state, structure quality
- `market_data_officer/structure/io.py` — bar loading, atomic JSON writes
- `market_data_officer/structure/engine.py` — orchestration, `run_engine()`
- `run_structure.py` — CLI entry point

**What you are extending in Phase 3B:**
- `structure/schemas.py` — add new fields to LiquidityLevel and SweepEvent
- `structure/liquidity.py` — add reclaim detection, post-sweep classification, internal/external tagging, lifecycle refinement
- `structure/config.py` — add narrow 3B config surface
- `tests/` — add 3B test groups

---

## Phase 3A decisions that are locked — do not reopen

| Decision | Value |
|---|---|
| Swing confirmation | Fixed left/right pivot only |
| BOS/MSS confirmation | Close beyond prior swing only |
| EQH/EQL tolerance | Fixed per-instrument value in config |
| Active timeframes | 15m, 1h, 4h |
| Output format | JSON only |
| FVG/imbalance | Not in scope |
| Cross-timeframe synthesis | Not in scope |
| Officer integration | Not in scope |
| Parquet output | Deferred to Phase 3D |

Any change to these is a scope violation.

---

## File reading order

Before writing any code, read in order:

1. `CLAUDE.md` ← you are here
2. `OBJECTIVE.md` — what 3B adds and why
3. `CONSTRAINTS.md` — hard rules, schema evolution policy, 3B config surface
4. `CONTRACTS.md` — exact field additions to LiquidityLevel and SweepEvent
5. `ACCEPTANCE_TESTS.md` — 7 test groups you must pass

---

## Repo placement

No new top-level modules. Extensions only:

```
market_data_officer/
  structure/
    schemas.py       ← extend LiquidityLevel + SweepEvent fields
    config.py        ← add reclaim_window_bars, allow_same_bar_reclaim
    liquidity.py     ← add reclaim, classification, tagging, lifecycle
  tests/
    test_structure_swings.py      ← existing, must still pass
    test_structure_events.py      ← existing, must still pass
    test_structure_liquidity.py   ← extend with 3B groups
    test_structure_regime.py      ← existing, must still pass
    test_structure_replay.py      ← existing, must still pass
    test_structure_eurusd.py      ← extend with 3B coverage
    test_structure_xauusd.py      ← extend with 3B coverage
```

---

## When you are done

Run all test groups in `ACCEPTANCE_TESTS.md` — both 3B-specific and the full 3A regression suite. Report pass/fail per group. Do not declare Phase 3B complete until both EURUSD and XAUUSD pass all groups and the Officer and feed modules are confirmed untouched.
