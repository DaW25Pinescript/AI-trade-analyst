# Phase A3 — Structure Short vs Medium Comparison Report

**Split**: train
**Total comparison bars**: 9845
**Short params**: lookback_bars=80, pivot_window=2 (horizon=4 bars)
**Medium params**: lookback_bars=250, pivot_window=9 (horizon=12 bars)

## 1. Agreement Matrix

### Counts

| short \\ medium | bullish | bearish | ranging | **total** |
|-----------------|---------|---------|---------|-----------|
| bullish | 1258 | 620 | 1297 | 3175 |
| bearish | 845 | 569 | 1013 | 2427 |
| ranging | 1678 | 866 | 1699 | 4243 |
| **total** | 3781 | 2055 | 4009 | 9845 |

### Percentages

| short \\ medium | bullish | bearish | ranging |
|-----------------|---------|---------|---------|
| bullish | 12.8% | 6.3% | 13.2% |
| bearish | 8.6% | 5.8% | 10.3% |
| ranging | 17.0% | 8.8% | 17.3% |

**Overall agreement rate**: 35.8%

## 2. Accuracy by Agreement State

### Both Bullish
- 4-bar forward accuracy: 54.8% (n=1258)
- 12-bar forward accuracy: 57.3% (n=1258)

### Both Bearish
- 4-bar forward accuracy: 41.5% (n=569)
- 12-bar forward accuracy: 40.9% (n=565)

### Disagreement: Short Bullish / Medium Bearish
- Count: 620
- Short (bullish) correct at 4-bar: 48.4% (n=616)
- Medium (bearish) correct at 4-bar: 51.0% (n=616)
- Short (bullish) correct at 12-bar: 55.0% (n=614)
- Medium (bearish) correct at 12-bar: 44.6% (n=614)

### Disagreement: Short Bearish / Medium Bullish
- Count: 845
- Short (bearish) correct at 4-bar: 49.7% (n=845)
- Medium (bullish) correct at 4-bar: 49.9% (n=845)
- Short (bearish) correct at 12-bar: 44.5% (n=845)
- Medium (bullish) correct at 12-bar: 55.5% (n=845)

### Short Ranging / Medium Has a View
- Count: 2544
- Medium bullish correct at 4-bar: 54.6% (n=1678)
- Medium bullish correct at 12-bar: 57.0% (n=1678)
- Medium bearish correct at 4-bar: 46.1% (n=866)
- Medium bearish correct at 12-bar: 44.6% (n=864)

### Medium Ranging / Short Has a View
- Count: 2310
- Short bullish correct at 4-bar: 56.2% (n=1297)
- Short bullish correct at 12-bar: 57.4% (n=1297)
- Short bearish correct at 4-bar: 47.9% (n=1013)
- Short bearish correct at 12-bar: 43.9% (n=1013)

## 3. Transition Analysis

Total bar-to-bar transitions: 9844

| Pattern | Count | % |
|---------|-------|---|
| Short flips, medium steady | 1324 | 13.4% |
| Medium flips, short steady | 270 | 2.7% |
| Both flip | 74 | 0.8% |
| Neither flips | 8176 | 83.1% |

### Do short flips against steady medium predict reversals?

When short flips direction while medium stays steady, the short's NEW direction is correct (4-bar forward) 51.6% of the time (n=669).

## 4. Signal Value Summary

### Individual Instance Accuracy (directional calls only, rolling 1-bar)

- **Short alone** (4-bar forward): 51.1% (n=5598)
- **Medium alone** (12-bar forward): 52.1% (n=5824)

### Agreement vs Individual Accuracy

- **Both agree** (4-bar forward): 50.7% (n=1823)
- **Both agree** (12-bar forward): 52.2% (n=1823)

Agreement vs short alone (4-bar): -0.3%
Agreement vs medium alone (12-bar): +0.1%

**Does agreement predict better accuracy than either alone?** Yes

### Disagreement Analysis

- When they disagree (opposite directional calls): short correct at 4-bar 718/1461 (49.1%)
- When they disagree: medium correct at 12-bar 743/1459 (50.9%)

### Strongest Disagreement Patterns

- **Short bullish / Medium bearish** (n=620): short correct at 4-bar: 48.4%, medium correct at 12-bar: 44.6%
- **Short bearish / Medium bullish** (n=845): short correct at 4-bar: 49.7%, medium correct at 12-bar: 55.5%

### High Confidence Subset

High confidence = both agree on direction (bullish or bearish).
- Count: 1823 / 9845 (18.5% of all bars)
- 4-bar accuracy: 50.7%
- 12-bar accuracy: 52.2%

## 5. Raw Data

Full bar-by-bar comparison saved to: `autotune/results/phase_a3_comparison_data.csv`
