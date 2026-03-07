# CONTRACTS.md — Phase 3G: ExplainabilityBlock and supporting dataclasses

## New file: `analyst/explain_contracts.py`

All 3G dataclasses live here. No existing file is modified except the single additive field on `MultiAnalystOutput`.

```python
# analyst/explain_contracts.py
from dataclasses import dataclass, field
from typing import Optional
```

---

## SignalInfluence

```python
@dataclass
class SignalInfluence:
    """Influence classification for one structure signal."""
    signal: str           # e.g. "htf_regime", "bos_mss", "fvg_context", "sweep_reclaim"
    value: str            # the actual value from the digest, e.g. "bullish", "discount_bullish"
    influence: str        # "dominant" | "supporting" | "conflicting" | "neutral" | "absent"
    direction: str        # "bullish" | "bearish" | "neutral" | "n/a"
    note: str             # one-line human-readable note, template-rendered
```

### Influence classification rules

Computed from `StructureDigest` fields:

| Signal | Dominant when | Supporting when | Conflicting when | Neutral/Absent |
|---|---|---|---|---|
| `htf_regime` | gate=pass, bias aligns with verdict | bias present, minor LTF conflict | gate=fail or bias opposes verdict | gate=no_data |
| `bos_mss` | both BOS+MSS align with verdict direction | BOS aligns, MSS minor conflict | MSS directly opposes HTF direction | neither present |
| `liquidity` | nearest level is internal and below price (bullish) or above (bearish) | liquidity bias aligned | external level just above (bearish barrier) | no active levels |
| `fvg_context` | price at or below discount FVG (bullish) / at or above premium (bearish) | active FVG present and aligned | FVG partially filled | no active FVG |
| `sweep_reclaim` | bullish/bearish reclaim confirmed | accepted beyond level | reclaim opposed direction | none |
| `no_trade_flags` | — | — | any flag present = conflicting | no flags |
| `caution_flags` | — | — | any flag present = conflicting (minor) | no flags |

---

## SignalInfluenceRanking

```python
@dataclass
class SignalInfluenceRanking:
    """Ranked list of signal influences. Dominant first, absent last."""
    signals: list[SignalInfluence]
    dominant_signal: Optional[str]    # signal name of top-ranked dominant, or None
    primary_conflict: Optional[str]   # signal name of top-ranked conflicting, or None

    def ranked(self) -> list[SignalInfluence]:
        """Return signals sorted: dominant → supporting → conflicting → neutral → absent.
        Conflicting ranks above neutral so primary conflicts are prominent in audit views."""
        order = {"dominant": 0, "supporting": 1, "conflicting": 2, "neutral": 3, "absent": 4}
        return sorted(self.signals, key=lambda s: order[s.influence])
```

---

## PersonaDominance

```python
@dataclass
class PersonaDominance:
    """Records which persona drove or constrained the final decision."""
    direction_driver: str           # "technical_structure" | "execution_timing" | "both" | "arbiter_override"
    confidence_driver: str          # persona whose confidence tier was used, or "arbiter_rule"
    confidence_effect: str          # "held" | "downgraded" | "upgraded" | "overridden_by_python"
    stricter_persona: Optional[str] # persona with lower confidence, or None if aligned
    python_override_active: bool    # True if hard no-trade flag triggered

    note: str                       # template-rendered summary sentence
```

### Computation rules

```python
def compute_persona_dominance(
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision
) -> PersonaDominance:

    pa = next(p for p in persona_outputs if p.persona_name == "technical_structure")
    pb = next(p for p in persona_outputs if p.persona_name == "execution_timing")

    if arbiter.no_trade_enforced:
        return PersonaDominance(
            direction_driver="arbiter_override",
            confidence_driver="arbiter_rule",
            confidence_effect="overridden_by_python",
            stricter_persona=None,
            python_override_active=True,
            note="Python hard no-trade constraint overrode both personas."
        )

    if pa.directional_bias == pb.directional_bias:
        direction_driver = "both"
    elif pa.is_directional() and not pb.is_directional():
        direction_driver = "technical_structure"
    else:
        direction_driver = "execution_timing"

    conf_order = {"high": 3, "moderate": 2, "low": 1, "none": 0}
    if conf_order[pa.confidence] < conf_order[pb.confidence]:
        stricter = "technical_structure"
        confidence_driver = "technical_structure"
    elif conf_order[pb.confidence] < conf_order[pa.confidence]:
        stricter = "execution_timing"
        confidence_driver = "execution_timing"
    else:
        stricter = None
        confidence_driver = "arbiter_rule"  # same tier, arbiter held it

    if arbiter.final_confidence != pa.confidence and arbiter.final_confidence != pb.confidence:
        effect = "downgraded"
    elif stricter and arbiter.final_confidence == _lower(pa.confidence, pb.confidence):
        effect = "downgraded"
    else:
        effect = "held"

    return PersonaDominance(
        direction_driver=direction_driver,
        confidence_driver=confidence_driver,
        confidence_effect=effect,
        stricter_persona=stricter,
        python_override_active=False,
        note=_render_dominance_note(direction_driver, confidence_driver, effect, stricter)
    )
```

