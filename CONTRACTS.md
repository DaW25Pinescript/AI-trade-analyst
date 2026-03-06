# CONTRACTS.md — Phase 3A Structure Object Schemas

## Why this file matters

Every downstream consumer — analyst agents, Senate, future replay tools — reads structure packets. The schemas defined here are the contract. Field names, types, and lifecycle values must be stable across 3A/3B/3C or downstream consumers break.

Fields may be **added** in later phases. Fields must never be **removed or renamed** without a versioned migration.

---

## ICT vocabulary standard

Use ICT vocabulary directly in all external schemas. Do not substitute generic names.

| ICT term | Use in schema |
|---|---|
| Break of Structure | `bos_bull`, `bos_bear` |
| Market Structure Shift / CHoCH | `mss_bull`, `mss_bear` |
| Swing High | `swing_high` |
| Swing Low | `swing_low` |
| Equal Highs | `equal_highs` |
| Equal Lows | `equal_lows` |
| Prior Day High | `prior_day_high` |
| Prior Day Low | `prior_day_low` |
| Prior Week High | `prior_week_high` |
| Prior Week Low | `prior_week_low` |
| Liquidity Sweep | `sweep_high`, `sweep_low` |

Internal helper variable names may stay neutral. Output objects use ICT-native terms.

---

## Structure Packet v1

Top-level packet written per instrument per timeframe:

```json
{
  "schema_version": "structure_packet_v1",
  "instrument": "EURUSD",
  "timeframe": "1h",
  "as_of": "2026-03-07T10:00:00Z",
  "build": {
    "engine_version": "phase_3a",
    "source": "derived_1h_parquet",
    "quality_flag": "trusted",
    "pivot_left_bars": 3,
    "pivot_right_bars": 3,
    "bos_confirmation": "close",
    "eqh_eql_tolerance": 0.00010
  },
  "swings": [],
  "events": [],
  "liquidity": [],
  "regime": {},
  "diagnostics": {
    "bars_processed": 240,
    "swings_confirmed": 14,
    "bos_events": 3,
    "mss_events": 1,
    "liquidity_levels": 6,
    "sweep_events": 2
  }
}
```

---

## SwingPoint

```json
{
  "id": "sw_1h_20260306T0800_sh",
  "type": "swing_high",
  "price": 1.08642,
  "anchor_time": "2026-03-06T08:00:00Z",
  "confirm_time": "2026-03-06T11:00:00Z",
  "timeframe": "1h",
  "confirmation_method": "pivot_lr",
  "left_bars": 3,
  "right_bars": 3,
  "strength": 3,
  "status": "confirmed"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Stable unique ID — never changes on rerun |
| `type` | `swing_high` \| `swing_low` | ICT swing type |
| `price` | float | Exact high (for swing_high) or low (for swing_low) of anchor bar |
| `anchor_time` | ISO8601 UTC | Timestamp of the anchor bar |
| `confirm_time` | ISO8601 UTC | Timestamp of the bar that completed right-side confirmation |
| `timeframe` | string | Source timeframe |
| `confirmation_method` | `pivot_lr` | Fixed pivot method in 3A |
| `left_bars` | int | Left-side bars used for confirmation |
| `right_bars` | int | Right-side bars used for confirmation |
| `strength` | int | Number of right bars confirmed (up to `right_bars`) |
| `status` | `confirmed` \| `broken` \| `superseded` \| `archived` | Lifecycle state |

**Python dataclass:**

```python
@dataclass
class SwingPoint:
    id:                   str
    type:                 str        # "swing_high" | "swing_low"
    price:                float
    anchor_time:          datetime
    confirm_time:         datetime
    timeframe:            str
    confirmation_method:  str = "pivot_lr"
    left_bars:            int = 3
    right_bars:           int = 3
    strength:             int = 3
    status:               str = "confirmed"

    def to_dict(self) -> dict: ...
