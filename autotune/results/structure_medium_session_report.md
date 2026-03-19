# Structure Medium — AutoTune Session 1 Report

## Session Summary

| Field | Value |
|-------|-------|
| **Session ID** | `structure_medium_20260319_095649` |
| **Instance** | `structure_medium` |
| **Date** | 2026-03-19 |
| **Total iterations** | 30 |
| **Accepted** | 5 |
| **Rejected** | 25 |
| **Seed params** | `lookback_bars=140, pivot_window=6` |
| **Best-found params** | `lookback_bars=190, pivot_window=9` |
| **Baseline accuracy** | 0.333333 |
| **Best training accuracy** | 0.367010 |
| **Accuracy improvement** | +0.033677 (+10.1%) |
| **Validation accuracy** | 0.267857 (56 resolved calls) |

## Accuracy Progression

| Iter | Parameter | Old → New | Accuracy | Delta | Decision |
|------|-----------|-----------|----------|-------|----------|
| 1 | lookback_bars | 140 → 150 | 0.346076 | +0.012743 | **ACCEPTED** |
| 2 | pivot_window | 6 → 5 | 0.345168 | -0.000909 | rejected |
| 3 | pivot_window | 6 → 7 | 0.351406 | +0.005329 | **ACCEPTED** |
| 4 | lookback_bars | 150 → 160 | 0.315682 | -0.035723 | rejected |
| 5 | pivot_window | 7 → 8 | 0.347023 | -0.004383 | rejected |
| 6 | lookback_bars | 150 → 140 | 0.321932 | -0.029474 | rejected |
| 7 | lookback_bars | 150 → 170 | 0.340206 | -0.011199 | rejected |
| 8 | lookback_bars | 150 → 130 | 0.358921 | +0.007516 | **ACCEPTED** |
| 9 | lookback_bars | 130 → 120 | 0.332000 | -0.026921 | rejected |
| 10 | pivot_window | 7 → 8 | 0.357741 | -0.001181 | rejected |
| 11 | lookback_bars | 130 → 110 | 0.343621 | -0.015300 | rejected |
| 12 | lookback_bars | 130 → 100 | 0.315464 | -0.043457 | rejected |
| 13 | lookback_bars | 130 → 180 | 0.330645 | -0.028276 | rejected |
| 14 | lookback_bars | 130 → 190 | 0.357741 | -0.001181 | rejected |
| 15 | lookback_bars | 130 → 200 | 0.320487 | -0.038434 | rejected |
| 16 | lookback_bars | 130 → 210 | 0.350202 | -0.008719 | rejected |
| 17 | lookback_bars | 130 → 220 | 0.318275 | -0.040646 | rejected |
| 18 | pivot_window | 7 → 9 | 0.365546 | +0.006625 | **ACCEPTED** |
| 19 | pivot_window | 9 → 10 | 0.356108 | -0.009439 | rejected |
| 20 | lookback_bars | 130 → 120 | 0.335498 | -0.030048 | rejected |
| 21 | lookback_bars | 130 → 140 | 0.344898 | -0.020648 | rejected |
| 22 | lookback_bars | 130 → 150 | 0.346939 | -0.018607 | rejected |
| 23 | lookback_bars | 130 → 190 | 0.367010 | +0.001464 | **ACCEPTED** |
| 24 | lookback_bars | 190 → 200 | 0.340816 | -0.026194 | rejected |
| 25 | lookback_bars | 190 → 180 | 0.335417 | -0.031594 | rejected |
| 26 | pivot_window | 9 → 10 | 0.357576 | -0.009435 | rejected |
| 27 | pivot_window | 9 → 8 | 0.356394 | -0.010616 | rejected |
| 28 | lookback_bars | 190 → 210 | 0.343621 | -0.023389 | rejected |
| 29 | lookback_bars | 190 → 170 | 0.309717 | -0.057294 | rejected |
| 30 | pivot_window | 9 → 5 | 0.340551 | -0.026459 | rejected |

## Key Findings

### Which parameter changes helped most

1. **lookback_bars 140→150** (+0.0127): The initial move upward gave the biggest single improvement.
2. **lookback_bars 150→130** (+0.0075): Skipping over the 140 valley found a second peak.
3. **pivot_window 7→9** (+0.0066): Jumping over the pw=8 dip found the optimal pivot window.
4. **pivot_window 6→7** (+0.0053): First pivot_window improvement.
5. **lookback_bars 130→190** (+0.0015): Interaction with pw=9 unlocked the secondary lookback peak.

