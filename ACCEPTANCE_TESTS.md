# ACCEPTANCE_TESTS.md — Phase 3C Exit Criteria

## How to use this file

Run Group 0 first. If anything fails, stop and report before proceeding. Then run Groups A through G. Report pass/fail per group before declaring Phase 3C complete.

---

## Group 0 — Full 3A + 3B regression

### T0.1 — All prior test files pass

```bash
pytest market_data_officer/tests/test_structure_swings.py
pytest market_data_officer/tests/test_structure_events.py
pytest market_data_officer/tests/test_structure_liquidity.py
pytest market_data_officer/tests/test_structure_regime.py
pytest market_data_officer/tests/test_structure_replay.py
pytest market_data_officer/tests/test_structure_eurusd.py
pytest market_data_officer/tests/test_structure_xauusd.py
# All must pass — 0 failures
```

### T0.2 — Engine version updated

```python
import json
with open("structure/output/eurusd_1h_structure.json") as f:
    packet = json.load(f)
assert packet["build"]["engine_version"] == "phase_3c"
```

### T0.3 — `fvg_use_body_only` is True in config

```python
from structure.config import StructureConfig
config = StructureConfig()
assert config.fvg_use_body_only is True
```

---

## Group A — FVG detection

### TA.1 — Bullish FVG detected correctly from body boundaries

```python
# Fixture: 3-bar sequence
# c1: open=1.0820, close=1.0840  → body_high=1.0840
# c2: open=1.0845, close=1.0880  → impulse candle
# c3: open=1.0882, close=1.0895  → body_low=1.0882
# Gap: c3_body_low (1.0882) > c1_body_high (1.0840) → bullish FVG

zones = detect_fvg(fixture_bars, config, "EURUSD")
assert len(zones) == 1
assert zones[0].fvg_type == "bullish_fvg"
assert zones[0].zone_low == 1.0840
assert zones[0].zone_high == 1.0882
assert zones[0].zone_size == pytest.approx(0.0042, abs=1e-5)
```

### TA.2 — Bearish FVG detected correctly from body boundaries

```python
# c1: open=1.0900, close=1.0880  → body_low=1.0880
# c2: open=1.0875, close=1.0840  → impulse candle
# c3: open=1.0838, close=1.0820  → body_high=1.0838
# Gap: c3_body_high (1.0838) < c1_body_low (1.0880) → bearish FVG

zones = detect_fvg(fixture_bars, config, "EURUSD")
assert zones[0].fvg_type == "bearish_fvg"
assert zones[0].zone_high == 1.0880
assert zones[0].zone_low == 1.0838
```

### TA.3 — Wick extension does not create false FVG

```python
# c1: open=1.0820, close=1.0840, high=1.0860  (wick extends higher)
# c3: open=1.0855, close=1.0865, low=1.0842   (wick dips lower)
# Body gap: c3_body_low=1.0855 > c1_body_high=1.0840 → valid bullish FVG
# But wick-based gap would be different — confirm body is used

zones = detect_fvg(fixture_bars, config, "EURUSD")
assert zones[0].zone_low == 1.0840   # c1 body high, not wick
assert zones[0].zone_high == 1.0855  # c3 body low, not wick
```

### TA.4 — Zone below minimum size is filtered out

```python
# EURUSD min size = 0.0003
# Create a 3-bar sequence with gap of 0.0001 (below minimum)

zones = detect_fvg(tiny_gap_bars, config, "EURUSD")
assert len(zones) == 0
```

### TA.5 — Zone above minimum size passes through

```python
# Gap = 0.0005 (above EURUSD minimum of 0.0003)
zones = detect_fvg(valid_gap_bars, config, "EURUSD")
assert len(zones) == 1
```

### TA.6 — `confirm_time` equals candle 3 timestamp

```python
zones = detect_fvg(fixture_bars, config, "EURUSD")
assert zones[0].confirm_time == fixture_bars.index[2]  # candle 3
assert zones[0].origin_time == fixture_bars.index[1]   # candle 2
```

### TA.7 — No zone emitted from first two bars (no lookahead)

```python
# Only 2 bars available — no candle 3 yet
zones = detect_fvg(fixture_bars.head(2), config, "EURUSD")
assert len(zones) == 0
```

---

## Group B — Fill progression

### TB.1 — Bullish FVG transitions to partially_filled on close into zone

```python
# Zone: zone_low=1.0840, zone_high=1.0882
# Subsequent bar: close=1.0855 (inside zone — below zone_high, above zone_low)

zone = update_fvg_fills(zone, subsequent_bars)
assert zone.status == "partially_filled"
assert zone.partial_fill_time is not None
assert zone.fill_low == 1.0855
```

