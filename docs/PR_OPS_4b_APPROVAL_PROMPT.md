Diagnostic approved. Proceed with PR-OPS-4b — the agent-detail endpoint only.

This is the second of two sub-PRs. PR-OPS-4a (agent-trace) has already landed.
Start from the PR-OPS-4a green baseline.

Read `docs/PR_OPS_4_SPEC_FINAL.md` in full before starting.
Treat it as the controlling spec. Your scope is §7 (agent-detail) and §13.1c (PR-OPS-4b sequence).
The trace endpoint (§6) is already implemented — do not modify it.

---

Scope for this pass — PR-OPS-4b:

- `GET /ops/agent-detail/{entity_id}` endpoint
- Detail response models (`ai_analyst/api/models/ops_detail.py`)
- Detail projection service (`ai_analyst/api/services/ops_detail.py`)
- Static profile registry (`ai_analyst/api/services/ops_profile_registry.py`)
- Detail route added to existing `ai_analyst/api/routers/ops.py`
- Detail tests (`tests/test_ops_detail_endpoints.py`)
- Contract doc update (`AGENT_OPS_CONTRACT.md` §6 promotion)

ACs for this pass: AC-10 through AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25 (16 of 25)

---

Implementation sequence per spec §13.1c:

1. Create detail response models (`ops_detail.py`)
   - Discriminated union: `type_specific` field keyed by `entity_type`
   - Four variants: PersonaDetail, OfficerDetail, ArbiterDetail, SubsystemDetail
   - Each variant has a `variant` tag field matching entity_type
   - Verify: models import cleanly alongside trace models
2. Create static profile registry (`ops_profile_registry.py`)
   - Purpose, responsibilities, type-specific fields per entity
   - Config-derived, parallel to `ops_roster.py` pattern (14 entities)
   - Source: hardcoded per entity — no separate config file needed
3. Implement detail projection service (`ops_detail.py`)
   - Reads from: roster (identity, department, visual_family) + health (run_state, health_state) + profile registry (purpose, responsibilities, type-specific) + bounded recent-run scan
   - Recent participation scan bound: max 20 run artifact dirs or 7 days, whichever smaller
   - Returned array capped at 5 most recent entries
   - Graceful degradation: health unavailable → return response with degraded data_state, not 500
4. Add detail route to `ai_analyst/api/routers/ops.py`
   - Thin handler — same pattern as roster/health/trace
   - Gate: all trace tests + 55/55 PR-OPS-2 baseline still pass
5. Write detail tests
   - One test per variant (persona, officer, arbiter, subsystem)
   - entity_type matches type_specific.variant (consistency check)
   - Unknown entity_id → 404 ENTITY_NOT_FOUND
   - Health unavailable → degraded data_state, not 500
   - Bounded payloads proven by test
   - Gate: all new tests pass + all trace tests + 55/55 baseline preserved
6. Update `AGENT_OPS_CONTRACT.md` — promote §6 from reserved to full contract (AC-23)
   - Add full endpoint specs matching implementation
   - Verify: no contradictions with §4/§5
7. Close spec and update docs

---

Named constraints confirmed by diagnostic:

- Flat `ResponseMeta` inheritance — `AgentDetailResponse(ResponseMeta)` — no data/meta wrapper
- Plain slug entity IDs — no namespace prefix
- Entity type discrimination via `entity_type` field, not by parsing ID string
- No separate profile registry module exists — create `ops_profile_registry.py` (static config)
- Entity metadata from roster: id, display_name, type, department, role, capabilities, supports_verdict, initials, visual_family, orb_color
- Fields NOT in roster that registry must provide: purpose, responsibilities, type-specific variant fields
- Roster is structural source of truth — detail augments, does not redefine hierarchy
- Recent participation scan bounded (20 dirs / 7 days max)

Hard constraints:

- No pipeline changes — read-side projection only
- No mutation, no new persistence, no SQLite, no new top-level module
- No frontend wiring — that is PR-OPS-5
- No trace endpoint modifications — that is PR-OPS-4a (already landed)
- No scheduler changes
- Deterministic fixture-based tests only — no live provider dependency in CI
- Bounded payloads: purpose ≤ 500, health_summary ≤ 300, contribution_summary ≤ 500, recent_participation ≤ 5, recent_warnings ≤ 10, policy_summary ≤ 500

---

Do not change any code until you have confirmed you have read the full spec.

On completion of PR-OPS-4b, close the spec and update docs per Workflow E:
1. `docs/PR_OPS_4_SPEC_FINAL.md` — mark ✅ Complete, flip all remaining AC cells,
   verify §18 findings are current
2. `docs/AI_TradeAnalyst_Progress.md` — update phase status, add test count row,
   update next actions (PR-OPS-5 unblocked), update debt register if applicable
3. `docs/ui/AGENT_OPS_CONTRACT.md` — promote §6 from reserved to full contract,
   add endpoint specs for BOTH trace and detail matching implementation
4. Review `system_architecture.md`, `repo_map.md`, `technical_debt.md`,
   `AI_ORIENTATION.md` — update only if this phase changed architecture,
   structure, or debt state
5. Cross-document sanity check: no contradictions, no stale phase refs
6. Return Phase Completion Report:
   - Phase: PR-OPS-4b (and PR-OPS-4 overall)
   - Test delta: [PR-OPS-4a count] → [final count]
   - Code changes: files touched, one-line each
   - Docs updated: which of E.2–E.6 were touched
   - Debt introduced / resolved

Commit all doc changes on the same branch as the implementation.
