# CONSTRAINTS.md — Phase 3A Hard Rules and Logic Contracts

## Non-negotiable rules

---

### RULE 1 — No lookahead leakage

This is the most important rule in the entire Structure Engine.

A confirmed swing, BOS, MSS, or sweep must never appear before its confirmation conditions are satisfied on already-closed bars.

```python
# Correct — confirmation uses bars[i + right_bars] which is already closed
if all(bars[i].high > bars[j].high for j in range(i - left_bars, i)) \
   and all(bars[i].high > bars[j].high for j in range(i + 1, i + right_bars + 1)):
    confirm_time = bars[i + right_bars].timestamp  # confirmation is the close of the right-side bar

# Wrong — inferring confirmation before right_bars are closed
confirm_time = bars[i].timestamp  # lookahead — confirmation not yet possible
```

Test this explicitly with fixture datasets. See `ACCEPTANCE_TESTS.md` Group A.

---

### RULE 2 — Close confirmation for BOS only

BOS is confirmed **only** when a candle **closes** beyond the reference swing price.

```python
# Correct
if bar.close > swing_high.price:
    emit_bos_bull(...)

# Wrong — wick breach is not a BOS trigger in 3A
if bar.high > swing_high.price:
    emit_bos_bull(...)
```

Wick interaction in 3A is reserved exclusively for sweep detection.

---

### RULE 3 — Append-safe reruns, no retroactive mutation

When new bars are appended and the engine reruns:

- Previously confirmed swings, events, and liquidity objects must not change
- New confirmed objects may be added for newly confirmed bars only
- The only allowed status transitions are additive: `active → swept`, `active → invalidated`
- No confirmed object's `price`, `anchor_time`, `confirm_time`, or `id` may change on rerun

```python
# Correct — new bars may produce new confirmed swings
existing_ids = {sw.id for sw in prior_swings}
new_swings = [sw for sw in recomputed if sw.id not in existing_ids]

# Wrong — replacing or mutating existing confirmed objects
prior_swings[3] = recomputed[3]  # mutation
```

---

### RULE 4 — Timeframe isolation

Each timeframe (15m, 1h, 4h) computes its own structure independently from its own derived bars.

No cross-timeframe logic in 3A. No "15m BOS confirmed by 1h" synthesis. No HTF bias filtering LTF swings. That is Phase 3D.

```python
# Correct
for tf in ["15m", "1h", "4h"]:
    bars = load_bars(instrument, tf)
    packet = engine.compute(bars, tf, config)
    write_packet(packet)

# Wrong — passing HTF context into LTF computation
bars_15m = load_bars(instrument, "15m")
bars_1h = load_bars(instrument, "1h")
packet = engine.compute(bars_15m, context=bars_1h)  # cross-TF synthesis not in 3A
```

---

### RULE 5 — Instrument neutrality

The engine must work identically for EURUSD and XAUUSD. No instrument-specific logic inside `swings.py`, `events.py`, `liquidity.py`, or `regime.py`.

Instrument-specific values (EQH/EQL tolerance, session calendar) belong in `config.py` only.

```python
# Correct — tolerance from config, not hardcoded
tolerance = config.eqh_eql_tolerance[instrument]

# Wrong — instrument check inside logic module
if instrument == "XAUUSD":
    tolerance = 0.50
```

---

### RULE 6 — Do not touch Officer or feed modules

The Structure Engine is a separate lane. It reads from `market_data/derived/` (same source as the Officer) but does not call Officer functions, modify Officer contracts, or alter feed pipeline code.

If the Officer needs updating to reference structure packets later, that is Phase 3D.

---

### RULE 7 — IDs must be stable and unique

Every `SwingPoint`, `StructureEvent`, `LiquidityLevel`, and `SweepEvent` must have a stable, unique ID that does not change on rerun.

Recommended ID scheme:
```python
# SwingPoint
f"sw_{timeframe}_{anchor_time_compact}_{type_abbrev}"
# e.g. "sw_1h_20260306T0800_sh"

# StructureEvent
f"ev_{timeframe}_{event_time_compact}_{type_abbrev}"
# e.g. "ev_15m_20260307T1015_bos_bull"

# LiquidityLevel
f"liq_{timeframe}_{type_abbrev}_{origin_time_compact}"
# e.g. "liq_1h_pdh_20260306T2100"
```

