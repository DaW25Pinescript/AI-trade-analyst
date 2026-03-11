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
