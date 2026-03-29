# AlignmentAssessment — Field Classification Exercise

**Purpose:** Pressure-test every field in §3.5 of the Briefing Engine design.
Classify each as: fact, derived fact, constraint, bias/preference, or narrative convenience.
Anything in the last two categories must be challenged hard.

**Date:** 29 March 2026

---

## The Classification Framework

| Category | Definition | Test | Belongs in |
|----------|-----------|------|------------|
| **Fact** | Directly present in a source artifact | Can you point to the exact field it came from? | Compiler — no question |
| **Derived fact** | Computed deterministically from two or more facts | Given the same inputs, does everyone get the same output regardless of trading philosophy? | Compiler — safe |
| **Constraint** | A condition that limits or qualifies — "if X then Y is more/less reliable" | Does it describe what IS true, not what you SHOULD do? | Compiler — safe |
| **Bias / preference** | An interpretation that depends on trading doctrine or philosophy | Would two experienced traders with different styles disagree on this field's value given the same inputs? | Challenge hard — may belong in narrator |
| **Narrative convenience** | Exists to make the output readable, not to encode truth | Could you remove it and lose no analytical content? | Narrator — not compiler |

---

## Field-by-Field Classification

### `macro_price_alignment: "aligned" | "conflicted" | "neutral"`

**Classification: DERIVED FACT — but only if the definition is tight.**

If "aligned" means "macro frame directional lean matches price frame directional lean" — that's a factual comparison of two computed states. You can point to the inputs and the rule is mechanical.

But "aligned" is doing hidden work. What does it mean for macro to "align" with price?
- If institutions are 87th percentile long gold and gold price is trending up — is that aligned?
- Or is it "crowded" — which means the trend is vulnerable, not supported?

**The problem:** The same data supports opposite conclusions. "Institutions are heavily long" could mean:
- "Smart money is behind this move" → aligned
- "Everyone's on one side of the boat" → crowded, fragile

**Resolution:** This field can be a derived fact IF it is defined as **directional agreement** only, NOT as quality judgment. Specifically:

> `aligned` = macro positioning lean and price trend direction point the same way
> `conflicted` = they point opposite ways
> `neutral` = one or both are directionless

That is factual. Whether aligned is *good* or *dangerous* is a separate question — and that question is doctrine.

**Verdict: Keep in compiler, but strip any quality judgment from the definition.**

---

### `macro_favours: "longs" | "shorts" | None`

**Classification: BIAS / PREFERENCE — as currently defined.**

"Macro favours longs" smuggles in an interpretation. Does SPEC_MONEY_EXTREME_LONG favour longs?
- Momentum trader: Yes — institutions are behind the move, ride it
- Mean reversion trader: No — crowded trade, look for the reversal
- ICT trader: Depends — are they accumulating or distributing?

The same percentile reading produces opposite "favours" conclusions depending on your framework.

**Resolution:** Replace with a factual description that doesn't choose sides:

> `macro_positioning_lean: "long" | "short" | "neutral"` — factual: where is net positioning pointed?
> `macro_positioning_intensity: "extreme" | "strong" | "moderate" | "weak"` — factual: how far from center?

Now the compiler says "institutions are strongly leaned long" — a fact. Whether that *favours* the long side is the trader's interpretation (or the narrator's, optionally).

**Verdict: Reclassify as derived fact by renaming to a factual description. Remove "favours."**

---

### `price_favours: "longs" | "shorts" | None`

**Classification: DERIVED FACT — borderline.**

This is closer to safe because price structure is more mechanically directional. If structure is HH/HL on the 4H and trend is bullish across HTFs, the *price* frame leans long. That's not doctrine — that's structure.

But "favours" still implies recommendation. A ranging market doesn't "favour" anything — it's just ranging. And a bearish structure doesn't "favour shorts" if you're a counter-trend trader looking for the reversal.

**Resolution:** Same treatment:

> `price_structure_lean: "bullish" | "bearish" | "ranging"` — factual: what direction does structure point?

**Verdict: Reclassify as derived fact by renaming. Remove "favours."**

---

### `tensions: list[str]`

**Classification: DERIVED FACT — this is the strongest field in the section.**

"price_bearish_but_institutions_long" is a factual observation. Two computed states disagree. You're not saying what to do about it — you're saying the disagreement exists.

The tension vocabulary must be carefully designed — each tension should be a factual description of a cross-layer conflict, not an implied recommendation.

Good tension: `"price_trending_up_positioning_extreme_long"` — factual observation of two states
Bad tension: `"crowded_trade_risk_of_reversal"` — that's interpretation, not fact

**Verdict: Keep in compiler. Ensure the tension vocabulary describes states, not implications.**

---

### `favoured_play_types: list[str]`

**Classification: BIAS / PREFERENCE — this is the most dangerous field.**

"favour trend_continuation" is doctrine. Different trading frameworks produce different answers:
- Trend follower: aligned macro + trending price → trend continuation ✓
- ICT practitioner: depends on liquidity targets, not just trend + positioning
- Mean reversion: extreme positioning + trending price → reversal opportunity
- Range trader: ranging structure → fade extremes, regardless of macro

This field is the compiler quietly becoming a hidden strategist.

**Resolution:** Two options:

**Option A — Remove entirely from compiler.** The compiled state provides the facts (positioning lean, intensity, structure, tensions). The narrator or the human trader decides what play types are favoured.

**Option B — Reframe as "conditions present" rather than "play types favoured."**

