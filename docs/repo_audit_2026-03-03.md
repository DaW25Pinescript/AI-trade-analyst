# Repository Audit Report — 2026-03-03

## Scope

Full-codebase audit covering security, code quality, test coverage, dependencies, CI pipeline,
and architecture. Performed against the `claude/audit-repo-ykQHJ` branch (post MRO-P4 / G11 merge).

## Methodology

- Static analysis of all Python and JavaScript source files
- Review of CI/CD workflow, Dockerfile, docker-compose, Makefile
- Review of .gitignore, .env handling, and CORS configuration
- Review of SQL query patterns, LLM output handling, and input validation
- Review of test suite coverage and previous audit reports

---

## Security Findings

### Fixed in This Audit

| # | Severity | Location | Issue | Resolution |
|---|----------|----------|-------|------------|
| 1 | Medium | `ai_analyst/api/main.py` | CORS origins hardcoded to `localhost:8080`; not configurable for non-local deployments | Now reads `ALLOWED_ORIGINS` env var (comma-separated); falls back to localhost defaults |
| 2 | Low | `ai_analyst/api/main.py` | Generic `except Exception` handler exposed raw exception string in HTTP 500 detail, risking information leakage | Detail sanitised to generic message; stack trace stays server-side in logs |
| 3 | Low | `.github/workflows/ci.yml` | No dependency CVE scanning; known-vulnerable packages could enter undetected | Added `pip-audit` step to both `analyst-tests` and `mro-tests` jobs |
| 4 | Low | `.github/workflows/ci.yml` | `macro_risk_officer/tests` not covered by CI; MRO regressions would not surface on PRs | Added dedicated `mro-tests` job to CI |

### No Issues Found (Confirmed Safe)

- **Hardcoded secrets:** None. All API keys loaded via `os.getenv()`. `.env` excluded from git.
- **SQL injection:** All SQLite queries use parameterized statements (`?` placeholders). No string interpolation in SQL.
- **Code injection:** No `eval`, `exec`, `pickle.loads`, or `subprocess` with untrusted input.
- **XSS:** `textContent` used (not `innerHTML`) for user-controlled content. LocalStorage values validated via schema before rendering.
- **LLM output trust:** All LLM responses parsed through Pydantic models before use; unstructured text never executed.
- **File uploads:** Uploaded images read as bytes and base64-encoded only; no shell execution or filesystem write of user content.
- **CORS method scope:** Only `GET` and `POST` allowed.

---

## Code Quality

### Strengths

- Consistent async/await patterns throughout Python (LangGraph, FastAPI, LiteLLM).
- Pydantic v2 models with `frozen=True` on `GroundTruthPacket` prevent accidental mutation.
- Retry logic with exponential backoff in both Python (`llm_client.py`) and JavaScript (`api_bridge.js`).
- Graceful degradation: MRO failures never block chart analysis pipeline.
- Schema versioning: Ticket v4.0.0, AAR v1.0.0, with migration support in browser state.
- `yfinance` declared as soft dependency in MRO; `YFinanceClient` fails gracefully when absent.

### Minor Notes (No Action Required)

- `storage_indexeddb.js` is a forward stub that delegates to localStorage. Comment explains this is intentional; no regression risk.
- `lens_classical`, `lens_harmonic`, `lens_volume_profile` are hardcoded `false` in `api_bridge.js`. This is intentional per current lens configuration; no bug.

---

## Test Coverage

| Suite | Tests | Pass | Fail | Skip |
|-------|-------|------|------|------|
| Browser (Node `--test`) | 105 | 105 | 0 | 0 |
| AI Analyst (pytest) | 256 | 256 | 0 | 0 |
| Macro Risk Officer (pytest) | 169 | 153 | 0 | 16 |
| **Total** | **530** | **514** | **0** | **16** |

MRO skips are by design (require `MRO_SMOKE_TESTS=1` env flag for live API calls).

---

## CI/CD Changes

### Before

```
browser-tests  — node --test tests/*.js
analyst-tests  — pytest -q ai_analyst/tests
```

### After

```
browser-tests  — node --test tests/*.js
analyst-tests  — pip-audit -r ai_analyst/requirements.txt
               — pytest -q ai_analyst/tests
mro-tests      — pip-audit -r macro_risk_officer/requirements.txt
               — pytest -q macro_risk_officer/tests
```

---

## Dependency Review

### Python (ai_analyst)

| Package | Version Constraint | Status |
|---------|-------------------|--------|
| langgraph | ≥0.2.0 | Current |
| litellm | ≥1.35.0 | Current |
| pydantic | ≥2.5.0 | Current (v2) |
| fastapi | ≥0.110.0 | Current |
| uvicorn[standard] | ≥0.27.0 | Current |
| python-multipart | ≥0.0.9 | Current |
| typer | ≥0.12.0 | Current |
| python-dotenv | ≥1.0.0 | Current |
| pytest | ≥8.0.0 | Current |
| pytest-asyncio | ≥0.23.0 | Current |

### Python (macro_risk_officer)

| Package | Version Constraint | Status |
|---------|-------------------|--------|
| httpx | ≥0.27.0 | Current |
| pyyaml | ≥6.0 | Current |
| pydantic | ≥2.5.0 | Shared with ai_analyst |
| yfinance | ≥0.2.40 | Soft dependency |
| pytest | ≥8.0.0 | Current |

No pinned versions with known CVEs detected. `pip-audit` now runs in CI to catch future regressions.

---

## Architecture Assessment

The two-subsystem split (static browser app + Python AI pipeline) is clean and well-maintained:

- Browser app is fully self-contained (no server required for ticket management).
- Python pipeline is independently testable (CLI + FastAPI).
- MRO is an opt-in advisory layer with zero impact on pipeline stability when unavailable.
- LangGraph node graph is auditable: each node logs its output before passing state downstream.
- Lens-aware screenshot architecture (3 clean + 1 optional overlay) is enforced at both the API
  boundary (Pydantic) and within `GroundTruthPacket`.

---

## Production Readiness

| Area | Score | Notes |
|------|-------|-------|
| Security | 9/10 | No critical issues; CORS + error leak fixed |
| Code Quality | 9/10 | Strong patterns, immutable models, retry logic |
| Test Coverage | 8.5/10 | 514 passing; MRO now in CI |
| Documentation | 9/10 | Comprehensive READMEs, schema docs, runbooks |
| Dependency Health | 8/10 | pip-audit now gates PRs |
| Deployment | 8/10 | Docker Compose ready; CORS env-var now configurable |
| **Overall** | **8.5/10** | Production-ready with fixes applied |

---

## Recommendations (Remaining / Future Work)

| Priority | Item |
|----------|------|
| Medium | Add `SECURITY.md` with deployment hardening guide (HTTPS, reverse-proxy, rate limiting for `/analyse`) |
| Medium | Add `pytest-cov` + coverage threshold gate to CI (currently no minimum enforced) |
| Low | Consider structured JSON logging in Python pipeline for easier audit ingestion |
| Low | Evaluate TypeScript migration for browser app as codebase grows beyond G12 |
| Low | Expose API timeout (currently 12 s) as a configurable UI setting in the bridge panel |

---

## Files Changed

| File | Change |
|------|--------|
| `ai_analyst/api/main.py` | CORS configurable via `ALLOWED_ORIGINS` env var; 500 detail sanitised |
| `.github/workflows/ci.yml` | Added `mro-tests` job; added `pip-audit` to both Python jobs |
| `docs/repo_audit_2026-03-03.md` | This report |
