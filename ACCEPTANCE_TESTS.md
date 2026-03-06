# ACCEPTANCE_TESTS.md — Phase 1A Exit Criteria

## How to use this file

Run each test group in order. Phase 1A is not complete until every criterion below passes. Where Python test snippets are provided, they should be implemented in `tests/` and runnable via `pytest`.

---

## Group 1 — Fetch layer

### T1.1 — URL construction is correct

```python
from feed.fetch import build_bi5_url
from datetime import datetime, timezone

dt = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
url = build_bi5_url("EURUSD", dt)

assert url == "https://www.dukascopy.com/datafeed/EURUSD/2025/00/15/09h_ticks.bi5"
# Note: Dukascopy uses zero-based month index (January = 00)
```

### T1.2 — Empty or 404 response returns empty bytes without crashing

```python
from feed.fetch import fetch_bi5
from datetime import datetime, timezone

# Use a future date that will return no data
far_future = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
result = fetch_bi5("EURUSD", far_future, save_raw=False)
assert result == b""
```

### T1.3 — Raw cache writes to correct path

If `save_raw=True`, verify the bi5 file appears at:
`market_data/raw/dukascopy/EURUSD/<year>/<month>/<day>/<hour>h_ticks.bi5`

---

## Group 2 — Decode layer

### T2.1 — Tick decode produces correct schema

```python
from feed.decode import decode_dukascopy_ticks
from feed.config import INSTRUMENTS
from datetime import datetime, timezone

meta = INSTRUMENTS["EURUSD"]
hour_start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

# Use a real fetched bi5 payload for this test
df = decode_dukascopy_ticks(raw_bytes, hour_start, meta)

assert not df.empty
assert set(df.columns) >= {"mid", "volume"}
assert df.index.name == "timestamp_utc"
assert df.index.tzinfo is not None  # UTC-aware
assert df.index.is_monotonic_increasing
```

### T2.2 — Price scale applied correctly for EURUSD

Decoded `mid` values must be in the range 0.8–1.5 (plausible EURUSD range).

```python
assert df["mid"].between(0.8, 1.5).all(), f"Suspicious EURUSD price: {df['mid'].describe()}"
```

### T2.3 — Corrupt or empty bytes return empty DataFrame without crash

```python
result = decode_dukascopy_ticks(b"", hour_start, meta)
assert result.empty

result = decode_dukascopy_ticks(b"not_valid_lzma_data", hour_start, meta)
assert result.empty
```

---

## Group 3 — Aggregation layer

### T3.1 — 1m OHLCV schema is correct

```python
from feed.aggregate import ticks_to_1m_ohlcv

m1 = ticks_to_1m_ohlcv(tick_df)

assert set(m1.columns) >= {"open", "high", "low", "close", "volume"}
assert m1.index.tzinfo is not None
assert m1.index.freq == "T" or m1.index.is_monotonic_increasing
```

### T3.2 — OHLC derivation is correct

For a known tick sequence, verify:

```python
# If ticks at 09:00 are: 1.0900, 1.0950, 1.0880, 1.0920
# Then 1m bar at 09:00 must be:
assert bar["open"] == 1.0900
assert bar["high"] == 1.0950
assert bar["low"]  == 1.0880
assert bar["close"] == 1.0920
```

### T3.3 — Empty tick input returns empty DataFrame

```python
result = ticks_to_1m_ohlcv(pd.DataFrame())
assert result.empty
```

---

## Group 4 — Validation layer

### T4.1 — Valid DataFrame passes silently

```python
from feed.validate import validate_ohlcv
# Should not raise
validate_ohlcv(clean_df, "test")
```

### T4.2 — Non-monotonic index raises

```python
import pytest
with pytest.raises(ValueError, match="monotonic"):
    validate_ohlcv(df_with_scrambled_index, "test")
```

### T4.3 — Duplicate timestamps raise

```python
with pytest.raises(ValueError, match="duplicate"):
    validate_ohlcv(df_with_dupes, "test")
```

### T4.4 — Null OHLC raises

```python
with pytest.raises(ValueError, match="null"):
    validate_ohlcv(df_with_null_close, "test")
```

### T4.5 — Invalid high/low envelope raises

```python
# Row where high < open (impossible candle)
with pytest.raises(ValueError, match="invalid high"):
    validate_ohlcv(df_with_bad_high, "test")
```

---

## Group 5 — Resample layer

### T5.1 — Derived timeframes have correct schemas

For each of 5m, 15m, 1h, 4h, 1d:

