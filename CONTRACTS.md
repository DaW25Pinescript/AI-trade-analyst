# CONTRACTS.md — Phase 3F: PersonaVerdict, ArbiterDecision, MultiAnalystOutput

## New file: `analyst/multi_contracts.py`

3F dataclasses live in a **new file only**. `analyst/contracts.py` is not modified.
Import existing 3E types from `analyst.contracts` as needed.

```python
# analyst/multi_contracts.py
from dataclasses import dataclass, field
from typing import Optional
from analyst.contracts import StructureDigest, AnalystVerdict, ReasoningBlock

```python
@dataclass
class PersonaVerdict:
    """
    Structured verdict from a single LLM persona.
    Produced by analyst/personas.py. Never produced by Arbiter or pre-filter.
    """
    persona_name: str            # "technical_structure" | "execution_timing"
    instrument: str
    as_of_utc: str

    verdict: str                 # same taxonomy as AnalystVerdict
    confidence: str              # "high" | "moderate" | "low" | "none"
    directional_bias: str        # "bullish" | "bearish" | "neutral" | "none"

    structure_gate: str          # echoed from digest — must not differ
    persona_supports: list[str]  # what this persona found supportive
    persona_conflicts: list[str] # what this persona found conflicting
    persona_cautions: list[str]  # persona-specific caution flags

    reasoning: ReasoningBlock    # reuse existing ReasoningBlock schema

    def is_directional(self) -> bool:
        return self.verdict in ("long_bias", "short_bias")

    def is_blocked(self) -> bool:
        return self.verdict in ("no_trade", "no_data")
```

---

## ArbiterDecision dataclass

```python
@dataclass
class ArbiterDecision:
    """
    Final synthesized decision from the Arbiter.
    Directional fields are pre-determined by Python conflict rules.
    LLM writes synthesis_notes and winning_rationale_summary only.
    """
    instrument: str
    as_of_utc: str

    # Pre-determined by Python conflict rules (no LLM involvement)
    consensus_state: str         # see taxonomy in OBJECTIVE.md
    final_verdict: str           # "long_bias" | "short_bias" | "no_trade" | "conditional" | "no_data"
    final_confidence: str        # "high" | "moderate" | "low" | "none"
    final_directional_bias: str  # "bullish" | "bearish" | "neutral" | "none"
    no_trade_enforced: bool      # True if Python hard-constraint triggered override

    # Agreement/conflict record
    personas_agree_direction: bool
    personas_agree_confidence: bool
    confidence_spread: str       # e.g. "high vs moderate" or "aligned"

    # LLM-written fields (synthesis call only — given the pre-computed skeleton above)
    synthesis_notes: str         # plain English: what aligned, what conflicted, how resolved
    winning_rationale_summary: str  # why final_verdict was the right outcome

    def is_actionable(self) -> bool:
        return (
            self.final_verdict in ("long_bias", "short_bias")
            and self.final_confidence in ("high", "moderate")
            and not self.no_trade_enforced
        )
```

---

## MultiAnalystOutput dataclass

```python
@dataclass
class MultiAnalystOutput:
    """
    Top-level container for one full multi-analyst run.
    Preserved entirely for audit and replay.
    """
    instrument: str
    as_of_utc: str

    digest: StructureDigest           # shared input — identical for both personas
    persona_outputs: list[PersonaVerdict]  # ordered: [technical_structure, execution_timing]
    arbiter_decision: ArbiterDecision
    final_verdict: AnalystVerdict      # Arbiter decision re-expressed as AnalystVerdict for downstream compat

    def to_dict(self) -> dict:
        ...
```

The `final_verdict` field re-expresses the `ArbiterDecision` in `AnalystVerdict` schema so downstream systems (and the 3E contract) remain unchanged.

---

## Persona prompt contracts

### Technical Structure Analyst system prompt

```
You are a disciplined ICT-style technical structure analyst.
Your job is to assess whether the structural case for a trade is valid.
You do not re-derive structure from raw price data.
Your structural knowledge comes exclusively from the structure digest provided.

