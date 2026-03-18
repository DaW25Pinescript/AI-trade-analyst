# Persona Architecture Audit — AI Trade Analyst

_Date audited: 2026-03-18 (UTC)_

## 1. EXECUTIVE SUMMARY

- **CONFIRMED:** The active production pipeline is `ai_analyst` FastAPI + LangGraph (`build_analysis_graph`) with multi-analyst fan-out and a single arbiter node; this is the path wired into `POST /analyse`.  
- **CONFIRMED:** Persona identity is primarily implemented as prompt files (`prompt_library/v1.2/personas/*.txt`) plus enum/config names (`PersonaType`, analyst roster), not as a per-persona output schema contract.  
- **CONFIRMED:** Persona output unit is a strongly-typed `AnalystOutput` Pydantic object (bias/structure/action/confidence/etc.) with enforced no-trade guardrails.  
- **CONFIRMED:** Arbiter output is also strongly typed (`FinalVerdict` Pydantic) with fallback handling for malformed LLM output (forced `NO_TRADE`).  
- **CONFIRMED:** Analysts receive the same GroundTruth packet and clean charts in Phase 1; differentiation comes from persona prompt text, optional peer-review round, and overlay delta stage.  
- **CONFIRMED:** There is no code-level weighted voter or explicit contradiction engine in arbiter logic; synthesis is prompt-mediated LLM aggregation over JSON evidence, with Python-side schema/fallback checks.  
- **CONFIRMED:** `run_record.json` does **not** persist full analyst evidence fields; full per-analyst evidence is stored in audit logs (`ai_analyst/logs/runs/{run_id}.jsonl`). Reflect and Ops infer persona metrics by combining both artifacts when available.  
- **PARTIAL:** Persona divergence is measurable indirectly (bias detector heuristics injected into arbiter prompt; Reflect alignment/override metrics), but there is no canonical persistent disagreement table per run.  
- **CONFIRMED:** No durable persona weighting decay/learning loop is applied in production verdict path; historical analytics exist as separate tooling (`feedback_loop`, Reflect aggregations).  
- **CONFIRMED:** Multiple persona architectures coexist: active `ai_analyst` (5-persona enum, configurable roster) and legacy `analyst/` (2 personas + deterministic consensus). This creates ambiguity in docs/roster semantics.  
- **HIGH RISK:** Persona collapse risk is real in active path because default roster maps multiple personas to the same model profile and same temperature, with differentiation mostly via short persona prompt text.  
- **HIGH RISK:** Arbiter governance language (quorum/veto/debate semantics) is mostly prompt text and API metadata; no deterministic quorum/veto algorithm is implemented in active arbiter node.  

## 2. EVIDENCE INDEX

