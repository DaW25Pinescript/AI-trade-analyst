# CONSTRAINTS.md — Post-Merge Audit, Trade Ideation Journey V1.1

## Auditor constraints

These rules govern how the audit is conducted. They are not optional.

---

### 1. No PASS without evidence

Every PASS, FAIL, or PARTIAL verdict must be backed by at least one of:
- file path + function or class name
- route path + response shape or example
- saved JSON path on disk
- console or runtime error text
- OpenAPI route listing

Impressions and assumptions do not count as evidence.

---

### 2. No redesign suggestions during audit

The auditor must not suggest UI changes, architectural rewrites, or new features during the audit pass.

If a structural violation is found, document it as a finding with severity. Do not propose a fix that changes the accepted V1.1 design.

Exception: if a Critical finding requires a one-line targeted fix to unblock acceptance, that fix may be described. It must be scoped to the exact violation — no broader changes.

---

### 3. Fake save success is an immediate blocker

If `success: true` is returned or shown to the user without a confirmed disk write, that is a Critical finding. Stop the audit on persistence and escalate immediately.

Do not continue to mark other persistence checks as PASS if the save path is fake.

---

### 4. Browser-only persistence is a blocker

If `localStorage`, `sessionStorage`, or `IndexedDB` is the primary persistence layer for saved records, that is a Critical finding. The constraint from V1.1 CONSTRAINTS.md is absolute: browser-only persistence is not acceptable.

---

### 5. Placeholder data without demo marker is a blocker

If the dashboard or journey bootstrap is serving placeholder/mock data without a visible `data_state: "demo"` marker in the UI, that is a Critical finding.

If the data is genuinely unavailable and the UI shows a truthful unavailable state, that is acceptable.

---

### 6. data_state must not be dropped

If `data_state` is present in the backend response but absent from the component render layer, that is a High finding. The entire chain must preserve it: backend response → adapter output → store → component.

---

### 7. Casing violations are High severity

If components reference `snake_case` field names directly, or if adapters pass `snake_case` into the store, that is a High finding. The casing convention from CONTRACTS.md Section 5 is locked.

---

### 8. Scope creep is not a finding

If the implementation added something outside V1.1 scope that does not violate any contract or constraint, document it as a Low observation — not a finding. Do not escalate out-of-scope additions unless they break something.

---

## Severity guide

| Level | Definition |
|-------|-----------|
| **Critical** | Blocks acceptance completely. Must be fixed before merge is called accepted. |
| **High** | Major contract violation but localized. Does not block acceptance but must be in the follow-up patch. |
| **Medium** | Usable but incomplete. Contract partially met. |
| **Low** | Non-blocking polish issue — no contract impact. |

### Critical examples
- No real disk persistence
- Fake save success (`success: true` with no file write)
- Missing Journey endpoint
- Placeholder data active without `demo` marker
- Blocking regression in V1 UI (broken stage, broken gate, broken route)

### High examples
- Wrong endpoint response shape vs CONTRACTS.md
- Casing boundary broken (components consume `snake_case`)
- `data_state` dropped at adapter or component layer
- Journal/review still reading placeholder arrays
- Decision snapshot immutability not enforced

### Medium examples
- Stale/partial banners missing from UI
- Weak empty-state truthfulness (shows nothing instead of explicit unavailable state)
- Backend readiness edge cases not handled

### Low examples
- Noisy logs
- Minor wording inconsistencies
- Non-blocking cosmetic differences that don't affect contracts
