# AI Trade Analyst — Security/API Hardening Spec

## Header block
- **Status:** ✅ Complete — 10 March 2026
- **Date:** 10 March 2026
- **Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
- **Follows:** Operationalise Phase 2 closure + TD-1 arbiter contract fix
- **Debt register:** TD-2 (`call_llm` safeguards) is in-scope for this phase

## 1. Purpose

This phase follows the closure of Operationalise Phase 2 and answers the next real blocking question:

**Can the production-facing analysis path be hardened so that API misuse, oversized inputs, provider stalls, and malformed LLM behavior fail safely and observably — without redesigning the product or introducing platform complexity?**

### Moves FROM → TO
- **From:** operational scheduler/runtime is stable, but the analysis edge and LLM call path still rely on implicit trust and minimal operational safeguards.
- **To:** the `/analyse` edge and `call_llm()` path have explicit guardrails, deterministic failure handling, and resilience tests that make the system safer to run and safer to change.

## 2. Scope

### In scope
- `/analyse` request hardening
- Request/body/file guardrails
- Error-surface policy for API responses (including stream-specific error framing)
- Server-side timeout policy for analysis execution
- `call_llm()` timeout / retry / bounded failure behavior (resolves TD-2)
- Resilience tests for provider failure modes
- Production security checklist document (TLS expectations, key management, rate-limit tuning, spend limits)
- Narrow docs/spec/progress updates required to close the phase
- TD-2 resolution and debt register update

### Target components

| Component | Target |
|---|---|
| API edge | `/analyse` and `/analyse/stream` and closely related analysis request path(s) |
| Analyst runtime | `analyst/analyst.py` `call_llm()` path |
| Tests | API edge tests + LLM resilience tests |
| Docs | Specs index + progress plan + this phase spec + production security checklist |

### Out of scope
- No account system or user-management redesign
- No OAuth, SSO, RBAC, or multi-tenant auth layer
- No deployment platform work (Docker/K8s/systemd/cloud infra)
- No API gateway or reverse proxy infrastructure
- No distributed rate limiting or cache layer
- No notifier transport work
- No scheduler/runtime redesign
- No MarketPacket/officer contract change
- No UI redesign
- No broad packaging refactor
- No SQLite or database layer introduced
- No new top-level module

If implementation reveals an out-of-scope item is required for correctness, stop and flag it before coding continues.

## 3. Repo-Aligned Assumptions

| Area | Assumption |
|---|---|
| API edge | `/analyse` is the production-facing risk surface that needs explicit guardrails |
| Analyst runtime | `call_llm()` is currently a thin provider wrapper and is the right place for timeout/retry/circuit-breaker style safeguards |
| Tests | Existing analyst tests mock `call_llm()` heavily; resilience coverage likely needs to be added rather than inferred |
| Scope discipline | The smallest safe next phase is API edge + LLM runtime hardening, not a generic cleanup sweep |
| Stream surface | `/analyse/stream` may have different error framing (SSE events vs JSON responses) — diagnostic should confirm whether they need different treatment |

### Current likely state

The analyst call path currently selects a model from `ANALYST_LLM_MODEL`, tries `litellm.completion(...)`, then falls back to `openai.OpenAI().chat.completions.create(...)`, but the visible implementation does not include explicit timeout, retry, or circuit-breaker behavior.

The `/analyse` endpoint already has meaningful input-side hardening:
- Input sanitisation before prompt use (instrument, session, regime, news, open positions, no-trade windows)
- Per-image bounded upload + magic-byte validation with 413/422 responses
- Screenshot count limit via Pydantic model validation
- In-process sliding-window rate limiting
- CORS + production HTTPS-origin filtering + security headers middleware
- Secret masking in logged errors and sanitised feeder error logging

The gaps are concentrated on four surfaces: auth, timeout, error contracts, and global body limits. Existing analyst verdict tests emphasize mocked happy-path schema validation and hard-constraint enforcement — provider failure modes such as timeout, malformed payload, or transient transport failure likely remain under-covered.

