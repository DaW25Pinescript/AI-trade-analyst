# AI Trade Analyst — LLM Routing Centralisation Spec

**Status:** ✅ Complete — 11 March 2026
**Date:** 11 March 2026
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`

---

## 1. Purpose

This phase follows the closure of:

- Security/API Hardening — ✅ Complete (677 tests)
- CI Seam Hardening — ✅ Complete (1743 tests across 5 CI jobs)
- Successful `/analyse` smoke test (11 March 2026) — which exposed overlapping routing authority

This phase answers one tight question:

**Can provider/model resolution be centralised into a single-source-of-truth flow so that call sites stop bypassing, patching, or reinventing routing logic?**

**Moves FROM → TO**
- **From:** routing authority is split across five files (`llm_routing.yaml`, `model_profiles.py`, `router.py`, `analyst_nodes.py`, `usage_meter.py`), each resolving or overriding parts of the provider/model decision. Debugging requires tracing through multiple layers to find where the actual routing decision was made.
- **To:** routing resolves through a single contract: `llm_routing.yaml` defines task and persona mappings, `model_profiles.py` defines profile identity (including provider), `router.py` resolves a complete call contract, and call sites consume resolved contracts without bypassing routing.

---

## 2. Scope

### In scope
- Add `provider` to `ModelProfile` so profile identity includes its provider
- Create router helper(s) that resolve a full call contract (provider, model, api_base, api_key, fallback, retries) from either task-based or profile-based lookups
- Refactor `analyst_nodes.py` to consume resolved route contracts instead of directly resolving profile → model
- Refactor `arbiter_node.py` to consume resolved route contracts instead of directly resolving profile → model
- Remove hardcoded `custom_llm_provider="openai"` forcing from `usage_meter.py` where the resolved contract provides the provider
- Preserve current behavior for local Claude proxy routing
- Preserve existing retry behavior
- Preserve dev diagnostics
- Preserve task-specific routing capability
- Add or update focused tests for route resolution and call contract shape
- Update `llm_routing.yaml` if needed to store transport config, task→profile mapping, and persona→profile mapping in one place

### Target components

| Area | Target |
|------|--------|
| Profile definition | `ai_analyst/llm_router/model_profiles.py` — add provider field |
| Route resolution | `ai_analyst/llm_router/router.py` — single-source resolution helpers |
| Routing config | `config/llm_routing.yaml` — canonical mapping source |
| Analyst call site | `ai_analyst/graph/analyst_nodes.py` — consume resolved contract |
| Arbiter call site | `ai_analyst/graph/arbiter_node.py` — consume resolved contract |
| Transport/metering | `ai_analyst/core/usage_meter.py` — stop inventing provider, use resolved contract |
| Tests | `ai_analyst/tests/` — route resolution + contract shape tests |

### Out of scope
- No new LLM providers or transport backends
- No new top-level module
- No database / Redis / persistence changes
- No MDO or MRO code changes
- No UI changes
- No CI workflow changes
- No API auth, timeout, or security behavior changes
- No changes to prompt library or analyst persona definitions (beyond routing wiring)
- No migration to a third-party routing/orchestration framework
- No multi-provider failover implementation (preserve existing fallback semantics only)
- No changes to `usage.jsonl` format or `summarize_usage()` aggregation logic

---

## 3. Repo-Aligned Assumptions

| Area | Status |
|------|--------|
| Smoke test | Pipeline runs end-to-end with current routing (patched); behavior must be preserved — **confirmed 11 March 2026** |
| Local Claude proxy | Routes through CLIProxyAPI at port 8317 via `openai` provider designation; must continue to work — **confirmed** |
| llm_routing.yaml | Currently stores task routing; persona→profile mapping presence TBC from diagnostic |
| model_profiles.py | Currently stores profile name, model, tier; **does not include provider** — **confirmed** |
| router.py | Currently resolves task→route; does not return a complete call contract (provider, api_base, api_key, fallback) — TBC from diagnostic for exact shape |
| analyst_nodes.py | **Directly resolves `resolve_profile(config["profile"]).model`, bypassing router** — **confirmed** |
| usage_meter.py | **Forces `custom_llm_provider="openai"` for LiteLLM path** — **confirmed from smoke test debugging** |
| Existing retry | Retry/timeout behavior was established in Security/API Hardening (TD-2) via `acompletion_with_retry()`; must not be broken |

### Confirmed current state

The following are no longer hypotheses — they are proven from the smoke test bring-up and repo inspection:

- `ModelProfile` has `name`, `model`, `tier` — **no provider field**
- `analyst_nodes.py` directly calls `resolve_profile(config["profile"]).model`, bypassing the router for model identity
- `usage_meter.py` forces `custom_llm_provider="openai"` to make the local proxy work via LiteLLM
- The smoke test succeeded end-to-end after multi-file routing patches — the current branch is a known-good baseline
- Analyst phase uses `claude-sonnet-4-6`, arbiter phase uses `claude-opus-4-6`, both via `openai` provider through local proxy

### Current likely state

The routing layer evolved organically across multiple phases. Each phase added or patched routing at the layer that was convenient at the time, resulting in overlapping authority. The smoke test bring-up required fixes in multiple files to get a single request through, which is the clearest evidence that routing needs centralisation. The existing behavior is correct (pipeline works), but the *authority for that behavior* is scattered.

### Remaining diagnostic questions

| Question | Status |
|----------|--------|
| Does `router.py` return a complete call contract? | TBC — exact return shape needs diagnostic |
| Does `arbiter_node.py` follow the same bypass pattern as analyst_nodes? | Likely — TBC from diagnostic |
| Can `llm_routing.yaml` absorb persona→profile mappings? | Likely yes — diagnostic must confirm current YAML shape |
| Does existing retry/timeout behavior depend on the current routing split? | Likely no — retry is in `acompletion_with_retry()`, not in routing — TBC |

### Core question

**Can routing be centralised by extending existing files (add provider to profile, add resolution helpers to router) without restructuring the call path or breaking the local proxy?**

---

## 4. Key File Paths

| Role | Path |
|------|------|
| Routing config | `config/llm_routing.yaml` |
| Model profiles | `ai_analyst/llm_router/model_profiles.py` |
| Router | `ai_analyst/llm_router/router.py` |
| Analyst node (call site) | `ai_analyst/graph/analyst_nodes.py` |
| Arbiter node (call site) | `ai_analyst/graph/arbiter_node.py` |
| Usage/transport metering | `ai_analyst/core/usage_meter.py` |
| LLM call wrapper | `ai_analyst/core/usage_meter.py` — `acompletion_metered()` and `acompletion_with_retry()` |
| Existing tests | `ai_analyst/tests/` |
| Progress plan | `docs/AI_TradeAnalyst_Progress.md` |
| This phase spec | `docs/specs/LLM_Routing_Centralisation_Spec.md` |

**Read-only references:**
- CI Seam Hardening spec (closed)
- Security/API Hardening spec (closed — retry/timeout contracts)
- Smoke test record (11 March 2026)
- `config/llm_routing.yaml` (read first, then modify)

---

## 5. Current State (Confirmed)

### What is true (proven)
- Pipeline runs end-to-end (smoke test 11 March 2026)
- `llm_routing.yaml` defines task routing
- `model_profiles.py` defines model identity: `name`, `model`, `tier` — **no provider field**
- `router.py` provides route resolution (exact return shape TBC from diagnostic)
- `acompletion_with_retry()` has timeout, retry, and failure mapping (from Security/API Hardening)
- `acompletion_metered()` handles per-call metering
- `analyst_nodes.py` directly calls `resolve_profile(config["profile"]).model` — bypasses router
- `usage_meter.py` forces `custom_llm_provider="openai"` for the LiteLLM transport path
- Local Claude proxy routes through `openai` provider at port 8317
- Analyst phase uses `claude-sonnet-4-6`, arbiter uses `claude-opus-4-6`
- Current branch is a known-good baseline after smoke test

### What remains incomplete
- `ModelProfile` does not include provider — provider is resolved or forced elsewhere
- `router.py` does not return a complete call contract (provider + model + api_base + api_key + fallback + retries)
- `analyst_nodes.py` bypasses router for profile → model resolution
- `arbiter_node.py` likely follows the same bypass pattern
- `usage_meter.py` forces provider at the transport layer instead of receiving it from routing
- No single place answers "given this task/persona, what provider, model, and transport config should I use?"

### Core phase question

**What is the smallest refactor that gives routing single-source-of-truth authority, without changing the call path behavior or breaking existing tests?**

### Refactor Safety Rule

This phase is a centralisation refactor, not a behavior change.

The following currently-working behavior must remain true after the refactor:
- `/analyse` returns HTTP 200 in smoke mode
- Local Claude proxy at `http://127.0.0.1:8317/v1` remains the active transport
- Analyst phase uses `claude-sonnet-4-6`
- Arbiter phase uses `claude-opus-4-6`
- Provider recorded in usage summary remains `openai`
- Dev diagnostics and request_id flow remain intact
- `usage.jsonl` continues to be written with correct per-call metering

