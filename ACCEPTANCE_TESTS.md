# ACCEPTANCE_TESTS.md — Phase 3A Exit Criteria

## How to use this file

Seven test groups. Phase 3A is not complete until all pass for both EURUSD and XAUUSD. Implement tests in `market_data_officer/tests/` and run via `pytest`. Report pass/fail per group.

Prerequisite: Phase 1A/1B feed pipeline has run. Derived Parquet files exist in `market_data/derived/` for both instruments.

---

## Group A — Swing detection

### A.1 — Confirmed swings detected on known fixture

Build a synthetic bar fixture with known pivot geometry:

```python
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

def make_fixture_bars(prices: list, start: datetime) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame from a list of close prices."""
    rows = []
    for i, p in enumerate(prices):
        rows.append({
            "open": p, "high": p + 0.0005, "low": p - 0.0005,
            "close": p, "volume": 100.0
        })
    idx = pd.date_range(start=start, periods=len(prices), freq="1h", tz="UTC")
    return pd.DataFrame(rows, index=idx)

# Fixture: prices that form a clear swing high at index 3 with 3L/3R confirmation
prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,  # swing high at index 3
          1.080, 1.079, 1.078, 1.075, 1.077, 1.078, 1.079]  # swing low at index 10
```

```python
from structure.swings import detect_swings
from structure.config import StructureConfig

config = StructureConfig(pivot_left_bars=3, pivot_right_bars=3)
bars = make_fixture_bars(prices, datetime(2026, 1, 1, tzinfo=timezone.utc))
swings = detect_swings(bars, config)

highs = [s for s in swings if s.type == "swing_high"]
lows  = [s for s in swings if s.type == "swing_low"]

assert len(highs) >= 1
assert abs(highs[0].price - 1.085) < 0.0001
assert len(lows) >= 1
assert abs(lows[0].price - 1.075) < 0.0001
```

### A.2 — Confirmation timestamps are correct

```python
# For 3L/3R pivot, confirm_time = anchor_time + right_bars * bar_interval
swing_high = highs[0]
expected_confirm = swing_high.anchor_time + timedelta(hours=3)
assert swing_high.confirm_time == expected_confirm
```

### A.3 — No pre-confirmation lookahead

```python
# Swings must not have confirm_time before anchor_time + right_bars * interval
for swing in swings:
    delta = (swing.confirm_time - swing.anchor_time).total_seconds() / 3600
    assert delta >= config.pivot_right_bars, \
        f"Lookahead detected: {swing.id} confirmed before right bars closed"
```

### A.4 — Swing IDs are stable across reruns

```python
swings_run1 = detect_swings(bars, config)
swings_run2 = detect_swings(bars, config)

ids_run1 = {s.id for s in swings_run1}
ids_run2 = {s.id for s in swings_run2}
assert ids_run1 == ids_run2
```

### A.5 — Empty bars return empty swing list, no crash

```python
empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
result = detect_swings(empty, config)
assert result == []
```

---

## Group B — BOS and MSS events

### B.1 — BOS fires only after close confirmation

```python
from structure.events import detect_events

# Build fixture: swing high at 1.085, then bars that wick above but don't close above,
# then a bar that closes above
wick_only_prices = [1.080, 1.081, 1.082, 1.085, 1.083, 1.082, 1.081,
                    1.082, 1.083, 1.084]  # wick can go to 1.086 but close stays below 1.085

# Verify no BOS emitted on wick-only breach
bars_wick = make_fixture_with_wicks(...)  # high=1.086, close=1.084 on bar 9
events_wick = detect_events(bars_wick, swings, config)
bos_events = [e for e in events_wick if "bos" in e.type]
assert len(bos_events) == 0, "BOS must not fire on wick-only breach"
```