---

## ConfidenceProvenance

```python
@dataclass
class ConfidenceStep:
    step: int
    label: str      # e.g. "Technical Structure Analyst"
    value: str      # confidence value at this step
    rule: str       # rule applied, e.g. "use lower confidence on split"

@dataclass
class ConfidenceProvenance:
    """Step-by-step trace of how final_confidence was determined."""
    steps: list[ConfidenceStep]
    final_confidence: str
    python_override: bool
    override_reason: Optional[str]
```

### Provenance construction

```python
def compute_confidence_provenance(
    persona_outputs: list[PersonaVerdict],
    arbiter: ArbiterDecision,
    digest: StructureDigest
) -> ConfidenceProvenance:

    steps = []
    pa = next(p for p in persona_outputs if p.persona_name == "technical_structure")
    pb = next(p for p in persona_outputs if p.persona_name == "execution_timing")

    steps.append(ConfidenceStep(1, "Technical Structure Analyst", pa.confidence, "persona output"))
    steps.append(ConfidenceStep(2, "Execution/Timing Analyst",    pb.confidence, "persona output"))
    steps.append(ConfidenceStep(3, "Consensus state",             arbiter.consensus_state, "arbiter classification"))

    rule = _confidence_rule_for_state(arbiter.consensus_state)
    steps.append(ConfidenceStep(4, "Arbiter rule applied", arbiter.final_confidence, rule))

    if digest.has_hard_no_trade():
        steps.append(ConfidenceStep(5, "Python override", "none", f"hard no-trade flags: {digest.no_trade_flags}"))
        return ConfidenceProvenance(steps=steps, final_confidence="none", python_override=True,
                                    override_reason=str(digest.no_trade_flags))

    steps.append(ConfidenceStep(5, "Final confidence", arbiter.final_confidence, "no override"))
    return ConfidenceProvenance(steps=steps, final_confidence=arbiter.final_confidence,
                                python_override=False, override_reason=None)
```

---

## CausalChain

```python
@dataclass
class CausalDriver:
    flag: str
    source: str       # "digest" | "persona_technical" | "persona_execution" | "arbiter"
    raised_by: str    # "pre_filter" | "persona" | "arbiter_rule"
    effect: str       # human-readable effect description

@dataclass
class CausalChain:
    no_trade_drivers: list[CausalDriver]
    caution_drivers: list[CausalDriver]
    has_hard_block: bool
```

---

## ExplainabilityBlock

```python
@dataclass
class ExplainabilityBlock:
    """
    Top-level explanation container. Fully deterministic.
    Produced by explainability.py from saved MultiAnalystOutput.
    No LLM calls permitted anywhere in this object's construction.
    """
    instrument: str
    as_of_utc: str
    source_verdict: str           # final_verdict echoed for quick reference
    source_confidence: str        # final_confidence echoed

    signal_ranking: SignalInfluenceRanking
    persona_dominance: PersonaDominance
    confidence_provenance: ConfidenceProvenance
    causal_chain: CausalChain

    audit_summary: str            # template-rendered human-readable text (no LLM)

    def to_dict(self) -> dict:
        ...
```

---

## Additive change to `analyst/multi_contracts.py`

Add one optional field to `MultiAnalystOutput`. This is the **only** permitted modification to any existing file:

```python
# In MultiAnalystOutput dataclass — add at end of field list:
explanation: Optional["ExplainabilityBlock"] = None
```

