# OBJECTIVE.md — Phase 3B: Liquidity Refinement

## What Phase 3B adds and why

Phase 3A established trusted structural primitives — confirmed swings, BOS, MSS, prior levels, EQH/EQL, and basic sweep detection. Every object is confirmed-only, deterministic, and replay-safe.

The gap 3A leaves is: after a sweep fires, the liquidity object goes silent. It knows it was swept, but nothing downstream knows what happened next — did price reclaim, accept beyond, or remain unresolved? That question matters for every downstream consumer: analyst agents, arbiter reasoning, Senate deliberation.

Phase 3B answers that question deterministically by extending the liquidity layer with:

1. **Reclaim detection** — was the swept level reclaimed?
2. **Post-sweep classification** — `reclaimed`, `accepted_beyond`, or `unresolved`
3. **Internal/external tagging** — what kind of liquidity was this?
4. **Lifecycle refinement** — richer but still additive state transitions
5. **Sweep metadata enrichment** — enough post-sweep context for downstream agents to reason without inference

This does not change how sweeps are detected. It extends what happens after detection.

---

## Reclaim detection

### Rule

A sweep is followed by reclaim detection using a close-confirmation rule:

- **High-side level** (prior_day_high, prior_week_high, equal_highs): reclaim confirmed when a subsequent bar closes **back below** the level
- **Low-side level** (prior_day_low, prior_week_low, equal_lows): reclaim confirmed when a subsequent bar closes **back above** the level

### Reclaim window

- Same-bar reclaim is allowed: if the sweep bar itself closes back through the level, reclaim is confirmed immediately
- Otherwise, reclaim window = 1 subsequent closed bar (default, configurable)
- After the window closes without reclaim, classify as `accepted_beyond`
- Until the window closes, classify as `unresolved`

### What reclaim applies to

All swept liquidity level types:
- `prior_day_high` / `prior_day_low`
- `prior_week_high` / `prior_week_low`
- `equal_highs` / `equal_lows`

---

## Post-sweep outcome classification

Three states, mutually exclusive, assigned deterministically:

| Outcome | Condition |
|---|---|
| `reclaimed` | Reclaim confirmed within the reclaim window |
| `accepted_beyond` | Reclaim window closed without reclaim |
| `unresolved` | Not enough subsequent closed bars yet |

Classification is additive. `unresolved` → `reclaimed` or `accepted_beyond` as bars close. Once resolved, the outcome is immutable.

---

## Internal vs external liquidity tagging

Tag each liquidity level with its scope. Use deterministic rules only — do not invent fragile heuristics for ambiguous cases.

### Rules

| Level type | Tag |
|---|---|
| `prior_day_high` | `external_liquidity` |
| `prior_day_low` | `external_liquidity` |
| `prior_week_high` | `external_liquidity` |
| `prior_week_low` | `external_liquidity` |
| `equal_highs` | classify relative to most relevant confirmed swing: if EQH sits above the most recent confirmed swing high, tag `external_liquidity`; if below, tag `internal_liquidity`; if ambiguous, tag `unclassified` |
| `equal_lows` | symmetric rule |

Correctness over coverage. `unclassified` is a valid and preferred output when determinism cannot be guaranteed.

---

## Liquidity lifecycle refinement

Extend Phase 3A lifecycle states:

```
active → swept → reclaimed
              → accepted_beyond
       → invalidated
       → archived
```

Allowed transitions:
- `active` → `swept` (sweep detected)
- `swept` → `reclaimed` (reclaim confirmed within window)
- `swept` → `accepted_beyond` (window closed, no reclaim)
- `active` → `invalidated` (structural invalidation — e.g. BOS removes relevance)
- any terminal state → `archived` (cleanup, future use)

Disallowed:
- `reclaimed` → `accepted_beyond` (or any backward transition)
- `accepted_beyond` → `reclaimed`
- any terminal state → `active`

Transitions must be additive and replay-safe. Reruns on unchanged bars must not alter resolved outcomes.

---

## Sweep metadata enrichment

Enrich SweepEvent so downstream consumers have complete post-sweep context:

| New field | Description |
|---|---|
| `post_sweep_close` | Close price of the bar that confirmed or failed reclaim |
| `reclaim_time` | Timestamp of reclaim confirmation (null if not reclaimed) |
| `outcome` | `reclaimed` \| `accepted_beyond` \| `unresolved` |
| `reclaim_window_bars` | Config value in effect at time of sweep |
| `linked_liquidity_id` | ID of the LiquidityLevel this sweep is attached to |

---

## What Phase 3B explicitly does NOT include

| Out of scope | Phase |
|---|---|
| ATR-scaled dynamic pivots | 3B extension |
| ATR-scaled EQH/EQL tolerance | 3B extension |
| Wick-based BOS mode | 3B |
| FVG / imbalance detection | 3C |
| Order blocks | 3C+ |
| Cross-timeframe synthesis | 3D |
| Officer contract changes | 3D |
| Parquet structure output | 3D |
| Multi-bar acceptance engine | 3C |
| 5m / 1d timeframe expansion | Separate decision |
| Trade logic / confluence scoring | Never in structure engine |

---

## Definition of done

Phase 3B is complete when:
- Reclaim detection works correctly for all level types, both instruments
- Post-sweep classification is deterministic and additive
- Internal/external tagging follows the documented rules with clean `unclassified` fallback
- Liquidity lifecycle only transitions through allowed states
- SweepEvent and LiquidityLevel carry all new metadata fields
- All 3B test groups pass
- All 3A test groups still pass (full regression)
- Officer and feed modules are untouched
- JSON packets remain schema-complete and atomically written
