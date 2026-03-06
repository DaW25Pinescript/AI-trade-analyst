# OBJECTIVE.md — Phase 3A: What the Structure Engine Must Deliver

## Strategic framing

The feed gives you verified candles. The Officer gives you a market packet. But neither tells you *what the market is doing structurally* — where swings are, whether structure is broken, where liquidity sits, what the bias is.

Think of it like this: the feed is the raw sensor data, the Officer is the dashboard summary, and the Structure Engine is the analyst who reads the dashboard and maps the terrain — where are the hills, the valleys, the traps. Except in 3A, that analyst is purely mechanical. No opinions. Only confirmed facts.

The Structure Engine's job is to answer, deterministically, per timeframe:

- Where are the confirmed swing highs and lows?
- Has structure broken, and in which direction?
- Has the market shifted character (MSS)?
- Where is resting liquidity — prior highs/lows, equal levels?
- Has any liquidity been swept?
- What is the objective structural bias?

Every answer must be a typed object with timestamps, prices, and a confirmation basis. Nothing inferred. Nothing guessed.

---

## What Phase 3A must deliver

### 1. Confirmed swing detection (`swings.py`)

**Method: fixed left/right pivot confirmation only in 3A.**

A swing high is confirmed when:
- The anchor bar's high is greater than the highs of `left_bars` bars to the left
- The anchor bar's high is greater than the highs of `right_bars` bars to the right
- Both conditions are met on already-closed bars (no lookahead)

A swing low is confirmed symmetrically using lows.

Configuration:
```python
PIVOT_LEFT_BARS: int = 3   # default, configurable
PIVOT_RIGHT_BARS: int = 3  # default, configurable
```

Each confirmed swing must emit a `SwingPoint` object. See `CONTRACTS.md` for full schema.

ATR-scaled dynamic pivot is deferred to Phase 3B.

**No provisional swings in 3A.** A swing either meets confirmation criteria or does not exist yet.

---

### 2. BOS detection (`events.py`)

A **Break of Structure (BOS)** is confirmed when:

- A confirmed prior swing exists on the same timeframe
- A subsequent candle **closes** beyond that swing's price level
- Close-confirmation only — wick-only breaches do not trigger BOS in 3A
- Break direction is explicit: `bos_bull` (close above prior swing high) or `bos_bear` (close below prior swing low)
- The reference swing ID is linked in the event object

Each BOS must emit a `StructureEvent` object. See `CONTRACTS.md`.

Wick-based BOS mode is deferred to Phase 3B. Wick interaction in 3A is handled only by sweep detection.

---

### 3. MSS / CHoCH detection (`events.py`)

A **Market Structure Shift (MSS)** is confirmed when:

- A prior structural direction is established (from at least one confirmed BOS)
- A BOS fires in the **opposite** direction
- The prior bias is explicitly referenced in the event

Each MSS must emit a `StructureEvent` with:
- `type: "mss_bull"` or `"mss_bear"`
- `prior_bias` field
- Reference to the broken swing

MSS is directional confirmation of a structural character change. It is not a trade signal.

---

### 4. Prior period liquidity levels (`liquidity.py`)

Compute and track:

| Level | Description |
|---|---|
| `prior_day_high` | Previous completed day's high |
| `prior_day_low` | Previous completed day's low |
| `prior_week_high` | Previous completed week's high |
| `prior_week_low` | Previous completed week's low |

Each level must carry:
- `origin_time` — the session start of the prior period
- `price` — the exact high or low
- `status` — `active`, `swept`, `invalidated`
- `swept_time` — timestamp if swept, else null

Session calendar for prior period derivation is configurable.

---

### 5. Equal highs / equal lows (`liquidity.py`)

Detect **EQH** (equal highs) and **EQL** (equal lows) within a timeframe using a deterministic proximity rule:

- Two or more confirmed swing highs (or lows) within tolerance → EQH (or EQL)
- Minimum count: 2
- Same timeframe only in 3A
- Tolerance is **fixed pip/point value per instrument in config** for 3A
- ATR-scaled tolerance is deferred to Phase 3B

Each EQH/EQL object must include:
- Member swing IDs
- Representative price (average of members)
- Tolerance used
- Status: `active`, `swept`

---

### 6. Sweep detection (`liquidity.py`)

A sweep is identified when:

- Price trades through (wick or close) a `prior_day_high/low`, `prior_week_high/low`, or `EQH/EQL` level
- The liquidity object status updates to `swept`
- A `SweepEvent` is emitted with: level ID, sweep time, sweep direction, sweep type (`wick_sweep` or `close_sweep`)

**Important distinction from BOS:**
- BOS requires close confirmation
- Sweeps can be triggered by wick or close — price merely needs to trade through the level

Post-sweep reclaim/acceptance logic is deferred to Phase 3B.

---

### 7. Regime summary (`regime.py`)

Derive an objective structural summary per timeframe from the above outputs:

```python
{
  "bias": "bullish" | "bearish" | "neutral",
  "last_bos_direction": "bullish" | "bearish" | null,
  "last_mss_direction": "bullish" | "bearish" | null,
  "trend_state": "trending" | "ranging" | "unknown",
  "structure_quality": "clean" | "choppy" | "unknown"
}
```

**Derivation rules:**
- `bias`: direction of the most recent confirmed BOS
- `last_bos_direction`: direction field of the most recent BOS event
- `last_mss_direction`: direction of the most recent MSS event, else null
- `trend_state`: `trending` if last 3 BOS events are same direction, `ranging` if alternating, `unknown` if insufficient events
- `structure_quality`: `clean` if no opposing BOS within last 5 swing cycles, `choppy` if opposing BOS present, `unknown` if insufficient history

Regime is derivative and non-authoritative. It summarises confirmed events — it does not predict.

---

## What Phase 3A explicitly does NOT include

| Out of scope | Phase |
|---|---|
| FVG / imbalance detection | 3C |
| Order blocks | 3C+ |
| Internal vs external liquidity classification | 3B |
| Sweep reclaim / acceptance logic | 3B |
| Wick-based BOS mode | 3B |
| ATR-scaled pivot confirmation | 3B |
| 5m and 1d structure timeframes | 3B |
| Cross-timeframe synthesis | 3D |
| Officer packet integration | 3D |
| Parquet structure output | 3D |
| Trade entries / exits | Never in this layer |
| Confluence scoring | Never in this layer |
| LLM interpretation | Never in this layer |

---

## Definition of done

Phase 3A is complete when:
- Confirmed swings, BOS, MSS, prior levels, EQH/EQL, sweeps, and regime summary are all computed
- Both EURUSD and XAUUSD produce valid structure packets on 15m, 1h, and 4h
- All 7 acceptance test groups pass
- JSON packets are written to `structure/output/` with correct naming
- No lookahead leakage in any confirmed object
- Re-runs on same input produce identical output (determinism)
- Adding new bars does not silently alter already-confirmed objects (replay stability)
- Officer layer and feed pipeline are untouched