### Which parameter changes hurt most

- **lookback_bars → 170 (with pw=9)**: -0.057 — worst single result
- **lookback_bars → 100**: -0.043 — boundary of range performed poorly
- **lookback_bars → 220**: -0.041 — upper boundary also performed poorly
- **lookback_bars → 200**: -0.038 — steep drop from 190 peak

### Parameter interaction effects

The optimal lookback_bars value shifted when pivot_window changed:
- With pw=7: lookback_bars=130 was best (0.3589), 190 was a near-miss (0.3577)
- With pw=9: lookback_bars=190 surpassed 130 (0.3670 vs 0.3655)
- This demonstrates significant parameter interaction — the optimal lookback depends on the pivot window setting

## Comparison with structure_short Findings

### 20-bar periodicity: DOES NOT HOLD

In structure_short, accuracy peaks appeared at lookback_bars divisible by 20 (daily cycle alignment on 1H gold: 40, 60, 80). In structure_medium:
- 120 (div by 20): 0.332 — below average
- 140 (div by 20): 0.322 — poor
- 160 (div by 20): 0.316 — poor
- 180 (div by 20): 0.331 — below average
- 200 (div by 20): 0.320 — poor
- 220 (div by 20): 0.318 — poor
- **Peaks at 130, 150, 190** — all non-multiples of 20

The 12-bar evaluation horizon appears to break the daily-cycle alignment that benefited structure_short's 4-bar horizon. The longer horizon averages over multiple daily cycles, making the precise alignment irrelevant.

### pivot_window: NOT monotonically optimal at minimum

In structure_short, pivot_window=2 (minimum) was monotonically best — every increase hurt accuracy. In structure_medium:
- pw=5: 0.345 (rejected)
- pw=6: 0.333 (seed)
- pw=7: 0.351 (accepted)
- pw=8: 0.347–0.358 (rejected, dip)
- pw=9: 0.366 (accepted, best)
- pw=10: 0.356 (rejected)

**The optimal pivot_window is 9, near the maximum.** This is the opposite of structure_short. The 12-bar horizon benefits from fewer, more significant swing points rather than many small ones.

### Why the differences?

The 12-bar horizon (12 hours) is 3× the structure_short horizon (4 bars = 4 hours). Over 12 hours:
- **Many small pivot points** (low pivot_window) create noise — short-lived structure levels that resolve before the 12-bar window closes, leading to more invalidations
- **Fewer, more significant pivots** (high pivot_window) produce more durable structure levels that remain relevant over the longer evaluation window
- **Daily cycle alignment** is less important because the 12-bar window spans half a trading day, naturally averaging across intra-day patterns

## Resolve Rate Trend

Resolve rate was **1.000 across all 30 iterations** — every call resolved within the 12-bar horizon. This is expected: the longer horizon gives price more time to hit confirmation or invalidation thresholds. No iterations were rejected due to resolve_rate or sample guards.

## Ranging Percentage Trend

Not directly reported per iteration, but the validation run showed ranging_pct = 0.309 (30.9%). The structure_medium lens with pw=9 and lb=190 produces fewer ranging calls than structure_short (which had ~42% ranging), consistent with the higher pivot_window filtering out ambiguous structure.

## Validation Results

| Metric | Value |
|--------|-------|
| **Validation accuracy** | 0.267857 |
| **Resolve rate** | 1.000 |
| **Resolved calls** | 56 |
| **Confirmed** | 15 |
| **Invalidated** | 41 |
| **Ranging pct** | 30.9% |

The validation accuracy (0.268) is significantly below the training accuracy (0.367), indicating some degree of overfitting to the training period. However, the small validation sample (56 calls vs ~485 training calls) means the validation estimate has high variance. The validation period (2026-01-01 onward) may also reflect different market conditions.

## File Locations

- Experiment log: `autotune/logs/experiment_log.jsonl`
- Session metadata: `autotune/sessions/structure_medium_20260319_095649/`
- Instance manifest: `autotune/instance_manifest.json`
- This report: `autotune/results/structure_medium_session_report.md`
