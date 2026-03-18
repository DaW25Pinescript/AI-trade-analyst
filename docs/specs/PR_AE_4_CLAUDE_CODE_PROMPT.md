# PR-AE-4 — Claude Code Agent Prompt

**Branch:** `feature/pr-ae-4-persona-contracts-validators`
**Spec:** `docs/ANALYSIS_ENGINE_SPEC_v1.2.md` (controlling document — Sections 6.1–6.6, 12.4)
**Depends on:** PR-AE-1, PR-AE-2, PR-AE-3 merged — full P1 (Gate 1 closed)
**Acceptance criteria:** AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-20
**Note:** AC-19 (hallucination test on degraded snapshot) deferred to PR-AE-5

---

## Gate Context

Gate 1 is closed. P1 is complete:
- All 3 lenses compute valid schema or clean failure
- Snapshot builder assembles immutable evidence surface
- Derived alignment/conflict signals are deterministic
- Failure-aware meta is working
- Snapshot hashing is deterministic

PR-AE-4 starts P2, but only at the **contract layer**.

This PR does **not** implement persona prompt behavior.
This PR does **not** redesign orchestration.
This PR does **not** introduce new personas.
This PR does **not** modify governance.

It only locks the typed contract surface that later persona execution will use.

Do not redesign anything.
Do not add features beyond what the spec defines for PR-AE-4.
Do not reinterpret the spec.

---

## Hard Rules

- Treat the spec as law
- Do NOT modify `ai_analyst/models/analyst_output.py` — see Grain Boundary section below
- Do NOT modify any existing persona, governance, or pipeline files
- Do NOT wire into the graph/pipeline — that's PR-AE-5
- Do NOT create prompt templates — that's PR-AE-5
- Do NOT add LLM calls or live provider dependencies
- Do NOT add new personas beyond `default_analyst` and `risk_officer`
- Do NOT introduce inline validator callables inside persona contracts
- Validator references must be **named strings** into the registry, per spec
- Validators are **soft-only in v1**, except where the spec explicitly tests moderate downgrade behavior
- Tests must use frozen, deterministic fixtures only
- All new code under `ai_analyst/`
- If an existing file shape conflicts with the spec, stop and keep the change minimal and contract-focused

---

## CRITICAL: Grain Boundary — Existing AnalystOutput

**The spec (Section 12.4) says "modify `ai_analyst/models/analyst_output.py`". This is unsafe and must be treated as a new model instead.**

The existing `AnalystOutput` class has:
- 100+ references across 18 files (cli, prompt builders, arbiter, bias detector, execution router, graph state, 7 test files)
- ICT-specific fields: `htf_bias`, `structure_state`, `key_levels`, `setup_valid`, `sweep_status`, `fvg_zones`, `displacement_quality`
- Different `recommended_action` values: `WAIT | LONG | SHORT | NO_TRADE`
- A `model_validator` enforcing ICT-specific NO_TRADE rules
- Every existing test constructs `AnalystOutput` with these ICT fields

The new Analysis Engine schema has:
- Evidence-engine fields: `persona_id`, `bias`, `recommended_action`, `confidence`, `reasoning`, `evidence_used`, `counterpoints`, `what_would_change_my_mind`
- Different `bias` type: `BULLISH | BEARISH | NEUTRAL` (not `bullish | bearish | neutral | ranging`)
- Different `recommended_action` values: `BUY | SELL | NO_TRADE` (not `WAIT | LONG | SHORT | NO_TRADE`)
- Different validation rules (evidence citation, confidence bands, counterpoint enforcement)

**These schemas are fundamentally incompatible.** Modifying the existing class would break every test that constructs an `AnalystOutput` and nuke AC-20 (regression).

**Resolution:** Create a new model class `AnalysisEngineOutput` in a new file `ai_analyst/models/engine_output.py`. The existing `AnalystOutput` stays untouched. The legacy pipeline continues to work. The new Analysis Engine pipeline uses its own output type. Both models coexist.

---

## Spec Contract to Follow

### PersonaContract schema

Use the spec's contract exactly (Section 6.4):

