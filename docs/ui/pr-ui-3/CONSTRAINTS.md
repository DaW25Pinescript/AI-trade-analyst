# CONSTRAINTS — PR-UI-3

## Hard scope boundaries
PR-UI-3 is a **frontend internal quality and reuse** PR.

It may:
- move, rename, or reorganize frontend files inside `ui/`
- refine component props and internal ownership boundaries
- extract common view-model or adapter helpers
- add tests and lightweight developer-facing documentation inside the frontend lane
- improve consistency of state handling, layout structure, and export surfaces

It must not:
- change backend code
- introduce or require new API endpoints
- alter API payload shapes
- add SSE, WebSockets, polling beyond what already exists, or streaming UI behavior
- implement Agent Ops
- implement Journey / Analysis / Journal / Review pages beyond placeholder status
- replace the Triage Board with an abstraction-heavy rewrite
- add speculative shared abstractions with no present evidence of reuse value

## Architectural rules
1. **Triage remains the proving workspace.**
   Do not damage or over-generalize the only real workspace to satisfy hypothetical future needs.

2. **Extract only from evidence.**
   A component/hook/util belongs in `shared/` only if it is already generic in behavior or can be made generic cleanly without distorting the Triage Board.

3. **Keep workspace logic close to the workspace.**
   View-model mapping and route/page orchestration stay in the triage workspace unless a smaller reusable helper clearly emerges.

4. **No contract drift.**
   Shared abstractions must still respect the documented UI contract, especially mixed error detail handling and explicit data-state semantics.

5. **No hidden phase-jumping.**
   Do not smuggle in Agent Ops, detailed design-system work, or a generic entity framework under the banner of "extraction."

## Preferred extraction mindset
Prefer:
- modest, grounded extraction
- clear ownership boundaries
- explicit imports/exports
- deterministic tests
- naming that reflects current repo reality

Avoid:
- premature generic frameworks
- clever component hierarchies nobody asked for
- large visual restyling
- introducing a new state-management model
