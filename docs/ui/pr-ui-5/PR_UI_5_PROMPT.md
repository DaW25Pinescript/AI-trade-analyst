# PR-UI-5 — Analysis Run Workspace MVP

Implement **PR-UI-5** for the AI Trade Analyst repo.

This is the next frontend phase after PR-UI-4 (Journey Studio) and PR-UI-4a (canFreeze hardening). It is the second of three Phase 6 PRs: PR-UI-4 (Journey), **PR-UI-5 (Analysis Run)**, PR-UI-6 (Journal & Review).

## Mission

Build a real `/analysis` workspace — the **expert execution surface** for direct multi-analyst analysis.

Analysis Run is where the user submits a manual analysis request, watches the pipeline execute, and inspects the full verdict and usage data. It sits alongside the primary product lane (Triage → Journey) as the compatibility/expert path.

This PR is **frontend only** and must use **existing backend endpoints only**.

## Governance

Frontend behavior must conform to the UI contract. The contract hierarchy is:

```
Backend code
    ↓
UI_CONTRACT.md
    ↓
Frontend implementation
```

The frontend must not derive contracts from OpenAPI or ad-hoc backend observation.

---

## Hard scope boundaries

Do:
- implement Analysis Run in `ui/src/workspaces/analysis/`
- inspect the repo and determine the exact field names accepted by `POST /analyse` (multipart/form-data)
- add typed API client(s) for `/analyse` and `/runs/{run_id}/usage`
- add workspace-local hook(s), adapter(s), and run lifecycle state machine
- implement the canonical run state model (UI_CONTRACT §7) for the synchronous flow
- implement three-panel tabbed layout with tab persistence
- implement Journey → Analysis escalation with provenance breadcrumb
- design the execution panel so streaming can be added later without redesign
- reuse proven shared components where appropriate
- add tests
- update progress docs

