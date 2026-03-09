# AI Trade Analyst — Project Progress Plan
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`  
**Last updated:** 9 March 2026
**Current phase:** Operationalise — scheduler / APScheduler integration

---

## Overall Architecture

The system is a multi-surface trading intelligence workspace with three integrated layers:

```
Static Frontend (UI)
        ↓
Python Analyst Engine  ←→  Market Data Officer
        ↓
Multi-Agent Governance (Trade Senate / Arbiter)
        ↓
LLM Layer (Claude via CLIProxyAPI)
```

---

## Phase Status Overview

| Phase | Description | Status |
|-------|-------------|--------|
| Phase A | Single analyst smoke path | ✅ Complete |
| Phase B | Central provider/model config | ✅ Complete |
| Phase C | Quorum/degraded failure handling | ✅ Complete |
| Phase D | V1.1 snapshot integrity patch (H-1 → H-4) | ✅ Complete |
| Phase 1A | Market Data Officer — EURUSD baseline spine | ✅ Complete |
| Phase 1B | Market Data Officer — XAUUSD spine (15m, 1h, 4h, 1d) | ✅ Complete |
| Phase E+ | Additional instruments, provider abstraction | ✅ Complete |
| Instrument Promotion | GBPUSD/XAGUSD/XPTUSD → trusted — 419/419 tests | ✅ Complete |
| Per-Instrument Provider Routing | Explicit per-instrument provider policy — 468/468 tests | ✅ Complete |
| Tidy | Async marker cleanup (4 files) | ⏳ Pending |
| Config | jCodeMunch API key config (Anthropic + GitHub PAT) | ⏳ Pending |
| Operationalise | Scheduler / APScheduler integration | ⏳ Pending |

---

## Completed Phases — Detail

### ✅ Phase A — Single Analyst Smoke Path
**Goal:** Prove the full `/triage → /analyse → LangGraph → LLM → arbiter` pipeline end-to-end.

**What was broken at start:**
- Triage path entirely stub-based
- 401 Unauthorized on every LLM attempt
- 0/4 analysts returning valid responses (503 quorum failure)
- No logs or visibility

**Key fixes:**
- Session validation (`session: "London"` hardcoded for deterministic smoke)
- `TRIAGE_SMOKE_MODE` propagated per-request through `GraphState`
- Proxy auth: `LOCAL_LLM_PROXY_API_KEY=qwe123` via `RUN.local.bat`
- Arbiter JSON fence parsing — `_extract_json()` helper added
- `chart_lenses_node` fan-in merge fix (partial state dict return)
- Model routing: all personas now resolve from `llm_routing.yaml` (`openai/claude-sonnet-4-6`)
- `RUN.bat` stale process auto-kill (no more Y/N prompt)

**Smoke run result:** 7 runs to get from 422 → 200 with real arbiter verdict (`NO_TRADE`, correct — no chart data).

**Test count:** 121/121 Python + 96/96 JS contract tests.

---

### ✅ Phase B — Central Provider/Model Config
**Goal:** Single source of truth for model routing — no hardcoded model strings per persona.

**What changed:** `router.get_analyst_roster()` resolves model from `task_routing.analyst_reasoning.primary_model` in `llm_routing.yaml` for all personas.

---

### ✅ Phase C — Quorum/Degraded Failure Handling
**Goal:** System degrades gracefully when fewer than 4 analysts respond, rather than hard-failing.

**What changed:** Arbiter now accepts partial analyst sets; `_fallback_verdict()` accepts `analysts_received`/`analysts_valid` params; quorum logic made configurable rather than hardcoded.

---

### ✅ Phase D — V1.1 Snapshot Integrity Patch (H-1 → H-4)
**Goal:** Fix 4 snapshot integrity issues in the frontend/backend contract.

| Hotfix | Issue | Fix |
|--------|-------|-----|
| H-1 | casing boundary | `deepSnakeToCamel(digest)` in `adapters.js` |
| H-2 | `journeyId` missing | Fixed in prior work, verified + test coverage added |
| H-3 | `gateJustifications` missing | Fixed in prior work, verified + test coverage added |
| H-4 | `provenance` missing | Fixed in prior work, verified + test coverage added |

**Test result:** 96/96 JS contract tests (up from 65, +31 assertions).

---

### ✅ Phase 1A — Market Data Officer: EURUSD Baseline Spine
**Goal:** Feed a real `MarketPacketV2` into the analyst graph. Analysts were previously reasoning from prompt context only.

**Spec:** `docs/MDO_Phase1A_Spec.md`

**Key findings from diagnostic:**
- Code was not broken — the "truck hadn't restocked the vending machine"
- Root cause: no hot-package artifacts in dev (Dukascopy returns empty on weekends)
- Provider mismatch: spec originally said yFinance primary; actual module uses Dukascopy exclusively

**What was built:**
- `--fixture` flag on `run_feed.py` — writes synthetic EURUSD hot package to `market_data/packages/latest/` using exact same manifest/CSV shape as existing test fixtures
- `tests/test_phase1a_relay.py` — two deterministic tests:
  - **Test A (officer relay):** seed fixture → `refresh_from_latest_exports("EURUSD")` → assert valid `MarketPacketV2` → assert all 6 timeframes (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`)
  - **Test B (analyst consumption):** `run_analyst()` with injected packet + mocked LLM → assert structured `AnalystOutput` returned

