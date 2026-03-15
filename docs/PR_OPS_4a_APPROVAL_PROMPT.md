Diagnostic approved. Proceed with PR-OPS-4a — the agent-trace endpoint only.

This is the first of two sub-PRs. PR-OPS-4b (agent-detail) follows after this lands.

Read `docs/PR_OPS_4_SPEC_FINAL.md` in full before starting.
Treat it as the controlling spec. Your scope is §6 (agent-trace) and §13.1b (PR-OPS-4a sequence).
Do NOT implement §7 (agent-detail) — that is PR-OPS-4b.

---

Scope for this pass — PR-OPS-4a:

- `GET /runs/{run_id}/agent-trace` endpoint
- Trace response models (`ai_analyst/api/models/ops_trace.py`)
- Trace projection service (`ai_analyst/api/services/ops_trace.py`)
- Trace route added to existing `ai_analyst/api/routers/ops.py`
- Test fixtures (`tests/fixtures/sample_run_record.json`, `tests/fixtures/sample_audit_log.jsonl`)
- Trace tests (`tests/test_ops_trace_endpoints.py`)

ACs for this pass: AC-1 through AC-9, AC-18, AC-19, AC-20, AC-21, AC-22, AC-24, AC-25 (15 of 25)

---

One clarification before starting:

The `TraceEdge` type uses `from` and `to` as field names. PR-OPS-2 already handles the Python
reserved word collision via `from_` with alias `"from"` (using `model_dump(by_alias=True)` for
`EntityRelationship`). Confirm you will use the same alias pattern for `TraceEdge.from`.
Do not rename the JSON field.

---

Implementation sequence per spec §13.1b:

1. Create trace response models (`ops_trace.py`)
   - Verify: models import cleanly, no circular deps
2. Create test fixtures (sample_run_record.json, sample_audit_log.jsonl)
3. Implement trace projection service (`ops_trace.py`)
   - Read run_record.json (primary) + audit log {run_id}.jsonl (secondary for stances/overrides)
   - Map bare persona names → roster IDs (`{persona}` → `persona_{persona}`)
   - Audit log missing → degrade to data_state: "stale", stances/override details absent
   - TraceStage uses duration_ms, NOT started_at/finished_at
4. Add trace route to `ai_analyst/api/routers/ops.py`
   - Thin handler — same pattern as roster/health (validation + service handoff + JSONResponse)
   - Gate: 55/55 PR-OPS-2 baseline still pass
5. Write trace tests
   - Gate: all new tests pass + 55/55 baseline preserved
6. Update spec — flip trace AC cells in §11, note PR-OPS-4a complete

---

Named constraints confirmed by diagnostic:

- Flat `ResponseMeta` inheritance — `AgentTraceResponse(ResponseMeta)` — no data/meta wrapper
- Plain slug entity IDs — no namespace prefix
- `model_dump(by_alias=True)` for `TraceEdge.from` → `"from"`
- Persona ID mapping: `{persona}` → `persona_{persona}` in trace service only
- Audit log missing → degrade to `data_state: "stale"`, do not 500
- `duration_ms` per stage, NOT `started_at`/`finished_at`
- `_dev_diagnostics.jsonl` skipped entirely
- Stage vocabulary locked: `validate_input`, `macro_context`, `chart_setup`, `analyst_execution`, `arbiter`, `logging`
- TraceEdge types locked: `considered_by_arbiter`, `skipped_before_arbiter`, `failed_before_arbiter`, `override`
- Override semantics are best-effort derived in V1 (§6.9b)

Hard constraints:

- No pipeline changes — both sources are existing read-side artifacts
- No mutation, no new persistence, no SQLite, no new top-level module
- No frontend wiring — that is PR-OPS-5
- No agent-detail work — that is PR-OPS-4b
- No scheduler changes
- Deterministic fixture-based tests only — no live provider dependency in CI
- Bounded payloads: contribution.summary ≤ 500, override_reason ≤ 300, trace_edges ≤ 50, dissent_summary ≤ 500, edge.summary ≤ 300

---

Do not change any code until you have confirmed you have read the full spec.

On completion of PR-OPS-4a:
1. `docs/PR_OPS_4_SPEC_FINAL.md` — flip AC-1 through AC-9 + AC-18–AC-22 + AC-24–AC-25 to ✅
2. `docs/AI_TradeAnalyst_Progress.md` — note PR-OPS-4a complete, add test count row
3. Do NOT update AGENT_OPS_CONTRACT.md yet — that happens in PR-OPS-4b
4. Return a short completion summary: files created, test count delta, any assumption corrections

Commit all changes on one branch.
