# PR-AE-2 — Claude Code Agent Prompt

**Branch:** `feature/pr-ae-2-trend-momentum-lenses`
**Spec:** `docs/ANALYSIS_ENGINE_SPEC_v1.2.md` (controlling document)
**Depends on:** PR-AE-1 (merged — `LensBase`, `LensOutput`, `StructureLens` all proven)
**Acceptance criteria:** AC-2, AC-3, AC-4, AC-10

---

## Context

PR-AE-1 shipped: `LensBase` abstract class, `LensOutput` contract, `StructureLens`, data adapter, 40 tests. The base class and test patterns are proven. PR-AE-2 adds the remaining two v1 lenses using the same foundation.

Both lenses inherit from `LensBase` and follow identical contracts:
- `run()` never raises — always returns `LensOutput`
- On success: `status="success"`, `data=<complete schema>`, `error=None`
- On failure: `status="failed"`, `data=None`, `error=<message>`
- All fields always present — null where unavailable, never absent keys
- Partial data is a contract violation

**Regression baseline: 613 tests passing in `ai_analyst/`** (591 original + 22 from PR-AE-1 structure lens + 18 from PR-AE-1 adapter... verify exact count before starting).

---

## Files to Create (all new — no modifications to existing files)

| File | Purpose |
|---|---|
| `ai_analyst/lenses/trend.py` | `TrendLens` v1.0 implementation |
| `ai_analyst/lenses/momentum.py` | `MomentumLens` v1.0 implementation |
| `ai_analyst/tests/lenses/test_trend_lens.py` | TrendLens unit tests |
| `ai_analyst/tests/lenses/test_momentum_lens.py` | MomentumLens unit tests |

Also update (minimal, additive only):
| File | Change |
|---|---|
| `ai_analyst/lenses/__init__.py` | Add `TrendLens` and `MomentumLens` to exports |

**No other existing files modified.**

---

## Trend Lens — `ai_analyst/lenses/trend.py`

**Spec reference:** Section 4.4

`lens_id = "trend"`, `version = "v1.0"`

**Purpose:** Determine directional bias and trend quality using EMA alignment, price position, and slope. Provides directional context — NOT entry signals.

### Configuration (v1)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `timeframe` | str | required | Timeframe label (e.g. "1H") |
| `ema_fast` | int | 20 | Fast EMA period |
| `ema_slow` | int | 50 | Slow EMA period |
| `slope_lookback` | int | 10 | Bars to measure EMA slope |

### Output Schema (all fields always present)

```json
{
  "timeframe": "1H",
  "direction": {
    "ema_alignment": "bullish",
    "price_vs_ema": "above",
    "overall": "bullish"
  },
  "strength": {
    "slope": "positive",
    "trend_quality": "strong"
  },
  "state": {
    "phase": "continuation",
    "consistency": "aligned"
  }
}
```

### Field Value Contracts (enforced in `_validate_schema`)

| Field | Allowed values |
|---|---|
| `direction.ema_alignment` | `bullish` · `bearish` · `neutral` |
| `direction.price_vs_ema` | `above` · `below` · `mixed` |
| `direction.overall` | `bullish` · `bearish` · `ranging` |
| `strength.slope` | `positive` · `negative` · `flat` |
| `strength.trend_quality` | `strong` · `moderate` · `weak` |
| `state.phase` | `continuation` · `pullback` · `transition` |
| `state.consistency` | `aligned` · `conflicting` |

### Computation Logic

1. **EMA calculation:** Compute fast EMA and slow EMA from close prices.
2. **EMA alignment:** fast > slow = bullish, fast < slow = bearish, approximately equal = neutral.
3. **Price vs EMA:** current close above both = above, below both = below, between = mixed.
4. **Overall direction:** Derive from alignment + price position. Both bullish = bullish; both bearish = bearish; mixed/conflicting = ranging.
5. **Slope:** Measure change in slow EMA over `slope_lookback` bars. Positive/negative/flat (use a small threshold for flat, e.g. < 0.01% per bar).
6. **Trend quality:** Derived from slope magnitude + consistency of alignment over recent bars. Strong = clear slope + aligned; Moderate = slope present but mixed signals; Weak = flat slope or conflicting.
7. **Phase:** If price is above both EMAs and was above in recent bars = continuation. If price recently crossed below fast EMA but above slow = pullback. Otherwise = transition.
8. **Consistency:** If all direction signals agree = aligned. Any conflict = conflicting.

**numpy is available.** Use it for EMA computation (exponential weighted mean) and array operations.

---

## Momentum Lens — `ai_analyst/lenses/momentum.py`

**Spec reference:** Section 4.5

