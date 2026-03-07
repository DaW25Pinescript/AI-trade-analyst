# ACCEPTANCE_TESTS.md

# AI Trade Analyst – Acceptance Tests
Version: 1.0

## 1. Purpose

These acceptance tests define what “done” means for the Trade Ideation Journey rollout. They are written to enforce staged delivery and to prevent the UI from drifting away from real repo contracts.

---

## 2. Phase 0 — Interface Audit and Contract Freeze

### AT-0.1 Interface inventory exists
Pass when:
- the repo has a documented inventory of journey-relevant inputs/outputs
- each producer/consumer can be traced to a real file/module

### AT-0.2 Availability matrix exists
Pass when:
- fields needed by the triage board and journey stages are marked as available, derivable, missing, unstable, deprecated, or adapter-required

### AT-0.3 Contract freeze exists
Pass when:
- a v1 frontend-safe contract layer is documented
- audit ambiguity is explicit rather than hidden

### AT-0.4 No major UI build before audit exit
Pass when:
- serious UI implementation is sequenced after the audit gate, not before it

---

## 3. Phase 1 — Domain Model and Store

### AT-1.1 Shared journey types exist
Pass when:
- the repo contains journey-related frontend types for status, stages, provenance, gates, snapshots, and core journey state

### AT-1.2 Semantic stage keys are used
Pass when:
- stage identity uses semantic names such as `market_overview` and `gate_checks`, not anonymous numeric tabs in the domain model

### AT-1.3 Journey store exists
Pass when:
- a typed journey store supports stage changes, asset selection, triage updates, notes, overrides, evidence, gates, verdict, decision, execution plan, snapshot creation, and reset

---

## 4. Phase 2 — Shell and Route Backbone

### AT-2.1 Route scaffolds exist
Pass when:
- the repo contains route/page stubs for dashboard, journey, journal, and review surfaces

### AT-2.2 Stage shell exists
Pass when:
- a reusable stage shell provides progress, content layout, and navigation actions

### AT-2.3 Progress stepper exists
Pass when:
- the journey has a visible stepper or equivalent stage navigation aid

---

## 5. Phase 3 — Triage Board

### AT-3.1 Landing is triage-first
Pass when:
- the default entry surface is a market/asset overview rather than a blank form

### AT-3.2 Triage cards explain relevance
Pass when:
- each triage card shows at least symbol, triage status, why-interesting tags, and a rationale placeholder or equivalent

### AT-3.3 Triage data is contract-safe
Pass when:
- card data is sourced through a typed service or explicitly marked mock interface rather than freehand component objects

---

## 6. Phase 4 — Context, Structure, and Macro Screens

### AT-4.1 Asset context stage exists
Pass when:
- the journey includes a stage for base analytical context and quick summary

### AT-4.2 Structure/liquidity stage exists
Pass when:
- the journey includes a stage for chart structure, liquidity, and evidence capture placeholders

### AT-4.3 Macro alignment stage exists
Pass when:
- the journey includes a stage for macro/news alignment and conflict framing

---

## 7. Phase 5 — Gate Checks

### AT-5.1 Gate states exist
Pass when:
- gate rows support `passed`, `conditional`, and `blocked`

### AT-5.2 Non-passed gates support justification
Pass when:
- blocked/conditional gate states can capture justification or rationale

### AT-5.3 Progression respects policy hooks
Pass when:
- the journey has a clear mechanism to disable or restrict forward movement when gate policy requires it

### AT-5.4 Gate UI treatment is structurally distinct from content cards
Pass when:
- blocked gate rows render a visually distinct state (e.g. error/warning colour token, not the default card style)
- the forward-progression action (Next / Continue) is visibly disabled or absent when any gate is `blocked`
- a `conditional` gate state renders differently from both `passed` and `blocked` (three distinct states are visually distinguishable)
- gate justification input is surfaced inline on the gate row, not buried in a separate settings panel

---

## 8. Phase 6 — Verdict and Plan

### AT-6.1 Verdict split exists
Pass when:
- the UI renders distinct sections for `systemVerdict`, `userDecision`, and `executionPlan`

### AT-6.2 Recommendation and commitment are separated in state
Pass when:
- the underlying state model does not collapse system output and human commitment into a single object

