# PR-UI-3 Implementation Prompt

You are implementing **PR-UI-3 — Shared Component Extraction and Hardening** for the AI Trade Analyst repo.

## Context
PR-UI-1 created the React + TypeScript + Tailwind shell in `ui/`.
PR-UI-2 replaced the triage placeholder with a real Triage Board using live backend data, a trust strip, feeder health, shared feedback/state/layout components, and TanStack Query hooks.

The next step is **not** another workspace yet. The next step is to turn the PR-UI-2 output into a more disciplined reusable frontend foundation.

## Your task
Refine the frontend structure inside `ui/` so that the shared layer is clearer, safer, and more reusable **without** expanding scope into Agent Ops, Journey, Analysis, Journal, Review, or backend work.

This is an extraction/hardening PR, not a feature-expansion PR.

## Primary goals
1. Audit the current frontend surfaces created by PR-UI-2.
2. Tighten ownership boundaries between:
   - `ui/src/app/`
   - `ui/src/shared/`
   - `ui/src/workspaces/triage/`
3. Keep genuinely reusable primitives in `shared/`.
4. Move or split triage-specific code that does not belong in `shared/`.
5. Improve naming, prop coherence, exports, and tests where that directly helps reuse.
6. Preserve all current Triage Board behavior.

## Strong guidance
- Extract only from evidence already present in the codebase.
- Do not invent a giant design system.
- Do not introduce new tools or frontend frameworks.
- Do not change backend code or API shapes.
- Do not add Agent Ops or other workspace implementation.
- Do not rewrite the Triage Board into abstractions that are harder to understand.

## Specific review targets
Please inspect and make grounded decisions about:
- `DataStateBadge`
- `StatusPill`
- `TrustStrip`
- `FeederHealthChip`
- `PanelShell`
- `LoadingSkeleton`
- `EmptyState`
- `UnavailableState`
- `ErrorState`
- `EntityRowCard`
- `useWatchlistTriage`
- `useTriggerTriage`
- `useFeederHealth`
- triage view-model adapter ownership
- shared export surfaces and import-path clarity

`EntityRowCard` is the most likely candidate to move out of `shared/` or be split into a smaller shared primitive plus a triage-owned wrapper. Make a disciplined call based on the current code, not hypothetical future screens.

## Deliverables
- updated frontend file structure inside `ui/`
- any justified file moves / splits / prop refinements
- stronger tests around shared surfaces and extraction-sensitive behavior
- documentation closure updates in:
  - `docs/AI_TradeAnalyst_Progress.md`
  - `docs/specs/ui_reentry_phase_plan.md`
  - `ui/README.md` if structure guidance changed

## Acceptance bar
The PR is successful only if:
- the Triage Board still works on real backend data
- Run Triage still works
- loading/ready/empty/stale/unavailable/demo-fallback/error handling still works
- typecheck/build/tests all pass
- the shared layer is visibly cleaner and better owned
- no new backend or workspace scope is introduced

## Output format
Provide:
1. A concise implementation summary
2. File-by-file change list
3. Verification results (`typecheck`, `build`, `test`)
4. Any deviations from scope
5. Suggested commit message
6. Suggested PR title and PR description