```python
class PersonaContract(BaseModel):
    persona_id: PersonaType
    version: str
    display_name: str
    primary_stance: Literal["balanced", "risk_averse", "adversarial", "method_pure", "skeptical_prob"]
    temperature_override: float | None
    model_profile_override: str | None
    must_enforce: list[str]
    soft_constraints: list[str]
    constraints: list[dict]     # {"rule": str, "level": "soft|moderate|hard"}
    validator_rules: list[str]  # named references into VALIDATOR_REGISTRY — NOT inline Callables
```

Constraint enforcement levels:
- `soft` = log violation only
- `moderate` = log + downgrade confidence by 0.10
- `hard` = invalidate output — treated as failed analyst

All v1 validators start at `soft` level. Promoting requires contract version bump — not a code change.

### Persona output schema (8 fields)

The spec's persona output shape (Section 6.5):

```json
{
  "persona_id": "default_analyst",
  "bias": "BULLISH",
  "recommended_action": "BUY",
  "confidence": 0.72,
  "reasoning": "Bullish because structure shows HH/HL continuation ...",
  "evidence_used": [
    "lenses.structure.trend.structure_state",
    "lenses.structure.breakout.status"
  ],
  "counterpoints": [
    "Price within 1.5% of resistance — reversal risk elevated ..."
  ],
  "what_would_change_my_mind": [
    "Close below structure support ..."
  ]
}
```

Field rules from the spec:
- `bias`: `BULLISH | BEARISH | NEUTRAL`
- `recommended_action`: `BUY | SELL | NO_TRADE`
- `confidence`: 0.0–1.0
- `evidence_used`: minimum 2 entries; must be valid `lenses.*` dot-paths
- `reasoning`: must reference at least 2 evidence field values explicitly
- `counterpoints`: minimum 1 entry unless confidence >= 0.80
- `what_would_change_my_mind`: minimum 1 entry

Confidence bands (Section 6.3):
- Weak: 0.0–0.35
- Moderate: 0.36–0.65
- Strong: 0.66–1.00
- When `meta.failed_lenses` is non-empty: max persona confidence capped at 0.65

### Validator registry

Use the spec's pattern (Section 6.4):

```python
VALIDATOR_REGISTRY: dict[str, Callable[[AnalysisEngineOutput], bool | str]] = {
    "risk_officer.no_aggressive_buy_without_confidence": ...,
    "default_analyst.requires_two_evidence_fields": ...,
    "all_personas.no_evidence_contradiction": ...,
}
```

Registry values return `True` when valid, or a violation string when invalid.

---

## Files to Create

| File | Purpose |
|---|---|
| `ai_analyst/models/persona_contract.py` | `PersonaContract` Pydantic model + `ConstraintRule` + v1 contract instances |
| `ai_analyst/models/engine_output.py` | `AnalysisEngineOutput` — new 8-field persona output schema |
| `ai_analyst/core/persona_validators.py` | `VALIDATOR_REGISTRY` + `run_validators()` runner |
| `ai_analyst/tests/models/__init__.py` | Test package init (if not present) |
| `ai_analyst/tests/models/test_persona_contract.py` | PersonaContract tests |
| `ai_analyst/tests/models/test_engine_output.py` | AnalysisEngineOutput schema tests |
| `ai_analyst/tests/core/test_persona_validators.py` | Validator registry + runner tests |

**No existing files modified.**

---

## Component 1 — PersonaContract (`ai_analyst/models/persona_contract.py`)

**Spec reference:** Section 6.4

```python
from pydantic import BaseModel
from typing import Literal
from ai_analyst.models.persona import PersonaType


class ConstraintRule(BaseModel):
    rule: str
    level: Literal["soft", "moderate", "hard"]


class PersonaContract(BaseModel):
    persona_id: PersonaType
    version: str
    display_name: str
    primary_stance: Literal[
        "balanced", "risk_averse", "adversarial",
        "method_pure", "skeptical_prob"
    ]
    temperature_override: float | None = None
    model_profile_override: str | None = None
    must_enforce: list[str]
    soft_constraints: list[str]
    constraints: list[ConstraintRule]
    validator_rules: list[str]           # named references into VALIDATOR_REGISTRY
```

