# CONTRACTS.md — Phase 3C Schema and Packet Integration

## FairValueGap dataclass

Add to `structure/schemas.py`:

```python
@dataclass
class FairValueGap:
    id: str                          # e.g. "fvg_001"
    fvg_type: str                    # "bullish_fvg" | "bearish_fvg"
    zone_high: float                 # upper boundary
    zone_low: float                  # lower boundary
    zone_size: float                 # zone_high - zone_low
    origin_time: datetime            # candle 2 timestamp
    confirm_time: datetime           # candle 3 timestamp (emit after this)
    timeframe: str                   # "15m" | "1h" | "4h"
    status: str                      # see lifecycle below

    # Fill tracking
    fill_high: Optional[float]       # highest close reached into zone (bearish FVG)
    fill_low: Optional[float]        # lowest close reached into zone (bullish FVG)
    first_touch_time: Optional[datetime]
    partial_fill_time: Optional[datetime]
    full_fill_time: Optional[datetime]
```

---

## FVG JSON object — full schema

```json
{
  "id": "fvg_001",
  "fvg_type": "bullish_fvg",
  "zone_high": 1.08620,
  "zone_low": 1.08475,
  "zone_size": 0.00145,
  "origin_time": "2026-03-07T08:00:00Z",
  "confirm_time": "2026-03-07T08:15:00Z",
  "timeframe": "15m",
  "status": "partially_filled",

  "fill_high": null,
  "fill_low": 1.08510,
  "first_touch_time": "2026-03-07T09:30:00Z",
  "partial_fill_time": "2026-03-07T09:30:00Z",
  "full_fill_time": null
}
```

---

## Active zone registry JSON object

```json
{
  "instrument": "EURUSD",
  "timeframe": "1h",
  "as_of": "2026-03-07T10:00:00Z",
  "active_zones": [
    {
      "id": "fvg_001",
      "fvg_type": "bullish_fvg",
      "zone_high": 1.08620,
      "zone_low": 1.08475,
      "zone_size": 0.00145,
      "status": "partially_filled",
      "origin_time": "2026-03-07T08:00:00Z"
    },
    {
      "id": "fvg_003",
      "fvg_type": "bearish_fvg",
      "zone_high": 1.09140,
      "zone_low": 1.09010,
      "zone_size": 0.00130,
      "status": "open",
      "origin_time": "2026-03-06T14:00:00Z"
    }
  ]
}
```

Active zones = `open` + `partially_filled` only. `invalidated` and `archived` zones are not in this registry.

---

## Structure packet — 3C additions

The packet envelope gains two new keys: `imbalance` and `active_zones`.

```json
{
  "schema_version": "structure_packet_v1",
  "instrument": "EURUSD",
  "timeframe": "1h",
  "as_of": "2026-03-07T10:15:00Z",
  "build": {
    "engine_version": "phase_3c",
    "source_archive": "canonical_1m",
    "quality_flag": "trusted"
  },
  "swings": [...],
  "events": [...],
  "liquidity": [...],
  "imbalance": [...],
  "active_zones": {
    "count": 2,
    "zones": [...]
  },
  "regime": {...},
  "diagnostics": {}
}
```

### `imbalance`

Full list of all FVG objects for this timeframe — all statuses including invalidated. Same pattern as `liquidity` array in 3A/3B.

### `active_zones`

Compact registry of only `open` and `partially_filled` zones. Downstream agents read this for current live imbalance state without filtering the full `imbalance` array.

---

## StructureConfig — 3C additions

```python
@dataclass
class StructureConfig:
    # --- existing 3A fields ---
    pivot_left_bars: int = 3
    pivot_right_bars: int = 3
    eqh_eql_tolerance_eurusd: float = 0.0005
    eqh_eql_tolerance_xauusd: float = 0.50

    # --- existing 3B fields ---
    allow_same_bar_reclaim: bool = True
    reclaim_window_bars: int = 1

    # --- 3C additions ---
    fvg_min_size_eurusd: float = 0.0003    # 3 pips minimum gap
    fvg_min_size_xauusd: float = 0.30      # 30 cents minimum gap
    fvg_use_body_only: bool = True          # always True in 3C, wick mode deferred
```

`fvg_use_body_only` is always `True` in 3C. It is exposed as a config field to make future wick-mode extension clean, but must not be set to `False` in Phase 3C. The acceptance tests will assert this.

---

## FVG detection reference implementation

