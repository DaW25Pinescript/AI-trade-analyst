# Persona Refinement Plan

**Status:** Proposed  
**Version:** v0.2  
**Date:** 2026-03-18  
**Changes from v0.1:** Gate A corrected; low-divergence fork defined; `PersonaContract` validators made serialisable; `ConsensusClass` type fixed; PR-PER-5 promoted to critical path; P1 AC split by PR; P2 methodology strengthened; P6 rollback policy added; `prompt_manifest` schema clarified; concerns table mapped to artifacts.  
**Planning basis:** `persona_architecture_audit_2026-03-18.md` · `Persona_Audit_Synthesis.docx`  
**Production path:** `ai_analyst/` (LangGraph + FastAPI)

---

## 1. Problem Statement

The audit confirmed three specific implementation problems — not an abstract architecture failure.

| Problem | Audit finding |
|---|---|
| **Weak persona differentiation** | Five personas share the same model profile, temperature (0.1), and input packet. Traits are free-text prompt directives with no code-level enforcement or post-output validation. Collapse risk is high. |
| **Governance language exceeds governance reality** | Quorum, veto, and debate semantics exist in specs and API metadata. No deterministic quorum/veto algorithm is present in the active `arbiter_node.py`. Governance is prompt-mediated only. |
| **Split observability** | Full analyst outputs live in audit JSONL. `run_record.json` contains metadata only. Reflect receives `run_record` + usage but not per-persona reasoning. A complete persona stack trace for one run requires reading two artifact families manually. |

---

## 2. Objectives

Make the existing five-persona system:

- **Measurably differentiated** — or provably collapsed — based on empirical run data
- **Attributable and reproducible** per run via persisted prompt manifests and persona IDs
- **Partially machine-enforceable** — typed, serialisable persona contracts with post-output validators
- **Governed with a deterministic layer** before LLM synthesis, closing the spec-vs-reality gap
- **Inspectable and tunable** via Reflect persona drilldown and replay

---

## 3. Non-Goals (this plan)

- Build a persona studio, marketplace, or user-editable trait UI
- Replace LangGraph with a different orchestration framework
- Switch the production path to the legacy `analyst/` consensus logic
- Fine-tune models or train new LoRAs
- Add long-term persona memory across trading sessions

---

## 4. Design Principles

### 4.1  Preserve current foundations — extend, do not rebuild

The following are confirmed working and must not be replaced:

- `AnalystOutput` Pydantic schema (typed, validated, safe fallback)
- Parallel analyst fan-out in `parallel_analyst_node`
- `MINIMUM_VALID_ANALYSTS` quorum gate before Arbiter
- `FinalVerdict` + `NO_TRADE` fallback on malformed output
- Configurable analyst roster via `llm_routing.yaml`

### 4.2  Separate four concerns in code

The current system conflates these. The refinement plan keeps them as separate design axes:

| Concern | Definition | Lives in |
|---|---|---|
| **Persona identity** | What lens this analyst represents | `PersonaContract` (name, stance, domain) |
| **Persona behavior** | How that lens constrains output — enforced by validators | `PersonaContract.validator_rules` (named registry) |
| **Governance authority** | How much weight or veto power this analyst has | `GovernanceSummary` + governance policy module |
| **Observability** | How behavior is logged, surfaced in Reflect, and replayed | `run_record.json` + audit JSONL + Reflect bundle |

A persona can be sharply defined without being heavily weighted. A risk officer can have limited analytical breadth but high veto authority. These are independent axes — do not conflate them in code.

### 4.3  Measurement before trait redesign

No persona trait changes are permitted until a baseline divergence benchmark exists. Redesigning traits before measurement risks building a more elaborate but still unprovable persona layer.

---

## 5. Sequencing — Hard Gates