A reference implementation exists: `services/claude_code_api` already has `X-API-Key` enforcement and timeout controls.

### Core question

Can we harden `/analyse` and `call_llm()` with explicit guardrails and deterministic tests **without** introducing a full auth platform, provider abstraction rewrite, or deployment project?

## 4. Key File Paths

| Role | Path | Notes |
|---|---|---|
| API request handling | `ai_analyst/api/main.py` | Primary change surface — hosts `/analyse`, `/analyse/stream`, middleware |
| Analyst LLM path | `analyst/analyst.py` | TD-2 timeout/retry target — `call_llm()` |
| Existing auth pattern | `services/claude_code_api` | Reference implementation for `X-API-Key` — read-only |
| Analyst verdict/resilience tests | `tests/test_analyst_verdict.py` | Likely test target |
| AI analyst tests | `ai_analyst/tests/` | Primary test target |
| Node tests | `tests/*.js` | Bridge/contract tests — regression check |
| Arbiter tests | `tests/test_arbiter.py` | Read-only reference unless needed |
| Specs index | `docs/specs/README.md` | Update on phase closure |
| Progress plan | `docs/AI_TradeAnalyst_Progress.md` | Update on phase closure + TD-2 resolution |
| This phase spec | `docs/specs/Security_API_Hardening_Spec.md` | Phase closure |

### Read-only references
- `market_data_officer/` runtime and contracts should remain unchanged in this phase.
- PR 1/PR 2/PR 3 Operationalise outputs are dependencies, not targets.

## 5. Current State Audit Hypothesis

### What is already true
- Operationalise Phase 2 has stabilised scheduler/runtime behavior and observability at the MDO layer.
- TD-1 arbiter contract enforcement was fixed explicitly.
- `call_llm()` exists as a small contained function that is feasible to harden without touching broad pipeline logic.
- `/analyse` already has significant input-side hardening (sanitisation, bounded uploads, magic-byte checks, screenshot limits, rate limiting, CORS, security headers, secret masking).
- `services/claude_code_api` demonstrates the `X-API-Key` and timeout patterns that should inform this phase.

### What likely remains incomplete
- `/analyse` may not yet have explicit auth/authorisation policy suitable for non-local use.
- Request/body/file limits may be partial or inconsistent — file uploads are bounded, but non-file JSON/form fields may lack a global cap.
- Server-side analysis timeout policy may be implicit or absent (`graph.ainvoke` with no timeout wrapper).
- `call_llm()` likely has no timeout/retry/circuit-breaker semantics today.
- Resilience tests for provider failure modes are likely thinner than schema/hard-constraint tests.
- `/analyse/stream` error framing may differ from `/analyse` error contract — diagnostic should confirm.

### Core phase question

Can we move the analysis path from "works when healthy" to "fails safely, predictably, and testably" with one tight hardening phase?

## 6. Design — Security/API Hardening

### 6.1 Phase shape

This phase has two tightly coupled workstreams:

1. **API edge hardening** — make `/analyse` safer to call.
2. **Analyst runtime hardening** — make `call_llm()` safer to run.

These belong together because API timeouts, oversized requests, and provider stalls all surface to the same end-user analysis flow.

### 6.2 API edge hardening

The phase should establish an explicit policy for the `/analyse` edge covering:
- who may call it
- how large requests may be
- what content is accepted
- how long the server will wait
- what error detail is safe to return

#### Minimum required policy outcomes
- Explicit auth gate or trusted-local-only mode with deterministic rejection path
- Explicit request/body/file size enforcement (including a global body-size cap for non-file fields, not just per-file upload bounds)
- Explicit server-side timeout boundary for analysis execution
- Explicit sanitised error contract

#### Hypothesis table — auth approach

