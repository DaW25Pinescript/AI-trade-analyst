# AutoTune Session Report: structure_short

## Session Info

| Field | Value |
|-------|-------|
| Session ID | `structure_short_20260319_084933` |
| Instance | `structure_short` |
| Harness Version | v1.0 |
| Ticker | GC=F (Gold Futures) |
| Train Period | 2024-04-01 to 2025-12-31 |
| Validation Period | 2026-01-02 to 2026-03-19 |
| Data Coverage | 9,872 / 10,097 bars (97.8%) |

## Parameters

| Parameter | Seed | Best Found | Bounds | Step |
|-----------|------|------------|--------|------|
| `lookback_bars` | 60 | **80** | 40–100 | 5 |
| `pivot_window` | 3 | **2** | 2–6 | 1 |

## Accuracy Summary

| Metric | Value |
|--------|-------|
| Baseline (seed) accuracy | 0.355956 |
| Best-found accuracy (train) | **0.364281** |
| Improvement | +0.008325 (+2.34%) |
| Validation accuracy (best params) | **0.312102** |
| Total iterations | 30 |
| Accepted | 3 |
| Rejected | 27 |

## Accuracy Progression

| Iter | Parameter | Change | Candidate Accuracy | Delta | Decision |
|------|-----------|--------|--------------------|-------|----------|
| 1 | lookback_bars | 60→55 | 0.338429 | -0.017526 | rejected |
| 2 | lookback_bars | 60→65 | 0.343378 | -0.012578 | rejected |
| 3 | pivot_window | 3→4 | 0.349901 | -0.006055 | rejected |
| 4 | pivot_window | 3→2 | 0.363251 | +0.007295 | **accepted** |
| 5 | lookback_bars | 60→55 | 0.330806 | -0.032445 | rejected |
| 6 | lookback_bars | 60→65 | 0.326747 | -0.036504 | rejected |
| 7 | lookback_bars | 60→50 | 0.338287 | -0.024964 | rejected |
| 8 | pivot_window | 2→3 | 0.355956 | -0.007295 | rejected |
| 9 | lookback_bars | 60→70 | 0.338538 | -0.024713 | rejected |
| 10 | lookback_bars | 60→40 | 0.364023 | +0.000772 | **accepted** |
| 11 | pivot_window | 2→3 | 0.358339 | -0.005683 | rejected |
| 12 | lookback_bars | 40→45 | 0.327696 | -0.036327 | rejected |
| 13 | lookback_bars | 40→75 | 0.331030 | -0.032993 | rejected |
| 14 | lookback_bars | 40→80 | 0.364281 | +0.000258 | **accepted** |
| 15 | lookback_bars | 80→85 | 0.327440 | -0.036841 | rejected |
| 16 | lookback_bars | 80→75 | 0.331030 | -0.033251 | rejected |
| 17 | pivot_window | 2→3 | 0.356250 | -0.008031 | rejected |
| 18 | lookback_bars | 80→90 | 0.338549 | -0.025732 | rejected |
| 19 | lookback_bars | 80→95 | 0.330561 | -0.033719 | rejected |
| 20 | lookback_bars | 80→100 | 0.362926 | -0.001355 | rejected |
| 21 | pivot_window | 2→4 | 0.348684 | -0.015596 | rejected |
| 22 | pivot_window | 2→5 | 0.338635 | -0.025646 | rejected |
| 23 | pivot_window | 2→6 | 0.333792 | -0.030488 | rejected |
| 24 | lookback_bars | 80→50 | 0.338287 | -0.025993 | rejected |
| 25 | lookback_bars | 80→60 | 0.363251 | -0.001030 | rejected |
| 26 | lookback_bars | 80→55 | 0.330806 | -0.033474 | rejected |
| 27 | lookback_bars | 80→65 | 0.326747 | -0.037534 | rejected |
| 28 | lookback_bars | 80→70 | 0.338538 | -0.025743 | rejected |
| 29 | pivot_window | 2→4 | 0.348684 | -0.015596 | rejected |
| 30 | lookback_bars | 80→45 | 0.327696 | -0.036585 | rejected |

## Key Findings

### Which parameter changes helped most

1. **pivot_window 3→2** (iter 4): Largest single improvement (+0.0073). Reducing pivot sensitivity to detect more swing points consistently improved accuracy across all lookback_bars positions tested.
2. **lookback_bars 60→40** (iter 10): Small improvement (+0.0008). Revealed a secondary accuracy peak at the minimum bound.
3. **lookback_bars 40→80** (iter 14): Smallest accepted improvement (+0.0003). Found the global best at an unexpected distant position.

### Which parameter changes hurt most

- **lookback_bars to off-grid values** (45, 55, 65, 70, 75, 85, 90, 95): All values not divisible by 20 performed significantly worse (accuracy ~0.327–0.339 vs ~0.363 at peaks). The odd-step values fall into a consistent accuracy valley.
- **pivot_window increases** (3, 4, 5, 6): Monotonically decreasing accuracy. pivot_window=2 (minimum) is unambiguously optimal. Each step increase costs ~0.6–0.8pp.

### Search Surface Observations

1. **Periodic structure in lookback_bars**: The accuracy surface shows sharp peaks at values divisible by 20 (40, 60, 80, 100) with deep valleys at intermediate values. This likely relates to the hourly data's weekly/daily periodicity (24h/day, 120 bars/week). lookback_bars values that align with market time cycles capture structure more cleanly.

2. **lookback_bars peak ordering** (at pivot_window=2):
   - 80: 0.364281 (best)
   - 40: 0.364023
   - 60: 0.363251
   - 100: 0.362926
   - All peaks within ~0.15pp of each other — very flat across multiples of 20

3. **pivot_window is monotonically optimal at minimum**: Lower = better, no exceptions. The minimum detectable pivot sensitivity produces the best accuracy. This suggests the lens benefits from dense swing detection.

4. **No rejections due to resolve_rate or sample guards**: All 27 rejections were purely accuracy-based. Resolve rate remained consistently high (0.996–0.999) across all parameter combinations. The resolved_calls sample count stayed stable (~1,400–1,520).

## Resolve Rate Trend

Resolve rate was remarkably stable across all 30 iterations:
- Range: 0.996 to 0.999
- No iteration approached the 0.70 floor
- Parameter changes had negligible effect on resolve rate

## Ranging Percentage Trend

| lookback_bars | pivot_window | ranging_pct |
|---------------|-------------|-------------|
| 40 | 2 | 0.437 |
| 60 | 2 | 0.435 |
| 80 | 2 | 0.435 |
| 100 | 2 | 0.435 |
| 80 | 3 | 0.423 |
| 80 | 4 | 0.392 |
| 80 | 5 | 0.397 |
| 80 | 6 | 0.418 |

- pivot_window has more influence on ranging_pct than lookback_bars
- Lower pivot_window (more swing points) slightly increases ranging percentage
- Despite higher ranging_pct, pivot_window=2 still produces the best accuracy

## Validation Performance

Best-found params `(lookback_bars=80, pivot_window=2)` on validation split (2026-01-02 to 2026-03-19):
- Accuracy: **0.312102** (vs 0.364281 on train, -5.2pp gap)
- Resolve rate: 0.998
- Resolved calls: 163 (smaller validation window)
- Ranging pct: 0.399

The train-to-validation accuracy drop of ~5pp is moderate, suggesting some overfitting to the training period but the parameters remain in a reasonable generalization range. The reduced validation sample size (163 vs ~1,411 calls) adds uncertainty to the validation estimate.
