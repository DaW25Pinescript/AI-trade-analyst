# PR-AE-5 — Persona Prompt Rewrite + Engine Runner + Evidence Citation Tests (Gate 2 Closer)

## Branch

`feature/pr-ae-5-engine-prompts-runner`

## Controlling Spec

`docs/ANALYSIS_ENGINE_SPEC_v1.2.md`

Primary references:
- Section 6.3 — confidence bands / degraded confidence behavior
- Section 6.5 — persona output schema and field rules
- Section 6.6 — hard persona discipline rules
- Section 6.7 — prompt structure
- Section 6.8 — degraded / failed lens handling
- Section 13 — PR sequence
- Section 17 — implementation constraints

## Scope Classification

This PR is the **Gate 2 closer** for P2.

Per the spec PR sequence, PR-AE-5 delivers:
- persona prompt rewrite (Default Analyst + Risk Officer)
- evidence citation tests
- confidence tests

This PR is the **first LLM-involved PR** for the new Analysis Engine path.

This PR may add narrowly scoped runtime support needed to prove those behaviors, but it is **not**:
- a governance PR
- a graph rewiring PR
- a legacy pipeline replacement PR
- a full orchestration redesign PR

Keep the center of gravity on:
1. v2.0 evidence-driven persona prompts
2. prompt builder for snapshot-based reasoning
3. engine analyst runner for mocked-LLM execution
4. evidence citation validation against real snapshot structure
5. AC-12, AC-13, AC-14, AC-15, AC-19, AC-20 proof

---

## Existing State (already merged)

### Analysis Engine path

- `ai_analyst/lenses/base.py`
- `ai_analyst/lenses/structure.py`
- `ai_analyst/lenses/trend.py`
- `ai_analyst/lenses/momentum.py`
- `ai_analyst/lenses/registry.py`
- `ai_analyst/lenses/data_adapter.py`
- `ai_analyst/core/snapshot_builder.py`
- `ai_analyst/models/persona_contract.py`
- `ai_analyst/models/engine_output.py`
- `ai_analyst/core/persona_validators.py`

### Locked decisions from earlier PRs

- `AnalysisEngineOutput` is a new model. Legacy `AnalystOutput` remains untouched.
- Evidence Snapshot is a plain `dict`, not a Pydantic model.
- `run_validators()` returns `list[ValidationResult]`; it does not mutate outputs.
- All v1 validators remain `soft`.
- Legacy path and new Analysis Engine path coexist.

### Legacy pipeline (do not modify behavior)

- `ai_analyst/graph/analyst_nodes.py` existing functions
- `ai_analyst/core/analyst_prompt_builder.py`
- `ai_analyst/models/analyst_output.py`
- everything under `analyst/`
- `ai_analyst/prompt_library/v1.2/personas/`

---

## Hard Rules

- Treat the spec as law.
- Do not redesign architecture.
- Do not replace the legacy pipeline.
- Do not modify legacy `AnalystOutput`.
- Do not modify `ai_analyst/core/analyst_prompt_builder.py`.
- Do not modify `ai_analyst/core/lens_loader.py`.
- Do not change `PROMPT_LIBRARY_VERSION`.
- Do not change `ai_analyst/core/snapshot_builder.py`.
- Do not change `ai_analyst/models/engine_output.py` unless a tiny import/export fix is strictly required.
- Do not change `ai_analyst/models/persona_contract.py` unless a tiny import/export fix is strictly required.
- Do not change the signature or semantics of `run_validators()`.
- Do not make live LLM calls in tests.
- All tests must be deterministic with mocks/frozen fixtures.
- Keep graph changes additive only.
- If a contract ambiguity appears, stop and choose the smallest additive fix.

---

## Critical Contract Corrections (must follow)

### 1. `run_status` is NOT part of the snapshot dict

The Evidence Snapshot is a plain dict with:
- `context`
- `lenses`
- `derived`
- `meta`

`run_status` is determined by the Snapshot Builder stage but is **not embedded into the snapshot schema itself**.

Therefore the engine runner must **not** read `snapshot["run_status"]`.

Use this contract instead:

