# CONSTRAINTS.md — Phase 3G Hard Rules

## RULE 1 — Zero LLM calls in the explanation path

No LLM call of any kind is permitted inside:
- `explainability.py`
- `explain_contracts.py`
- `templates.py`
- `explain_service.py`
- `run_explain.py`

This is absolute. If any function in these files makes an HTTP call, imports an LLM client, or calls any function that eventually reaches an LLM, that is a violation.

Human-readable prose in `audit_summary` is produced by `templates.py` using string formatting over saved field values. It is not generated.

```python
# Correct
def render_htf_context(digest: StructureDigest) -> str:
    return (
        f"HTF Context: {digest.htf_source_timeframe} regime was {digest.htf_bias}. "
        f"Last confirmed BOS was {digest.last_bos}."
    )

# Wrong — never do this
def render_htf_context(digest: StructureDigest) -> str:
    return call_llm(f"Describe the HTF context: {digest}")
```

---

## RULE 2 — Replay produces identical output from saved artifacts

Given a saved `MultiAnalystOutput` JSON file, `run_explain.py --file <path>` must produce the identical `ExplainabilityBlock` as was produced at run time. No field may differ.

This means:
- All classification logic must be pure functions of the saved fields
- No timestamps, random values, or external lookups in explanation construction
- Template strings are fixed — they do not vary by run

Test: save output → re-run from file → assert byte-level equality on all structured fields.

---

## RULE 3 — Influence classification is rule-based, not heuristic

Signal influence (`dominant`, `supporting`, `conflicting`, `neutral`, `absent`) must be computed from the explicit rule table in `CONTRACTS.md`. It is not inferred, scored with floating point, or approximated.

```python
# Correct
def classify_htf_regime(digest: StructureDigest, verdict: str) -> str:
    if not digest.structure_available:
        return "absent"
    if digest.structure_gate == "pass" and digest.htf_bias in verdict:
        return "dominant"
    if digest.structure_gate == "fail":
        return "conflicting"
    return "neutral"

# Wrong
def classify_htf_regime(digest, verdict):
    score = 0.3 * regime_strength + 0.7 * alignment  # no float scoring
    return "dominant" if score > 0.6 else "supporting"
```

---

## RULE 4 — `audit_summary` is a template fill-in, not freeform generation

`templates.py` must contain named template functions, one per section. Each function takes structured inputs and returns a formatted string. The templates themselves are fixed strings with interpolated values.

```python
# templates.py — correct pattern
def render_persona_summary(pa: PersonaVerdict, pb: PersonaVerdict, arbiter: ArbiterDecision) -> str:
    return (
        f"Persona Summary: Technical Structure returned {pa.verdict} at {pa.confidence} confidence. "
        f"Execution/Timing returned {pb.verdict} at {pb.confidence} confidence. "
        f"Consensus: {arbiter.consensus_state}. Arbiter used {arbiter.final_confidence} confidence."
    )
```

Templates may use conditionals (`if`/`else`) to vary phrasing based on field values. They must not produce freeform text beyond what the field values determine.

---

## RULE 5 — Standalone file is derived from embedded field, not independently computed

`_multi_analyst_explainability.json` must be written as:

```python
with open(explainability_path, "w") as f:
    json.dump(output.explanation.to_dict(), f, indent=2)
```

Where `output.explanation` is the same `ExplainabilityBlock` object embedded in `MultiAnalystOutput`. It must never be recomputed separately. If `output.explanation` is `None`, do not write the standalone file — raise instead.

---

## RULE 6 — `multi_contracts.py` additive extension only

The only permitted change to any existing file is adding one optional field to `MultiAnalystOutput` in `analyst/multi_contracts.py`:

```python
explanation: Optional["ExplainabilityBlock"] = None
```

No other field, method, or import in any existing file may be modified. If a change to another file seems necessary, it is a design error — solve it in the new 3G modules.

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/|analyst/pre_filter|analyst/contracts\.py|analyst/prompt_builder|analyst/analyst\.py|analyst/service|analyst/personas|analyst/arbiter|analyst/multi_analyst_service"
# Must return no output
# Only permitted diff: analyst/multi_contracts.py (additive field only)
```

---

## RULE 7 — Confidence provenance must be step-complete

Every step in the confidence chain must be recorded, even if the value did not change:

```
Step 1: Technical persona confidence
Step 2: Execution persona confidence
Step 3: Consensus state classification
Step 4: Arbiter rule and result
Step 5: Python override check (even if not triggered)
```

A provenance chain missing any step is invalid. Post-construction validator must assert `len(provenance.steps) >= 5`.

---

## RULE 8 — Signal ranking must cover all seven signals

The `SignalInfluenceRanking.signals` list must always contain exactly seven entries — one per signal in the defined set:

```python
REQUIRED_SIGNALS = {
    "htf_regime", "bos_mss", "liquidity", "fvg_context",
    "sweep_reclaim", "no_trade_flags", "caution_flags"
}
```

If a signal is unavailable, classify it as `"absent"` — do not omit it. Post-construction validator must assert all seven are present.

---

## RULE 9 — `ExplainabilityBlock` construction from file must not touch the network or filesystem beyond the input file

`run_explain --file <path>` must:
1. Load the JSON file
2. Deserialise to `MultiAnalystOutput`
3. Re-derive `ExplainabilityBlock` from the in-memory object
4. Write standalone file

It must not re-fetch market data, re-run Officer, re-run structure engine, or make any calls to external services.

---

## Common failure modes to avoid

| Failure | Guard |
|---|---|
| LLM call sneaks into template rendering | Rule 1 — static template functions only |
| Replay produces different output | Rule 2 — assert equality in tests |
| Signal classification uses heuristic scoring | Rule 3 — rule table only |
| Standalone file recomputed independently | Rule 5 — derive from embedded field |
| `multi_contracts.py` modified beyond additive field | Rule 6 — git diff check |
| Confidence provenance missing steps | Rule 7 — validator asserts `len >= 5` |
| Signal ranking missing entries | Rule 8 — validator asserts all 7 present |
| Explain-from-file fetches live data | Rule 9 — no network/filesystem beyond input |
