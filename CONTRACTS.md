# CONTRACTS.md — Market Packet v1 Schema

## Why this file matters most

The Market Packet is the single most important JSON schema in the entire AI Trade Analyst system. It defines exactly what every AI agent sees as "the market." Every analyst persona, every arbiter verdict, every senate deliberation starts from this packet.

Getting this contract right now — with reserved fields and clean placeholders — means future phases can populate advanced features without schema churn, without breaking downstream agents, and without rewriting analyst prompts.

---

## Market Packet v1 — Full Schema

```json
{
  "instrument": "EURUSD",
  "as_of_utc": "2026-03-06T12:00:00Z",

  "source": {
    "vendor": "dukascopy",
    "canonical_tf": "1m",
    "quality": "validated"
  },

  "timeframes": {
    "1m":  { "count": 3000, "rows": [...] },
    "5m":  { "count": 1200, "rows": [...] },
    "15m": { "count": 600,  "rows": [...] },
    "1h":  { "count": 240,  "rows": [...] },
    "4h":  { "count": 120,  "rows": [...] },
    "1d":  { "count": 30,   "rows": [...] }
  },

  "features": {
    "core": {
      "atr_14":            2.34,
      "volatility_regime": "normal",
      "momentum":          0.27,
      "ma_50":             1.0842,
      "ma_200":            1.0791,
      "swing_high":        1.0901,
      "swing_low":         1.0763,
      "rolling_range":     0.0138,
      "session_context":   "london"
    },
    "structure":   null,
    "imbalance":   null,
    "compression": null
  },

  "state_summary": {
    "trend_1h":          "bullish",
    "trend_4h":          "bullish",
    "trend_1d":          "neutral",
    "volatility_regime": "normal",
    "momentum_state":    "expanding",
    "session_context":   "london",
    "data_quality":      "validated"
  },

  "quality": {
    "manifest_valid":      true,
    "all_timeframes_present": true,
    "staleness_minutes":   4,
    "stale":               false,
    "partial":             false,
    "flags":               []
  }
}
```

---

## Field definitions

### Top level

| Field | Type | Description |
|---|---|---|
| `instrument` | string | Instrument symbol e.g. `EURUSD` |
| `as_of_utc` | ISO8601 string | Timestamp the packet was assembled |

### `source`

| Field | Type | Description |
|---|---|---|
| `vendor` | string | Source vendor e.g. `dukascopy` |
| `canonical_tf` | string | Canonical truth timeframe, always `1m` |
| `quality` | string | `validated` \| `partial` \| `stale` \| `unverified` |

### `timeframes`

