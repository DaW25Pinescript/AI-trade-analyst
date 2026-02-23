# Enums Reference

Canonical enum sets used for prompt-generation payloads, import/export validation, and AAR metrics.

## 1) Ticket enums (stored values)

- `decisionMode`: `LONG`, `SHORT`, `WAIT`, `CONDITIONAL`
- `ticketType`: `Zone ticket`, `Exact ticket`
- `entryType`: `Market`, `Limit`, `Stop`
- `entryTrigger`: `Pullback to zone`, `Break + retest`, `Sweep + reclaim`, `Close above/below level`, `Momentum shift (MSS/BOS)`
- `confirmationTF`: `1m`, `5m`, `15m`, `1H`
- `timeInForce`: `This session`, `Next 1H`, `24H`, `Custom`
- `stop.logic`: `Below swing low / above swing high`, `Below zone`, `ATR-based`, `Structure-based + buffer`
- `targets[].label`: `TP1`, `TP2`, `TP3`

Checklist enums:

- `checklist.htfState`: `Trending`, `Ranging`, `Transition`
- `checklist.htfLocation`: `At POI`, `Mid-range`, `At extremes`
- `checklist.ltfAlignment`: `Aligned`, `Counter-trend`, `Mixed`
- `checklist.liquidityContext`: `Near obvious highs/lows`, `Equilibrium`, `None identified`
- `checklist.volRisk`: `Normal`, `Elevated`
- `checklist.execQuality`: `Clean`, `Messy`, `Chop`
- `checklist.conviction`: `Very High`, `High`, `Medium`, `Low`
- `checklist.edgeTag`: `High-probability pullback`, `Liquidity grab`, `FVG reclaim`, `Structure BOS`, `Range boundary`, `Other`
- `checklist.confluenceScore`: integer range `1..10` (not string enum)

Gate enums:

- `gate.status`: `INCOMPLETE`, `PROCEED`, `CAUTION`, `WAIT`
- `gate.waitReasonCode`: `""`, `Chop / range noise`, `HTF-LTF conflict`, `No POI / poor R:R`, `News risk / volatility`, `Already moved / late trend`

## 2) AAR / metrics enums (stored values)

- `outcomeEnum`: `WIN`, `LOSS`, `BREAKEVEN`, `MISSED`, `SCRATCH`
- `verdictEnum`: `PLAN_FOLLOWED`, `PLAN_VIOLATION`, `PROCESS_GOOD`, `PROCESS_POOR`
- `exitReasonEnum`: `TP_HIT`, `SL_HIT`, `TIME_EXIT`, `MANUAL_EXIT`, `INVALIDATION`, `NO_FILL`
- `failureReasonCodes[]`: `LATE_ENTRY`, `OVERSIZED_RISK`, `IGNORED_GATE`, `MISREAD_STRUCTURE`, `NEWS_BLINDSPOT`, `EMOTIONAL_EXECUTION`, `NO_EDGE`
- `psychologicalTag`: `CALM`, `FOMO`, `HESITATION`, `REVENGE`, `OVERCONFIDENCE`, `FATIGUE`, `DISCIPLINED`

## 3) UI label → stored enum mapping rules

The persistence layer should always write the **stored enum value**, never the display label.

### 3.1 Checklist mappings

- UI label `Aligned with HTF` → stored `Aligned`
- UI label `Pullback` (edge tag button) → stored `High-probability pullback`
- UI label `Liquidity grab` → stored `Liquidity grab`
- UI label `FVG reclaim` → stored `FVG reclaim`
- UI label `Structure BOS` → stored `Structure BOS`
- UI label `Range boundary` → stored `Range boundary`
- UI label `Other` → stored `Other`

### 3.2 Gate mappings

- UI `gateStatus` class `wait` → stored `WAIT`
- UI `gateStatus` class `caution` → stored `CAUTION`
- UI `gateStatus` class `proceed` → stored `PROCEED`
- UI `gateStatus` with no decision class → stored `INCOMPLETE`

### 3.3 WAIT reason mappings

Displayed WAIT reasons must match stored enum values exactly:

- `Chop / range noise`
- `HTF-LTF conflict`
- `No POI / poor R:R`
- `News risk / volatility`
- `Already moved / late trend`

## 4) Import/export stability guidance

1. Do not localize/rename stored enum tokens in payloads.
2. UI copy may change, but each label must still map to a canonical stored token above.
3. Backup import must validate against canonical enums before migration.
4. Tests should assert canonical values in exported JSON, not UI display text.
