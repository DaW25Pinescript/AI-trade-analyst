# ACCEPTANCE_TESTS.md — Phase 3F Exit Criteria

## How to use this file

Run Group 0 first. Any failure stops all further work. Groups A–D test deterministic logic without LLM calls. Groups E–G test the full pipeline including LLM. Report pass/fail per group before declaring Phase 3F complete.

---

## Group 0 — Full regression

### T0.1 — All prior phase tests pass

```bash
pytest market_data_officer/tests/ tests/test_pre_filter.py tests/test_analyst_verdict.py tests/test_analyst_integration.py
# All must pass — 0 failures
```

### T0.2 — 3E single-analyst service runs unchanged

```python
from analyst.service import run_analyst
output = run_analyst("EURUSD")
assert output.verdict is not None
assert output.reasoning is not None
```

### T0.3 — Existing analyst modules not modified

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/|analyst/pre_filter|analyst/contracts\.py|analyst/prompt_builder|analyst/analyst\.py|analyst/service"
# Must return no output — imports permitted, modifications forbidden
# analyst/multi_contracts.py is a NEW file and will not appear here
```

---

## Group A — Persona isolation

### TA.1 — Both personas receive the same digest object

```python
from analyst.personas import run_all_personas
from analyst.pre_filter import compute_digest

packet = build_market_packet("EURUSD")
digest = compute_digest(packet)
persona_outputs = run_all_personas(digest)

assert len(persona_outputs) == 2
# Verify same digest was used — spot check key fields
for pv in persona_outputs:
    assert pv.structure_gate == digest.structure_gate
    assert pv.instrument == digest.instrument
```

### TA.2 — Neither persona receives raw structure block

```python
# Inspect prompt_builder output for each persona — must not contain raw structure arrays
from analyst.personas import build_persona_prompt
prompt_a = build_persona_prompt("technical_structure", digest)
prompt_b = build_persona_prompt("execution_timing", digest)

for prompt in (prompt_a, prompt_b):
    assert "swings" not in prompt
    assert '"events"' not in prompt
    assert '"rows"' not in prompt
```

### TA.3 — Persona prompts differ only in system prompt, not data payload

```python
from analyst.personas import build_persona_prompt
prompt_a = build_persona_prompt("technical_structure", digest)
prompt_b = build_persona_prompt("execution_timing", digest)

# Data sections must be identical
assert prompt_a["user_content"] == prompt_b["user_content"]
# System prompts must differ
assert prompt_a["system"] != prompt_b["system"]
```

### TA.4 — Both persona names are correct

```python
names = [pv.persona_name for pv in persona_outputs]
assert "technical_structure" in names
assert "execution_timing" in names
```

---

## Group B — Persona output schema

### TB.1 — PersonaVerdict schema valid for both personas

```python
for pv in persona_outputs:
    assert pv.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
    assert pv.confidence in ("high", "moderate", "low", "none")
    assert pv.directional_bias in ("bullish", "bearish", "neutral", "none")
    assert isinstance(pv.persona_supports, list)
    assert isinstance(pv.persona_conflicts, list)
    assert isinstance(pv.persona_cautions, list)
    assert pv.reasoning is not None
```

### TB.2 — `structure_gate` echoed correctly from digest

```python
for pv in persona_outputs:
    assert pv.structure_gate == digest.structure_gate
```

### TB.3 — Malformed LLM output raises, not silently accepted

```python
import pytest
from analyst.personas import validate_persona_verdict

bad_verdict = PersonaVerdict(..., verdict="STRONG_BUY", ...)
with pytest.raises(ValueError):
    validate_persona_verdict(bad_verdict, digest)
```

### TB.4 — Hard no-trade forces both personas to `no_trade`

```python
no_trade_digest = build_no_trade_digest()  # has_hard_no_trade() == True

persona_outputs = run_all_personas(no_trade_digest)
for pv in persona_outputs:
    assert pv.verdict == "no_trade"
    assert pv.confidence == "none"
```

---

## Group C — Arbiter synthesis

### TC.1 — Full alignment produces aligned final verdict

```python
from analyst.arbiter import compute_consensus

a = PersonaVerdict(..., verdict="long_bias", confidence="high", directional_bias="bullish")
b = PersonaVerdict(..., verdict="long_bias", confidence="high", directional_bias="bullish")
state, verdict, confidence = compute_consensus(a, b, clean_digest)

assert state == "full_alignment"
assert verdict == "long_bias"
assert confidence in ("high", "moderate")  # can hold or slightly upgrade
```

### TC.2 — Directional alignment, confidence split → lower confidence

```python
a = PersonaVerdict(..., verdict="long_bias", confidence="high", directional_bias="bullish")
b = PersonaVerdict(..., verdict="conditional", confidence="moderate", directional_bias="bullish")
state, verdict, confidence = compute_consensus(a, b, clean_digest)

assert state == "directional_alignment_confidence_split"
assert verdict == "long_bias"
assert confidence == "moderate"  # lower of high vs moderate
```

### TC.3 — Directional conflict → mixed, conditional, low

```python
a = PersonaVerdict(..., verdict="long_bias", directional_bias="bullish")
b = PersonaVerdict(..., verdict="short_bias", directional_bias="bearish")
state, verdict, confidence = compute_consensus(a, b, clean_digest)

