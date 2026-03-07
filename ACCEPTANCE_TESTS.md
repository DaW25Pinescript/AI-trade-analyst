# ACCEPTANCE_TESTS.md — Phase 3D Exit Criteria

## How to use this file

Run Group 0 first. Any failure there stops all further work. Then Groups A through G. Report pass/fail per group before declaring Phase 3D complete.

---

## Group 0 — Full regression (all prior phases)

### T0.1 — All structure engine tests pass

```bash
pytest market_data_officer/tests/test_structure_swings.py
pytest market_data_officer/tests/test_structure_events.py
pytest market_data_officer/tests/test_structure_liquidity.py
pytest market_data_officer/tests/test_structure_regime.py
pytest market_data_officer/tests/test_structure_replay.py
pytest market_data_officer/tests/test_structure_imbalance.py
pytest market_data_officer/tests/test_structure_eurusd.py
pytest market_data_officer/tests/test_structure_xauusd.py
# All must pass — 0 failures
```

### T0.2 — All Phase 2 Officer tests pass

```bash
pytest market_data_officer/tests/test_loader.py
pytest market_data_officer/tests/test_features.py
pytest market_data_officer/tests/test_summarizer.py
pytest market_data_officer/tests/test_quality.py
pytest market_data_officer/tests/test_contracts.py
# All must pass — 0 failures
```

### T0.3 — Feed pipeline and structure engine modules untouched

This check guards the feed pipeline and existing structure engine modules only.
Officer files (`officer/`), tests (`tests/`), and the new `structure/reader.py` are
all legitimately modified in 3D — do not include them in this check.

```bash
git diff --name-only HEAD | grep "feed/"
# Must return no output — feed pipeline is never touched

git diff --name-only HEAD | grep "structure/" \
  | grep -v "reader.py"
# Must return no output — only reader.py is a permitted addition to structure/
```

---

## Group A — Structure reader API

### TA.1 — `load_structure_packet` returns dict for existing packet

```python
from structure.reader import load_structure_packet

packet = load_structure_packet("EURUSD", "1h")
assert packet is not None
assert isinstance(packet, dict)
assert "instrument" in packet
assert "regime" in packet
```

### TA.2 — `load_structure_packet` returns None for missing instrument

```python
result = load_structure_packet("FAKEINSTRUMENT", "1h")
assert result is None
```

### TA.3 — `load_structure_packet` returns None for missing timeframe

```python
result = load_structure_packet("EURUSD", "1d")  # 1d not an active structure TF
assert result is None
```

### TA.4 — `load_structure_packet` returns None for corrupt JSON, not exception

```python
# Write a corrupt JSON file to the structure output path
# Then call load_structure_packet
result = load_structure_packet("EURUSD", "1h")
assert result is None  # graceful, not exception
```

### TA.5 — `structure_is_available` returns True when fresh packets exist

```python
from structure.reader import structure_is_available
assert structure_is_available("EURUSD") is True
```

### TA.6 — `structure_is_available` returns False when no packets exist

```python
assert structure_is_available("FAKEINSTRUMENT") is False
```

### TA.7 — Reader does not import or call structure engine modules

```bash
grep -n "from structure.engine\|import engine\|run_engine" \
  market_data_officer/structure/reader.py
# Must return no matches
```

---

## Group B — StructureBlock assembly

### TB.1 — StructureBlock.unavailable() produces correct shape

```python
from officer.contracts import StructureBlock

block = StructureBlock.unavailable()
assert block.available is False
assert block.source_engine_version is None
assert block.regime is None
assert block.recent_events is None
assert block.liquidity is None
assert block.active_fvg_zones is None
```

### TB.2 — Available StructureBlock has all fields populated

```python
block = assemble_structure_block("EURUSD")
assert block.available is True
assert block.source_engine_version is not None
assert block.regime is not None
assert block.recent_events is not None
assert block.liquidity is not None
assert block.active_fvg_zones is not None
```

### TB.3 — `recent_events` capped at 5

```python
block = assemble_structure_block("EURUSD")
assert len(block.recent_events) <= 5
```

### TB.4 — `recent_events` sorted time descending

```python
times = [e.time for e in block.recent_events]
assert times == sorted(times, reverse=True)
```

### TB.5 — `active_fvg_zones` contains only open and partially_filled

```python
for zone in block.active_fvg_zones:
    assert zone.status in ("open", "partially_filled")
```

### TB.6 — Regime source timeframe follows 4h → 1h → 15m preference

```python
# When 4h packet exists
assert block.regime.source_timeframe == "4h"

# When only 1h exists (simulate missing 4h)
block_no_4h = assemble_structure_block("EURUSD", available_timeframes=["15m", "1h"])
assert block_no_4h.regime.source_timeframe == "1h"
```

### TB.7 — Liquidity summary has nearest_above and nearest_below per timeframe

```python
current_price = 1.0842
block = assemble_structure_block("EURUSD", current_price=current_price)

for tf, summary in block.liquidity.items():
    if summary.nearest_above:
        assert summary.nearest_above.price > current_price
    if summary.nearest_below:
        assert summary.nearest_below.price < current_price
```

---

## Group C — Market Packet v2 schema

### TC.1 — `schema_version` is `market_packet_v2`

