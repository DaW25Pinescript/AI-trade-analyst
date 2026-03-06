# CONSTRAINTS.md — Phase 1B Hard Rules and Verification Protocol

## The verification gate is non-negotiable

This is the single most important constraint in Phase 1B.

**Do not populate `XAUUSD` in `INSTRUMENTS` dict until all of the following are true:**

1. At least 5 decoded XAUUSD bars have been compared against TradingView XAUUSD
2. At least 5 decoded XAUUSD bars have been compared against CMC Markets XAUUSD
3. Price scale has been confirmed — not assumed
4. Volume semantics have been explicitly documented
5. A written verification note exists in the codebase

This gate cannot be bypassed by:
- Assuming XAUUSD uses the same scale as EURUSD (it does not)
- Assuming a "likely" value of 1000 without confirmation
- Producing bars that look internally consistent but were never externally compared
- Declaring "close enough" without documenting the delta

If verification produces ambiguous results, the correct action is to document the ambiguity and leave the stub — not to guess and proceed.

---

## Verification protocol — step by step

### Step 1 — Fetch a sample hour

Choose a recent trading hour with known market activity (avoid weekends, holidays).

Fetch the raw bi5 file for that hour:
```
https://www.dukascopy.com/datafeed/XAUUSD/{year}/{month_zero_based}/{day}/{hour}h_ticks.bi5
```

### Step 2 — Decode raw integers before scaling

Print the first 5 rows of decoded data showing:
- `time_ms` offset
- `ask_raw` (raw integer, before division)
- `bid_raw` (raw integer, before division)
- `ask_vol_raw`
- `bid_vol_raw`

Do not apply price scale yet. First understand the raw values.

### Step 3 — Derive candidate mid price

Try candidate scales and compute mid:
```python
for candidate_scale in [100, 1000, 10000, 100000]:
    mid = ((ask_raw / candidate_scale) + (bid_raw / candidate_scale)) / 2
    print(f"scale={candidate_scale}: mid={mid:.4f}")
```

One of these should produce a value in the 1,500–3,500 USD range. That is the confirmed scale.

### Step 4 — Aggregate to 1m OHLCV

Using the confirmed scale, aggregate the sample hour to 1-minute OHLCV bars.

### Step 5 — Compare against TradingView

Open TradingView. Navigate to XAUUSD on the 1-minute chart. Find the same timestamp.

For at least 5 bars, record:

| Timestamp UTC | Decoded O | Decoded H | Decoded L | Decoded C | TV O | TV H | TV L | TV C | Delta |
|---|---|---|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

Acceptable parity: within 0.50 USD on gold (minor spread/source differences are expected).

### Step 6 — Compare against CMC Markets

Repeat the same comparison using CMC Markets XAUUSD chart.

### Step 7 — Document volume semantics

Examine `ask_vol_raw + bid_vol_raw` values. Determine:
- Are they in units that make sense as tick volume?
- Is a divisor needed to normalise?
- Are they zero or absent for some bars?
- Document conclusion explicitly

### Step 8 — Write verification note

Produce this comment block in `feed/config.py` above the XAUUSD entry:

```python
# XAUUSD Verification — [DATE]
# Verified by: [your name or "Phase 1B automated check"]
# Reference sources: TradingView XAUUSD, CMC Markets XAUUSD
# Bars compared: [N]
# Price scale confirmed: [value]
# Volume semantics: [description]
# Max OHLC delta vs TradingView: [value] USD
# Max OHLC delta vs CMC: [value] USD
# Status: VERIFIED / PARTIALLY VERIFIED / UNRESOLVED
# Notes: [any caveats]
```

---

## All Phase 1A rules carry forward

Every constraint from Phase 1A `CONSTRAINTS.md` applies to XAUUSD:

- UTC everywhere
- Canonical truth is 1m OHLCV
- Higher timeframes derived only, never fetched
- Validation before every write
- Instrument metadata controls all parsing assumptions
- Source abstraction boundary maintained
- Incremental append is idempotent
- No framework bloat

Do not relax any of these for XAUUSD.

---

## XAUUSD-specific additional constraints

### RULE X1 — Price range guard for XAUUSD

After decoding, all XAUUSD close prices must pass a plausibility check:

```python
XAUUSD_PRICE_RANGE = (1_500.0, 3_500.0)

def validate_xauusd_price_range(df: pd.DataFrame) -> None:
    out_of_range = ~df["close"].between(*XAUUSD_PRICE_RANGE)
    if out_of_range.any():
        raise ValueError(
            f"XAUUSD close prices out of plausible range "
            f"{XAUUSD_PRICE_RANGE}: {df.loc[out_of_range, 'close'].describe()}"
        )
```

This catches scale errors that pass structural validation.

### RULE X2 — Do not reuse EURUSD price range guards for XAUUSD

Phase 1A has a plausibility check that EURUSD closes are between 0.8 and 1.5. That check must not be applied to XAUUSD. Each instrument needs its own range constants. Centralise these in `config.py`.

### RULE X3 — Session gap behaviour must be documented

Gold may exhibit different session gap behaviour vs FX. If gaps are observed in the canonical archive at specific hours, document them rather than treating as errors. The validation layer should distinguish between:
- Genuine data gaps (missing bi5 files = no activity or source gap)
- Expected session gaps (if gold has thinner overnight hours)

### RULE X4 — Do not modify Officer internals to accommodate XAUUSD parsing

If the Officer needs updating for XAUUSD, it should be limited to the instrument status registry (`trusted` / `provisional`). No parsing logic, no new feature thresholds, no special-casing XAUUSD inside Officer modules.

---

## What "verified" means vs "assumed"

| State | Meaning | Action |
|---|---|---|
| Verified | Decoded bars match TradingView + CMC within tolerance, scale confirmed, volume documented | Populate `InstrumentMeta`, proceed |
| Partially verified | Price scale confirmed, volume ambiguous | Populate with `volume_divisor=None` and explicit note, proceed with caution |
| Unresolved | Price scale produces values outside plausible range, or bars don't match references | Leave stub, document findings, do not proceed |

Partial verification is acceptable if documented. Silent assumption is never acceptable.