### V1 Contract Instances

Provide two canonical contract instances:

```python
DEFAULT_ANALYST_CONTRACT = PersonaContract(
    persona_id=PersonaType.DEFAULT_ANALYST,
    version="v1.0",
    display_name="Default Analyst",
    primary_stance="balanced",
    temperature_override=None,
    model_profile_override=None,
    must_enforce=[],
    soft_constraints=[],
    constraints=[
        ConstraintRule(rule="minimum 2 evidence fields", level="soft"),
        ConstraintRule(rule="minimum 1 counterpoint", level="soft"),
        ConstraintRule(rule="minimum 1 what_would_change_my_mind", level="soft"),
    ],
    validator_rules=[
        "default_analyst.requires_two_evidence_fields",
        "all_personas.no_evidence_contradiction",
        "all_personas.evidence_paths_exist",
        "all_personas.counterpoint_required",
        "all_personas.falsifiable_required",
    ],
)

RISK_OFFICER_CONTRACT = PersonaContract(
    persona_id=PersonaType.RISK_OFFICER,
    version="v1.0",
    display_name="Risk Officer",
    primary_stance="risk_averse",
    temperature_override=None,
    model_profile_override=None,
    must_enforce=[],
    soft_constraints=[],
    constraints=[
        ConstraintRule(rule="minimum 2 evidence fields", level="soft"),
        ConstraintRule(rule="no aggressive buy without high confidence", level="soft"),
        ConstraintRule(rule="minimum 1 counterpoint", level="soft"),
    ],
    validator_rules=[
        "default_analyst.requires_two_evidence_fields",
        "risk_officer.no_aggressive_buy_without_confidence",
        "all_personas.no_evidence_contradiction",
        "all_personas.evidence_paths_exist",
        "all_personas.counterpoint_required",
        "all_personas.falsifiable_required",
    ],
)
```

### Key Design Rules

- All v1 constraints at `soft` level — no exceptions
- `validator_rules` is `list[str]` — named references only, NOT callables
- PersonaContract must JSON round-trip without data loss (AC-16)
- `PersonaType` enum already exists at `ai_analyst/models/persona.py` with `DEFAULT_ANALYST` and `RISK_OFFICER`
- No prompt text embedded in this file

---

## Component 2 — AnalysisEngineOutput (`ai_analyst/models/engine_output.py`)

**Spec reference:** Section 6.5

The new 8-field output schema for evidence-engine personas. This is NOT a modification of the existing `AnalystOutput`.

```python
from pydantic import BaseModel, field_validator
from typing import Literal
from ai_analyst.models.persona import PersonaType


class AnalysisEngineOutput(BaseModel):
    persona_id: PersonaType
    bias: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    recommended_action: Literal["BUY", "SELL", "NO_TRADE"]
    confidence: float                                          # 0.0–1.0
    reasoning: str                                             # must reference >= 2 evidence dot-paths
    evidence_used: list[str]                                   # minimum 2; valid lenses.* dot-paths
    counterpoints: list[str]                                   # minimum 1 (unless confidence >= 0.80)
    what_would_change_my_mind: list[str]                       # minimum 1

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v
```

The Pydantic model handles basic type/range validation only. Semantic rules (evidence minimum, counterpoint requirement, confidence band compliance) are enforced by the validator registry — NOT by model validators on this class.

Do not invent extra fields. Do not add orchestration logic here.

---

## Component 3 — Validator Registry (`ai_analyst/core/persona_validators.py`)

**Spec reference:** Section 6.4, 6.6

### Registry

