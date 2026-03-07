# ACCEPTANCE_TESTS.md — Phase 3G Exit Criteria

## How to use this file

Run Group 0 first. Any failure stops all further work. All Groups A–G are pure Python — no LLM calls are required or permitted anywhere in this test suite. Report pass/fail per group before declaring Phase 3G complete.

---

## Group 0 — Full regression

### T0.1 — All prior phase tests pass

```bash
pytest market_data_officer/tests/ tests/test_pre_filter.py tests/test_analyst_verdict.py tests/test_analyst_integration.py tests/test_personas.py tests/test_arbiter.py tests/test_multi_analyst_integration.py
# All must pass — 0 failures
```

### T0.2 — 3F multi-analyst service runs unchanged

```python
from analyst.multi_analyst_service import run_multi_analyst
output = run_multi_analyst("EURUSD")
assert output.arbiter_decision is not None
assert len(output.persona_outputs) == 2
```

### T0.3 — Existing modules not modified (additive field on multi_contracts.py expected)

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/|analyst/pre_filter|analyst/contracts\.py|analyst/prompt_builder|analyst/analyst\.py|analyst/service|analyst/personas|analyst/arbiter|analyst/multi_analyst_service"
# Must return no output
```

`analyst/multi_contracts.py` IS expected to appear in the diff — it gains one additive optional field.
If it does not appear, the `explanation` field was not added and 3G is incomplete.
All other analyst modules above must show zero modifications.

---

## Group A — ExplainabilityBlock construction

### TA.1 — ExplainabilityBlock produced from valid MultiAnalystOutput

```python
from analyst.explainability import build_explanation
from analyst.multi_analyst_service import run_multi_analyst

output = run_multi_analyst("EURUSD")
block = build_explanation(output)

assert block is not None
assert block.instrument == "EURUSD"
assert block.source_verdict == output.arbiter_decision.final_verdict
assert block.source_confidence == output.arbiter_decision.final_confidence
```

### TA.2 — All seven signals present in ranking

```python
from analyst.explainability import REQUIRED_SIGNALS

signal_names = {s.signal for s in block.signal_ranking.signals}
assert signal_names == REQUIRED_SIGNALS
```

### TA.3 — All influence values are valid

```python
valid_influences = {"dominant", "supporting", "conflicting", "neutral", "absent"}
for s in block.signal_ranking.signals:
    assert s.influence in valid_influences
```

### TA.4 — Confidence provenance has at least 5 steps

```python
assert len(block.confidence_provenance.steps) >= 5
assert block.confidence_provenance.final_confidence == output.arbiter_decision.final_confidence
```

### TA.5 — Causal chain distinguishes no-trade from caution drivers

```python
assert isinstance(block.causal_chain.no_trade_drivers, list)
assert isinstance(block.causal_chain.caution_drivers, list)
# no overlap between the two lists
nt_flags = {d.flag for d in block.causal_chain.no_trade_drivers}
caution_flags = {d.flag for d in block.causal_chain.caution_drivers}
assert nt_flags.isdisjoint(caution_flags)
```

### TA.6 — `audit_summary` is a non-empty string

```python
assert isinstance(block.audit_summary, str)
assert len(block.audit_summary) > 100
```

---

## Group B — Signal influence classification

### TB.1 — Bullish HTF regime with pass gate → `dominant` bullish

```python
from analyst.explainability import classify_signal_influence

