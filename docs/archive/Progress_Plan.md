# AI Trade Analyst — Project Progress Plan

**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 8 March 2026  
**Current phase:** **Phase 1B+ — XAUUSD spine** *(spec not yet drafted)*

---

## 1. Purpose

This document is the high-level project baseline and forward plan for **AI Trade Analyst**.

It is intended to answer four questions quickly:

1. What architecture is already proven?
2. Which phases are complete?
3. What is the next approved implementation target?
4. What environment assumptions matter for getting back to a working baseline?

Use this together with:

- `docs/README_specs.md` — active specs index
- `docs/MDO_Phase1A_Spec.md` — closed Phase 1A implementation record
- future phase specs (starting with `docs/MDO_Phase1B_Spec.md`)

---

## 2. Overall Architecture

The system is a multi-surface trading intelligence workspace with three integrated layers:

```text
Static Frontend (UI)
        ↓
Python Analyst Engine  ←→  Market Data Officer
        ↓
Multi-Agent Governance (Trade Senate / Arbiter)
        ↓
LLM Layer (Claude via CLIProxyAPI)
```

### Architecture summary

- The **frontend** provides triage, journey workflow, state snapshots, and review surfaces.
- The **analyst engine** handles `/triage`, `/analyse`, LangGraph orchestration, persona execution, and arbiter verdict generation.
- The **Market Data Officer (MDO)** is the deterministic data-preparation lane that produces and loads market artifacts and packet contracts.
- The **governance layer** turns analyst outputs into structured verdicts, fallback handling, and auditable artifacts.
- The **LLM layer** currently routes through **CLIProxyAPI** at `127.0.0.1:8317` using the OpenAI-compatible path.

---

## 3. Phase Status Overview

| Phase | Description | Status |
|------|-------------|--------|
| Phase A | Single analyst smoke path | ✅ Complete |
| Phase B | Central provider/model config | ✅ Complete |
| Phase C | Quorum / degraded failure handling | ✅ Complete |
| Phase D | V1.1 snapshot integrity patch (H-1 → H-4) | ✅ Complete |
| Phase 1A | Market Data Officer — EURUSD baseline spine | ✅ Complete |
| Phase 1B+ | Market Data Officer — XAUUSD spine | ⏳ Next |
| Phase E+ | Additional instruments, provider abstraction | ⏳ Pending |
| Operationalise | Scheduler / APScheduler integration | ⏳ Pending |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |

---

## 4. Completed Phases — Baseline Record

### Phase A — Single Analyst Smoke Path ✅

**Goal:** Prove the full `/triage → /analyse → LangGraph → LLM → arbiter` relay end to end.

#### What was broken at the start
- Triage path was effectively stub-based
- LLM calls were failing with auth/config issues
- Analyst quorum failures caused hard 503 outcomes
- There was no reliable hop-by-hop visibility

#### What was fixed
- Deterministic smoke-session handling
- Smoke-mode propagation through the request/graph path
- Proxy auth wiring via local environment + startup flow
- Router/model path centralized through `llm_routing.yaml`
- Fan-in / merge-path bug fixed so analyst output survives to arbiter
- Startup reliability improved in `RUN.bat`

#### Result
The smoke path is now genuinely online:
- loopback works
- graph entry works
- LLM call succeeds
- analyst output reaches arbiter
- verdict returns
- artifact writes successfully

---

### Phase B — Central Provider / Model Config ✅

**Goal:** Move model routing out of scattered call sites and into one source of truth.

#### Result
- Persona/model routing resolves from config rather than hardcoded strings
- All personas use the same configured model route
- Local proxy auth is environment-driven rather than hardcoded placeholder behavior

---

### Phase C — Quorum / Degraded Failure Handling ✅

**Goal:** Make the system degrade gracefully rather than collapsing when analyst responses are partial.

#### Result
- Smoke mode can bypass full quorum requirements deterministically
- Quorum/fallback handling is configurable rather than rigid
- Partial analyst sets no longer necessarily cause opaque hard failure

---

### Phase D — V1.1 Snapshot Integrity Patch (H-1 → H-4) ✅

**Goal:** Repair snapshot/state integrity issues in the frontend/backend contract.

#### Fixed hot spots
- casing boundary cleanup
- `journeyId` presence
- `gateJustifications` capture
- `provenance` field tracking

#### Result
The snapshot layer now reflects the actual journey state more faithfully and is suitable as the baseline for continued UI/workflow refinement.

---

### Phase 1A — Market Data Officer: EURUSD Baseline Spine ✅

**Goal:** Prove the deterministic relay from feed artifacts into analyst consumption using a real `MarketPacketV2`.

**Source of truth:** `docs/MDO_Phase1A_Spec.md`