```python
from typing import Callable
from ai_analyst.models.engine_output import AnalysisEngineOutput

VALIDATOR_REGISTRY: dict[str, Callable[[AnalysisEngineOutput], bool | str]] = {

    "default_analyst.requires_two_evidence_fields": lambda o: (
        True if len(o.evidence_used) >= 2
        else "minimum 2 evidence fields required"
    ),

    "risk_officer.no_aggressive_buy_without_confidence": lambda o: (
        True if o.recommended_action != "BUY" or o.confidence >= 0.75
        else "risk_officer: BUY requires confidence >= 0.75"
    ),

    "all_personas.no_evidence_contradiction": lambda o: (
        True  # placeholder — full implementation requires reasoning text analysis
        # v1 soft-only: always passes, logs intent
    ),

    "all_personas.evidence_paths_exist": lambda o: (
        True  # placeholder — full validation requires snapshot access
        # actual path traversal implemented in PR-AE-5 with snapshot integration
    ),

    "all_personas.counterpoint_required": lambda o: (
        True if len(o.counterpoints) >= 1 or o.confidence >= 0.80
        else "minimum 1 counterpoint required when confidence < 0.80"
    ),

    "all_personas.falsifiable_required": lambda o: (
        True if len(o.what_would_change_my_mind) >= 1
        else "minimum 1 what_would_change_my_mind entry required"
    ),
}
```

### Validator Runner

`run_validators()` returns results only — it does NOT mutate the output. The caller decides what to do with violations (log, downgrade confidence, invalidate).

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ValidationResult:
    validator_name: str
    passed: bool
    message: str | None = None
    level: Literal["soft", "moderate", "hard"] = "soft"


def run_validators(
    output: AnalysisEngineOutput,
    validator_names: list[str],
    level: Literal["soft", "moderate", "hard"] = "soft",
) -> list[ValidationResult]:
    """
    Run named validators against an AnalysisEngineOutput.

    Returns list of ValidationResult. Does NOT modify the output.
    Caller decides enforcement:
    - soft:     log violation only
    - moderate: log + caller should downgrade confidence by 0.10
    - hard:     caller should invalidate output (treated as failed analyst)
    """
    results = []
    for name in validator_names:
        validator_fn = VALIDATOR_REGISTRY.get(name)
        if validator_fn is None:
            results.append(ValidationResult(
                validator_name=name,
                passed=False,
                message=f"Unknown validator: {name}",
                level=level,
            ))
            continue

        result = validator_fn(output)
        if result is True:
            results.append(ValidationResult(
                validator_name=name, passed=True, level=level,
            ))
        else:
            results.append(ValidationResult(
                validator_name=name, passed=False, message=result, level=level,
            ))

    return results
```

### Key Design Rules

- `run_validators()` is pure — no mutation, no side effects
- All v1 validators at `soft` level — no exceptions in shipped contracts
- `all_personas.no_evidence_contradiction` and `all_personas.evidence_paths_exist` are **placeholders** in PR-AE-4 — full implementations require snapshot access and reasoning text analysis, arriving in PR-AE-5
- Unknown validator names produce a failing `ValidationResult`, not a crash

---

## Scope Boundaries for AC-15 / AC-17 / AC-18

These three ACs are where drift is most likely. Keep them as **contract-enforcement proofs**, not orchestration behavior.

### AC-15 — Confidence bands + degraded cap

"Confidence within defined bands; capped at 0.65 on degraded snapshot."

For PR-AE-4, implement the contract-side enforcement only:
- Confidence must be within 0.0–1.0 (Pydantic field_validator)
- When the run is degraded, confidence must not exceed 0.65

Test the cap as a standalone helper or narrow validator that accepts a `degraded` flag. Do not build persona-generation logic. Do not rewire the graph.

Recommended approach:
```python
def check_degraded_confidence_cap(
    output: AnalysisEngineOutput,
    degraded: bool,
) -> bool | str:
    if degraded and output.confidence > 0.65:
        return f"confidence {output.confidence} exceeds 0.65 cap on degraded snapshot"
    return True