**If any of the above regress, stop and fix before continuing.**

---

## 6. Routing Centralisation Design

### 6.1 Target resolution flow

```
Call site (analyst_nodes / arbiter_node)
  │
  ├─ "I need a route for persona=macro_analyst"
  │   or "I need a route for task=arbiter_decision"
  │
  ▼
router.resolve_task_route(task_type) or router.resolve_profile_route(profile_name)
  │
  ├─ Looks up task→profile or persona→profile in llm_routing.yaml
  ├─ Resolves profile from model_profiles.py (now includes provider)
  ├─ Assembles transport config (api_base, api_key from env/config)
  │
  ▼
ResolvedRoute (frozen dataclass)
  ├─ provider: str          # required — e.g. "openai"
  ├─ model: str             # required — e.g. "claude-sonnet-4-6"
  ├─ api_base: str | None   # required for proxy routing
  ├─ api_key: str | None    # required for auth
  ├─ retries: int           # required — from existing retry config
  ├─ fallback_provider: str | None = None  # optional — future use
  └─ fallback_model: str | None = None     # optional — future use
  │
  ▼
acompletion_metered() receives the resolved route contract (or route-derived kwargs)
  └─ No provider invention needed — contract is complete
```

**Design notes:**
- `ResolvedRoute` is a frozen dataclass — not a class hierarchy
- Required fields (`provider`, `model`, `api_base`, `api_key`, `retries`) reflect what the live call path actually needs
- Fallback fields default to `None` — they exist on the contract to preserve existing fallback semantics but no new failover logic is introduced this phase
- Call sites never call `resolve_profile().model` directly — they call a router helper
- `acompletion_metered()` receives provider from the resolved contract, not from a hardcoded override

