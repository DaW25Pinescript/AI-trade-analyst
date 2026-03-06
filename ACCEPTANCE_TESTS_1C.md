# ACCEPTANCE_TESTS_1C.md — Phase 1C Exit Criteria (Incremental Updater Hardening)

## How to use this file

Phase 1C hardens the incremental updater. It is not complete until every criterion below passes and all Phase 1A/1B tests continue to pass (no regressions).

---

## Group 1 — Selective derived regeneration

### T1.1 — Incremental update only resamples affected window

After a full initial run, extend the date range by one day. Confirm that:
- Only the new data window is resampled (not the full history)
- Derived outputs are identical to a full resample (correctness preserved)

```python
# Run for days 1-3, then extend to day 4
# Derived output after incremental should match a clean full resample
import pandas as pd

df_incremental = pd.read_parquet("market_data/derived/EURUSD_1h.parquet")
# Compare against a fresh full resample of canonical
# Bars should be identical
```

### T1.2 — No new data skips derived regeneration when using hot-only

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-13 --hot-only
```

Hot packages should be regenerated from existing canonical without any fetching.

### T1.3 — Selective regeneration produces same output as full resample

For each derived timeframe, the output from a selective incremental update must
be byte-for-byte identical (modulo metadata timestamps) to a full resample from
the same canonical data.

---

## Group 2 — Gap detection

### T2.1 — Contiguous data has zero gaps

```python
from feed.gaps import detect_gaps
gaps = detect_gaps(contiguous_1m_df, "EURUSD")
assert len(gaps) == 0
```

### T2.2 — Missing minutes are detected

```python
# Drop minutes 5,6 from a 20-minute series
gaps = detect_gaps(df_with_holes, "EURUSD")
assert len(gaps) >= 1
assert any(g["missing_minutes"] > 0 for g in gaps)
```

### T2.3 — Weekend gaps classified separately from trading-hour gaps

```python
gaps = detect_gaps(df_spanning_weekend, "EURUSD")
weekend = [g for g in gaps if g["classification"] == "weekend"]
trading = [g for g in gaps if g["classification"] == "trading_hours"]
# Weekend gaps should be classified as "weekend"
assert len(weekend) >= 1
```

### T2.4 — Gap detection is idempotent

```python
gaps1 = detect_gaps(df, "EURUSD")
gaps2 = detect_gaps(df, "EURUSD")
assert gaps1 == gaps2
```

---

## Group 3 — Gap report

### T3.1 — Gap report has correct structure

```python
from feed.gaps import generate_gap_report
report = generate_gap_report("EURUSD", canonical_df)

assert report["symbol"] == "EURUSD"
assert "generated_utc" in report
assert "canonical_range" in report
assert "summary" in report
assert "trading_hour_gaps" in report
assert "weekend_gaps" in report
```

### T3.2 — Gap report is saved to disk

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-15 --gap-report
```

File `market_data/reports/EURUSD_gap_report.json` must exist and be valid JSON.

### T3.3 — Gap report is idempotent

Running gap report twice on the same data produces identical gap lists
(generated_utc may differ).

---

## Group 4 — Hot-only refresh

### T4.1 — --hot-only regenerates packages without fetching

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-15 --hot-only
```

Expected: no network fetches, hot packages regenerated from canonical.

### T4.2 — --hot-only on missing canonical produces helpful message

```bash
# With no canonical data for FOOBAR:
python run_feed.py --instrument EURUSD --start-date 2099-01-01 --end-date 2099-01-01 --hot-only
```

Should print a message about no existing data and exit cleanly.

---

## Group 5 — CLI

### T5.1 — --help shows new flags

```bash
python run_feed.py --help
```

Must show `--gap-report` and `--hot-only` flags.

### T5.2 — --gap-report flag works

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-15 --gap-report
```

No exceptions, gap report file created.

---

## Group 6 — No regressions

### T6.1 — All Phase 1A/1B tests pass

```bash
cd market_data_officer && python -m pytest tests/ -v
```

All existing tests must pass.

### T6.2 — Pipeline end-to-end still works for both instruments

```bash
python run_feed.py --instrument EURUSD --start-date 2025-01-13 --end-date 2025-01-15
python run_feed.py --instrument XAUUSD --start-date 2025-01-13 --end-date 2025-01-15
```

Both must complete cleanly with all output files.

---

## Phase 1C sign-off checklist

- [ ] Selective derived regeneration only resamples affected windows
- [ ] Full resample and selective regeneration produce identical output
- [ ] Gap detection identifies missing trading-hour minutes
- [ ] Weekend gaps classified separately from trading-hour gaps
- [ ] Gap detection is idempotent
- [ ] Gap report saved as JSON with correct structure
- [ ] --hot-only flag works without fetching
- [ ] --gap-report flag generates and saves report
- [ ] All Phase 1A/1B tests pass (no regressions)
- [ ] New Phase 1C tests pass
