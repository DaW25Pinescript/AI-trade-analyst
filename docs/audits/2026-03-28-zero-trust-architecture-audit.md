# AI Trade Analyst Zero-Trust Architecture Audit (2026-03-28)

## Executive Summary

- **Repository Health Score:** **5.8 / 10**
- **Top 3 critical risks:**
  1. **Hard contract drift in Agent Ops trace payloads** between backend models and frontend types/components (`trace_edges` vs `edges`, `artifact_refs` vs `artifacts`, `status` vs `participation_status`, etc.), creating silent UI misprojection risk.
  2. **Observability trust inflation** where projection layers infer stronger semantics than artifacts prove (override attribution heuristic and health “live” statuses inferred from coarse proxy signals).
  3. **Projection coupling and duplication** across roster/trace/detail layers (private constant imports, duplicated persona-ID mapping and status derivation), which will amplify churn for Run Browser + Reflective Intelligence phases.
- **Verdict:** **healthy with required fixes** (not blocked today, but structurally risky for Phase 8 expansion if unresolved).

---

## Deep Dive Findings

### A) Agent Ops Contract & Trace Surfaces

#### 1) Severity: **Critical**
- **Issue:** Backend trace contract diverges from frontend and contract doc in multiple field names/enums.
- **Context:** Backend `AgentTraceResponse` uses `run_status`, `instrument`, `session`, `started_at`, `finished_at`, `trace_edges`, `artifact_refs`, participant `status`, and stage `stage_index`; frontend expects summary-level `instrument/session`, `edges`, `artifacts`, participant `participation_status`, and stage `order`.
- **Why it matters:** UI can render structurally valid JSON with semantically missing data, producing false operator confidence (e.g., empty edges/artifacts/timestamps without clear contract error).
- **Suggested fix:** Introduce a **single shared trace schema artifact** (generated TS from backend OpenAPI/Pydantic or JSON Schema). Add strict runtime validation in UI adapters and fail loudly with a contract-mismatch banner.

#### 2) Severity: **High**
- **Issue:** UI partial-run detection is dead logic.
- **Context:** UI checks for stage statuses `running`/`pending`, while backend trace stage enum is only `completed`/`failed`/`skipped`.
- **Why it matters:** Partial runs can be misrepresented as complete traces, undermining trust in operator review.
- **Suggested fix:** Compute partialness from backend `run_status === "partial"` and expose explicit partial reason codes from backend.

#### 3) Severity: **High**
- **Issue:** Trace edge semantics are inconsistent across layers.
- **Context:** Backend edge enum is run-scoped (`considered_by_arbiter`, `skipped_before_arbiter`, etc.), but frontend styling map is roster-relationship oriented (`supports`, `feeds`, etc.).
- **Why it matters:** Operator may infer architectural/static dependency semantics from run-scoped edges, blurring causality and governance interpretation.
- **Suggested fix:** Separate static and run-edge visual vocabularies with explicit legend text and edge provenance tags.

### B) Observability / Trust Integrity

#### 4) Severity: **High**
- **Issue:** Override attribution is heuristic, not evidence-grounded.
- **Context:** `was_overridden` is inferred only when `risk_override_applied` and analyst stance is directional while arbiter decision is `NO_TRADE`.
- **Why it matters:** This can undercount/overcount overrides and misattribute dissent, presenting “explainability” that is partly fabricated.
- **Suggested fix:** Persist explicit per-analyst override metadata in run artifacts (e.g., `overrides:[{entity_id,reason,type}]`) and project directly.

#### 5) Severity: **Medium**
- **Issue:** Health projection marks governance entities `live` when `feeder_context` exists, independent of actual arbiter/synthesis runtime evidence.
- **Context:** Governance health is inferred from macro-context presence.
- **Why it matters:** A stale or partially initialized environment can appear healthier than it is; this is a trust-layer false positive.
- **Suggested fix:** Introduce evidence classes per entity (`runtime_event`, `derived_proxy`, `none`) and show them explicitly in health/detail payloads.

#### 6) Severity: **Medium**
- **Issue:** `data_state` conflates freshness and completeness.
- **Context:** Trace uses `data_state="live"` when audit exists, otherwise stale, but does not encode whether core fields were defaulted, heuristic, or missing.
- **Why it matters:** Operators cannot distinguish “fresh but low-fidelity” from genuinely complete traces.
- **Suggested fix:** Add `projection_quality` and `missing_fields[]` metadata to trace/detail responses.

### C) Architectural Integrity & Coupling

#### 7) Severity: **Medium**
- **Issue:** Projection services import private roster constants directly.
- **Context:** Trace/detail services depend on `_GOVERNANCE_LAYER`, `_OFFICER_LAYER`, `_DEPARTMENTS`, `_RELATIONSHIPS` internals.
- **Why it matters:** Internal refactors in roster service can silently break trace/detail behavior; weak module boundaries increase future rewrite cost.
- **Suggested fix:** Promote public read APIs (`get_roster_entities()`, `get_relationships()`) and remove direct private-constant imports.

#### 8) Severity: **Medium**
- **Issue:** Duplicated identity mapping logic (`_persona_to_roster_id`) across trace/detail.
- **Context:** Mapping implemented in multiple services with slight behavior differences.
- **Why it matters:** Drift risk and hard-to-debug mismatches in participant/detail projections.
- **Suggested fix:** Centralize in one utility module with invariant tests.