**Test result:** 359/359 (354 baseline + 5 new). Zero regressions.

**Constraints held:** No SQLite, no new top-level module, no scheduler, no side-channel loader.

---

## Current State — What Works End-to-End Today

```
run_feed.py --fixture
        ↓
market_data/packages/latest/  (EURUSD, 6 timeframes)
        ↓
refresh_from_latest_exports("EURUSD")
        ↓
MarketPacketV2  (trusted, 6 TFs, quality flags clean)
        ↓
run_analyst()  (consumes packet, calls LLM via CLIProxyAPI)
        ↓
AnalystOutput  (structured result)
        ↓
Arbiter  (verdict + artifact written)
```

The full relay is proven. Analysts receive real market data structure. LLM calls are live via `CLIProxyAPI` at `127.0.0.1:8317`.

---

## Next Up — Phase 1B+: XAUUSD Spine

**Goal:** Extend the proven EURUSD spine to XAUUSD.

**Spec status:** Not yet drafted — draft spec before any coding (same process as Phase 1A).

**Known scope:**
- Instruments: XAUUSD
- Timeframes: `15m`, `1h`, `4h`, `1d`
- Provider: Dukascopy (same as EURUSD)
- Storage: file-based spine (same pattern)
- Interface: same `get_market_snapshot()` / `MarketPacketV2` contract

**Expected effort:** Significantly less than Phase 1A — the spine is proven, the officer contract is locked, and the fixture pattern is in place. Main work is instrument config and ensuring the XAUUSD feed/loader paths are correctly wired.

**First step for next session:**
```
Draft docs/MDO_Phase1B_Spec.md using the same structure as Phase 1A.
Audit XAUUSD-specific config in market_data_officer/ before writing any code.
```

---

## Pending Items

### ⏳ Async Marker Cleanup (Low priority)
4 files have async markers that need cleanup. Non-blocking — no functional impact.

### ⏳ jCodeMunch API Key Config (Medium priority)
Configure Anthropic API key and GitHub PAT for jCodeMunch MCP server integration with Claude Desktop.  
Confirmed exe path: `C:\Users\david\AppData\Roaming\Python\Python314\Scripts\jcodemunch-mcp.exe`

### ⏳ Phase E+ — Additional Instruments & Provider Abstraction (Medium priority)
After XAUUSD is proven, extend to further instruments and build proper provider abstraction layer (yFinance as alternative to Dukascopy, alias config).

### ⏳ Operationalise — Scheduler (Low priority)
APScheduler or similar to trigger feed runs automatically. Out of scope until the manual path is fully stable across instruments.

---

## Environment Reference

| Component | Value |
|-----------|-------|
| Backend port | 8000 |
| UI port | 8080 |
| Proxy port | 8317 |
| Proxy URL | `http://127.0.0.1:8317/v1` |
| Proxy auth token | `qwe123` (via `RUN.local.bat` — gitignored) |
| Model | `openai/claude-sonnet-4-6` (all personas) |
| Model config source | `config/llm_routing.yaml` |
| Bootstrap | `.\RUN.bat` (auto-kills stale port 8000, loads `RUN.local.bat`) |
| Python | 3.14 |
| OS | Windows |

---

## Repo Docs Index

| Doc | Path | Purpose |
|-----|------|---------|
| Specs index | `docs/README_specs.md` | Active phase, completed phases, pending |
| Phase 1A spec (closed) | `docs/MDO_Phase1A_Spec.md` | Controlling spec + closed phase record |
| Phase 1B+ spec | `docs/MDO_Phase1B_Spec.md` | To be drafted |

---

*Generated from session handoff notes and Phase 1A spec — 8 March 2026*