```
P1 Observability ──► P2 Divergence benchmark ──────────────────────────────────► P3 Persona contracts
                              │
                     mandatory fork after P2 report:
                     ├── high divergence  → proceed to P3 (targeted refinement)
                     └── low divergence   → P2b Structural Differentiation first,
                                            then P3 on top of strengthened foundation

P3 ──► P4 Arbiter governance ──► P5 Reflect drilldown + versioning ──► P6 Controlled enhancements
```

| Gate | Closes after | Must have before proceeding |
|---|---|---|
| **Gate A** | End of P1 | `persona_id` in `AnalystOutput`, `prompt_manifest` in `run_record`, `disagreement_summary` in `run_record`, Reflect bundle includes full analyst output blocks |
| **Gate B** | End of P2 | P2 baseline report committed; fork decision made (targeted refinement vs. structural differentiation); P2b complete if triggered |
| **Gate C** | End of P3 | Typed persona contracts, normalised bias/action extraction, legacy `analyst/arbiter.py` review completed, trait validators live |
| **Gate D** | End of P4 | Governance summary in production path, at least one deterministic veto path and one downgrade path in code |
| **Gate E** | End of P5 | Replay endpoint live, persona versioning active, Reflect drilldown complete |

---

## 6. Phase Breakdown

### P1 — Observability & Reproducibility Hardening

**Goal:** Make current personas measurable before changing their design. A run cannot be debugged or replayed until its full stack trace is retrievable as a single artifact.

**Scope**

- Add `persona_id: PersonaType` field to `AnalystOutput`
- Add `prompt_manifest` to `run_record.json` — full structure:
  ```json
  {
    "personas": {
      "default_analyst": { "file": "str", "sha256": "str", "size": "int" },
      "risk_officer":    { "file": "str", "sha256": "str", "size": "int" }
    },
    "arbiter_template": { "file": "str", "sha256": "str" },
    "model_profile": "str",
    "temperature": "float"
  }
  ```
- Compute and persist `disagreement_summary` in `run_record.json`:
  - `bias_counts`: `{ bullish | bearish | neutral | ranging → count }`
  - `action_histogram`: `{ recommended_action → count }`
  - `no_trade_count`, `mean_confidence`, `min_confidence`
  - `consensus_class`: `unanimous | strong_majority | split | veto_candidate | chaotic`
- Extend `/reflect/run/{run_id}` response to include the full list of `AnalystOutput` dicts (hydrated from audit JSONL when available)
- _(Nice-to-have)_ Persist `bias_detector` advisory as a first-class `run_record` field

**Key files likely affected**

`ai_analyst/models/analyst_output.py` · `ai_analyst/graph/logging_node.py` · `ai_analyst/core/logger.py` · `ai_analyst/api/services/reflect_bundle.py` · `ai_analyst/api/routers/reflect.py`

**Acceptance criteria — split by PR**

PR-PER-1 is done when:
- `run_record.json` persists `persona_id` per analyst, `prompt_manifest`, and `disagreement_summary` on both success and analyst failure paths
- Unit tests verify `disagreement_summary` calculation in isolation — including all five `consensus_class` values — not only that the field is written
- `prompt_manifest` SHA-256 hashes match the actual files used (verified by test that mutates a file and checks hash changes)

PR-PER-2 is done when:
- A single `/reflect/run/{id}` response allows reconstruction of: `ground_truth → per-persona outputs → disagreement_summary → final_verdict`
- Integration test confirms analyst output blocks hydrate correctly when audit JSONL is present and degrade gracefully when it is absent

Gate A closes when both PRs pass.

---

### P2 — Divergence Baseline (mandatory fork)

**Goal:** Produce numbers, not narratives. Answer: *are the current five personas actually different?*

This is the fork in the road. The outcome determines whether P3 proceeds directly or whether P2b runs first.

**Benchmark implementation**

Build `tests/benchmarks/persona_divergence/`:

- Frozen input packet corpus — minimum coverage:
  - Obvious trend continuation
  - Obvious mean-reversion setup
  - Choppy / ranging environment
  - High-volatility / risk-off event
  - Ambiguous setup (no clear signal)
  - Clean no-trade case
  - _(Optional)_ Synthetic setups designed to maximise expected disagreement
