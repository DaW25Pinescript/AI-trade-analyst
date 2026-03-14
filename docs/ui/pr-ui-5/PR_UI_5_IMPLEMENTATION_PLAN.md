# IMPLEMENTATION PLAN — PR-UI-5

## Implementation strategy

Build Analysis Run as a **real, contract-safe execution workspace** using existing endpoints, a deterministic run lifecycle state machine, and proven frontend patterns.

Analysis Run is the expert execution surface — not the default product path. Think of it like a manual override: the normal user flow is Triage → Journey → freeze. Analysis Run is for when you want to fire a direct multi-analyst analysis with full control over submission inputs and immediate verdict inspection.

The critical challenge in this workspace is **making a long-running synchronous HTTP call feel safe and informative without inventing progress that doesn't exist.** `POST /analyse` blocks until the pipeline finishes (30–90+ seconds). There are no partial events in sync mode. The UI must communicate "running, please wait" honestly — not fake a progress bar.

Do not overreach.
Streaming (`/analyse/stream`) is reserved for Phase 3B. Design the state machine and execution panel so streaming can be added without restructuring, but do not implement it now.

## Step 1 — Route and endpoint audit

Before coding, inspect:
- current backend routes for `/analyse` and `/runs/{run_id}/usage`
- the legacy `app/scripts/` UI that already submits to `/analyse` — determine the exact multipart field names
- `docs/ui/UI_CONTRACT.md` §7 (run state model), §8 (execution semantics), §9.1–9.4 (domain model), §10.1 (analysis endpoints), §11.1 (mixed detail errors), §12.2 (timeout/retry)
- `docs/ui/UI_WORKSPACES.md` §7 (Analysis Run workspace spec)
- `docs/ui/DESIGN_NOTES.md` §1.6 (tab persistence), §1.7 (usage panel), §1.8 (header provenance)
- `docs/ui/VISUAL_APPENDIX.md` (Analysis Run wireframe)
- existing `ui/` route structure
- `ui/src/shared/api/` — check if a stub or multipart helper exists

Confirm the real existing backend endpoint(s) that support Analysis Run.
Determine the exact multipart field names accepted by `/analyse`.
Record that basis in the PR summary.

## Step 2 — Define Analysis Run MVP shape

From the real available endpoints, define the minimum viable Analysis Run structure.

**Three-panel layout with tab persistence:**

1. **Submission panel** — instrument/context inputs, chart upload, submit button. Locks to read-only post-submission for "what did I submit?" verification.
2. **Execution panel** — run lifecycle state (idle → validating → submitting → running → completed | failed). Spinner with elapsed time. Preserved `run_id`. Reserved space for future streaming log.
3. **Verdict panel** — full FinalVerdict at expert density. Ticket draft. Disabled with "No verdict — run failed" on failure. Usage accordion below verdict.

All three tabs remain navigable post-run.

## Step 3 — Build run lifecycle state machine

Create at `ui/src/workspaces/analysis/state/runLifecycle.ts`.

This is a standalone, testable module — not embedded in hooks or adapters.

Type definition includes all canonical states (including `partial` for future streaming). Only synchronous transitions are active:

```
idle → validating → submitting → running → completed | failed
```

The state machine must:
- enforce valid transitions (reject invalid state jumps)
- preserve `run_id` / `request_id` across transitions
- expose typed transition actions
- support reset (completed → idle, failed → idle)

## Step 4 — Build API layer

Create analysis API functions. Determine whether to extend `ui/src/shared/api/` for multipart support or use a workspace-local function.

Functions:
- `submitAnalysis(formData: FormData)` — `POST /analyse` as multipart/form-data
- `fetchRunUsage(runId: string)` — `GET /runs/{run_id}/usage` as JSON

The error handler must normalize mixed `detail` shapes (string or object) and preserve `run_id` / `request_id` from failure payloads.

## Step 5 — Build workspace adapter

Create at `ui/src/workspaces/analysis/adapters/analysisAdapter.ts`.

Responsibilities:
- map backend responses → UI view models
- normalize verdict to expert density (all fields)
- normalize usage (tolerate empty-but-valid)
- normalize error shapes into stable display model
- derive tab enablement, post-run read-only, usage availability

## Step 6 — Implement Analysis Run UI

Build components in `ui/src/workspaces/analysis/`.

Reuse shared system where appropriate (`PanelShell`, feedback components, `StatusPill`).

### The submission form
Multipart/form-data with fields discovered in Step 1. Local validation before dispatch. Locks to read-only after submission.

### The execution panel (the critical interaction)
- `idle`: form interactive, "Submit to see verdict"
- `running`: form locked, spinner with elapsed time, "Analysis running..."
- `completed`: `run_id` displayed, verdict panel active, usage accordion fires
- `failed`: error detail displayed, verdict panel shows "No verdict — run failed", retry available

No fake progress. No auto-retry.

### The verdict panel
Expert density — every FinalVerdict field visible. Ticket draft as secondary output. Disabled/greyed on failure.

### Usage accordion
Inline below verdict. Closed by default. Tolerates `artifact-missing`. Does not block verdict rendering.

### Streaming extensibility
Leave vertical space in execution panel. Include a comment marking where streaming events would render. Do not implement SSE.

## Step 7 — Implement Journey → Analysis escalation

- `#/analysis?asset=SYMBOL` pre-populates instrument and shows provenance breadcrumb
- "Return to Journey" link navigates to `#/journey/{symbol}`
- No asset parameter → blank form, no provenance
- Add escalation action in Journey Studio if not present

## Step 8 — Test

Add tests covering: state machine transitions, adapter normalization, submission form, execution lifecycle, verdict rendering, usage accordion, error shapes, escalation/navigation, tab persistence, and at least one end-to-end submission → verdict flow.

No snapshots. Explicit assertions.

## Step 9 — Docs closure

Update:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Do not overstate later phases.

## Design guidance

### The run is a commitment, not a preview
Once submitted, the pipeline is running. The shift from interactive form to locked-and-waiting must feel deliberate — like pulling the trigger on a trade.

### Honesty about the wait
No fake progress bars. Spinner + elapsed time + "Analysis running..." is more honest than a progress indicator on a timer.

### Verdict at expert density
This is the expert surface. Show every FinalVerdict field. Don't summarize or hide fields.

### Tabs are memory, not navigation
All three tabs stay navigable post-run. The user must be able to flip back to Submission and verify "did I upload the right chart?"

### Multipart is not JSON
This is the only workspace that submits multipart/form-data. Handle it explicitly.
