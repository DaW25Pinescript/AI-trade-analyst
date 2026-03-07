# OBJECTIVE.md — Post-Merge Audit, Trade Ideation Journey V1.1

## What this audit is

A formal phase-gate audit run after V1.1 is merged. Its purpose is to confirm the merge delivers against the locked V1.1 requirements — not to review code quality generally, and not to suggest redesigns.

This is an acceptance audit. The output is a go/no-go decision.

---

## What the audit must confirm

Four things, in priority order:

1. **No V1 UI regression** — the accepted V1 surface is intact: dashboard, journey, journal, review, seven stages, gate enforcement, verdict layer separation
2. **Real triage and bootstrap wiring is active** — placeholder/mock data is no longer the active path
3. **Saves are backend-mediated and disk-backed** — in-memory store mutation is not treated as a completed save
4. **Truthful data-state handling is preserved end to end** — `data_state` flows from backend → adapter → store → component without being dropped or fabricated

---

## What the audit is NOT

- Not a code quality review
- Not a refactor opportunity
- Not a redesign task
- Not a speculative architecture review
- Not a scope expansion

If an issue is found, the auditor documents it and flags severity. The auditor does not fix it during the audit.

---

## Stack context (confirmed)

| Port | Service |
|------|---------|
| 8080 | UI — vanilla ES modules, `python -m http.server` |
| 8000 | FastAPI backend — `ai_analyst/api/main.py` |
| 8317 | Local Claude proxy — OpenAI-compatible |

---

## Persistence root (locked)

```
app/data/journeys/
  drafts/       journey_<journeyId>.json
  decisions/    decision_<snapshotId>.json
  results/      result_<snapshotId>.json
```

Any writes outside this root are a contract violation.

---

## Acceptance threshold

The merge is accepted only when:

- No Critical findings remain open
- Group A (regression) conditions hold
- Saves are confirmed disk-backed — not in-memory only
- Triage and bootstrap are confirmed real — not placeholder
- V1 UI is visually and structurally unchanged

PASS WITH ISSUES is acceptable only when all open findings are Medium or Low severity, and a follow-up patch is scoped and assigned.

FAIL means the merge must be reverted or patched before acceptance.
