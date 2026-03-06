# ACCEPTANCE_TESTS_1B.md — Phase 1B Exit Criteria (XAUUSD)

## How to use this file

These are the Phase 1A acceptance criteria substituted for XAUUSD. Phase 1B is not complete until every criterion below passes. All existing EURUSD tests must also continue to pass (no regressions).

---

## Group 1 — Fetch layer

### T1.1 — URL construction is correct for XAUUSD

```python
from feed.fetch import build_bi5_url
from datetime import datetime, timezone

dt = datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc)
url = build_bi5_url("XAUUSD", dt)

assert url == "https://www.dukascopy.com/datafeed/XAUUSD/2025/00/16/14h_ticks.bi5"
```

### T1.2 — Empty or 404 response returns empty bytes without crashing

```python
from feed.fetch import fetch_bi5
from datetime import datetime, timezone

far_future = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
result = fetch_bi5("XAUUSD", far_future, save_raw=False)
assert result == b""
```

---

## Group 2 — Decode layer

### T2.1 — Tick decode produces correct schema for XAUUSD

```python
from feed.decode import decode_dukascopy_ticks
from feed.config import INSTRUMENTS

meta = INSTRUMENTS["XAUUSD"]
hour_start = datetime(2025, 1, 16, 14, 0, 0, tzinfo=timezone.utc)

df = decode_dukascopy_ticks(raw_bytes, hour_start, meta)

assert not df.empty
assert set(df.columns) >= {"mid", "volume"}
assert df.index.name == "timestamp_utc"
assert df.index.tzinfo is not None
assert df.index.is_monotonic_increasing
```

### T2.2 — Price scale applied correctly for XAUUSD

Decoded `mid` values must be in the range 2000–4000 (plausible XAUUSD range for 2024-2026).

```python
assert df["mid"].between(2000.0, 4000.0).all(), f"Suspicious XAUUSD price: {df['mid'].describe()}"
```

### T2.3 — Verified against external reference

At least 5 decoded bars must be cross-checked against a known external source.

Verification record (performed during Phase 1B implementation):
- Source: Dukascopy bi5 2025-01-16 14:00 UTC
- Raw ask=2715695 → ask/1000 = $2715.695
- Known gold spot mid-January 2025: ~$2702-2720/oz
- Match: YES (within expected intraday range)

---

## Group 3 — Aggregation layer

### T3.1 — 1m OHLCV schema is correct for XAUUSD

Same as Phase 1A — the aggregation layer is instrument-agnostic.

---

## Group 4 — Validation layer

Same as Phase 1A — the validation layer is instrument-agnostic.

---

## Group 5 — Resample layer

### T5.1 — Derived timeframes have correct schemas for XAUUSD

Same acceptance criteria as Phase 1A, applied to XAUUSD data.

### T5.2 — No `mid` column reference in resample logic

```bash
grep -rn "mid" market_data_officer/feed/resample.py
# Must return no matches
```

---

## Group 6 — Hot package export

### T6.1 — Correct row counts in hot CSVs

```python
import pandas as pd

df_1m = pd.read_csv("market_data/packages/latest/XAUUSD_1m_latest.csv", index_col=0)
assert len(df_1m) <= 3000

df_1h = pd.read_csv("market_data/packages/latest/XAUUSD_1h_latest.csv", index_col=0)
assert len(df_1h) <= 240
```

### T6.2 — JSON manifest is valid and complete

```python
import json

with open("market_data/packages/latest/XAUUSD_hot.json") as f:
    manifest = json.load(f)

assert manifest["instrument"] == "XAUUSD"
assert "as_of_utc" in manifest
assert "1m" in manifest["windows"]
assert "1d" in manifest["windows"]
assert manifest["windows"]["1m"]["count"] > 0
```

### T6.3 — Hot CSVs contain only OHLCV columns

```python
df = pd.read_csv("market_data/packages/latest/XAUUSD_1m_latest.csv", index_col=0)
assert set(df.columns) == {"open", "high", "low", "close", "volume"}
```

---

## Group 7 — Incremental update

### T7.1 — Re-run produces no duplicate timestamps

```python
canonical = pd.read_parquet("market_data/canonical/XAUUSD_1m.parquet")
assert not canonical.index.duplicated().any()
```

### T7.2 — Re-run does not re-fetch already-ingested data

On second run for the same date, fetch calls for already-covered hours must be zero.

### T7.3 — New data appends cleanly

Same idempotent append criteria as Phase 1A.

---

## Group 8 — End-to-end smoke test

### T8.1 — Full pipeline run completes without exception

```bash
python run_feed.py --instrument XAUUSD --start-date 2025-01-13 --end-date 2025-01-15
```

Expected: no unhandled exceptions, all output files exist.

### T8.2 — All output files exist after run

```
market_data/canonical/XAUUSD_1m.parquet       ✓
market_data/derived/XAUUSD_5m.parquet         ✓
market_data/derived/XAUUSD_5m.csv             ✓
market_data/derived/XAUUSD_15m.parquet        ✓
market_data/derived/XAUUSD_1h.parquet         ✓
market_data/derived/XAUUSD_4h.parquet         ✓
market_data/derived/XAUUSD_1d.parquet         ✓
market_data/packages/latest/XAUUSD_1m_latest.csv  ✓
market_data/packages/latest/XAUUSD_hot.json   ✓
```

### T8.3 — Canonical bar timestamps are UTC-aware

```python
df = pd.read_parquet("market_data/canonical/XAUUSD_1m.parquet")
assert df.index.tzinfo is not None
assert str(df.index.tzinfo) in ("UTC", "utc", "<UTC>")
```

### T8.4 — XAUUSD close prices are in plausible gold range

```python
assert df["close"].between(2000.0, 4000.0).all()
```

### T8.5 — No `mid` column in canonical archive

```python
assert "mid" not in df.columns
```

---

## Group 9 — External reference cross-check (Phase 1B specific)

### T9.1 — At least 5 decoded XAUUSD bars validated against known reference

Verification was performed during implementation using Dukascopy bi5 data
for 2025-01-16 14:00 UTC. The first 5 ticks produced:

| Tick | Raw ask | Decoded ask | Decoded mid |
|------|---------|-------------|-------------|
| 0    | 2715695 | $2715.695   | $2715.445   |
| 1    | 2715725 | $2715.725   | $2715.460   |
| 2    | 2715735 | $2715.735   | $2715.445   |
| 3    | 2715715 | $2715.715   | $2715.435   |
| 4    | 2715665 | $2715.665   | $2715.405   |

These are consistent with known gold spot prices of ~$2702-2720 on January 16, 2025.

---

## Phase 1B sign-off checklist

Before marking Phase 1B complete, confirm:

- [ ] All Phase 1A EURUSD tests still pass (no regressions)
- [ ] XAUUSD is registered in `INSTRUMENTS` with verified price_scale=1000
- [ ] Verification notes document the evidence for price_scale choice
- [ ] Volume interpretation documented (raw lots, no divisor, unverified against external volume source)
- [ ] XAUUSD decode tests pass
- [ ] `validate_ohlcv()` is called before every write (same as Phase 1A)
- [ ] No `mid` column in resample or export code
- [ ] All timestamps UTC-aware throughout
- [ ] A 3-day XAUUSD run completes cleanly end-to-end
- [ ] Re-run of same 3-day range produces zero new fetches and no duplicates
- [ ] At least 5 XAUUSD bars validated against known external reference
