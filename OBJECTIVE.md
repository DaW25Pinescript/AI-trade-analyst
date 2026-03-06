# OBJECTIVE.md — Phase 1B: XAUUSD Extension

## Why Phase 1B is a separate phase

XAUUSD is not simply "EURUSD with a different symbol." Gold has specific properties that make silent parsing errors highly likely if assumptions are carried over from FX:

| Property | EURUSD | XAUUSD | Risk |
|---|---|---|---|
| Price scale | 100,000 (5 decimal places) | Unknown — likely 1,000 but must be verified | 10x price error if wrong |
| Price range | ~0.80–1.50 | ~1,800–2,800 | Out-of-range check values differ entirely |
| Volume semantics | Tick volume, additive | May differ — lots, units, or absent | Silent volume corruption |
| Decimal precision | Pips at 4th decimal | Different pip structure | Misaligned OHLC spread |
| Session behaviour | 24h FX | Metals may have session gaps | Gap handling differences |

A 10x price scaling error on gold produces bars that look structurally valid — monotonic, positive, internally consistent — but are completely wrong numerically. The validation layer will not catch it because it cannot know what gold "should" be worth. Only external comparison catches it.

This is why Phase 1B exists as an isolated phase with an explicit verification gate.

---

## What Phase 1B must deliver

### 1. XAUUSD verification report

Before any code is committed to `config.py`, produce a written verification note (as a code comment block or a `docs/` markdown file) documenting:

- Raw Dukascopy bi5 source bytes decoded for at least one sample hour
- Decoded `ask_raw` and `bid_raw` integer values (before scaling)
- Applied `price_scale` and resulting `mid` price
- Comparison against TradingView XAUUSD for same timestamp: open, high, low, close
- Comparison against CMC Markets XAUUSD for same timestamp: open, high, low, close
- Assessment of volume: what does `ask_vol_raw + bid_vol_raw` represent? Is a divisor needed?
- Explicit conclusion: verified / partially verified / needs further investigation
- At least 5 bars compared, not just 1

This note is a required deliverable. It is not optional documentation.

### 2. Verified `InstrumentMeta` for XAUUSD

Only after the verification report is produced:

```python
"XAUUSD": InstrumentMeta(
    symbol="XAUUSD",
    price_scale=????,        # confirmed value from verification
    volume_divisor=????,     # confirmed value or None
    # verification_note: "Verified YYYY-MM-DD against TradingView + CMC, 5 bars"
)
```

If verification is incomplete or ambiguous, leave the stub and document exactly what remains unresolved. Do not guess.

### 3. End-to-end XAUUSD ingestion

With verified metadata:
- Dukascopy fetch for XAUUSD
- Tick decode using verified price scale
- Canonical 1m OHLCV archive: `market_data/canonical/XAUUSD_1m.parquet`
- Derived timeframes: 5m, 15m, 1h, 4h, 1d
- Hot package export
- Incremental update logic

### 4. Officer instrument status update

After XAUUSD canonical archive is validated, update the Officer's instrument policy from `provisional_until_verified` to `trusted`:

In `officer/contracts.py` or equivalent instrument registry:

```python
INSTRUMENT_STATUS = {
    "EURUSD": "trusted",
    "XAUUSD": "trusted",  # update only after Phase 1B sign-off
}
```

### 5. Phase 1A regression

All Phase 1A acceptance tests must continue to pass after Phase 1B changes. EURUSD ingestion must be unaffected.

---

## What Phase 1B explicitly does NOT include

| Out of scope | Reason |
|---|---|
| HistData seeding | Phase 1E |
| Incremental updater hardening | Phase 1C |
| Raw cache diagnostics | Phase 1D |
| New Officer features | Phase 2 is complete — do not modify |
| Any new instrument beyond XAUUSD | Future phase |

---

## Definition of done

Phase 1B is complete when:
- Verification report exists with at least 5 bars compared against both TradingView and CMC
- `InstrumentMeta` for XAUUSD is populated with confirmed values
- XAUUSD canonical archive builds cleanly
- XAUUSD prices are in plausible gold range (1,500–3,500 USD)
- All Phase 1B acceptance tests pass
- All Phase 1A acceptance tests still pass
- Officer emits `trusted` quality packets for XAUUSD