#### Key diagnostic finding
The MDO architecture was not fundamentally broken. The main gap was that **no hot-package artifacts existed in dev**, especially under weekend Dukascopy conditions.

#### What was implemented
- `run_feed.py --fixture`
- deterministic seeding of EURUSD hot-package artifacts under `market_data/packages/latest/`
- relay tests proving:
  - officer path
  - packet assembly
  - analyst consumption path with injected packet + mocked LLM

#### Result
The relay is now proven:

```text
run_feed.py --fixture
        ↓
market_data/packages/latest/
        ↓
refresh_from_latest_exports("EURUSD")
        ↓
MarketPacketV2
        ↓
run_analyst() with packet
        ↓
AnalystOutput
        ↓
Arbiter / artifact write
```

#### Constraints held
- no SQLite
- no new top-level module
- no scheduler
- no side-channel loader
- file-based spine preserved

---

## 5. Current Working Baseline

The project should now be treated as a **running baseline** rather than a speculative prototype.

### What works end to end today

- `RUN.bat` bootstraps the local environment, backend, UI, and proxy workflow
- `RUN.local.bat` provides the local secret/config overlay
- CLIProxyAPI-backed LLM calls are live
- `/triage` and `/analyse` paths are proven
- analyst output reaches the arbiter
- artifacts are written successfully
- snapshot integrity issues from H-1 → H-4 are closed
- MDO Phase 1A proves deterministic packet handoff into analyst consumption

### What this means operationally

If the repo is restored on the **same machine** and the broader local prerequisites still exist, the project can be brought back to this working baseline with relatively little manual effort.

This is not yet a universal “fresh machine from nothing” bootstrap, but it is a **strong rebuildable baseline**.

---

## 6. Next Up — Phase 1B+ (XAUUSD Spine)

**Status:** Next  
**Spec:** Not yet drafted  
**Rule:** **Draft spec first, run diagnostics second, code third**

### Goal
Extend the proven MDO spine from EURUSD to **XAUUSD**.

### Expected scope
- Instrument: `XAUUSD`
- Timeframes: `15m`, `1h`, `4h`, `1d`
- Provider: Dukascopy
- Storage: file-based spine
- Contract path: `build_market_packet()` / `refresh_from_latest_exports()` returning `MarketPacketV2`

### Why this should be faster than Phase 1A
- the spine is already proven
- the officer contract is already locked
- the fixture pattern already exists
- the analyst packet-consumption path is already proven

### First step for the next implementation pass
1. Draft `docs/MDO_Phase1B_Spec.md`
2. Audit the repo state for XAUUSD-specific assumptions
3. Run diagnostics against the new spec
4. Only then implement the smallest patch set

---

## 7. Pending Work After Phase 1B+

### Phase E+ — Additional Instruments & Provider Abstraction
After XAUUSD is proven, extend the same spine to more instruments and formalize provider abstraction cleanly.

### Operationalise — Scheduler / APScheduler
Only after the manual path is stable across instruments.

### Async Marker Cleanup
Low-priority tidy work on the remaining async-marker follow-up files.

### jCodeMunch Config
Complete the MCP/API-key setup for Anthropic + GitHub PAT integration.

---

## 8. Environment Reference

| Component | Value |
|-----------|-------|
| Backend port | 8000 |
| UI port | 8080 |
| Proxy port | 8317 |
| Proxy URL | `http://127.0.0.1:8317/v1` |
| Proxy auth token | stored via `RUN.local.bat` *(gitignored local secret)* |
| Model | `openai/claude-sonnet-4-6` |
| Model config source | `config/llm_routing.yaml` |
| Bootstrap | `RUN.bat` |
| Local secret overlay | `RUN.local.bat` |
| Python | 3.14 |
| OS | Windows |

### Startup expectation
`RUN.bat` is expected to:
- verify/install core dependencies
- load local env overrides
- start or restart local runtime components as needed
- restore the repo to the current working baseline on the same machine, assuming external prerequisites still exist

---

## 9. Repo Docs Index

| Doc | Path | Purpose |
|-----|------|---------|
| Specs index | `docs/README_specs.md` | active phase + completed specs index |
| Phase 1A closed spec | `docs/MDO_Phase1A_Spec.md` | controlling spec + historical implementation record |
| Phase 1B+ spec | `docs/MDO_Phase1B_Spec.md` | to be drafted |
| Progress plan | `docs/Progress_Plan.md` | project-level baseline and forward plan |

---

## 10. Working Rule for Future Phases

For any new implementation phase:

1. **Draft the spec first**
2. **Audit repo state against the spec**
3. **Report gaps before coding**
4. **Implement the smallest patch set**
5. **Update the spec and index after completion**

This process is now proven and should be reused for Phase 1B+ and beyond.

---

*Generated from the current repo handoff, closed Phase 1A spec, and specs index baseline on 8 March 2026.*
