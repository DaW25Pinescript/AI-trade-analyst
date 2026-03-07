# CONTRACTS.md — Phase 3D: v2 Packet Schema and Reader API

## Market Packet v2 — Full Schema

```json
{
  "schema_version": "market_packet_v2",
  "instrument": "EURUSD",
  "as_of_utc": "2026-03-07T10:15:00Z",

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
      "atr_14": 0.00234,
      "volatility_regime": "normal",
      "momentum": 0.27,
      "ma_50": 1.08420,
      "ma_200": 1.07910,
      "swing_high": 1.08901,
      "swing_low": 1.07630,
      "rolling_range": 0.01380,
      "session_context": "london"
    },
    "structure": null,
    "imbalance": null,
    "compression": null
  },

  "state_summary": {
    "trend_1h": "bullish",
    "trend_4h": "bullish",
    "trend_1d": "neutral",
    "volatility_regime": "normal",
    "momentum_state": "expanding",
    "session_context": "london",
    "data_quality": "validated"
  },

  "quality": {
    "manifest_valid": true,
    "all_timeframes_present": true,
    "staleness_minutes": 4,
    "stale": false,
    "partial": false,
    "flags": []
  },

  "structure": {
    "available": true,
    "source_engine_version": "phase_3c",
    "as_of": "2026-03-07T10:00:00Z",

    "regime": {
      "bias": "bullish",
      "last_bos_direction": "bullish",
      "last_mss_direction": null,
      "trend_state": "trending",
      "structure_quality": "clean",
      "source_timeframe": "4h"
    },

    "recent_events": [
      {
        "type": "bos_bull",
        "time": "2026-03-07T08:00:00Z",
        "timeframe": "1h",
        "reference_price": 1.08642
      },
      {
        "type": "bos_bull",
        "time": "2026-03-06T20:00:00Z",
        "timeframe": "4h",
        "reference_price": 1.08200
      }
    ],

    "liquidity": {
      "1h": {
        "active_count": 3,
        "nearest_above": {
          "type": "prior_day_high",
          "price": 1.08720,
          "scope": "external_liquidity",
          "status": "active"
        },
        "nearest_below": {
          "type": "equal_lows",
          "price": 1.08410,
          "scope": "internal_liquidity",
          "status": "active"
        }
      },
      "4h": {
        "active_count": 2,
        "nearest_above": {
          "type": "prior_week_high",
          "price": 1.09140,
          "scope": "external_liquidity",
          "status": "active"
        },
        "nearest_below": null
      }
    },

    "active_fvg_zones": [
      {
        "id": "fvg_003",
        "fvg_type": "bullish_fvg",
        "zone_high": 1.08620,
        "zone_low": 1.08475,
        "zone_size": 0.00145,
        "status": "open",
        "timeframe": "1h",
        "origin_time": "2026-03-07T06:00:00Z"
      },
      {
        "id": "fvg_007",
        "fvg_type": "bearish_fvg",
        "zone_high": 1.09140,
        "zone_low": 1.09010,
        "zone_size": 0.00130,
        "status": "partially_filled",
        "timeframe": "4h",
        "origin_time": "2026-03-06T12:00:00Z"
      }
    ]
  }
}
```

---

## Structure block — unavailable state

When structure packets are missing or stale:

```json
"structure": {
  "available": false,
  "source_engine_version": null,
  "as_of": null,
  "regime": null,
  "recent_events": null,
  "liquidity": null,
  "active_fvg_zones": null
}
```

The Officer must produce a valid v2 packet in this state. No crash, no exception propagation.

---

## Python dataclasses — Phase 3D additions

Add to `officer/contracts.py`:

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class StructureRegime:
    bias: str                          # "bullish" | "bearish" | "neutral"
    last_bos_direction: Optional[str]
    last_mss_direction: Optional[str]
    trend_state: str                   # "trending" | "ranging" | "unknown"
    structure_quality: str             # "clean" | "choppy" | "unknown"
    source_timeframe: str              # "4h" | "1h" | "15m"

@dataclass
class StructureRecentEvent:
    type: str                          # "bos_bull" | "bos_bear" | "mss_bull" | "mss_bear"
    time: str                          # ISO8601 UTC
    timeframe: str
    reference_price: float

@dataclass
class LiquidityNearest:
    type: str                          # level type e.g. "prior_day_high"
    price: float
    scope: str                         # "external_liquidity" | "internal_liquidity" | "unclassified"
    status: str                        # "active" | "swept"

@dataclass
class LiquidityTimeframeSummary:
    active_count: int
    nearest_above: Optional[LiquidityNearest]
    nearest_below: Optional[LiquidityNearest]

@dataclass
class ActiveFVGZone:
    id: str
    fvg_type: str                      # "bullish_fvg" | "bearish_fvg"
    zone_high: float
    zone_low: float
    zone_size: float
    status: str                        # "open" | "partially_filled"
    timeframe: str
    origin_time: str                   # ISO8601 UTC