influence = classify_signal_influence("htf_regime", bullish_pass_digest, verdict="long_bias")
assert influence == "dominant"
```

### TB.2 — Unavailable structure → htf_regime `absent`

```python
influence = classify_signal_influence("htf_regime", no_structure_digest, verdict="long_bias")
assert influence == "absent"
```

### TB.3 — External liquidity just above price (bullish verdict) → `conflicting`

```python
influence = classify_signal_influence("liquidity", liquidity_above_close_digest, verdict="long_bias")
assert influence == "conflicting"
```

### TB.4 — Discount FVG active (bullish verdict) → `supporting`

```python
influence = classify_signal_influence("fvg_context", discount_fvg_digest, verdict="long_bias")
assert influence in ("dominant", "supporting")
```

### TB.5 — No active FVG → `neutral` or `absent`

```python
influence = classify_signal_influence("fvg_context", no_fvg_digest, verdict="long_bias")
assert influence in ("neutral", "absent")
```

### TB.6 — Active no-trade flag → no_trade_flags `conflicting`

```python
influence = classify_signal_influence("no_trade_flags", no_trade_digest, verdict="no_trade")
assert influence == "conflicting"
```

### TB.7 — No flags → no_trade_flags `neutral`

```python
influence = classify_signal_influence("no_trade_flags", clean_digest, verdict="long_bias")
assert influence == "neutral"
```

---

## Group C — Persona dominance

### TC.1 — Both personas agree direction → `direction_driver = "both"`

```python
from analyst.explainability import compute_persona_dominance

dominance = compute_persona_dominance(aligned_persona_outputs, aligned_arbiter)
assert dominance.direction_driver == "both"
```

### TC.2 — Confidence split → stricter persona identified

```python
# technical=high, execution=moderate
dominance = compute_persona_dominance(split_confidence_outputs, split_arbiter)
assert dominance.stricter_persona == "execution_timing"
assert dominance.confidence_driver == "execution_timing"
assert dominance.confidence_effect == "downgraded"
```

### TC.3 — Python override active → `direction_driver = "arbiter_override"`

```python
dominance = compute_persona_dominance(no_trade_outputs, no_trade_arbiter)
assert dominance.direction_driver == "arbiter_override"
assert dominance.python_override_active is True
assert dominance.confidence_effect == "overridden_by_python"
```

### TC.4 — Dominance `note` field is a non-empty string

```python
assert isinstance(dominance.note, str)
assert len(dominance.note) > 10
```

---

## Group D — Confidence provenance

### TD.1 — Full alignment path produces correct steps

```python
from analyst.explainability import compute_confidence_provenance

# Fixture: both personas high, full_alignment, final=high
prov = compute_confidence_provenance(aligned_outputs, full_alignment_arbiter, clean_digest)

assert prov.steps[0].value == "high"   # technical
assert prov.steps[1].value == "high"   # execution
assert prov.steps[2].value == "full_alignment"
assert prov.final_confidence == "high"
assert prov.python_override is False
```

### TD.2 — Confidence split path records downgrade

```python
prov = compute_confidence_provenance(split_outputs, split_arbiter, clean_digest)

assert prov.steps[0].value == "high"
assert prov.steps[1].value == "moderate"
assert "lower" in prov.steps[3].rule.lower()
assert prov.final_confidence == "moderate"
```

### TD.3 — Python override path records override

```python
prov = compute_confidence_provenance(any_outputs, any_arbiter, no_trade_digest)

assert prov.python_override is True
assert prov.final_confidence == "none"
assert prov.override_reason is not None
assert len(prov.steps) >= 5
```

---

## Group E — Replay determinism

### TE.1 — Same MultiAnalystOutput produces identical ExplainabilityBlock

```python
from analyst.explainability import build_explanation

block_a = build_explanation(output)
block_b = build_explanation(output)

assert block_a.to_dict() == block_b.to_dict()
```

### TE.2 — Replay from saved file produces identical block

```python
import json, tempfile, os
from analyst.explainability import build_explanation_from_dict
from analyst.multi_contracts import MultiAnalystOutput

# Save output to temp file
with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    json.dump(output.to_dict(), f)
    tmp_path = f.name

# Reload and re-derive
with open(tmp_path) as f:
    saved_dict = json.load(f)

reloaded_output = MultiAnalystOutput.from_dict(saved_dict)
replayed_block = build_explanation(reloaded_output)

