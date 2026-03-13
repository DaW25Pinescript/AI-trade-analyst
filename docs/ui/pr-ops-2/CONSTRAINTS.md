# CONSTRAINTS — PR-OPS-2

## Hard scope boundaries

Implement only:

- `GET /ops/agent-roster`
- `GET /ops/agent-health`

Do not implement:

- `GET /runs/{run_id}/agent-trace`
- `GET /ops/agent-detail/{entity_id}`
- any POST/PUT/PATCH/DELETE Agent Ops endpoints
- any UI wiring or React changes
- any SSE, websocket, streaming, or long-polling behavior
- any new orchestration engine or runtime supervisor
- any control-plane behavior

## Behavioral constraints

- Endpoints must be **read-only** projections.
- Prefer deriving values from existing source-of-truth structures over inventing new persistence.
- Health is a **poll-based snapshot** only.
- Route behavior must follow `docs/ui/AGENT_OPS_CONTRACT.md` exactly.
- Error responses must use the contracted envelope.
- Do not return ad hoc fields outside the contract.

## Source-of-truth guidance

### `/ops/agent-roster`
Should be derived from stable repo/runtime truth such as:
- canonical role definitions
- analyst/officer/governance configuration
- known department mappings
- known relationships between entities

Avoid deriving roster from transient log evidence.

### `/ops/agent-health`
Should be derived from existing runtime/observability evidence such as:
- structured events
- recent runtime state
- scheduler/worker/runtime diagnostics already present in the repo
- currently known provider / execution / health indicators

Avoid inventing speculative health metrics that the repo cannot justify.

## Join rule

Every `AgentHealthItem.entity_id` must correspond to a roster `AgentSummary.id`.

- unknown health items are invalid
- missing health for a known roster item is allowed and should resolve to “no health data yet” semantics at the consumer layer

## Layering constraints

Keep implementation cleanly separated:
- route layer
- projection/service layer
- contract/serializer layer
- tests

Avoid embedding projection logic directly in route functions.

## Documentation closure

Update only the docs needed to record completion of the implementation phase, for example:
- `docs/AI_TradeAnalyst_Progress.md`
- `docs/specs/ui_reentry_phase_plan.md`

Do not reopen contract docs unless a true implementation mismatch is discovered. If one is discovered, document it explicitly rather than silently drifting.