Import guard:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from analyst.explain_contracts import ExplainabilityBlock
```

Or import directly if no circular dependency risk.

---

## Standalone file contract

`analyst/output/{instrument}_multi_analyst_explainability.json` must be:

1. Derived from `MultiAnalystOutput.explanation` — never independently computed
2. Written atomically at the same time as `_multi_analyst_output.json`
3. A complete serialisation of `ExplainabilityBlock.to_dict()`

If the embedded `explanation` field and the standalone file ever diverge, the embedded field is authoritative.

---

## Full ExplainabilityBlock JSON example

```json
{
  "instrument": "EURUSD",
  "as_of_utc": "2026-03-07T10:15:00Z",
  "source_verdict": "long_bias",
  "source_confidence": "moderate",

  "signal_ranking": {
    "dominant_signal": "htf_regime",
    "primary_conflict": "caution_flags",
    "signals": [
      {"signal": "htf_regime",     "value": "bullish",          "influence": "dominant",    "direction": "bullish", "note": "4h regime bullish — HTF gate passed."},
      {"signal": "bos_mss",        "value": "bullish_bos",      "influence": "supporting",  "direction": "bullish", "note": "Bullish BOS on 1h confirms directional momentum."},
      {"signal": "fvg_context",    "value": "discount_bullish", "influence": "supporting",  "direction": "bullish", "note": "Active discount FVG at 1.08475 — price approaching from above."},
      {"signal": "sweep_reclaim",  "value": "bullish_reclaim",  "influence": "supporting",  "direction": "bullish", "note": "Bullish reclaim of equal_lows confirmed."},
      {"signal": "liquidity",      "value": "above_closer",     "influence": "conflicting", "direction": "bearish", "note": "External liquidity (prior_day_high) closer above — potential barrier."},
      {"signal": "caution_flags",  "value": "ltf_mss_conflict", "influence": "conflicting", "direction": "bearish", "note": "LTF bearish MSS on 15m active — minor conflict against HTF bias."},
      {"signal": "no_trade_flags", "value": "none",             "influence": "neutral",     "direction": "n/a",     "note": "No hard no-trade flags active."}
    ]
  },

  "persona_dominance": {
    "direction_driver": "both",
    "confidence_driver": "execution_timing",
    "confidence_effect": "downgraded",
    "stricter_persona": "execution_timing",
    "python_override_active": false,
    "note": "Both personas agreed on bullish direction. Execution/Timing was stricter at moderate confidence. Arbiter used lower tier — confidence downgraded from high to moderate."
  },

  "confidence_provenance": {
    "final_confidence": "moderate",
    "python_override": false,
    "override_reason": null,
    "steps": [
      {"step": 1, "label": "Technical Structure Analyst", "value": "high",     "rule": "persona output"},
      {"step": 2, "label": "Execution/Timing Analyst",    "value": "moderate", "rule": "persona output"},
      {"step": 3, "label": "Consensus state",             "value": "directional_alignment_confidence_split", "rule": "arbiter classification"},
      {"step": 4, "label": "Arbiter rule applied",        "value": "moderate", "rule": "use lower confidence on split"},
      {"step": 5, "label": "Final confidence",            "value": "moderate", "rule": "no override"}
    ]
  },

  "causal_chain": {
    "has_hard_block": false,
    "no_trade_drivers": [],
    "caution_drivers": [
      {"flag": "ltf_mss_conflict",     "source": "digest", "raised_by": "pre_filter", "effect": "caution — did not block verdict"},
      {"flag": "liquidity_above_close","source": "digest", "raised_by": "pre_filter", "effect": "caution — contributed to execution persona confidence downgrade"}
    ]
  },

  "audit_summary": "HTF Context: 4h regime was bullish. Last confirmed BOS was bullish on 1h. Last MSS was bearish on 15m — classified as minor LTF conflict.\n\nLiquidity: Nearest overhead level was prior_day_high at 1.08720 (external). Nearest support was equal_lows at 1.08410 (internal). Liquidity draw toward levels above.\n\nFVG Context: Active bullish FVG at 1.08475–1.08620 (1h, open). Price approaching from above — discount zone active.\n\nSweep/Reclaim: Bullish reclaim of equal_lows confirmed. Supportive of bullish continuation.\n\nPersona Summary: Technical Structure returned long_bias at high confidence. Execution/Timing returned conditional at moderate confidence. Consensus: directional alignment, confidence split. Arbiter used lower confidence tier.\n\nFinal Verdict: long_bias — moderate confidence. Active cautions: ltf_mss_conflict, liquidity_above_close. No hard no-trade flags were active."
}
```
