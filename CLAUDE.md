# CLAUDE.md — Phase 3E: Analyst Structure Consumption

## Role

You are a principal Python/data engineer and prompt architect working inside the **AI Trade Analyst** repository.

Phase 3E is the first phase where structure state actively influences analyst reasoning and verdict generation. The feed, Officer, and structure engine are all complete. Your job now is to wire them into a working analyst layer that produces testable, auditable verdicts.

Read `ARCHITECTURE.md` first. Then read this file and the supporting spec files before writing any code or prompts.

---

## Repo context

Repo: `https://github.com/DaW25Pinescript/AI-trade-analyst`

**Already complete — do not touch:**
- `market_data_officer/feed/` — feed pipeline
- `market_data_officer/officer/` — Market Data Officer, Market Packet v2
- `market_data_officer/structure/` — Structure Engine, Phases 3A–3D including `reader.py`

**What you are building in Phase 3E:**
```
analyst/
  __init__.py
  pre_filter.py        ← Python structure digest + gate engine
  contracts.py         ← StructureDigest, AnalystVerdict, ReasoningBlock dataclasses
  prompt_builder.py    ← assembles LLM context from digest + packet
  analyst.py           ← LLM analyst call + response parsing
  service.py           ← top-level: run_analyst(instrument) orchestrator
tests/
  test_pre_filter.py
  test_analyst_verdict.py
  test_analyst_integration.py
run_analyst.py         ← CLI entry point
```

---

## Architecture for 3E

Two-layer hybrid:

```
MarketPacketV2
    ↓
Python Pre-filter (pre_filter.py)
  - reads structure block
  - applies HTF regime gate
  - computes structure digest
  - flags supports and conflicts
    ↓
StructureDigest (compact, deterministic)
    ↓
LLM Analyst (analyst.py)
  - receives digest + selected packet context
  - produces JSON verdict + reasoning block
    ↓
AnalystVerdict + ReasoningBlock
```

The Python layer owns: gating, normalization, digest compression, hard constraints.
The LLM owns: synthesis, conflict weighting, verdict text, reasoning quality.

---

## Locked decisions for 3E

| Decision | Value |
|---|---|
| Analyst architecture | Single persona in 3E, multi-persona deferred to 3F |
| Structure influence mode | Gating for HTF regime, advisory for LTF detail |
| Active structure fields | HTF regime, recent BOS/MSS, nearest liquidity, active FVGs, sweep reclaim outcomes |
| Output format | JSON verdict block + human-readable reasoning block |
| Analyst mechanism | Hybrid: Python pre-filter → LLM |
| LLM re-deriving structure | Explicitly forbidden — structure comes from digest only |

---

## File reading order

1. `ARCHITECTURE.md` ← read first
2. `CLAUDE.md` ← you are here
3. `OBJECTIVE.md` — what 3E builds and the hybrid architecture contract
4. `CONSTRAINTS.md` — hard rules, gate logic, prompt engineering standards
5. `CONTRACTS.md` — StructureDigest, AnalystVerdict, ReasoningBlock schemas
6. `ACCEPTANCE_TESTS.md` — test groups

---

## When you are done

Run Group 0 regression first. Any failure stops all further work. Then Groups A through G. Report pass/fail per group before declaring Phase 3E complete.
