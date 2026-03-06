# CONSTRAINTS.md — Hard Rules, Known Defects, Engineering Standards

## Non-negotiable engineering rules

These rules are not suggestions. Violating any of them is a defect.

---

### RULE 1 — UTC everywhere

All timestamps must be UTC and timezone-aware throughout the entire pipeline.

```python
# Correct
ts = datetime.now(timezone.utc)
df.index = pd.to_datetime(df.index, utc=True)

# Wrong
ts = datetime.utcnow()  # naive, not timezone-aware
df.index = pd.to_datetime(df.index)  # may lose tz info
```

If any timestamp is naive (no tzinfo), that is a defect. Raise on it.

---

### RULE 2 — Canonical truth is 1m OHLCV only

The canonical archive is `EURUSD_1m.parquet`. It is not a tick archive. It is not a mid-price series.

Once ticks have been aggregated to 1m OHLCV, the tick-level `mid` column no longer exists. Derived timeframes must resample from `open/high/low/close/volume` columns — **never from a `mid` column** (this was the critical bug in the prototype).

---

### RULE 3 — Higher timeframes derived only, never fetched

5m, 15m, 1h, 4h, 1d are always computed by resampling canonical 1m. They are never fetched independently from Dukascopy or any other source. This ensures:

- internal consistency across all timeframes
- a single source of truth
- simpler validation

---

### RULE 4 — Validation before every write

The validation function must run before any Parquet or CSV write. It must check:

1. **Monotonic timestamps** — index must be strictly increasing
2. **No duplicate timestamps** — zero tolerance
3. **No null OHLC** — open/high/low/close must all be non-null
4. **High/low envelope validity**:
   - `high >= max(open, close, low)` for every row
   - `low <= min(open, close, high)` for every row
5. **Required columns present** — open, high, low, close, volume

If validation fails, raise a `ValueError` with a descriptive message. Do not silently write corrupt data.

```python
def validate_ohlcv(df: pd.DataFrame, label: str) -> None:
    """Raises ValueError if df fails any integrity check."""
    ...
```

---

### RULE 5 — Instrument metadata controls parsing assumptions

All instrument-specific values (price scale, volume divisor, symbol name) must come from a single `InstrumentMeta` dataclass, not from hardcoded magic numbers inside parsing functions.

```python
@dataclass(frozen=True)
class InstrumentMeta:
    symbol: str
    price_scale: int
    volume_divisor: Optional[float] = None

INSTRUMENTS = {
    "EURUSD": InstrumentMeta(symbol="EURUSD", price_scale=100000),
    # XAUUSD: DO NOT POPULATE until Phase 1B with verified values
}
```

---

### RULE 6 — Source abstraction boundary

Dukascopy-specific parsing logic must live behind a clear module boundary (`fetch.py`, `decode.py`). The rest of the pipeline (`aggregate.py`, `validate.py`, `resample.py`, `export.py`) must be source-agnostic. This is what makes Phase 1B (XAUUSD) and Phase 1E (HistData bootstrap) possible without rewriting the core.

---

### RULE 7 — Incremental append is idempotent

Re-running the pipeline must:
- Detect the last canonical timestamp
- Only fetch data after that point
- Append without creating duplicate rows
- Produce the same result whether run once or ten times

Test this explicitly. See `ACCEPTANCE_TESTS.md`.

---

### RULE 8 — No framework bloat

Do not introduce:
- Celery, Airflow, Prefect, or task queue frameworks
- FastAPI/Flask endpoints
- Database ORM layers
- Heavy ML dependencies

Phase 1A is a data pipeline, not a web service. Keep it: `requests`, `pandas`, `pyarrow`, `lzma`, `struct`, `pathlib`, `dataclasses`. That is sufficient.

---

## Known defects in the prototype — must fix

These were identified in the prior Codex session. All must be corrected:

| # | Defect | Fix required |
|---|--------|--------------|
| 1 | `derive_timeframes()` referenced a nonexistent `mid` column after canonical 1m was already OHLCV | Resample from `open/high/low/close/volume` only |
| 2 | Dukascopy volume parsing was not isolated — `ask_vol_raw + bid_vol_raw` summed raw integers without instrument-aware divisor handling | Route through `InstrumentMeta.volume_divisor` |
| 3 | Price scaling was inconsistently applied — not always routed through `InstrumentMeta.price_scale` | All price scaling must go through metadata |
| 4 | Timezone handling was inconsistent — some paths produced naive timestamps | Enforce UTC-aware everywhere, raise on naive |
| 5 | No validation before writes | Add `validate_ohlcv()` before every Parquet/CSV write |
| 6 | Hour-by-hour loop had no error isolation — one bad hour crashed the day | Wrap each hour in try/except, log and continue |

---

## XAUUSD stubs — do not implement, do leave explicit notes

In `config.py`, leave this exact stub with comment block:

```python
# TODO Phase 1B — XAUUSD
# DO NOT populate until the following are independently verified:
#   1. Dukascopy price_scale for XAUUSD (likely 1000, but MUST be confirmed
#      against a known reference bar — e.g. compare decoded close vs CMC/TradingView)
#   2. Volume interpretation for XAUUSD (lots? units? divisor needed?)
#   3. Any session/gap behaviour differences vs EURUSD
# Populating with unverified values will silently corrupt the canonical archive.
# "XAUUSD": InstrumentMeta(symbol="XAUUSD", price_scale=???, volume_divisor=???),
```

In `decode.py`, leave a corresponding note at the tick parsing layer flagging the struct format assumption.

---

## Code quality standards

- Every public function must have a docstring (one line minimum)
- Functions do one thing — if a function name requires "and", split it
- No magic numbers — name your constants
- `print()` is acceptable for pipeline logging at this stage; structured logging is Phase 2
- Type hints on all function signatures
- No silent failures — log warnings, raise on data integrity issues

---

## Dependency list (Phase 1A)

```
pandas>=2.0
pyarrow>=14.0
requests>=2.28
```

No other external dependencies required for Phase 1A. Include a `requirements.txt` or note in `README.md`.