`lens_id = "momentum"`, `version = "v1.0"`

**Purpose:** Detect price impulse strength, acceleration/decay, and exhaustion/chop risk. Confluence amplifier and caution signal — NOT a primary entry trigger.

### Configuration (v1)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `timeframe` | str | required | Timeframe label (e.g. "1H") |
| `roc_lookback` | int | 10 | Rate of change lookback period |
| `momentum_smoothing` | int | 5 | Smoothing period for momentum |
| `signal_mode` | str | "roc" | Signal mode (roc only in v1) |

### Output Schema (all fields always present)

```json
{
  "timeframe": "1H",
  "direction": {
    "state": "bullish",
    "roc_sign": "positive"
  },
  "strength": {
    "impulse": "strong",
    "acceleration": "rising"
  },
  "state": {
    "phase": "expanding",
    "trend_alignment": "aligned"
  },
  "risk": {
    "exhaustion": false,
    "chop_warning": false
  }
}
```

### Field Value Contracts (enforced in `_validate_schema`)

| Field | Allowed values |
|---|---|
| `direction.state` | `bullish` · `bearish` · `neutral` |
| `direction.roc_sign` | `positive` · `negative` · `flat` |
| `strength.impulse` | `strong` · `moderate` · `weak` |
| `strength.acceleration` | `rising` · `falling` · `flat` |
| `state.phase` | `expanding` · `fading` · `reversing` · `flat` |
| `state.trend_alignment` | `aligned` · `conflicting` · `unknown` |
| `risk.exhaustion` | `true` · `false` (boolean) |
| `risk.chop_warning` | `true` · `false` (boolean) |

### Computation Logic

1. **ROC (Rate of Change):** `(close[-1] - close[-roc_lookback]) / close[-roc_lookback] * 100`
2. **Smoothed momentum:** Apply simple moving average of length `momentum_smoothing` to the ROC series.
3. **Direction state:** Smoothed ROC > threshold = bullish, < -threshold = bearish, within band = neutral.
4. **ROC sign:** Raw ROC positive/negative/flat (small threshold for flat).
5. **Impulse strength:** Magnitude of smoothed ROC. Thresholds: strong > 1.5%, moderate 0.5–1.5%, weak < 0.5%. (These are starting points — reasonable for most instruments on 1H.)
6. **Acceleration:** Compare current smoothed ROC to smoothed ROC N bars ago. Rising/falling/flat.
7. **Phase:**
   - `expanding`: impulse strong or moderate AND acceleration rising
   - `fading`: impulse was stronger N bars ago, now declining
   - `reversing`: ROC sign flipped in recent bars
   - `flat`: impulse weak AND acceleration flat
8. **Trend alignment:** Compare momentum direction to price trend (simple: is ROC sign consistent with price being above/below its short-term mean?). Aligned/conflicting/unknown (unknown if insufficient data).
9. **Exhaustion:** Trigger if ROC is extreme (> 2 standard deviations from mean over lookback window) AND acceleration is falling. This is a caution flag, not a reversal signal.
10. **Chop warning:** Trigger if ROC oscillates sign frequently over recent bars (e.g. 3+ sign changes in last 10 bars). Indicates ranging/noisy conditions.

**numpy is available.** Use it for ROC, SMA, standard deviation.

---

## Implementation Order (TDD)

Follow red/green/refactor. Write the test first, watch it fail, then implement.

### Trend Lens TDD Sequence

```
1. Write test_returns_lens_output_object           → RED (TrendLens doesn't exist)
2. Create minimal TrendLens skeleton                → GREEN
3. Write test_status_is_success_on_valid_data       → RED
4. Implement _compute() returning skeleton data     → GREEN
5. Write test_data_contains_all_required_fields     → RED
6. Implement full _compute() with all fields        → GREEN
7. Write field enum validation tests                → RED
8. Implement _validate_schema()                     → GREEN
9. Write failure behavior tests (empty data etc.)   → RED
10. Verify LensBase.run() catches and returns failed → GREEN
11. Write interpretation tests (bullish/bearish/ranging data) → RED
12. Implement EMA + classification logic            → GREEN
13. Refactor — clean up, run full suite
```

### Momentum Lens TDD Sequence

Same pattern:
```
1. Write test_returns_lens_output_object           → RED
2. Create minimal MomentumLens skeleton             → GREEN
3. Write test_status_is_success_on_valid_data       → RED
4. Implement _compute() skeleton                    → GREEN
5. Write test_data_contains_all_required_fields     → RED
6. Implement full _compute()                        → GREEN
7. Write field enum + boolean type tests            → RED
8. Implement _validate_schema()                     → GREEN
9. Write failure behavior tests                     → RED
10. Verify clean failure handling                    → GREEN
11. Write interpretation tests (trending/ranging/choppy) → RED
12. Implement ROC + phase + risk logic              → GREEN
13. Refactor — clean up, run full suite
```