```

### AC-17 — Soft validator logs without blocking

For this PR:
- "logs" = collected violation records in the returned `list[ValidationResult]`
- If the repo has logging conventions, a standard logger call is acceptable
- Output is NOT blocked — runner returns results, caller proceeds

### AC-18 — Moderate validator downgrades confidence by 0.10

For this PR:
- The runner reports `level="moderate"` on the ValidationResult
- The **caller** applies the exact downgrade: `confidence -= 0.10`, floored at 0.0
- Test proves: given a moderate-level violation result, applying the downgrade produces the expected value
- Do not downgrade twice for the same validator invocation
- Keep deterministic

---

## TDD Sequence

### PersonaContract

```text
1. Write test_default_analyst_contract_instantiates                  → RED
2. Create PersonaContract model + DEFAULT_ANALYST_CONTRACT            → GREEN
3. Write test_risk_officer_contract_instantiates                     → RED
4. Add RISK_OFFICER_CONTRACT                                         → GREEN
5. Write test_contract_json_roundtrip_no_data_loss (AC-16)           → RED
6. Verify model_dump_json / model_validate_json cycle                → GREEN
7. Write test_validator_rules_are_strings_not_callables              → GREEN
8. Write test_all_v1_constraints_are_soft_level                      → GREEN
9. Write test_constraint_level_rejects_invalid_value                 → RED
10. Implement ConstraintRule with Literal validation                  → GREEN
11. Refactor                                                          → GREEN
```

### AnalysisEngineOutput

```text
1. Write test_output_has_all_8_fields (AC-11)                        → RED
2. Create AnalysisEngineOutput model                                  → GREEN
3. Write test_confidence_must_be_0_to_1                              → RED
4. Add field_validator                                                → GREEN
5. Write test_confidence_rejects_negative_and_above_1                → RED/GREEN
6. Write test_bias_must_be_valid_literal                             → GREEN (Pydantic)
7. Write test_recommended_action_must_be_valid_literal               → GREEN
8. Write test_evidence_used_is_list_of_strings                       → GREEN
9. Write test_counterpoints_is_list_of_strings                       → GREEN
10. Write test_what_would_change_my_mind_is_list_of_strings          → GREEN
11. Refactor                                                          → GREEN
```

### Validator Registry + Runner

```text
1. Write test_registry_contains_expected_validator_names             → RED
2. Create VALIDATOR_REGISTRY                                          → GREEN
3. Write test_requires_two_evidence_fields_passes (AC-12)            → RED
4. Implement validator                                                → GREEN
5. Write test_requires_two_evidence_fields_fails_with_one            → RED/GREEN
6. Write test_counterpoint_required_passes (AC-13)                   → RED
7. Implement validator                                                → GREEN
8. Write test_counterpoint_required_fails_with_zero                  → RED/GREEN
9. Write test_counterpoint_not_required_at_high_confidence           → RED/GREEN
10. Write test_falsifiable_required_passes (AC-14)                   → RED
11. Implement validator                                               → GREEN
12. Write test_falsifiable_required_fails_with_zero                  → RED/GREEN
13. Write test_risk_officer_buy_below_075_fails                      → RED
14. Implement validator                                               → GREEN
15. Write test_risk_officer_buy_at_075_passes                        → RED/GREEN
16. Write test_run_validators_returns_list_of_results                → RED
17. Implement run_validators()                                        → GREEN
18. Write test_soft_violation_reports_without_blocking (AC-17)        → RED/GREEN
19. Write test_moderate_result_has_correct_level (AC-18)             → RED
20. Implement level passthrough                                       → GREEN
21. Write test_moderate_downgrade_applied_by_caller                  → RED
22. Implement test helper proving caller-side downgrade               → GREEN
23. Write test_unknown_validator_name_fails_gracefully               → RED/GREEN
24. Write test_degraded_confidence_cap_at_065 (AC-15)                → RED
25. Implement degraded cap check                                      → GREEN
26. Write test_degraded_cap_allows_065_and_below                     → RED/GREEN
27. Run full regression                                               → GREEN
```

---

## Test Fixtures

Create helper builders in test files:

```python
from ai_analyst.models.engine_output import AnalysisEngineOutput
from ai_analyst.models.persona import PersonaType


