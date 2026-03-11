# Repository Audit Report — 2026-03-04

## Scope

Closed the two remaining **Medium** items from the 2026-03-03 audit:

1. `pytest-cov` + coverage threshold gate in CI (previously "no minimum enforced")
2. `SECURITY.md` deployment hardening guide (previously absent)

---

## Changes Made

### 1. pytest-cov coverage gate

**Problem:** CI ran tests but enforced no minimum coverage threshold. A regression
that dropped coverage to 0% would pass CI silently.

**Fix:**

- Added `pytest-cov>=4.0.0` to `ai_analyst/requirements.txt` and
  `macro_risk_officer/requirements.txt`.
- Updated `.github/workflows/ci.yml`:
  - `analyst-tests` job: `pytest --cov=ai_analyst --cov-report=term-missing --cov-fail-under=70`
  - `mro-tests` job: `pytest --cov=macro_risk_officer --cov-report=term-missing --cov-fail-under=70`

Threshold set at **70%** — conservative enough not to break CI against the
existing test corpus (514 passing tests across a well-structured codebase),
while establishing a hard floor that prevents future regressions from going
undetected. Raise to 80%+ once a baseline measurement is confirmed on CI.

### 2. SECURITY.md

**Problem:** No documented hardening guide existed for operators deploying
beyond localhost.

**Fix:** Created `SECURITY.md` at the repo root covering:

| Section | Content |
|---------|---------|
| HTTPS | Caddy + nginx TLS reverse proxy examples; bind ports to 127.0.0.1 |
| CORS | `ALLOWED_ORIGINS` env var usage |
| Rate limiting | In-app sliding window + nginx `limit_req_zone` for multi-worker |
| API keys | `.env` pattern, secret manager recommendation for production |
| Cost ceiling | `MAX_COST_PER_RUN_USD` env var |
| Image size cap | `MAX_IMAGE_SIZE_MB` env var |
| Static server | Replace `python -m http.server` with nginx for production |
| Docker hardening | Non-root user, `no-new-privileges`, `read_only`, tmpfs |
| Network isolation | Internal Docker network, proxy-only external exposure |
| CVE scanning | `pip-audit` CI gate + local usage |
| Vulnerability reporting | Process for disclosing security issues |

---

## Files Changed

| File | Change |
|------|--------|
| `ai_analyst/requirements.txt` | Added `pytest-cov>=4.0.0` |
| `macro_risk_officer/requirements.txt` | Added `pytest-cov>=4.0.0` |
| `.github/workflows/ci.yml` | Added `--cov --cov-fail-under=70` to both pytest jobs |
| `SECURITY.md` | New file — deployment hardening guide |
| `docs/repo_audit_2026-03-04.md` | This report |

---

## Remaining Recommendations (from 2026-03-03 audit)

| Priority | Item | Status |
|----------|------|--------|
| Low | Structured JSON logging in Python pipeline | Open |
| Low | Evaluate TypeScript migration for browser app | Open |
| Low | Expose API timeout (12 s) as configurable UI setting | Open |

MRO Phase 4 — the remaining open items (opt-in live-source smoke CI path,
KPI definitions for availability/freshness) remain tracked in
`docs/MRO_PHASE4_PROGRESS_2026-03-02.md`.