```python
from feed.resample import resample_from_1m

df_5m = resample_from_1m(canonical_df, "5min")

assert set(df_5m.columns) >= {"open", "high", "low", "close", "volume", "vendor", "build_method", "quality_flag"}
assert df_5m.index.tzinfo is not None
assert df_5m["vendor"].iloc[0] == "derived"
assert df_5m["build_method"].iloc[0] == "resample_from_1m"
```

### T5.2 — No `mid` column reference anywhere in resample logic

Run a grep check:

```bash
grep -rn "mid" market_data_officer/feed/resample.py
# Must return no matches
```

### T5.3 — Derived bar count is plausible

A 5m bar produced from 5 1m bars must have `high` = max of those 5 highs, not some intermediate value. Verify on a known fixture.

### T5.4 — Validation runs on derived output before write

Confirm `validate_ohlcv()` is called inside `derive_timeframes()` for each timeframe before saving.

---

## Group 6 — Hot package export

### T6.1 — Correct row counts in hot CSVs

```python
import pandas as pd

df_1m = pd.read_csv("market_data/packages/latest/EURUSD_1m_latest.csv", index_col=0)
assert len(df_1m) <= 3000

df_1h = pd.read_csv("market_data/packages/latest/EURUSD_1h_latest.csv", index_col=0)
assert len(df_1h) <= 240
```

### T6.2 — JSON manifest is valid and complete

```python
import json

with open("market_data/packages/latest/EURUSD_hot.json") as f:
    manifest = json.load(f)

assert manifest["instrument"] == "EURUSD"
assert "as_of_utc" in manifest
assert "1m" in manifest["windows"]
assert "1d" in manifest["windows"]
assert manifest["windows"]["1m"]["count"] > 0
```

### T6.3 — Hot CSVs contain only OHLCV columns (no metadata columns)

```python
df = pd.read_csv("market_data/packages/latest/EURUSD_1m_latest.csv", index_col=0)
assert set(df.columns) == {"open", "high", "low", "close", "volume"}
```

---

## Group 7 — Incremental update

### T7.1 — Re-run produces no duplicate timestamps

After a successful run, run again on the same date range.

```python
canonical = pd.read_parquet("market_data/canonical/EURUSD_1m.parquet")
assert not canonical.index.duplicated().any()
```

### T7.2 — Re-run does not re-fetch already-ingested data

Add a fetch counter or log check. On second run for the same date, fetch calls for already-covered hours must be zero (or skipped).

### T7.3 — New data appends cleanly

Simulate: run for day 1, then run extending to day 2. Confirm:
- Row count increases
- Timestamps remain monotonic
- No duplicates at the boundary
- Validation passes after append

---

## Group 8 — End-to-end smoke test

### T8.1 — Full pipeline run completes without exception

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-15
```

Expected: no unhandled exceptions, all output files exist.

### T8.2 — All output files exist after run

```
market_data/canonical/EURUSD_1m.parquet       ✓
market_data/derived/EURUSD_5m.parquet         ✓
market_data/derived/EURUSD_5m.csv             ✓
market_data/derived/EURUSD_15m.parquet        ✓
market_data/derived/EURUSD_1h.parquet         ✓
market_data/derived/EURUSD_4h.parquet         ✓
market_data/derived/EURUSD_1d.parquet         ✓
market_data/packages/latest/EURUSD_1m_latest.csv  ✓
market_data/packages/latest/EURUSD_hot.json   ✓
```

### T8.3 — Canonical bar timestamps are UTC-aware

```python
df = pd.read_parquet("market_data/canonical/EURUSD_1m.parquet")
assert df.index.tzinfo is not None
assert str(df.index.tzinfo) in ("UTC", "utc", "<UTC>")
```

### T8.4 — EURUSD mid prices are in plausible FX range

```python
assert df["close"].between(0.8, 1.5).all()
```

### T8.5 — No `mid` column in canonical archive

```python
assert "mid" not in df.columns
```

---

## Phase 1A sign-off checklist

Before marking Phase 1A complete, confirm:

- [ ] All 8 test groups pass
- [ ] `validate_ohlcv()` is called before every Parquet/CSV write
- [ ] No `mid` column reference in resample or export code
- [ ] All timestamps UTC-aware throughout
- [ ] XAUUSD stub comment is present in `config.py`
- [ ] XAUUSD is not implemented
- [ ] `requirements.txt` is present
- [ ] `run_feed.py --help` works
- [ ] A 3-day EURUSD run completes cleanly end-to-end
- [ ] Re-run of same 3-day range produces zero new fetches and no duplicates
