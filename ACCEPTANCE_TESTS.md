# ACCEPTANCE_TESTS.md — Phase 3E Exit Criteria

## How to use this file

Run Group 0 first. Any failure stops all further work. Groups A–D test the Python pre-filter without any LLM. Groups E–G test the full pipeline including LLM calls. Report pass/fail per group before declaring Phase 3E complete.

---

## Group 0 — Full regression

### T0.1 — All prior phase tests pass

```bash
pytest market_data_officer/tests/
# All must pass — 0 failures
```

### T0.2 — Feed, Officer, structure engine files not modified

3E imports from `officer/` (e.g. `build_market_packet`) but must not edit any existing file there.
Imports are fine. Modifications are forbidden.

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/"
# Must return no output — no existing files in these paths may be modified
# New files under analyst/ are expected and correct
```

---

## Group A — Pre-filter: StructureDigest production

### TA.1 — Digest produced from valid v2 packet

```python
from analyst.pre_filter import compute_digest
from officer.service import build_market_packet

packet = build_market_packet("EURUSD")
digest = compute_digest(packet)

assert digest is not None
assert digest.instrument == "EURUSD"
assert digest.structure_gate in ("pass", "fail", "no_data", "mixed")
```

### TA.2 — `structure_available=False` produces `no_data` gate

```python
# Simulate unavailable structure
packet_no_structure = build_market_packet_without_structure("EURUSD")
digest = compute_digest(packet_no_structure)

assert digest.structure_available is False
assert digest.structure_gate == "no_data"
assert digest.has_hard_no_trade() is True
assert "no_structure_data" in digest.no_trade_flags
```

### TA.3 — Bullish 4h regime produces `pass` gate

```python
# Fixture: packet with structure.regime.bias = "bullish", source_timeframe = "4h"
digest = compute_digest(bullish_4h_packet)
assert digest.structure_gate == "pass"
assert digest.htf_bias == "bullish"
assert digest.htf_source_timeframe == "4h"
```

### TA.4 — Neutral 4h regime produces `mixed` gate

```python
digest = compute_digest(neutral_regime_packet)
assert digest.structure_gate == "mixed"
assert "htf_regime_neutral" in digest.no_trade_flags
```

### TA.5 — Conflicting 4h/1h regimes produce `mixed` gate

```python
# Fixture: 4h bias="bullish", 1h bias="bearish"
digest = compute_digest(conflicting_regime_packet)
assert digest.structure_gate == "mixed"
```

### TA.6 — BOS/MSS alignment classified correctly

```python
# Fixture: last BOS bullish, last MSS bearish
digest = compute_digest(mixed_bos_mss_packet)
assert digest.last_bos == "bullish"
assert digest.last_mss == "bearish"
assert digest.bos_mss_alignment == "conflicted"
```

### TA.7 — Aligned BOS/MSS produces `aligned`

```python
# Fixture: last BOS bullish, last MSS bullish
digest = compute_digest(aligned_packet)
assert digest.bos_mss_alignment == "aligned"
```

### TA.8 — FVG context: discount_bullish when price below bullish FVG

```python
# Fixture: active bullish FVG zone_low=1.08475, current price=1.08400
digest = compute_digest(discount_fvg_packet)
assert digest.active_fvg_context == "discount_bullish"
```

### TA.9 — FVG context: at_fvg when price inside zone

```python
# Fixture: bullish FVG zone_low=1.08475, zone_high=1.08620, current price=1.08550
digest = compute_digest(inside_fvg_packet)
assert digest.active_fvg_context == "at_fvg"
```

### TA.10 — FVG context: none when no active zones

```python
digest = compute_digest(no_fvg_packet)
assert digest.active_fvg_context == "none"
assert digest.active_fvg_count == 0
```

### TA.11 — Bullish reclaim produces `bullish_reclaim` sweep signal

```python
# Fixture: recent swept level with outcome="reclaimed", low-side type
digest = compute_digest(bullish_reclaim_packet)
assert digest.recent_sweep_signal == "bullish_reclaim"
```

### TA.12 — structure_supports and structure_conflicts are lists, never None

```python
digest = compute_digest(any_packet)
assert isinstance(digest.structure_supports, list)
assert isinstance(digest.structure_conflicts, list)
```

---

## Group B — Pre-filter: determinism

### TB.1 — Same packet produces identical digest

```python
digest_a = compute_digest(packet)
digest_b = compute_digest(packet)