- Run matrix: same packet × full default roster × **N=100 repeats minimum**
- Run at **two temperatures**: `0.1` (production default) and `0.3` (diagnostic)
  - This separates "temperature suppresses divergence" from "prompts produce no divergence"
  - If divergence is low at 0.1 but high at 0.3, the problem is temperature — not persona design
  - If divergence is low at both, the problem is persona prompt design

**Metrics to compute**

| Metric | Why it matters |
|---|---|
| Bias agreement rate (Fleiss' kappa or simple %) | Direct collapse indicator |
| Action distribution entropy | Measures spread of `recommended_action` |
| No-trade rate per persona | Checks whether safety personas behave differently |
| Pairwise reasoning cosine similarity | Structural overlap in analyst prose |
| Contradiction frequency | How often outputs explicitly oppose each other |
| Risk officer / prosecutor stance adherence rate | Directly tests whether claimed traits manifest |
| Arbiter override rate by persona position | Whether Arbiter systematically ignores any persona |

**Fork decision after P2 report**

| Result | Decision | Next step |
|---|---|---|
| Divergence meaningful at both temps | Targeted refinement path | Proceed to P3 |
| Divergence low at 0.1, present at 0.3 | Temperature is the suppressor | P2b: introduce per-persona temperature overrides before P3 |
| Divergence low at both temps | Persona prompt design is the problem | P2b: structural differentiation before P3 |

**Acceptance criteria**

- Benchmark harness is deterministic and repeatable on frozen inputs at both temperature settings
- A committed baseline report (tables + exemplar runs) answers with evidence which of the three fork outcomes applies
- The script can be re-run after any later change to produce a quantified delta

---

### P2b — Structural Differentiation (conditional — triggered by fork)

**Goal:** Only runs if P2 confirms divergence is insufficient. Close the structural gap before formalising contracts on a collapsed foundation.

**Scope (pick from, based on P2 findings)**

1. Introduce per-persona temperature overrides in roster config — `prosecutor: 0.30`, `risk_officer: 0.05`
2. Introduce per-persona model profile overrides for one or two personas
3. Give `risk_officer` / `skeptical_quant` an enriched data view (drawdown history, VaR summary)

**Rule:** Every change in P2b must be re-benchmarked against the P2 corpus before P3 begins. P2b is not done until the benchmark shows measurable divergence improvement.

---

### P3 — Persona Contract Formalisation

**Goal:** Convert persona identity from prompt-only text into machine-readable, versioned, serialisable contracts.

**Core model**

```python
class PersonaContract(BaseModel):
    persona_id: PersonaType
    version: str                           # e.g. "v1.0"
    display_name: str
    primary_stance: Literal[
        "balanced", "risk_averse", "adversarial",
        "method_pure", "skeptical_prob"
    ]
    temperature_override: float | None     # None = use global default
    model_profile_override: str | None     # None = use global default
    must_enforce: list[str]                # human-readable mandatory constraints
    soft_constraints: list[str]
    validator_rules: list[str]
    # Named references into the validator registry — NOT inline Callables.
    # e.g. ["risk_officer.no_aggressive_buy_without_confidence"]
    # Validators are registered in ai_analyst/core/persona_validators.py
    # and looked up by name at runtime. Contracts remain serialisable as JSON.
```

**Why not `Callable` in `validator_rules`:** Inline callables cannot be stored as JSON, committed to git as config, or diffed between versions. Named registry references make contracts serialisable, versionable, and reviewable as data without touching Python.

**Validator registry pattern**

```python
# ai_analyst/core/persona_validators.py
VALIDATOR_REGISTRY: dict[str, Callable[[AnalystOutput], bool | str]] = {
    "risk_officer.no_aggressive_buy_without_confidence": lambda o: (
        True if o.recommended_action != "STRONG_BUY" or o.confidence >= 0.75
        else "risk_officer: STRONG_BUY requires confidence >= 0.75"
    ),
    "prosecutor.requires_counter_argument": lambda o: (
        True if _has_negation(o.reasoning)
        else "prosecutor: reasoning must contain a counter-argument"
    ),
    # etc.
}
```

**Rule:** This phase formalises the current roster as-is. It does not redesign persona traits.

**Contract targets (active personas)**

| Persona | Key contract constraint | Validator name |
|---|---|---|
| `default_analyst` | Balanced baseline — no mandatory stance overrides | _(none required initially)_ |
| `risk_officer` | `recommended_action` must not be `STRONG_BUY` unless `confidence ≥ 0.75` | `risk_officer.no_aggressive_buy_without_confidence` |
| `prosecutor` | `reasoning` must contain ≥1 negation or counter-argument pattern | `prosecutor.requires_counter_argument` |
| `ict_purist` | If `htf_bias != neutral`, reasoning must cite an ICT concept | `ict_purist.requires_ict_citation` |
| `skeptical_quant` | Uncertainty expressed probabilistically; add to default roster via config + contract only | `skeptical_quant.requires_probabilistic_language` |

**Validators — start conservative**

Validators log violations and optionally downgrade confidence. They are not hard blockers on day one. The registry pattern means a validator can be promoted from soft to hard without changing the contract — only the registry entry changes.

**Acceptance criteria**

- Every active persona has a typed `PersonaContract` object committed as JSON or YAML config — not only a prompt file
- Each persona has at least one named validator in the registry
- `PersonaContract` round-trips through JSON serialisation without data loss
- Validators are tested in isolation (no LLM required in the test loop)
- Adding `skeptical_quant` to the default roster is a config line + contract entry — no code scatter
- Changing a persona requires a contract version bump that is visible in git diff

---

### P4 — Deterministic Pre-Arbiter Governance

**Goal:** Close the gap between governance language and executable governance logic.

The audit confirmed: `MINIMUM_VALID_ANALYSTS` quorum exists at the analyst stage. At the Arbiter stage, quorum/veto/debate semantics are prompt-described only.

**Before implementing this phase:** Review `analyst/arbiter.py` and `analyst/personas.py` in the legacy package. The audit flagged these as a reference implementation for reusable deterministic consensus patterns. Extract before writing new code.

**New pre-Arbiter governance node**

Receives: `list[AnalystOutput]`  
Produces: `GovernanceSummary`

```python
class VetoSignal(BaseModel):
    persona: str
    reason: str
    strength: float                    # 0.0–1.0

class GovernanceSummary(BaseModel):
    bias_vote_table: dict[str, int]    # { "bullish": 3, "bearish": 1, ... }
    action_vote_table: dict[str, int]  # { "BUY": 2, "NO_TRADE": 2, ... }
    veto_signals: list[VetoSignal]
    consensus_level: Literal[          # classification of the vote only
        "unanimous",
        "strong_majority",
        "split",
        "insufficient"
    ]
    veto_applied: bool                 # separate from consensus_level — a unanimous
                                       # vote can still have a veto applied
    confidence_ceiling_suggestion: float | None
```

Note: `veto_applied` is kept separate from `consensus_level`. A unanimous vote and an applied veto are orthogonal facts — conflating them into a single enum value loses information.

**First deterministic rules (start minimal)**

| Rule | Mechanism |
|---|---|
| `risk_officer` issues `NO_TRADE` with confidence above threshold | Set `veto_applied=True`; force `NO_TRADE` or apply confidence ceiling |
| Analyst disagreement exceeds split threshold | Set `consensus_level="split"`; downgrade `confidence_ceiling_suggestion` |
| `valid_analyst_count < MINIMUM_VALID_ANALYSTS` | Skip LLM call entirely; emit `NO_TRADE` directly |
| All personas agree | Set `consensus_level="unanimous"`; do not treat as proof of correctness — log explicitly |

**Updated Arbiter flow**

Arbiter prompt receives: `GovernanceSummary` + raw `analyst_outputs`. The LLM synthesis call is now informed by a precomputed, deterministic governance layer — not only by the raw array.

**Acceptance criteria**

- At least one veto path and one disagreement downgrade path are enforced in Python code
- Arbiter no longer relies solely on raw persona text for governance semantics
- Final verdict artifact includes both `governance_summary` and arbiter narrative synthesis
- Tests cover veto/quorum logic deterministically — no LLM in the test loop
- `GovernanceSummary` is persisted in `run_record` / audit log

---

### P5 — Reflect Persona Drilldown & Versioning

**Goal:** Make persona analysis inspectable in the product, not only in log files.

The audit classified current Reflect visibility as **B — Partial**. Reflect computes participation and aggregated metrics but does not expose individual analyst reasoning.

**Scope**

Backend:
- Extend `/reflect/run/{run_id}` bundle to include full `AnalystOutput` blocks from audit JSONL
- Add `persona_package_version` tag to all runs (SemVer or date-hash of prompt manifest)
- Add `/reflect/replay` endpoint: accepts frozen `analyst_outputs` + `governance_summary`, re-runs Arbiter only

UI:
- Per-run persona panel: bias / confidence / `recommended_action` row per analyst
- Per-persona reasoning block (expandable)
- Disagreement matrix / vote tally component
- Arbiter relation display: `supported | challenged | ignored | overridden`

**Acceptance criteria**

- A user can open any run in Reflect and answer: what each persona said, how strongly they said it, where disagreement occurred, and how the Arbiter resolved it
- A historical run can be re-evaluated without re-running the analyst fan-out
- A change in Arbiter behaviour can be isolated and compared against a frozen analyst output set
- `persona_package_version` is present on all new runs from this point forward

---

### P6 — Controlled Persona Enhancement

**Goal:** Only now begin actual persona refinement — safely, measurably, with a defined rollback path.

After P1–P5, the repo can answer: *should we refine the current traits or structurally differentiate personas?*

**Enhancement candidates — ordered safest to riskiest**

1. Enable `skeptical_quant` in default roster (config + contract only, no code change)
2. Introduce per-persona temperature overrides (e.g. `prosecutor: 0.25–0.40`, `risk_officer: 0.05`) — if not already done in P2b
3. Introduce light persona-specific evidence requirements via contract validators
4. Introduce model-profile variation for one or two personas (if router supports it)
5. Give `risk_officer` / `skeptical_quant` an enriched data view (drawdown history, VaR stats)
6. Add a devil's advocate persona — only if `prosecutor` is empirically insufficient

**Rules for every enhancement**

- Versioned: persona contract version bumped and tagged in run artifacts
- Benchmarked: run against P2 corpus to produce a quantified delta before merge
- Compared via replay: new Arbiter behaviour tested against frozen analyst outputs from prior runs
- No enhancement merged without a divergence comparison report

**Rollback policy**

An enhancement is considered failed if: the P2 corpus re-benchmark shows divergence regression, or Reflect shows a systematic increase in Arbiter override rate for the modified persona, or no-trade rate shifts unexpectedly outside a defined tolerance band.

Rollback procedure:
1. Revert the persona contract version in config (single file change — no code change required)
2. The `persona_package_version` tag on future runs will reflect the revert
3. Replay affected historical runs against the reverted contract using the `/reflect/replay` endpoint to confirm behaviour is restored
4. Document the failed enhancement and findings in `docs/persona_experiments/`

---

## 7. PR Sequence

| PR | Scope | Phase | Critical path |
|---|---|---|---|
| `PR-PER-1` | `persona_id` field · `prompt_manifest` · `disagreement_summary` persistence + calculation tests | P1 | ✅ |
| `PR-PER-2` | `/reflect/run/{id}` bundle expansion · analyst output blocks in Reflect UI | P1 | ✅ |
| `PR-PER-3` | Divergence benchmark harness · corpus · dual-temperature run · baseline report committed to `docs/` | P2 | ✅ |
| `PR-PER-4` | `PersonaContract` schema · validator registry · roster migration to typed definitions | P3 | ✅ |
| `PR-PER-5` | Trait validators · soft violation logging · confidence downgrade hooks | P3 | ✅ prerequisite for PR-PER-7 |
| `PR-PER-6` | `GovernanceSummary` module · pre-Arbiter disagreement matrix · consensus classification | P4 | ✅ |
| `PR-PER-7` | First deterministic veto gate (`risk_officer`) · disagreement downgrade path wired | P4 | ✅ |
| `PR-PER-8` | `/reflect/replay` endpoint · frozen analyst-output Arbiter replay | P5 | ✅ |
| `PR-PER-9` | `persona_package_version` tagging · version manifest | P5 | ✅ |
| `PR-PER-10` | Controlled persona diversification · temperature/model overrides · roster expansion | P6 | — |

**Recommended start order:**

```
PR-PER-1 → PR-PER-2 → [Gate A] → PR-PER-3 → [Gate B / fork decision]
→ PR-PER-4 → PR-PER-5 → [Gate C] → PR-PER-6 → PR-PER-7 → [Gate D]
→ PR-PER-8 → PR-PER-9 → [Gate E] → PR-PER-10
```

PR-PER-5 (validators) must land before PR-PER-7 (first veto gate). A veto fired on an unvalidated output cannot be reliably tested.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| **Overengineering too early** — persona studio, user-editable traits, marketplace | Not in scope for this plan. Decide after Gate E is confirmed stable. |
| **Validators too rigid** — brittle contracts block legitimate model behaviour | Start validators as soft guardrails: log violations, optionally downgrade confidence. Promote to hard-fail only with evidence. |
| **Conflating governance with personality** — persona tone/style merged with veto authority | Enforced by the four-concern separation in Section 4.2. `primary_stance` and governance authority are different fields in different modules. |
| **Tuning before measurement** — trait edits before P2 baseline | Gate B enforces this. No trait PR is merged before the benchmark report exists. |
| **Legacy arbiter patterns ignored** — deterministic logic in `analyst/arbiter.py` not consulted | Mandatory pre-P4 step. Treat it as a reference implementation, not dead code. |
| **Temperature suppression masking collapse** — N=100 at temp=0.1 may just confirm low variance | P2 runs at both 0.1 and 0.3. Fork decision accounts for temperature as a variable. |
| **Enhancement regression with no rollback path** — P6 changes degrade live analysis quality | Rollback policy defined in P6: contract version revert + replay endpoint verification. |

---

## 9. One-Line Summary

> Make the current five personas observable, reproducible, and measurable. Prove or falsify collapse — and understand whether temperature or prompt design is the suppressor — before redesigning traits. Make governance partly deterministic before trusting prompt language for veto semantics. Reflect drilldown closes the tuning loop.

---

## 10. Open Unknowns (must resolve before Gate A)

| Unknown | Blocking question | Action |
|---|---|---|
| Deployed `config/llm_routing.yaml` | Actual production roster and model profile diversity are unknown | Retrieve and diff against example config |
| Empirical divergence — current personas | Whether traits produce meaningfully different outputs is INFERRED, not confirmed | Run P2 benchmark before any trait changes |
| Prompt hash per run | No per-run prompt snapshot exists yet | P1 prerequisite — cannot forensically reproduce runs without this |
| `ExecutionRouter` operational status | Unknown whether this is live or dead code; impacts replay capability | Confirm before specifying P5 replay endpoint |
| Legacy `analyst/arbiter.py` patterns | Whether deterministic consensus logic is reusable is not assessed | Mandatory pre-P4 review |

---

_Last updated: 2026-03-18 · v0.2 — addresses 11 issues from structured review. Next update expected after P2 baseline report and fork decision._
