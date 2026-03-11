# Audit 0 — Repo Orientation + Risk Map

**Auditor:** Claude Code
**Date:** 2026-03-05
**Constraint:** No code modifications

---

## 1. Architecture Sketch

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser App (app/)                        │
│  ┌──────────┐  ┌────────────┐  ┌───────────┐  ┌──────────┐ │
│  │ formHand-│  │ stateManag-│  │ schema    │  │ exports/ │ │
│  │ ler.js   │→ │ er.js      │  │ Validator │  │ import   │ │
│  └────┬─────┘  └─────┬──────┘  └───────────┘  └──────────┘ │
│       │              │                                       │
│       ▼              ▼                                       │
│  ┌──────────────────────────┐                                │
│  │  analystBridge.js (G11)  │ ← Verdict card render (G12)   │
│  └────────────┬─────────────┘                                │
└───────────────┼─────────────────────────────────────────────┘
                │ POST /analyse (FormData + chart images)
                ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI (ai_analyst/api/main.py)                │
│  Rate limiter → Input validation → GroundTruthPacket build  │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│           ExecutionRouter → ChartAnalysisRuntime             │
│                                                              │
│  LangGraph Pipeline:                                         │
│  ┌────────────┐  ┌───────────────┐                           │
│  │ chart_setup│  │ macro_context │  (parallel)               │
│  └─────┬──────┘  └───────┬───────┘                           │
│        └────────┬─────────┘                                  │
│                 ▼                                             │
│  ┌──────────┐ → ┌──────────────┐ → ┌────────────┐           │
│  │chart_base│   │auto_detect   │   │chart_lenses│           │
│  └──────────┘   └──────────────┘   └─────┬──────┘           │
│                                          ▼                   │
│                                   ┌─────────────┐            │
│                                   │ run_arbiter  │            │
│                                   └──────┬──────┘            │
│                                          ▼                   │
│                              ┌────────────────────┐          │
│                              │ bridge_formatter → │          │
│                              │ logging_node       │          │
│                              └────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                │
                │ get_macro_context(pair)
                ▼
┌─────────────────────────────────────────────────────────────┐
│          Macro Risk Officer (macro_risk_officer/)            │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐          │
│  │DXYFeeder│ │VIXFeeder│ │RatesFeed│ │CalendarFd│          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └─────┬────┘          │
│       └───────────┼───────────┼─────────────┘               │
│                   ▼                                          │
│            ┌─────────────┐  ┌──────────────────┐             │
│            │ RiskEngine  │  │ HistoryTracker   │             │
│            │ (rule-based)│  │ (SQLite)         │             │
│            └─────────────┘  └──────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

**Execution Modes:**
- **Manual:** User picks lenses → base → selected lenses → arbiter
- **Hybrid:** base → auto_detect → user + auto lenses → arbiter
- **Auto:** base → auto_detect → all relevant lenses → arbiter

---

## 2. Top-12 Risk Map

### Correctness (C)

| # | Risk | Severity | Files | Status |
|---|------|----------|-------|--------|
| C-1 | No response schema validation in bridge — malformed backend response renders partial/broken verdict cards | MEDIUM | `app/scripts/bridge/analystBridge.js` | Open |
| C-2 | Double-retry potential — `llm_client.py` retry + `execution_router.py` error handling could re-invoke failed calls | MEDIUM | `ai_analyst/core/llm_client.py`, `ai_analyst/core/execution_router.py` | Needs verification |
| C-3 | JSON extractor regex fallback could extract wrong JSON block when LLM outputs multiple structures | LOW | `ai_analyst/core/json_extractor.py` | Open |

### Security (S)

| # | Risk | Severity | Files | Status |
|---|------|----------|-------|--------|
| S-1 | Image size limit defined but NOT enforced — OOM attack vector | HIGH | `ai_analyst/api/main.py` | Open (flagged in prior audit) |
| S-2 | Subprocess stderr leaked to client — internal path exposure | MEDIUM | `services/claude_code_api/app.py` | Fix merged (commit 2d4fa9c) |
| S-3 | Rate limiter in-process only — resets on restart, no multi-worker support | MEDIUM | `ai_analyst/api/main.py` | Known; documented |

### Developer Experience (DX)

| # | Risk | Severity | Files | Status |
|---|------|----------|-------|--------|
| DX-1 | ~30% of functions lack type hints — makes IDE navigation and refactoring harder | LOW | Various across `ai_analyst/core/` | Open |
| DX-2 | `ExecutionRouter.route_analysis` exceeds 100 lines — hard to test/reason about | LOW | `ai_analyst/core/execution_router.py` | Open |

### Maintainability (M)

| # | Risk | Severity | Files | Status |
|---|------|----------|-------|--------|
| M-1 | Schema version drift — JS schemas (`app/scripts/schema/`) and Python models (`ai_analyst/models/`) have no automated sync | MEDIUM | `app/scripts/schema/`, `docs/schema/`, `ai_analyst/models/` | Open |
| M-2 | No idempotency key — bridge retry runs (and bills) a full duplicate analysis | LOW | `ai_analyst/api/main.py`, `app/scripts/bridge/analystBridge.js` | Open |

### Release / Operations (R)

| # | Risk | Severity | Files | Status |
|---|------|----------|-------|--------|
| R-1 | No true integration tests — 806 tests are all unit-level; no UI→API→pipeline→response chain test | HIGH | `ai_analyst/tests/`, `tests/` | Open |
| R-2 | SQLite history tracker not replication-capable — single point of failure in production | MEDIUM | `macro_risk_officer/history/tracker.py` | Known; documented |

---

## 3. Concrete Audit Sequence for Audits 1–4 (File-Level Rationale)

### Audit 2 — G11 Bridge → G12 UI Integration Readiness

