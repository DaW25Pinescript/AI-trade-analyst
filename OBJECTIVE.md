# OBJECTIVE.md — Market Data Officer: What It Must Do and Why

## Strategic framing

Think of the feed as a verified database. The Market Data Officer is the query layer — it reads from that database and assembles a structured briefing that every downstream AI agent can reason over directly.

Without the Officer, downstream agents would need to read raw CSVs, compute their own features, handle their own quality checks, and make their own decisions about what "the market" looks like. That is duplicated logic, fragile, and untestable.

With the Officer, every agent gets a single consistent market packet — same schema, same provenance, same quality signals — every time.

---

## What the Officer must deliver

### 1. Package loader

Read the feed's validated hot package exports:
- Load hot CSV files per timeframe
- Parse the JSON manifest
- Validate manifest integrity before loading data
- Return typed, UTC-aware DataFrames

The Officer reads from `market_data/packages/latest/`. It does **not** read raw Parquet directly. Hot packages are the contract surface between feed and Officer.

### 2. Read-side quality checks

Before building any packet, the Officer must verify:
- Manifest file exists
- All expected timeframe CSVs exist
- Row counts meet minimum thresholds
- Timestamps are monotonic ascending per timeframe
- Last bar timestamps are reasonably current (staleness check)
- No duplicate timestamps within a timeframe
- `quality_flag` values are acceptable

If checks fail, degrade gracefully — emit a `partial` or `stale` packet with a quality marker. Do not crash. Do not silently continue.

### 3. Core feature computation

Compute deterministic, numerically stable features from loaded timeframe data:

| Feature | Description |
|---|---|
| `atr_14` | Average True Range, 14-period, on 1h bars |
| `volatility_regime` | `low` / `normal` / `expanding` based on ATR vs rolling ATR |
| `momentum` | Rate-of-change of close, 14-period, on 1h bars |
| `ma_50` | 50-period SMA of close on 1h bars |
| `ma_200` | 200-period SMA of close on 1h bars |
| `swing_high` | Most recent swing high (pivot high) on 1h bars |
| `swing_low` | Most recent swing low (pivot low) on 1h bars |
| `rolling_range` | High-Low range over last 20 bars on 1h |
| `session_context` | `asian` / `london` / `new_york` / `overlap` based on `as_of_utc` |

These features must be deterministic — same input data always produces same feature values.

### 4. Advanced feature stubs

Create empty module files for future structure/liquidity logic. Each stub must:
- Exist as a real Python file
- Contain a properly typed function signature
- Return `None` or `{}` explicitly
- Include a docstring explaining what Phase 3/4 will implement

Stubs required:
- `bos_detector.py` → `detect_bos(df: pd.DataFrame) -> None`
- `fvg_detector.py` → `detect_fvg(df: pd.DataFrame) -> None`
- `compression_detector.py` → `detect_compression(df: pd.DataFrame) -> None`
- `imbalance_detector.py` → `detect_imbalance(df: pd.DataFrame) -> None`

### 5. Market Packet assembly

Assemble the canonical Market Packet v1. Full schema is in `CONTRACTS.md`.

The packet includes:
- Instrument and timestamp metadata
- Source provenance (vendor, canonical TF, quality)
- Timeframe windows (rows as dicts, not DataFrames)
- Core features (populated)
- Structure/imbalance/compression fields (`null` — stubs)
- State summary (trend per TF, volatility regime, momentum state)

### 6. State summary builder

Derive a compact summary from features:

```python
{
  "trend_1h": "bullish" | "bearish" | "neutral",
  "trend_4h": "bullish" | "bearish" | "neutral",
  "trend_1d": "bullish" | "bearish" | "neutral",
  "volatility_regime": "low" | "normal" | "expanding",
  "momentum_state": "expanding" | "contracting" | "flat",
  "session_context": "asian" | "london" | "new_york" | "overlap",
  "data_quality": "validated" | "partial" | "stale"
}
```

Trend is derived from MA relationship: close > ma_50 > ma_200 = bullish, inverse = bearish, else neutral.

This summary is derivative and non-authoritative. It summarises; it does not replace raw bars.

### 7. Officer service / entry point

`service.py` provides the top-level orchestrator:

```python
def build_market_packet(instrument: str) -> MarketPacket:
    ...

def refresh_from_latest_exports(instrument: str) -> MarketPacket:
    ...

def validate_package_manifest(instrument: str) -> ValidationResult:
    ...
```

`run_officer.py` is the CLI entry point:

```bash
python run_officer.py --instrument EURUSD
python run_officer.py --instrument EURUSD --output-path state/packets/
```

---

## What the Officer explicitly does NOT do

| Out of scope | Owner |
|---|---|
| Vendor HTTP fetch | `feed/fetch.py` |
| bi5 decode | `feed/decode.py` |
| Canonical archive writes | `feed/pipeline.py` |
| Resampling truth rules | `feed/resample.py` |
| BOS / FVG / structure logic | Phase 3 (`structure/`) |
| Imbalance / liquidity sweep | Phase 4 |
| Analyst reasoning | Analyst engine |
| Arbiter verdicts | Senate / Arbiter layer |
| Chart screenshot ingestion | Optional human adjunct only |

---

## Definition of done

Phase 2 is complete when:

- The Officer reads validated feed outputs without touching vendor-fetch logic
- It constructs deterministic market packets per instrument
- It exposes rolling windows by timeframe
- It computes the full core feature set
- It emits auditable summaries with provenance and quality context
- It fails safely on stale, partial, or corrupt data
- Advanced feature stubs exist with correct signatures returning `None`
- Downstream agents can consume a market packet without needing screenshots or raw CSVs
- All acceptance criteria in `ACCEPTANCE_TESTS.md` pass
