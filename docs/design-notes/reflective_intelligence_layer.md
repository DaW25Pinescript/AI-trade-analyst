# AI Trade Analyst — Reflective Intelligence Layer
## Repo Design Note

**File:** `docs/design-notes/reflective_intelligence_layer.md`
**Status:** Future design direction — not an active implementation phase
**Scope:** Post-UI-reentry / post-Agent-Ops-foundation architecture
**Depends on:** Run-record architecture (exists), Observability Phase 2 (closed), Journal & Review workspace (pending Phase 6), Agent Operations observability (pending Phases 4–7), sufficient historical run volume
**Does not change:** Current UI re-entry implementation scope, Triage-first React sequencing, Agent Ops Phase 3B classification, or any active PR target

---

## 1. Purpose

This design note defines a future architecture direction for AI Trade Analyst: a **Reflective Intelligence Layer** that reviews historical system behaviour, surfaces structured patterns, generates bounded hypotheses, and proposes auditable policy improvements for human approval.

This is **not** a new trading engine and **not** an autonomous self-modifying AI system.

Its purpose is narrower and more realistic:

- turn run records into a disciplined review substrate
- help operators understand where the analytical system is weak or drifting
- convert ad hoc tuning into evidence-backed policy proposals
- preserve human control over all risk-relevant change

The system goal is to evolve from:

**signal generator → decision-support system → self-reviewing analytical desk**

without crossing into unsupervised or self-authorising system behaviour.

---

## 2. Place in the Repo

This note belongs in `docs/design-notes/`, not in the active UI implementation lane or the specs inventory.

That placement matters.

The repo is currently in a **UI re-entry phase** with the following locked sequencing (per `docs/specs/ui_reentry_phase_plan.md`):

| Phase | Scope | Status |
|-------|-------|--------|
| Phase 0 | UI Re-Entry Governance | ✅ Complete |
| Phase 1 | React App Shell + Triage Route | ✅ Complete |
| Phase 2 | Triage Board MVP (component seed) | ✅ Complete |
| Phase 3 | Shared Component Extraction | ⏳ Pending |
| Phase 4 | Agent Ops Contract + Backend MVP | ⏳ Pending |
| Phase 5 | Agent Ops React MVP | ⏳ Pending |
| Phase 6 | Journey Studio + Analysis Run + Journal & Review | ⏳ Pending |
| Phase 7 | Agent Ops Trace + Detail | ⏳ Pending |

The Reflective Intelligence Layer should be treated as:

- a **future architecture driver**, not a prerequisite for any current phase
- a **post-foundation review/governance layer**, not a first-wave UI dependency
- a **consumer of run artifacts and operator observability**, not a replacement for Agent Ops or Journal & Review

### Practical classification

This work becomes viable once the repo has:

1. **Structured run records with artifact provenance** — already exists post-Observability Phase 2 (structured JSON events across scheduler, feeder, triage, graph orchestration, and analyst pipeline lanes)
2. **Sufficient historical run volume** — a volume threshold, not a code dependency; pattern detection requires enough runs to distinguish signal from noise
3. **A readback surface for human review** — Journal & Review workspace (Phase 6) provides the decision/outcome readback that the reflective layer consumes
4. **Operator observability surfaces** — Agent Operations (Phases 4–7) provides the trust/explainability context that makes reflective findings actionable

Conditions 1 is already met. Conditions 2–4 are on the current roadmap. Until all four are satisfied, this layer remains a design note and future implementation track.

---

## 3. Relationship to Agent Ops and UI Workspaces

The Reflective Intelligence Layer should not compete with the current UI roadmap. It should **sit behind it** and eventually **feed it**.

### 3.1 Agent Ops relationship

Agent Ops is the operator-facing **observability / explainability / trust workspace** (DESIGN_NOTES.md §5).

Its north-star question is:

> **Why should I trust this system right now?**

The Reflective Intelligence Layer extends that into a slower, historical, governance-oriented question:

> **What should this system learn from its own audited history, and what disciplined improvement should a human consider next?**

The relationship:

- **Agent Ops** = current-state trust, diagnostics, participation, failures, drift hints
- **Reflective Layer** = historical review, pattern surfacing, hypothesis formation, policy proposals

Agent Ops answers:

- Who participated?
- What happened in this run?
- Why did the system reach this verdict?
- Where is trust weakened right now?
- What needs attention operationally?

The Reflective Layer answers:

- What weakness recurs over time?
- Under which conditions does it recur?
- What hypothesis best explains it?
- What bounded policy proposal might improve it?
- What evidence threshold must be met before a human should even consider changing policy?

### 3.2 Journal & Review relationship

Journal & Review (Phase 6) is the human-facing readback lane for decisions and outcomes.

The Reflective Layer should eventually consume:

- run records
- review artifacts
- decision snapshots
- outcome snapshots
- after-action review metadata