| Option | Starting hypothesis |
|---|---|
| Full user auth | Out of scope for this phase |
| Static/shared token gate (e.g. `X-API-Key`) | Plausible smallest safe option — matches `claude_code_api` pattern |
| Localhost / trusted-origin only | Plausible smallest safe option if current deployment model is local-first |
| No auth gate | Not acceptable for the hardened phase |

Diagnostic must confirm which smallest option fits the current repo and runtime model.

### 6.3 Analyst runtime hardening

`call_llm()` currently does direct provider calls through LiteLLM or OpenAI fallback with no visible timeout or retry semantics in the current implementation.

This phase should add:
- Explicit timeout boundary
- Bounded retry behavior for transient transport/provider failures
- Deterministic failure mapping to a safe runtime exception
- Optional simple circuit-breaker / fast-fail window **only if nearly free**

#### Timeout hypotheses (diagnostic should confirm)

| Parameter | Starting hypothesis | Notes |
|---|---|---|
| Graph execution timeout | 120 seconds | TBD by diagnostic — depends on typical graph completion time |
| LLM call timeout | 60 seconds | TBD by diagnostic — depends on provider SDK/client capabilities |
| Global body-size limit | 10 MB | TBD by diagnostic — covers non-file fields beyond existing upload bounds |

#### Required rule
`call_llm()` hardening must not alter verdict-schema validation, prompt-building logic, or MarketPacket contracts. This is transport/runtime hardening, not analyst-logic redesign.

### 6.4 Error contract policy

Errors returned to API clients should:
- Be stable enough to test
- Not leak stack traces, provider secrets, raw exception internals, or environment detail
- Preserve enough detail for operator debugging in logs

This phase should distinguish:
- **Client-facing error contract** — safe, consistent, no internals
- **Operator/internal log detail** — full error context, secret-masked (existing behavior preserved)

Stream-specific note: `/analyse/stream` currently emits raw `str(exc)` for `RuntimeError`. The error contract must cover both the JSON response path and the SSE event path. The diagnostic should confirm whether these need different handling or can share the same safe error shape.

### 6.5 Test posture

The next tests should prioritise failure realism over broad mocking optimism.

Required additions should include deterministic tests for:
- Provider timeout (LLM call exceeds timeout boundary)
- Provider transient failure then success (bounded retry works)
- Provider hard failure after bounded retries (deterministic exception)
- Malformed / non-JSON LLM response
- API request rejection on auth policy
- API request rejection on body-size limit
- API request rejection on timeout (graph execution exceeds boundary)
- Error contract enforcement (no internal detail in client responses)
- Stream error contract enforcement (no raw `str(exc)` in SSE events)

### 6.6 Production security checklist

Create a concise security checklist document covering production deployment expectations.

Required topics:
- TLS termination expectation (not implemented by this phase, but documented as a deployment requirement)
- CORS origin configuration for production vs development
- Auth configuration and key rotation guidance
- Rate-limit tuning (current defaults, how to adjust)
- Timeout configuration (graph, LLM call)
- Request-size limit configuration
- LLM provider spend limits / budget caps (external configuration, not implemented by this phase)
- Logging and secret-masking verification

This is a documentation deliverable, not a code deliverable. Keep it concise — a checklist, not a manual. No aspirational content — describe what the system does after this phase lands.

### 6.7 Schema-only / future fields

