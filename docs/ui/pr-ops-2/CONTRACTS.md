# CONTRACTS — PR-OPS-2

PR-OPS-2 must implement the contract already locked in:

- `docs/ui/AGENT_OPS_CONTRACT.md`
- `docs/ui/UI_CONTRACT.md` §10.6

This file restates only the implementation-critical rules.

## Endpoint 1 — `GET /ops/agent-roster`

Returns `AgentRosterResponse`.

### Required top-level structure

- `meta: ResponseMeta`
- `governance_layer: AgentSummary[]`
- `officer_layer: AgentSummary[]`
- `departments: Record<DepartmentKey, AgentSummary[]>`
- `relationships: AgentRelationship[]`

### Structural invariants

- Empty roster is invalid.
- v1 expects 2 governance entities and 2 officer entities, but this expectation is documented in prose and must not be encoded as tuple-only response typing.
- `departments` must use the contracted `DepartmentKey` union.
- Relationship records must reference valid roster ids.

### Roster entity rules

Each `AgentSummary` must conform to the contract, including typed department behavior and any optional fields exactly as documented.

## Endpoint 2 — `GET /ops/agent-health`

Returns `AgentHealthSnapshotResponse`.

### Required top-level structure

- `meta: ResponseMeta`
- `entities: AgentHealthItem[]`

### Health semantics

- poll-based snapshot only
- separate `run_state` and `health_state` dimensions must be preserved
- empty `entities` is valid on fresh start / no health observed yet
- degraded scenarios must be representable without collapsing the response shape

## Shared contract rules

### Error transport envelope

HTTP error responses must use:

```json
{
  "detail": {
    "code": "...",
    "message": "...",
    "retryable": false,
    "context": {}
  }
}
```

This is the contracted `OpsErrorEnvelope = { detail: OpsError }`.

### Response meta

`ResponseMeta` must follow the locked contract semantics, including:
- `data_state`
- timestamps / freshness fields if defined in the contract
- any source / generation metadata defined there

### Join rule

Every `AgentHealthItem.entity_id` must map to a roster `AgentSummary.id`.

### No speculative contract expansion

Do not add:
- trace/detail payloads
- run lineage structures beyond what health already contracts
- UI convenience fields not in contract
- control-plane fields

## Implementation note

If the implementation discovers a genuine mismatch or impossibility in the locked contract, surface it explicitly in the PR notes and docs closure rather than silently deviating.
