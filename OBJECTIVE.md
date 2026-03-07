# OBJECTIVE.md — Phase 3C: Imbalance Engine

## What Phase 3C adds and why

Phases 3A and 3B established deterministic structural state — confirmed swings, BOS, MSS, liquidity levels, sweep detection, reclaim, and lifecycle tracking. Every object is numeric, testable, and replay-safe.

The gap those phases leave is **price inefficiency zones**. After a rapid move, the market leaves behind imbalances — candles where price moved so quickly that one side of the market never fully participated. ICT calls these Fair Value Gaps (FVGs). They are price magnets: the market tends to return to fill them, partially or fully, before continuing.

Phase 3C makes FVGs first-class structural objects with the same deterministic, auditable properties as everything built so far:
- Detected from body-only gap logic
- Tracked through a defined fill lifecycle
- Invalidated at full fill
- Registered as an active zone registry per timeframe
- Available to downstream agents as structured state — not inferred from chart images

This is the natural next layer after liquidity refinement. Sweeps (3B) tell you where liquidity was taken. FVGs (3C) tell you where price may return to before the next directional move.

---

## FVG detection contract

### Definition

A Fair Value Gap is a three-candle pattern where a gap exists between the **body** of candle 1 and the **body** of candle 3.

- **Bullish FVG**: `candle_3.low > candle_1.high` — gap above candle 1, below candle 3
- **Bearish FVG**: `candle_3.high < candle_1.low` — gap below candle 1, above candle 3

Use **body** boundaries only in Phase 3C:
- `candle.high` = body top = `max(open, close)`
- `candle.low` = body bottom = `min(open, close)`

Do not use wick high/low for gap detection. Wick-inclusive mode is deferred.

### Minimum gap size

Filter out micro-gaps using a minimum size threshold configurable per instrument:

```python
fvg_min_size_eurusd: float = 0.0003   # 3 pips
fvg_min_size_xauusd: float = 0.30     # 30 cents
```

Gaps below the minimum size are discarded at detection time.

### Anchor timing

- `origin_time` = timestamp of candle 2 (the middle candle — the impulse candle)
- `confirm_time` = timestamp of candle 3 (when the gap is confirmed)
- Zone is not emitted until candle 3 closes — no pre-confirmation leakage

---

## FVG zone properties

Each detected FVG zone has:

| Property | Description |
|---|---|
| `fvg_type` | `bullish_fvg` or `bearish_fvg` |
| `zone_high` | Upper boundary of the gap |
| `zone_low` | Lower boundary of the gap |
| `zone_size` | `zone_high - zone_low` |
| `origin_time` | Timestamp of candle 2 |
| `confirm_time` | Timestamp of candle 3 |
| `timeframe` | Source timeframe |
| `status` | Lifecycle state |
| `fill_low` | Lowest close reached into the zone (for bullish FVG) |
| `fill_high` | Highest close reached into the zone (for bearish FVG) |
| `first_touch_time` | Timestamp when zone was first entered |
| `partial_fill_time` | Timestamp when partial fill was confirmed |
| `full_fill_time` | Timestamp when full fill was confirmed |

---

## Fill progression

Track two fill states as separate, sequential stages:

### Partial fill

Triggered when a candle **closes into the zone**:
- **Bullish FVG**: a bearish candle closes below `zone_high` but above `zone_low`
- **Bearish FVG**: a bullish candle closes above `zone_low` but below `zone_high`

### Full fill

Triggered when a candle **closes through to the opposite edge**:
- **Bullish FVG**: a candle closes at or below `zone_low`
- **Bearish FVG**: a candle closes at or above `zone_high`

A zone must pass through `partially_filled` before reaching `fully_filled`. A zone cannot skip directly from `open` to `fully_filled` — if price blows straight through, both transitions fire in sequence on the same bar.

---

## Zone lifecycle

```
open
  → partially_filled   (close enters zone)
  → fully_filled       (close reaches/breaches opposite edge)
  → invalidated        (triggered by full fill)
  → archived           (future cleanup)
```

Full fill and invalidation are the same event — when a zone is fully filled it is immediately marked invalidated. They are not two separate steps from the engine's perspective; `fully_filled` is the trigger state and `invalidated` is the resulting status.

Allowed transitions:
- `open` → `partially_filled`
- `partially_filled` → `fully_filled`
- `open` → `partially_filled` → `fully_filled` → `invalidated` (same bar if price blows through)
- `invalidated` → `archived`

Disallowed:
- `open` → `fully_filled` (must pass through `partially_filled`)
- Any backward transition
- `invalidated` → any active state

---

## Active zone registry

Maintain a per-timeframe active zone registry — the set of FVG zones currently in `open` or `partially_filled` status.

The registry is what downstream agents query. It answers: "what FVG zones are currently live for this instrument and timeframe?"

The registry updates on every engine run:
- New confirmed zones are added
- Zones that reach `invalidated` are removed from active
- `archived` zones are retained in the full packet but not in the active registry

---

## What Phase 3C explicitly does NOT include

| Out of scope | Phase |
|---|---|
| Wick-inclusive FVG detection | 3C extension |
| 50% fill threshold | Not planned for 3C |
| Config-selectable invalidation modes | Not planned for 3C |
| Order blocks | 3C+ |
| FVG confluence with structure | 3D+ |
| Cross-timeframe FVG synthesis | 3D |
| Officer packet integration | 3D |
| Parquet output | 3D |
| Trade signals or confluence scoring | Never in structure engine |

---

## Definition of done

Phase 3C is complete when:
- FVG detection uses body-only logic with minimum size filter
- Fill progression tracks partial and full as separate states
- Zones cannot skip from open to fully_filled without partial_fill transition
- Active zone registry is maintained per timeframe
- Invalidation fires at full fill
- All lifecycle transitions are additive and replay-safe
- Both EURUSD and XAUUSD pass all test groups
- All 3A and 3B tests still pass
- Officer and feed modules untouched
- JSON packets include `imbalance` array and `active_zones` registry
