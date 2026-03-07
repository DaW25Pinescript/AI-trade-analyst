# OBJECTIVE.md — Phase 3G: Explainability / Audit Layer

## Why Phase 3G exists

By the end of Phase 3F the system produces a rich decision artifact: digest, two persona verdicts, an Arbiter synthesis, and a final verdict. But most of the reasoning is trapped inside prose fields and JSON blobs. A human reviewing the output — or a downstream system consuming it — cannot easily answer:

- Why was the verdict `long_bias` and not `conditional`?
- Which signal most influenced the outcome?
- Did the Execution Timing persona constrain confidence, or did the Arbiter?
- Was the Python hard-constraint layer involved?
- If I replay this tomorrow, will I get the same explanation?

3G closes that gap. It adds a structured, deterministic, replay-safe explanation layer that answers all of these questions from saved artifacts alone — no re-running models, no LLM calls, no reinterpretation.

The key design principle: **3G explains decisions already made. It does not make new ones.**

---

## The four explanation outputs

### 1. Signal Influence Ranking

A ranked list of which structure signals had the most influence on the final verdict, with direction and magnitude classification for each.

Signals ranked:
- HTF regime
- BOS/MSS direction
- Liquidity positioning
- FVG context
- Sweep/reclaim outcome
- Active no-trade flags
- Active caution flags

Influence is classified, not scored with fake precision:
- `dominant` — signal was the primary driver
- `supporting` — signal reinforced the verdict
- `conflicting` — signal worked against the verdict
- `neutral` — signal was present but did not materially shift outcome
- `absent` — signal was unavailable

---

### 2. Persona Dominance Record

A compact record of how each persona contributed to, constrained, or was overridden in the final decision.

Fields:
- Which persona drove the directional verdict
- Which persona drove (or caused the downgrade of) the final confidence
- Whether the Arbiter used the stricter or more lenient confidence tier
- Whether the Python hard-constraint layer overrode both personas
- Consensus state classification and its downstream effect

This is computed from `ArbiterDecision` and `PersonaVerdict` fields — no interpretation needed.

---

### 3. Confidence Provenance

A step-by-step trace of how `final_confidence` was determined.

```
Step 1: Technical Structure Analyst → high
Step 2: Execution/Timing Analyst    → moderate
Step 3: Consensus state             → directional_alignment_confidence_split
Step 4: Arbiter rule applied        → use lower confidence
Step 5: Final confidence            → moderate
Step 6: Python override             → not triggered
```

Each step records the rule applied and the input values. Fully reconstructible from saved `MultiAnalystOutput`.

---

### 4. No-Trade / Caution Driver List

An explicit, machine-readable list of what blocked or weakened the setup, with source attribution for each entry.

```json
{
  "no_trade_drivers": [],
  "caution_drivers": [
    {
      "flag": "ltf_mss_conflict",
      "source": "digest",
      "raised_by": "pre_filter",
      "effect": "caution — did not block verdict"
    },
    {
      "flag": "liquidity_above_close",
      "source": "digest",
      "raised_by": "pre_filter",
      "effect": "caution — contributed to execution persona confidence downgrade"
    }
  ]
}
```

---

## The human-readable audit summary

On top of the four structured fields above, 3G renders a human-readable audit summary using deterministic templates — no LLM.

Templates use saved field values to produce strings like:

```
HTF Context: 4h regime was bullish. Last confirmed BOS was bullish on 1h.
Last MSS was bearish on 15m — classified as minor LTF conflict.

Liquidity: Nearest overhead level was prior_day_high at 1.08720 (external).
Nearest support was equal_lows at 1.08410 (internal). Liquidity draw above.

FVG Context: Active bullish FVG at 1.08475–1.08620 (1h, open).
Price approaching from above — discount zone in play.

Sweep/Reclaim: Bullish reclaim of equal_lows confirmed. Supportive.

Persona Summary: Technical Structure returned long_bias at high confidence.
Execution/Timing returned conditional at moderate confidence.
Consensus: directional alignment, confidence split. Arbiter used lower tier.

Final Verdict: long_bias — moderate confidence.
Caution: ltf_mss_conflict, liquidity_above_close.
No hard no-trade flags were active.
```

This is a template fill-in, not generation. The same saved output always produces the same audit text.

---

## Output artifacts

### Embedded in `MultiAnalystOutput`

```python
@dataclass
class MultiAnalystOutput:
    ...
    explanation: Optional[ExplainabilityBlock] = None  # new in 3G
```

This is the authoritative explanation contract.

### Standalone file

```
analyst/output/{instrument}_multi_analyst_explainability.json
```

Derived from the embedded `explanation` field. Written at the same time as the main output. Not a separate source of truth — if they diverge, the embedded version wins.

---

## Replay mode

`run_explain.py` must support:

```bash
python run_explain.py --instrument EURUSD
# Re-derive explanation from saved multi_analyst_output.json without any model calls

python run_explain.py --file analyst/output/EURUSD_multi_analyst_output.json
# Same, explicit file path
```

Given any saved `MultiAnalystOutput`, the explanation engine must reproduce the identical `ExplainabilityBlock` deterministically. This is the core replay guarantee.

---

## What 3G explicitly does NOT include

| Out of scope | Phase |
|---|---|
| New structure signals or features | 4A+ |
| LLM-generated explanation prose | Never in 3G |
| Multi-session memory or trend tracking | Future |
| UI rendering layer | Future |
| Performance scoring / backtesting | Future |
| Senate / governance layer | Future |
| Any modification to feed, Officer, structure engine | Never |

---

## Definition of done

Phase 3G is complete when:

- `ExplainabilityBlock` is produced deterministically from any saved `MultiAnalystOutput`
- All four explanation fields are Python-computed: signal ranking, persona dominance, confidence provenance, no-trade/caution drivers
- Human-readable audit summary is template-rendered, no LLM
- `MultiAnalystOutput.explanation` is populated on every 3F run going forward
- Standalone `_explainability.json` file is written alongside `_multi_analyst_output.json`
- Replay mode reproduces identical output from saved file
- `analyst/multi_contracts.py` gains `explanation` field — no other existing file modified
- Both EURUSD and XAUUSD produce valid `ExplainabilityBlock`
- All test groups pass
- All prior phase tests pass
