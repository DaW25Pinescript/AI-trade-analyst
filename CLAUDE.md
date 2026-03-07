# CLAUDE.md — Phase 3G: Explainability / Audit Layer

## Role

You are a principal Python engineer working inside the **AI Trade Analyst** repository.

Phase 3G adds a fully deterministic explainability and audit layer on top of the 3F multi-analyst output. No new intelligence is being built. No new market signals are being computed. The job is to make the system answer — from saved artifacts alone, without any LLM call — why a verdict happened, which signals drove it, which persona constrained it, and how confidence ended where it did.

Read `ARCHITECTURE.md` first. Then read this file and the supporting spec files before writing any code.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**Already complete — do not touch:**
- `market_data_officer/feed/`
- `market_data_officer/officer/`
- `market_data_officer/structure/`
- `analyst/pre_filter.py`
- `analyst/contracts.py`
- `analyst/prompt_builder.py`
- `analyst/analyst.py`
- `analyst/service.py`
- `analyst/multi_contracts.py`
- `analyst/personas.py`
- `analyst/arbiter.py`
- `analyst/multi_analyst_service.py`

**What you are building in Phase 3G:**
```
analyst/
  explainability.py          ← explanation engine: produces ExplainabilityBlock from MultiAnalystOutput
  explain_contracts.py       ← ExplainabilityBlock, SignalInfluence, PersonaDominance,
                                ConfidenceProvenance, CausalChain dataclasses
  explain_service.py         ← orchestrator: run_explain(instrument) or run_explain_from_file(path)
  templates.py               ← deterministic prose template renderer (no LLM)
tests/
  test_explainability.py
  test_templates.py
  test_explain_integration.py
run_explain.py               ← CLI entry point
```

Additionally, `analyst/multi_contracts.py` gains one new field on `MultiAnalystOutput`:
```python
explanation: Optional[ExplainabilityBlock] = None
```
This is the only permitted change to any existing file — additive only, no other modifications.

---

## Locked decisions for 3G

| Decision | Value |
|---|---|
| Explanation location | Embedded in `MultiAnalystOutput.explanation` AND written as standalone file |
| Standalone file | `analyst/output/{instrument}_multi_analyst_explainability.json` |
| LLM involvement | Zero — fully deterministic from saved artifacts |
| Replay capability | Re-derive explanation from saved `MultiAnalystOutput` without re-running models |
| Deterministic Python fields | Signal influence ranking, persona dominance, confidence provenance, no-trade/caution drivers — all four |
| Human-readable prose | Generated from structured templates over saved fields — no LLM |

---

## File reading order

1. `ARCHITECTURE.md` ← read first
2. `CLAUDE.md` ← you are here
3. `OBJECTIVE.md`
4. `CONSTRAINTS.md`
5. `CONTRACTS.md`
6. `ACCEPTANCE_TESTS.md`

---

## When you are done

Run Group 0 regression first. Any failure stops all further work. Then Groups A through G. Report pass/fail per group before declaring Phase 3G complete.
