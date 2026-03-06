# CONSTRAINTS.md — Phase 3B Hard Rules

## Locked 3A decisions — do not reopen

These are immutable. Any change is a scope violation:

| Rule | Value |
|---|---|
| Swing confirmation method | Fixed left/right pivot only |
| BOS/MSS confirmation | Close beyond prior swing only |
| EQH/EQL tolerance | Fixed per-instrument value in config |
| Active timeframes | 15m, 1h, 4h |
| Output format | JSON only, pretty-printed, UTF-8, atomic writes |
| FVG / imbalance | Not in scope until Phase 3C |
| Cross-timeframe synthesis | Not in scope until Phase 3D |
| Officer integration | Not in scope until Phase 3D |
| Parquet structure output | Not in scope until Phase 3D |
| Feed pipeline | Do not touch |

---

## Phase 3B hard rules

### RULE 1 — Schema additions only

Add new fields to `LiquidityLevel` and `SweepEvent`. Do not rename, remove, or reorder existing 3A fields. Existing JSON consumers must not break.

### RULE 2 — Reclaim logic uses close confirmation only

Reclaim is confirmed by a close through the level — not a wick, not a touch, not a midpoint. This mirrors the 3A BOS rule. Consistency matters.

```python
# High-side reclaim: close < level_price
# Low-side reclaim: close > level_price
```

### RULE 3 — Lifecycle transitions are one-directional

No backward transitions. Once `reclaimed` or `accepted_beyond`, the outcome is immutable. Reruns must not alter resolved outcomes.

```python
TERMINAL_STATES = {"reclaimed", "accepted_beyond", "invalidated"}
# A level in a terminal state must not transition to any other state
```

### RULE 4 — SweepEvent and LiquidityLevel must stay consistent

After any reclaim/classification update, verify:

```python
assert sweep.outcome == level.outcome
assert sweep.reclaim_time == level.reclaim_time
```

The engine enforces this. Consumers should not need to reconcile them.

### RULE 5 — `unclassified` is a valid output

Do not force a `liquidity_scope` value when the deterministic rule cannot resolve it. Returning `unclassified` is correct behaviour. Invented heuristics that produce wrong tags are worse than honest `unclassified`.

### RULE 6 — Config surface stays narrow

Add only:
```python
allow_same_bar_reclaim: bool = True
reclaim_window_bars: int = 1
```

Do not add:
- ATR-scaled tolerance
- ATR-scaled pivots
- wick BOS mode
- multi-bar acceptance windows beyond `reclaim_window_bars`
- any other Phase 3C/3D parameters

### RULE 7 — Replay safety

Appending new bars may resolve previously `unresolved` outcomes. It must not change already-resolved outcomes. Test this explicitly.

### RULE 8 — `engine_version` must update

In the build metadata block of every output packet:

```json
"build": {
  "engine_version": "phase_3b",
  ...
}
```

This allows downstream consumers to know which logic version produced the packet.

### RULE 9 — Officer and feed are untouched

Run this check before declaring complete:

```bash
git diff --name-only HEAD | grep -E "officer/|feed/"
# Must return no matches
```

### RULE 10 — Both instruments must pass

All 3B test groups must pass for both EURUSD and XAUUSD. Passing one instrument only is not acceptable.

---

## What "deterministic" means in 3B context

For reclaim and classification logic:

- Same bars → same `liquidity_scope` tags, same `outcome`, same `reclaim_time`
- The config values (`allow_same_bar_reclaim`, `reclaim_window_bars`) are the only variables
- No random seeds, no timestamp-dependent branching, no external lookups

Test this with hash-stable packet comparison on fixed fixture datasets.

---

## Common failure modes to avoid

| Failure | How it manifests | Guard |
|---|---|---|
| Backward transition | `accepted_beyond` → `reclaimed` on rerun | Check terminal state before any update |
| Inconsistent sweep/level outcome | `sweep.outcome != level.outcome` | Enforce in engine after every classification update |
| False reclaim via wick | Wick crosses level but close does not | Use `bar["close"]` only, never `bar["high"]` or `bar["low"]` for reclaim |
| EQH/EQL over-classification | Forcing internal/external when no relevant swing exists | Return `unclassified` when `relevant` list is empty |
| Unresolved leaking into history | Old unresolved outcomes not resolved as new bars arrive | Process unresolved levels on every engine run with available bars |
