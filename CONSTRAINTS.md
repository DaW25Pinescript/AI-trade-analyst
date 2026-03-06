# CONSTRAINTS.md — Hard Rules, Module Boundaries, Failure Handling

## Non-negotiable rules

---

### RULE 1 — The Officer does not fetch, decode, or write canonical data

The Officer is a **read layer only**. It must not:
- Make HTTP requests to Dukascopy or any vendor
- Decompress bi5 files
- Write to `market_data/canonical/`
- Write to `market_data/derived/`
- Call any function in `feed/fetch.py`, `feed/decode.py`, or `feed/pipeline.py`

If the feed hasn't run, the Officer should detect that via missing manifests and degrade gracefully — not attempt to fill the gap itself.

---

### RULE 2 — Read from hot packages, not raw Parquet

The Officer reads from `market_data/packages/latest/` only.

It must not read `market_data/canonical/EURUSD_1m.parquet` directly. Hot packages are the contract surface between feed and Officer. Raw Parquet is the feed's internal truth, not the Officer's input.

```python
# Correct
loader.load_hot_package("EURUSD", "1h")

# Wrong
pd.read_parquet("market_data/canonical/EURUSD_1m.parquet")
```

---

### RULE 3 — Validate before building

The Officer must run `quality.py` checks before assembling any packet. If validation fails:

- Set `quality.partial = True` or `quality.stale = True`
- Populate `quality.flags` with specific failure reasons
- Set `state_summary.data_quality` to `"partial"` or `"stale"`
- Still return a packet (do not crash)
- Log warnings for every flag raised

Never silently continue past a quality failure.

---

### RULE 4 — Features are computed from loaded DataFrames, not re-fetched data

All feature computation happens on the DataFrames already loaded from hot packages. Features must not trigger additional file reads, HTTP calls, or feed pipeline runs.

---

### RULE 5 — Advanced feature stubs return None, not partial logic

The structure stubs in `officer/structure/` must:

```python
def detect_bos(df: pd.DataFrame) -> None:
    """
    Phase 3: Detect Break of Structure events.
    Will require: pivot detection rules, break confirmation logic,
    close vs wick interpretation, timeframe interaction model.
    Not implemented in Phase 2.
    """
    return None
```

Do not implement partial BOS, FVG, or compression logic. Partial implementations are worse than explicit stubs because they create false confidence. Return `None`. Reserve the field in the packet. Move on.

---

### RULE 6 — Market Packet schema is fixed at v1

The packet schema defined in `CONTRACTS.md` is the contract. Do not add, remove, or rename fields during Phase 2 implementation without explicit instruction.

Fields present: `instrument`, `as_of_utc`, `source`, `timeframes`, `features`, `state_summary`, `quality`.

Feature sub-keys present: `core`, `structure`, `imbalance`, `compression`.

All four feature keys must always be present, even if value is `null`.

---

### RULE 7 — UTC everywhere

All timestamps in the packet must be UTC-aware ISO8601 strings.

```python
# Correct
"as_of_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# Wrong
"as_of_utc": datetime.utcnow().isoformat()
```

---

### RULE 8 — Instrument policy must be enforced

Only emit `quality: "validated"` for instruments that have passed Phase 1A/1B verification.

Current trusted list: `EURUSD`
Current provisional list: `XAUUSD` (until Phase 1B sign-off)

If an unverified instrument is requested, set quality to `"unverified"` and add flag `"instrument_not_verified"`. Do not crash. Do not silently emit validated quality for unverified instruments.

---

## Module boundary map

| Module | Owns | Must not touch |
|---|---|---|
| `loader.py` | Read hot CSVs, parse manifest, return DataFrames | feed pipeline, raw Parquet, vendor fetch |
| `features.py` | Compute core features from loaded DataFrames | file I/O, HTTP, feed internals |
| `summarizer.py` | Build StateSummary from features + timeframe DFs | raw bar calculations |
| `quality.py` | Read-side sanity checks, staleness, manifest validation | feature computation |
| `contracts.py` | Dataclass definitions, `to_dict()`, `is_trusted()` | computation logic |
| `service.py` | Orchestrate loader → quality → features → summarizer → packet | implement any of the above directly |
| `structure/*.py` | Stubs only, return None | any real logic |

---

## Failure mode handling

### Stale package

Staleness threshold: 60 minutes during assumed market hours.

```python
staleness_minutes = (now_utc - last_bar_utc).total_seconds() / 60
stale = staleness_minutes > 60
```

Emit packet with `quality.stale = True`, `data_quality = "stale"`.

### Partial package

One or more timeframe CSVs missing but manifest exists.

Emit packet with available timeframes only. Set `quality.partial = True`. Add specific flags e.g. `"4h_missing"`, `"1d_missing"`.

### Corrupt package

CSV schema mismatch, unparseable timestamps, duplicate rows detected.

Raise a warning. Skip the corrupt timeframe. Treat as partial. Do not crash.

### Missing manifest

`EURUSD_hot.json` does not exist.

```python
raise FileNotFoundError(f"Hot package manifest not found for {instrument}. Has the feed pipeline run?")
```

This is the one case where a hard raise is acceptable — the Officer cannot function without the manifest.

### Unverified instrument

Set quality fields as specified in RULE 8. Return packet. Do not raise.

---

## Code quality standards

- All public functions must have docstrings
- Type hints on all function signatures
- No magic numbers — use named constants for thresholds (e.g. `STALENESS_THRESHOLD_MINUTES = 60`)
- `print()` is acceptable for CLI logging; structured logging is Phase 3
- No silent failures on quality issues — always log and flag

---

## Dependencies

Phase 2 requires no new external dependencies beyond Phase 1:

```
pandas>=2.0
pyarrow>=14.0
```

No ML libraries, no HTTP clients, no task frameworks needed in the Officer layer.