If the phase needs internal enums or reason codes for timeout/retry/auth rejection, they may be added as implementation detail. Do not introduce external-facing versioned API contracts unless diagnostics prove it is already nearly free.

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|---|---|---|
| AC-1 | API auth policy | `/analyse` and `/analyse/stream` have an explicit deterministic access policy — rejection proven by test | ✅ Done |
| AC-2 | Request limits | Request/body/file guardrails are explicitly enforced including global body-size cap — rejection proven by test | ✅ Done |
| AC-3 | Server timeout | Analysis execution has an explicit server-side timeout boundary — timeout produces safe error response, proven by test | ✅ Done |
| AC-4 | Error contract | Client-facing errors are sanitised and deterministic — no exception detail, stack trace, or internal path leaks to client, proven by test | ✅ Done |
| AC-5 | Stream error contract | `/analyse/stream` error events use the same safe contract — no raw `str(exc)` emitted, proven by test | ✅ Done |
| AC-6 | `call_llm` timeout | `call_llm()` has an explicit timeout boundary — timeout produces deterministic exception, proven by test | ✅ Done |
| AC-7 | `call_llm` retry | `call_llm()` retries only bounded transient failures — proven by test | ✅ Done |
| AC-8 | Failure mapping | Repeated provider failure becomes a deterministic runtime exception path — proven by test | ✅ Done |
| AC-9 | Resilience tests | Timeout / malformed response / provider-down paths are covered by deterministic tests | ✅ Done |
| AC-10 | Existing hardening preserved | Input sanitisation, upload bounds, magic-byte checks, rate limiting, CORS, security headers, secret masking all remain functional | ✅ Done |
| AC-11 | Production checklist | Security checklist document exists covering TLS, CORS, auth, rate limits, timeouts, body limits, spend limits | ✅ Done |
| AC-12 | Regression safety | Existing analyst, arbiter, and bridge tests remain green — `ai_analyst/tests` at 485, `tests/*.js` at 235+ | ✅ Done |
| AC-13 | Scope discipline | No DB, no deployment project, no new top-level module, no auth-platform redesign | ✅ Done |
| AC-14 | MDO unchanged | `market_data_officer/` not modified — market-hours, alert policy, runtime config, pipeline all untouched | ✅ Done |
| AC-15 | Deterministic tests | All tests deterministic — no live LLM calls, no real network dependency | ✅ Done |
| AC-16 | TD-2 resolved | Technical Debt Register TD-2 row updated to ✅ Resolved | ✅ Done |
| AC-17 | Docs updated | Spec, specs index, progress plan, and debt register reflect the phase accurately on closure | ✅ Done |

## 8. Pre-Code Diagnostic Protocol

Do not implement until this list is reviewed.

### Step 1 — Audit `/analyse` request path
- **Run / inspect:** Locate the exact `/analyse` and `/analyse/stream` route handlers and middleware stack in `ai_analyst/api/main.py`. Confirm current auth behavior, request parsing, file/body guardrails, timeout handling, and client error mapping.
- **Expected result:** Complete map of the request lifecycle from incoming request to graph invocation to response.
- **Report:** List exact current safeguards as found / not found / partial. Note whether `/analyse` and `/analyse/stream` share error handling or diverge.

### Step 2 — Audit existing auth patterns in repo
- **Run / inspect:** Inspect `services/claude_code_api` for the `X-API-Key` implementation. Search for any other auth patterns:
  ```bash
  rg -rn "api.key\|API_KEY\|X-API-Key\|authenticate\|authorize\|Bearer" ai_analyst services tests
  ```
- **Expected result:** Confirm the existing auth pattern, whether dev-mode bypass exists, and whether it's directly reusable.
- **Report:** Auth implementation shape, env var name, bypass behavior, and reuse recommendation.

### Step 3 — Audit `call_llm()` and callers
- **Run / inspect:** Inspect `analyst/analyst.py` `call_llm()` plus the nearest callers. Trace the execution path from `/analyse` → graph invocation → LLM call.
  ```bash
  rg -rn "ainvoke\|call_llm\|acompletion\|acreate\|chat\.completions" ai_analyst analyst
  ```
- **Expected result:** Confirm exact provider call shape, timeout status, retry status, exception behavior, and underlying HTTP client or SDK used.
- **Report:** Smallest safe place to add timeout/retry without changing analyst logic. Recommended wrapping approach.

