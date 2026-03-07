# CLAUDE_CODE_PROMPT_AUDIT_V1.1.md — Audit Kickoff

## Your role

You are conducting a formal post-merge acceptance audit for Trade Ideation Journey V1.1.

This is not a code review. This is not a refactor task. This is a phase-gate audit — your job is to determine whether the merged implementation satisfies the locked V1.1 requirements, and to produce a go/no-go recommendation.

---

## Read these files first, in order

Do not begin auditing until you have read all of them.

1. `OBJECTIVE.md` — what the audit is and what acceptance means
2. `CONSTRAINTS.md` — how the audit must be conducted, severity guide
3. `ACCEPTANCE_TESTS.md` — the full checklist, Groups A–H
4. `REPORT_TEMPLATE.md` — the exact output format you must produce

Also read these V1.1 implementation spec files for contract reference. These files should be in the repo — locate them before starting the audit:
5. `CONTRACTS.md` (V1.1 spec) — endpoint shapes, data_state values, casing convention (Section 5)
6. `OBJECTIVE.md` (V1.1 spec) — what V1.1 was supposed to deliver

If either file is not found at the repo root, search for it under `docs/`, `spec/`, or any subdirectory containing the other V1.1 spec files. Do not proceed without reading them — if they cannot be located, report that as a blocker before starting the audit.

---

## Audit run order

Work in this sequence. Do not skip steps.

**Step 1 — Group A regression sweep**
Run Group A checks first. If any fail, the overall result is FAIL. Document the failures and stop — do not continue to other groups until Group A is resolved.

Checks:
- UI loads at `http://127.0.0.1:8080/journey.html` with no blocking console errors
- All four routes render: `#/dashboard`, `#/journal`, `#/review`, one asset journey
- All seven stage keys present in the journey flow
- Gate enforcement blocks forward navigation when a gate is blocked
- `SplitVerdictPanel` shows three distinct panels
- FastAPI responds at `http://127.0.0.1:8000/health`

**Step 2 — Backend route audit (Group B)**
- Check OpenAPI docs at `http://127.0.0.1:8000/docs`
- Confirm all seven Journey endpoints are listed
- Confirm existing routes are untouched
- Confirm Journey router is a separate file registered in `main.py`
- Confirm `load_dotenv()` call ordering in `ai_analyst/api/main.py`

**Step 3 — Response shape audit (Group C)**
- Call each Journey endpoint and inspect the response
- Check field names against CONTRACTS.md Section 1
- Confirm `snake_case` throughout backend responses and persisted JSON

**Step 4 — Triage/bootstrap truth audit (Group D)**
- Inspect `app/lib/services.js` — confirm real endpoint calls, not mock arrays
- Inspect `app/lib/adapters.js` — confirm real payload mapping
- Test with empty `analyst/output/` — confirm unavailable state, not placeholder cards
- Confirm demo mode is marked, not silent

**Step 5 — Save semantics audit (Group E) — highest priority**
- Trace the save/freeze action from UI trigger to file write
- Confirm `POST /journey/decision` is called before success state is shown
- Confirm a physical file is created at `app/data/journeys/decisions/`
- Test duplicate `snapshot_id` — confirm rejection
- Confirm no `localStorage`/`sessionStorage`/`IndexedDB` as source of truth

**Step 6 — Persistence durability (Group F)**
- After a confirmed save, refresh the browser — confirm record in journal
- Restart FastAPI — confirm record still appears
- Confirm review page reads the same record

**Step 7 — Architecture audit (Groups G and H)**
- Trace one full data flow: backend response → adapter → store → component
- Confirm `data_state` is not dropped at any layer
- Confirm components do not call `fetch` directly
- Confirm `decisionSnapshot` shape has all required fields
- Confirm `systemVerdict`, `userDecision`, `executionPlan` are separate objects

**Step 8 — Produce report**
- Fill in `REPORT_TEMPLATE.md` completely
- Every PASS must have evidence
- Every finding must have a severity and remediation target
- Issue go/no-go recommendation

---

## Hard audit rules

- Do not mark PASS without evidence
- Do not suggest redesigns during the audit
- Do not fix issues during the audit — document them
- Treat fake save success as an immediate blocker — stop Group E and escalate
- Treat browser-only persistence as an immediate blocker
- Treat placeholder data without `demo` marker as an immediate blocker
- Do not broaden scope — audit V1.1 only

---

## Output

Produce the completed `REPORT_TEMPLATE.md` as your final output.

Every section must be filled. No section may be skipped.

The final line must be one of:
- **Accept**
- **Accept with follow-up patch** (list the patch scope)
- **Reject pending fixes** (list the critical fixes required)