---

## 9. Phase 7 — Journal Capture and Snapshots

### AT-7.1 Evidence capture exists
Pass when:
- the journey supports file/evidence attachment in some baseline form

### AT-7.2 Decision snapshot exists
Pass when:
- the save flow produces a frozen decision snapshot object or explicit placeholder for one

### AT-7.3 Snapshot preview exists
Pass when:
- the user can review what is about to be frozen before save/commit

---

## 10. Phase 8 — Review Engine Surface

### AT-8.1 Review route exists
Pass when:
- a review page/surface exists in scaffold or implemented form

### AT-8.2 Planned vs actual framing exists
Pass when:
- the review surface is designed around comparison and policy review, not black-box model mystique

### AT-8.3 Override and gate pattern placeholders exist
Pass when:
- the review surface makes room for override-frequency and gate-failure analysis

---

## 11. Cross-Cutting Acceptance Tests

### AT-X.1 Provenance support exists
Pass when:
- AI-prefilled vs user-confirmed vs user-overridden vs manual fields are representable in the state model

### AT-X.2 Service layer exists and transport pattern is declared
Pass when:
- future API calls are stubbed or implemented through a thin typed service layer
- the service layer declares which transport pattern is in use: file-based (reads saved JSON artifacts) or API-based (calls a thin Python wrapper)
- no component contains raw fetch logic or direct Python execution

### AT-X.2a Transport pattern is consistent
Pass when:
- all service calls in the frontend use the same transport pattern declared in the audit
- no component bypasses the service layer to read files or call endpoints directly

### AT-X.3 Placeholder honesty is preserved
Pass when:
- placeholders are clearly marked and do not pretend to be final backend truth

### AT-X.4 Non-goals remain out of scope
Pass when:
- the first-pass implementation does not sprawl into multi-persona UI, advanced chart tooling, collaborative workflows, or opaque auto-learning claims

### AT-X.5 Visual language conformance
Pass when (per `UI_STYLE_GUIDE.md` Section 17):
- the UI clearly resembles the approved V1 mockup aesthetic — dark, premium, institutional workspace tone
- semantic state colors are used consistently: emerald for passed/aligned, amber for conditional, rose for blocked, indigo for AI/system context
- gate checks are rendered with visibly higher severity than normal content cards (distinct surface treatment, not just a color change)
- `SplitVerdictPanel` renders System Verdict, User Decision, and Execution Plan as three visually distinct sections
- AI-prefilled content and user-entered content are visually distinguishable via provenance markers
- snapshot and audit framing is preserved — nothing looks like mutable live state when it represents a frozen record
- no unnecessary visual invention outside the established component and color language

---

## 12. Phase 9 — Hardening and Policy Refinement

### AT-9.1 Contract conformance tests exist
Pass when:
- at least one test per journey stage validates that required contract fields are present in the service layer response
- missing or `undefined` fields from the backend do not silently produce broken UI state

### AT-9.2 Adapter gaps are resolved or explicitly deferred
Pass when:
- every field marked `requires_adapter` or `missing` in the availability matrix has a resolution: implemented, explicitly deferred with a dated note, or removed from scope
- no unresolved `requires_adapter` field is silently consumed as if it were `available_now`

### AT-9.3 Placeholder drift is cleaned
Pass when:
- no component or store field uses a hardcoded mock value that was intended as a temporary stub but was never replaced
- placeholder fields are either wired to real data, explicitly typed as `null | undefined` with a TODO, or removed

### AT-9.4 Review surface is not a black box
Pass when:
- every signal shown on the review surface can be traced to a specific field in a saved `decisionSnapshot` or `ExplainabilityBlock`
- no review insight is generated by freeform LLM summarisation without a traceable source field

---

## 13. Final Acceptance

The Trade Ideation Journey package is accepted when:
- the interface audit has grounded the contract layer
- the staged journey exists as a coherent frontend scaffold or implementation
- gate checks act as a real control boundary
- the system verdict and user decision are preserved separately
- a decision snapshot can be frozen for later review
- the review direction remains transparent, rule-based, and auditable
- transport pattern is declared and consistent across the service layer
- Phase 9 hardening tests pass
