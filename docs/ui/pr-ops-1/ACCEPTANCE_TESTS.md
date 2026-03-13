# ACCEPTANCE TESTS — PR-OPS-1

## Merge criteria

### A. Scope integrity
- [ ] No backend code changed (zero Python files)
- [ ] No frontend code changed (zero TypeScript/React files)
- [ ] No existing endpoint contracts altered
- [ ] No Phase 7 endpoints contracted (trace, detail)
- [ ] No changes to existing core workspace contracts (triage, journey, analysis, feeder)

### B. Contract completeness — `/ops/agent-roster`
- [ ] Response shape fully specified with TypeScript-style types
- [ ] `AgentSummary` type defined with all fields typed
- [ ] `DepartmentKey` union defined with exactly four canonical values
- [ ] `EntityRelationship` type defined with allowed relationship types
- [ ] `visual_family` and `orb_color` specified as semantic tokens (not CSS/hex)
- [ ] `data_state` semantics defined (`live`, `stale`, `unavailable`)
- [ ] Empty/invalid roster behavior specified (not silently valid)
- [ ] Error contract specified as structured `OpsErrorEnvelope = { detail: OpsError }`
- [ ] Governance/officer layers typed as arrays, with current expected counts documented in prose rather than tuple syntax
- [ ] What backs the endpoint is stated (config/roster definitions)

### C. Contract completeness — `/ops/agent-health`
- [ ] Response shape fully specified with TypeScript-style types
- [ ] `AgentHealthItem` type defined with all fields typed
- [ ] `run_state` and `health_state` specified as separate dimensions
- [ ] All `health_state` values defined (`live`, `stale`, `degraded`, `unavailable`, `recovered`)
- [ ] All `run_state` values defined (`idle`, `running`, `completed`, `failed`)
- [ ] Polling model explicitly stated as poll-based snapshot only (no SSE/WebSocket)
- [ ] `data_state` semantics defined for the snapshot response
- [ ] Empty entities behavior specified (valid if system just started)
- [ ] Degraded behavior specified (health fails but roster succeeds → render structure with banner)
- [ ] Error contract specified as structured `OpsErrorEnvelope`
- [ ] What backs the endpoint is stated (Obs P2 events, scheduler, feeder health)
- [ ] Explicit roster ↔ health join rule specified

### D. Shared convention references
- [ ] Transport convention referenced (JSON, §5.1)
- [ ] Auth convention referenced (§5.6)
- [ ] Failure boundary taxonomy referenced (§11.5)
- [ ] Timeout/retryability referenced as simple reads (§12.2)

### E. Future endpoint acknowledgment
- [ ] `/runs/{run_id}/agent-trace` acknowledged as Phase 7, not contracted
- [ ] `/ops/agent-detail/{entity_id}` acknowledged as Phase 7, not contracted
- [ ] Both noted as requiring separate future contract work

### F. Contract test priorities
- [ ] Appendix lists minimum tests PR-OPS-2 must implement
- [ ] Tests cover response shape, department keys, relationship array, `data_state`, and structured error envelopes
- [ ] Tests cover run_state/health_state separation
- [ ] Tests cover empty and degraded scenarios
- [ ] Tests cover health `entity_id` values joining to roster `id` values

### G. Cross-references
- [ ] `UI_CONTRACT.md` updated with Agent Ops extension section (§10.6 or equivalent)
- [ ] Extension section states endpoints don't exist until PR-OPS-2 merges
- [ ] Extension section states Phase 3B operator-lane classification
- [ ] `docs/specs/README.md` updated with new contract doc link

### H. Documentation closure
- [ ] `docs/AI_TradeAnalyst_Progress.md` updated — Phase 4 contract work complete, backend MVP next
- [ ] `docs/specs/ui_reentry_phase_plan.md` updated if applicable

## Review questions
A reviewer should be able to answer "yes" to these:
1. Could someone implement the backend endpoints using only this contract doc?
2. Could someone build the React workspace using only this contract doc + the component plan?
3. Are the response shapes consistent with the existing schema design note where intentionally reused?
4. Is the polling-only decision for health clearly stated?
5. Does this contract avoid specifying backend implementation details?
6. Is the roster ↔ health join rule explicit enough to prevent silent mismatches?

## Explicit non-acceptance
The PR is **not** complete if:
- any Python or TypeScript files are changed
- any existing endpoint contract is altered
- Phase 7 endpoints are contracted
- the polling model for health is ambiguous
- error shapes fall back to freeform `detail` strings
- the contract contradicts existing `UI_CONTRACT.md` conventions
- `run_state` and `health_state` are collapsed into a single field
- the HTML prototype is referenced as a contract source
- `department` remains an untyped freeform string

## Suggested PR title
`docs: Agent Operations endpoint contract spec for roster and health`

## Suggested commit message
`docs(ops): define Agent Ops contract for /ops/agent-roster and /ops/agent-health`

## Expected PR summary format
1. Summary of what was documented
2. Contract document created (name and location)
3. Endpoints contracted (with key response shape decisions)
4. `UI_CONTRACT.md` changes
5. Reserved future endpoints noted
6. Contract test priorities listed
7. Verification that no code files changed
8. Suggested PR description
