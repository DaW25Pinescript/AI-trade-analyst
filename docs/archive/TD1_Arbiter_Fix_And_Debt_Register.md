# Micro-PR: Arbiter Persona Contract Validation + Technical Debt Register

This prompt covers two tasks on the same branch. Both are small and non-overlapping.

---

## Task 1 — Fix arbiter assert (TD-1)

### What to change

**File 1: `analyst/arbiter.py`**

Replace:
```python
assert len(persona_outputs) == 2, f"Expected 2 persona outputs, got {len(persona_outputs)}"
```

With:
```python
if len(persona_outputs) != 2:
    raise ValueError(f"Expected exactly 2 persona outputs, got {len(persona_outputs)}")
```

**File 2: `tests/test_arbiter.py`**

Add one deterministic negative-path test at the end of `TestGroupD_ConstraintEnforcement`:

```python
def test_td_contract_requires_exactly_two_personas(self):
    """Arbiter must fail loudly if persona_outputs length is not exactly two."""
    digest = _clean_digest()
    a = _make_pv("long_bias", "high", "bullish")

    with pytest.raises(
        ValueError,
        match=r"Expected exactly 2 persona outputs, got 1",
    ):
        arbitrate([a], digest)
```

### Implementation sequence

1. Apply the validation change in `analyst/arbiter.py`.
2. Run baseline: `pytest tests/test_arbiter.py::TestGroupD_ConstraintEnforcement -q --tb=no`
3. Add the new test method to `tests/test_arbiter.py`.
4. Run: `pytest tests/test_arbiter.py::TestGroupD_ConstraintEnforcement -q --tb=no`
5. Run the broader arbiter test target if available.
6. Report final green results.

### Acceptance criteria

| AC | Gate | Condition |
|----|------|-----------|
| AC-1 | No assert | Arbiter no longer relies on `assert` for persona output count |
| AC-2 | Explicit exception | Contract violation raises `ValueError` |
| AC-3 | Happy-path preserved | Existing arbiter behavior unchanged for valid input |
| AC-4 | Negative-path test | One deterministic test proves the error path |
| AC-5 | Scope confined | Changes confined to `analyst/arbiter.py` + `tests/test_arbiter.py` only |
| AC-6 | No unrelated cleanup | No other changes included |

### Commit message
```
fix(arbiter): replace assert with explicit persona contract validation
```

---

## Task 2 — Add Technical Debt Register to progress plan

**File: `docs/AI_TradeAnalyst_Progress.md`**

Append the following section **after the existing content** (before any final closing markers if present). This is a new §8 section.