def make_valid_default_output(confidence: float = 0.72) -> AnalysisEngineOutput:
    return AnalysisEngineOutput(
        persona_id=PersonaType.DEFAULT_ANALYST,
        bias="BULLISH",
        recommended_action="BUY",
        confidence=confidence,
        reasoning="Structure HH_HL (lenses.structure.trend.structure_state) with trend bullish (lenses.trend.direction.overall).",
        evidence_used=[
            "lenses.structure.trend.structure_state",
            "lenses.trend.direction.overall",
        ],
        counterpoints=["Price near resistance (lenses.structure.distance.to_resistance)"],
        what_would_change_my_mind=["Close below support at lenses.structure.levels.support"],
    )


def make_valid_risk_output(confidence: float = 0.60) -> AnalysisEngineOutput:
    return AnalysisEngineOutput(
        persona_id=PersonaType.RISK_OFFICER,
        bias="NEUTRAL",
        recommended_action="NO_TRADE",
        confidence=confidence,
        reasoning="Risk elevated: proximity to resistance (lenses.structure.distance.to_resistance) with momentum fading (lenses.momentum.state.phase).",
        evidence_used=[
            "lenses.structure.distance.to_resistance",
            "lenses.momentum.state.phase",
        ],
        counterpoints=["Trend still bullish on EMA alignment"],
        what_would_change_my_mind=["Clear breakout above resistance with strong momentum"],
    )
```

No snapshot object required for most of this PR.
Only pass narrow flags like `degraded=True` where needed for AC-15.

---

## Required Tests

### `test_persona_contract.py`

| Test | AC |
|---|---|
| Default Analyst contract instantiates with all fields | — |
| Risk Officer contract instantiates with all fields | — |
| PersonaContract JSON round-trip preserves all fields | AC-16 |
| `validator_rules` contains only strings, not callables | — |
| All v1 constraints at `soft` level | — |
| `persona_id` uses existing `PersonaType` enum | — |
| Invalid constraint level rejected by ConstraintRule | — |

### `test_engine_output.py`

| Test | AC |
|---|---|
| AnalysisEngineOutput has all 8 fields | AC-11 |
| Confidence must be 0.0–1.0 (rejects out-of-range) | AC-15 |
| Confidence rejects negative values | AC-15 |
| Confidence rejects values > 1.0 | AC-15 |
| Bias must be BULLISH/BEARISH/NEUTRAL | — |
| recommended_action must be BUY/SELL/NO_TRADE | — |
| evidence_used accepts list of strings | — |
| counterpoints accepts list of strings | — |
| what_would_change_my_mind accepts list of strings | — |

### `test_persona_validators.py`

#### `TestValidatorRegistry`
- Contains all expected validator names (6 validators)
- Registry values are callable
- Unknown validator name handled deterministically (failing result, not crash)

#### `TestFieldRuleValidation`
- `evidence_used` with 1 entry fails minimum-2 rule (AC-12)
- `evidence_used` with 2+ entries passes (AC-12)
- `counterpoints` with 0 entries fails minimum-1 rule (AC-13)
- `counterpoints` with 1+ entries passes (AC-13)
- `counterpoints` with 0 entries passes when confidence >= 0.80 (AC-13)
- `what_would_change_my_mind` with 0 entries fails (AC-14)
- `what_would_change_my_mind` with 1+ entries passes (AC-14)
- `risk_officer.no_aggressive_buy` fails on BUY below 0.75
- `risk_officer.no_aggressive_buy` passes on BUY at 0.75+

#### `TestSoftValidation`
- Soft violation: `passed=False`, `level="soft"`, message present (AC-17)
- Output is NOT blocked — results returned, no exception raised (AC-17)

#### `TestModerateValidation`
- Moderate result has `level="moderate"` (AC-18)
- Caller-side downgrade: confidence reduced by exactly 0.10 (AC-18)
- Downgrade floored at 0.0 (AC-18)

#### `TestConfidenceRules`
- Degraded run caps confidence at 0.65 (AC-15)
- Confidence of 0.65 on degraded is allowed (AC-15)
- Confidence of 0.66 on degraded is violation (AC-15)

---

## Acceptance Criteria Mapping

| AC | Criterion | What proves it |
|---|---|---|
| AC-11 | AnalysisEngineOutput includes all 8 fields | `test_output_has_all_8_fields` |
| AC-12 | evidence_used minimum 2 entries — validated by test | `test_requires_two_evidence_fields_*` |
| AC-13 | counterpoints minimum 1 entry — validated by test | `test_counterpoint_required_*` |
| AC-14 | what_would_change_my_mind minimum 1 entry — validated by test | `test_falsifiable_required_*` |
| AC-15 | Confidence within bands; capped at 0.65 on degraded | confidence field_validator + degraded cap test |
| AC-16 | PersonaContract round-trips through JSON without data loss | `test_contract_json_roundtrip` |
| AC-17 | Soft validator logs violation without blocking output | `TestSoftValidation` |
| AC-18 | Moderate validator downgrades confidence by 0.10 | `TestModerateValidation` (runner reports; caller applies) |
| AC-20 | All existing + P1 tests green | Full `pytest ai_analyst/ -q` regression check |

**AC-19 deferred to PR-AE-5** — requires actual persona prompt + snapshot integration to test hallucination on degraded snapshot.

---

## Constraints

- All new code under `ai_analyst/`
- No modifications to existing files — especially NOT `analyst_output.py`
- No LLM calls or live provider dependency
- No pipeline/graph wiring — no node changes
- No prompt templates — that's PR-AE-5
- No governance changes
- No snapshot builder changes
- No UI changes
- All v1 validators at `soft` level in shipped contracts
- Tests use frozen fixtures only
- No SQLite, no new top-level modules
- No dynamic plugin registry
- No speculative prompt-library work

---

## Verification Checklist

```bash
# 1. New tests
python -m pytest ai_analyst/tests/models/test_persona_contract.py -v
python -m pytest ai_analyst/tests/models/test_engine_output.py -v
python -m pytest ai_analyst/tests/core/test_persona_validators.py -v

