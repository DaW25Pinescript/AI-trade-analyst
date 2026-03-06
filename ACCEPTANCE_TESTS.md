# ACCEPTANCE_TESTS.md — Phase 3B Exit Criteria

## How to use this file

Run Group 0 first (3A regression). If anything fails there, stop — do not proceed to 3B tests until 3A is clean. Then run Groups A through G. Report pass/fail per group before declaring Phase 3B complete.

---

## Group 0 — Phase 3A full regression (run first)

### T0.1 — All 3A test files pass

```bash
pytest market_data_officer/tests/test_structure_swings.py
pytest market_data_officer/tests/test_structure_events.py
pytest market_data_officer/tests/test_structure_liquidity.py
pytest market_data_officer/tests/test_structure_regime.py
pytest market_data_officer/tests/test_structure_replay.py
pytest market_data_officer/tests/test_structure_eurusd.py
pytest market_data_officer/tests/test_structure_xauusd.py
# All must pass — 48/48
```

### T0.2 — Engine version updated in packet output

```python
import json
with open("structure/output/eurusd_1h_structure.json") as f:
    packet = json.load(f)
assert packet["build"]["engine_version"] == "phase_3b"
```

---

## Group A — Reclaim detection

### TA.1 — High-side reclaim confirmed when close returns below level

```python
# Fixture: prior_day_high at 1.08720
# Sweep bar: high = 1.08731, close = 1.08740 (close above — no same-bar reclaim)
# Next bar: close = 1.08695 (close below level — reclaim confirmed)

level = get_level("liq_001")
assert level.outcome == "reclaimed"
assert level.reclaim_time == next_bar_timestamp
assert level.status == "reclaimed"
```

### TA.2 — Low-side reclaim confirmed when close returns above level

```python
# Fixture: prior_day_low at 1.07500
# Sweep bar: low = 1.07488, close = 1.07470 (close below — no same-bar reclaim)
# Next bar: close = 1.07530 (close above level — reclaim confirmed)

level = get_level("liq_002")
assert level.outcome == "reclaimed"
assert level.reclaim_time == next_bar_timestamp
```

### TA.3 — Same-bar reclaim when enabled

```python
# Fixture: prior_day_high at 1.08720
# Sweep bar: high = 1.08731, close = 1.08690 (same bar closes below level)
# allow_same_bar_reclaim = True

level = get_level("liq_003")
assert level.outcome == "reclaimed"
assert level.reclaim_time == sweep_bar_timestamp
```

### TA.4 — Same-bar reclaim blocked when disabled

```python
# Same fixture but allow_same_bar_reclaim = False
# Sweep bar closes below level — should NOT count as reclaim on sweep bar itself
# Next bar closes above level — outcome depends on next bar only

config = StructureConfig(allow_same_bar_reclaim=False, reclaim_window_bars=1)
# Run engine
level = get_level("liq_003")
# Same-bar reclaim must not have fired
assert level.reclaim_time != sweep_bar_timestamp
```

### TA.5 — No false reclaim when wick crosses but close does not

```python
# Fixture: prior_day_high at 1.08720
# Sweep bar: high = 1.08731, close = 1.08750 (close above)
# Next bar: high = 1.08700 (wick below), close = 1.08730 (close above level)

level = get_level("liq_004")
# Wick crossed but close did not — must NOT be reclaimed
assert level.outcome != "reclaimed"
```

### TA.6 — `accepted_beyond` after window exhausted

```python
# Fixture: prior_day_high at 1.08720
# Sweep bar: high = 1.08731, close = 1.08740
# Next bar: close = 1.08738 (still above — window exhausted)
# reclaim_window_bars = 1

level = get_level("liq_005")
assert level.outcome == "accepted_beyond"
assert level.reclaim_time is None
```

### TA.7 — `unresolved` when window not yet closed

```python
# Fixture: sweep detected but only sweep bar exists — no subsequent bars yet

level = get_level("liq_006")
assert level.outcome == "unresolved"
assert level.reclaim_time is None
```

---

## Group B — Post-sweep classification

### TB.1 — Classification is mutually exclusive

```python
# For any swept level, outcome must be exactly one of:
assert level.outcome in ("reclaimed", "accepted_beyond", "unresolved")
```

### TB.2 — SweepEvent outcome mirrors LiquidityLevel outcome