### TB.2 — Bearish FVG transitions to partially_filled on close into zone

```python
# Zone: zone_low=1.0838, zone_high=1.0880
# Subsequent bar: close=1.0860 (inside zone)

zone = update_fvg_fills(zone, subsequent_bars)
assert zone.status == "partially_filled"
assert zone.fill_high == 1.0860
```

### TB.3 — fill_low tracks the lowest close reached (bullish FVG)

```python
# Two bars close into bullish zone: 1.0865, then 1.0850
zone = update_fvg_fills(zone, two_bar_sequence)
assert zone.fill_low == 1.0850  # lowest, not first
```

### TB.4 — Full fill triggers invalidation (bullish FVG)

```python
# Zone: zone_low=1.0840
# Bar closes at 1.0838 (at or below zone_low)

zone = update_fvg_fills(zone_partially_filled, full_fill_bars)
assert zone.status == "invalidated"
assert zone.full_fill_time is not None
```

### TB.5 — Price blowthrough fires partial then full on same bar

```python
# Zone: open status, zone_low=1.0840, zone_high=1.0882
# Single bar: close=1.0835 (blows through entire zone)

zone = update_fvg_fills(open_zone, blowthrough_bar)
assert zone.status == "invalidated"
assert zone.partial_fill_time is not None  # must have fired
assert zone.full_fill_time is not None
assert zone.partial_fill_time == zone.full_fill_time  # same bar
```

### TB.6 — No fill processing on invalidated zone

```python
invalidated_zone = zone_with_status("invalidated")
result = update_fvg_fills(invalidated_zone, more_bars)
assert result.status == "invalidated"
assert result.full_fill_time == invalidated_zone.full_fill_time  # unchanged
```

---

## Group C — Zone lifecycle

### TC.1 — Only allowed transitions occur

```python
ALLOWED = {
    "open": {"partially_filled"},
    "partially_filled": {"invalidated"},
    "invalidated": {"archived"},
}
# For every zone in packet, verify all observed transitions are in ALLOWED
```

### TC.2 — Reruns do not alter invalidated zones

```python
zone_run1 = run_and_get_zone("fvg_001", bars)
zone_run2 = run_and_get_zone("fvg_001", bars)
assert zone_run1.status == zone_run2.status == "invalidated"
assert zone_run1.full_fill_time == zone_run2.full_fill_time
```

### TC.3 — Open zones remain open when price does not enter

```python
# Zone exists but subsequent bars close outside the zone
zone = update_fvg_fills(open_zone, bars_outside_zone)
assert zone.status == "open"
assert zone.first_touch_time is None
```

### TC.4 — Partially filled zones resolve correctly when new bars arrive

```python
# Day 1: zone is partially_filled
# Day 2: price closes through opposite edge → invalidated

zone_day1 = run_and_get_zone("fvg_002", bars_day1)
assert zone_day1.status == "partially_filled"

zone_day2 = run_and_get_zone("fvg_002", bars_day1_plus_day2)
assert zone_day2.status == "invalidated"
```

---

## Group D — Active zone registry

### TD.1 — Active registry contains only open and partially_filled zones

```python
packet = run_engine("EURUSD", "1h", bars)
active_ids = {z["id"] for z in packet["active_zones"]["zones"]}
all_zones = {z["id"]: z for z in packet["imbalance"]}

for zone_id in active_ids:
    assert all_zones[zone_id]["status"] in ("open", "partially_filled")
```

### TD.2 — Invalidated zones not in active registry

```python
invalidated_ids = {z["id"] for z in packet["imbalance"]
                   if z["status"] == "invalidated"}
active_ids = {z["id"] for z in packet["active_zones"]["zones"]}

assert invalidated_ids.isdisjoint(active_ids)
```

### TD.3 — Active zone count matches registry count field

```python
assert packet["active_zones"]["count"] == len(packet["active_zones"]["zones"])
```

### TD.4 — Registry updates correctly after new bar invalidates a zone

```python
active_before = {z["id"] for z in run_engine("EURUSD","1h",bars_day1)["active_zones"]["zones"]}
active_after  = {z["id"] for z in run_engine("EURUSD","1h",bars_day1_plus_day2)["active_zones"]["zones"]}

# Any zone that was invalidated in day 2 must no longer be in active
for zone_id in (active_before - active_after):
    zone = get_zone_by_id(run_engine("EURUSD","1h",bars_day1_plus_day2), zone_id)
    assert zone["status"] == "invalidated"
```

---

## Group E — Determinism and replay stability

### TE.1 — Identical inputs produce identical packets

