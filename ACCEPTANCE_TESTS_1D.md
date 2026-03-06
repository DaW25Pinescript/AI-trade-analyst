# ACCEPTANCE_TESTS_1D.md — Phase 1D: Raw Cache Diagnostics Layer

Phase 1D adds a structured diagnostics layer: per-hour fetch/decode audit trail,
raw cache inventory, and decode anomaly verification. No new instruments, no
Market Data Officer wiring.

---

## Test Group 1 — DiagnosticsCollector records fetch metadata

1. A `DiagnosticsCollector` accumulates per-hour `FetchRecord` entries with:
   url, http_status, payload_bytes, content_sha256, fetch_utc, cached_path, error.
2. `record_skipped()` marks incremental-skip hours with `http_status=-1`.
3. The built report (`build_report()`) contains a `summary` dict with:
   total_hour_slots, fetched, skipped_incremental, fetch_errors,
   empty_payloads, total_payload_bytes.
4. The `hours` list in the report is sorted by `hour_utc`.

## Test Group 2 — DiagnosticsCollector records decode statistics

1. `record_decode()` captures: tick_count, bars_produced, price_min, price_max,
   volume_total, decode_error per hour.
2. Summary aggregates: total_ticks_decoded, total_bars_produced, hours_with_ticks,
   decode_errors.
3. Hours with a decode record include both `fetch` and `decode` dicts.

## Test Group 3 — Diagnostics report persistence

1. `collector.save_report()` writes `{SYMBOL}_diagnostics.json` to the reports dir.
2. The JSON is valid, readable, and contains all summary + per-hour data.
3. Successive runs overwrite the previous report (no accumulation).

## Test Group 4 — Raw cache inventory

1. `generate_cache_inventory(symbol)` scans `market_data/raw/dukascopy/{SYMBOL}/`
   and returns a JSON-serializable dict.
2. Each cached .bi5 file is listed with: relative path, byte size, sha256 hash.
3. Summary includes: total_files, total_bytes, years covered.
4. If the cache directory does not exist, report `exists: false` gracefully.

## Test Group 5 — Decode anomaly verification

1. `verify_decode_assumptions()` detects:
   - `empty_decode`: non-empty payload but zero ticks decoded.
   - `price_range_outlier`: hour price range > 3x median.
   - `low_tick_density`: tick count < 10% of median.
   - `high_tick_density`: tick count > 500% of median.
2. Returns reference stats: median_ticks_per_hour, median_price_range_per_hour.
3. Returns zero anomalies for a clean, uniform dataset.

## Test Group 6 — fetch_bi5_detailed returns FetchResult

1. `fetch_bi5_detailed()` returns a `FetchResult` dataclass with:
   data, url, http_status, cached_path, error.
2. Network errors return `http_status=0` with a descriptive error string.
3. HTTP 4xx returns empty data with `http_{status}` error.
4. Successful fetch returns the raw bytes, status 200, and empty error.

## Test Group 7 — decode_with_diagnostics returns DecodeStats

1. `decode_with_diagnostics()` returns `(DataFrame, DecodeStats)`.
2. Empty input returns empty DataFrame + `DecodeStats(error="empty_input")`.
3. Valid input returns the tick DataFrame + stats with tick_count, price_min/max,
   volume_total populated.
4. Corrupt input returns empty DataFrame + DecodeStats (no crash).

## Test Group 8 — Pipeline integration

1. `run_pipeline(..., diagnostics=True)` produces a diagnostics JSON report
   in `market_data/reports/`.
2. With `--save-raw --diagnostics`, a cache inventory JSON is also produced.
3. The standard pipeline path (diagnostics=False) is unchanged — no overhead.
4. `--hot-only --diagnostics` generates a cache inventory without fetch diagnostics.

## Test Group 9 — CLI flag

1. `run_feed.py --diagnostics` activates diagnostics collection.
2. The flag is off by default (no overhead when not requested).
3. Can be combined with existing flags: `--save-raw --gap-report --diagnostics`.

---

## Exit gate

All test groups above pass. Existing Phase 1A/1B/1C tests remain green.
No changes to canonical data format, derived timeframes, or hot packages.