```python
sweep = get_sweep_event("sw_ev_001")
level = get_level(sweep.linked_liquidity_id)
assert sweep.outcome == level.outcome
assert sweep.reclaim_time == level.reclaim_time
```

### TB.3 — `post_sweep_close` is populated after resolution

```python
# For reclaimed or accepted_beyond outcome:
sweep = get_sweep_event("sw_ev_001")
assert sweep.outcome in ("reclaimed", "accepted_beyond")
assert sweep.post_sweep_close is not None
assert isinstance(sweep.post_sweep_close, float)
```

### TB.4 — `post_sweep_close` is null while unresolved

```python
sweep = get_unresolved_sweep()
assert sweep.outcome == "unresolved"
assert sweep.post_sweep_close is None
```

### TB.5 — Classification timing is deterministic

```python
# Run engine twice on identical bar set
outcome_a = run_engine_get_outcome("liq_001")
outcome_b = run_engine_get_outcome("liq_001")
assert outcome_a == outcome_b
```

---

## Group C — Liquidity lifecycle

### TC.1 — Levels only transition through allowed states

```python
ALLOWED_TRANSITIONS = {
    "active": {"swept", "invalidated"},
    "swept": {"reclaimed", "accepted_beyond"},
    "reclaimed": {"archived"},
    "accepted_beyond": {"archived"},
    "invalidated": {"archived"},
}

# For every level in packet, verify all observed transitions are in ALLOWED_TRANSITIONS
```

### TC.2 — Reruns do not create backward transitions

```python
# Run engine on day 1 — level is reclaimed
# Run engine again on same bars
# Level must still be reclaimed, not reset to swept or active

first_run_outcome = run_and_get_outcome("liq_001", bars_day1)
second_run_outcome = run_and_get_outcome("liq_001", bars_day1)
assert first_run_outcome == second_run_outcome == "reclaimed"
```

### TC.3 — Historical resolved levels not mutated on new bar append

```python
# Run engine through day 1 — liq_001 is accepted_beyond
# Append day 2 bars — liq_001 must remain accepted_beyond

outcome_before = run_and_get_outcome("liq_001", bars_day1)
outcome_after = run_and_get_outcome("liq_001", bars_day1_plus_day2)
assert outcome_before == outcome_after == "accepted_beyond"
```

### TC.4 — Unresolved levels resolve correctly as new bars arrive

```python
# Day 1: sweep detected, no subsequent bars — outcome is unresolved
# Day 2: subsequent bar closes back below level — outcome becomes reclaimed

outcome_day1 = run_and_get_outcome("liq_007", bars_day1)
assert outcome_day1 == "unresolved"

outcome_day2 = run_and_get_outcome("liq_007", bars_day1_plus_day2)
assert outcome_day2 == "reclaimed"
```

---

## Group D — Internal/external tagging

### TD.1 — Prior day/week levels tagged as external

```python
for level in packet["liquidity"]:
    if level["type"] in ("prior_day_high", "prior_day_low",
                          "prior_week_high", "prior_week_low"):
        assert level["liquidity_scope"] == "external_liquidity", \
            f"{level['id']} should be external_liquidity"
```

### TD.2 — EQH above most recent swing high tagged as external

```python
# Fixture: confirmed swing_high at 1.08500
# EQH cluster at 1.08720 (above swing high)

eqh_level = get_level_by_type("equal_highs")
assert eqh_level["liquidity_scope"] == "external_liquidity"
```

### TD.3 — EQH below most recent swing high tagged as internal

```python
# Fixture: confirmed swing_high at 1.09000
# EQH cluster at 1.08720 (below swing high)

eqh_level = get_level_by_type("equal_highs")
assert eqh_level["liquidity_scope"] == "internal_liquidity"
```

### TD.4 — EQH/EQL without relevant confirmed swing tagged as unclassified

```python
# Fixture: EQH exists but no confirmed swing_high in the timeframe window

eqh_level = get_level_by_type("equal_highs")
assert eqh_level["liquidity_scope"] == "unclassified"
```

### TD.5 — `liquidity_scope` is set at creation time, not post-sweep

```python
# Level should have liquidity_scope populated before any sweep occurs
active_level = get_active_level("liq_010")
assert active_level["liquidity_scope"] is not None
assert active_level["status"] == "active"
```

---

## Group E — Determinism and replay stability

### TE.1 — Identical inputs produce identical packets