```python
async def run_engine_analyst(
    persona_contract: PersonaContract,
    snapshot: dict,
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"],
    run_id: str,
    macro_context: dict | None = None,
) -> EngineAnalystRunResult:
    ...
```

### 2. Runner must return output + validator results together

`run_validators()` returns results and does not mutate the output.
`engine_analyst_node()` needs both:
- `engine_outputs`
- `engine_validator_results`

Therefore the runner must return a typed bundle, not just the output.

Use:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class EngineAnalystRunResult:
    output: AnalysisEngineOutput
    validator_results: list[ValidationResult]
```

This keeps ownership clean:
- runner executes LLM + validation
- caller stores output and validator results separately
- no hidden mutation

---

## Deliverables

### New files

| File | Purpose |
|---|---|
| `ai_analyst/prompt_library/v2.0/personas/default_analyst.txt` | Evidence-driven Default Analyst prompt |
| `ai_analyst/prompt_library/v2.0/personas/risk_officer.txt` | Evidence-driven Risk Officer prompt |
| `ai_analyst/core/engine_prompt_builder.py` | Build snapshot-based prompts for Analysis Engine personas |
| `ai_analyst/core/engine_analyst_runner.py` | Async runner for one persona against one snapshot |
| `ai_analyst/tests/core/test_engine_prompt_builder.py` | Prompt-builder tests |
| `ai_analyst/tests/core/test_engine_analyst_runner.py` | Runner tests with mocked LLM calls |
| `ai_analyst/tests/core/test_evidence_path_validator.py` | Snapshot-aware evidence path validator tests |

### Existing files allowed to modify

| File | Change |
|---|---|
| `ai_analyst/core/persona_validators.py` | Add snapshot-aware validator factory + helper runner |
| `ai_analyst/graph/state.py` | Add optional fields for new engine path |
| `ai_analyst/graph/analyst_nodes.py` | Add new `engine_analyst_node()` only |
| `ai_analyst/core/__init__.py` | additive exports only if needed |
| `ai_analyst/graph/__init__.py` | additive exports only if needed |

### Files not to modify

- `ai_analyst/models/analyst_output.py`
- `ai_analyst/models/engine_output.py`
- `ai_analyst/models/persona_contract.py`
- `ai_analyst/core/analyst_prompt_builder.py`
- `ai_analyst/core/lens_loader.py`
- `ai_analyst/core/snapshot_builder.py`
- any file under `analyst/`
- existing functions in `ai_analyst/graph/analyst_nodes.py`

---

## Component 1 — v2.0 Persona Prompt Templates

Create directory:

```
ai_analyst/prompt_library/v2.0/personas/
```

Create two files.

### default_analyst.txt

Must include:
- role: interpret pre-computed structured evidence; do not invent facts
- hard rule: cite evidence as `lenses.*` dot-paths only
- hard rule: minimum 2 evidence fields in `evidence_used`
- hard rule: vague prose is invalid
- hard rule: abstain via NO_TRADE if evidence is insufficient or split
- reasoning sequence:
  1. identify relevant evidence
  2. interpret directional alignment
  3. evaluate cross-lens consistency
  4. consider counterpoints / risk
  5. conclude
- exact 8-field JSON output template matching `AnalysisEngineOutput`
- stance:
  - consider all evidence equally
  - do not overcommit unless clearly aligned
  - prefer clarity over aggression
  - summarise strongest directional case and main risk
- degraded rule:
  - if run is DEGRADED, cap confidence at 0.65
  - cite only paths that resolve under active lenses
  - mention failed-lens context in counterpoints
- falsifiability:
  - include at least one `what_would_change_my_mind`

### risk_officer.txt

Same shared rules plus:
- prioritise downside risk, unstable structure, and adverse-level proximity
- be skeptical of strong directional bias near key levels
- prefer NO_TRADE if risk is elevated, evidence is split, or momentum is fading
- veto-ready posture if structural invalidation is present and confidence >= 0.60
- additional rule:
  - BUY requires confidence >= 0.75

Do not mention charts, screenshots, overlays, or image analysis anywhere in v2.0 prompts.

---

## Component 2 — Engine Prompt Builder

Create:

```
ai_analyst/core/engine_prompt_builder.py
```

### Required functions

```python
def load_engine_persona_prompt(persona: PersonaType) -> str:
    """Load prompt text from prompt_library/v2.0/personas/."""

