# OBJECTIVE.md — Phase 3E: Analyst Structure Consumption

## Why Phase 3E exists

By the end of Phase 3D the system has:
- A trusted feed producing canonical OHLCV
- An Officer producing Market Packet v2 with core features and structure state
- A structure engine computing confirmed swings, BOS/MSS, liquidity, FVGs, and regime

But nothing downstream is consuming that structure yet. The structure block in every v2 packet is populated, deterministic, and auditable — and completely ignored by any reasoning layer.

Phase 3E closes that gap. It builds the analyst layer that turns structured market state into verdicts. Not by re-deriving structure from scratch via chart interpretation, but by reading the pre-computed structure block and reasoning over it explicitly.

This is the payoff of the entire Phase 3 investment.

---

## The hybrid architecture

### Layer 1 — Python pre-filter (`pre_filter.py`)

Reads `MarketPacketV2.structure` and produces a `StructureDigest` — a compact, deterministic, machine-readable summary of what the structure block says about current market context.

The pre-filter:
- Applies the HTF regime gate (hard: pass / fail / no-data)
- Extracts and classifies recent BOS/MSS direction
- Identifies nearest liquidity above and below current price
- Classifies active FVG context (discount / premium / none)
- Summarises sweep/reclaim outcomes
- Produces explicit `structure_supports` and `structure_conflicts` lists
- Sets `structure_gate` status

This layer is deterministic. Same v2 packet → same digest, every time. It is fully testable without an LLM.

### Layer 2 — LLM analyst (`analyst.py`)

Receives the `StructureDigest` plus selected context from the v2 packet (core features, state summary, timeframes if needed). Does not receive the raw structure block directly — the digest is the only structure input.

The LLM:
- Synthesises the digest into a coherent directional view
- Weighs mixed or conflicting signals
- Produces a structured `AnalystVerdict` JSON block
- Produces a compact `ReasoningBlock` in plain English

The LLM must not re-derive structure from raw OHLCV or attempt chart interpretation. Its structural knowledge comes exclusively from the digest.

---

## What the pre-filter computes

### HTF regime gate

The hard gate. If HTF regime is unavailable or contradicts the proposed direction, the gate fails.

```
structure_gate = "pass"     → HTF regime is present and internally consistent
structure_gate = "fail"     → HTF regime contradicts trade direction
structure_gate = "no_data"  → structure block unavailable or stale
structure_gate = "mixed"    → 4h and 1h regimes conflict
```

Gate logic:
- Check `structure.available` — if False, gate = `no_data`
- Read `structure.regime.bias` from the 4h-preferred source
- If `bias == "neutral"` → gate = `mixed`
- If `bias` conflicts with proposed direction → gate = `fail`
- If `bias` aligns or no direction yet proposed → gate = `pass`

### BOS/MSS direction summary

From `structure.recent_events`, extract the most recent BOS and MSS:
- `last_bos`: `"bullish"` / `"bearish"` / `None`
- `last_mss`: `"bullish"` / `"bearish"` / `None`
- `bos_mss_alignment`: `"aligned"` / `"conflicted"` / `"incomplete"`

### Liquidity context

From `structure.liquidity` on the primary timeframe (1h preferred):
- `nearest_liquidity_above`: type, price, scope
- `nearest_liquidity_below`: type, price, scope
- `liquidity_bias`: `"above_closer"` / `"below_closer"` / `"balanced"`

### FVG context

From `structure.active_fvg_zones`:
- `active_fvg_context`: `"discount_bullish"` / `"premium_bearish"` / `"at_fvg"` / `"none"`
- Discount = price inside or below a bullish FVG
- Premium = price inside or above a bearish FVG

### Sweep/reclaim summary

From `structure.liquidity` levels with sweep outcomes:
- `recent_sweep_signal`: `"bullish_reclaim"` / `"bearish_reclaim"` / `"accepted_beyond"` / `"none"`
- Bullish reclaim = low-side sweep reclaimed = bullish signal
- Bearish reclaim = high-side sweep reclaimed = bearish signal

### Supports and conflicts

Plain-language strings describing what structure supports or conflicts with a bullish or bearish case:

