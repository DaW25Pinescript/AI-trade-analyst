# CONSTRAINTS.md — Phase 3D Hard Rules

## Non-negotiable rules

### RULE 1 — Officer reads structure via reader API only

The Officer must call `structure/reader.py` functions. It must not:
- Read structure JSON files via hardcoded `open()` paths
- Import from `structure/engine.py` directly
- Call `run_engine()` or any structure computation function

```python
# Correct
from structure.reader import load_structure_summary, structure_is_available

# Wrong
import json
with open("structure/output/eurusd_1h_structure.json") as f:  # hardcoded path
    packet = json.load(f)
```

### RULE 2 — Officer never crashes on missing structure

If structure packets are unavailable, stale, or corrupt:
- Return `StructureBlock.unavailable()`
- Set `structure.available = False`
- All sub-fields `None`
- Continue assembling the rest of the v2 packet normally

```python
# Correct
if not structure_is_available(instrument):
    structure_block = StructureBlock.unavailable()
else:
    structure_block = assemble_structure_block(instrument)
```

### RULE 3 — All v1 fields preserved unchanged in v2

`MarketPacketV2.to_dict()` must produce all fields that `MarketPacketV1.to_dict()` produced. No v1 field may be renamed, removed, or moved.

The only changes from v1 to v2:
- `schema_version` changes from `"market_packet_v1"` to `"market_packet_v2"`
- `structure` top-level key is added

### RULE 4 — Feed pipeline untouched

No modifications to `market_data_officer/feed/`.

```bash
git diff --name-only HEAD | grep "feed/"
# Must return no output
```

### RULE 5 — Structure engine modules untouched

No modifications to `structure/swings.py`, `structure/events.py`, `structure/liquidity.py`, `structure/imbalance.py`, `structure/regime.py`, `structure/engine.py`, `structure/io.py`, `structure/schemas.py`, or `structure/config.py`.

The only permitted structure module addition is `structure/reader.py`.

```bash
git diff --name-only HEAD | grep "structure/" | grep -v "reader.py"
# Must return no output
```

### RULE 6 — `recent_events` is capped at 5

Never include more than 5 events in `structure.recent_events`. The reader must enforce this cap regardless of how many events exist in the structure packets.

### RULE 7 — `active_fvg_zones` contains only open and partially_filled

```python
assert all(z["status"] in ("open", "partially_filled")
           for z in packet["structure"]["active_fvg_zones"])
```

### RULE 8 — `schema_version` must be `market_packet_v2`

```python
assert packet["schema_version"] == "market_packet_v2"
```

### RULE 9 — `has_structure()` is reliable

`MarketPacketV2.has_structure()` must return `True` if and only if `structure.available` is `True` and at least one structure sub-field is non-null.

### RULE 10 — Regime source timeframe preference

When assembling `structure.regime`, prefer 4h regime if available. Fall back to 1h, then 15m. Document the source in `regime.source_timeframe`.

```python
for preferred_tf in ("4h", "1h", "15m"):
    if preferred_tf in packets and packets[preferred_tf]:
        regime = packets[preferred_tf].get("regime")
        if regime:
            regime["source_timeframe"] = preferred_tf
            return regime
```

---

## Module boundary summary

| Module | Permitted to call | Must not call |
|---|---|---|
| `officer/service.py` | `structure/reader.py` | `structure/engine.py`, feed modules |
| `structure/reader.py` | `pathlib`, `json` | `structure/engine.py`, Officer modules |
| `officer/contracts.py` | stdlib only | any external module |
| `structure/engine.py` | unchanged | Officer modules |

---

## Common failure modes to avoid

| Failure | Guard |
|---|---|
| Crash when structure JSON missing | `load_structure_packet` returns `None`, never raises |
| v1 field renamed in v2 serialization | Test v1 field presence explicitly in Group C |
| Stale structure silently treated as fresh | `_is_fresh()` check in `structure_is_available()` |
| `active_fvg_zones` including invalidated zones | Filter on `status in {"open", "partially_filled"}` |
| `recent_events` exceeding 5 | Cap with `[:5]` slice after sort |
| Regime from wrong timeframe | Enforce 4h → 1h → 15m preference order |
| `has_structure()` returning True with null sub-fields | Check `available` AND at least one non-null sub-field |