assert state == "mixed"
assert verdict == "conditional"
assert confidence == "low"
```

### TC.4 — Blocked persona → blocked state, no-trade

```python
a = PersonaVerdict(..., verdict="long_bias", directional_bias="bullish")
b = PersonaVerdict(..., verdict="no_trade", directional_bias="none")
state, verdict, confidence = compute_consensus(a, b, clean_digest)

assert state == "blocked"
assert verdict == "no_trade"
```

### TC.5 — Arbiter does not make LLM call when no-trade enforced

```python
# Mock LLM call counter — must not be called
no_trade_digest = build_no_trade_digest()
with mock.patch("analyst.arbiter.call_llm") as mock_llm:
    decision = arbitrate(persona_outputs, no_trade_digest)
    mock_llm.assert_not_called()

assert decision.no_trade_enforced is True
assert "Hard no-trade" in decision.synthesis_notes
```

---

## Group D — Deterministic constraint enforcement

### TD.1 — Hard no-trade overrides Arbiter LLM output

```python
import pytest
from analyst.arbiter import validate_arbiter_decision

no_trade_digest = build_no_trade_digest()
bad_decision = ArbiterDecision(..., no_trade_enforced=False, final_verdict="long_bias")

with pytest.raises(ValueError, match="no_trade_enforced"):
    validate_arbiter_decision(bad_decision, no_trade_digest)
```

### TD.2 — Arbiter `final_verdict` matches pre-computed value

```python
# After arbitrate() call, LLM must not have changed the verdict
decision = run_arbiter_with_skeleton(pre_computed_verdict="long_bias", llm_returns_verdict="short_bias")
assert decision.final_verdict == "long_bias"  # pre-computed wins
```

### TD.3 — `final_verdict` in MultiAnalystOutput is valid AnalystVerdict

```python
from analyst.service import run_analyst  # reuse 3E validator
output = run_multi_analyst("EURUSD")

# Re-express as AnalystVerdict and validate with 3E schema validator
validate_analyst_verdict(output.final_verdict, output.digest)
```

---

## Group E — Replay and consistency

### TE.1 — Same digest produces same consensus state

```python
output_a = run_multi_analyst_with_digest(digest)
output_b = run_multi_analyst_with_digest(digest)

assert output_a.arbiter_decision.consensus_state == output_b.arbiter_decision.consensus_state
assert output_a.arbiter_decision.final_verdict == output_b.arbiter_decision.final_verdict
assert output_a.arbiter_decision.final_confidence == output_b.arbiter_decision.final_confidence
```

### TE.2 — LLM nondeterminism limited to text fields only

```python
# Run twice, assert contract-shape fields are stable
assert output_a.arbiter_decision.no_trade_enforced == output_b.arbiter_decision.no_trade_enforced
assert output_a.arbiter_decision.personas_agree_direction == output_b.arbiter_decision.personas_agree_direction
```

---

## Group F — Output completeness

### TF.1 — MultiAnalystOutput file written after run

```python
import os
assert os.path.exists("analyst/output/EURUSD_multi_analyst_output.json")
```

### TF.2 — Output file contains all required blocks

```python
import json
with open("analyst/output/EURUSD_multi_analyst_output.json") as f:
    saved = json.load(f)

assert "digest" in saved
assert "persona_outputs" in saved
assert len(saved["persona_outputs"]) == 2
assert "arbiter_decision" in saved
assert "final_verdict" in saved
```

### TF.3 — JSON serialization roundtrip is lossless

```python
import json
output = run_multi_analyst("EURUSD")
serialized = json.dumps(output.to_dict())
restored = json.loads(serialized)
assert restored["arbiter_decision"]["final_verdict"] == output.arbiter_decision.final_verdict
```

### TF.4 — 3E single-analyst output file preserved and unchanged

```python
assert os.path.exists("analyst/output/EURUSD_analyst_output.json")
# File must still be written by analyst/service.py independently
```

---

## Group G — Cross-instrument coverage

### TG.1 — CLI runs end-to-end for both instruments

```bash
python run_multi_analyst.py --instrument EURUSD
python run_multi_analyst.py --instrument XAUUSD
# Both must complete without exception
```

### TG.2 — Both instruments produce valid MultiAnalystOutput

```python
for instrument in ("EURUSD", "XAUUSD"):
    output = run_multi_analyst(instrument)
    assert output.arbiter_decision.final_verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
    assert len(output.persona_outputs) == 2
```

### TG.3 — Final check: no existing files modified

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/|analyst/pre_filter|analyst/contracts\.py|analyst/prompt_builder|analyst/analyst\.py|analyst/service"
# Must return no output
```

---

## Phase 3F sign-off checklist

- [ ] Group 0 — Full regression + 3E service: 0 failures
- [ ] Group A — Persona isolation: all pass
- [ ] Group B — Persona output schema: all pass
- [ ] Group C — Arbiter synthesis: all pass
- [ ] Group D — Deterministic constraint enforcement: all pass
- [ ] Group E — Replay and consistency: all pass
- [ ] Group F — Output completeness: all pass
- [ ] Group G — Cross-instrument coverage: all pass
- [ ] Both personas use identical digest — verified
- [ ] Arbiter direction/confidence pre-computed in Python — LLM writes text only
- [ ] Hard no-trade skips Arbiter LLM call entirely
- [ ] `final_verdict` passes 3E AnalystVerdict validator
- [ ] MultiAnalystOutput written atomically
- [ ] 3E `analyst/service.py` runs unchanged
- [ ] Feed, Officer, structure engine, all 3E modules: 0 modifications