---

## Test Fixtures

Reuse the fixture pattern from PR-AE-1 (`test_structure_lens.py`). Each test file needs:

- `make_bullish_price_data(n=120)` — clear uptrend (use `np.linspace` ascending + noise)
- `make_bearish_price_data(n=120)` — clear downtrend (use `np.linspace` descending + noise)
- `make_noisy_price_data(n=120)` — ranging/choppy (flat mean + noise)
- `make_insufficient_data(n=5)` — too few bars for calculation
- `DEFAULT_CONFIG` — default config dict with all params

Use `np.random.seed()` for reproducibility.

### Test Classes per Lens (minimum coverage)

**TrendLens tests (~18-22 tests):**

| Class | Tests | What it proves |
|---|---|---|
| `TestTrendLensOutputSchema` | ~6 | Returns LensOutput, status success, all fields present, enum values valid |
| `TestTrendLensFailureBehavior` | ~5 | Insufficient data → failed, never raises, partial data never returned, lens_id/version always present |
| `TestTrendLensInterpretation` | ~5 | Bullish data → bullish/ranging, bearish data → bearish/ranging, noisy data → ranging/mixed |
| `TestTrendLensConfig` | ~2 | Custom EMA periods respected, timeframe passed through |

**MomentumLens tests (~18-22 tests):**

| Class | Tests | What it proves |
|---|---|---|
| `TestMomentumLensOutputSchema` | ~6 | Returns LensOutput, status success, all fields present, enum values valid, risk fields are boolean |
| `TestMomentumLensFailureBehavior` | ~5 | Same pattern as above |
| `TestMomentumLensInterpretation` | ~5 | Strong trend → expanding/strong impulse, ranging → weak/flat, choppy → chop_warning |
| `TestMomentumLensConfig` | ~2 | Custom ROC lookback respected, timeframe passed through |

---

## Hard Constraints

- No modifications to existing files (except `__init__.py` export additions)
- No snapshot builder — that's PR-AE-3
- No persona or governance changes
- No live API calls in tests — frozen fixture data only
- numpy is acceptable — already in the project
- All fields always present — null where unavailable, never absent keys
- A lens must never partially return data — valid schema OR clean failure
- Each lens must never raise from `run()` — always returns `LensOutput`

---

## Verification Checklist (run before opening PR)

```bash
# 1. All new tests pass
python -m pytest ai_analyst/tests/lenses/test_trend_lens.py -v
python -m pytest ai_analyst/tests/lenses/test_momentum_lens.py -v

# 2. All PR-AE-1 tests still pass
python -m pytest ai_analyst/tests/lenses/ -v

# 3. Full regression check — must be >= 613
python -m pytest ai_analyst/ --tb=short -q 2>&1 | tail -5

# 4. Only expected files changed
git diff --name-only main
# Expected: only files under ai_analyst/lenses/ and ai_analyst/tests/lenses/

# 5. AC-2: Trend Lens valid schema — all fields present
# Covered by TestTrendLensOutputSchema

# 6. AC-3: Momentum Lens valid schema — all fields present
# Covered by TestMomentumLensOutputSchema

# 7. AC-4: Clean failure on both lenses (extends PR-AE-1 proof)
# Covered by failure behavior test classes

# 8. AC-10: Existing tests green
# Covered by step 3 above
```

---

## PR Description

```
PR-AE-2: Trend Lens + Momentum Lens

Completes the v1 lens set for P1 (Lens Engine):
- ai_analyst/lenses/trend.py: TrendLens v1.0 — EMA alignment, slope, trend quality, phase
- ai_analyst/lenses/momentum.py: MomentumLens v1.0 — ROC impulse, acceleration, exhaustion/chop risk
- ai_analyst/tests/lenses/test_trend_lens.py: unit tests
- ai_analyst/tests/lenses/test_momentum_lens.py: unit tests
- ai_analyst/lenses/__init__.py: updated exports

Closes AC-2 (trend lens schema), AC-3 (momentum lens schema).
Extends AC-4 (clean failure) to both new lenses.
AC-10 (regression): 613 baseline → [613 + N new], all green.

No existing files modified (except __init__.py exports).
Next: PR-AE-3 (Lens registry + Evidence Snapshot Builder + derived signals).

Spec: docs/ANALYSIS_ENGINE_SPEC_v1.2.md, Sections 4.4, 4.5
```