def build_engine_prompt(
    snapshot: dict,
    persona_contract: PersonaContract,
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"],
    macro_context: dict | None = None,
) -> dict[str, str]:
    """Return {'system': str, 'persona': str, 'user': str}."""
```

### Behavior

**system**
Must contain:
- role definition
- hard rules
- exact 8-field output schema
- evidence citation rules
- reasoning discipline
- confidence bands:
  - weak: 0.0–0.35
  - moderate: 0.36–0.65
  - strong: 0.66–1.00
- degraded rule:
  - if run_status is DEGRADED, confidence must not exceed 0.65
- explicit prohibition on citing inactive/failed lenses

**persona**
Load exact text from:
- `v2.0/personas/default_analyst.txt`
- `v2.0/personas/risk_officer.txt`

Do not route through legacy prompt loader.
Do not modify existing version constants.

**user**
Must contain:
- instrument/timeframe/timestamp block
- full serialized evidence snapshot JSON
- clearly labeled meta section
- clearly labeled derived section
- explicit `run_status`
- optional macro advisory block when `macro_context` is provided

If macro context exists, append it in a clearly labeled advisory section only.
It is context, not authority.

---

## Component 3 — Snapshot-Aware Evidence Path Validator

Modify:

```
ai_analyst/core/persona_validators.py
```

**Keep:**
- `all_personas.no_evidence_contradiction` as placeholder returning True
- comment: full implementation deferred to v2 due to NLP/semantic reasoning dependency

**Implement:**

```python
def make_evidence_paths_validator(snapshot: dict) -> Callable[[AnalysisEngineOutput], bool | str]:
    """Return validator that checks each evidence_used path against a real snapshot."""
```

Rules:
- every path must start with `lenses.`
- lens name must be in `meta.active_lenses`
- path must resolve through `snapshot["lenses"]`
- null leaf values are allowed if the path resolves
- referencing inactive lenses is a violation
- referencing failed lenses is a violation
- referencing nonexistent nested fields is a violation

**Add helper:**

```python
def run_validators_with_snapshot(
    output: AnalysisEngineOutput,
    validator_names: list[str],
    snapshot: dict,
    level: Literal["soft", "moderate", "hard"] = "soft",
) -> list[ValidationResult]:
    """
    Run named validators, swapping in snapshot-aware evidence_paths_exist
    without changing the base run_validators() contract.
    """
```

This helper must:
- preserve the existing `run_validators()` behavior
- only special-case `all_personas.evidence_paths_exist`
- return `list[ValidationResult]`
- never mutate the output

Do not widen the base validator function signature.

---

## Component 4 — Engine Analyst Runner

Create:

```
ai_analyst/core/engine_analyst_runner.py
```

### Required surface

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class EngineAnalystRunResult:
    output: AnalysisEngineOutput
    validator_results: list[ValidationResult]


async def run_engine_analyst(
    persona_contract: PersonaContract,
    snapshot: dict,
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"],
    run_id: str,
    macro_context: dict | None = None,
) -> EngineAnalystRunResult:
    ...
```

### Behavior

1. Build prompt via `build_engine_prompt(snapshot, persona_contract, run_status, macro_context)`
2. Resolve LLM profile route:
   - use `persona_contract.model_profile_override` if present
   - otherwise fall back to the default analyst profile
3. Build messages:
   - system message = merged system + persona
   - user message = prompt user section
   - no images
4. Call `acompletion_metered()` with:
   - `response_format={"type": "json_object"}`
   - temperature from `persona_contract.temperature_override` or 0.1
   - `max_tokens=1500`
5. Extract JSON via `extract_json()`
6. Validate using `AnalysisEngineOutput.model_validate_json()`
7. Run validators:
   - use `run_validators_with_snapshot()` so `evidence_paths_exist` sees the real snapshot
