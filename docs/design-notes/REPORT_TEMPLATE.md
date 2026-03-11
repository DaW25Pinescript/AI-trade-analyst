# REPORT_TEMPLATE.md — Audit Report, Trade Ideation Journey V1.1

Use this template to produce the audit report. Fill in every section. Do not skip sections.

---

## 1. Executive Summary

**Overall result:** PASS / PASS WITH ISSUES / FAIL

**One-paragraph explanation:**
[Summarise what was checked, what the key findings were, and the basis for the overall result.]

**Top 3 risks:**
1. 
2. 
3. 

---

## 2. Pass/Fail Matrix

| Group | Area | Result | Evidence |
|-------|------|--------|---------|
| A | V1 UI non-regression | PASS / FAIL / PARTIAL | |
| B | Backend endpoint existence | PASS / FAIL / PARTIAL | |
| C | Backend response shape conformance | PASS / FAIL / PARTIAL | |
| D | Triage/bootstrap truth | PASS / FAIL / PARTIAL | |
| E | Save semantics | PASS / FAIL / PARTIAL | |
| F | Persistence durability | PASS / FAIL / PARTIAL | |
| G | Service/adapter architecture | PASS / FAIL / PARTIAL | |
| H | Snapshot completeness | PASS / FAIL / PARTIAL | |

---

## 3. Critical Findings

> Only findings that block acceptance. If none, write "None."

| ID | Area | Description | Evidence | Required fix |
|----|------|-------------|---------|-------------|
| C-1 | | | | |

---

## 4. High Findings

> Major contract violations that must be in the follow-up patch.

| ID | Area | Description | Evidence | Remediation |
|----|------|-------------|---------|------------|
| H-1 | | | | |

---

## 5. Medium / Low Findings

| ID | Severity | Area | Description |
|----|---------|------|------------|
| M-1 | Medium | | |
| L-1 | Low | | |

---

## 6. Evidence Log

> One entry per checked item. Reference file paths, routes, JSON, console output, or screenshots.
> **A PASS without evidence is invalid and must be downgraded to PARTIAL or FAIL.**

| Check | Evidence type | Location / content |
|-------|--------------|-------------------|
| | | |

---

## 7. Required Fixes Before Acceptance

> Concrete remediation list for all Critical findings. High findings go in the follow-up patch section below.

**Critical fixes (must resolve before acceptance):**

1. 

**Follow-up patch (High findings — resolve in next PR):**

1. 

---

## 8. Go / No-Go Recommendation

**Decision:** Accept / Accept with follow-up patch / Reject pending fixes

**Rationale:**
[One paragraph explaining the decision.]

**Follow-up patch scope (if applicable):**
[List any High findings that must be addressed in the next PR before the system is considered production-ready.]