That makes Journal & Review a key evidence source rather than a separate conceptual island.

### 3.3 UI implication

This design note does **not** add immediate UI scope.

It does, however, imply future UI surfaces such as:

- a review diagnostics board
- policy proposal queue
- evidence cards for recurring weak points
- approval / reject / sandbox workflow panels
- before/after comparison views for approved policy changes

Those are later surfaces. They should not be folded into any current phase or used to expand UI implementation scope prematurely.

---

## 4. Foundation Already in Place

This concept is realistic because the repo already has the beginning of the right substrate.

### What exists now

The **run-record / audit-trail architecture** built through Observability Phases 1–2 provides:

- stage execution traces
- analyst participation data
- arbiter verdicts
- confidence outcomes
- failure points
- artifact provenance
- model/provider usage via `llm_routing.yaml` and ResolvedRoute contracts
- structured observability events (16 event codes under 5 canonical categories)
- scheduler lifecycle events
- feeder ingest events

The **packaging and import stability** work (TD-3) ensures these artifacts are accessible through a proper Python packaging model rather than fragile path hacks.

The **centralised enum definitions** (TD-5) ensure verdict, confidence, and alignment values are consistent across the codebase — a prerequisite for meaningful cross-run comparison.

Without this foundation, reflective improvement would be guesswork. With it, the repo can support historical review and structured policy discussion.

---

## 5. What the Reflective Layer Is

The Reflective Intelligence Layer is a **bounded review-and-governance architecture** composed of four logical stages.

### Stage A — Review Engine

The Review Engine processes historical run records and review artifacts to surface structured patterns.

Example questions:

- Where does confidence repeatedly collapse?
- Which instruments, sessions, or regimes produce repeated NO_TRADE outcomes?
- Which personas rarely influence the final verdict?
- When do arbiter overrides spike?
- Which providers introduce repeated latency or degradation?

Example outputs:

- recurring low-confidence clusters
- disagreement frequency by regime
- persona influence distribution
- veto concentration by instrument/session
- degraded dependency hotspots
- routing anomaly summaries

The Review Engine is **diagnostic**, not prescriptive.

### Stage B — Hypothesis Engine

The Hypothesis Engine proposes explanations for recurring weak patterns.

Example hypotheses:

- Friday London low-confidence clusters are driven by insufficient macro context
- one persona is overweighted relative to its observed value contribution
- specific NO_TRADE spikes align with stale upstream artifacts rather than true market ambiguity
- a provider fallback path is degrading confidence more than expected

Hypotheses are not truth. They are structured, testable explanations anchored to evidence windows.

### Stage C — Policy Recommendation Engine

The Policy Recommendation Engine converts validated hypotheses into bounded proposals.

Examples:

- adjust analyst weighting
- change quorum threshold
- refine macro-context weighting
- tighten or relax a gating rule
- alter a confidence downgrade threshold
- revise a prompt or explanation rubric
- add a new observability alert or review trigger

Every proposal must include:

- proposal identifier
- target parameter or policy surface
- current value
- proposed value
- reason
- evidence window
- regime segmentation
- confidence in the proposal
- approval required flag
- reversibility metadata

### Stage D — Human-Governed Adaptation

No policy change applies automatically.

A human operator must be able to:

- approve
- reject
- request more evidence
- sandbox-test
- run before/after comparison
- roll back a previously approved change

This preserves the repo's most important governance principle:

**the system may recommend; the human authorises.**

---

## 6. What the Reflective Layer Is Not

To prevent scope drift and unrealistic expectations, the following are explicitly out of scope:

- autonomous trading intelligence
- automatic parameter mutation in production
- self-evolving strategies without review
- black-box optimisation loops
- hidden prompt drift
- unsupervised learning that changes trade policy on its own
- a replacement for explicit system specs, contracts, or human judgement

This is a **review-and-proposal layer**, not a self-directing machine.

---

## 7. Proposed Repo Role and Future Lane

The Reflective Layer should be treated as a future program of work that bridges:

- **Agent Ops** (operational trust + explainability)
- **Journal & Review** (decision and outcome readback)
- **governance / policy refinement** (human-approved system improvement)

### Recommended roadmap position

This is:

- a **future roadmap item**, not an active implementation phase
- a **post-UI-reentry / post-Agent-Ops-foundation direction**
- a **review/governance architecture track**

It does not start until all four viability conditions from §2 are met.

---

## 8. Enhancements Beyond the Original Concept

The following refinements make the concept more repo-ready and safer.

### 8.1 Evidence hierarchy

Not all evidence should carry equal weight.

The reflective layer should rank evidence sources:

1. structured run records (highest — deterministic, machine-generated)
2. review artifacts / outcome records
3. observability logs and routing traces
4. provider / latency diagnostics
5. qualitative operator notes (lowest — useful but not authoritative)