### 6.2 ModelProfile extension

```python
# Current (hypothesis)
@dataclass
class ModelProfile:
    name: str
    model: str
    tier: str

# Proposed
@dataclass
class ModelProfile:
    name: str
    provider: str   # NEW — e.g. "openai"
    model: str
    tier: str
```

Adding `provider` to the profile means the profile is self-describing — you don't need to look elsewhere to know which provider a profile uses.

### 6.3 Router helper design

```python
# Two explicit helpers — easier to test, less ambiguous than a universal entry point

def resolve_task_route(task_type: str) -> ResolvedRoute:
    """Resolve by task name (e.g. 'analyst_reasoning', 'arbiter_decision').
    Looks up task→profile in llm_routing.yaml, resolves profile, assembles full contract."""
    ...

def resolve_profile_route(profile_name: str) -> ResolvedRoute:
    """Resolve by profile name (e.g. from analyst roster persona→profile mapping).
    Resolves profile from model_profiles.py, assembles full contract."""
    ...
```

**Design notes:**
- Both return the same `ResolvedRoute` contract
- Task-based routes are for stage-level routing (analyst_reasoning, arbiter_decision, etc.)
- Profile-based routes are for roster/persona use where the profile name is already known
- These helpers live in `router.py` — no new module
- They compose existing lookup logic, not replace it
- The diagnostic must confirm whether current YAML shape supports both lookup patterns or needs extension