### Step 4 — Audit current error handling and response shapes
- **Run / inspect:** Inspect error handling in `/analyse` and `/analyse/stream`. Search for exception-to-response mappings:
  ```bash
  rg -rn "RuntimeError\|HTTPException\|JSONResponse\|str\(exc\)\|str\(e\)" ai_analyst/api/
  ```
- **Expected result:** Identify all paths where internal error detail reaches the client.
- **Report:** Each leakage path with file and line number, current response shape, and the specific detail that leaks.

### Step 5 — Audit current tests and coverage gaps
- **Run / inspect:** Identify the exact existing analyst/API test files covering `call_llm()`, `run_analyst_llm()`, parsing, and API edge behavior. Run baseline suites.
- **Expected result:** Green baseline. Coverage map: happy path vs malformed vs timeout vs transport failure vs access rejection.
- **Report:** Exact test counts, which failure paths are already covered, which are missing.

### Step 6 — Decide smallest auth gate
- **Run / inspect:** Compare current deployment assumptions against the smallest acceptable hardening options from the §6.2 hypothesis table.
- **Expected result:** Choose one: trusted-local-only, static token, or equivalent minimal gate.
- **Report:** Recommendation with rationale. Explicitly reject broader auth work if not required.

### Step 7 — Propose smallest patch set
- **Run / inspect:** Based on Steps 1–6. Apply the "smallest safe option" principle — if multiple approaches exist, default to the narrowest one that passes all ACs.
- **Expected result:** Smallest correct implementation surface.
- **Report:** Files, one-line descriptions, estimated line delta. Recommended timeout values. Recommended body-size limit. Any scope flags or ambiguities to resolve before coding.

Do not change any code until the diagnostic report is reviewed and approved.

## 9. Implementation Constraints

### 9.1 General rule
This phase is **edge hardening and failure containment**, not a product redesign.

### 9.1b Implementation Sequence
1. Complete Steps 1–7 diagnostic and report findings. No code changes yet.
2. Harden `/analyse` edge with the smallest acceptable access + request-limit policy.
3. **Gate 1:** verify baseline tests still pass — auth added (existing test fixtures may need API key header).
4. Harden `call_llm()` with timeout/retry/failure mapping.
5. **Gate 2:** verify baseline tests still pass.
6. Tighten error contracts: replace internal detail leakage with safe error shape in both `/analyse` and `/analyse/stream`.
7. **Gate 3:** verify baseline tests still pass — error shape changes may break existing test assertions. Update test expectations to match the new safe shape, but do not suppress or weaken test coverage.
8. Add global request-body size limit.
9. **Gate 4:** verify baseline tests still pass.
10. Add deterministic resilience tests and targeted API rejection tests from §6.5 list.
11. **Final gate:** all baselines hold plus all new tests green.
12. Write production security checklist document.
13. Close spec and update docs only after all gates are proven green.

**Never skip a gate.** Gate 3 is the highest risk — error shape changes may break existing test assertions.

### 9.2 Code change surface
Expected change surface:
- `ai_analyst/api/main.py` — auth dependency, timeout wrappers, error contract, body-size limit
- `ai_analyst/api/dependencies.py` or equivalent — auth check function (new or existing file)
- `analyst/analyst.py` — `call_llm()` timeout/retry wrapper (TD-2)
- `ai_analyst/tests/` — new hardening tests + existing test fixture updates for auth
- One or more existing analyst/API test files
- `docs/runbooks/Security_Checklist.md` or equivalent — production defaults documentation
- `docs/specs/Security_API_Hardening_Spec.md` — phase closure
- `docs/specs/README.md` — phase closure
- `docs/AI_TradeAnalyst_Progress.md` — phase closure + TD-2 resolution

No changes expected to:
- `market_data_officer/` — entire package untouched
- `ai_analyst/graph/` internals — only the invocation call site is wrapped, not the graph structure
- MarketPacket contracts
- `app/` — UI client code unless diagnostics prove a current request contract mismatch
- `services/claude_code_api` — reference only, not modified
- Deployment/platform files

