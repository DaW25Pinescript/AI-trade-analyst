# Audit Programme — Full Execution Report

**Auditor:** Claude Code
**Date:** 2026-03-05
**Scope:** Audits 0–4 as defined in V3 Master Plan Stage 1

---

## Programme Summary

| Audit | Status | New Tests | Findings |
|-------|--------|-----------|----------|
| Audit 0 — Repo Orientation + Risk Map | **COMPLETE** | 0 (no-code) | 12-risk map delivered |
| Audit 2 — G11 Bridge → G12 Integration | **COMPLETE** | 19 JS tests | 1 design finding (retry on 422) |
| Audit 1 — Schema + Contract Governance | **COMPLETE** | 16 JS tests | Zero enum drift; contracts aligned |
| Audit 3 — LLM Execution Correctness | **COMPLETE** | 10 Python tests | Execution truth table verified; single retry ownership confirmed |
| Audit 4 — Security + Secrets + Supply Chain | **COMPLETE** | 0 (analysis) | 16 findings (3 CRIT, 5 HIGH, 5 MED, 3 LOW) |

**Total new tests:** 45 (19 + 16 JS bridge/contract + 10 Python execution)
**All existing tests pass:** 218 JS + 460 Python (4 pre-existing Phase 5 failures unrelated)

---

## Audit 0 — Repo Orientation + Risk Map

**Deliverables:** See `docs/audit_0_orientation_risk_map.md`
- Architecture sketch: `app ↔ bridge ↔ FastAPI ↔ LangGraph pipeline ↔ MRO`
- Top-12 risk map (Correctness: 3, Security: 3, DX: 2, Maintainability: 2, Release: 2)
- Concrete file-level audit sequence for Audits 1–4

**Key observation:** Prior audit finding S-1 (image size not enforced) has been **resolved** — `_read_upload_bounded()` streams in 64KB chunks and raises 413 on overflow.

---

## Audit 2 — G11 Bridge → G12 UI Integration Readiness

**Test file:** `tests/test_audit2_bridge_integration.js` (19 tests)

**Coverage:**
- Happy-path: valid v2.0 envelope with all fields → correct extraction
- API unreachable: network error, timeout, retries exhausted → proper propagation
- Schema mismatch: missing verdict, empty response, unexpected shape → no crash
- HTTP error codes: 422 (with audit finding), 429 (retried), 500 (retried)
- Response envelope invariants: usage_summary, run_id always present
- Health check: unreachable + degraded → proper error
- Form contract: required API fields, boolean lens fields, JSON timeframes array

**Audit Finding:**
- **BRIDGE-1 (LOW):** `postAnalyseWithOptions` retries non-retriable HTTP errors (e.g., 422) because the `throw` inside the try block is caught by the generic `catch` block which also retries. Low risk — 422 will fail identically on retry — but wastes 2 extra roundtrips.

**Integration Map:**
```
UI form → formHandler → buildAnalyseFormData() → POST /analyse (FormData)
  → FastAPI: rate_limit → parse JSON fields → build charts dict → GroundTruthPacket
  → graph.ainvoke(initial_state) → FinalVerdict → build_ticket_draft()
  → AnalysisResponse envelope → bridge: response.json() → UI verdict cards
```

---

## Audit 1 — Schema + Contract Governance

**Test file:** `tests/test_audit1_contract_governance.js` (16 tests)

**Findings:**
- **Zero enum drift** across all 34 enums between `docs/schema/`, `enums.json`, and `backup_validation.js`
- Python `ticket_draft.py` outputs (`decisionMode`, `rawAIReadBias`, `gate.status`, `stop.logic`, `targets[].label`, `conviction`) are all valid schema enum values
- Screenshot architecture contract: cleanCharts timeframes match `ALLOWED_CLEAN_TIMEFRAMES`; overlay bound to M15/ICT
- Schema versions enforced: ticket 4.0.0, AAR 1.0.0

**Contract Matrix:**
| Artifact | Producer | Consumer | Validation | Status |
|----------|----------|----------|------------|--------|
| Ticket schema | docs/schema/ticket.schema.json | backup_validation.js | 60+ fields validated | ALIGNED |
| AAR schema | docs/schema/aar.schema.json | backup_validation.js | 17 fields validated | ALIGNED |
| Enum reference | docs/schema/enums.json | UI dropdowns, validation | 34 enums, bidirectional checks | ALIGNED |
| ticket_draft | Python build_ticket_draft() | JS form pre-population | Partial (marked `_draft: True`) | BY DESIGN |
| FinalVerdict | Python arbiter | JS bridge | Pydantic model, Literal types | ALIGNED |

