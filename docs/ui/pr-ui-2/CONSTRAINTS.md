# CONSTRAINTS — PR-UI-2

## Hard scope boundaries
This PR is intentionally narrow.

### In scope
- Triage Board page only
- Real-data wiring to existing triage endpoints
- Minimal shared UI primitives required by Triage
- Query / mutation handling for fetch + trigger-refresh
- Navigation handoff to Journey placeholder route
- Real handling of data/trust/error/loading states

### Out of scope
- Agent Operations UI or `/ops/*` work
- New backend endpoints
- Backend contract changes
- Journey Studio implementation
- Analysis Run implementation
- Journal / Review implementation
- Broad component-system refactor beyond what Triage needs
- Streaming / SSE / WebSocket behavior
- Full polling framework beyond what Triage genuinely requires
- Chart viewers, artifact inspectors, or Phase 3C work
- Big-bang legacy `app/` migration

## Contract discipline
- Do not infer contract shape from ad hoc backend code if it conflicts with the documented UI contract.
- Do not invent per-row `data_state` if the contract only supports board-level `data_state` plus row freshness derived from timestamps.
- Preserve mixed backend error detail behavior through the typed client.
- UI must remain resilient to empty, unavailable, or degraded payloads.

## Shared-component rule
Create shared components only when they are directly needed by Triage. Do not attempt PR-UI-3 early.

## Design rule
The page should feel like a trustworthy triage board, not a raw JSON viewer and not a decorative dashboard.

## Migration rule
All work stays in `ui/` and must coexist with the legacy `app/` without breaking it.