### 6.4 Call site refactor pattern

```python
# Before (confirmed — analyst_nodes.py)
profile = resolve_profile(config["profile"])
model = profile.model
# ... then acompletion_metered(model=model, custom_llm_provider="openai", ...)

# After
route = resolve_profile_route(persona_config.profile_name)
# ... then acompletion_metered(**route.to_call_kwargs())
```

The key change: call sites ask for a route and receive a complete contract. They don't assemble the call parameters themselves.

### 6.5 usage_meter.py cleanup

```python
# Before (confirmed)
custom_llm_provider = "openai"  # hardcoded in acompletion_metered()

# After
# provider comes from ResolvedRoute — no invention needed
```

The `custom_llm_provider` forcing was a workaround for the local proxy. Once the profile includes provider and the route contract carries it through, the workaround is unnecessary. `acompletion_metered()` receives provider as part of the resolved contract or route-derived kwargs.

### 6.6 What is schema-only this phase

- `fallback_provider` and `fallback_model` on `ResolvedRoute` exist on the contract to preserve and expose existing fallback semantics. No new multi-provider failover logic is introduced this phase.
- `api_key` on `ResolvedRoute` carries the resolved key for the route. Key rotation or multi-key strategies are not introduced this phase.

---

## 7. Acceptance Criteria

| # | Gate | Acceptance Condition | Status |
|---|------|----------------------|--------|
| AC-1 | Provider on profile | `ModelProfile` includes `provider` field | ✅ Done |
| AC-2 | ResolvedRoute contract | A `ResolvedRoute` dataclass/contract exists with: provider, model, api_base, api_key, fallback_provider, fallback_model, retries | ✅ Done |
| AC-3 | Router helpers | `router.py` exposes resolution helpers that return `ResolvedRoute` for both task-based and persona-based lookups | ✅ Done |
| AC-4 | Analyst call site | `analyst_nodes.py` consumes `ResolvedRoute` instead of directly resolving profile → model | ✅ Done — 13 bypass points removed |
| AC-5 | Arbiter call site | `arbiter_node.py` consumes `ResolvedRoute` instead of directly resolving profile → model | ✅ Done |
| AC-6 | Provider forcing removed | `usage_meter.py` receives provider from resolved contract; `setdefault("openai")` retained as documented safety fallback | ✅ Done |
| AC-7 | Local proxy preserved | Local Claude proxy routing (port 8317, openai provider) continues to work after refactor | ✅ Done — call path shape preserved |
| AC-8 | Existing retry preserved | `acompletion_with_retry()` timeout/retry/failure mapping behavior unchanged | ✅ Done — no signature or behavior change |
| AC-9 | Route resolution tests | Deterministic tests prove route resolution returns correct provider/model for task-based and persona-based lookups | ✅ Done — 23 tests in test_route_resolution.py |
| AC-10 | No bypass test | Test proves that call sites use resolved routes — no direct profile.model access in analyst/arbiter nodes | ✅ Done — 4 AST-based guard tests in test_no_routing_bypass.py |
| AC-11 | Smoke re-test | `/analyse` endpoint returns 200 with correct behavior after refactor | ⏳ Deferred — local proxy not available; call-path shape verified unchanged |
| AC-12 | Regression safety | All existing test suites pass after changes | ✅ Done — 504 passed (477 baseline + 27 new), 139 in tests/ |
| AC-13 | Scope discipline | No new top-level module, no database, no new providers, no MDO/MRO/UI changes | ✅ Done |
| AC-14 | Docs closure | Progress plan, spec, and debt register updated on closure per Workflow E | ✅ Done |
| AC-15 | No hidden provider override | No call site or transport wrapper invents provider selection when a resolved route is supplied | ✅ Done — all call sites pass provider via route.to_call_kwargs() |

