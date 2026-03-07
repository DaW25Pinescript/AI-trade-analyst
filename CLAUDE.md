# CLAUDE.md — Phase 3F: Multi-Analyst Consensus Layer

## Role

You are a principal Python/prompt architect working inside the **AI Trade Analyst** repository.

Phase 3F extends the single-analyst 3E pipeline into a controlled multi-analyst architecture. Two LLM personas consume the same deterministic `StructureDigest`, produce separate structured verdicts, and an Arbiter synthesizes them into one final decision — all governed by the existing Python hard-constraint layer.

Read `ARCHITECTURE.md` first. Then read this file and the supporting spec files before writing any code or prompts.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**Already complete — do not touch:**
- `market_data_officer/feed/`
- `market_data_officer/officer/`
- `market_data_officer/structure/`
- `analyst/pre_filter.py` — deterministic digest engine
- `analyst/contracts.py` — StructureDigest, AnalystVerdict, ReasoningBlock
- `analyst/prompt_builder.py`
- `analyst/analyst.py` — single-persona LLM analyst
- `analyst/service.py` — single-analyst orchestrator

**What you are building in Phase 3F:**
```
analyst/
  multi_contracts.py       ← PersonaVerdict, ArbiterDecision, MultiAnalystOutput dataclasses
  personas.py              ← persona definitions and per-persona prompt policies
  arbiter.py               ← Arbiter synthesis logic
  multi_analyst_service.py ← top-level orchestrator: run_multi_analyst(instrument)
tests/
  test_personas.py
  test_arbiter.py
  test_multi_analyst_integration.py
run_multi_analyst.py       ← CLI entry point
```

Do not modify any existing `analyst/` modules. Extend only.

---

## Locked decisions for 3F

| Decision | Value |
|---|---|
| Number of personas | 2 — Technical Structure Analyst, Execution/Timing Analyst |
| Digest sharing | All personas consume the same `StructureDigest` — no exceptions |
| Data access parity | Personas differ by prompt/policy only, not by data access |
| Arbiter | Required — only the Arbiter produces the final exported verdict |
| Python hard constraints | Supreme — Arbiter cannot override deterministic no-trade conditions |
| 3E pipeline | Preserved — `analyst/service.py` continues to work unchanged |
| Senate/swarm layer | Explicitly out of scope for 3F |

---

## Architecture

```
MarketPacketV2
    ↓
pre_filter.py  →  StructureDigest (deterministic, shared)
    ↓                      ↓
    ↓          ┌───────────┴───────────┐
    ↓    Technical Structure     Execution/Timing
    ↓        Analyst                Analyst
    ↓          └───────────┬───────────┘
    ↓               PersonaVerdict × 2
    ↓                      ↓
    ↓                 arbiter.py
    ↓                      ↓
    ↓              ArbiterDecision
    ↓                      ↓
    └──────────→  MultiAnalystOutput (saved to file)
```

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

Run Group 0 regression first. Any failure stops all further work. Then Groups A through G. Report pass/fail per group before declaring Phase 3F complete.