You assess: HTF regime consistency, BOS/MSS direction and quality,
liquidity positioning (internal vs external), FVG zone context (discount/premium),
and sweep/reclaim outcomes.

You do not optimise for timing or execution cleanliness.
You answer only: is the structural case for a directional bias sound?

Output only valid JSON matching PersonaVerdict schema. No preamble. No markdown.
```

### Execution/Timing Analyst system prompt

```
You are a disciplined ICT-style execution and timing analyst.
Your job is to assess whether the current context is a good place and time to act.
You do not re-derive structure from raw price data.
Your structural knowledge comes exclusively from the structure digest provided.

You assess: proximity and quality of nearby liquidity barriers, FVG positioning
relative to current price, reclaim vs acceptance outcomes, execution cleanliness,
and short-term conflict signals (LTF MSS, partial FVG fills, unresolved sweeps).

You do not re-assess HTF regime validity. You take the HTF gate result as given
and focus entirely on execution context quality.

You answer only: is this a good place and time to act on the structural case?

Output only valid JSON matching PersonaVerdict schema. No preamble. No markdown.
```

### Arbiter system prompt

```
You are the Arbiter. You do not form opinions about the market.
You have been given a pre-computed ArbiterDecision skeleton:
- consensus_state, final_verdict, final_confidence, no_trade_enforced are already determined.

Your only job is to write:
1. synthesis_notes: 2-4 sentences explaining what aligned, what conflicted, and how it resolved.
2. winning_rationale_summary: 1-2 sentences stating why the final verdict is the right outcome.

Do not change final_verdict. Do not change final_confidence.
Do not argue against no_trade_enforced if it is True.
Output only valid JSON with exactly two fields: synthesis_notes, winning_rationale_summary.
```

---

## Full MultiAnalystOutput JSON example

```json
{
  "instrument": "EURUSD",
  "as_of_utc": "2026-03-07T10:15:00Z",

  "digest": { "...": "same StructureDigest as 3E" },

  "persona_outputs": [
    {
      "persona_name": "technical_structure",
      "verdict": "long_bias",
      "confidence": "high",
      "directional_bias": "bullish",
      "structure_gate": "pass",
      "persona_supports": ["bullish 4h regime", "bullish BOS on 1h", "active discount FVG"],
      "persona_conflicts": ["bearish MSS on 15m"],
      "persona_cautions": ["ltf_mss_conflict"],
      "reasoning": { "...": "ReasoningBlock" }
    },
    {
      "persona_name": "execution_timing",
      "verdict": "conditional",
      "confidence": "moderate",
      "directional_bias": "bullish",
      "structure_gate": "pass",
      "persona_supports": ["price approaching discount FVG", "bullish reclaim of equal_lows"],
      "persona_conflicts": ["external liquidity (prior_day_high) close above — potential barrier"],
      "persona_cautions": ["liquidity_above_close", "entry may be late relative to FVG"],
      "reasoning": { "...": "ReasoningBlock" }
    }
  ],

  "arbiter_decision": {
    "consensus_state": "directional_alignment_confidence_split",
    "final_verdict": "long_bias",
    "final_confidence": "moderate",
    "final_directional_bias": "bullish",
    "no_trade_enforced": false,
    "personas_agree_direction": true,
    "personas_agree_confidence": false,
    "confidence_spread": "high vs moderate",
    "synthesis_notes": "Both personas agree on a bullish directional bias. Technical structure sees a clean HTF alignment with minor LTF conflict. Execution timing notes the prior_day_high as a nearby barrier and rates the setup conditional. Arbiter resolves to long_bias at moderate confidence — lower confidence tier honoured due to timing caution.",
    "winning_rationale_summary": "Directional alignment holds across both personas. Confidence is moderated by execution timing concern. Long bias at moderate confidence is the defensible output."
  },

  "final_verdict": {
    "verdict": "long_bias",
    "confidence": "moderate",
    "structure_gate": "pass",
    "htf_bias": "bullish",
    "...": "full AnalystVerdict schema"
  }
}
```

---

## Output file path

```
analyst/output/{instrument}_multi_analyst_output.json
```

Single-analyst 3E output at `{instrument}_analyst_output.json` is preserved and unchanged.