If any of the above "no changes expected" items require edits, flag before proceeding.

### 9.3 Hard constraints
- `MarketPacketV2` contract locked — officer layer unchanged
- `market_data_officer/` package not modified — market-hours, alert policy, runtime config, scheduler all untouched
- Analyst graph structure unchanged — only the invocation call site is wrapped with timeout
- No full identity management system (no OAuth, no SSO, no RBAC, no user database)
- No API gateway or reverse proxy infrastructure
- No distributed rate limiting or cache layer
- No SQLite or database layer introduced
- Work confined to existing repo packages only — no new top-level module
- No deployment automation or cloud infrastructure work
- Deterministic fixture/mock tests are the required acceptance backbone — no live provider dependency in CI
- `call_llm()` hardening is transport/runtime only — do not redesign analyst logic
- Error contract tightening is client-facing only — server-side logging of full error detail preserved
- Client error sanitisation must be proven by deterministic tests — not assumed
- If this work resolves or partially addresses any Technical Debt Register items (§8 of progress plan), update their status

## 10. Success Definition

Security/API Hardening is done when `/analyse` and `/analyse/stream` have an explicit safe access and request-limit policy, client-facing errors are sanitised with no internal detail leakage, analysis execution cannot hang indefinitely, `call_llm()` fails within bounded and testable runtime rules, deterministic resilience tests cover the new failure paths, existing hardening remains functional, a production security checklist exists, the regression baselines hold, TD-2 is resolved in the debt register, and all of this lands without database introduction, deployment sprawl, or new top-level modules.

## 11. Why This Phase Matters

| Without this phase | With this phase |
|---|---|
| `/analyse` edge remains partially trust-based | `/analyse` edge has explicit guardrails |
| Provider stalls can translate into hidden or unstable failures | Provider failure modes are bounded and testable |
| Internal exception details leak to API clients | Error responses are safe and consistent |
| Tests mostly prove healthy mocked behavior | Tests also prove unhealthy behavior and safe failure |
| Large non-file payloads have no explicit size cap | Request size is bounded at all layers |
| No documented production security posture | Security checklist exists and is verifiable |
| TD-2 remains open | TD-2 is resolved |
| Future refactors remain risky | Future refactors become safer because failure paths are covered |

## 12. Phase Roadmap

| Phase | Scope | Status |
|---|---|---|
| Operationalise Phase 1 | APScheduler feed refresh | ✅ Done — 494 tests |
| Operationalise Phase 2 | Market-hours + alerting + runtime posture | ✅ Done — 644 tests |
| TD-1 | Arbiter assert fix | ✅ Done — micro-PR |
| **Security/API Hardening** | **`/analyse` edge + `call_llm()` safeguards** | **✅ Done — 515 tests** |
| CI Seam Hardening | Gate missing Python integration seams in CI | 🔜 Next candidate |
| Cleanup | Async marker tidy, enum centralisation (TD-5), unused vars (TD-9) | 🔜 Micro-PRs |

## 13. Diagnostic Findings

### Auth pattern chosen
`X-API-Key` header checked against `AI_ANALYST_API_KEY` env var. Reuses the `services/claude_code_api` pattern exactly. If env var is unset or empty, all `/analyse` and `/analyse/stream` requests are rejected 401. No open-by-default bypass.

### Timeout values confirmed
| Parameter | Value | Call site |
|---|---|---|
| Graph execution timeout | 120s (`GRAPH_TIMEOUT_SECONDS`) | `main.py` — `asyncio.wait_for(graph.ainvoke(...))` on both `/analyse` and `/analyse/stream` |
| LLM call timeout (`call_llm`) | 60s (`LLM_CALL_TIMEOUT_S`) | `analyst/analyst.py` — passed to `litellm.completion(timeout=)` and `openai.OpenAI(timeout=)` |
| LLM call timeout (graph pipeline) | 45s (hardcoded) | `ai_analyst/core/llm_client.py` — already hardened, not modified |

