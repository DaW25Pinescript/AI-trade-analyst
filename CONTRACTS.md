# CONTRACTS.md — Phase 3B Schema Additions

## Schema evolution policy

Add fields only. Do not rename or remove any Phase 3A fields. Downstream consumers depending on existing field names must not break.

New fields added in 3B are nullable where resolution is pending. Once resolved, they become immutable.

---

## LiquidityLevel — 3B additions

### Full 3B schema

```json
{
  "id": "liq_001",
  "type": "prior_day_high",
  "price": 1.08720,
  "origin_time": "2026-03-06T21:00:00Z",
  "timeframe": "1h",
  "status": "swept",

  "swept_time": "2026-03-07T10:15:00Z",

  "liquidity_scope": "external_liquidity",

  "outcome": "reclaimed",
  "reclaim_time": "2026-03-07T10:30:00Z",
  "reclaim_window_bars": 1
}
```

### New fields

| Field | Type | Values | Notes |
|---|---|---|---|
| `liquidity_scope` | `str \| None` | `external_liquidity` \| `internal_liquidity` \| `unclassified` | Set at level creation time, not post-sweep |
| `outcome` | `str \| None` | `reclaimed` \| `accepted_beyond` \| `unresolved` \| `null` | `null` until swept, then resolves |
| `reclaim_time` | `ISO8601 str \| null` | UTC timestamp | Set when reclaim is confirmed, else `null` |
| `reclaim_window_bars` | `int \| null` | positive int | Config value in effect when sweep occurred |

### Allowed status transitions (full lifecycle)

```
active
  → swept          (sweep detected)
  → invalidated    (structural invalidation)

swept
  → reclaimed      (reclaim confirmed within window)
  → accepted_beyond (window closed, no reclaim)

invalidated → archived
reclaimed   → archived
accepted_beyond → archived
```

No backward transitions. No skipped states.

---

## SweepEvent — 3B additions

### Full 3B schema

```json
{
  "id": "sw_ev_001",
  "type": "sweep_high",
  "time": "2026-03-07T10:15:00Z",
  "timeframe": "1h",
  "sweep_price": 1.08731,
  "linked_liquidity_id": "liq_001",

  "post_sweep_close": 1.08695,
  "reclaim_time": "2026-03-07T10:30:00Z",
  "outcome": "reclaimed",
  "reclaim_window_bars": 1
}
```

### New fields

| Field | Type | Values | Notes |
|---|---|---|---|
| `post_sweep_close` | `float \| null` | price | Close of the bar that confirmed or failed reclaim |
| `reclaim_time` | `ISO8601 str \| null` | UTC timestamp | Matches linked LiquidityLevel.reclaim_time |
| `outcome` | `str \| null` | `reclaimed` \| `accepted_beyond` \| `unresolved` | Mirrors linked level outcome |
| `reclaim_window_bars` | `int \| null` | positive int | Config value in effect at sweep time |

### Relationship to LiquidityLevel

SweepEvent and its linked LiquidityLevel must remain consistent:

```python
assert sweep_event.outcome == liquidity_level.outcome
assert sweep_event.reclaim_time == liquidity_level.reclaim_time
assert sweep_event.linked_liquidity_id == liquidity_level.id
```

This consistency must be enforced by the engine, not assumed by consumers.

---

## StructureConfig — 3B additions

Add only these two fields to `StructureConfig`:

```python
@dataclass
class StructureConfig:
    # --- existing 3A fields ---
    pivot_left_bars: int = 3
    pivot_right_bars: int = 3
    eqh_eql_tolerance_eurusd: float = 0.0005
    eqh_eql_tolerance_xauusd: float = 0.50
    # ... other 3A fields ...

    # --- 3B additions ---
    allow_same_bar_reclaim: bool = True
    reclaim_window_bars: int = 1
```

Do not add ATR scaling, wick BOS mode, or multi-bar acceptance parameters. Those are future phases.

---

## Structure packet — 3B impact

The top-level packet schema does not change. Existing consumers see enriched liquidity and sweep objects, but the packet envelope is unchanged:

```json
{
  "schema_version": "structure_packet_v1",
  "instrument": "EURUSD",
  "timeframe": "1h",
  "as_of": "2026-03-07T10:15:00Z",
  "build": {
    "engine_version": "phase_3b",
    "source_archive": "canonical_1m",
    "quality_flag": "trusted"
  },
  "swings": [...],
  "events": [...],
  "liquidity": [...],
  "regime": {...},
  "diagnostics": {}
}
```

Note: `engine_version` should update from `phase_3a` to `phase_3b`.

---

## Internal/external tagging reference

Implement this exactly. Do not expand or interpret beyond these rules:

```python
EXTERNAL_LEVEL_TYPES = {
    "prior_day_high",
    "prior_day_low",
    "prior_week_high",
    "prior_week_low",
}

def classify_liquidity_scope(level_type: str, level_price: float,
                              confirmed_swings: list) -> str:
    """
    Returns 'external_liquidity', 'internal_liquidity', or 'unclassified'.
    Prior day/week H/L are always external.
    EQH/EQL are classified relative to the most recent confirmed swing of the same side.
    If no relevant confirmed swing exists, return 'unclassified'.
    """
    if level_type in EXTERNAL_LEVEL_TYPES:
        return "external_liquidity"

    if level_type == "equal_highs":
        relevant = [s for s in confirmed_swings if s.type == "swing_high"]
        if not relevant:
            return "unclassified"
        most_recent_swing_high = max(relevant, key=lambda s: s.anchor_time)
        if level_price > most_recent_swing_high.price:
            return "external_liquidity"
        return "internal_liquidity"

    if level_type == "equal_lows":
        relevant = [s for s in confirmed_swings if s.type == "swing_low"]
        if not relevant:
            return "unclassified"
        most_recent_swing_low = min(relevant, key=lambda s: s.anchor_time)
        if level_price < most_recent_swing_low.price:
            return "external_liquidity"
        return "internal_liquidity"

    return "unclassified"
```

---

## Reclaim logic reference

Implement this exactly:

```python
def detect_reclaim(level_price: float, level_type: str,
                   sweep_bar_index: int, bars: pd.DataFrame,
                   config: StructureConfig) -> tuple[str, datetime | None, float | None]:
    """
    Returns (outcome, reclaim_time, post_sweep_close).
    outcome: 'reclaimed' | 'accepted_beyond' | 'unresolved'
    """
    is_high_side = level_type in {
        "prior_day_high", "prior_week_high", "equal_highs"
    }

    # Window: sweep bar + reclaim_window_bars subsequent bars
    window_start = sweep_bar_index if config.allow_same_bar_reclaim else sweep_bar_index + 1
    window_end = sweep_bar_index + config.reclaim_window_bars + 1

    window_bars = bars.iloc[window_start:window_end]

    if window_bars.empty:
        return "unresolved", None, None

    for _, bar in window_bars.iterrows():
        if is_high_side and bar["close"] < level_price:
            return "reclaimed", bar.name, bar["close"]
        if not is_high_side and bar["close"] > level_price:
            return "reclaimed", bar.name, bar["close"]

    # Window exhausted, check if we have enough bars to resolve
    if len(bars) > window_end:
        post_sweep_close = bars.iloc[window_end - 1]["close"]
        return "accepted_beyond", None, post_sweep_close

    return "unresolved", None, None
```