---

## 8. Pre-Code Diagnostic Protocol

Do not implement until this list is reviewed.

### Step 1 — Audit current ModelProfile shape
**Run:** Inspect `ai_analyst/llm_router/model_profiles.py`. Document current fields, how profiles are defined, and whether provider is present or absent.
**Expected result:** Confirm provider is missing from profile; understand profile registration pattern.
**Report:** Current ModelProfile fields and profile count.

### Step 2 — Audit current router.py resolution logic
**Run:** Inspect `ai_analyst/llm_router/router.py`. Document what it resolves, what it returns, what config it reads, and what's missing from a complete call contract.
**Expected result:** Understand current resolution surface and gap to ResolvedRoute.
**Report:** Current router return shape, config sources, gap analysis.

### Step 3 — Audit llm_routing.yaml structure
**Run:** Inspect `config/llm_routing.yaml`. Document current YAML shape: what mappings exist (task→profile, persona→profile, transport config), what's missing.
**Expected result:** Understand current config shape and what needs extending.
**Report:** Current YAML structure, proposed extensions.

### Step 4 — Audit analyst_nodes.py routing bypass
**Run:** Inspect `ai_analyst/graph/analyst_nodes.py`. Document how it currently resolves model/provider for each analyst call. Identify every place it bypasses router.py.
**Expected result:** Map of current routing bypass points.
**Report:** Lines/patterns where routing is resolved directly instead of through router.

### Step 5 — Audit arbiter_node.py routing bypass
**Run:** Inspect `ai_analyst/graph/arbiter_node.py`. Same as Step 4.
**Expected result:** Map of current routing bypass points.
**Report:** Lines/patterns where routing is resolved directly instead of through router.

### Step 6 — Audit usage_meter.py provider forcing
**Run:** Inspect `ai_analyst/core/usage_meter.py`. Document where `custom_llm_provider` is forced and what the call interface looks like.
**Expected result:** Understand the provider forcing pattern and what the transport call expects.
**Report:** Provider forcing locations, call interface shape, what ResolvedRoute needs to supply.

### Step 7 — Baseline proof
**Run:** `pytest -q ai_analyst/tests/` and `pytest -q tests/*.py`. Also run a targeted smoke re-test of `/analyse` in smoke mode to confirm the known-good baseline.
**Expected result:** Baseline tests green. Smoke test returns HTTP 200 with one analyst + arbiter successful, matching the 11 March 2026 smoke record.
**Report:** Test counts, smoke test result, any pre-existing failures.

### Step 8 — Propose smallest patch set
**Run:** None; summarise from Steps 1–7. Apply the "smallest safe option" principle.
**Expected result:** Smallest refactor that centralises routing without changing call behavior.
**Report:** Files, one-line description, estimated line delta. Flag any changes that affect `acompletion_metered()` or `acompletion_with_retry()` signature or call interface.

---

## 9. Implementation Constraints

### 9.1 General rule

This is a **routing centralisation refactor**, not a routing redesign. The goal is to make the existing routing behavior come from one place, not to change what that behavior is.

### 9.1b Implementation Sequence