**Rationale:** R-1 (no integration tests) is the highest-impact operational risk. The bridge is the single point of connection between the two halves of the system. Validating this first ensures the system works end-to-end before auditing deeper layers.

**File-level scope:**
| File | Audit Action |
|------|-------------|
| `app/scripts/bridge/analystBridge.js` | Trace request construction; verify error handling for all failure modes; check response parsing robustness |
| `ai_analyst/api/main.py` | Trace `/analyse` handler; verify input validation → `GroundTruthPacket` build → pipeline invocation → response serialization |
| `app/scripts/formHandler.js` | Verify form data matches expected API contract |
| `app/scripts/state/appState.js` | Verify verdict storage after bridge response |
| `ai_analyst/core/execution_router.py` | Trace route_analysis entry/exit; verify response shape matches bridge expectations |
| `ai_analyst/tests/test_pipeline_integration.py` | Assess existing integration coverage; identify gaps |
| New: integration tests | Add happy-path, API-down, schema-mismatch tests |

### Audit 1 — Schema + Contract Governance

**Rationale:** M-1 (schema drift) undermines every export/import/validation path. Must be verified before trusting pipeline outputs in Audit 3.

**File-level scope:**
| File | Audit Action |
|------|-------------|
| `docs/schema/ticket.schema.json` | Authoritative ticket schema — verify all fields, types, enums |
| `docs/schema/aar.schema.json` | Authoritative AAR schema — verify structure |
| `docs/schema/enums.json` | Shared enums — verify used consistently across JS + Python |
| `app/scripts/schema/ticketSchema.js` | Compare field-by-field against `ticket.schema.json` |
| `app/scripts/schema/aarSchema.js` | Compare field-by-field against `aar.schema.json` |
| `app/scripts/schema/schemaValidator.js` | Verify validation logic covers required fields, types, enums |
| `app/scripts/exports/ticketExporter.js` | Verify validates before export |
| `app/scripts/exports/importHandler.js` | Verify validates before import + migration |
| `ai_analyst/models/ground_truth.py` | Verify Pydantic model matches ticket schema contract |
| `ai_analyst/models/arbiter_output.py` | Verify output model matches expected response shape |
| `ai_analyst/tests/test_schema_round_trip.py` | Verify round-trip tests cover JS↔Python boundary |

### Audit 3 — LLM Execution Correctness + Observability

**Rationale:** Depends on schema/contract understanding from Audit 1. The pipeline is the core value — must verify execution correctness per mode.

**File-level scope:**
| File | Audit Action |
|------|-------------|
| `ai_analyst/graph/pipeline.py` | Verify node ordering, conditional edges, mode branching |
| `ai_analyst/graph/state.py` | Verify PipelineState shape; check for mutation risks |
| `ai_analyst/graph/analyst_nodes.py` | Verify base → auto_detect → lenses sequence contracts |
| `ai_analyst/graph/arbiter_node.py` | Verify arbiter receives all expected inputs per mode |
| `ai_analyst/core/execution_router.py` | Verify mode routing logic; check for double-retry (C-2) |
| `ai_analyst/core/llm_client.py` | Verify retry ownership is single; check idempotency |
| `ai_analyst/core/usage_meter.py` | Verify cost ceiling enforcement works mid-run |
| `ai_analyst/core/json_extractor.py` | Verify extraction robustness (C-3) |
| `ai_analyst/graph/logging_node.py` | Verify correlation ID propagation; check log completeness |
| `ai_analyst/tests/test_langgraph_async_integration.py` | Assess sequencing test coverage |
| `ai_analyst/tests/test_execution_router_arbiter.py` | Assess mode-specific test coverage |
| Deliverable | Execution truth table per mode |

### Audit 4 — Security + Secrets + Supply Chain

**Rationale:** Capstone audit — benefits from full system understanding built in Audits 0–3. Covers all trust boundaries.

**File-level scope:**
| File | Audit Action |
|------|-------------|
| `ai_analyst/api/main.py` | Fix S-1 (image size enforcement); verify CORS config; audit all endpoints |
| `ai_analyst/core/api_key_manager.py` | Verify no key logging; check rotation support |
| `ai_analyst/core/logger.py` | Verify no secrets in structured logs |
| `.github/workflows/ci.yml` | Verify pip-audit runs; check for secret leaks in CI |
| `Dockerfile` | Verify non-root, read-only fs, minimal image |
| `docker-compose*.yml` | Verify network isolation, env var handling |
| `ai_analyst/.env.example` | Verify no real secrets committed |
| `services/claude_code_api/app.py` | Verify S-2 fix (stderr sanitization) holds |
| `ai_analyst/core/prompt_pack_generator.py` | Check prompt injection surface in user-supplied fields |
| `ai_analyst/requirements.txt` | Dependency risk review |
| Deliverable | Threat model with trust boundaries + severity-ranked findings |

---

## 4. Cross-Reference with Prior Audit (2026-03-05b)

| Prior Finding | Status | Addressed In |
|---------------|--------|-------------|
| HIGH-1: Image size not enforced | **Still open** | Audit 4 (S-1) |
| MEDIUM-1: Rate limiter not distributed | Known limitation | Noted; not in audit scope (infra) |
| MEDIUM-2: Subprocess stderr leak | **Fixed** | Commit 2d4fa9c |
| MEDIUM-3: Missing integration tests | **Still open** | Audit 2 (R-1) |
| MEDIUM-4: MRO cache not shared | Known limitation | Noted; not in audit scope (infra) |
| LOW-1: Missing type hints | Open | DX-1 noted; not blocking |
| LOW-2: Long functions | Open | DX-2 noted; not blocking |
| LOW-3: Feeder polling undocumented | Open | Low priority |
