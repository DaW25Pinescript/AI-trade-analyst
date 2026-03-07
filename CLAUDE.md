# CLAUDE.md — Structure Engine: Phase 3C

## Role

You are a principal Python/data engineer working inside the **AI Trade Analyst** repository.

Your job in this task is to build the **imbalance engine** — Phase 3C of the Structure Engine. Phases 3A and 3B are complete and merged. You are adding a new module, not rewriting anything that exists.

Read this file first. Then read the supporting spec files in order before writing any code.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**Already complete — do not touch:**
- `market_data_officer/feed/` — Phase 1A–1D feed pipeline
- `market_data_officer/officer/` — Phase 2 Market Data Officer
- `market_data_officer/structure/swings.py` — confirmed swing detection
- `market_data_officer/structure/events.py` — BOS/MSS close-confirmed
- `market_data_officer/structure/liquidity.py` — prior H/L, EQH/EQL, sweeps, reclaim, lifecycle
- `market_data_officer/structure/regime.py` — bias, trend state, structure quality
- `market_data_officer/structure/schemas.py` — all 3A/3B typed objects
- `market_data_officer/structure/config.py` — StructureConfig with 3A/3B parameters
- `market_data_officer/structure/io.py` — bar loading, atomic JSON writes
- `market_data_officer/structure/engine.py` — orchestration

**What you are building in Phase 3C:**
- `structure/imbalance.py` — FVG detection, fill tracking, invalidation, zone registry
- `structure/schemas.py` — extend with `FairValueGap` dataclass
- `structure/config.py` — add narrow 3C config surface
- `structure/engine.py` — integrate imbalance into orchestration and packet output
- `tests/` — add 3C test groups

---

## Phase 3A and 3B decisions that are locked

| Decision | Value |
|---|---|
| Swing confirmation | Fixed left/right pivot only |
| BOS/MSS confirmation | Close beyond prior swing only |
| EQH/EQL tolerance | Fixed per-instrument in config |
| Reclaim rule | Close confirmation only |
| Reclaim window | `allow_same_bar_reclaim` + `reclaim_window_bars` |
| Active timeframes | 15m, 1h, 4h |
| Output format | JSON only, pretty-printed, UTF-8, atomic |
| Officer integration | Not in scope |
| Cross-timeframe synthesis | Not in scope |
| Parquet output | Deferred to Phase 3D |

Do not reopen any of these.

---

## 3C decisions locked in this spec

| Decision | Value |
|---|---|
| FVG definition | Body-only (open-to-close gap between candle 1 and candle 3) |
| Wick-inclusive mode | Deferred to later phase |
| Fill progression | Partial + full tracked as separate states |
| Invalidation rule | Zone invalidated when fully filled |
| 50% threshold mode | Not in scope for 3C |
| Config-selectable invalidation | Not in scope for 3C |

---

## File reading order

Before writing any code, read in order:

1. `CLAUDE.md` ← you are here
2. `OBJECTIVE.md` — what 3C builds and the FVG detection contract
3. `CONSTRAINTS.md` — hard rules, schema evolution, config surface
4. `CONTRACTS.md` — FairValueGap schema, lifecycle, packet integration
5. `ACCEPTANCE_TESTS.md` — 7 test groups you must pass

---

## Repo placement

```
market_data_officer/
  structure/
    schemas.py        ← add FairValueGap dataclass
    config.py         ← add 3C config fields
    imbalance.py      ← NEW: FVG detection, fill tracking, zone registry
    engine.py         ← extend to include imbalance in packet output
  tests/
    test_structure_swings.py       ← existing, must still pass
    test_structure_events.py       ← existing, must still pass
    test_structure_liquidity.py    ← existing, must still pass
    test_structure_regime.py       ← existing, must still pass
    test_structure_replay.py       ← existing, must still pass
    test_structure_eurusd.py       ← extend with 3C coverage
    test_structure_xauusd.py       ← extend with 3C coverage
    test_structure_imbalance.py    ← NEW: all 3C test groups
```

---

## When you are done

Run Group 0 regression first. If anything fails there, stop and report before proceeding to 3C tests. Then run Groups A through G. Report pass/fail per group before declaring Phase 3C complete.