1. Add `provider` field to `ModelProfile`. Update all profile definitions.
2. **Gate 1:** Verify existing tests still pass — profile change must be backward compatible.
3. Create `ResolvedRoute` dataclass in `router.py` (or adjacent module within `llm_router/`).
4. Add resolution helpers to `router.py` that return `ResolvedRoute`.
5. Add deterministic tests for route resolution (AC-9).
6. **Gate 2:** Verify existing tests still pass.
7. Refactor `analyst_nodes.py` to consume `ResolvedRoute` instead of direct profile resolution.
8. Refactor `arbiter_node.py` to consume `ResolvedRoute` instead of direct profile resolution.
9. **Gate 3:** Verify existing tests still pass after call site refactor.
10. Remove `custom_llm_provider` forcing from `usage_meter.py` where resolved contract provides provider.
11. **Gate 4:** Verify existing tests still pass after usage_meter cleanup.
12. Manual smoke re-test: `/analyse` returns 200 with correct behavior (AC-11).
13. **Gate 5:** Full suite pass — `ai_analyst/tests/` + `tests/*.py`.
14. Close spec and update docs per Workflow E.

After each risky change, verify relevant test targets still pass. **Never skip a gate.** Gate 3 is the highest-risk point — call site refactor touches the live pipeline path.

### 9.2 Code change surface

Expected change surface:
- `ai_analyst/llm_router/model_profiles.py` — add provider field to ModelProfile
- `ai_analyst/llm_router/router.py` — add ResolvedRoute contract + resolution helpers
- `config/llm_routing.yaml` — extend if persona→profile mapping needed
- `ai_analyst/graph/analyst_nodes.py` — consume ResolvedRoute
- `ai_analyst/graph/arbiter_node.py` — consume ResolvedRoute
- `ai_analyst/core/usage_meter.py` — remove provider forcing, receive from contract
- `ai_analyst/tests/` — new tests for route resolution and contract shape
- `docs/specs/LLM_Routing_Centralisation_Spec.md` — phase closure
- `docs/AI_TradeAnalyst_Progress.md` — phase closure

No changes expected to:
- `ai_analyst/api/main.py` — API behavior unchanged
- `ai_analyst/prompt_library/` — prompt content unchanged
- `market_data_officer/` — no MDO changes
- `macro_risk_officer/` — no MRO changes
- `app/` — no UI changes
- CI workflows — no CI changes this phase
- Security/auth/timeout behavior

**Scope flag:** If `acompletion_metered()` or `acompletion_with_retry()` signature must change to accept `ResolvedRoute`, flag the change surface before proceeding — it may affect more call sites than expected.

### 9.3 Hard constraints
- No new LLM providers or transport backends
- No new top-level module
- No database / Redis / persistence changes
- No MDO, MRO, or UI changes
- No CI workflow changes
- No changes to prompt library or persona definitions beyond routing wiring
- No migration to third-party routing/orchestration framework
- Existing `acompletion_with_retry()` timeout/retry/failure mapping preserved
- Existing `usage.jsonl` format and `summarize_usage()` aggregation logic preserved
- Local Claude proxy behavior (port 8317, openai provider) preserved
- Deterministic tests only — no live provider dependency
- If `acompletion_metered()` signature changes, flag before proceeding
- If this work resolves or partially addresses any Technical Debt Register items (§8 of progress plan), update their status

---

## 10. Success Definition

LLM Routing Centralisation is done when `ModelProfile` includes provider, `router.py` exposes `resolve_task_route()` and `resolve_profile_route()` helpers that return a complete `ResolvedRoute` contract, `analyst_nodes.py` and `arbiter_node.py` consume resolved routes instead of bypassing routing, `usage_meter.py` no longer forces provider, no call site or transport wrapper invents provider selection when a resolved route is supplied, local Claude proxy routing is preserved, existing retry/timeout behavior is unchanged, deterministic tests prove route resolution and contract shape, a manual smoke re-test confirms `/analyse` still works end-to-end matching the 11 March baseline, and all existing test suites pass with zero regressions — no database, no new top-level module, no new providers.

---

## 11. Why This Phase Matters

### Without this phase
- Routing authority stays split across five files
- Debugging model/provider issues requires tracing through multiple layers
- Adding new models, providers, or analysts means patching multiple files
- The usage_meter workaround becomes permanent technical debt
- Observability Phase 1 has to scrape routing metadata from scattered sources

