# ACCEPTANCE_TESTS.md — Market Data Officer Phase 2 Exit Criteria

## How to use this file

Run each test group in order. Phase 2 is not complete until every criterion passes. Implement tests in `market_data_officer/tests/` and run via `pytest`.

Prerequisite: Phase 1A feed pipeline has run successfully and hot packages exist in `market_data/packages/latest/`.

---

## Group 1 — Loader

### T1.1 — Manifest loads and parses correctly

```python
from officer.loader import load_manifest

manifest = load_manifest("EURUSD")

assert manifest["instrument"] == "EURUSD"
assert "as_of_utc" in manifest
assert "windows" in manifest
assert "1m" in manifest["windows"]
assert "1d" in manifest["windows"]
```

### T1.2 — All six timeframe DataFrames load with correct schema

```python
from officer.loader import load_timeframe

for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
    df = load_timeframe("EURUSD", tf)
    assert not df.empty, f"{tf} DataFrame is empty"
    assert set(df.columns) >= {"open", "high", "low", "close", "volume"}
    assert df.index.tzinfo is not None, f"{tf} index is not UTC-aware"
    assert df.index.is_monotonic_increasing, f"{tf} index is not monotonic"
```

### T1.3 — Loader does not read raw Parquet

```python
# Grep check — must return no matches
# grep -rn "read_parquet" market_data_officer/officer/loader.py
# Expected: no output
```

### T1.4 — Missing manifest raises FileNotFoundError

```python
import pytest
with pytest.raises(FileNotFoundError):
    load_manifest("FAKEINSTRUMENT")
```

---

## Group 2 — Quality checks

### T2.1 — Valid package passes all quality checks

```python
from officer.quality import check_package_quality

result = check_package_quality("EURUSD")

assert result.manifest_valid is True
assert result.all_timeframes_present is True
assert result.partial is False
assert result.flags == []
```

### T2.2 — Stale package is flagged, not crashed

```python
# Simulate: modify manifest as_of_utc to be 3 hours ago
# Re-run quality check
result = check_package_quality("EURUSD")
assert result.stale is True
assert result.staleness_minutes > 60
assert "stale" in result.flags or result.stale is True
```

### T2.3 — Partial package degrades gracefully

```python
# Simulate: rename EURUSD_4h_latest.csv temporarily
result = check_package_quality("EURUSD")
assert result.partial is True
assert any("4h" in f for f in result.flags)
```

### T2.4 — Unverified instrument returns unverified quality, not crash

```python
from officer.service import build_market_packet

packet = build_market_packet("XAUUSD")  # provisional instrument
assert packet.quality.flags  # must have at least one flag
assert packet.state_summary.data_quality in ("unverified", "partial")
# Must NOT raise an exception
```

---

## Group 3 — Core features

### T3.1 — All core feature fields are present and non-null

```python
from officer.features import compute_core_features
from officer.loader import load_timeframe

df_1h = load_timeframe("EURUSD", "1h")
features = compute_core_features(df_1h)

assert features.atr_14 > 0
assert features.volatility_regime in ("low", "normal", "expanding")
assert features.momentum is not None
assert features.ma_50 > 0
assert features.ma_200 > 0
assert features.swing_high > 0
assert features.swing_low > 0
assert features.rolling_range > 0
assert features.session_context in ("asian", "london", "new_york", "overlap")
```

### T3.2 — ATR is positive and plausible for EURUSD

```python
# EURUSD ATR on 1h should be in range 0.0001 to 0.02
assert 0.0001 < features.atr_14 < 0.02, f"ATR out of plausible range: {features.atr_14}"
```

### T3.3 — MA values are plausible for EURUSD

```python
assert 0.8 < features.ma_50 < 1.5
assert 0.8 < features.ma_200 < 1.5
```

### T3.4 — Feature computation is deterministic

```python
features_a = compute_core_features(df_1h)
features_b = compute_core_features(df_1h)
assert features_a.atr_14 == features_b.atr_14
assert features_a.ma_50 == features_b.ma_50
```

### T3.5 — Insufficient data returns graceful result, not crash

```python
import pandas as pd
tiny_df = df_1h.head(10)  # only 10 bars, not enough for MA200
features = compute_core_features(tiny_df)
# Should not raise — ma_200 may be None or 0.0, not an exception
assert features is not None
```

---

## Group 4 — Advanced feature stubs

### T4.1 — All stub modules exist

```bash
# Each of these files must exist:
ls market_data_officer/officer/structure/bos_detector.py
ls market_data_officer/officer/structure/fvg_detector.py
ls market_data_officer/officer/structure/compression_detector.py
ls market_data_officer/officer/structure/imbalance_detector.py
```