### D) Execution Efficiency / Scale Readiness

#### 9) Severity: **Medium**
- **Issue:** Repeated filesystem scans and JSON reads for detail/run surfaces.
- **Context:** Detail recent-participation scans directories and parses many run records; run browser separately scans/parses runs.
- **Why it matters:** At higher run counts, operator surfaces become IO-bound and latency spikes.
- **Suggested fix:** Add a compact append-only run index (or cache with invalidation on new run) consumed by both run browser and detail projections.

#### 10) Severity: **Low-Medium**
- **Issue:** Detail participation scan assumes run directory name ordering for recency.
- **Context:** Sorted by directory name descending “by convention,” not robust timestamp ordering.
- **Why it matters:** Recent participation panel may silently omit newest runs in non-conforming environments.
- **Suggested fix:** Sort by parsed run timestamp first, directory mtime fallback second.

### E) Error Resilience / Silent Failure Modes

#### 11) Severity: **Medium**
- **Issue:** Malformed/partial artifacts often degrade silently to omitted entries.
- **Context:** Detail and run-browser skip malformed records without exposing structured degradation reasons.
- **Why it matters:** Operator sees “clean” panels even when source evidence quality is poor.
- **Suggested fix:** Expose counters (`skipped_records`, `malformed_records`) and show warning banners in UI.

#### 12) Severity: **Medium**
- **Issue:** Tests mostly validate mocked payload contracts, not backend-frontend real contract compatibility.
- **Context:** UI tests define fixtures matching frontend assumptions and can pass despite backend contract drift.
- **Why it matters:** High-confidence false green in CI; contract regressions reach production.
- **Suggested fix:** Add contract tests generated from backend OpenAPI and consumed by UI adapter tests (consumer-driven and provider-verified).

---

## Contract Risk Review

### Response envelope consistency
- Roster/health envelopes are mostly aligned, but trace envelope drift is severe across docs/backend/frontend.
- Backend emits fields not represented in frontend types; frontend expects fields backend no longer emits.

### Identifier consistency
- Roster IDs are stable, but persona bare-name to roster-id conversion is repeated and not canonicalized through one module.

### Enum/type drift
- Stage status, participant status, edge type, arbiter summary, artifact ref types have drift between docs, frontend, backend.

### Trace/detail/health/roster alignment
- Health and detail are nominally aligned, but health evidence provenance is not explicit; “live” can mean proxy-derived.

### Run artifact projection integrity
- Projection quality is not encoded; consumers cannot distinguish direct evidence from heuristic inference.

### Arbiter/analyst/operator projection boundaries
- Current override projection partially conflates arbiter governance intent with analyst stance inference.

### Docs/spec vs code drift
- `docs/ui/AGENT_OPS_CONTRACT.md` trace shape currently reflects older naming/semantics than backend trace models.

---

## Observability and Trust Review

- **Run trace honesty:** medium risk. The pipeline is explainability-oriented, but several fields are inferred and not provenance-tagged.
- **Override semantics:** high risk due to heuristic attribution.
- **Health-state integrity:** medium risk due to proxy-derived governance health.
- **Detail-panel truthfulness:** medium risk because recent participation can omit/skip malformed runs without operator-visible quality signal.
- **Graceful degradation quality:** generally crash-safe, but often too silent; degradation reason transparency is weak.
- **Operator misinterpretation risk:** high in Run mode until contract and semantic drift are corrected.

---

## Test Gaps (Priority Order)

### Backend gaps
1. Contract snapshot tests for `AgentTraceResponse` including exact field names/enums and alias behavior.
2. Projection provenance tests ensuring heuristic fields are labeled and quality metadata is emitted.
3. Corrupt/mixed artifact corpus tests validating explicit degradation counters (not silent drops).

### Frontend gaps
1. Runtime schema validation tests (backend payload fixtures) for trace/detail adapters.
2. Tests asserting explicit operator warning on contract mismatch/missing critical fields.
3. Tests for partial-run indicator driven by backend `run_status` rather than stage-status assumptions.

### Integration/contract gaps
1. Provider/consumer contract pipeline: backend OpenAPI schema → generated TS types + UI contract tests.
2. End-to-end golden run fixtures (real `run_record.json` + audit logs) rendered through API + UI.
3. Drift gate in CI that diffs docs contract sections vs generated schema.

---

## Refactor Recommendations (Material Only)

1. **Contract source-of-truth unification (highest ROI):** generate typed contracts from backend models and consume in UI; deprecate hand-written parallel types.
2. **Projection-core module:** centralize run artifact parsing, persona ID mapping, run-status derivation, and provenance tagging used by run-browser/trace/detail.
3. **Observability fidelity model:** add explicit evidence provenance + quality fields across health/trace/detail responses.
4. **Read-side index/cache for runs:** single bounded index reused by run browser and detail recent-participation to avoid repeated scans/parses.
5. **Governance semantics hardening:** move override attribution from heuristic projection to explicit artifact-level fields produced by arbiter stage.

---

## Phase-Readiness Verdict (Run Browser / Charts / Reflective Intelligence)

- **Run Browser:** workable today but needs projection/index hardening for scale.
- **Charts integration:** moderate risk until run/trace contracts are stable and shareable across UI surfaces.
- **Reflective Intelligence:** **at risk** if built on current heuristic + drift-prone trace summaries; fix provenance/contract seams first to avoid compounding historical truth debt.