| Claim / Question | Status | Evidence | File path(s) | Notes |
|---|---|---|---|---|
| Active API uses `ai_analyst` LangGraph pipeline | CONFIRMED | `app.state.graph = build_analysis_graph()` and `POST /analyse` invokes graph | `ai_analyst/api/main.py`, `ai_analyst/graph/pipeline.py` | Production path for current backend |
| Personas defined as enum + prompt files | CONFIRMED | `PersonaType` enum and prompt loader by `{persona}.txt` | `ai_analyst/models/persona.py`, `ai_analyst/core/lens_loader.py`, `ai_analyst/prompt_library/v1.2/personas/*.txt` | Identity stored by names and files |
| Persona roster is configurable | CONFIRMED | `router.get_analyst_roster()` loads YAML `analyst_roster` with fallback defaults | `ai_analyst/llm_router/router.py`, `ai_analyst/llm_router/config_loader.py`, `config/llm_routing.example.yaml` | Runtime list can vary by config |
| Persona output schema is structured + validated | CONFIRMED | `AnalystOutput` Pydantic validation and hard no-trade rule | `ai_analyst/models/analyst_output.py`, `ai_analyst/graph/analyst_nodes.py` | LLM output parsed as JSON and validated |
| Arbiter output schema is structured + validated | CONFIRMED | `FinalVerdict` model; arbiter node fallback for malformed JSON/schema | `ai_analyst/models/arbiter_output.py`, `ai_analyst/graph/arbiter_node.py` | Forced safe fallback to `NO_TRADE` |
| Orchestration is parallel then sequential with conditionals | CONFIRMED | `validate_input -> (macro_context || chart_setup) -> chart_lenses -> ...` | `ai_analyst/graph/pipeline.py` | Conditional deliberation/overlay branches |
| Analysts receive same core packet/charts in round 1 | CONFIRMED | `build_analyst_prompt` uses same `ground_truth`, persona-specific developer prompt | `ai_analyst/core/analyst_prompt_builder.py`, `ai_analyst/graph/analyst_nodes.py` | Differentiation mostly prompt-level |
| Arbiter receives named analyst JSON list | CONFIRMED | `build_arbiter_prompt` injects array of all analyst outputs | `ai_analyst/core/arbiter_prompt_builder.py` | No anonymous blend before arbiter prompt |
| Explicit weighted vote/quorum/veto algorithm in code | NOT FOUND | No deterministic vote table/scoring function in arbiter node | `ai_analyst/graph/arbiter_node.py`, `ai_analyst/core/arbiter_prompt_builder.py` | Rules exist mostly in prompt text |
| Persona-level observability in run artifacts | PARTIAL | run_record keeps persona participation metadata; audit log keeps analyst outputs | `ai_analyst/graph/logging_node.py`, `ai_analyst/core/logger.py` | Split across two artifact families |
| Reflect persona analytics from artifacts | CONFIRMED | Aggregates `run_record` + optional audit logs for persona metrics | `ai_analyst/api/services/reflect_aggregation.py`, `ai_analyst/api/routers/reflect.py` | `data_state` becomes stale when audit missing |
| Replay with frozen persona outputs in prod API | NOT FOUND | No `/replay` route or run re-execution endpoint using persisted analyst outputs | `ai_analyst/api/main.py`, `ai_analyst/api/routers/*.py` | Legacy/manual `ExecutionRouter` exists but not main API path |
| Legacy alternate persona/arbiter implementation exists | CONFIRMED | `analyst/` package has 2-persona deterministic consensus contracts | `analyst/personas.py`, `analyst/arbiter.py`, `tests/test_personas.py` | Separate from active `ai_analyst` path |

## 3. PERSONA DEFINITION INVENTORY

### Active production persona layer (`ai_analyst`)

1. **default_analyst**
   - File path: `ai_analyst/models/persona.py`, `ai_analyst/prompt_library/v1.2/personas/default_analyst.txt`
   - Defining symbol/config: `PersonaType.DEFAULT_ANALYST`; roster entries via `analyst_roster`
   - Fields/traits: free-text persona instructions (“balanced, professional analyst”)
   - Identity enforcement mode: enum/config + prompt file name
   - Output unit: `AnalystOutput`
   - Differentiation mechanism: developer/system persona prompt text only
   - Ambiguity/gap: no explicit numeric trait parameters

2. **risk_officer**
   - Path: `ai_analyst/models/persona.py`, `.../personas/risk_officer.txt`
   - Traits: text directives (tighten thresholds by 0.10, capital preservation)
   - Enforcement: prompt instruction only (no direct code branch enforcing “+0.10” per persona)
   - Output: `AnalystOutput`
   - Gap: textual trait may or may not be followed by model; no deterministic post-check for persona-specific threshold delta

3. **prosecutor**
   - Path: `.../personas/prosecutor.txt`
   - Traits: adversarial/disproving stance
   - Enforcement: prompt-layer only
   - Output: `AnalystOutput`
   - Gap: no explicit code-level “must include counter-arguments” validation

4. **ict_purist**
   - Path: `.../personas/ict_purist.txt`
   - Traits: ICT-only constraints
   - Enforcement: prompt-layer only
   - Output: `AnalystOutput`
   - Gap: no deterministic parser validating ICT confluence claims

5. **skeptical_quant**
   - Path: `.../personas/skeptical_quant.txt`
   - Traits: probabilistic/statistical skepticism
   - Enforcement: prompt-layer only
   - Output: `AnalystOutput`
   - Gap: default roster file includes 4 personas (skeptical_quant absent) unless config changes