> `conditions_present: list[str]` — e.g., `["trending_with_institutional_support", "extreme_positioning", "macro_price_conflict"]`

These are factual conditions. The trader maps conditions → play types based on their own framework.

**Verdict: Remove "favoured_play_types" from compiler. Either move to narrator or replace with factual condition flags.**

---

### `suppressed_play_types: list[str]`

**Classification: BIAS / PREFERENCE — same problem as favoured_play_types.**

"suppress counter_trend_short" is the compiler making a trading decision. The same macro state that one framework reads as "don't short" another reads as "crowded long — this is where the short opportunity lives."

**Verdict: Remove from compiler. Same treatment as favoured_play_types.**

---

### `conviction_context: "high" | "moderate" | "low" | "conflicted"`

**Classification: DERIVED FACT — if defined precisely.**

This is actually measuring **agreement between evidence layers**, not recommending confidence in a trade. If macro and price both lean the same way strongly — the evidence state has high internal coherence. If they conflict — the evidence state is internally conflicted.

The danger word is "conviction" — it sounds like it's telling you how confident to be in a trade. But if redefined as evidence coherence, it's factual:

> `evidence_coherence: "strong" | "moderate" | "weak" | "conflicted"` — measures how much the evidence layers agree, not how confident you should be in any specific action.

**Verdict: Keep in compiler, but rename from "conviction" to "evidence coherence" and define as internal agreement, not trading confidence.**

---

### `invalidation_triggers: list[str]`

**Classification: CONSTRAINT — the second strongest field in the section.**

"COT regime shifts to DIVERGENT_SPLIT" — that's a factual condition that would change the frame. "4H structure breaks below 2340" — that's a structural invalidation. These are "if-then" constraints, not recommendations.

The compiler is saying: "the current evidence state depends on these conditions remaining true. If they change, recompute."

**Verdict: Keep in compiler. This is pure constraint logic.**

---

## Summary Table

| Field | Current classification | Should be | Action |
|-------|----------------------|-----------|--------|
| `macro_price_alignment` | Derived fact (borderline) | Derived fact | Keep — tighten definition to directional agreement only |
| `macro_favours` | Bias / preference | Derived fact | Rename → `macro_positioning_lean` + `macro_positioning_intensity` |
| `price_favours` | Derived fact (borderline) | Derived fact | Rename → `price_structure_lean` |
| `tensions` | Derived fact | Derived fact | Keep — ensure vocabulary describes states not implications |
| `favoured_play_types` | Bias / preference | Remove from compiler | Move to narrator, or replace with factual `conditions_present` |
| `suppressed_play_types` | Bias / preference | Remove from compiler | Move to narrator, or replace with factual `conditions_present` |
| `conviction_context` | Derived fact (borderline) | Derived fact | Rename → `evidence_coherence` — measures agreement not confidence |
| `invalidation_triggers` | Constraint | Constraint | Keep as-is |

---

## The Revised AlignmentAssessment (after classification)

```
AlignmentAssessment:
    # DERIVED FACTS — directional comparison
    macro_price_alignment: "aligned" | "conflicted" | "neutral"
    macro_positioning_lean: "long" | "short" | "neutral"
    macro_positioning_intensity: "extreme" | "strong" | "moderate" | "weak"
    price_structure_lean: "bullish" | "bearish" | "ranging"

    # DERIVED FACTS — cross-layer observations
    tensions: list[str]                # factual conflict descriptions
    conditions_present: list[str]      # factual state descriptions

    # DERIVED FACT — internal evidence agreement
    evidence_coherence: "strong" | "moderate" | "weak" | "conflicted"

    # CONSTRAINTS — frame dependencies
    invalidation_triggers: list[str]   # conditions that would change the frame
```

Removed:
- `macro_favours` → replaced by lean + intensity (factual)
- `price_favours` → replaced by lean (factual)
- `favoured_play_types` → moved to narrator territory
- `suppressed_play_types` → moved to narrator territory
- `conviction_context` → renamed to evidence_coherence

---

## The Design Principle This Reveals

The compiler should answer: **"What is the state of the world?"**
The narrator should answer: **"What does this mean for you today?"**

The compiler says: "Institutions are strongly leaned long, price structure is bearish, these two facts are in conflict."
The narrator says: "Gold is in a tension zone — institutional flow supports the upside but the chart is broken. Caution on shorts even though structure is bearish."

The compiler never says "favour" or "suppress" or "conviction." It describes states, measures agreement, identifies conflicts, and lists constraints. The trader (or the narrator, optionally) translates that into trading decisions.

---

## What This Means for §8 Open Questions

Three of the six open questions are now reframed:

**Q1 (Positioning bias rules):** No longer about mapping to "supportive_of_longs." Now about mapping percentiles to lean + intensity. Much cleaner: 0–10 → extreme short, 10–30 → strong short, 30–50 → moderate short, etc. These are descriptive, not prescriptive.

**Q3 (Alignment computation):** Now simpler — directional agreement between lean and structure_lean. "Aligned" = same direction, "conflicted" = opposite, "neutral" = one is directionless. No doctrine needed.

**Q4 (Play-type vocabulary):** Moved to narrator. The compiler produces `conditions_present` which are factual. If a narrator is enabled, IT maps conditions → play types. Different narrator personas could even map conditions differently.

**Q2 (Macro environment):** Still needs work — "risk_on" vs "risk_off" might be a bias/preference depending on how it's defined.

**Q5/Q6 (Update semantics, instrument rules):** Unchanged — still need answers.