```python
# Now add a bar that closes above 1.085
bars_close_break = make_fixture_with_close_break(...)  # close=1.086
events_close = detect_events(bars_close_break, swings, config)
bos_events = [e for e in events_close if e.type == "bos_bull"]
assert len(bos_events) == 1
assert bos_events[0].break_close > 1.085
```

### B.2 — BOS event links to correct reference swing

```python
bos = bos_events[0]
assert bos.reference_swing_id == swing_high.id
assert abs(bos.reference_price - swing_high.price) < 0.00001
```

### B.3 — MSS fires only on valid directional transition

```python
# Sequence: establish bearish structure via bos_bear, then fire bos_bull → should emit mss_bull
# Establish bos_bear first, then bos_bull:
events = detect_events(bars_with_directional_change, swings, config)
mss_events = [e for e in events if "mss" in e.type]

assert len(mss_events) >= 1
assert mss_events[0].type == "mss_bull"
assert mss_events[0].prior_bias == "bearish"
```

### B.4 — MSS prior_bias field is populated

```python
for mss in mss_events:
    assert mss.prior_bias in ("bullish", "bearish"), \
        f"MSS missing prior_bias: {mss.id}"
```

### B.5 — No BOS before its reference swing is confirmed

```python
for event in [e for e in events if "bos" in e.type]:
    ref_swing = next(s for s in swings if s.id == event.reference_swing_id)
    assert event.time > ref_swing.confirm_time, \
        f"BOS {event.id} fires before reference swing confirmed"
```

---

## Group C — Liquidity detection

### C.1 — Prior day high and low are correct

```python
from structure.liquidity import detect_liquidity_levels

levels = detect_liquidity_levels(bars, swings, config)
pdh_levels = [l for l in levels if l.type == "prior_day_high"]
pdl_levels = [l for l in levels if l.type == "prior_day_low"]

assert len(pdh_levels) >= 1
assert len(pdl_levels) >= 1

# Verify price is the actual high of the prior day's bars
prior_day_bars = bars[bars.index.date == prior_date]
assert abs(pdh_levels[0].price - prior_day_bars["high"].max()) < 0.00001
```

### C.2 — EQH detected within tolerance

```python
# Build fixture with two swing highs within 1 pip of each other
prices_eqh = [1.080, 1.083, 1.085, 1.083, 1.080, 1.079, 1.082,
              1.0849, 1.082, 1.080, 1.079, 1.077]  # second swing high at ~1.0849

levels = detect_liquidity_levels(bars_eqh, swings_eqh, config)
eqh_levels = [l for l in levels if l.type == "equal_highs"]

assert len(eqh_levels) >= 1
assert len(eqh_levels[0].member_swing_ids) >= 2
assert eqh_levels[0].tolerance_used == config.eqh_eql_tolerance["EURUSD"]
```

### C.3 — Sweep fires on wick-through, not just close-through

```python
# Build fixture: PDH at 1.087, then a bar with high=1.0875 but close=1.086
bars_sweep = make_bars_with_wick_through_pdh(...)

levels = detect_liquidity_levels(bars_sweep, swings, config)
sweeps = [l for l in levels if l.status == "swept"]

assert len(sweeps) >= 1
assert sweeps[0].sweep_type == "wick_sweep"
assert sweeps[0].swept_time is not None
```

### C.4 — Swept level status updates correctly

```python
# Before sweep bar: level is active
# After sweep bar: level is swept
pdh = next(l for l in levels if l.type == "prior_day_high")
assert pdh.status == "swept"
assert pdh.swept_time is not None
```

### C.5 — EQH/EQL uses instrument-correct tolerance

```python
# EURUSD tolerance != XAUUSD tolerance
eurusd_levels = detect_liquidity_levels(eurusd_bars, eurusd_swings, config)
xauusd_levels = detect_liquidity_levels(xauusd_bars, xauusd_swings, config)

eurusd_eqh = next((l for l in eurusd_levels if l.type == "equal_highs"), None)
xauusd_eqh = next((l for l in xauusd_levels if l.type == "equal_highs"), None)

if eurusd_eqh and xauusd_eqh:
    assert eurusd_eqh.tolerance_used != xauusd_eqh.tolerance_used
```

