# IMPLEMENTATION PLAN — PR-OPS-1

## Recommended execution order

### Step 1 — Read existing Agent Ops design docs
Before writing the contract:
- read `docs/ui/agent_operations_workspace.schema.refined.md` (design-level response shapes)
- read `docs/ui/agent_operations_component_adapter_plan.refined.md` (frontend component plan)
- read `docs/ui/DESIGN_NOTES.md` §5 (Agent Ops governance decisions — north-star question, negative scope, classification)
- read `docs/specs/ui_reentry_phase_plan.md` Phase 4 (contract requirements)
- read `docs/ui/UI_CONTRACT.md` §6 (state semantics), §11 (error contracts), §12 (timeout/retryability) for shared conventions

These documents are the inputs. The contract extension is the output.

### Step 2 — Create the Agent Ops contract extension document
Create `docs/ui/AGENT_OPS_CONTRACT.md` with:

**Header:**
- status: Active (becomes active once PR-OPS-2 merges the endpoints)
- scope: Agent Ops backend → UI contract extension
- depends on: `UI_CONTRACT.md` for shared conventions
- phase: 3B — operator observability / explainability / trust workspace

**Preamble:**
- reference the governing design note (`DESIGN_NOTES.md` §5) for product framing
- state that these endpoints do not exist until PR-OPS-2 merges
- state that the HTML prototype is visual reference only, not a contract source
- reference the schema design note for deeper context

**Shared types and conventions:**
- define `DepartmentKey`
- define `ResponseMeta`
- define `OpsError`
- define the locked transport envelope `OpsErrorEnvelope = { detail: OpsError }`

**Endpoint contracts:**
- `GET /ops/agent-roster` — full response shape, `data_state`, error contract, empty behavior, what backs it
- `GET /ops/agent-health` — full response shape, state semantics (`run_state` vs `health_state`), polling model, `data_state`, error contract, empty/degraded behavior, join rule, what backs it

**Shared convention references:**
- JSON transport (§5.1)
- auth assumptions (§5.6)
- failure boundaries (§11.5)
- timeout/retryability as simple reads (§12.2)

**Reserved future endpoints:**
- `/runs/{run_id}/agent-trace` — acknowledged, not contracted
- `/ops/agent-detail/{entity_id}` — acknowledged, not contracted
- note that these will be contracted in a separate Phase 7 PR

**Contract test priorities:**
- appendix listing minimum tests for PR-OPS-2

### Step 3 — Update UI_CONTRACT.md
Add a cross-reference section (suggested: §10.6) that:
- points to the new `AGENT_OPS_CONTRACT.md`
- lists the two contracted endpoints
- lists the two reserved future endpoints
- states these endpoints don't exist until backend PR merges
- states they are Phase 3B operator-lane surfaces

Do not rewrite or restructure any existing sections of `UI_CONTRACT.md`.

### Step 4 — Update progress hub
Update `docs/AI_TradeAnalyst_Progress.md`:
- note that Agent Ops contract spec is complete
- Phase 4 contract work done, backend MVP (PR-OPS-2) is next
- do not change any existing phase statuses except to advance Phase 4 contract work

### Step 5 — Update specs inventory
Update `docs/specs/README.md` (or equivalent) to include the new contract extension document.

### Step 6 — Verify document consistency
Before committing:
- confirm all type names match between the new contract and the existing schema design note where intentionally reused
- confirm `data_state` values are consistent with `UI_CONTRACT.md`
- confirm the transport error envelope is explicitly stated as `{ detail: OpsError }`
- confirm department typing uses the locked canonical key union
- confirm governance/officer layers are arrays, with current expected counts documented in prose rather than tuple syntax
- confirm the polling model statement matches `DESIGN_NOTES.md` §5 and the phase plan
- confirm the roster ↔ health join rule is stated explicitly
- confirm no existing endpoint contracts were altered

## Implementation notes
- The contract extension should be self-contained enough that someone implementing PR-OPS-2 can read it without also reading the full schema design note
- Response types should use TypeScript-style notation for clarity
- Keep the document focused on what the backend must return and what the frontend can expect — not on how the backend should be implemented internally
- The contract test priorities appendix is the bridge between PR-OPS-1 (contract) and PR-OPS-2 (implementation) — it tells the implementer what tests to write
