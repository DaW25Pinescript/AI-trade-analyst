# ACCEPTANCE_TESTS.md — Phase 1B Exit Criteria

## How to use this file

Run all test groups. Phase 1B is not complete until every criterion passes — including the full Phase 1A regression suite. Report pass/fail per group.

---

## Group 0 — Phase 1A regression (must still pass)

Before running any XAUUSD tests, confirm Phase 1A is unbroken.

### T0.1 — EURUSD end-to-end run still completes

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-15
# Must complete without exception
```

### T0.2 — EURUSD canonical archive is intact

```python
import pandas as pd

df = pd.read_parquet("market_data/canonical/EURUSD_1m.parquet")
assert not df.empty
assert not df.index.duplicated().any()
assert df.index.tzinfo is not None
assert df["close"].between(0.8, 1.5).all()
```

### T0.3 — All original Phase 1A pytest tests pass

```bash
pytest market_data_officer/tests/test_validate.py
pytest market_data_officer/tests/test_resample.py
pytest market_data_officer/tests/test_decode.py
# All must pass with zero failures
```

---

## Group 1 — Verification gate (must pass before any other XAUUSD tests)

This group cannot be automated. It requires human confirmation. Claude Code must produce the verification artefacts and you must review them before sign-off.

### T1.1 — Verification note exists in config.py

```python
# grep check
grep -A 10 "XAUUSD Verification" market_data_officer/feed/config.py
# Must return the full comment block including date, sources, bars compared, scale, status
```

### T1.2 — At least 5 bars documented in verification output

The verification note or accompanying output must show a comparison table with at least 5 rows containing:
- Timestamp UTC
- Decoded OHLC
- TradingView OHLC
- CMC Markets OHLC
- Delta

### T1.3 — Price scale is explicitly stated and justified

The comment block must contain a line like:
```
# Price scale confirmed: 1000
```
Not "assumed" or "likely". Confirmed.

### T1.4 — Volume semantics are explicitly documented

The comment block must contain a volume semantics line. Acceptable values:
```
# Volume semantics: raw tick count, no divisor needed
# Volume semantics: divisor=1000 applied to normalise lot units
# Volume semantics: volume absent/zero for XAUUSD, set to 0.0
```
Absence of this line is a test failure.

### T1.5 — Verification status is not UNRESOLVED

```python
# grep check
grep "Status:" market_data_officer/feed/config.py
# Must return: VERIFIED or PARTIALLY VERIFIED
# Must NOT return: UNRESOLVED
```

If status is UNRESOLVED, Phase 1B cannot proceed. Document findings and pause for human review.

---

## Group 2 — XAUUSD fetch layer

### T2.1 — XAUUSD URL construction uses zero-based month

```python
from feed.fetch import build_bi5_url
from datetime import datetime, timezone

dt = datetime(2025, 3, 15, 9, 0, 0, tzinfo=timezone.utc)
url = build_bi5_url("XAUUSD", dt)

assert "XAUUSD" in url
assert "/2025/02/15/09h_ticks.bi5" in url  # month 3 → zero-based index 02
```

### T2.2 — Empty or 404 response returns empty bytes without crashing

```python
from feed.fetch import fetch_bi5
from datetime import datetime, timezone

far_future = datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
result = fetch_bi5("XAUUSD", far_future, save_raw=False)
assert result == b""
```

---

## Group 3 — XAUUSD decode layer

### T3.1 — Decoded XAUUSD mid prices are in plausible gold range

```python
from feed.decode import decode_dukascopy_ticks
from feed.config import INSTRUMENTS
from datetime import datetime, timezone

meta = INSTRUMENTS["XAUUSD"]
hour_start = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone.utc)

df = decode_dukascopy_ticks(raw_bytes, hour_start, meta)

assert not df.empty
assert df["mid"].between(1_500.0, 3_500.0).all(), \
    f"XAUUSD mid prices out of plausible range: {df['mid'].describe()}"
```

### T3.2 — XAUUSD uses its own InstrumentMeta, not EURUSD's

```python
from feed.config import INSTRUMENTS

eurusd_meta = INSTRUMENTS["EURUSD"]
xauusd_meta = INSTRUMENTS["XAUUSD"]

assert xauusd_meta.price_scale != eurusd_meta.price_scale, \
    "XAUUSD and EURUSD should not share the same price scale"
```

### T3.3 — Corrupt or empty bytes return empty DataFrame

```python
result = decode_dukascopy_ticks(b"", hour_start, meta)
assert result.empty

result = decode_dukascopy_ticks(b"invalid", hour_start, meta)
assert result.empty
```

---

## Group 4 — XAUUSD aggregation and validation

### T4.1 — 1m OHLCV schema is correct

```python
from feed.aggregate import ticks_to_1m_ohlcv

m1 = ticks_to_1m_ohlcv(xauusd_tick_df)

assert set(m1.columns) >= {"open", "high", "low", "close", "volume"}
assert m1.index.tzinfo is not None
assert m1.index.is_monotonic_increasing
```

### T4.2 — XAUUSD canonical archive price range is valid

```python
import pandas as pd