```python
from officer.service import build_market_packet

packet = build_market_packet("EURUSD")
d = packet.to_dict()
assert d["schema_version"] == "market_packet_v2"
```

### TC.2 — All v1 fields present in v2

```python
v1_required_keys = {
    "instrument", "as_of_utc", "source",
    "timeframes", "features", "state_summary", "quality"
}
assert v1_required_keys.issubset(d.keys())
```

### TC.3 — `structure` is a top-level key

```python
assert "structure" in d
assert "available" in d["structure"]
```

### TC.4 — v2 serializes to valid JSON

```python
import json
json_str = json.dumps(packet.to_dict())  # must not raise
assert len(json_str) > 100
```

### TC.5 — `has_structure()` returns True when structure is available

```python
assert packet.has_structure() is True
```

### TC.6 — `is_trusted()` still works on v2 packet

```python
assert packet.is_trusted() is True
```

---

## Group D — Graceful degradation

### TD.1 — Packet builds successfully when no structure packets exist

```python
# Simulate: rename structure output directory temporarily
packet = build_market_packet("EURUSD")
d = packet.to_dict()

assert d["schema_version"] == "market_packet_v2"
assert d["structure"]["available"] is False
assert d["structure"]["regime"] is None
assert d["structure"]["active_fvg_zones"] is None
```

### TD.2 — `has_structure()` returns False when unavailable

```python
# Same simulation as TD.1
assert packet.has_structure() is False
```

### TD.3 — Feed features and state summary still populated when structure missing

```python
# With structure unavailable:
assert d["features"]["core"]["atr_14"] > 0
assert d["state_summary"]["trend_1h"] in ("bullish", "bearish", "neutral")
assert d["quality"]["manifest_valid"] is True
```

### TD.4 — Stale structure packets treated as unavailable

```python
# Simulate: set structure packet as_of to 3 hours ago
# structure_is_available() must return False
# structure block must have available=False
```

---

## Group E — Determinism

### TE.1 — Identical inputs produce identical v2 packets

```python
import json, hashlib

def packet_hash(instrument):
    p = build_market_packet(instrument)
    return hashlib.md5(
        json.dumps(p.to_dict(), sort_keys=True).encode()
    ).hexdigest()

assert packet_hash("EURUSD") == packet_hash("EURUSD")
```

### TE.2 — `active_fvg_zones` order is deterministic

```python
zones_a = build_market_packet("EURUSD").to_dict()["structure"]["active_fvg_zones"]
zones_b = build_market_packet("EURUSD").to_dict()["structure"]["active_fvg_zones"]
assert [z["id"] for z in zones_a] == [z["id"] for z in zones_b]
```

---

## Group F — Cross-instrument coverage

### TF.1 — EURUSD v2 packet builds and passes all groups

```bash
pytest market_data_officer/tests/test_officer_v2.py -k "eurusd"
```

### TF.2 — XAUUSD v2 packet builds and passes all groups

```bash
pytest market_data_officer/tests/test_officer_v2.py -k "xauusd"
```

### TF.3 — XAUUSD active FVG prices are in plausible range

```python
xauusd_packet = build_market_packet("XAUUSD").to_dict()
for zone in xauusd_packet["structure"]["active_fvg_zones"]:
    assert 1_500.0 < zone["zone_low"] < 3_500.0
    assert 1_500.0 < zone["zone_high"] < 3_500.0
```

---

## Group G — Output and boundaries

### TG.1 — v2 packet written to correct path

```python
import os
assert os.path.exists("market_data_officer/state/packets/EURUSD_market_packet.json")

with open("market_data_officer/state/packets/EURUSD_market_packet.json") as f:
    saved = json.load(f)
assert saved["schema_version"] == "market_packet_v2"
```

### TG.2 — CLI runs end-to-end for both instruments

```bash
python run_officer.py --instrument EURUSD
python run_officer.py --instrument XAUUSD
# Both must complete without exception
```

### TG.3 — Feed pipeline untouched (final check)

```bash
git diff --name-only HEAD | grep "feed/"
# Must return no output
```

### TG.4 — Structure engine modules untouched (final check)

```bash
git diff --name-only HEAD | grep "structure/" | grep -v "reader.py"
# Must return no output
```

### TG.5 — `run_officer.py --help` works

```bash
python run_officer.py --help
# Must exit 0
```

---

## Phase 3D sign-off checklist

- [ ] Group 0 — Full regression (all prior phases): 0 failures
- [ ] Group A — Structure reader API: all pass
- [ ] Group B — StructureBlock assembly: all pass
- [ ] Group C — Market Packet v2 schema: all pass
- [ ] Group D — Graceful degradation: all pass
- [ ] Group E — Determinism: all pass
- [ ] Group F — Cross-instrument coverage: all pass
- [ ] Group G — Output and boundaries: all pass
- [ ] `schema_version` is `market_packet_v2` in all Officer output
- [ ] All v1 fields preserved and unchanged
- [ ] `structure` is top-level key with correct shape
- [ ] `StructureBlock.unavailable()` factory works correctly
- [ ] `has_structure()` reliable in both available and unavailable states
- [ ] No hardcoded structure JSON file paths in Officer modules
- [ ] Feed pipeline files: 0 modifications
- [ ] Structure engine files: 0 modifications (reader.py only new file)
- [ ] ARCHITECTURE.md committed to repo root