```python
def detect_fvg(bars: pd.DataFrame, config: StructureConfig,
               instrument: str) -> list[FairValueGap]:
    """
    Detect Fair Value Gaps using body-only logic.
    A zone is not emitted until candle 3 closes (no lookahead).
    Minimum gap size filtered per instrument config.
    """
    min_size = (config.fvg_min_size_xauusd
                if instrument == "XAUUSD"
                else config.fvg_min_size_eurusd)

    zones = []
    for i in range(2, len(bars)):
        c1 = bars.iloc[i - 2]
        c3 = bars.iloc[i]

        # Body boundaries
        c1_body_high = max(c1["open"], c1["close"])
        c1_body_low  = min(c1["open"], c1["close"])
        c3_body_high = max(c3["open"], c3["close"])
        c3_body_low  = min(c3["open"], c3["close"])

        # Bullish FVG: gap between c1 body top and c3 body low
        if c3_body_low > c1_body_high:
            gap_size = c3_body_low - c1_body_high
            if gap_size >= min_size:
                zones.append(FairValueGap(
                    id=generate_id("fvg"),
                    fvg_type="bullish_fvg",
                    zone_high=c3_body_low,
                    zone_low=c1_body_high,
                    zone_size=gap_size,
                    origin_time=bars.index[i - 1],   # candle 2
                    confirm_time=bars.index[i],       # candle 3
                    timeframe=...,
                    status="open",
                    fill_high=None, fill_low=None,
                    first_touch_time=None,
                    partial_fill_time=None,
                    full_fill_time=None,
                ))

        # Bearish FVG: gap between c3 body high and c1 body low
        elif c3_body_high < c1_body_low:
            gap_size = c1_body_low - c3_body_high
            if gap_size >= min_size:
                zones.append(FairValueGap(
                    id=generate_id("fvg"),
                    fvg_type="bearish_fvg",
                    zone_high=c1_body_low,
                    zone_low=c3_body_high,
                    zone_size=gap_size,
                    origin_time=bars.index[i - 1],
                    confirm_time=bars.index[i],
                    timeframe=...,
                    status="open",
                    fill_high=None, fill_low=None,
                    first_touch_time=None,
                    partial_fill_time=None,
                    full_fill_time=None,
                ))

    return zones
```

---

## Fill tracking reference implementation

```python
def update_fvg_fills(zone: FairValueGap, bars: pd.DataFrame) -> FairValueGap:
    """
    Process subsequent bars after zone confirmation.
    Tracks partial and full fill transitions in order.
    A zone cannot skip from open to fully_filled without partial_fill.
    """
    if zone.status == "invalidated":
        return zone  # terminal state — do not reprocess

    subsequent = bars[bars.index > zone.confirm_time]

    for ts, bar in subsequent.iterrows():
        close = bar["close"]

        if zone.fvg_type == "bullish_fvg":
            if zone.status == "open" and close < zone.zone_high:
                # Entered the zone
                zone.status = "partially_filled"
                zone.first_touch_time = ts
                zone.partial_fill_time = ts
                zone.fill_low = close

            if zone.status == "partially_filled":
                zone.fill_low = min(zone.fill_low or close, close)
                if close <= zone.zone_low:
                    # Fully filled
                    zone.status = "invalidated"
                    zone.full_fill_time = ts
                    return zone

        elif zone.fvg_type == "bearish_fvg":
            if zone.status == "open" and close > zone.zone_low:
                zone.status = "partially_filled"
                zone.first_touch_time = ts
                zone.partial_fill_time = ts
                zone.fill_high = close

            if zone.status == "partially_filled":
                zone.fill_high = max(zone.fill_high or close, close)
                if close >= zone.zone_high:
                    zone.status = "invalidated"
                    zone.full_fill_time = ts
                    return zone

    return zone
```

---

## Lifecycle allowed transitions

```python
ALLOWED_FVG_TRANSITIONS = {
    "open":             {"partially_filled"},
    "partially_filled": {"invalidated"},
    "invalidated":      {"archived"},
}
```

Note: `open` → `partially_filled` → `invalidated` can occur on the same bar if price blows through the zone. Both transitions must fire in sequence, not skipped.

---

## Schema evolution note

`imbalance` and `active_zones` are new top-level packet keys. Existing consumers reading `swings`, `events`, `liquidity`, and `regime` are unaffected. `engine_version` updates to `phase_3c`.