```python
structure_supports = [
    "bullish 4h regime",
    "active discount FVG at 1.08475",
    "bullish BOS on 1h"
]
structure_conflicts = [
    "bearish MSS on 15m against HTF bullish regime",
    "external liquidity above at prior_day_high 1.08720"
]
```

---

## AnalystVerdict schema

```json
{
  "instrument": "EURUSD",
  "as_of_utc": "2026-03-07T10:15:00Z",
  "verdict": "long_bias",
  "confidence": "moderate",
  "structure_gate": "pass",
  "htf_bias": "bullish",
  "ltf_structure_alignment": "mixed",
  "active_fvg_context": "discount_bullish",
  "recent_sweep_signal": "bullish_reclaim",
  "structure_supports": ["bullish 4h regime", "active discount FVG"],
  "structure_conflicts": ["bearish MSS on 15m"],
  "no_trade_flags": [],
  "caution_flags": ["ltf_mss_conflict"]
}
```

### Verdict values
- `long_bias` — structure supports bullish
- `short_bias` — structure supports bearish
- `no_trade` — gate fail or too many conflicts
- `conditional` — mixed signals, conditional entry criteria needed
- `no_data` — structure unavailable

### Confidence values
- `high` — gate pass, strong alignment across HTF + LTF
- `moderate` — gate pass, some conflict at LTF
- `low` — gate pass but significant conflict
- `none` — gate fail or no_data

---

## ReasoningBlock schema

```json
{
  "summary": "Bullish bias on EURUSD. HTF 4h regime is bullish with recent bullish BOS on 1h confirming directional momentum. Price is trading near an active discount FVG at 1.08475–1.08620, providing a potential area of interest for continuation. A recent bullish reclaim of prior low-side liquidity adds conviction. Caution: 15m shows a bearish MSS, which introduces short-term conflict. Overall structure supports a long bias with moderate confidence, contingent on LTF stabilisation.",
  "htf_context": "4h regime: bullish. Last BOS: bullish (1h). Last MSS: bearish (15m) — minor conflict.",
  "liquidity_context": "Nearest above: prior_day_high at 1.08720 (external). Nearest below: equal_lows at 1.08410 (internal). Liquidity bias: above is closer — potential draw on liquidity above.",
  "fvg_context": "Active bullish FVG at 1.08475–1.08620 (1h, open). Price approaching from above — discount zone in play.",
  "sweep_context": "Recent bullish reclaim of equal_lows. Supportive of bullish continuation.",
  "verdict_rationale": "Long bias with moderate confidence. HTF gate passes. LTF MSS conflict noted but does not override HTF alignment. No hard no-trade flags."
}
```

---

## No-trade and caution flags

The pre-filter must emit explicit flags when conditions warrant:

### No-trade flags (hard — LLM must respect these)
- `htf_gate_fail` — HTF regime contradicts direction
- `no_structure_data` — structure block unavailable
- `htf_regime_neutral` — no directional bias available

### Caution flags (advisory — LLM weighs these)
- `ltf_mss_conflict` — LTF MSS against HTF direction
- `liquidity_above_close` — significant external liquidity just above price
- `fvg_partially_filled` — nearest FVG is partially filled, may have less magnetic pull
- `sweep_unresolved` — recent sweep with unresolved outcome
- `htf_mss_present` — HTF MSS fired recently, possible trend change

---

## What Phase 3E explicitly does NOT include

| Out of scope | Phase |
|---|---|
| Multiple analyst personas | 3F |
| Arbiter / Senate layer | Future |
| Backtesting / performance tracking | Future |
| Trade entry / exit logic | Never in analyst layer |
| Confluence scoring system | Future |
| New structure features | 4A+ |
| Officer or feed modifications | Not needed |
| Cross-timeframe structure synthesis | 4A |

---

## Definition of done

Phase 3E is complete when:
- `pre_filter.py` produces deterministic `StructureDigest` from any v2 packet
- HTF gate logic is correct and testable without LLM
- `AnalystVerdict` and `ReasoningBlock` schemas are defined and populated
- LLM analyst receives digest only — never raw structure block
- No-trade flags from pre-filter are respected in LLM output
- Verdict changes deterministically when structure inputs change
- Both EURUSD and XAUUSD produce coherent verdicts
- All test groups pass
- All prior phase tests pass
