# AutoTune v1 — Locked Design Summary

**Generated:** 2026-03-19
**Status:** Design phase complete for Phase A1 (structure_short) and Phase A2 (structure_medium)
**Next step:** Implementation scoping / Claude Code prompt

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
- Harness owns the enum→int translation layer

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

### Iteration Rules
- One parameter change per iteration
- Run full evaluation → compare accuracy to previous best
- If improved → accept (overwrite manifest)
- If not → reject (revert manifest)
- Log every iteration to append-only JSONL

### File Governance
| File | Agent access | Purpose |
|---|---|---|
| `instance_manifest.json` | Read/write | Current best parameters + inline bounds |
| `eval_config.json` | Read-only | Evaluator settings (horizon, ATR, stepping) |
| `eval.py` | Read-only | Windowed evaluator code |
| `data_loader.py` | Read-only | Historical data fetcher |
| `run.py` | Read-only | Orchestrator |
| `program.md` | Read-only | Agent skill instructions |
| `seed_manifest.json` | Read-only | Snapshot of initial params (written once at session start) |
| `logs/experiment_log.jsonl` | Append-only | Full iteration history |

### Overfitting Strategy (for implementation)
- Train/test split: e.g., 2020–2024 for tuning, 2025–2026 held out
- Agent sees training accuracy only
- Human reviews validation accuracy
- Early stopping if training improves but validation degrades

---

## Phased Build Order

### Phase A1 — structure_short (first)
Tune structure_short in isolation. Prove the loop works.

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
| `eval_config.json` | Read-only evaluator configuration |
| `instance_manifest.json` | Agent-editable parameter manifest with inline bounds |
| `experiment_log_schema.json` | Schema + examples for the JSONL experiment log |
| This file | Locked design summary |

---

## Open for Implementation Phase

- Train/test date split: exact years to lock
- Data loader: yFinance pull + local cache format (parquet vs CSV)
- `program.md` content: agent skill instructions
- `run.py` orchestration: CLI interface, session management
- Harness shim: where exactly to inject pivot_window bypass
- Wall-clock budget: target iterations per session
