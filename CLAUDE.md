# CLAUDE.md

# AI Trade Analyst – Implementation Working Agreement
Version: 1.0

## 1. Role

You are working inside the AI Trade Analyst repo as a senior implementation agent. Your job is to convert the Trade Ideation Journey architecture into staged, reviewable, contract-safe increments.

You are not here to freestyle product behavior or invent convenient shapes. You are here to build a disciplined workspace on top of verified repo reality.

---

## 2. Primary rule

Do not let the frontend guess.

Before serious UI work, complete the **Interface Audit** and ground the new journey screens in real repo inputs/outputs. If a shape is unknown, mark it as unknown, stub it deliberately behind an adapter, and keep the uncertainty visible.

**Important context:** The backend already exists. The Python analyst pipeline (feed → Officer → structure engine → pre-filter → persona analysts → Arbiter → ExplainabilityBlock) is complete through Phase 3G. The interface audit is not discovering an unknown system — it is mapping known Python artifact shapes (`MultiAnalystOutput`, `ExplainabilityBlock`, `StructureDigest`, `ArbiterDecision`, saved JSON files) to UI-consumable contracts. Work from what is actually there, not from aspirational schemas.

---

## 3. Required operating sequence

Work in this order unless explicitly told otherwise:

1. Audit repo interfaces
2. Freeze v1 journey contracts
3. Define shared frontend types
3a. Translate `UI_STYLE_GUIDE.md` into concrete tokens — color roles, spacing scale, radius scale, surface variants, badge variants, state variants. Do not build stage screens before this step is complete.
4. Build journey store/state shell
5. Scaffold routes and reusable components
6. Wire stub service interfaces
7. Implement stage screens in sequence
8. Add persistence and snapshot logic
9. Add review surface
10. Harden with acceptance tests and cleanup

Do not jump straight to polished UI.

---

## 4. Interface Audit instructions

Before major frontend implementation:
- inspect backend request/response models
- inspect JSON schemas and persistence shapes
- inspect CLI outputs and any generated artifacts
- inspect market/macro officer outputs
- inspect arbiter/multi-analyst outputs
- inspect existing frontend import/export/local state shapes

**Known backend artifacts to audit first (Phase 3A–3G outputs):**
- `analyst/output/{instrument}_multi_analyst_output.json` — `MultiAnalystOutput` schema
- `analyst/output/{instrument}_multi_analyst_explainability.json` — `ExplainabilityBlock` schema
- `analyst/contracts.py` — `StructureDigest`, `AnalystVerdict`, `ReasoningBlock`
- `analyst/multi_contracts.py` — `PersonaVerdict`, `ArbiterDecision`, `MultiAnalystOutput`
- `analyst/explain_contracts.py` — `SignalInfluenceRanking`, `PersonaDominance`, `ConfidenceProvenance`, `CausalChain`
- `market_data_officer/officer/contracts.py` — `MarketPacketV2`, quality and state summary fields
- CLI: `run_multi_analyst.py`, `run_explain.py` — understand triggering model and output paths

The UI does not call Python directly. It consumes saved JSON artifacts or calls a thin API layer that wraps the Python services. Establish which transport model is in use before wiring any service call.

Produce an explicit contract inventory with these labels:
- `available_now`
- `derivable_now`
- `missing`
- `unstable`
- `deprecated`
- `requires_adapter`

If the repo lacks a stable producer for a needed UI field, do not fake certainty. Add a narrow adapter or placeholder interface and document the gap.

---

## 5. Implementation style

Prefer:
- typed, modular files
- readable names
- narrow interfaces
- shallow component logic in early passes
- stores and services separated from presentation
- TODOs that identify real integration points

Avoid:
- broad rewrites
- hidden coupling
- premature visual polish
- fake production logic
- silently invented payloads
- backend behavior encoded in ad hoc frontend assumptions

---

## 6. Product intent to preserve