---

## Audit 3 — LLM Execution Correctness + Observability

**Test file:** `ai_analyst/tests/test_audit3_execution_correctness.py` (10 tests)

**Execution Truth Table (verified by tests):**

| enable_deliberation | m15_overlay | Node sequence after lenses |
|---|---|---|
| False | None | arbiter → pinekraft → logging |
| False | Present | overlay → arbiter → pinekraft → logging |
| True | None | deliberation → arbiter → pinekraft → logging |
| True | Present | deliberation → overlay → arbiter → pinekraft → logging |

All 4 rows verified by dedicated async pipeline tests.

**Key Findings:**
- **Retry ownership: SINGLE-OWNED** — `acompletion_metered` routes to either `acompletion_with_retry` OR `acompletion_with_fallback`, never both. No double-retry risk.
- **Mode determinism: CONFIRMED** — Routing functions `_route_after_phase1` and `_route_after_deliberation` are pure functions of `enable_deliberation` and `m15_overlay`.
- **Idempotency: NOT SAFE for replay** — LLM temperature=0.1 reduces but doesn't eliminate variance; macro context cache TTL means different data on replay.
- **Parallel branches: CONFLICT-FREE** — `macro_context` and `chart_setup` write to different state keys; LangGraph fan-in merges without conflict.

**Architecture Note:** `ExecutionRouter` (CLI path) and LangGraph pipeline (service path) are separate execution paths. The arbiter prompt is built with slightly different parameters in each path (e.g., `overlay_delta_reports` always empty in ExecutionRouter). This is documented as intentional but increases maintenance surface.

---

## Audit 4 — Security + Secrets + Supply Chain

**Full analysis:** 16 findings across 4 severity levels.

### Critical (3)
1. **Prompt Injection** — User-supplied fields (instrument, session, market_regime) interpolated into LLM prompts without sanitization. Validate with regex/enum.
2. **API Key Exposure Risk** — Exception messages and subprocess stderr may contain API keys if external services echo them. Sanitize error logging.
3. **CORS HTTP Default** — Default origins include `http://localhost:8080`. Safe for dev but no enforcement of HTTPS in production ALLOWED_ORIGINS.

### High (5)
4. **Subprocess Input** — No prompt length or structure validation in Claude Code API service.
5. **Rate Limiter In-Process** — Known; not distributed across workers. Documented.
6. **No File Type Validation** — Uploads accept any file type; should check PNG/JPEG magic bytes.
7. **Feeder JSON Not Schema-Validated** — `/feeder/ingest` accepts arbitrary JSON before processing.
8. **Error Response Info Disclosure** — FastAPI validation errors reveal internal field names.

### Medium (5)
9. Dependencies not pinned to exact versions (use `>=`).
10. No log masking configuration for sensitive fields.
11. No security headers at application level (relies on reverse proxy).
12. API key availability changes not logged/alerted.
13. Dev docker-compose mounts entire repo as volume.

### Low (3)
14. Git history may contain stale secrets.
15. Static file server (dev) has no security headers.
16. Pre-commit secret detection hook not configured.

### Positive Controls Confirmed
- API keys from environment only (never hardcoded)
- `.env` in `.gitignore`
- `pip-audit` in CI
- Pydantic validation on all models
- Docker: non-root user, read-only FS in prod
- Comprehensive SECURITY.md
- Cost ceiling per run (`MAX_COST_PER_RUN_USD`)
- Image upload size bounded via streaming validation (`_read_upload_bounded`)

---

## Recommendations — Prioritized

### Immediate (before next release)
1. Add input validation for prompt-embedded fields (instrument regex, session/regime enums)
2. Sanitize error messages — strip potential API keys from logged exceptions
3. Add PNG/JPEG magic-byte validation for uploaded chart images

### Next Sprint
4. Pin dependencies to exact versions (`pip-compile`)
5. Add structured logging configuration with field masking
6. Add `/health` endpoint reporting analyst model availability

### Backlog
7. Redis-backed rate limiter for multi-worker deployments
8. Add `detect-secrets` pre-commit hook
9. Security headers middleware (HSTS, X-Content-Type-Options)