Do not:
- add backend routes
- modify backend response shapes
- implement SSE streaming (`/analyse/stream`) — reserved for Phase 3B
- implement or render `partial` run state (only meaningful with streaming; reserve in the state model, do not surface in UI)
- add Journal & Review UI (that's PR-UI-6)
- add auto-retry on submission failure
- fake progress indicators during the synchronous wait
- use SSE/WebSocket
- invent unsupported backend data

---

## Allowed endpoints

| Endpoint | Purpose | Contract ref | Transport |
|----------|---------|-------------|-----------|
| `POST /analyse` | Multi-analyst analysis with final verdict | §10.1, §8.1 | multipart/form-data |
| `GET /runs/{run_id}/usage` | Usage summary after completion | §10.1 | JSON |

**Documented but NOT implemented this PR:**

| Endpoint | Purpose | Why deferred |
|----------|---------|-------------|
| `POST /analyse/stream` | SSE streaming analysis | Phase 3B — streaming reserved for later |

No new endpoints may be introduced.

---

## Contract-aligned domain model

### AnalysisResponse

Terminal response from `/analyse`.

```
AnalysisResponse {
  run_id: string
  verdict: FinalVerdict
  ticket_draft: object
  usage_summary?: UsageSummary
}
```

### FinalVerdict

Minimum fields required by UI (expert density — all visible, no "show more"):

```
FinalVerdict {
  final_bias
  decision
  approved_setups[]
  no_trade_conditions[]
  overall_confidence
  analyst_agreement_pct
  arbiter_notes
}
```

### UsageSummary

Usage data retrieved after run completion. The UI must support empty-but-valid usage summaries.

```
UsageSummary {
  total_tokens?
  total_cost?
  model_breakdown?
}
```

---

## UI Run Lifecycle Model

The workspace must implement the canonical lifecycle defined in UI_CONTRACT §7.

### Synchronous flow (implemented this PR):

```
idle → validating → submitting → running → completed | failed
```

### Streaming flow (reserved — not implemented this PR):

```
idle → validating → submitting → running → partial → completed | failed
```

`partial` must exist in the state machine type definition so streaming can be added later. It must not be rendered or entered in the shipped MVP.

### Post-completion modifiers (handle where applicable):

- `artifact-missing` — usage fetch returns empty or fails
- `stale` — related data freshness degraded
- `inconsistent` — payloads disagree

### State transition rules:

- enforce valid transitions only (the state machine must reject invalid state jumps)
- `run_id` / `request_id` must be preserved across all states where available, including failure states (UI_CONTRACT §12.3)

---

## Required implementation process

### 1. Audit first

Before implementing, inspect:
- current backend routes for `/analyse` (FastAPI app, existing routers)
- the legacy `app/scripts/` UI that already submits to `/analyse` — determine the exact multipart field names
- `docs/ui/UI_CONTRACT.md` §7 (run state model), §8 (execution semantics), §9.1–9.4 (domain model), §10.1 (analysis endpoints), §11.1 (mixed detail errors), §12.2 (timeout/retry)
- `docs/ui/UI_WORKSPACES.md` §7 (Analysis Run workspace spec)
- `docs/ui/DESIGN_NOTES.md` §1.6 (tab persistence), §1.7 (usage panel), §1.8 (header provenance)
- `VISUAL_APPENDIX.md` (Analysis Run wireframe)
- existing `ui/` route structure
- `ui/src/shared/api/` — check if a stub or multipart helper exists
- `ui/src/shared/` — check what shared components are available from PR-UI-3

**Determine the exact multipart field names from the backend code. In your final summary, explicitly state which fields you found and which you used.**

### 2. Architecture

The implementation must follow this layering:

```
API Layer (ui/src/shared/api/ or workspace-local)
    ↓
Workspace Adapter (ui/src/workspaces/analysis/adapters/)
    ↓
Run Lifecycle State Machine (ui/src/workspaces/analysis/state/)
    ↓
Workspace UI (ui/src/workspaces/analysis/)
```

Each layer has a single responsibility:

- **API layer** — enforce correct transport (multipart for `/analyse`, JSON for usage), normalize error shapes, return contract-aligned payloads
- **Adapter** — translate backend responses to UI domain objects, isolate components from backend variability
- **State machine** — enforce valid lifecycle transitions, provide current UI state, preserve `run_id` / `request_id` across transitions
- **UI** — render based on state, never derive state from ad-hoc response inspection

### 3. API Layer

Create analysis API functions.

Location: `ui/src/workspaces/analysis/api/` (or extend `ui/src/shared/api/` if multipart support is cleanly general)

Functions:
- `submitAnalysis(formData: FormData)` — `POST /analyse` as multipart/form-data
- `fetchRunUsage(runId: string)` — `GET /runs/{run_id}/usage` as JSON

**Transport rule:** `POST /analyse` accepts multipart/form-data (UI_CONTRACT §5.2). Do not use `apiFetch<T>` if it assumes JSON Content-Type. Either extend the shared fetch layer to support FormData, or create a workspace-local multipart submit function. Document which approach is used.

**Error handling:** `/analyse` returns mixed `detail` patterns — string or structured object (UI_CONTRACT §11.1). The API layer must handle both shapes without crashing. Structured objects may include `message`, `code`, `request_id`, `run_id`. Preserve all identifiers.

**Timeout rule:** This is a long-running POST. Do not auto-retry on timeout or network interruption (UI_CONTRACT §12.2). Preserve any `run_id` or `request_id` from the failure payload.

### 4. Workspace Adapter

Create adapter translating backend responses to UI domain objects.

Location: `ui/src/workspaces/analysis/adapters/analysisAdapter.ts`

Responsibilities:
- `normalizeAnalysisResponse()` — map `AnalysisResponse` → Analysis view model
- `normalizeVerdict()` — map `FinalVerdict` → Verdict view model (expert density, all fields)
- `normalizeUsageSummary()` — map `UsageSummary` → Usage view model (tolerate empty-but-valid)
- `normalizeError()` — normalize mixed `detail` shapes (string or object) into stable error display model with preserved `run_id` / `request_id`
- derive tab enablement (verdict tab disabled on `failed`)
- derive submission panel read-only state post-submit
- derive usage availability (`artifact-missing` vs `ready` vs `loading`)

### 5. Run Lifecycle State Machine

Create deterministic run lifecycle manager.

Location: `ui/src/workspaces/analysis/state/runLifecycle.ts`

**This is workspace-local, not shared.** Move to `ui/src/shared/state/` only if another workspace genuinely reuses the same lifecycle semantics.

State type definition must include all canonical states:
```
idle | validating | submitting | running | partial | completed | failed
```

`partial` exists in the type so streaming can be added later. It is not entered or rendered in this PR.

Implemented transitions (synchronous flow):
```
idle → validating
validating → submitting (or back to idle on validation failure)
submitting → running
running → completed
running → failed
completed → idle (reset)
failed → idle (reset)
```

Responsibilities:
- enforce valid transitions (reject invalid state jumps)
- provide current UI state to components
- preserve `run_id` / `request_id` across transitions
- expose transition actions as typed functions
- accommodate future streaming events without restructuring

### 6. Implement Analysis Run UI

Build the three-panel tabbed workspace with **tab persistence** (DESIGN_NOTES §1.6).

Use the shared system where appropriate:
- `PanelShell`
- feedback components (`LoadingSkeleton`, `ErrorState`, `EmptyState`)
- state pills / badges (`StatusPill` for run lifecycle)

Workspace-local components:

- **`AnalysisRunPage`** — main orchestrator with tab state
- **`AnalysisHeader`** — instrument, provenance breadcrumb, "Return to Journey" link (when escalated)
- **`SubmissionPanel`** — form inputs, chart upload, submit button. Locks to read-only post-submission.
- **`ExecutionPanel`** — run lifecycle state, spinner with elapsed time, `run_id` display, reserved vertical space for future streaming log
- **`VerdictPanel`** — full verdict card, ticket draft, disabled state on failure
- **`UsageAccordion`** — inline below verdict, secondary artifact read
- **`AnalysisActionBar`** — submit, retry, reset actions

### Tab persistence (non-negotiable)

All three tabs (Submission | Execution | Verdict) remain navigable post-run.
- Submission becomes **read-only** but accessible for "what did I submit?" verification
- Execution shows terminal state (completed/failed) with preserved `run_id`
- Verdict shows full verdict or "No verdict — run failed" disabled state

### Submission panel

The submission form must handle multipart/form-data:
- instrument field (text input)
- session field (text input or select)
- context/risk fields as the backend accepts them
- chart file upload (file input)
- optional flags (deliberation, triage reference, source ticket) if backend accepts them

**Audit the actual backend `/analyse` route to determine the exact accepted field names.** Do not guess. The legacy `app/scripts/` UI already submits to this endpoint — inspect it for the real field set.

The form has a `validating` state: local field validation before request dispatch. Show inline validation errors. Block submit if validation fails.

### Execution panel (the critical interaction)

Pre-run:
- form fields interactive, submit button enabled
- execution panel shows `idle`
- verdict panel shows placeholder or "Submit to see verdict"

Submit → Running:
- form locks to read-only (duplicate submission prevention)
- execution panel transitions: `validating` → `submitting` → `running`
- submit button disabled, **spinner with elapsed time counter** visible
- "Analysis running..." text — no fake progress bar, no percentage, no timer-driven animation
- `run_id` / `request_id` displayed as soon as available

Post-success:
- execution panel shows `completed` with `run_id`
- verdict panel renders full FinalVerdict + ticket_draft
- usage accordion enabled (fires `GET /runs/{run_id}/usage`)
- submission panel remains navigable but read-only
- "New Analysis" reset action available

Post-failure:
- execution panel shows `failed` with error detail (normalized from mixed `detail` shape)
- verdict panel shows **"No verdict — run failed"** (disabled/greyed, not empty, not hidden)
- submission panel remains navigable and read-only
- explicit "Retry" action (user-driven only, no auto-retry)
- `run_id` / `request_id` preserved if available from error payload

### Verdict panel

- Full `FinalVerdict` at expert density: `final_bias`, `decision`, `approved_setups`, `no_trade_conditions`, `overall_confidence`, `analyst_agreement_pct`, `arbiter_notes`
- `ticket_draft` as secondary output
- **Disabled with "No verdict — run failed" on failure state** (DESIGN_NOTES §1.6)
- Never implies partial output exists on a terminal failed state

### Usage accordion (DESIGN_NOTES §1.7)

- Positioned **inline below Verdict** (not a separate navigation target)
- Loads from `GET /runs/{run_id}/usage` after successful completion
- Closed by default, expandable on click
- Tolerates empty-but-valid usage (`artifact-missing` modifier, not error)
- Handles `artifact-missing` gracefully — "Usage data unavailable" message, not crash
- Usage fetch failure is a warning only — must not block verdict rendering

### Streaming extensibility (design constraint, not implementation)

Do not implement streaming in this PR. But:
- the execution panel's vertical layout must accommodate a future event log below the spinner
- the state machine type includes `partial` for future use
- the hook layer must not be structured in a way that makes adding `useAnalysisStream` painful later
- a comment in the execution panel should mark where streaming events would render

### 7. Implement Journey → Analysis escalation

Journey Studio §6.6 defines a warm handoff: context travels with the user.

Implement:
- route `#/analysis` accepts an optional `?asset=SYMBOL` query parameter
- when `asset` present: pre-populate instrument field, show provenance breadcrumb ("Analysis Run · {SYMBOL} · Escalated from Journey Studio"), show "Return to Journey" link (`#/journey/{symbol}`)
- when `asset` absent: blank form, no provenance breadcrumb
- header context per DESIGN_NOTES §1.8: always shows provenance when escalated

Add escalation action in Journey Studio if not already present — a button or link in the Journey action area that navigates to `#/analysis?asset={symbol}`.

Handle safely:
- asset parameter exists → pre-populate instrument
- asset parameter missing → blank form, no provenance
- asset parameter invalid → form usable, no crash

### 8. Test properly

Add:
- **State machine unit tests** — valid transitions, invalid transition rejection, `run_id` preservation, reset behavior, `partial` exists in type but not entered
- **Adapter unit tests** — response normalization, verdict mapping, usage empty-but-valid, error shape normalization (string detail, object detail), tab enablement derivation, post-run read-only derivation
- **Submission panel tests** — form inputs render, validation blocks invalid submit, read-only lock post-submit, multipart FormData construction
- **Execution panel tests** — idle, running with elapsed time, completed with run_id, failed with error detail
- **Verdict panel tests** — full verdict rendering at expert density, disabled on failure ("No verdict — run failed"), ticket_draft display
- **Usage accordion tests** — loaded, empty-but-valid, artifact-missing, accordion toggle
- **Run lifecycle integration tests** — submit → running → completed with verdict; submit → running → failed with error detail
- **Error handling tests** — string `detail`, object `detail`, preserved `run_id` from error payload
- **Escalation tests** — asset parameter → pre-populated instrument + provenance breadcrumb, no asset → blank form, "Return to Journey" link
- **Tab persistence tests** — all three tabs navigable post-completion, submission read-only but accessible
- **Navigation/route tests** — route render, parameter handling
- At least one **full submission → verdict end-to-end test** with mocked backend

No snapshots. Explicit assertions.

### 9. Docs closure

Update only the relevant docs:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Mark the phase accurately.
Do not overstate completion of later workflow phases (Journal & Review is PR-UI-6, not this PR).

---

## Acceptance bar

The PR is successful only if:
- `/analysis` is no longer a placeholder
- it uses real existing backend endpoint(s)
- `POST /analyse` is correctly submitted as multipart/form-data (not JSON)
- the run lifecycle state model matches UI_CONTRACT §7 (idle → validating → submitting → running → completed | failed)
- the state machine is a standalone testable module at `ui/src/workspaces/analysis/state/`
- the wait during `running` feels safe and honest (elapsed time, not fake progress)
- all three tabs remain navigable post-run (tab persistence)
- verdict tab shows "No verdict — run failed" on failure (not empty/hidden)
- usage accordion is inline below verdict, tolerates empty-but-valid
- mixed `detail` error shapes handled without crash
- `run_id` / `request_id` preserved across all states including failure
- no auto-retry on submission failure
- Journey → Analysis escalation works with provenance breadcrumb and return link
- streaming is not implemented but execution panel can accommodate it later
- `partial` exists in state machine type but is not entered or rendered
- no backend files changed
- tests pass
- docs updated accurately

---

## Final output format

When complete, return:

1. **Summary** — what Analysis Run now does
2. **Endpoint basis** — the exact existing backend endpoint(s) used, the multipart field names discovered, and why
3. **Files added / changed** — grouped by area (API, adapter, state, components, route, tests, docs)
4. **Architecture** — how API → Adapter → State Machine → UI layering is implemented
5. **State handling** — how each run lifecycle condition is handled
6. **Tab persistence** — how the three panels behave post-run
7. **Error handling** — how string vs object `detail` is normalized, how `run_id` is preserved
8. **Escalation** — how Journey → Analysis handoff works
9. **Streaming extensibility** — how the execution panel accommodates future streaming without redesign
10. **Tests** — count and coverage
11. **Verification** — typecheck, build, test results
12. **Deviations** — anything changed from the plan
13. **Suggested commit message**
14. **Suggested PR description**

---

## Quality bar

Analysis Run should feel like a deliberate expert tool — not a loading screen, not a legacy form, and not a settings page. The submission should feel like arming a trade decision. The wait should feel like confident patience, not anxiety. The verdict should feel like a complete expert briefing. If the run fails, the failure should be informative and recoverable, not a dead end.