@dataclass
class StructureBlock:
    available: bool
    source_engine_version: Optional[str] = None
    as_of: Optional[str] = None
    regime: Optional[StructureRegime] = None
    recent_events: Optional[list[StructureRecentEvent]] = None
    liquidity: Optional[dict[str, LiquidityTimeframeSummary]] = None
    active_fvg_zones: Optional[list[ActiveFVGZone]] = None

    @classmethod
    def unavailable(cls) -> "StructureBlock":
        """Factory for the unavailable state."""
        return cls(available=False)

@dataclass
class MarketPacketV2:
    # --- all Phase 2 / v1 fields preserved ---
    instrument: str
    as_of_utc: str
    source: dict
    timeframes: dict
    features: "FeatureBlock"
    state_summary: "StateSummary"
    quality: "QualityBlock"

    # --- v2 addition ---
    structure: StructureBlock

    def to_dict(self) -> dict:
        """Serialize to Market Packet v2 JSON structure."""
        ...

    def is_trusted(self) -> bool:
        """True if packet is validated, not stale, not partial."""
        return (
            not self.quality.stale
            and not self.quality.partial
            and self.quality.manifest_valid
            and self.state_summary.data_quality == "validated"
        )

    def has_structure(self) -> bool:
        """
        True if structure block is available AND at least one sub-field is non-null.
        available=True with all null sub-fields is treated as unavailable.
        """
        return (
            self.structure.available
            and any([
                self.structure.regime is not None,
                self.structure.recent_events is not None,
                self.structure.liquidity is not None,
                self.structure.active_fvg_zones is not None,
            ])
        )
```

---

## Structure reader API (`structure/reader.py`)

```python
from pathlib import Path
from datetime import datetime, timezone, timedelta

STRUCTURE_OUTPUT_DIR = Path("market_data_officer/structure/output")
STRUCTURE_STALENESS_MINUTES = 120  # configurable

def load_structure_packet(instrument: str, timeframe: str) -> dict | None:
    """
    Load the latest structure packet JSON for an instrument/timeframe.
    Returns None if file does not exist or cannot be parsed.
    Never raises on missing files.
    """
    path = STRUCTURE_OUTPUT_DIR / f"{instrument.lower()}_{timeframe}_structure.json"
    if not path.exists():
        return None
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def load_structure_summary(instrument: str,
                           timeframes: list[str] = ("15m", "1h", "4h")) -> dict:
    """
    Load and merge structure packets across timeframes into a summary dict.
    Missing timeframes are skipped — not an error.
    """
    return {
        tf: load_structure_packet(instrument, tf)
        for tf in timeframes
        if load_structure_packet(instrument, tf) is not None
    }

def structure_is_available(instrument: str,
                            timeframes: list[str] = ("15m", "1h", "4h")) -> bool:
    """
    Returns True if at least one valid, non-stale structure packet exists.
    """
    for tf in timeframes:
        packet = load_structure_packet(instrument, tf)
        if packet and _is_fresh(packet):
            return True
    return False

def _is_fresh(packet: dict) -> bool:
    """Returns True if packet as_of is within staleness threshold."""
    try:
        as_of = datetime.fromisoformat(packet["as_of"].replace("Z", "+00:00"))
        age_minutes = (datetime.now(timezone.utc) - as_of).total_seconds() / 60
        return age_minutes <= STRUCTURE_STALENESS_MINUTES
    except Exception:
        return False
```

---

## `recent_events` assembly rule

Select last 5 BOS/MSS events across all active timeframes, sorted by time descending:

```python
def assemble_recent_events(packets: dict[str, dict],
                           max_events: int = 5) -> list[StructureRecentEvent]:
    all_events = []
    for tf, packet in packets.items():
        for event in packet.get("events", []):
            if event["type"] in ("bos_bull", "bos_bear", "mss_bull", "mss_bear"):
                all_events.append(StructureRecentEvent(
                    type=event["type"],
                    time=event["time"],
                    timeframe=tf,
                    reference_price=event["reference_price"],
                ))
    all_events.sort(key=lambda e: e.time, reverse=True)
    return all_events[:max_events]
```

---

## `liquidity` summary assembly rule

For each timeframe, find the nearest active level above and below current price:

```python
def assemble_liquidity_summary(packets: dict[str, dict],
                                current_price: float) -> dict[str, LiquidityTimeframeSummary]:
    summary = {}
    for tf, packet in packets.items():
        active_levels = [l for l in packet.get("liquidity", [])
                         if l["status"] == "active"]
        above = [l for l in active_levels if l["price"] > current_price]
        below = [l for l in active_levels if l["price"] < current_price]

        nearest_above = min(above, key=lambda l: l["price"] - current_price) if above else None
        nearest_below = max(below, key=lambda l: l["price"]) if below else None

        summary[tf] = LiquidityTimeframeSummary(
            active_count=len(active_levels),
            nearest_above=_to_liquidity_nearest(nearest_above),
            nearest_below=_to_liquidity_nearest(nearest_below),
        )
    return summary
```

---

## Schema evolution rule

`market_packet_v1` consumers are not broken by v2. The only change is:
- `schema_version` string changes from `market_packet_v1` to `market_packet_v2`
- New top-level key `structure` is added

All existing v1 keys (`source`, `timeframes`, `features`, `state_summary`, `quality`) are present and unchanged in v2.