# 2. P1 tests still green
python -m pytest ai_analyst/tests/lenses/ ai_analyst/tests/core/test_lens_registry.py ai_analyst/tests/core/test_snapshot_builder.py -v

# 3. Full regression — must be >= previous baseline
python -m pytest ai_analyst/ --tb=short -q 2>&1 | tail -5

# 4. Only expected files changed — NO changes to analyst_output.py
git diff --name-only main
# Expected: only files under ai_analyst/models/, ai_analyst/core/,
#           ai_analyst/tests/models/, ai_analyst/tests/core/

# 5. Explicit regression safety check
git diff main -- ai_analyst/models/analyst_output.py
# Expected: empty (no changes)
```

---

## PR Description

```
PR-AE-4: PersonaContract + Validator Registry + AnalysisEngineOutput

Begins P2 (Persona Engine Rebuild) by locking the contract layer:
- ai_analyst/models/persona_contract.py: PersonaContract schema + v1 instances
- ai_analyst/models/engine_output.py: AnalysisEngineOutput — new 8-field output
- ai_analyst/core/persona_validators.py: VALIDATOR_REGISTRY + run_validators()
- Tests for contract round-trip, output schema, validator behavior, confidence rules

Note: AnalysisEngineOutput is a NEW model, not a modification of the existing
AnalystOutput. The legacy model has 100+ references across 18 files with an
incompatible ICT-specific schema — modifying it would break AC-20 (regression).
Both models coexist; the legacy pipeline is untouched.

Acceptance criteria closed:
- AC-11 AnalysisEngineOutput includes all 8 fields
- AC-12 evidence_used minimum 2 entries
- AC-13 counterpoints minimum 1 entry
- AC-14 what_would_change_my_mind minimum 1 entry
- AC-15 confidence bands enforced; degraded cap at 0.65
- AC-16 PersonaContract JSON round-trip without data loss
- AC-17 soft validator logs violation without blocking output
- AC-18 moderate validator downgrades confidence by 0.10
- AC-20 all existing + P1 tests green

No existing files modified.
Next: PR-AE-5 (persona prompts + LLM wiring + evidence citation + AC-19).

Spec: docs/ANALYSIS_ENGINE_SPEC_v1.2.md, Sections 6.1–6.6, 12.4
```