8. Enforce degraded confidence rule deterministically:
   - if `run_status == "DEGRADED"` and `output.confidence > 0.65`, do not silently mutate the output
   - instead surface this via a failing `ValidationResult` from a narrow helper like `check_degraded_confidence_cap()`
   - runner still returns the validated output + validator results
9. Push progress event to `progress_store`
10. Return `EngineAnalystRunResult`

**On exception:**
- log
- re-raise
- caller handles retry/skip policy

### Important behavior rule

This PR does not introduce hidden output mutation.
The runner returns:
- the model-validated LLM output
- the validator results proving pass/fail conditions

Any future downgrade, veto, or hard invalidation behavior belongs to later governance/orchestration PRs.

---

## Component 5 — Minimal Additive Graph Support

Graph support is secondary in this PR.
It exists only to make the new runner independently callable from graph state without touching legacy execution.

### Modify `ai_analyst/graph/state.py`

Add optional fields only:

```python
evidence_snapshot: dict | None = None
evidence_run_status: Literal["SUCCESS", "DEGRADED", "FAILED"] | None = None
engine_outputs: list[AnalysisEngineOutput] | None = None
engine_validator_results: list[list[ValidationResult]] | None = None
```

Do not remove or alter legacy fields.

### Modify `ai_analyst/graph/analyst_nodes.py`

Add one new function only:

```python
async def engine_analyst_node(state: GraphState) -> GraphState:
    ...
```

**Behavior:**
- read `evidence_snapshot`
- read `evidence_run_status`
- run both personas in parallel:
  - `DEFAULT_ANALYST_CONTRACT`
  - `RISK_OFFICER_CONTRACT`
- collect:
  - `engine_outputs`
  - `engine_validator_results`
- on per-persona failure:
  - log warning
  - skip failed persona
  - require at least one valid `EngineAnalystRunResult`
- write new state keys only
- do not call or alter legacy analyst node functions

**Do not change:**
- `run_analyst()`
- `parallel_analyst_node()`
- `overlay_delta_node()`
- `deliberation_node()`
- any existing legacy flow

This function is additive only.
Pipeline selection remains a future PR concern.

---

## Test Strategy

No live LLM calls.
All LLM tests use mocked `acompletion_metered()` responses.

Use:
- deterministic prompt assertions
- mocked JSON responses
- synthetic `AnalysisEngineOutput`
- structurally correct snapshots built from `build_evidence_snapshot()` using synthetic lens outputs

---

## Required Tests

### `ai_analyst/tests/core/test_engine_prompt_builder.py`

Write focused tests for prompt content.

Required cases:
- system prompt includes all 8 `AnalysisEngineOutput` fields
- system prompt includes `lenses.*` citation rule
- system prompt includes confidence bands
- system prompt includes degraded confidence rule
- system prompt explicitly forbids citing inactive/failed lenses
- user content includes serialized snapshot
- user content includes meta
- user content includes derived
- user content includes `run_status`
- default analyst persona file loads correctly
- risk officer persona file loads correctly
- macro advisory included when provided
- macro advisory absent when None
- no chart/image/screenshot/overlay language
- no legacy schema terms:
  - `setup_valid`
  - `sweep_status`
  - `fvg_zones`
  - `displacement_quality`

### `ai_analyst/tests/core/test_evidence_path_validator.py`

Required cases:
- valid path resolves and returns True
- non-`lenses.*` path fails
- inactive lens path fails
- failed lens path fails
- nonexistent nested key fails
- empty evidence list passes here
- null leaf value allowed
- multiple paths stops on first invalid
- all three-lens paths pass
- deep nested path resolves correctly

### `ai_analyst/tests/core/test_engine_analyst_runner.py`

Mock `acompletion_metered()` to return controlled JSON strings.

Required cases:

**Schema validation**
- valid output parses successfully
- missing required field raises
- confidence out of range raises
- invalid bias raises
- invalid action raises

**Evidence / counterpoints / falsifiability**
- minimum 2 evidence paths passes
- 1 evidence path yields validator failure result
- counterpoints minimum passes
- empty counterpoints under 0.80 yields validator failure result
- falsifiability minimum passes
- empty `what_would_change_my_mind` yields validator failure result