That prevents loose narrative evidence from overriding hard execution evidence.

### 8.2 Regime-aware analysis by default

Every pattern and proposal should be segmentable by:

- instrument
- session
- volatility regime
- macro regime
- market-hours / freshness state
- provider condition / fallback usage

This reduces false generalisation and overfitting. The repo already has the building blocks for this: the MDO instrument registry governs per-instrument trust levels and provider policy, and the market-hours awareness from Operationalise Phase 2 provides session/freshness classification.

### 8.3 Confidence calibration lane

The system should not only ask whether verdicts were right or wrong.

It should also ask whether confidence was **well-calibrated**.

Examples:

- high-confidence calls with weak realised edge
- repeated medium-confidence calls that actually perform best
- systematic overconfidence when one persona dominates

This is one of the most useful long-term review surfaces for a multi-analyst system. Think of it as position-sizing validation — if the system says "high confidence" but outcomes are no better than medium, the confidence signal is broken regardless of directional accuracy.

### 8.4 Persona contribution and dead-weight detection

A mature review layer should quantify:

- contribution frequency
- contribution usefulness
- repeated caution value
- repeated noise generation
- dead-weight personas with minimal influence

This complements Agent Ops maintenance/drift diagnostics and makes persona architecture review evidence-based rather than intuition-based.

### 8.5 Proposal registry and governance workflow

Policy proposals should live in a formal registry with states:

- proposed
- evidence-insufficient
- under-review
- sandbox-approved
- rejected
- promoted
- rolled-back

That gives the repo an institutional memory of why policies changed.

### 8.6 Sandbox and replay-first validation

Before any proposal affects live analysis policy, it should be testable via:

- historical replay
- segmented comparison windows
- before/after metric snapshots
- explicit rollback path

### 8.7 Drift and regression watch

Approved policy changes should create follow-up review tasks:

- did the proposal help?
- did it merely shift failure somewhere else?
- has it degraded another instrument or regime?

Reflection should therefore include **post-change review**, not only proposal generation. Like monitoring a trade after entry — the thesis doesn't end at the fill.

### 8.8 Review cadence model

The layer should support multiple cadences:

- per-run explanation and anomaly capture
- daily summaries
- weekly review packs
- proposal-generation windows over larger evidence sets

This prevents mixing immediate diagnostics with slower policy-refinement logic.

---

## 9. Suggested Future Modules

When the repo is ready, this area could evolve into modules such as:

- `review_engine/` — historical diagnostics and pattern surfacing
- `hypothesis_engine/` — bounded explanation generation
- `policy_recommendation/` — proposal objects and validation rules
- `policy_registry/` — versioned proposal lifecycle store
- `review_jobs/` — scheduled batch review runs
- `governance_surfaces/` — approval, sandbox, rollback UI/API surfaces

These are future ideas, not immediate implementation requirements.

---

## 10. Minimum Data Contract Ideas for Later

When this becomes real work, it will likely require explicit contracts such as:

- `review_summary.json`
- `hypothesis_report.json`
- `policy_proposal.json`
- `proposal_evaluation.json`
- `review_window_manifest.json`

Each should be deterministic, auditable, and versioned. No hidden freeform mutation pipeline.

---

## 11. Acceptance Criteria for the Design Note Itself

This design note is successful if it accomplishes the following:

- clearly states that the reflective layer is a **future** architecture direction
- positions it **after** the current UI re-entry and Agent Ops foundation work
- links it conceptually to Agent Ops and Journal & Review without expanding present scope
- defines strict governance and anti-autonomy boundaries
- turns "self-improving AI" language into disciplined, auditable review language
- gives future contributors enough structure to build a real spec later
- does not alter any current phase status, PR target, or implementation sequence

---

## 12. Recommended Progress-Hub Wording

Suggested entry for the progress hub future-direction section:

> **Future Design Direction — Reflective Intelligence Layer:** Human-governed review and policy-refinement architecture built on run-record audit trails. Intended to use Agent Ops observability and Journal & Review artifacts to surface recurring weaknesses, generate bounded hypotheses, and propose reversible policy changes for human approval. Becomes viable once the repo has stable run artifacts, Agent Ops observability surfaces, Journal & Review readback, and sufficient historical run volume. Not part of current UI re-entry implementation scope. Design note: `docs/design-notes/reflective_intelligence_layer.md`.

---

## 13. Bottom Line

The Reflective Intelligence Layer is one of the strongest long-term ideas in the repo because it shifts optimisation from intuition to evidence.

But its place is clear:

- **not before UI re-entry completes**
- **not instead of Agent Ops**
- **not inside any current PR**
- **not as autonomous policy mutation**

Its proper role is to become the repo's future **review, reflection, and policy-governance layer** once the current foundations are stable enough to support it.