```python
import json, hashlib

def packet_hash(instrument, timeframe, bars):
    packet = run_engine(instrument, timeframe, bars)
    return hashlib.md5(json.dumps(packet, sort_keys=True).encode()).hexdigest()

hash_a = packet_hash("EURUSD", "1h", fixture_bars)
hash_b = packet_hash("EURUSD", "1h", fixture_bars)
assert hash_a == hash_b
```

### TE.2 — Reruns on unchanged bars produce no changes to resolved objects

```python
packet_run1 = run_engine("EURUSD", "1h", bars)
packet_run2 = run_engine("EURUSD", "1h", bars)

resolved_run1 = [l for l in packet_run1["liquidity"] if l["outcome"] != "unresolved"]
resolved_run2 = [l for l in packet_run2["liquidity"] if l["outcome"] != "unresolved"]

assert resolved_run1 == resolved_run2
```

### TE.3 — Appending new bars only resolves unresolved outcomes, not rewrites resolved

```python
unresolved_before = [l["id"] for l in packet_day1["liquidity"] if l["outcome"] == "unresolved"]
packet_day2 = run_engine("EURUSD", "1h", bars_day1_plus_day2)

for level_id in unresolved_before:
    level_after = get_level_by_id(packet_day2, level_id)
    # Outcome may now be resolved — that is correct
    # But previously resolved levels must not have changed
```

---

## Group F — Cross-instrument coverage

### TF.1 — EURUSD passes all Groups A–E

```bash
pytest market_data_officer/tests/test_structure_eurusd.py -k "3b"
# All pass
```

### TF.2 — XAUUSD passes all Groups A–E

```bash
pytest market_data_officer/tests/test_structure_xauusd.py -k "3b"
# All pass
```

### TF.3 — XAUUSD uses its own tolerance, not EURUSD tolerance

```python
eurusd_config = get_config("EURUSD")
xauusd_config = get_config("XAUUSD")
assert eurusd_config.eqh_eql_tolerance != xauusd_config.eqh_eql_tolerance
```

---

## Group G — Output and boundaries

### TG.1 — JSON packets are schema-complete

```python
required_liquidity_fields = {
    "id", "type", "price", "origin_time", "timeframe", "status",
    "swept_time",
    "liquidity_scope", "outcome", "reclaim_time", "reclaim_window_bars"
}

required_sweep_fields = {
    "id", "type", "time", "timeframe", "sweep_price", "linked_liquidity_id",
    "post_sweep_close", "reclaim_time", "outcome", "reclaim_window_bars"
}

for level in packet["liquidity"]:
    assert required_liquidity_fields.issubset(level.keys())

for sweep in packet["events"]:
    if sweep["type"] in ("sweep_high", "sweep_low"):
        assert required_sweep_fields.issubset(sweep.keys())
```

### TG.2 — CLI runs end-to-end for both instruments

```bash
python run_structure.py --instrument EURUSD
python run_structure.py --instrument XAUUSD
# Both must complete without exception
```

### TG.3 — Officer and feed modules untouched

```bash
git diff --name-only HEAD | grep -E "officer/|feed/"
# Must return no output
```

### TG.4 — `engine_version` is `phase_3b` in all output packets

```python
for instrument in ["EURUSD", "XAUUSD"]:
    for tf in ["15m", "1h", "4h"]:
        with open(f"structure/output/{instrument.lower()}_{tf}_structure.json") as f:
            packet = json.load(f)
        assert packet["build"]["engine_version"] == "phase_3b"
```

---

## Phase 3B sign-off checklist

- [ ] Group 0 — 3A regression: 48/48 pass
- [ ] Group A — Reclaim detection: all pass
- [ ] Group B — Post-sweep classification: all pass
- [ ] Group C — Liquidity lifecycle: all pass
- [ ] Group D — Internal/external tagging: all pass
- [ ] Group E — Determinism and replay stability: all pass
- [ ] Group F — EURUSD + XAUUSD cross-instrument: all pass
- [ ] Group G — Output and boundaries: all pass
- [ ] `engine_version` updated to `phase_3b` in all packets
- [ ] No Officer or feed files modified
- [ ] Both `allow_same_bar_reclaim` and `reclaim_window_bars` present in StructureConfig
- [ ] No ATR-scaled parameters, wick BOS mode, or FVG logic introduced
- [ ] JSON packets pretty-printed, UTF-8, atomically written