---

## Group D — Determinism

### D.1 — Identical inputs produce identical packet

```python
import json
from structure.engine import compute_structure_packet

packet_a = compute_structure_packet("EURUSD", "1h", config)
packet_b = compute_structure_packet("EURUSD", "1h", config)

dict_a = packet_a.to_dict()
dict_b = packet_b.to_dict()

# Core structural objects must be identical
assert dict_a["swings"] == dict_b["swings"]
assert dict_a["events"] == dict_b["events"]
assert dict_a["liquidity"] == dict_b["liquidity"]
assert dict_a["regime"] == dict_b["regime"]
```

### D.2 — Swing IDs are hash-stable from bar data

```python
# Manually recompute expected ID for a known swing
expected_id = f"sw_1h_{anchor_time.strftime('%Y%m%dT%H%M')}_sh"
assert swing_high.id == expected_id
```

### D.3 — `as_of` field updates but structure objects do not change on rerun

```python
# Two runs at different wall-clock times on same bar data
# as_of will differ, but structural objects must be identical
assert dict_a["swings"] == dict_b["swings"]  # not as_of
```

---

## Group E — Replay stability

### E.1 — Adding new bars does not alter existing confirmed swings

```python
bars_day1 = load_bars("EURUSD", "1h", end="2026-03-06")
bars_day2 = load_bars("EURUSD", "1h", end="2026-03-07")  # one more day

swings_day1 = detect_swings(bars_day1, config)
swings_day2 = detect_swings(bars_day2, config)

# All swings from day1 run must appear unchanged in day2 run
ids_day1 = {s.id: s for s in swings_day1}
ids_day2 = {s.id: s for s in swings_day2}

for sid, swing in ids_day1.items():
    assert sid in ids_day2, f"Swing {sid} disappeared after adding bars"
    assert ids_day2[sid].price == swing.price
    assert ids_day2[sid].anchor_time == swing.anchor_time
    assert ids_day2[sid].confirm_time == swing.confirm_time
```

### E.2 — New bars may add new confirmed objects but not mutate old ones

```python
new_swings = [s for s in swings_day2 if s.id not in ids_day1]
# New swings may exist (newly confirmed from day2 bars)
# Old swings must be unchanged
assert len(new_swings) >= 0  # zero or more is fine
```

### E.3 — Status transitions are additive only

```python
# A swing that was "confirmed" in day1 can only be "broken" or "superseded" in day2
# It cannot go back to a prior state
for sid, swing_d1 in ids_day1.items():
    swing_d2 = ids_day2.get(sid)
    if swing_d2:
        valid_transitions = {
            "confirmed": {"confirmed", "broken", "superseded", "archived"},
            "broken":    {"broken", "archived"},
            "superseded": {"superseded", "archived"},
            "archived":  {"archived"},
        }
        assert swing_d2.status in valid_transitions[swing_d1.status], \
            f"Invalid status transition: {swing_d1.status} → {swing_d2.status}"
```

---

## Group F — Cross-instrument coverage

### F.1 — EURUSD passes full structure suite on 15m, 1h, 4h

```bash
pytest market_data_officer/tests/test_structure_eurusd.py -v
# All tests pass, zero failures
```

### F.2 — XAUUSD passes full structure suite on 15m, 1h, 4h

```bash
pytest market_data_officer/tests/test_structure_xauusd.py -v
# All tests pass, zero failures
```

### F.3 — XAUUSD price range guard passes

```python
packet_xau = compute_structure_packet("XAUUSD", "1h", config)
all_swing_prices = [s.price for s in packet_xau.swings]

for price in all_swing_prices:
    assert 1_500.0 < price < 3_500.0, \
        f"XAUUSD swing price out of plausible range: {price}"
```