```python
import json, hashlib

def packet_hash(instrument, timeframe, bars):
    packet = run_engine(instrument, timeframe, bars)
    return hashlib.md5(json.dumps(packet, sort_keys=True).encode()).hexdigest()

assert packet_hash("EURUSD", "1h", fixture_bars) == packet_hash("EURUSD", "1h", fixture_bars)
```

### TE.2 — Reruns do not mutate resolved zones

```python
packet_a = run_engine("EURUSD", "1h", bars)
packet_b = run_engine("EURUSD", "1h", bars)

resolved_a = [z for z in packet_a["imbalance"] if z["status"] == "invalidated"]
resolved_b = [z for z in packet_b["imbalance"] if z["status"] == "invalidated"]
assert resolved_a == resolved_b
```

### TE.3 — Appending bars only adds or advances, never rewrites

```python
zones_day1 = {z["id"]: z for z in run_engine("EURUSD","1h",bars_day1)["imbalance"]}
zones_day2 = {z["id"]: z for z in run_engine("EURUSD","1h",bars_day1_plus_day2)["imbalance"]}

for zone_id, zone in zones_day1.items():
    if zone["status"] == "invalidated":
        # Must still be invalidated after day 2
        assert zones_day2[zone_id]["status"] == "invalidated"
        assert zones_day2[zone_id]["full_fill_time"] == zone["full_fill_time"]
```

---

## Group F — Cross-instrument coverage

### TF.1 — EURUSD passes all Groups A–E

```bash
pytest market_data_officer/tests/test_structure_eurusd.py -k "3c"
```

### TF.2 — XAUUSD passes all Groups A–E

```bash
pytest market_data_officer/tests/test_structure_xauusd.py -k "3c"
```

### TF.3 — XAUUSD uses its own minimum gap size

```python
eurusd_config = get_config("EURUSD")
xauusd_config = get_config("XAUUSD")
assert eurusd_config.fvg_min_size != xauusd_config.fvg_min_size
assert xauusd_config.fvg_min_size == pytest.approx(0.30)
```

### TF.4 — XAUUSD FVG prices are in plausible gold range

```python
for zone in xauusd_packet["imbalance"]:
    assert 1_500.0 < zone["zone_low"] < 3_500.0
    assert 1_500.0 < zone["zone_high"] < 3_500.0
```

---

## Group G — Output and boundaries

### TG.1 — Packet contains `imbalance` and `active_zones` keys

```python
packet = run_engine("EURUSD", "1h", bars)
assert "imbalance" in packet
assert "active_zones" in packet
assert "count" in packet["active_zones"]
assert "zones" in packet["active_zones"]
```

### TG.2 — All FVG objects have required fields

```python
required = {
    "id", "fvg_type", "zone_high", "zone_low", "zone_size",
    "origin_time", "confirm_time", "timeframe", "status",
    "fill_high", "fill_low",
    "first_touch_time", "partial_fill_time", "full_fill_time"
}
for zone in packet["imbalance"]:
    assert required.issubset(zone.keys()), f"Missing fields in {zone['id']}"
```

### TG.3 — CLI runs end-to-end for both instruments

```bash
python run_structure.py --instrument EURUSD
python run_structure.py --instrument XAUUSD
```

### TG.4 — Officer and feed untouched

```bash
git diff --name-only HEAD | grep -E "officer/|feed/"
# Must return no output
```

### TG.5 — `engine_version` is `phase_3c` in all output packets

```python
for instrument in ["EURUSD", "XAUUSD"]:
    for tf in ["15m", "1h", "4h"]:
        with open(f"structure/output/{instrument.lower()}_{tf}_structure.json") as f:
            p = json.load(f)
        assert p["build"]["engine_version"] == "phase_3c"
```

---

## Phase 3C sign-off checklist

- [ ] Group 0 — Full 3A + 3B regression: 0 failures
- [ ] Group A — FVG detection: all pass
- [ ] Group B — Fill progression: all pass
- [ ] Group C — Zone lifecycle: all pass
- [ ] Group D — Active zone registry: all pass
- [ ] Group E — Determinism and replay stability: all pass
- [ ] Group F — EURUSD + XAUUSD cross-instrument: all pass
- [ ] Group G — Output and boundaries: all pass
- [ ] `fvg_use_body_only` is `True` in StructureConfig
- [ ] `engine_version` updated to `phase_3c` in all packets
- [ ] No Officer or feed files modified
- [ ] No wick-inclusive logic, no 50% threshold, no config-selectable invalidation
- [ ] Blowthrough fires partial then full in sequence on same bar
- [ ] Active registry contains only `open` and `partially_filled` zones
