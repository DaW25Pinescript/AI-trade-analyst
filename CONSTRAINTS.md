# CONSTRAINTS.md — Phase 3F Hard Rules

## RULE 1 — All personas consume the same StructureDigest

Every persona call receives the identical `StructureDigest` object produced by `pre_filter.py`. No persona may receive a different digest, a filtered subset, or any raw structure data.

```python
# Correct
digest = compute_digest(packet)
verdict_a = run_persona("technical_structure", digest)
verdict_b = run_persona("execution_timing", digest)

# Wrong — never do this
digest_a = compute_digest(packet, persona="technical")   # no per-persona filtering
verdict_b = run_persona("execution_timing", packet.structure)  # raw structure forbidden
```

---

## RULE 2 — Personas differ by prompt/policy only, not by data access

Both personas receive the same `digest.to_prompt_dict()` output. The only difference between persona calls is the system prompt. Do not pass different data subsets to different personas.

---

## RULE 3 — Python hard-constraint layer is supreme

If `digest.has_hard_no_trade()` is True:
- Both persona prompts must state the no-trade constraint explicitly
- Both personas must return `verdict = "no_trade"` and `confidence = "none"`
- The Arbiter must set `no_trade_enforced = True`, `final_verdict = "no_trade"`, `final_confidence = "none"`
- Post-parse validation must assert this for all three outputs
- No LLM call — persona or Arbiter — may override this

```python
def validate_persona_verdict(verdict: PersonaVerdict, digest: StructureDigest) -> None:
    if digest.has_hard_no_trade():
        if verdict.verdict != "no_trade":
            raise ValueError(
                f"Persona {verdict.persona_name} overrode hard no-trade. "
                f"Flags: {digest.no_trade_flags}"
            )

def validate_arbiter_decision(decision: ArbiterDecision, digest: StructureDigest) -> None:
    if digest.has_hard_no_trade():
        if not decision.no_trade_enforced:
            raise ValueError("Arbiter did not enforce hard no-trade condition")
        if decision.final_verdict != "no_trade":
            raise ValueError("Arbiter final_verdict must be no_trade when flags present")
```

---

## RULE 4 — Arbiter direction and confidence are Python-determined

The Arbiter LLM call receives a pre-computed skeleton. It writes `synthesis_notes` and `winning_rationale_summary` only. It does not compute `final_verdict`, `final_confidence`, `consensus_state`, or `no_trade_enforced`. Those are set by `arbiter.py` Python logic before any LLM call.

Post-parse validator must assert that LLM-returned `final_verdict` and `final_confidence` — if present — match the pre-computed values. If they differ, raise `ValueError`.

---

## RULE 5 — `structure_gate` is echoed, never recomputed

Every `PersonaVerdict` must echo `structure_gate` from the digest. No persona may compute a different gate value. Validator asserts:

```python
assert verdict.structure_gate == digest.structure_gate
```

---

## RULE 6 — Existing 3E modules are not modified

3F adds four new files only. No existing `analyst/` file is touched.

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/|analyst/pre_filter|analyst/contracts\.py|analyst/prompt_builder|analyst/analyst\.py|analyst/service"
# Must return no output — imports permitted, modifications forbidden
```

New files permitted in 3F:
- `analyst/multi_contracts.py` — 3F dataclasses; imports from `analyst/contracts.py`
- `analyst/personas.py`
- `analyst/arbiter.py`
- `analyst/multi_analyst_service.py`
- `run_multi_analyst.py`
- `tests/test_personas.py`, `tests/test_arbiter.py`, `tests/test_multi_analyst_integration.py`

`analyst/contracts.py` is not modified. `PersonaVerdict`, `ArbiterDecision`, and `MultiAnalystOutput` live in `analyst/multi_contracts.py`.

---

## RULE 7 — Arbiter does not make a synthesis LLM call if no-trade is enforced

If `digest.has_hard_no_trade()`, skip the Arbiter LLM synthesis call entirely. Set `synthesis_notes` and `winning_rationale_summary` to deterministic strings:

```python
synthesis_notes = f"Hard no-trade condition enforced. Flags: {digest.no_trade_flags}. No synthesis performed."
winning_rationale_summary = "No-trade is the only valid outcome under active hard constraint flags."
```

This avoids an unnecessary LLM call and keeps no-trade enforcement fast and deterministic.

---

## RULE 8 — Conflict resolution rules are deterministic Python, not LLM inference

The mapping from `(PersonaVerdict_A, PersonaVerdict_B)` → `(consensus_state, final_verdict, final_confidence)` must be implemented as explicit Python logic in `arbiter.py`. No LLM may determine these values.

Reference logic:

```python
def compute_consensus(a: PersonaVerdict, b: PersonaVerdict, digest: StructureDigest) -> tuple[str, str, str]:
    """
    Returns (consensus_state, final_verdict, final_confidence).
    Evaluated in priority order — first match wins.
    """

    # Priority 1 — hard no-trade overrides everything
    if digest.has_hard_no_trade():
        return "no_trade", "no_trade", "none"

    # Priority 2 — either persona blocked
    if a.is_blocked() or b.is_blocked():
        return "blocked", "no_trade", "none"

    # Priority 3 & 4 — both directional, same direction
    if a.directional_bias == b.directional_bias and a.is_directional() and b.is_directional():
        if a.confidence == b.confidence:
            return "full_alignment", a.verdict, a.confidence
        else:
            lower = _lower_confidence(a.confidence, b.confidence)
            return "directional_alignment_confidence_split", a.verdict, lower

    # Priority 5 — both directional, opposite directions
    if a.is_directional() and b.is_directional():
        return "mixed", "conditional", "low"

    # Priority 6 — one or both conditional (neither blocked, neither purely directional-opposite)
    return "conditional", "conditional", "low"


_CONFIDENCE_ORDER = {"high": 3, "moderate": 2, "low": 1, "none": 0}

def _lower_confidence(a: str, b: str) -> str:
    return a if _CONFIDENCE_ORDER[a] <= _CONFIDENCE_ORDER[b] else b
```

---

## RULE 9 — `final_verdict` in MultiAnalystOutput re-expresses ArbiterDecision as AnalystVerdict

The `final_verdict` field must be a fully populated `AnalystVerdict` object built from `ArbiterDecision` fields. It must pass the same post-parse validator used in 3E. This ensures downstream systems using the 3E contract continue to work without modification.

---

## RULE 10 — Output file written atomically

Write `MultiAnalystOutput.to_dict()` to a temp file, then rename to the target path. Do not leave partial files on any error during persona calls or Arbiter call.

---

## Common failure modes to avoid

| Failure | Guard |
|---|---|
| Persona A gets different data than Persona B | Single digest object passed to both |
| Arbiter rewrites direction via LLM | Pre-compute direction before LLM call; validator asserts match |
| no-trade overridden by enthusiastic persona | validate_persona_verdict raises |
| `structure_gate` diverges between digest and verdict | assert in validator |
| 3E `analyst/service.py` broken by 3F changes | Rule 6 — no modifications to existing files |
| Partial MultiAnalystOutput written on LLM error | Atomic write pattern |
| LLM synthesis call made on no-trade condition | Rule 7 — skip call, use deterministic strings |