### Active/Current configuration behavior notes

- Persona count is **configurable** via `analyst_roster` in routing config, with fallback defaults if missing.
- Personas are activated per run based on loaded roster; smoke mode can slice roster to first analyst.
- Identity is encoded in:
  - persona enum values,
  - roster entries (`profile`, `persona`),
  - prompt file names,
  - analyst result metadata in run_record.

### Coexisting legacy persona layer (`analyst/`)

- **technical_structure** and **execution_timing** personas are implemented in `analyst/personas.py` with `PersonaVerdict` contracts and deterministic consensus logic in `analyst/arbiter.py`.
- This appears as a parallel/legacy stack (used heavily in `tests/test_personas.py`, `tests/test_arbiter.py`) and is not the FastAPI `POST /analyse` path.

## 4. ORCHESTRATION TRACE

- **Graph construction location:** `ai_analyst/graph/pipeline.py::build_analysis_graph`.
- **Entry path:** `validate_input`.
- **Execution pattern:**
  1. Parallel fan-out: `macro_context` and `chart_setup`.
  2. Fan-in at `chart_lenses` (which triggers `parallel_analyst_node`).
  3. Conditional route: deliberation first (if enabled), otherwise overlay branch if overlay exists, else direct to arbiter.
  4. `run_arbiter` → `pinekraft_bridge` → `log_and_emit`.
- **Analyst participation:** `parallel_analyst_node` runs all roster configs concurrently; failures are retained in `_analyst_results`; quorum check enforces minimum valid analysts except smoke mode.
- **Output flow to arbiter:** `analyst_outputs` (+ optional `overlay_delta_reports`, `deliberation_outputs`, `macro_context`) passed to `arbiter_node` prompt builder.
- **Attribution preservation:**
  - In-memory: yes (`analyst_configs_used`, persona in config).
  - `run_record.json`: partial (persona/status/model/provider; no full analytical fields).
  - audit log JSONL: full analyst output objects retained.
- **Ambiguity:** No deterministic per-persona abstain contract beyond `recommended_action=NO_TRADE` and schema checks.

## 5. ARBITER CONTRACT AUDIT

- **Inputs received:**
  - Phase 1 analyst outputs (structured JSON array),
  - risk constraints,
  - optional overlay delta reports,
  - optional macro context block,
  - optional deliberation outputs,
  - bias detector advisory section.
- **Attribution:** inputs remain per-analyst objects in array form; arbiter prompt is not anonymous.
- **Synthesis pattern:** prompt-driven LLM synthesis (single arbiter model call) + Python schema/fallback enforcement.
- **Weighting/voting implementation:**
  - Prompt text defines rules (e.g., no-trade conditions, confidence downgrade);
  - No deterministic Python weighted voting engine found in active arbiter node.
- **Contradiction handling:**
  - Implicit via prompt instructions and overlay contradiction fields;
  - No explicit contradiction matrix algorithm in code.
- **Can arbiter ignore persona?** Practically yes (LLM can output decision regardless of individual persona fields); no hard validator enforcing persona-by-persona consideration.
- **Veto/quorum behavior:**
  - Persona quorum at analyst stage: minimum valid analyst count in `parallel_analyst_node` (except smoke mode).
  - Arbiter veto/quorum semantics: prompt-described, not deterministic code.
- **Determinism level:** low-to-moderate; temperature fixed low (0.1) but final synthesis remains LLM nondeterministic.
- **Spec-language gap:** governance terminology in APIs/docs (supports/challenges/veto/quorum-like metadata) exceeds explicit executable governance logic in active arbiter implementation.

## 6. OBSERVABILITY / REFLECT / ARTIFACT AUDIT

- **Run artifact paths:**
  - `ai_analyst/output/runs/{run_id}/run_record.json`
  - `ai_analyst/output/runs/{run_id}/usage.jsonl`
  - `ai_analyst/logs/runs/{run_id}.jsonl` (audit log with analyst outputs + final verdict)