### F.4 — Engine uses correct EQH/EQL tolerance per instrument

```python
# EURUSD 1h packet should use 0.00010 tolerance
eurusd_packet = compute_structure_packet("EURUSD", "1h", config)
eqh_levels = [l for l in eurusd_packet.liquidity if l.type == "equal_highs"]
for level in eqh_levels:
    assert level.tolerance_used == 0.00010

# XAUUSD 1h packet should use 0.50 tolerance
xauusd_packet = compute_structure_packet("XAUUSD", "1h", config)
eqh_levels_xau = [l for l in xauusd_packet.liquidity if l.type == "equal_highs"]
for level in eqh_levels_xau:
    assert level.tolerance_used == 0.50
```

---

## Group G — Timeframe consistency and output

### G.1 — Each timeframe packet has correct `timeframe` field

```python
for tf in ["15m", "1h", "4h"]:
    packet = compute_structure_packet("EURUSD", tf, config)
    assert packet.timeframe == tf
    for swing in packet.swings:
        assert swing.timeframe == tf
    for event in packet.events:
        assert event.timeframe == tf
```

### G.2 — No impossible event ordering within a packet

```python
for event in packet.events:
    ref_swing = next((s for s in packet.swings if s.id == event.reference_swing_id), None)
    if ref_swing:
        assert event.time >= ref_swing.confirm_time, \
            f"Event {event.id} fires before reference swing confirmed"
```

### G.3 — JSON packets are written to correct paths

```python
import os

for instrument in ["EURUSD", "XAUUSD"]:
    for tf in ["15m", "1h", "4h"]:
        path = f"market_data_officer/structure/output/{instrument.lower()}_{tf}_structure.json"
        assert os.path.exists(path), f"Missing: {path}"
```

### G.4 — JSON packets are valid and schema-complete

```python
import json

with open("market_data_officer/structure/output/eurusd_1h_structure.json") as f:
    packet = json.load(f)

assert packet["schema_version"] == "structure_packet_v1"
assert packet["instrument"] == "EURUSD"
assert packet["timeframe"] == "1h"
assert "swings" in packet
assert "events" in packet
assert "liquidity" in packet
assert "regime" in packet
assert "diagnostics" in packet
assert "build" in packet
assert packet["build"]["engine_version"] == "phase_3a"
assert packet["build"]["bos_confirmation"] == "close"
```

### G.5 — CLI entry point runs without exception

```bash
python run_structure.py --instrument EURUSD --timeframes 15m 1h 4h
python run_structure.py --instrument XAUUSD --timeframes 15m 1h 4h
# Both must complete without unhandled exceptions
```

### G.6 — Officer and feed modules are untouched

```bash
# Confirm no imports of structure modules in officer or feed
grep -rn "from structure" market_data_officer/officer/
grep -rn "from structure" market_data_officer/feed/
# Must return no matches
```

---

## Phase 3A sign-off checklist

Before marking Phase 3A complete:

- [ ] Group A (swing detection) — all pass, EURUSD + XAUUSD
- [ ] Group B (BOS/MSS) — all pass, including wick-only BOS rejection test
- [ ] Group C (liquidity) — all pass, sweep fires on wick, EQH uses instrument tolerance
- [ ] Group D (determinism) — identical inputs produce identical packets
- [ ] Group E (replay stability) — confirmed objects never mutate on new bars
- [ ] Group F (cross-instrument) — both instruments pass full suite
- [ ] Group G (timeframe + output) — 6 JSON packets written, schema-complete
- [ ] No lookahead in any confirmed object (Group A.3)
- [ ] No BOS fires on wick-only breach (Group B.1)
- [ ] Officer and feed modules untouched (Group G.6)
- [ ] `run_structure.py --help` works
- [ ] `run_structure.py` produces all 6 JSON packets end-to-end