df = pd.read_parquet("market_data/canonical/XAUUSD_1m.parquet")

assert not df.empty
assert df["close"].between(1_500.0, 3_500.0).all(), \
    f"XAUUSD canonical prices out of range: {df['close'].describe()}"
```

### T4.3 — XAUUSD canonical archive has no duplicate timestamps

```python
assert not df.index.duplicated().any()
```

### T4.4 — XAUUSD canonical archive is UTC-aware

```python
assert df.index.tzinfo is not None
```

### T4.5 — No `mid` column in XAUUSD canonical archive

```python
assert "mid" not in df.columns
```

---

## Group 5 — XAUUSD derived timeframes

### T5.1 — All derived files exist

```python
import os
for tf in ["5m", "15m", "1h", "4h", "1d"]:
    assert os.path.exists(f"market_data/derived/XAUUSD_{tf}.parquet"), f"Missing: XAUUSD_{tf}.parquet"
    assert os.path.exists(f"market_data/derived/XAUUSD_{tf}.csv"), f"Missing: XAUUSD_{tf}.csv"
```

### T5.2 — Derived timeframes have plausible price range

```python
import pandas as pd

df_1h = pd.read_parquet("market_data/derived/XAUUSD_1h.parquet")
assert df_1h["close"].between(1_500.0, 3_500.0).all()
```

### T5.3 — Validation ran on all derived outputs (no mid column reference)

```bash
grep -rn "mid" market_data_officer/feed/resample.py
# Must return no matches
```

---

## Group 6 — XAUUSD hot packages

### T6.1 — Hot package files exist

```python
import os
for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
    assert os.path.exists(f"market_data/packages/latest/XAUUSD_{tf}_latest.csv")
assert os.path.exists("market_data/packages/latest/XAUUSD_hot.json")
```

### T6.2 — Hot package manifest is valid

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

### T6.3 — Hot CSV row counts are within window limits

```python
import pandas as pd

limits = {"1m": 3000, "5m": 1200, "15m": 600, "1h": 240, "4h": 120, "1d": 30}

for tf, limit in limits.items():
    df = pd.read_csv(f"market_data/packages/latest/XAUUSD_{tf}_latest.csv", index_col=0)
    assert len(df) <= limit, f"{tf} hot package exceeds limit: {len(df)} > {limit}"
```

---

## Group 7 — Incremental update

### T7.1 — XAUUSD re-run produces no duplicates

```python
# Run pipeline twice on same date range
# Then check:
df = pd.read_parquet("market_data/canonical/XAUUSD_1m.parquet")
assert not df.index.duplicated().any()
```

### T7.2 — EURUSD canonical archive unaffected by XAUUSD run

```python
eurusd_before = pd.read_parquet("market_data/canonical/EURUSD_1m.parquet")
# Run XAUUSD pipeline
eurusd_after = pd.read_parquet("market_data/canonical/EURUSD_1m.parquet")

assert len(eurusd_before) == len(eurusd_after)
assert eurusd_before.index.equals(eurusd_after.index)
```

---

## Group 8 — Officer instrument status

### T8.1 — Officer emits `trusted` quality for XAUUSD after Phase 1B sign-off

```python
from officer.service import build_market_packet

packet = build_market_packet("XAUUSD")
assert packet.source["quality"] == "validated"
assert packet.state_summary.data_quality == "validated"
assert packet.is_trusted() is True
```

### T8.2 — Officer EURUSD packet still valid after update

```python
eurusd_packet = build_market_packet("EURUSD")
assert eurusd_packet.is_trusted() is True
```

---

## Group 9 — End-to-end smoke test

### T9.1 — Full XAUUSD pipeline run completes without exception

```bash
python run_feed.py --instrument XAUUSD --start-date 2025-01-13 --end-date 2025-01-15
# Must complete without unhandled exceptions
```

### T9.2 — All output files exist

```
market_data/canonical/XAUUSD_1m.parquet          ✓
market_data/derived/XAUUSD_5m.parquet            ✓
market_data/derived/XAUUSD_1h.parquet            ✓
market_data/derived/XAUUSD_1d.parquet            ✓
market_data/packages/latest/XAUUSD_hot.json      ✓
```

---

## Phase 1B sign-off checklist

Before marking Phase 1B complete, confirm:

- [ ] Group 0 (Phase 1A regression) — all pass
- [ ] Group 1 (verification gate) — human reviewed and confirmed
- [ ] Verification note in `config.py` with date, sources, 5+ bars, scale, volume, status
- [ ] `InstrumentMeta` for XAUUSD populated with confirmed (not assumed) values
- [ ] XAUUSD canonical archive prices in range 1,500–3,500 USD
- [ ] No `mid` column in XAUUSD canonical archive or derived files
- [ ] All XAUUSD hot package files exist
- [ ] Officer emits `trusted` quality for XAUUSD
- [ ] Officer EURUSD packet unaffected
- [ ] XAUUSD re-run produces zero duplicates
- [ ] `run_feed.py --instrument XAUUSD` completes end-to-end on 3-day range