- **What is logged where:**
  - `run_record.json`: stage timings, analyst participation metadata, arbiter summary verdict metadata.
  - audit log JSONL: full `ground_truth` (excluding charts), full `analyst_outputs`, full `final_verdict`.
  - usage logs: token/cost/call metadata only (no prompts/messages persisted).
- **Persona prompts logged?** Not found in persistent artifacts.
- **Reflect persona-level detail:**
  - Persona performance endpoint computes participation/override/alignment/avg-confidence from run_record + optional audit.
  - Run bundle endpoint returns run_record + usage, but not full audit analyst outputs.
- **Decision decomposition availability:**
  - Possible with combined artifacts (`ground_truth`, `analyst_outputs`, `final_verdict`) from audit + run_record.
  - Not possible from run_record alone.
- **Visibility classification (Phase 7):** **B — Partial visibility**.
  - UI shows persona participation and aggregated reflect metrics.
  - Full per-persona reasoning/evidence not fully exposed in reflect run detail by default.
- **Missing for robust persona tuning:**
  - prompt/version hash per persona per run,
  - deterministic disagreement table persisted per run,
  - direct persona-level outcome attribution over realized market outcomes,
  - replay endpoint for frozen persona outputs.

## 7. DIRECT ANSWERS TO MANDATORY QUESTIONS

### Q1
- **Answer:** Actual persona output unit is structured JSON validated into `AnalystOutput` (fields include `htf_bias`, `confidence`, `recommended_action`, evidence fields).  
- **Confidence:** High  
- **Evidence:** `ai_analyst/models/analyst_output.py::AnalystOutput`; `ai_analyst/graph/analyst_nodes.py::run_analyst`  
- **Next step if unresolved:** N/A.

### Q2
- **Answer:** Personas are effectively stateless across runs in the active pipeline; each run uses current GroundTruth and optional in-run deliberation. No persisted persona memory is applied in production decision path.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/graph/state.py`, `ai_analyst/graph/analyst_nodes.py`, absence of persona state store in `POST /analyse` flow (`ai_analyst/api/main.py`)  
- **Next step if unresolved:** Confirm whether external infra injects historical context into prompts at runtime (not seen in repo).

### Q3
- **Answer:** Persona identity is enforced by enum/config/prompt naming and function context; primarily prompt-layer behavioral identity, not separate schema contract per persona.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/models/persona.py`, `ai_analyst/core/lens_loader.py::load_persona_prompt`, `ai_analyst/llm_router/router.py::get_analyst_roster`  
- **Next step if unresolved:** Add explicit persona contract object (not currently present).

### Q4
- **Answer:** Yes, persona outputs are programmatically validated via Pydantic (`AnalystOutput`), JSON extraction (`extract_json`), and exception handling; malformed outputs are rejected and can fail quorum.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/models/analyst_output.py`, `ai_analyst/graph/analyst_nodes.py`, `ai_analyst/core/json_extractor.py`  
- **Next step if unresolved:** N/A.

### Q5
- **Answer:** In active Round 1 they operate on identical input packet and charts; differences come from persona prompt text. Additional optional phases (overlay/deliberation) add different context but still per-analyst parallel structure.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/core/analyst_prompt_builder.py::build_analyst_prompt`, `ai_analyst/graph/analyst_nodes.py::parallel_analyst_node`  
- **Next step if unresolved:** Capture final rendered messages per persona for audit verification.

### Q6
- **Answer:** Divergence is partially measurable: bias heuristics (`detect_bias`) and Reflect metrics (alignment/override/confidence) exist, but no canonical persisted vote/disagreement table per run.  
- **Confidence:** Medium  
- **Evidence:** `ai_analyst/core/bias_detector.py`, `ai_analyst/api/services/reflect_aggregation.py`  
- **Next step if unresolved:** Persist per-run divergence metrics directly in run_record/audit schema.

### Q7
- **Answer:** Canonical bias schema exists at analyst level (`htf_bias`: bullish/bearish/neutral/ranging) and arbiter level (`final_bias` same enum-like literals).  
- **Confidence:** High  
- **Evidence:** `ai_analyst/models/analyst_output.py`, `ai_analyst/models/arbiter_output.py`  
- **Next step if unresolved:** Align ops models that only allow neutral/bullish/bearish in some views.