Each key is a timeframe label (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`).

Each value:

| Field | Type | Description |
|---|---|---|
| `count` | int | Number of rows in this window |
| `rows` | list of dicts | OHLCV rows as `{timestamp_utc, open, high, low, close, volume}` |

Row schema per bar:

```json
{
  "timestamp_utc": "2026-03-06T11:00:00Z",
  "open":   1.0831,
  "high":   1.0847,
  "low":    1.0823,
  "close":  1.0842,
  "volume": 1842.0
}
```

### `features.core`

| Field | Type | Phase |
|---|---|---|
| `atr_14` | float | Phase 2 |
| `volatility_regime` | `low` \| `normal` \| `expanding` | Phase 2 |
| `momentum` | float | Phase 2 |
| `ma_50` | float | Phase 2 |
| `ma_200` | float | Phase 2 |
| `swing_high` | float | Phase 2 |
| `swing_low` | float | Phase 2 |
| `rolling_range` | float | Phase 2 |
| `session_context` | `asian` \| `london` \| `new_york` \| `overlap` | Phase 2 |

### `features.structure` — Phase 3, stub now

```json
null
```

Future shape (do not implement yet):

```json
{
  "bos": [...],
  "swing_structure": "higher_highs_higher_lows",
  "trend_state": "bullish"
}
```

### `features.imbalance` — Phase 4, stub now

```json
null
```

Future shape (do not implement yet):

```json
{
  "fvg_zones": [...],
  "imbalance_bias": "bullish"
}
```

### `features.compression` — Phase 4, stub now

```json
null
```

Future shape (do not implement yet):

```json
{
  "compression_state": "compressed",
  "range_percentile": 12.4
}
```

### `state_summary`

| Field | Type | Derivation |
|---|---|---|
| `trend_1h` | `bullish` \| `bearish` \| `neutral` | close vs ma_50 vs ma_200 |
| `trend_4h` | `bullish` \| `bearish` \| `neutral` | same logic on 4h bars |
| `trend_1d` | `bullish` \| `bearish` \| `neutral` | same logic on 1d bars |
| `volatility_regime` | `low` \| `normal` \| `expanding` | ATR vs rolling ATR baseline |
| `momentum_state` | `expanding` \| `contracting` \| `flat` | ROC direction |
| `session_context` | `asian` \| `london` \| `new_york` \| `overlap` | UTC hour of `as_of_utc` |
| `data_quality` | `validated` \| `partial` \| `stale` | from quality block |

### `quality`

| Field | Type | Description |
|---|---|---|
| `manifest_valid` | bool | Manifest file parsed successfully |
| `all_timeframes_present` | bool | All 6 TF CSVs found |
| `staleness_minutes` | int | Minutes since last bar in 1m file |
| `stale` | bool | True if staleness > threshold (e.g. 60 min during market hours) |
| `partial` | bool | True if some but not all TFs loaded |
| `flags` | list of strings | Human-readable quality issues e.g. `["4h_missing", "stale_1d"]` |

---

## Trend derivation logic

```python
def derive_trend(df: pd.DataFrame) -> str:
    """
    Derives trend state from MA relationship on a given timeframe DataFrame.
    Returns 'bullish', 'bearish', or 'neutral'.
    """
    if len(df) < 200:
        return "neutral"
    close = df["close"].iloc[-1]
    ma50  = df["close"].rolling(50).mean().iloc[-1]
    ma200 = df["close"].rolling(200).mean().iloc[-1]
    if close > ma50 > ma200:
        return "bullish"
    if close < ma50 < ma200:
        return "bearish"
    return "neutral"
```

---

## Session context logic

```python
SESSION_WINDOWS = {
    "asian":    (0,  8),
    "london":   (8,  13),
    "overlap":  (13, 17),
    "new_york": (17, 21),
}

def derive_session(as_of_utc: datetime) -> str:
    hour = as_of_utc.hour
    for session, (start, end) in SESSION_WINDOWS.items():
        if start <= hour < end:
            return session
    return "asian"  # outside all windows defaults to asian
```

---

## Python dataclass contracts

Implement these in `officer/contracts.py`:

```python
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

@dataclass
class CoreFeatures:
    atr_14:            float
    volatility_regime: str
    momentum:          float
    ma_50:             float
    ma_200:            float
    swing_high:        float
    swing_low:         float
    rolling_range:     float
    session_context:   str

@dataclass
class FeatureBlock:
    core:        CoreFeatures
    structure:   None = None   # Phase 3
    imbalance:   None = None   # Phase 4
    compression: None = None   # Phase 4

@dataclass
class StateSummary:
    trend_1h:          str
    trend_4h:          str
    trend_1d:          str
    volatility_regime: str
    momentum_state:    str
    session_context:   str
    data_quality:      str

@dataclass
class QualityBlock:
    manifest_valid:          bool
    all_timeframes_present:  bool
    staleness_minutes:       int
    stale:                   bool
    partial:                 bool
    flags:                   list[str] = field(default_factory=list)

@dataclass
class MarketPacket:
    instrument:    str
    as_of_utc:     str
    source:        dict
    timeframes:    dict
    features:      FeatureBlock
    state_summary: StateSummary
    quality:       QualityBlock

    def to_dict(self) -> dict:
        """Serialize to the canonical Market Packet v1 JSON structure."""
        ...

    def is_trusted(self) -> bool:
        """Returns True only if packet is validated and not stale or partial."""
        return (
            not self.quality.stale
            and not self.quality.partial
            and self.quality.manifest_valid
            and self.state_summary.data_quality == "validated"
        )
```

---

## Schema evolution policy

- **Phase 2**: `features.core` populated. `structure`, `imbalance`, `compression` = `null`.
- **Phase 3**: `features.structure` populated. Core unchanged.
- **Phase 4**: `features.imbalance` and `features.compression` populated. Core and structure unchanged.

**Never remove or rename a field without a versioned migration.** Downstream analyst prompts depend on field names being stable. Adding fields is safe. Removing or renaming is a breaking change.

---

## Instrument policy

| Instrument | Status | Notes |
|---|---|---|
| `EURUSD` | `trusted` | Verified Phase 1A |
| `XAUUSD` | `provisional_until_verified` | Do not emit `validated` quality until Phase 1B sign-off |

If an instrument is not in the trusted list, the Officer must set:

```json
"source": { "quality": "unverified" }
"state_summary": { "data_quality": "unverified" }
"quality": { "flags": ["instrument_not_verified"] }
```