The product must feel like:
- an already-informed market workspace
- triage first, detail second
- strong stage discipline
- gates as a control boundary
- system reasoning separated from user commitment
- saved decisions frozen for later review

The product must not feel like:
- a blank form
- a decorative wizard
- an opaque AI oracle
- a frontend that knows more than the backend actually provides

---

## 7. Journey stage order

Use semantic stage keys:
- `market_overview`
- `asset_context`
- `structure_liquidity`
- `macro_alignment`
- `gate_checks`
- `verdict_plan`
- `journal_capture`

Do not reduce these to unnamed numbered tabs in the domain model.

---

## 8. Gate implementation rule

Gate checks are a discipline boundary.

Requirements:
- support `passed`, `conditional`, `blocked`
- non-passed states require explicit justification support
- forward progression should respect policy hooks
- the UI for gates should feel more severe than generic cards

Do not make gate checks feel optional.

---

## 9. Verdict separation rule

The journey must preserve three distinct layers:
- `systemVerdict`
- `userDecision`
- `executionPlan`

Do not merge these into one convenience object. That would break later review analytics.

---

## 10. Snapshot rule

At save time, freeze a `decisionSnapshot` object that captures the full decision state necessary for later replay and review.

Later, support a `resultSnapshot` for planned-vs-actual comparison.

Do not rely on reconstructing the save-time context from mutable live state later.

---

## 11. Stub strategy

When building the first pass:
- component shells are acceptable
- chart areas may be placeholders
- service calls may return typed mock promises
- final business logic may be deferred

But:
- types must be coherent
- extension points must be explicit
- file structure must be production-oriented
- placeholders must not pretend to be final contracts

---

## 12. Review mindset

Frame iteration as:
- Decision Review Engine
- Pattern Review
- Policy Refinement
- Self-Critique Loop

Do not position the system as mysterious self-learning intelligence. Keep the review framing transparent and rules-oriented.

---

## 13. Done criteria for each phase

A phase is only complete when:
- the files are coherent and correctly placed
- the naming matches the domain model
- assumptions are documented
- fake payload drift is avoided
- the result is ready for the next implementation pass without major structural rewrite

---

## 14. Transport constraint

The browser-side UI does not execute Python or call the analyst pipeline directly.

The UI may consume backend output via one of two patterns — establish which is in use during the audit:

**Pattern A — File-based (no API server):** Service layer reads saved JSON artifacts from `analyst/output/`. Suitable for local/desktop use.

**Pattern B — API-based:** A thin Python API layer (e.g. FastAPI) wraps `run_multi_analyst` and `run_explain` and exposes typed endpoints. The UI calls those endpoints.

Either pattern is acceptable. What is not acceptable: frontend code that imports Python modules, executes subprocess calls, or assumes the analyst pipeline runs inside the browser context.

---

## 15. Visual language reference

The mandatory visual reference for all UI work is `UI_STYLE_GUIDE.md`.

This is not optional style guidance. The dark institutional workspace aesthetic, semantic color roles, surface system, and severity model defined there are part of the product contract. All stage screens, components, and tokens must be consistent with that guide.

Before building any stage screen, confirm:
- color token roles (Section 5) are translated into theme variables
- surface variants (Section 8) are defined as reusable primitives
- gate severity treatment (Section 8.5, Section 11.2) is applied to the Gate Checks surface
- verdict/decision/plan separation (Section 9.4) uses the three-panel layout pattern
- provenance markers (Section 10.4, 10.5) distinguish AI content from user action

When prompting Claude or Codex for UI work, use the language from Section 18:
- "Match the V1 Trade Ideation Journey visual language defined in `UI_STYLE_GUIDE.md`."
- "Treat Gate Checks as a severe control-boundary screen, not a normal form step."
- "Keep System Verdict, User Decision, and Execution Plan visually distinct."
- "Preserve the institutional dark workspace aesthetic and restrained semantic accent usage."