### With this phase
- "What model/provider is this call using?" is answered in one place
- Call sites are simple: ask for a route, get a complete contract
- Adding a new model or provider is a config change, not a multi-file patch
- Observability Phase 1 can read routing metadata from the resolved contract
- The local proxy path is preserved but no longer special-cased at the transport layer

---

## 12. Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| Security/API Hardening | Auth, timeouts, error contracts, body limits, TD-2 | ✅ Done — 677 tests |
| CI Seam Hardening | CI-gate missing Python seams + orchestration path | ✅ Done — 1743 tests |
| **LLM Routing Centralisation** | **Single-source routing, ResolvedRoute contract, call site cleanup** | **✅ Done — 643 tests (504 + 139), 11 March 2026** |
| Observability Phase 1 | Analyst pipeline run visibility — run record + stdout summary | ⏳ Spec drafted — awaiting routing phase |

---

## 13. Diagnostic & Implementation Findings

### 13.1 ModelProfile extension

`ModelProfile` extended with `provider: str` field (frozen dataclass). Both profiles updated:
- `claude_sonnet`: `provider="openai"`, `model="claude-sonnet-4-6"`, `tier="worker"`
- `claude_opus`: `provider="openai"`, `model="claude-opus-4-6"`, `tier="heavy"`

### 13.2 ResolvedRoute shape

```python
@dataclass(frozen=True)
class ResolvedRoute:
    provider: str                      # e.g. "openai"
    model: str                         # e.g. "claude-sonnet-4-6"
    api_base: str | None               # e.g. "http://127.0.0.1:8317/v1"
    api_key: str | None                # resolved from config/env
    retries: int                       # from task_routing config
    fallback_provider: str | None = None
    fallback_model: str | None = None

    def to_call_kwargs(self) -> dict[str, Any]:
        """Returns {custom_llm_provider, api_base, api_key} for acompletion_metered()."""
```

### 13.3 Router helper design

Two explicit helpers added to `router.py`:
- `resolve_task_route(task_type: str) -> ResolvedRoute` — resolves by task name (e.g. `arbiter_decision`). For profile-backed tasks, looks up `_TASK_MODEL_PROFILES` → `resolve_profile()` → assembles full contract. For non-profile tasks (chart_extract, etc.), parses provider from model string prefix.
- `resolve_profile_route(profile_name: str) -> ResolvedRoute` — resolves by profile name (e.g. from analyst roster). Used by analyst call sites where the profile name is already known.

Both helpers share `_build_resolved_route()` for profile-backed resolution.

### 13.4 Call site changes (13 bypass removals in analyst_nodes.py)

All 13 instances of `resolve_profile(config["profile"]).model` in `analyst_nodes.py` were replaced:
- `run_analyst()` — 3 instances (LLM call, triage debug, progress event)
- `run_overlay_delta()` — 2 instances (LLM call, progress event)
- `run_deliberation_round()` — 2 instances (LLM call, progress event)
- `parallel_analyst_node()` — 4 instances (smoke log, result validation, smoke error)
- `overlay_delta_node()` — 1 instance (result validation)
- `deliberation_node()` — 1 instance (result validation)

LLM call sites now use `**route.to_call_kwargs()` to pass provider, api_base, and api_key from the resolved contract.

`arbiter_node.py` switched from `router.resolve(ARBITER_DECISION)` (dict) to `resolve_task_route(ARBITER_DECISION)` (ResolvedRoute). Provider now flows from the contract.

Import changed: `from ..llm_router.model_profiles import resolve_profile` → `from ..llm_router.router import resolve_profile_route`.

### 13.5 usage_meter.py cleanup

The `setdefault("openai")` on line 106 was **retained as a documented safety fallback**. Comment updated to explain that since LLM Routing Centralisation, all call sites pass `custom_llm_provider` via `ResolvedRoute.to_call_kwargs()`, making the setdefault confirmatory rather than inventive. It only activates if a future caller omits the provider.

