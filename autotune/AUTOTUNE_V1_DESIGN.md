# AutoTune v1 — Locked Design Summary

**Generated:** 2026-03-19
**Status:** Implementation complete — Phase A1 harness build
**Implementation date:** 2026-03-19
**Baseline accuracy (structure_short):** 0.356 (train split 2024-04-01 to 2025-12-31)

---

## Implementation Notes

### Data Availability Deviation
yFinance limits 1H data to ~730 days. Original spec requested 2020-01-01 to 2025-12-31.
Actual available range: 2024-03-19 to 2026-03-19 (~11,400 bars from GC=F).
- **Train split:** 2024-04-01 to 2025-12-31
- **Validation split:** 2026-01-01 to 2026-12-31

### Shim Feasibility: Outcome A (Subclass Override)
The production `StructureLens._detect_swings()` converts `swing_sensitivity` enum to int via `_SENSITIVITY_WINDOW.get(sensitivity, 5)`. The shim subclasses `StructureLens` and overrides `_detect_swings()` to accept a numeric `_pivot_window_override` from config. No monkeypatching. Continuous pivot_window search is fully supported.

### ATR Implementation
The `ta` library failed to install in the build environment. ATR is implemented manually using Wilder's smoothed moving average formula (period 14). Verified against known values in tests.

---

## Locked Decisions

### Scope
- **Side quest** — separate from main AI Trade Analyst repo
- **Phase A only** — config-parameter tuning (no hidden thresholds, no logic edits)
- **Structure lens family** — two separate instances
- **Single instrument:** XAUUSD
- **Single timeframe:** 1H

### Architecture
- Lenses are deterministic Python functions with typed LensOutput contracts
- AutoTune wraps existing production lenses — does not modify them
- Production config uses `swing_sensitivity` enum; AutoTune manifest exposes `pivot_window` as numeric
- Harness owns the enum→int translation layer via `AutoTuneStructureLens` shim

### Instances
| Property | structure_short | structure_medium |
|---|---|---|
| Purpose | Reactive local structure | Smoother durable structure |
| lookback_bars | 60 (range 40–100, step 5) | 140 (range 100–220, step 10) |
| pivot_window | 3 (range 2–6, step 1) | 6 (range 5–10, step 1) |
| Evaluation horizon | 4 bars (4 hours) | 12 bars (12 hours) |
| Step interval | 4 bars (non-overlapping) | 12 bars (non-overlapping) |

### Evaluator
- **Scored directions:** bullish, bearish only
- **Excluded:** ranging (logged as diagnostic, not scored)
- **Confirmation:** price moves ≥ 0.25 × ATR(14) in predicted direction within horizon
- **Invalidation:** price moves ≥ 0.25 × ATR(14) against prediction within horizon
- **Unresolved:** neither threshold crossed — excluded from accuracy denominator
- **Primary metric:** accuracy = confirmed / (confirmed + invalidated)
- **Secondary metric:** resolve_rate = (confirmed + invalidated) / total_calls
- **Sequential scan:** bar-by-bar, invalidation checked before confirmation (same-bar → INVALIDATED)

### Acceptance Policy (3 conditions, all required)
1. `candidate.accuracy > baseline.accuracy` (strict — ties rejected)
2. `candidate.resolve_rate >= 0.70`
3. `candidate.resolved_calls >= 0.80 × baseline.resolved_calls`

### Iteration Rules
- One parameter change per iteration
- Run full evaluation → compare accuracy to previous best
- If improved → accept (overwrite manifest)
- If not → reject (revert manifest)
- Log every iteration to append-only JSONL

### File Governance
| File | Agent access | Purpose |
|---|---|---|
| `instance_manifest.json` | Via runner CLI only | Current best parameters + inline bounds |
| `eval_config.json` | Read-only | Evaluator settings (horizon, ATR, stepping) |
| `evaluator.py` | Read-only | Windowed evaluator code |
| `data_loader.py` | Read-only | Historical data fetcher |
| `run.py` | Read-only | Orchestrator |
| `program.md` | Read-only | Agent skill instructions |
| `sessions/*/active/seed_manifest.json` | Read-only | Snapshot of initial params |
| `logs/experiment_log.jsonl` | Append-only | Full iteration history |

---

## Phased Build Order

### Phase A1 — structure_short (COMPLETE)
Tune structure_short in isolation. Harness loop proven.

### Phase A2 — structure_medium
Tune structure_medium in isolation. Confirm both instances produce meaningfully different behavior.

### Phase A3 — Comparison layer
Run both together. Compare agreement/divergence patterns. Build toward multi-horizon outlook.

### Phase B — Hidden threshold tuning
Unlock `rejection_tolerance_pct` and other hidden thresholds. Requires code-edit capability in the harness.

### Phase C — New lens creation
Support authoring new deterministic lenses. Register, tune, compare using the same harness.

---

## V1 File Artifacts

| File | Description |
|---|---|
| `eval_config.json` | Read-only evaluator configuration with train/validation date ranges |
| `instance_manifest.json` | Agent-editable parameter manifest with inline bounds |
| `experiment_log_schema.json` | Schema reference for the JSONL experiment log |
| `evaluator.py` | Windowed evaluator — ATR-scaled, sequential scan, deterministic |
| `data_loader.py` | yFinance data fetcher with parquet caching |
| `run.py` | Runner/orchestrator with acceptance policy and session management |
| `shims/structure_shim.py` | Outcome A pivot_window shim (subclass override) |
| `program.md` | Agent skill file for future optimization agent |
| `tests/` | Test suite covering evaluator, runner, acceptance policy |
| This file | Design summary |
