# PR-UI-4 — Journey Studio MVP

Implement **PR-UI-4** for the AI Trade Analyst repo.

This is the next frontend phase after PR-UI-1 (React shell), PR-UI-2 (Triage Board), PR-UI-3 (shared components), and PR-OPS-3 (Agent Ops workspace).

## Mission

Build a real `/journey` workspace that begins the **core product workflow lane**:

**Triage Board → Journey Studio → Analysis Run → Journal & Review**

Journey Studio should become the structured planning / staging workspace between triage selection and analysis execution.

This PR is **frontend only** and must use **existing backend endpoints only**.

## Hard scope boundaries

Do:
- implement Journey Studio in `ui/src/workspaces/journey/`
- inspect the repo and determine which existing backend endpoint(s) can support Journey today
- add typed API client(s)
- add workspace-local hook(s) and adapter(s)
- implement deterministic state handling
- reuse the proven shared component system where appropriate
- wire safe continuity from Triage into Journey
- add tests
- update progress docs

Do not:
- add backend routes
- modify backend response shapes
- add Analysis Run execution UI
- add Journal & Review UI
- add Agent Ops functionality
- add trace/detail or reflective/review features
- use SSE/WebSocket
- invent unsupported backend data

## Required implementation process

### 1. Audit first

Before implementing, inspect:
- current backend routes (FastAPI app, existing routers)
- `docs/ui/UI_CONTRACT.md` §10.3 (journey endpoint contracts)
- `docs/ui/UI_WORKSPACES.md` §6 (Journey Studio spec)
- `docs/ui/DESIGN_NOTES.md` §1.3–1.5 (freeze, gating, handoff)
- `VISUAL_APPENDIX.md` (Journey Studio wireframe)
- existing `ui/` route structure and Triage navigation
- `ui/src/shared/api/journey.ts` — check if a stub exists

**Documented endpoints to look for:**

| Endpoint | Purpose | Contract ref |
|----------|---------|-------------|
| `GET /journey/{asset}/bootstrap` | Preloaded evidence/context | §9.6 |
| `POST /journey/draft` | Mutable draft save | §10.3, §11.2 |
| `POST /journey/decision` | Immutable freeze (409 on duplicate) | §10.3, §11.2 |
| `POST /journey/result` | Result linked to decision | §10.3, §11.2 |

Determine which actually exist in the backend. Build from what's available. In your final summary, **explicitly state which endpoints you used and why.**

### 2. Keep the MVP honest

Only display content that can be grounded in real existing data.

**If write endpoints exist:** implement full staged flow with freeze lifecycle, conditional right rail, Save Result gating.

**If only bootstrap/read exists:** implement structured read-only planning workspace with candidate context and analysis handoff.

**If no journey endpoints exist:** implement minimal Triage-continuity workspace showing asset context with honest "data unavailable" handling.

### 3. Use typed frontend contracts

Any used endpoint must have:
- typed API client function(s)
- no `any`
- no inline ad hoc fetch logic in the page component
- if write endpoints: preserve `{ success: false, error }` envelope from §11.2

### 4. Add a workspace adapter

Create an adapter layer in `ui/src/workspaces/journey/adapters/` that:
- maps backend payloads to Journey view models
- normalizes missing/null values
- if bootstrap exists: derives which right rail panels render from field presence
- if write endpoints exist: derives frozen/unfrozen state, Save Result enablement
- preserves honest state handling

### 5. Implement Journey UI

If write endpoints exist, build the full interaction model:
- **Staged flow** (UI concept, NOT a backend entity — do not POST stage state)
- **Freeze lifecycle:** pre-freeze interactive → freeze → post-freeze read-only
- **Conditional right rail:** panels appear for present bootstrap fields only; single fallback when unavailable
- **Save Result gating:** disabled until freeze succeeds
- **409 handling:** conflict message, not generic error

If read-only, build a clean planning workspace with shared component reuse.

### 6. Implement navigation continuity

PR-UI-1 route: `#/journey/:asset`. PR-UI-2 Triage row click should navigate there. Verify end-to-end.

Handle safely:
- route parameter exists → fetch bootstrap for that asset
- route parameter missing → safe fallback
- endpoint returns empty/unavailable → honest state handling

### 7. Test properly

Add:
- adapter unit tests
- Journey page state tests (loading, ready, empty, unavailable, error)
- route/integration tests
- navigation continuity tests
- if write endpoints exist: freeze lifecycle, 409 handling, Save Result gating
- if conditional right rail: panel presence/absence tests

No snapshots. Explicit assertions.

## Acceptance bar

The PR is successful only if:
- `/journey` is no longer a placeholder
- it uses real existing backend data
- it safely handles loading / ready / empty / unavailable / error
- if write endpoints exist: freeze feels deliberate, Save Result gated, 409 handled
- it does not overclaim execution or later-phase capabilities
- no backend files changed
- tests pass
- docs updated accurately

## Final output format

When complete, return:

1. **Summary** — what Journey Studio now does
2. **Endpoint basis** — the exact existing backend endpoint(s) used, and why
3. **Files added / changed** — grouped by area
4. **State handling** — how each condition is handled
5. **Freeze behavior** — if implemented, pre/post-freeze details; if not, why
6. **Navigation continuity** — how Triage → Journey works
7. **Tests** — count and coverage
8. **Verification** — typecheck, build, test results
9. **Deviations** — anything changed from the plan
10. **Suggested commit message**
11. **Suggested PR description**

## Quality bar
Journey Studio should feel like a structured trade ideation workspace — not a data dump, not a blank form, and not a settings page. If freeze exists, it should feel like commitment. The workspace should guide the user from "interesting candidate" toward "committed decision" without pretending capabilities that don't exist yet.
