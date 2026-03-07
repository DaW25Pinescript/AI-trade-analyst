# OBJECTIVE.md — Phase 3D: Officer Integration

## What Phase 3D does and why

Phases 3A through 3C built a deterministic structure engine that computes explicit ICT-style structural state — confirmed swings, BOS, MSS, liquidity levels, sweep outcomes, FVG zones, and regime summaries. Every object is numeric, auditable, and replay-safe.

Phase 2 built the Market Data Officer, which produces a market packet consumed by downstream AI agents. That packet currently contains feed-derived features and state summaries — but no structural context.

Phase 3D closes that gap. It connects the structure engine into the Officer, producing **Market Packet v2** — a single unified packet that gives downstream agents everything they need: price data, core features, and explicit structural state, in one schema-versioned JSON object.

Think of it like this: the feed is the raw database, the structure engine is the analytics layer that runs queries on it, and the Officer is the report that lands on the analyst's desk. Phase 3D is the moment the report starts including the analytics output, not just the raw numbers.

---

## What the Officer gains in 3D

### 1. Structure read API (`structure/reader.py`)

A clean, Officer-facing read interface over structure engine outputs. The Officer calls this API — it does not read structure JSON files directly via hardcoded paths.

```python
def load_structure_packet(instrument: str, timeframe: str) -> StructurePacket | None:
    """Load the latest structure packet for an instrument/timeframe. Returns None if unavailable."""

def load_structure_summary(instrument: str) -> StructureSummary | None:
    """Load a compact cross-timeframe structure summary. Returns None if unavailable."""

def structure_is_available(instrument: str) -> bool:
    """Returns True if valid structure packets exist and are not stale."""
```

The reader handles: file existence checks, JSON parsing, staleness detection, and graceful None returns. It never raises on missing files.

### 2. `StructureBlock` dataclass (`officer/contracts.py`)

A typed container for the structure state that flows into the Officer packet:

```python
@dataclass
class StructureBlock:
    available: bool
    source_engine_version: str | None
    as_of: str | None
    regime: dict | None
    recent_events: list | None
    liquidity: dict | None
    active_fvg_zones: list | None
```

### 3. Market Packet v2 (`officer/contracts.py`)

Extends `MarketPacketV1` by adding `structure: StructureBlock` as a new top-level field. All v1 fields preserved unchanged.

```python
@dataclass
class MarketPacketV2:
    # --- all v1 fields preserved ---
    instrument: str
    as_of_utc: str
    source: dict
    timeframes: dict
    features: FeatureBlock
    state_summary: StateSummary
    quality: QualityBlock

    # --- v2 addition ---
    structure: StructureBlock
```

### 4. Officer service integration (`officer/service.py`)

`build_market_packet()` extended to:
1. Check if structure is available via `structure_is_available(instrument)`
2. If yes: load structure packets for all active timeframes, assemble `StructureBlock`
3. If no: assemble `StructureBlock` with `available=False`, all sub-fields `None`
4. Assemble and return `MarketPacketV2`

The Officer never crashes because structure is unavailable. It degrades gracefully.

---

## What flows into the structure block

### `regime`

Compact regime summary from the highest-confidence timeframe (4h preferred, fall back to 1h):

```json
{
  "bias": "bullish",
  "last_bos_direction": "bullish",
  "last_mss_direction": null,
  "trend_state": "trending",
  "structure_quality": "clean",
  "source_timeframe": "4h"
}
```

### `recent_events`

Last 5 confirmed BOS/MSS events across all active timeframes, sorted by time descending:

```json
[
  {
    "type": "bos_bull",
    "time": "2026-03-07T08:00:00Z",
    "timeframe": "1h",
    "reference_price": 1.08642
  }
]
```

Keep this compact — downstream agents need recency context, not full event history.

### `liquidity`

Per-timeframe active liquidity summary — levels that are currently `active` or `swept` but not yet resolved:

```json
{
  "1h": {
    "active_count": 3,
    "nearest_above": { "type": "prior_day_high", "price": 1.08720, "scope": "external_liquidity" },
    "nearest_below": { "type": "equal_lows", "price": 1.08410, "scope": "internal_liquidity" }
  },
  "4h": { ... }
}
```

Do not dump the full liquidity array. Downstream agents need orientation, not a raw list.

### `active_fvg_zones`

All `open` and `partially_filled` FVG zones across all active timeframes, sorted by proximity to current price (nearest first):

```json
[
  {
    "id": "fvg_003",
    "fvg_type": "bullish_fvg",
    "zone_high": 1.08620,
    "zone_low": 1.08475,
    "status": "open",
    "timeframe": "1h",
    "origin_time": "2026-03-07T06:00:00Z"
  }
]
```

---

## What Phase 3D explicitly does NOT include

| Out of scope | Reason |
|---|---|
| Cross-timeframe structure synthesis | Separate future phase |
| Confluence scoring | Never in structure engine |
| Trade signal generation | Never in this stack |
| Analyst persona logic | Downstream layer |
| Parquet structure output | Deferred — JSON is sufficient |
| New instruments | Feed decision, not 3D |
| New timeframes | Separate config decision |
| Rewriting structure engine modules | 3A/3B/3C are locked |
| Rewriting Officer v1 fields | v1 fields are preserved unchanged |

---

## Definition of done

Phase 3D is complete when:
- `structure/reader.py` provides a clean Officer-facing read API
- `StructureBlock` dataclass is typed and complete
- `MarketPacketV2` extends v1 with `structure` block
- Officer assembles v2 packet with structure when available
- Officer assembles v2 packet with `available=False` gracefully when structure is missing
- `schema_version` is `market_packet_v2` in all Officer output
- All 3A/3B/3C/Phase 2 tests still pass
- Feed pipeline untouched
- All 3D test groups pass for EURUSD and XAUUSD