### Error leakage paths closed
| ID | Path | Fix |
|---|---|---|
| E1 | `/analyse` RuntimeError → `_mask_secrets(str(e))` leaked to client | Now returns generic `"Analysis failed. Check server logs."` |
| E4 | `/analyse/stream` RuntimeError → raw `str(exc)` in SSE event | Now returns generic `"Analysis failed. Check server logs."` |
| E2, E3 | Smoke-mode debug paths | Left as-is per diagnostic recommendation — LOW severity, not production-facing |
| E5–E9 | Validation/parse error detail | Left as-is — LOW severity, expose only standard user-input validation messages |

### Body-limit value
10 MB (`MAX_REQUEST_BODY_MB` env var). Enforced via `BodySizeLimitMiddleware` checking `Content-Length` header. Returns 413 with safe error shape.

### Retry behavior
`call_llm()` retries up to 2 times (`LLM_CALL_MAX_RETRIES`) with exponential backoff (1s, 2s, capped at 8s). Only transient/transport errors are retried (timeout, rate limit, 5xx). Non-retriable errors (auth, bad request, validation) fail immediately. All failures map to `RuntimeError` with type name only — no raw provider message in the exception.

### Two-LLM-path discovery
The diagnostic discovered two separate LLM call paths:
1. **`analyst/analyst.py:call_llm()`** — synchronous, standalone module. Was unhardened (TD-2 target). Now has timeout + retry + failure mapping.
2. **`ai_analyst/core/llm_client.py:acompletion_with_retry()`** — async, graph pipeline path. Already hardened with 45s timeout, 2 retries, non-retriable filtering, fallback model routing. Not modified.

### Test count delta
| Suite | Before | After | Delta |
|---|---|---|---|
| `ai_analyst/tests/` | 470 | 485 | +15 (security hardening tests) |
| `tests/` Python | 13 | 30 | +17 (call_llm resilience tests) |
| **Total new tests** | — | — | **+32** |

## 14. Appendix — Recommended Agent Prompt

Read `docs/specs/Security_API_Hardening_Spec.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings before changing any code:

1. D1–D7 findings (Steps 1–7)
2. AC gap table (AC-1 through AC-17)
3. Smallest patch set: files, one-line description, estimated line delta
4. Auth pattern recommendation: reuse `claude_code_api` pattern, trusted-local-only, or equivalent — with rationale
5. Timeout recommendation: exact call sites, wrapping approach, default values
6. Error leakage inventory: every path where internal detail currently reaches clients
7. Stream vs JSON error handling: confirm whether `/analyse/stream` needs different treatment

Hard constraints:
- `MarketPacketV2` contract locked — officer layer unchanged
- `market_data_officer/` package not modified
- Analyst graph structure unchanged — only invocation call site wrapped with timeout
- `call_llm()` hardening is transport/runtime only — do not redesign analyst logic
- No full identity management system (no OAuth, no SSO, no RBAC)
- No API gateway or reverse proxy infrastructure
- No SQLite, no new top-level module
- Deterministic tests only — no live LLM calls or provider dependency in CI
- Client error sanitisation must be proven by deterministic tests — not assumed
- No deployment automation in this phase

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion, close the spec and update docs:
1. `docs/specs/Security_API_Hardening_Spec.md` — mark ✅ Complete, flip all AC cells,
   populate §13 Diagnostic Findings with: auth pattern chosen, timeout values confirmed,
   error leakage paths closed, body-limit value, retry behavior, test count delta
2. `docs/specs/README.md` — move to Completed, update Current Phase to next candidate
3. `docs/AI_TradeAnalyst_Progress.md` — update current phase, add completed row with test count
4. If any Technical Debt Register items (§8 of progress plan) were resolved
   or partially addressed by this work, update their status in the register.

Commit all doc changes on the same branch as the implementation.