assert block_a.to_dict() == replayed_block.to_dict()
os.unlink(tmp_path)
```

### TE.3 — Different structure inputs produce different signal rankings

```python
block_bullish = build_explanation(bullish_output)
block_bearish = build_explanation(bearish_output)

assert block_bullish.signal_ranking.dominant_signal != block_bearish.signal_ranking.dominant_signal or \
       block_bullish.confidence_provenance.final_confidence != block_bearish.confidence_provenance.final_confidence
```

---

## Group F — Output files

### TF.1 — `explanation` field populated in MultiAnalystOutput after full run

```python
from analyst.multi_analyst_service import run_multi_analyst
output = run_multi_analyst("EURUSD")
assert output.explanation is not None
assert isinstance(output.explanation.audit_summary, str)
```

### TF.2 — Standalone explainability file written

```python
import os
assert os.path.exists("analyst/output/EURUSD_multi_analyst_explainability.json")
```

### TF.3 — Standalone file matches embedded block

```python
import json
with open("analyst/output/EURUSD_multi_analyst_explainability.json") as f:
    standalone = json.load(f)

assert standalone == output.explanation.to_dict()
```

### TF.4 — Main output file also contains explanation field

```python
with open("analyst/output/EURUSD_multi_analyst_output.json") as f:
    main = json.load(f)

assert "explanation" in main
assert main["explanation"]["source_verdict"] == output.arbiter_decision.final_verdict
```

### TF.5 — JSON serialisation roundtrip is lossless

```python
import json
block = output.explanation
serialized = json.dumps(block.to_dict())
restored = json.loads(serialized)
assert restored["confidence_provenance"]["final_confidence"] == block.confidence_provenance.final_confidence
assert len(restored["signal_ranking"]["signals"]) == 7
```

---

## Group G — CLI and cross-instrument coverage

### TG.1 — CLI run-time generation works

```bash
python run_explain.py --instrument EURUSD
python run_explain.py --instrument XAUUSD
# Both must complete without exception and write explainability files
```

### TG.2 — CLI replay from file works

```bash
python run_explain.py --file analyst/output/EURUSD_multi_analyst_output.json
# Must produce identical explainability output as TG.1 EURUSD run
```

### TG.3 — No LLM calls made in any explain path

```python
# Mock LLM client — must not be called
with mock.patch("anthropic.Anthropic") as mock_client:
    from analyst.explainability import build_explanation
    block = build_explanation(output)
    mock_client.assert_not_called()
```

### TG.4 — Final: no existing modules modified (additive field on multi_contracts.py expected)

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/|analyst/pre_filter|analyst/contracts\.py|analyst/prompt_builder|analyst/analyst\.py|analyst/service|analyst/personas|analyst/arbiter|analyst/multi_analyst_service"
# Must return no output
```

`analyst/multi_contracts.py` IS expected in the diff — additive `explanation` field only.
Verify the change is additive: `git diff HEAD analyst/multi_contracts.py` must show only the new field, no deletions or modifications to existing fields.

---

## Phase 3G sign-off checklist

- [ ] Group 0 — Full regression + 3F service: 0 failures
- [ ] Group A — ExplainabilityBlock construction: all pass
- [ ] Group B — Signal influence classification: all pass
- [ ] Group C — Persona dominance: all pass
- [ ] Group D — Confidence provenance: all pass
- [ ] Group E — Replay determinism: all pass
- [ ] Group F — Output files: all pass
- [ ] Group G — CLI and cross-instrument: all pass
- [ ] Zero LLM calls in entire explain path — verified by mock test TG.3
- [ ] All 7 signals present in every ranking — validator asserts
- [ ] Confidence provenance has ≥ 5 steps — validator asserts
- [ ] Standalone file derived from embedded field — not independently computed
- [ ] Replay from saved file produces byte-identical structured fields
- [ ] `audit_summary` is template-rendered, not generated
- [ ] Only change to existing files: `multi_contracts.py` additive field
- [ ] Both EURUSD and XAUUSD produce valid ExplainabilityBlock