**Confidence rule**
- degraded run with confidence > 0.65 yields degraded-cap validation failure
- healthy run allows confidence > 0.65

**AC-19 hallucination protection**
- structure-only active snapshot + momentum evidence path → validator failure
- nonexistent structure path → validator failure
- all valid paths in full snapshot → pass

**Risk Officer rule**
- BUY below 0.75 yields validator failure result

**Progress / return contract**
- progress event pushed
- runner returns `EngineAnalystRunResult`
- validator results preserved on return

### Optional graph-level smoke tests

Only if the repo already has a clean pattern for graph-node unit tests.
Do not expand scope if graph testing is brittle.
If added, keep them minimal:
- missing `evidence_snapshot` raises cleanly
- one persona fails, one succeeds → node returns one output
- both fail → node raises or returns controlled failure per existing graph conventions

---

## Acceptance Criteria Mapping

- **AC-12:** minimum 2 `evidence_used` entries proved by validator tests
- **AC-13:** counterpoint minimum proved by validator tests
- **AC-14:** falsifiability minimum proved by validator tests
- **AC-15:** degraded confidence ceiling proved by runner validation tests
- **AC-19:** inactive/failed/nonexistent lens evidence rejected by snapshot-aware validator
- **AC-20:** full regression suite green

Already closed in PR-AE-4 and not reopened here:
- AC-11
- AC-16
- AC-17
- AC-18

---

## Pre-Flight

Before implementation:

```bash
cd ai_analyst && python -m pytest --tb=short -q 2>&1 | tail -5
ls ai_analyst/models/engine_output.py ai_analyst/models/persona_contract.py ai_analyst/core/persona_validators.py
ls ai_analyst/core/snapshot_builder.py
ls ai_analyst/prompt_library/v2.0/ || echo "v2.0 does not exist yet"
```

Record baseline test count.
Do not start implementation until baseline is recorded.

---

## Implementation Order

1. create v2.0 prompt templates
2. implement `engine_prompt_builder.py`
3. implement `make_evidence_paths_validator()` + `run_validators_with_snapshot()`
4. implement `engine_analyst_runner.py`
5. add optional GraphState fields
6. add additive `engine_analyst_node()`
7. write tests
8. run full regression suite

---

## Verification Checklist

```bash
python -m pytest ai_analyst/tests/core/test_engine_prompt_builder.py -v
python -m pytest ai_analyst/tests/core/test_evidence_path_validator.py -v
python -m pytest ai_analyst/tests/core/test_engine_analyst_runner.py -v
python -m pytest ai_analyst/ --tb=short -q 2>&1 | tail -5
git diff --name-only main
```

Expected changed files:
- new files under `ai_analyst/prompt_library/v2.0/personas/`
- new files under `ai_analyst/core/`
- test files under `ai_analyst/tests/core/`
- additive edits only to:
  - `ai_analyst/core/persona_validators.py`
  - `ai_analyst/graph/state.py`
  - `ai_analyst/graph/analyst_nodes.py`

No legacy-analysis behavior changes.

---

## PR Description

**PR-AE-5: Persona Prompt Rewrite + Engine Runner + Evidence Citation Tests**

Closes Gate 2 for P2 by adding the first LLM-backed Analysis Engine persona execution path:
- v2.0 evidence-driven persona prompts for Default Analyst and Risk Officer
- snapshot-based engine prompt builder
- async engine analyst runner returning `AnalysisEngineOutput` + validator results
- snapshot-aware evidence path validation to prevent inactive/failed lens hallucination
- confidence-cap validation for DEGRADED runs
- additive graph support via `engine_analyst_node()` and optional GraphState fields

This PR does not modify the legacy analyst pipeline.
Legacy `AnalystOutput`, prompt builder, and existing graph functions remain untouched.

Acceptance criteria closed here:
- AC-12 evidence minimum
- AC-13 counterpoints minimum
- AC-14 falsifiability minimum
- AC-15 degraded confidence ceiling
- AC-19 no inactive/failed lens hallucination
- AC-20 full regression green

Spec: `docs/ANALYSIS_ENGINE_SPEC_v1.2.md`, Sections 6.3–6.8, 13, 17
