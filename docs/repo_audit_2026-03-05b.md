# Repository Audit — 2026-03-05 (Session Audit)

**Auditor:** Claude Code
**Date:** 2026-03-05
**Scope:** Full codebase — security, code quality, architecture, testing, operational readiness

---

## Executive Summary

The AI Trade Analyst is a well-engineered, actively maintained codebase combining a static browser trade-management app and a Python multi-model LLM pipeline. With 514 passing tests, thorough documentation, and professional security practices, it is **near production-ready** — but requires one critical bug fix and operational hardening before live deployment.

**Verdict: PRODUCTION-READY with Caveats**

---

## Overall Ratings

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Code Quality | 7/10 | Solid architecture; ~30% of functions lack type hints |
| Security | 8/10 | Good defaults; image validation bug present |
| Test Coverage | 8/10 | 514 passing; 70%+ CI-enforced; integration tests limited |
| Documentation | 9/10 | Excellent README, SECURITY.md, architecture docs |
| Operational Readiness | 6/10 | Not hardened out-of-box; manual setup required |
| Scalability | 6/10 | Single-process assumptions; Redis/PG guidance only |

---

## Critical Issues

### HIGH-1: Image Size Limit Not Enforced
- **File:** `ai_analyst/api/main.py`
- **Issue:** `_MAX_IMAGE_BYTES` is defined but never checked in the `/analyse` endpoint
- **Risk:** OOM attack via oversized image uploads
- **Fix:**
  ```python
  for upload in [chart_h4, chart_h1, chart_m15, chart_m5, chart_m15_overlay]:
      if upload and upload.size > _MAX_IMAGE_BYTES:
          raise HTTPException(413, f"Image exceeds size limit")
  ```

---

## Medium Priority Issues

### MEDIUM-1: Rate Limiter Not Distributed
- **Issue:** In-process sliding-window limiter resets on restart; doesn't work across multiple workers
- **Recommendation:** Use Redis with sliding-window counters; fallback to in-process if Redis unavailable
- **Note:** Already documented in SECURITY.md §3; add more prominent warning to API docs

### MEDIUM-2: Subprocess stderr Leakage
- **File:** `services/claude_code_api/app.py:60-62`
- **Issue:** Raw stderr returned to client — can expose internal paths
- **Fix:** Log stderr internally; return generic error message to client

### MEDIUM-3: Missing Integration Tests
- **Issue:** All 514 tests are unit-level; no end-to-end pipeline test with mocked LLMs
- **Recommendation:** Add integration test: `validate_input → analyst_nodes → arbiter → FinalVerdict`

### MEDIUM-4: MRO Cache Not Shared Across Workers
- **Issue:** Per-process TTL cache means multiple workers each independently hit external APIs
- **Recommendation:** Redis cache layer for macro context; fallback to per-process if Redis unavailable

---

## Low Priority Issues

### LOW-1: Missing Type Hints (~30% of functions)
- Run `mypy --strict` in CI; migrate incrementally
- Examples: `ai_analyst/core/prompt_pack_generator.py`

### LOW-2: Long Functions
- `ExecutionRouter.route_analysis` exceeds 100 lines
- Recommend splitting into smaller, testable helpers

### LOW-3: Feeder Polling Not Documented
- Default staleness threshold (3600s) not clearly documented
- Add expected polling interval to MRO_RUNBOOK.md

---

## Security Assessment

### Strengths
- No hardcoded secrets — all API keys via environment variables
- Parameterized SQL queries in `macro_risk_officer/history/tracker.py` — no SQL injection risk
- CORS whitelist (localhost:8080 by default)
- `pip-audit` CVE scanning on every PR (`ci.yml`)
- SECURITY.md covers 10 production hardening steps
- Async LLM calls with 45s timeouts and exponential backoff
- `MAX_COST_PER_RUN_USD` ceiling prevents runaway spend

### Concerns

| Risk | Severity | Status |
|------|----------|--------|
| Image size not validated in `/analyse` | HIGH | Bug — fix required |
| Rate limiter not distributed | MEDIUM | Known; documented |
| subprocess stderr leaked to client | MEDIUM | Low risk; should sanitize |
| API keys in `.env` files | LOW | Gitignored; use secrets manager for prod |
| HTTP by default (no TLS) | HIGH by design | Documented — requires reverse proxy |

---

## Architecture Highlights

**Strengths:**
- Immutable `GroundTruthPacket` (frozen Pydantic) prevents mutation bugs
- LangGraph orchestration with explicit node boundaries
- Multi-provider LLM support (Claude, GPT-4o, Gemini, Grok) via LiteLLM
- Structured logging with correlation IDs (Phase 3)
- Parallel macro_context + chart_setup (Phase 4 performance)
- Schema versioning on ticket/AAR exports

**Improvement Areas:**
- No Prometheus-format metrics export (only structured logs)
- No alerting integration (Slack/PagerDuty)
- SQLite outcome tracking not replication-capable

---

## Production Deployment Checklist

- [ ] **Fix image size validation in `/analyse` endpoint** (CRITICAL)
- [ ] Configure HTTPS reverse proxy (nginx or Caddy)
- [ ] Set `ALLOWED_ORIGINS` to production domain
- [ ] Run containers as non-root with read-only filesystem
- [ ] Set `MAX_COST_PER_RUN_USD` ceiling
- [ ] Enable structured audit logging (all POST /analyse)
- [ ] Rotate API keys monthly (Anthropic, OpenAI, Google, xAI)
- [ ] Test MRO failover (degraded-mode path)
- [ ] Test LLM timeout / retry scenarios
- [ ] Document expected feeder polling interval in runbook

---

## Recommendations Summary

### Fix Immediately
1. Add image size check in `ai_analyst/api/main.py` (see fix above)

### Next Sprint
2. Sanitize subprocess stderr in `services/claude_code_api/app.py`
3. Add `mypy` to CI; enforce type hints incrementally
4. Write one integration test for full pipeline (mocked LLMs)

### Next Quarter
5. Distributed rate limiting via Redis
6. Prometheus `/metrics` endpoint
7. Migrate SQLite outcome DB to PostgreSQL for HA

---

## Codebase Statistics

- Python source: ~16,623 lines
- JavaScript source: ~4,902 lines
- Test files: 22
- Tests passing: 514 (0 failing)
- CI coverage: 70%+ enforced
- Recent commits: 105+ PRs, active development