assert digest_a.structure_gate == digest_b.structure_gate
assert digest_a.htf_bias == digest_b.htf_bias
assert digest_a.active_fvg_context == digest_b.active_fvg_context
assert digest_a.structure_supports == digest_b.structure_supports
assert digest_a.structure_conflicts == digest_b.structure_conflicts
```

### TB.2 — Digest changes when structure changes

```python
digest_bullish = compute_digest(bullish_regime_packet)
digest_bearish = compute_digest(bearish_regime_packet)

assert digest_bullish.htf_bias != digest_bearish.htf_bias
assert digest_bullish.structure_gate != digest_bearish.structure_gate or \
       digest_bullish.structure_supports != digest_bearish.structure_supports
```

---

## Group C — Pre-filter: flag logic

### TC.1 — `htf_gate_fail` flag when regime contradicts direction

```python
# Fixture: bearish regime, proposed long direction
digest = compute_digest(bearish_regime_long_direction_packet)
assert "htf_gate_fail" in digest.no_trade_flags
assert digest.has_hard_no_trade() is True
```

### TC.2 — `ltf_mss_conflict` caution when LTF MSS against HTF

```python
# Fixture: HTF bullish, 15m bearish MSS present
digest = compute_digest(ltf_mss_conflict_packet)
assert "ltf_mss_conflict" in digest.caution_flags
assert "ltf_mss_conflict" not in digest.no_trade_flags  # caution only, not hard gate
```

### TC.3 — `liquidity_above_close` caution when external level near above

```python
# Fixture: prior_day_high just above current price (within 0.5 ATR)
digest = compute_digest(liquidity_close_above_packet)
assert "liquidity_above_close" in digest.caution_flags
```

### TC.4 — No flags on clean aligned structure

```python
# Fixture: bullish regime, aligned BOS/MSS, no conflicting levels
digest = compute_digest(clean_bullish_packet)
assert digest.no_trade_flags == []
assert "ltf_mss_conflict" not in digest.caution_flags
```

---

## Group D — Pre-filter: to_prompt_dict

### TD.1 — `to_prompt_dict()` produces serialisable dict

```python
import json
d = digest.to_prompt_dict()
json.dumps(d)  # must not raise
```

### TD.2 — `to_prompt_dict()` does not contain raw structure arrays

```python
d = digest.to_prompt_dict()
assert "swings" not in str(d)
assert "events" not in str(d)
assert "rows" not in str(d)
```

### TD.3 — `to_prompt_dict()` contains all key digest fields

```python
d = digest.to_prompt_dict()
required = {
    "structure_gate", "htf_bias", "last_bos", "last_mss",
    "active_fvg_context", "recent_sweep_signal",
    "structure_supports", "structure_conflicts",
    "no_trade_flags", "caution_flags"
}
assert required.issubset(d.keys())
```

---

## Group E — LLM analyst: verdict schema

### TE.1 — Verdict contains all required fields

```python
from analyst.service import run_analyst

output = run_analyst("EURUSD")
verdict = output.verdict