### Q8
- **Answer:** Traits are free-text persona prompt directives in persona files; deliberate wording exists but traits are not encoded as structured trait objects.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/prompt_library/v1.2/personas/*.txt`  
- **Next step if unresolved:** Create machine-readable trait schema if needed.

### Q9
- **Answer:** Meaningful differentiation is **inferred** rather than guaranteed; mechanism is prompt wording. No deterministic code test proves stable behavior differences in active `ai_analyst` path.  
- **Confidence:** Medium  
- **Evidence:** `ai_analyst/core/analyst_prompt_builder.py`, shared model/temperature in `ai_analyst/graph/analyst_nodes.py`, roster defaults in `config/llm_routing.example.yaml`  
- **Next step if unresolved:** Run controlled A/B harness and store divergence stats.

### Q10
- **Answer:** Yes, personas can disagree implicitly via differing `AnalystOutput` fields/actions; there is no explicit inter-persona argument protocol except optional deliberation round review.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/models/analyst_output.py`, `ai_analyst/graph/analyst_nodes.py::deliberation_node`  
- **Next step if unresolved:** Persist explicit contradiction matrices.

### Q11
- **Answer:** Arbiter receives persona-attributed outputs as an array; attribution is preserved by ordering and per-analyst objects from fan-out.  
- **Confidence:** Medium  
- **Evidence:** `ai_analyst/core/arbiter_prompt_builder.py`, `ai_analyst/graph/analyst_nodes.py`  
- **Next step if unresolved:** Add explicit persona_id field to `AnalystOutput` or wrapper for unambiguous attribution.

### Q12
- **Answer:** Traits are currently decorative-to-instructional prompt text (not additive/mutually-exclusive in typed code).  
- **Confidence:** High  
- **Evidence:** persona prompt files + lack of structured trait composition logic in runtime  
- **Next step if unresolved:** Formalize trait composition engine.

### Q13
- **Answer:** Model variation per persona is possible via roster profile mapping, but default config maps all analysts to the same profile. Temperature is constant (0.1) across analysts/arbiter.  
- **Confidence:** High  
- **Evidence:** `config/llm_routing.example.yaml`, `ai_analyst/llm_router/router.py`, `ai_analyst/graph/analyst_nodes.py`, `ai_analyst/graph/arbiter_node.py`  
- **Next step if unresolved:** Verify deployed `config/llm_routing.yaml` (not present in repo snapshot).

### Q14
- **Answer:** Arbiter behaves as context-dependent prompt-level advisor synthesizer, not explicit equal-vote or deterministic weighted-expert algorithm in code.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/graph/arbiter_node.py`, `ai_analyst/core/arbiter_prompt_builder.py`, `arbiter_v1.1.txt`  
- **Next step if unresolved:** Implement explicit weighted aggregation if required.

### Q15
- **Answer:** Yes, effectively possible. No code-level check forces inclusion of each persona signal in final verdict rationale.  
- **Confidence:** Medium  
- **Evidence:** `ai_analyst/graph/arbiter_node.py` (single LLM synthesis output accepted if schema-valid)  
- **Next step if unresolved:** Add validator requiring per-persona disposition field.

### Q16
- **Answer:** Explicit contradiction detection exists partially for overlay (`contradicts`) and bias heuristics; no generalized arbiter contradiction graph in code.  
- **Confidence:** Medium  
- **Evidence:** `OverlayDeltaReport.contradicts` in `analyst_output.py`; `bias_detector.py`; prompt rules in arbiter template  
- **Next step if unresolved:** Add deterministic contradiction extraction stage.

### Q17
- **Answer:** No explicit arbiter quorum/veto algorithm in active code. Analyst-stage quorum (minimum valid analyst responses) exists before arbiter.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/graph/analyst_nodes.py::MINIMUM_VALID_ANALYSTS`; absence in arbiter node logic  
- **Next step if unresolved:** Define code-level arbiter quorum/veto contract.

### Q18
- **Answer:** Persona performance tracking over time is available in Reflect/feedback tooling (participation, override, alignment), but not fed back into live arbiter weighting.  
- **Confidence:** High  
- **Evidence:** `ai_analyst/api/services/reflect_aggregation.py`, `ai_analyst/core/feedback_loop.py`  
- **Next step if unresolved:** Integrate tracking output into runtime policy if desired.

### Q19
- **Answer:** No dynamic influence decay/strengthen mechanism in live production arbiter path found.  
- **Confidence:** High  
- **Evidence:** no weighting memory in `ai_analyst/graph/arbiter_node.py` / prompt builder / state  
- **Next step if unresolved:** Add persisted persona weight store + update policy.

### Q20
- **Answer:** User can see partial persona stack trace via Ops trace and Reflect run details, but not complete persona prompt→reasoning→arbiter linkage in one canonical UI artifact.  
- **Confidence:** Medium  
- **Evidence:** `ai_analyst/api/services/ops_trace.py`, `ai_analyst/api/services/reflect_bundle.py`, `ui/src/workspaces/reflect/components/RunDetailView.tsx`  
- **Next step if unresolved:** Expose audit analyst outputs in run bundle/UI drilldown.

### Q21
- **Answer:** No explicit persona drift indicator is implemented, but enough logs/metrics exist to build one (historical analyst outputs + verdicts + reflect metrics).  
- **Confidence:** Medium  
- **Evidence:** `ai_analyst/core/logger.py`, `ai_analyst/api/services/reflect_aggregation.py`  
- **Next step if unresolved:** Add first-class drift metric computation and persistence.

### Q22
- **Answer:** Full replay with frozen persona outputs is not available in production API. Partial/manual replay capability exists in `ExecutionRouter` workflow (non-primary path).  
- **Confidence:** Medium  
- **Evidence:** absence in `ai_analyst/api/routers`; manual response flow in `ai_analyst/core/execution_router.py`  
- **Next step if unresolved:** Add replay endpoint accepting frozen `analyst_outputs`.

### Q23
- **Answer:** Safeguards are mostly conservative prompt + schema guardrails (risk override, no-trade rules, fallback). No external truth-check safeguard in live decision path.  
- **Confidence:** Medium  
- **Evidence:** `arbiter_v1.1.txt`, `FinalVerdict` schema, fallback logic in `arbiter_node.py`  
- **Next step if unresolved:** Add post-hoc outcome calibration loop into live gating.

### Q24
- **Answer:** Resolution mechanism is arbiter synthesis prompt; if uncertainty/malformed outputs occur, fallback/no-trade mechanisms apply. No deterministic disagreement resolver table found.  
- **Confidence:** High  
- **Evidence:** `arbiter_node.py`, arbiter template rules  
- **Next step if unresolved:** Implement explicit disagreement policy matrix.

### Q25
- **Answer:** Prompt overfit risk is present and evidenced by heavy behavior dependence on prompt wording (persona text + arbiter template) with limited deterministic safeguards.  
- **Confidence:** High  
- **Evidence:** `analyst_prompt_builder.py`, `arbiter_prompt_builder.py`, persona files, arbiter template  
- **Next step if unresolved:** version/hash prompts per run and evaluate robustness tests.

### Q26
- **Answer:** Evidence supports persona collapse risk in active stack: same model profile default for multiple personas, same temperature, same input packet, differentiation mostly textual persona prompt.  
- **Confidence:** High  
- **Evidence:** `config/llm_routing.example.yaml`, `model_profiles.py`, `analyst_nodes.py`, `analyst_prompt_builder.py`  
- **Next step if unresolved:** run controlled divergence benchmarks and consider model/profile diversification.

## 8. ARCHITECTURAL RISK REGISTER

| Risk | Why it matters | Evidence | Severity | Suggested next investigation |
|---|---|---|---|---|
| Persona collapse | Reduces multi-agent value; false consensus risk | same model profile defaults + same temp/input, prompt-only differentiation | High | Build per-run divergence dashboard from audit outputs |
| Decorative personas | Trait promises may not produce deterministic behavior | persona traits are free-text, no trait contract validators | High | Add trait schema + output checks linked to trait claims |
| Unvalidated free-text to arbiter | Could corrupt synthesis | mitigated in active path by JSON extraction + Pydantic | Low | Keep strict JSON mode tests; extend malformed-case coverage |
| Arbiter over-reliance on concatenated prompt rules | Governance may be non-deterministic and brittle | arbiter logic mostly single LLM prompt + schema check | High | Prototype deterministic consensus layer pre-arbiter |
| Limited divergence observability | Hard to quantify persona value | no canonical per-run disagreement/vote artifact | Medium | Persist disagreement matrix in run_record |
| Weak persona outcome attribution in live loop | Cannot adapt weights from performance | reflect/feedback are read-only analytics, not runtime control | Medium | Add persona scorecard feeding runtime policy |
| Abstain/no-trade robustness uncertain | Safety if confidence low | hard no-trade rules exist, but arbiter still prompt-driven | Medium | Add deterministic abstain gate before final verdict |
| Veto/quorum governance gap | Spec language may overstate implemented governance | no arbiter veto/quorum engine in active code | High | Reconcile spec/API fields with executable logic |
| Reflect tuning blind spots | UI sees partial persona detail | run bundle excludes full analyst outputs from audit log | Medium | Extend `/reflect/run/{id}` payload with persona evidence blocks |
| Prompt/config drift auditability | Difficult forensic reproducibility | prompt version static (`v1.2`), no per-run prompt hash snapshot | High | Persist prompt package manifest with hashes per run |

## 9. UNKNOWNS THAT BLOCK DESIGN

1. Cannot confirm deployed production `config/llm_routing.yaml` roster/profile mapping (repo only has example); this blocks certainty on real persona count/model diversity.
2. Cannot confirm whether any external runtime layer injects persona-specific historical memory/context not visible in repository code.
3. Cannot confirm true behavior impact of each persona trait without empirical run corpus using identical market inputs.
4. Cannot confirm if `ExecutionRouter` manual/hybrid path is operationally used in production; impacts replay and persona attribution assumptions.
5. Cannot confirm if UI/ops tooling elsewhere (outside this repo) surfaces full audit log analyst evidence for run drilldown.

## 10. RECOMMENDED NEXT INSPECTION SEQUENCE

1. **`config/llm_routing.yaml` (deployed env file, not example)** — verify actual analyst roster/profile diversity; resolves Q9/Q13/Q26.
2. **`ai_analyst/output/runs/*/run_record.json` + `ai_analyst/logs/runs/*.jsonl` from live runs** — compute real disagreement and persona alignment; resolves Q6/Q20/Q21.
3. **`ai_analyst/core/arbiter_prompt_builder.py` + `prompt_library/v1.2/arbiter/arbiter_v1.1.txt`** — map every governance rule to executable enforcement; resolves Q14–Q17/Q23–Q24.
4. **`ai_analyst/graph/analyst_nodes.py` + `core/analyst_prompt_builder.py`** — inspect trait-to-behavior mechanics and determinism controls; resolves Q5/Q8–Q13/Q25–Q26.
5. **`ai_analyst/api/services/reflect_aggregation.py`** — confirm persona metrics formulas and edge handling for missing audit logs; resolves Q6/Q18/Q21.
6. **`ai_analyst/api/services/reflect_bundle.py` + UI adapter/components** — assess missing persona drilldown payload fields; resolves Q20/Q22 and visibility classification.
7. **`ai_analyst/api/services/ops_trace.py`** — verify trace attribution quality and override inference assumptions; resolves Q11/Q16/Q20.
8. **`ai_analyst/core/logger.py` + `graph/logging_node.py`** — confirm exactly what forensic data is retained and what is dropped (prompts/messages); resolves Q20/Q21.
9. **`ai_analyst/core/execution_router.py`** — determine operational status of manual/hybrid replay paths; resolves Q22 and replay capability uncertainty.
10. **Legacy `analyst/` package + associated tests** — explicitly mark non-production behaviors in architecture docs to prevent mixing with active path; resolves implementation ambiguity.

