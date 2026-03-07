# CONSTRAINTS.md — Phase 3C Hard Rules

## Locked decisions — do not reopen

### From 3A
- Swing confirmation: fixed left/right pivot only
- BOS/MSS: close-confirmed only
- EQH/EQL tolerance: fixed per-instrument in config
- Active timeframes: 15m, 1h, 4h
- Output: JSON only, pretty-printed, UTF-8, atomic writes

### From 3B
- Reclaim: close confirmation only
- Reclaim window: `allow_same_bar_reclaim` + `reclaim_window_bars`
- Liquidity lifecycle: additive, no backward transitions

### From 3C spec decisions
- FVG detection: body-only (open-to-close boundaries)
- Wick-inclusive mode: not in scope
- Fill progression: partial + full as separate sequential states
- Invalidation: full fill only
- 50% threshold: not in scope
- Config-selectable invalidation modes: not in scope

---

## Phase 3C hard rules

### RULE 1 — Body-only detection, always

```python
# Correct — body boundaries
c1_body_high = max(c1["open"], c1["close"])
c1_body_low  = min(c1["open"], c1["close"])

# Wrong — wick boundaries
c1_wick_high = c1["high"]
c1_wick_low  = c1["low"]
```

`fvg_use_body_only` must always be `True` in Phase 3C. Acceptance tests will assert this.

### RULE 2 — No pre-confirmation emission

A zone is emitted only after candle 3 closes. Never emit a zone based on candle 1 or candle 2 alone. `confirm_time` must equal candle 3's timestamp.

```python
# Correct
zone.confirm_time = bars.index[i]  # candle 3 timestamp

# Wrong
zone.confirm_time = bars.index[i - 1]  # candle 2 — premature
```

### RULE 3 — No skipping partial fill

A zone cannot transition from `open` to `invalidated` without first passing through `partially_filled`. If price blows straight through the zone in one bar, both transitions must fire in sequence on that bar.

```python
# When price blows through:
zone.status = "partially_filled"  # fire first
zone.partial_fill_time = ts
# then immediately:
zone.status = "invalidated"
zone.full_fill_time = ts
```

### RULE 4 — Invalidated zones are terminal

Once a zone reaches `invalidated`, it must not be reprocessed or transitioned backward on reruns.

```python
if zone.status == "invalidated":
    return zone  # skip all fill processing
```

### RULE 5 — Active zone registry contains only live zones

The `active_zones` packet key must contain only zones with `status` in `{"open", "partially_filled"}`. Invalidated and archived zones must not appear there.

```python
active = [z for z in all_zones if z.status in ("open", "partially_filled")]
```

### RULE 6 — Minimum gap size is instrument-specific

Use `fvg_min_size_eurusd` for EURUSD and `fvg_min_size_xauusd` for XAUUSD. Do not use a single shared value. Do not silently default to zero.

### RULE 7 — Replay safety

Reruns on unchanged bars must not alter confirmed zones or resolved fill states. New bars may:
- Add new confirmed zones
- Advance `open` → `partially_filled`
- Advance `partially_filled` → `invalidated`

They must not:
- Change `confirm_time` of existing zones
- Reset fill tracking fields
- Remove zones from the packet

### RULE 8 — `engine_version` must update

```json
"build": {
  "engine_version": "phase_3c"
}
```

### RULE 9 — Officer and feed untouched

```bash
git diff --name-only HEAD | grep -E "officer/|feed/"
# Must return no output
```

### RULE 10 — Both instruments must pass

EURUSD and XAUUSD must both pass all test groups. Each uses its own minimum gap size from config.

---

## Common failure modes to avoid

| Failure | Guard |
|---|---|
| Using wick high/low for gap boundaries | Always use `max(open,close)` and `min(open,close)` |
| Emitting zone before candle 3 closes | `confirm_time` must be candle 3 index, emit only after `i >= 2` |
| Skipping partial_fill on blowthrough | Fire both transitions in sequence on same bar |
| Reprocessing invalidated zones | Check `status == "invalidated"` before any fill update |
| Active registry including invalidated zones | Filter on `status in {"open", "partially_filled"}` strictly |
| XAUUSD using EURUSD minimum gap size | Route through instrument-specific config field |
| fill_low/fill_high not updating progressively | Update on every bar inside zone, not just first touch |