assert verdict.verdict in ("long_bias", "short_bias", "no_trade", "conditional", "no_data")
assert verdict.confidence in ("high", "moderate", "low", "none")
assert verdict.structure_gate in ("pass", "fail", "no_data", "mixed")
assert isinstance(verdict.structure_supports, list)
assert isinstance(verdict.structure_conflicts, list)
assert isinstance(verdict.no_trade_flags, list)
assert isinstance(verdict.caution_flags, list)
```

### TE.2 — Hard no-trade flag forces `no_trade` verdict

```python
# Simulate digest with no_trade_flags = ["no_structure_data"]
output = run_analyst_with_digest(no_trade_digest)
assert output.verdict.verdict == "no_trade"
assert output.verdict.confidence == "none"
```

### TE.3 — Validator raises if LLM overrides hard no-trade

```python
import pytest
from analyst.analyst import validate_verdict

no_trade_digest.no_trade_flags = ["no_structure_data"]
bad_verdict = AnalystVerdict(..., verdict="long_bias", confidence="high", ...)

with pytest.raises(ValueError, match="hard no-trade"):
    validate_verdict(bad_verdict, no_trade_digest)
```

### TE.4 — `structure_gate` in verdict matches digest gate

```python
assert output.verdict.structure_gate == output.digest.structure_gate
```

---

## Group F — LLM analyst: reasoning block

### TF.1 — ReasoningBlock contains all required fields

```python
reasoning = output.reasoning
assert reasoning.summary
assert reasoning.htf_context
assert reasoning.liquidity_context
assert reasoning.fvg_context
assert reasoning.sweep_context
assert reasoning.verdict_rationale
```

### TF.2 — Reasoning mentions HTF bias from digest

```python
if output.digest.htf_bias:
    assert output.digest.htf_bias in output.reasoning.htf_context.lower() or \
           output.digest.htf_bias in output.reasoning.summary.lower()
```

### TF.3 — No-trade reasoning explains the flag

```python
# When verdict is no_trade:
if output.verdict.verdict == "no_trade":
    assert len(output.reasoning.verdict_rationale) > 20
    # Must not be an empty or generic rationale
```

---

## Group G — Integration and output

### TG.1 — Output file written after run

```python
import os
assert os.path.exists("analyst/output/EURUSD_analyst_output.json")
```

### TG.2 — Output file is valid JSON with all three blocks

```python
import json
with open("analyst/output/EURUSD_analyst_output.json") as f:
    saved = json.load(f)

assert "verdict" in saved
assert "reasoning" in saved
assert "digest" in saved
```

### TG.3 — CLI runs end-to-end for both instruments

```bash
python run_analyst.py --instrument EURUSD
python run_analyst.py --instrument XAUUSD
# Both must complete without exception
```

### TG.4 — Verdict changes when structure changes

```python
# Run with bullish structure → record verdict
# Swap to bearish structure fixture → re-run
# Verdict must differ

output_bullish = run_analyst_with_packet(bullish_packet)
output_bearish = run_analyst_with_packet(bearish_packet)

assert output_bullish.verdict.verdict != output_bearish.verdict.verdict or \
       output_bullish.verdict.htf_bias != output_bearish.verdict.htf_bias
```

### TG.5 — Feed, Officer, structure files not modified (final check)

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/"
# Must return no output — imports permitted, modifications forbidden
```

---

## Phase 3E sign-off checklist

- [ ] Group 0 — Full regression: 0 failures
- [ ] Group A — Pre-filter digest production: all pass
- [ ] Group B — Pre-filter determinism: all pass
- [ ] Group C — Flag logic: all pass
- [ ] Group D — `to_prompt_dict()`: all pass
- [ ] Group E — LLM verdict schema: all pass
- [ ] Group F — LLM reasoning block: all pass
- [ ] Group G — Integration and output: all pass
- [ ] LLM system prompt contains explicit no-re-derive instruction
- [ ] Hard no-trade override raises `ValueError`
- [ ] `structure_gate` echoed correctly from digest into verdict
- [ ] `pre_filter.py` has zero LLM calls
- [ ] Output file written atomically
- [ ] Both EURUSD and XAUUSD produce valid AnalystOutput
- [ ] Feed, Officer, structure engine: 0 modifications