IDs must be deterministic — same bar data always produces same IDs.

---

### RULE 8 — JSON output is human-readable

Structure packets are JSON only in 3A. They must be:

- Pretty-printed (`indent=2`)
- UTF-8 encoded
- Written atomically (write to temp file, rename — avoid partial writes)
- Named predictably: `{instrument_lower}_{tf}_structure.json`

```python
import json, tempfile, os

def write_packet_atomic(packet: dict, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, default=str)
    os.replace(tmp, path)
```

---

## Module boundary map

| Module | Owns | Must not touch |
|---|---|---|
| `schemas.py` | Dataclass definitions, `to_dict()` | Computation logic, file I/O |
| `config.py` | All configurable parameters | Computation logic |
| `swings.py` | Confirmed pivot swing detection | Events, liquidity, regime, I/O |
| `events.py` | BOS and MSS detection from confirmed swings | Swing computation, liquidity, I/O |
| `liquidity.py` | Prior levels, EQH/EQL, sweep events | Swing computation, BOS logic |
| `regime.py` | Objective summary from swings + events | Any computation from raw bars |
| `io.py` | Load derived bars, write JSON packets | Computation logic |
| `engine.py` | Orchestrate all modules | Implement any module's logic directly |

---

## Configuration surface — keep narrow in 3A

Expose only these parameters in `config.py`:

```python
@dataclass
class StructureConfig:
    # Pivot confirmation
    pivot_left_bars:  int   = 3
    pivot_right_bars: int   = 3

    # BOS confirmation
    bos_confirmation: str   = "close"   # "close" only in 3A

    # EQH/EQL tolerance — fixed pip/point value per instrument
    eqh_eql_tolerance: dict = field(default_factory=lambda: {
        "EURUSD": 0.00010,   # 1 pip
        "XAUUSD": 0.50,      # 50 cents
    })

    # Enabled timeframes
    timeframes: list = field(default_factory=lambda: ["15m", "1h", "4h"])

    # Session calendar for prior high/low derivation (UTC hour of day session open)
    day_session_open_utc: int  = 21    # Sunday 21:00 UTC = start of FX week
    week_session_open_day: int = 6     # Sunday = 6 (ISO weekday)
```

Do not expose more knobs than this in 3A. Configuration sprawl before the logic is proven creates untestable combinations.

---

## Swing lifecycle

```
detected (internal only, not emitted)
    ↓
confirmed  ← emitted in SwingPoint object
    ↓
broken     ← status update when BOS fires through this swing
    ↓
superseded ← status update when a higher/lower swing replaces it
    ↓
archived   ← retained in packet history but no longer active
```

Status transitions are additive only. A `confirmed` swing never goes back to `detected`.

---

## Liquidity lifecycle

```
active      ← emitted when level is identified
    ↓
swept       ← price trades through (wick or close)
    ↓
invalidated ← level context no longer valid (e.g. far exceeded, period expired)
    ↓
archived    ← retained in packet history
```

---

## What "deterministic" means in this context

Given the same set of input bars:

1. The same `SwingPoint` objects are produced with the same IDs, prices, and timestamps
2. The same `StructureEvent` objects are produced
3. The same `LiquidityLevel` objects are produced
4. The JSON packet is logically identical (field values match, order may vary)

This must hold across:
- Multiple runs on the same machine
- Runs after adding new bars (existing confirmed objects unchanged)
- Runs on EURUSD vs XAUUSD (same logic, different config values)

---

## Code quality standards

- Every public function has a docstring
- Type hints on all function signatures
- Named constants for all threshold values — no magic numbers
- Raise `ValueError` for invalid bar data inputs
- Raise `RuntimeError` for internal state consistency violations
- `print()` acceptable for CLI progress; no logging framework required in 3A
- No ML libraries, no HTTP clients, no task frameworks

---

## Dependencies

No new dependencies beyond what exists. Phase 3A requires only:

```
pandas>=2.0
pyarrow>=14.0   # for reading derived Parquet inputs
```
