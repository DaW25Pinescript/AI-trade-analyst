# ACCEPTANCE TESTS — PR-OPS-2

PR-OPS-2 is complete only when all of the following are true.

## 1. Docs contract implemented, not reinterpreted

- `GET /ops/agent-roster` exists.
- `GET /ops/agent-health` exists.
- Response payloads conform to `docs/ui/AGENT_OPS_CONTRACT.md`.
- No trace/detail endpoints are added.

## 2. Roster response invariants hold

Tests verify that:
- top-level response shape matches the contract
- roster is non-empty
- `governance_layer` exists and contains valid `AgentSummary` objects
- `officer_layer` exists and contains valid `AgentSummary` objects
- `departments` keys match `DepartmentKey`
- department values are arrays of valid `AgentSummary`
- `relationships` reference valid roster ids only
- v1 governance/officer expected counts are documented but not hard-coded as tuple-only transport constraints
- `data_state` reflects config source freshness

## 3. Health response invariants hold

Tests verify that:
- top-level response shape matches the contract
- health uses a poll-based snapshot model
- `entities` is an array
- empty `entities` is allowed on fresh start
- each health item preserves separate `run_state` and `health_state`
- all `entity_id` values map to roster ids
- missing health for a known roster entity is valid, not error
- `data_state` reflects observability data freshness

## 4. Degraded behavior is explicit and structured

Tests verify at least one degraded scenario such as:
- roster available, health partially unavailable
- route still returns a structured health snapshot consistent with the contract rather than collapsing into an ad hoc error shape

## 5. Error envelope is correct

Tests verify that HTTP errors use the contracted `OpsErrorEnvelope` shape.

If the implementation evolves the error shape from what was locked in PR-OPS-1 (e.g. `code`/`retryable`/`context` instead of `error`/`entity_id`), the change must be:
- documented in the PR description
- reflected in an update to `AGENT_OPS_CONTRACT.md`
- tested against the new shape

No freeform string-only `detail` responses are acceptable for these routes.

## 6. No control-plane leakage

Review confirms:
- no mutation endpoints added
- no config editing behavior introduced
- no prompt editing behavior introduced
- no orchestration/control actions exposed

## 7. No UI changes

Review confirms:
- no `ui/` changes
- no `app/` changes

## 8. Build / test hygiene

- All new deterministic tests pass
- All existing backend tests pass (no regressions)
- At minimum, the PR should provide command evidence for the specific backend tests added

## 9. Contract evolution handling

If the implementation discovers a genuine mismatch between the locked contract and the best implementation approach:
- the mismatch is documented in the PR description
- `AGENT_OPS_CONTRACT.md` is updated to reflect the implementation
- the change is flagged for PR-OPS-3 (React workspace) awareness

Silent contract drift is non-acceptance.

## 10. Docs closure

The PR updates the progress/spec tracking docs to mark PR-OPS-2 complete without reopening or drifting the contract docs unless an explicit mismatch note is documented.
