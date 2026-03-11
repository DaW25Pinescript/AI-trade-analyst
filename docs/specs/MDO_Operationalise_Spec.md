# Market Data Officer — Operationalise Phase 1 Spec

## Repo-Aligned Implementation Target

This phase establishes the first runtime scheduling layer for Market Data Officer by adding an APScheduler-driven refresh loop around the existing feed pipeline.

**Status:** ✅ Complete — 494/494 tests green  
**Current repo phase:** Operationalise Phase 2  
**Next phase spec:** `docs/specs/MDO_Operationalise_Phase2_Spec.md`  
**Date closed:** 9 March 2026

---

## 1. Purpose

Operationalise Phase 1 was the first phase where the runtime shape was genuinely new. Earlier phases proved the feed, contracts, routing, and packet assembly logic. This phase added the scheduler layer needed to run those pieces repeatedly without manual invocation.

The purpose of Phase 1 was to:

- add APScheduler as the accepted scheduling base
- define the scheduler runtime shape
- isolate jobs by instrument
- preserve last-known-good artifacts on failure
- keep the patch surface small and test-safe

This phase is complete. The repo should now treat this document as the closed record of the scheduler base, not as the active implementation target.

---

## 2. Scope

### In scope

- APScheduler installation and scheduler runtime introduction
- scheduler entrypoint shape
- per-instrument job isolation
- cadence configuration for refresh jobs
- schedule/run logging
- preservation of last-known-good artifacts on failure
- regression safety through existing and new tests

### Out of scope

- market-hours awareness
- alerting/notifications
- remote deployment/runtime guidance
- distributed scheduling
- cloud infrastructure
- major pipeline redesign

These out-of-scope items now belong to **Operationalise Phase 2**.

---

## 3. Repo-Aligned Assumptions

### What was already true before implementation

- The feed pipeline existed and could be invoked directly.
- MarketPacketV2 generation, provider routing, and packet assembly already worked.
- The repo needed a small, explicit scheduler layer rather than a broad runtime rewrite.

### Refresh cadence hypothesis

Initial cadence was expected to be simple, deterministic, and local-configurable rather than adaptive or distributed.

### Failure behavior hypothesis

A failed scheduled refresh should not destroy useful existing artifacts. The scheduler should preserve last-known-good outputs and record failure clearly.

---

## 4. Key File Paths

This phase centered on the scheduler/runtime surface around Market Data Officer and its tests. Exact implementation files are now part of the repo and should be audited directly when modifying the scheduler.

The historical intent was to touch only the smallest file set necessary:

- scheduler/runtime module(s)
- scheduler entrypoint
- minimal config/logging surface
- targeted tests

---

## 5. Current State Audit Hypothesis (Historical)

### What was already true

- Feed contracts and refresh/build functions existed.
- Provider routing and trusted instrument policy were already complete.
- Per-instrument isolation was already a design requirement.

### What likely remained

- Explicit scheduler module and CLI/runtime entrypoint
- schedule logging
- deterministic scheduler tests

### Core Operationalise question

How do we add a scheduler without destabilizing a codebase that already has strong test coverage and a clear packet pipeline?

Phase 1 answered that question by adding a narrow scheduler layer and keeping behavior explicit.

---

## 6. Scheduler Design

### 6.1 Runtime shape

APScheduler was chosen as the scheduler base. The runtime shape was intentionally simple:

- one scheduler service
- per-instrument jobs
- deterministic cadence config
- explicit startup entrypoint

### 6.2 No-overlap policy

The scheduler design aimed to avoid overlapping refresh work for the same instrument/job cadence unless explicitly allowed.

### 6.3 Job isolation

A failure in one instrument job should not crash the whole scheduler loop. Instrument jobs should fail independently and preserve usable state elsewhere.

### 6.4 Cadence config

Cadence is repo-configured and deterministic rather than dynamic or cloud-managed.

### 6.5 Last-known-good preservation

This rule remains in force for future phases: do not destroy useful artifacts because a newer refresh attempt fails.

### 6.6 Schedule logging

Scheduler behavior should be inspectable through explicit logs rather than inferred from silence.

---

## 7. Acceptance Criteria

Operationalise Phase 1 was complete when all of the following became true:

1. APScheduler was installed and importable.
2. A scheduler/runtime module existed.
3. A scheduler entrypoint existed.
4. Per-instrument jobs were isolated.
5. Existing tests remained green.
6. New scheduler-focused behavior was covered by tests.

These criteria are now satisfied.

---

## 8. Pre-Code Diagnostic Protocol (Historical Record)

Before Phase 1 implementation, the intended protocol was:

1. verify APScheduler availability
2. audit existing pipeline entrypoint
3. audit failure behavior in the pipeline
4. check existing logging infrastructure
5. run baseline tests
6. recommend startup/shutdown shape
7. report the smallest patch set

This section is retained as historical method, not as the active checklist.

---

## 9. Implementation Constraints

### 9.1 General rule

Keep the scheduler patch narrow. If a broad pipeline redesign is required, that is a scope violation.

### 9.2 Testing strategy

Protect the repo’s existing regression baseline first, then add targeted scheduler tests.

### 9.3 Code change surface

The intended change surface was limited to scheduler/runtime files, minimal config/logging, and tests.

---

## 10. Success Definition

Operationalise Phase 1 succeeded because the repo gained a scheduler base without disturbing the already-complete feed and packet architecture.

The outcome is:

- scheduled refresh exists
- scheduler behavior is testable
- last-known-good preservation remains intact
- the repo can now move to operational policy questions rather than scheduler existence questions

---

## 11. Why This Phase Matters

Without Phase 1, the repo had a feed pipeline but no clean runtime loop to operate it repeatedly. Phase 1 created the baseline scheduler foundation that all later operational maturity depends on.

---

## 12. Phase Roadmap

- **Operationalise Phase 1** — APScheduler feed refresh base — ✅ Complete
- **Operationalise Phase 2** — market-hours awareness, alerting, remote deployment — ⏳ Active (`docs/specs/MDO_Operationalise_Phase2_Spec.md`)
- **Next likely phase** — Security/API Hardening — authn/authz, timeout policy, error contract tightening — 🔜 Candidate

---

## 13. Diagnostic Findings (Closure Summary)

### Scheduler base implemented

Phase 1 delivered the APScheduler foundation and passed regression gates.

### Regression gate results

**494/494 tests green** at phase close.

### Operational posture after close

The scheduler exists, but intelligent closed-market handling, alerting, and remote deployment guidance remain the next workstream. Those concerns are intentionally deferred to Operationalise Phase 2.

---

## 14. Appendix — Recommended Agent Prompt

Use this document only for historical context or scheduler-base audits. For active implementation work, use:

- `docs/specs/MDO_Operationalise_Phase2_Spec.md` for current operationalisation work
- the canonical progress document for repo-wide sequencing