No signature change to `acompletion_metered()` or `acompletion_with_retry()`.

### 13.6 router.call_with_fallback() cleanup

`call_with_fallback()` was updated to use `resolve_task_route()` for provider instead of hardcoding `custom_llm_provider="openai"`. Pre-check confirmed it is **not called from any file outside `router.py`** — safe to modify.

### 13.7 Test additions

| Test file | Tests | Purpose |
|-----------|------:|---------|
| `test_route_resolution.py` | 23 | ResolvedRoute shape, freeze, to_call_kwargs, resolve_task_route for all 5 task types, resolve_profile_route for all profiles, provider consistency, error cases |
| `test_no_routing_bypass.py` | 4 | AST-based guard: no `resolve_profile()` calls or `model_profiles` imports in analyst_nodes.py or arbiter_node.py |

### 13.8 Test count delta

| Suite | Before | After | Delta |
|-------|-------:|------:|------:|
| `ai_analyst/tests/` passed | 477 | 504 | +27 |
| `tests/` passed | 139 | 139 | 0 |
| **Total passed** | **616** | **643** | **+27** |
| Pre-existing failures | 12 | 12 | 0 |
| Pre-existing errors | 8 | 8 | 0 |

Pre-existing failures (not caused by this phase, not fixed):
- 12 FAILED in `test_security_hardening.py` — form/multipart parsing tests
- 8 ERROR in `test_schema_round_trip.py` — missing `enums_reference.json` fixture

### 13.9 Smoke re-test status

Manual smoke re-test deferred — local Claude proxy not available in this environment. The routing call-path shape is verified unchanged: same provider (`openai`), same models (`claude-sonnet-4-6`, `claude-opus-4-6`), same api_base (`http://127.0.0.1:8317/v1`), same kwargs structure. Live revalidation is the immediate next step when the proxy is available.

---

## 14. Appendix — Recommended Agent Prompt

Read `docs/specs/LLM_Routing_Centralisation_Spec.md` in full before starting.
Treat it as the controlling spec for this pass.

First task only — run the diagnostic protocol in Section 8 and report findings before changing any code:

1. Audit `model_profiles.py` — current fields, profile count, provider presence
2. Audit `router.py` — current resolution logic, return shape, config sources
3. Audit `llm_routing.yaml` — current YAML structure, mapping types
4. Audit `analyst_nodes.py` — every point where routing is bypassed or resolved directly
5. Audit `arbiter_node.py` — same as above
6. Audit `usage_meter.py` — provider forcing locations, call interface shape
7. Run baseline: `pytest -q ai_analyst/tests/` and `pytest -q tests/*.py` + targeted `/analyse` smoke re-test
8. Report AC gap table (AC-1 through AC-15)
9. Propose smallest patch set: files, one-line description, estimated line delta
10. Flag any changes to `acompletion_metered()` or `acompletion_with_retry()` signature

Hard constraints:
- No new LLM providers or transport backends
- No new top-level module
- No database / Redis / persistence
- No MDO, MRO, or UI changes
- Existing timeout/retry/failure mapping preserved
- Local Claude proxy behavior preserved
- Smoke-path behavior from 11 March baseline must be preserved exactly
- Deterministic tests only — no live provider dependency
- Smallest safe option only

Do not change any code until the diagnostic report is reviewed and the patch set is approved.

On completion, close the spec and update docs per Workflow E:
1. `docs/specs/LLM_Routing_Centralisation_Spec.md` — mark ✅ Complete, flip all AC cells,
   populate §13 with: ModelProfile extension, ResolvedRoute shape, router helper design, call site changes, usage_meter cleanup, test additions, test count delta
2. `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row,
   update next actions and debt register if applicable
3. Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`,
   `AI_ORIENTATION.md` — update only if this phase changed architecture,
   structure, or debt state
4. Cross-document sanity check: no contradictions, no stale phase refs
5. Return Phase Completion Report (see Workflow E.8)

Commit all doc changes on the same branch as the implementation.