```

---

## StructureEvent (BOS and MSS)

```json
{
  "id": "ev_1h_20260307T1000_bos_bull",
  "type": "bos_bull",
  "time": "2026-03-07T10:00:00Z",
  "timeframe": "1h",
  "reference_swing_id": "sw_1h_20260306T0800_sh",
  "reference_price": 1.08642,
  "break_close": 1.08660,
  "prior_bias": null,
  "status": "confirmed"
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable unique ID |
| `type` | `bos_bull` \| `bos_bear` \| `mss_bull` \| `mss_bear` | ICT event type |
| `time` | ISO8601 UTC | Close time of the confirming bar |
| `timeframe` | string | Source timeframe |
| `reference_swing_id` | string | ID of the broken swing |
| `reference_price` | float | Price level of the broken swing |
| `break_close` | float | Actual close price that confirmed the break |
| `prior_bias` | `"bullish"` \| `"bearish"` \| null | Required for MSS; null for plain BOS |
| `status` | `confirmed` \| `superseded` | Usually immutable once confirmed |

**Python dataclass:**

```python
@dataclass
class StructureEvent:
    id:                  str
    type:                str
    time:                datetime
    timeframe:           str
    reference_swing_id:  str
    reference_price:     float
    break_close:         float
    prior_bias:          Optional[str] = None
    status:              str = "confirmed"

    def to_dict(self) -> dict: ...
```

---

## LiquidityLevel

```json
{
  "id": "liq_1h_pdh_20260306T2100",
  "type": "prior_day_high",
  "price": 1.08720,
  "origin_time": "2026-03-06T21:00:00Z",
  "timeframe": "1h",
  "status": "active",
  "swept_time": null,
  "sweep_type": null
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable unique ID |
| `type` | `prior_day_high` \| `prior_day_low` \| `prior_week_high` \| `prior_week_low` \| `equal_highs` \| `equal_lows` | ICT level type |
| `price` | float | Representative price of the level |
| `origin_time` | ISO8601 UTC | Session open of the originating period |
| `timeframe` | string | Source timeframe |
| `status` | `active` \| `swept` \| `invalidated` \| `archived` | Lifecycle state |
| `swept_time` | ISO8601 UTC \| null | Time of sweep if swept |
| `sweep_type` | `wick_sweep` \| `close_sweep` \| null | How it was swept |

**For EQH/EQL, additional fields:**

```json
{
  "id": "liq_1h_eqh_20260306T1200",
  "type": "equal_highs",
  "price": 1.08645,
  "origin_time": "2026-03-06T12:00:00Z",
  "timeframe": "1h",
  "status": "active",
  "swept_time": null,
  "sweep_type": null,
  "member_swing_ids": ["sw_1h_20260306T0800_sh", "sw_1h_20260306T1200_sh"],
  "tolerance_used": 0.00010
}
```

**Python dataclass:**

```python
@dataclass
class LiquidityLevel:
    id:                str
    type:              str
    price:             float
    origin_time:       datetime
    timeframe:         str
    status:            str = "active"
    swept_time:        Optional[datetime] = None
    sweep_type:        Optional[str] = None
    member_swing_ids:  list[str] = field(default_factory=list)
    tolerance_used:    Optional[float] = None

    def to_dict(self) -> dict: ...
```

---

## SweepEvent

```json
{
  "id": "swp_1h_20260307T0900_pdh",
  "type": "sweep_high",
  "time": "2026-03-07T09:00:00Z",
  "timeframe": "1h",
  "liquidity_level_id": "liq_1h_pdh_20260306T2100",
  "sweep_price": 1.08735,
  "sweep_type": "wick_sweep",
  "status": "confirmed"
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable unique ID |
| `type` | `sweep_high` \| `sweep_low` | Side of liquidity swept |
| `time` | ISO8601 UTC | Bar time of the sweep |
| `timeframe` | string | Source timeframe |
| `liquidity_level_id` | string | ID of the swept level |
| `sweep_price` | float | Wick high (or low) that traded through the level |
| `sweep_type` | `wick_sweep` \| `close_sweep` | How price interacted |
| `status` | `confirmed` | Immutable once confirmed |

**Python dataclass:**

```python
@dataclass
class SweepEvent:
    id:                   str
    type:                 str
    time:                 datetime
    timeframe:            str
    liquidity_level_id:   str
    sweep_price:          float
    sweep_type:           str
    status:               str = "confirmed"

    def to_dict(self) -> dict: ...
```

---

## RegimeSummary

```json
{
  "bias": "bullish",
  "last_bos_direction": "bullish",
  "last_mss_direction": null,
  "trend_state": "trending",
  "structure_quality": "clean"
}
```

| Field | Values | Derivation |
|---|---|---|
| `bias` | `bullish` \| `bearish` \| `neutral` | Direction of most recent confirmed BOS |
| `last_bos_direction` | `bullish` \| `bearish` \| null | Most recent BOS event direction |
| `last_mss_direction` | `bullish` \| `bearish` \| null | Most recent MSS event direction, else null |
| `trend_state` | `trending` \| `ranging` \| `unknown` | Last 3 BOS same direction → trending; alternating → ranging |
| `structure_quality` | `clean` \| `choppy` \| `unknown` | No opposing BOS in last 5 swing cycles → clean |

**Python dataclass:**

```python
@dataclass
class RegimeSummary:
    bias:                 str
    last_bos_direction:   Optional[str]
    last_mss_direction:   Optional[str]
    trend_state:          str
    structure_quality:    str

    def to_dict(self) -> dict: ...
```

---

## Schema evolution policy

- **Phase 3A**: Core structure objects as defined above
- **Phase 3B**: `LiquidityLevel` gains `reclaim_time`, `acceptance_confirmed` fields; `SweepEvent` gains `post_sweep_close`; ATR-scaled tolerance added to config
- **Phase 3C**: New top-level `imbalance` array added to packet; `FVGZone` object introduced
- **Phase 3D**: Cross-timeframe synthesis fields; Officer integration fields; Parquet output

**Never remove or rename a field. Adding fields is always safe.**

---

## Output file naming

```
structure/output/{instrument_lower}_{tf}_structure.json

eurusd_15m_structure.json
eurusd_1h_structure.json
eurusd_4h_structure.json
xauusd_15m_structure.json
xauusd_1h_structure.json
xauusd_4h_structure.json
```
