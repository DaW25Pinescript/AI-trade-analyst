# OBJECTIVE.md — Phase 3F: Multi-Analyst Consensus Layer

## Why Phase 3F exists

Phase 3E proved that a single LLM analyst can consume a deterministic `StructureDigest` and produce a validated structured verdict. The single-analyst model works. But it has one structural weakness: a single LLM call has no internal disagreement. If the prompt nudges toward a bullish read, nothing pushes back on timing or execution quality.

3F introduces controlled disagreement. Two analyst personas read the same digest from different professional perspectives and produce separate verdicts. An Arbiter synthesizes them. That creates:

- **Better explainability** — you can see exactly where the two personas agree or conflict
- **Stronger decision discipline** — conflicts force the system toward caution, not false confidence
- **Auditable reasoning** — every component of the final decision is preserved and inspectable
- **Replayable structure** — same digest produces same contract shape every time

## What the two personas are

### Persona A — Technical Structure Analyst

**Focus:** Is the structural case valid?

- HTF regime consistency
- BOS/MSS direction and quality
- Liquidity positioning (internal vs external)
- FVG zone context (discount/premium)
- Sweep/reclaim outcome interpretation

**Prompt emphasis:** Assess directional structure alignment. Judge regime consistency. Weigh BOS/MSS, liquidity, FVG, and sweep context. Avoid execution micro-optimism — this persona does not care whether now is a good time to enter, only whether the structural case is sound.

---

### Persona B — Execution/Timing Analyst

**Focus:** Is this a good place and time to act?

- Proximity and quality of nearby liquidity barriers
- FVG positioning relative to current price
- Reclaim vs acceptance outcome interpretation
- Execution cleanliness (is price extended, compressed, crowded?)
- Short-term conflict signals (LTF MSS, partial FVG fill, unresolved sweeps)

**Prompt emphasis:** Assess timing quality and execution risk. Judge whether the entry context is clean, late, risky, or weak. Focus on nearby barriers, FVG positioning, and reclaim outcome. Avoid over-extending into structural narrative — this persona does not re-assess HTF regime, only execution context.

**The intended tension:** Persona A answers "is the idea structurally valid?" Persona B answers "is this a good place/time to act?" These two questions can and will disagree. That disagreement is the signal.

---

## The Arbiter

The Arbiter is not a third LLM opinion. It is a synthesis layer that applies deterministic conflict rules where possible and uses a constrained LLM call for the synthesis narrative only.

### Arbiter responsibilities

1. Read both `PersonaVerdict` outputs
2. Identify consensus state (see taxonomy below)
3. Apply conflict rules deterministically
4. Produce `ArbiterDecision` with final direction and confidence
5. Record which persona(s) contributed to the final verdict and why
6. Enforce Python hard-constraint layer — no persona enthusiasm can override a no-trade flag

### Consensus state taxonomy

Evaluated in this exact order — first match wins:

| Priority | State | Condition |
|---|---|---|
| 1 | `no_trade` | `digest.has_hard_no_trade()` is True — overrides everything |
| 2 | `blocked` | Either persona returns `no_trade` or `no_data` |
| 3 | `full_alignment` | Both personas directional, same direction, same confidence tier |
| 4 | `directional_alignment_confidence_split` | Both personas directional, same direction, different confidence |
| 5 | `mixed` | Both personas directional, opposite directions |
| 6 | `conditional` | One or both personas return `conditional` (and neither is `no_trade`/`no_data`) |

**Explicit case resolution:**

| Persona A | Persona B | State | Final verdict | Final confidence |
|---|---|---|---|---|
| `long_bias` high | `long_bias` high | `full_alignment` | `long_bias` | `high` |
| `long_bias` high | `long_bias` moderate | `directional_alignment_confidence_split` | `long_bias` | `moderate` |
| `long_bias` | `short_bias` | `mixed` | `conditional` | `low` |
| `long_bias` | `conditional` | `conditional` | `conditional` | `low` |
| `conditional` | `conditional` | `conditional` | `conditional` | `low` |
| `long_bias` | `no_trade` | `blocked` | `no_trade` | `none` |
| `no_trade` | `no_trade` | `blocked` | `no_trade` | `none` |
| any | any + hard flag | `no_trade` | `no_trade` | `none` |

### Arbiter conflict rules (deterministic)

```
if digest.has_hard_no_trade():
    final = no_trade, confidence = none, state = no_trade

elif consensus_state == full_alignment:
    final = persona direction, can upgrade confidence slightly

elif consensus_state == directional_alignment_confidence_split:
    final = persona direction, use lower confidence

elif consensus_state == mixed:
    final = conditional, confidence = low, caution flag added

elif consensus_state == blocked:
    final = no_trade or conditional depending on severity
```

The Arbiter LLM call — if used — receives only:
- The `ArbiterDecision` skeleton (pre-computed fields above)
- Both `PersonaVerdict` summaries
- A prompt to write the `synthesis_notes` and `winning_rationale_summary` fields only

The Arbiter LLM never recomputes direction or confidence. Those are pre-determined by the rules above.

---

## What 3F explicitly does NOT include

| Out of scope | Phase |
|---|---|
| Senate / full council layer | Future |
| Open-ended agent debate | Future |
| Macro Alignment persona | Deferred until macro is in packet form |
| Memory or cross-session state | Future |
| Model routing / provider selection logic | Future |
| Changes to pre-filter, feed, Officer, structure engine | Never in 3F |
| Modifying `analyst/service.py` or any 3E module | Never in 3F |

---

## Definition of done

Phase 3F is complete when:

- Both personas consume the same `StructureDigest` — no direct packet access in persona prompts
- Persona outputs conform to `PersonaVerdict` schema
- Arbiter applies conflict rules deterministically before any LLM synthesis call
- Python hard-constraint layer overrides all persona outputs
- `MultiAnalystOutput` is written atomically to file
- `analyst/service.py` (3E single-analyst) runs unchanged
- Both EURUSD and XAUUSD produce valid `MultiAnalystOutput`
- All test groups pass
- All prior phase tests pass