### T4.2 — All stubs return None without raising

```python
from officer.structure.bos_detector import detect_bos
from officer.structure.fvg_detector import detect_fvg
from officer.structure.compression_detector import detect_compression
from officer.structure.imbalance_detector import detect_imbalance

df_1h = load_timeframe("EURUSD", "1h")

assert detect_bos(df_1h) is None
assert detect_fvg(df_1h) is None
assert detect_compression(df_1h) is None
assert detect_imbalance(df_1h) is None
```

### T4.3 — All stubs have docstrings explaining Phase 3/4 intent

```python
import inspect
from officer.structure import bos_detector

assert bos_detector.detect_bos.__doc__ is not None
assert len(bos_detector.detect_bos.__doc__) > 20
```

---

## Group 5 — State summary

### T5.1 — All state summary fields present

```python
from officer.summarizer import build_state_summary

summary = build_state_summary(features, timeframes)

assert summary.trend_1h in ("bullish", "bearish", "neutral")
assert summary.trend_4h in ("bullish", "bearish", "neutral")
assert summary.trend_1d in ("bullish", "bearish", "neutral")
assert summary.volatility_regime in ("low", "normal", "expanding")
assert summary.momentum_state in ("expanding", "contracting", "flat")
assert summary.session_context in ("asian", "london", "new_york", "overlap")
assert summary.data_quality in ("validated", "partial", "stale", "unverified")
```

### T5.2 — Trend derivation is consistent with MA relationship

```python
# If close > ma_50 > ma_200 on 1h, trend_1h must be "bullish"
# Construct a synthetic DataFrame to verify this deterministically
```

---

## Group 6 — Market Packet assembly

### T6.1 — Full packet builds without exception

```python
from officer.service import build_market_packet

packet = build_market_packet("EURUSD")
assert packet is not None
```

### T6.2 — Packet serialises to valid JSON matching v1 schema

```python
import json

d = packet.to_dict()
json_str = json.dumps(d)  # must not raise
parsed = json.loads(json_str)

# Top-level keys
assert set(parsed.keys()) >= {"instrument", "as_of_utc", "source", "timeframes", "features", "state_summary", "quality"}

# All four feature keys present
assert set(parsed["features"].keys()) == {"core", "structure", "imbalance", "compression"}

# Advanced features are null
assert parsed["features"]["structure"] is None
assert parsed["features"]["imbalance"] is None
assert parsed["features"]["compression"] is None

# Core features populated
assert parsed["features"]["core"]["atr_14"] > 0
```

### T6.3 — All six timeframes present in packet

```python
d = packet.to_dict()
for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
    assert tf in d["timeframes"], f"Missing timeframe: {tf}"
    assert d["timeframes"][tf]["count"] > 0
```

### T6.4 — Timestamps in packet are UTC ISO8601 strings

```python
from datetime import datetime, timezone

as_of = datetime.fromisoformat(packet.as_of_utc.replace("Z", "+00:00"))
assert as_of.tzinfo is not None
```

### T6.5 — `is_trusted()` returns True for clean EURUSD packet

```python
assert packet.is_trusted() is True
```

### T6.6 — Packet written to correct output path

```python
import os
packet_path = "market_data_officer/state/packets/EURUSD_market_packet.json"
# After run_officer.py --instrument EURUSD
assert os.path.exists(packet_path)
```

---

## Group 7 — CLI entry point

### T7.1 — Help flag works

```bash
python run_officer.py --help
# Must exit 0 and show usage
```

### T7.2 — Full run completes without exception

```bash
python run_officer.py --instrument EURUSD
# Expected: no unhandled exceptions, packet file written
```

### T7.3 — Output confirms packet quality in terminal

The CLI must print something like:

```
Market packet built: EURUSD
  as_of_utc: 2026-03-06T12:00:00Z
  data_quality: validated
  stale: False
  partial: False
  flags: []
```

---

## Phase 2 sign-off checklist

Before marking Phase 2 complete, confirm:

- [ ] All 7 test groups pass
- [ ] `features.structure`, `features.imbalance`, `features.compression` are all `null` in serialized packet
- [ ] No raw Parquet reads in `officer/loader.py`
- [ ] No feed pipeline calls anywhere in `officer/`
- [ ] All four stub files exist and return `None`
- [ ] All stubs have docstrings
- [ ] Market Packet JSON validates against v1 schema
- [ ] `is_trusted()` returns `True` for clean EURUSD packet
- [ ] `run_officer.py --instrument EURUSD` completes end-to-end
- [ ] Packet file written to `state/packets/EURUSD_market_packet.json`
- [ ] XAUUSD handled gracefully as `unverified` without crashing