```markdown
## 8) Technical Debt Register

Findings from the senior architect audit conducted after Operationalise Phase 2 closure (644 tests, 10 March 2026). Items are severity-ranked and tagged with recommended resolution timing.

### Critical — resolve in next named phase or as micro-PR

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-1 | `assert` used for runtime contract enforcement | `analyst/arbiter.py` | Silent contract violation under `-O` flag; invalid state reaches downstream decision logic | **Micro-PR — immediate** (fix drafted, ship before Security/API Hardening) |
| TD-2 | `call_llm()` lacks timeout, retry, circuit-breaker | `analyst/analyst.py`, LLM call path | Stalled upstream call blocks processing; unstable tail latency; failure amplification | **Fold into Security/API Hardening** — same risk surface as `/analyse` timeout policy |
| TD-3 | `sys.path.insert` used as dependency wiring | Multiple core modules | Environment-dependent import resolution; deployment instability; shadowing risk | **Named micro-PR** — prerequisite for multi-environment config profiles; requires proper packaging (`pyproject.toml` / editable install) |

### Maintenance — resolve opportunistically or as named cleanup

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-4 | Orchestration duplication (single vs multi-analyst) | `analyst/service.py`, `analyst/multi_analyst_service.py` | Parallel pipelines with drift risk; lifecycle changes must be made in two places | **Named cleanup** — extract shared orchestration steps into common helper; pick up between phases |
| TD-5 | Magic-string enum duplication | `analyst/analyst.py`, `analyst/personas.py`, `analyst/arbiter.py` | Verdict/confidence/alignment enums hand-maintained in multiple modules; drift and inconsistent validation | **Micro-PR** — centralise into shared contracts module; low risk, high leverage |
| TD-6 | `build_market_packet()` God-function | `market_data_officer/officer/service.py` | Trust policy, quality, feature extraction, serialization, and logging in one function; hard to test in isolation | **Future cleanup** — decompose when packet assembly needs to evolve; not blocking current work |
| TD-7 | `build_market_packet()` eager loading + `iterrows()` | `market_data_officer/officer/service.py` | O(total_rows) Python loop per request; CPU/memory pressure scales with instrument count | **Future optimisation** — current scale (5 instruments, 4–6 TFs) is within tolerance; revisit when concurrency or instrument count grows |
| TD-8 | Mixed data-shape handling in `classify_fvg_context` | `analyst/pre_filter.py` | `hasattr`/`get` branches for object vs dict payloads; weak upstream contracts | **Resolves with runtime lane convergence** — architectural, not a standalone cleanup |
| TD-9 | Unused variables in `build_market_packet()` | `market_data_officer/officer/service.py` | `is_provisional`, `quality_label`, `quality_flags`, `struct_kwargs` assigned but unused; misleading intent | **Micro-PR** — remove or document intent; very small |

### Documentation / testing gaps — address as part of related phases

| # | Item | Location | Risk | Resolution timing |
|---|------|----------|------|-------------------|
| TD-10 | LLM failure modes under-tested | Test suites for analyst path | Tests mock `call_llm` but don't exercise timeout, malformed response, or retry behavior | **Addressed by TD-2 resolution** — when safeguards are added, tests follow |
| TD-11 | No import-path stability tests | No coverage for `sys.path.insert` patterns | Path mutation normalised in tests; packaging regressions not actively caught | **Addressed by TD-3 resolution** — when packaging is fixed, add environment-matrix tests |
| TD-12 | Cross-module architecture contracts undocumented | Core service boundaries | Ownership of policy decisions, fallback semantics, scaling expectations embedded in code flow | **Future documentation** — address when runtime lanes converge or during next architecture review |

### Resolution sequence

1. **Now:** TD-1 arbiter assert fix (micro-PR, already drafted)
2. **Next phase:** TD-2 folds into Security/API Hardening spec
3. **Between phases:** TD-3 (sys.path.insert), TD-5 (enum centralisation), TD-9 (unused vars) as opportunistic micro-PRs
4. **Future:** TD-4 (orchestration duplication), TD-6/TD-7 (packet assembly), TD-8 (data-shape convergence), TD-12 (architecture docs)
5. **Follows from above:** TD-10, TD-11 resolve as side-effects of their parent items
```

### Commit message for the debt register addition
```
docs(progress): add technical debt register from post-Phase 2 architect audit
```

---

## Execution order

1. Complete Task 1 (arbiter fix) first — get it green.
2. Then apply Task 2 (debt register) to the progress plan.
3. Both tasks can share a branch or be separate commits — either is fine.
4. After TD-1 is marked as shipped, update its row in the debt register: change "Micro-PR — immediate" to "✅ Resolved — [date]".

## Hard constraints

- No new top-level module
- No unrelated arbiter refactor
- No `call_llm` changes
- No API/schema changes
- No MDO changes
- Deterministic tests only
- Smallest safe option only
- Do not broaden scope beyond these two tasks

## On completion, report

- Files changed (should be 3: `arbiter.py`, `test_arbiter.py`, `AI_TradeAnalyst_Progress.md`)
- Final test output for arbiter tests
- Whether AC-1 through AC-6 are all satisfied
- Confirmation that debt register is appended to progress plan
