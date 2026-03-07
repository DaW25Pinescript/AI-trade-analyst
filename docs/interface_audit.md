# Interface Audit Report — Trade Ideation Journey v1

Date: 2026-03-07
Status: Complete

---

## 1. Transport Pattern Decision

**Pattern A — File-based** is the primary transport for v1.

Rationale:
- `run_multi_analyst.py` writes output to `analyst/output/{instrument}_multi_analyst_output.json`
- `run_explain.py` writes to `analyst/output/{instrument}_multi_analyst_explainability.json`
- The existing FastAPI layer (`ai_analyst/api/main.py`) serves the original chart-upload analysis flow, not the multi-analyst journey flow
- No API endpoint currently wraps `run_multi_analyst` or `run_explain` for HTTP consumption
- The macro snapshot is already file-based: `app/data/macro_snapshot.json`

The frontend service layer will read saved JSON artifacts from `analyst/output/` and `app/data/`.
A thin adapter layer will normalize raw JSON into UI-consumable typed shapes.

---

## 2. Interface Inventory

### 2.1 Backend Producers

| Contract Name | Source File | Producer | Transport | Schema/Model | Status |
|---|---|---|---|---|---|
| MultiAnalystOutput | `analyst/multi_contracts.py` | `multi_analyst_service.run_multi_analyst()` | JSON file: `analyst/output/{instrument}_multi_analyst_output.json` | `MultiAnalystOutput.to_dict()` | `available_now` |
| ExplainabilityBlock | `analyst/explain_contracts.py` | `explain_service.run_explain()` | JSON file: `analyst/output/{instrument}_multi_analyst_explainability.json` | `ExplainabilityBlock.to_dict()` | `available_now` |
| StructureDigest | `analyst/contracts.py` | `pre_filter.py` | Embedded in MultiAnalystOutput.digest | `StructureDigest.to_dict()` | `available_now` |
| PersonaVerdict | `analyst/multi_contracts.py` | `personas.py` | Embedded in MultiAnalystOutput.persona_outputs[] | `PersonaVerdict.to_dict()` | `available_now` |
| ArbiterDecision | `analyst/multi_contracts.py` | `arbiter.py` | Embedded in MultiAnalystOutput.arbiter_decision | `ArbiterDecision.to_dict()` | `available_now` |
| AnalystVerdict | `analyst/contracts.py` | Arbiter re-expression | Embedded in MultiAnalystOutput.final_verdict | `AnalystVerdict.to_dict()` | `available_now` |
| ReasoningBlock | `analyst/contracts.py` | Per-persona | Embedded in PersonaVerdict.reasoning | `ReasoningBlock.to_dict()` | `available_now` |
| SignalInfluenceRanking | `analyst/explain_contracts.py` | `explainability.py` | Embedded in ExplainabilityBlock.signal_ranking | `SignalInfluenceRanking.to_dict()` | `available_now` |
| PersonaDominance | `analyst/explain_contracts.py` | `explainability.py` | Embedded in ExplainabilityBlock.persona_dominance | `PersonaDominance.to_dict()` | `available_now` |
| ConfidenceProvenance | `analyst/explain_contracts.py` | `explainability.py` | Embedded in ExplainabilityBlock.confidence_provenance | `ConfidenceProvenance.to_dict()` | `available_now` |
| CausalChain | `analyst/explain_contracts.py` | `explainability.py` | Embedded in ExplainabilityBlock.causal_chain | `CausalChain.to_dict()` | `available_now` |
| MarketPacketV2 | `market_data_officer/officer/contracts.py` | Market Data Officer | Not directly persisted as standalone JSON | `MarketPacketV2.to_dict()` | `requires_adapter` |
| MacroSnapshot | `app/data/macro_snapshot.json` | Feeder pipeline | JSON file | Feeder contract schema | `available_now` |

### 2.2 Frontend Consumers (existing)

| Consumer | Source File | Current Shape | Notes |
|---|---|---|---|
| Gate evaluation | `app/scripts/ui/gates.js` | Manual `ptcState` fields | Will be replaced by contract-backed gate model |
| State model | `app/scripts/state/model.js` | Flat ticket-centric state | Will be replaced by journey store |
| API bridge | `app/scripts/api_bridge.js` | Chart-upload FormData flow | Separate from journey flow; keep as-is |
| Macro page | `app/scripts/ui/macro_page.js` | Reads macro_snapshot.json | Can be adapted for journey macro stage |

---

## 3. Availability Matrix

### 3.1 Triage Board Fields

| Field | Used By | Current Source | Status | Notes |
|---|---|---|---|---|
| symbol/instrument | Triage card | `MultiAnalystOutput.instrument` | `available_now` | |
| triage_status | Triage card | Derivable from `ArbiterDecision.final_verdict` + `is_actionable()` | `derivable_now` | Adapter maps verdict → triage status |
| bias_hint | Triage card | `ArbiterDecision.final_directional_bias` | `available_now` | |
| why_interesting_tags | Triage card | `StructureDigest.structure_supports` + `caution_flags` | `derivable_now` | Adapter combines signal lists |
| rationale_summary | Triage card | `ArbiterDecision.winning_rationale_summary` | `available_now` | |
| confidence | Triage card | `ArbiterDecision.final_confidence` | `available_now` | |
| mini_chart | Triage card | Not produced | `missing` | Placeholder for v1 |
| consensus_state | Triage card | `ArbiterDecision.consensus_state` | `available_now` | |

### 3.2 Journey Bootstrap Fields

| Field | Used By | Current Source | Status | Notes |
|---|---|---|---|---|
| digest (full) | Asset Context, Structure | `MultiAnalystOutput.digest` | `available_now` | |
| persona_outputs | Asset Context | `MultiAnalystOutput.persona_outputs` | `available_now` | |
| arbiter_decision | Verdict | `MultiAnalystOutput.arbiter_decision` | `available_now` | |
| final_verdict | Verdict | `MultiAnalystOutput.final_verdict` | `available_now` | |
| explanation | Explainability | `MultiAnalystOutput.explanation` or separate file | `available_now` | |
| signal_ranking | Structure stage | `ExplainabilityBlock.signal_ranking` | `available_now` | |
| persona_dominance | Verdict stage | `ExplainabilityBlock.persona_dominance` | `available_now` | |
| confidence_provenance | Verdict stage | `ExplainabilityBlock.confidence_provenance` | `available_now` | |
| causal_chain | Gate Checks | `ExplainabilityBlock.causal_chain` | `available_now` | |
| macro_context | Macro stage | `app/data/macro_snapshot.json` | `available_now` | |
| market_features | Market Overview | `MarketPacketV2` | `requires_adapter` | Not persisted as standalone JSON |
| gate_seed_state | Gate Checks | Derivable from digest + causal_chain | `derivable_now` | |

### 3.3 Persistence Fields (UI-created)

| Field | Used By | Status | Notes |
|---|---|---|---|
| userDecision | Journal, Review | `missing` — UI creates this | New domain object |
| executionPlan | Journal, Review | `missing` — UI creates this | New domain object |
| decisionSnapshot | Journal | `missing` — UI creates this | Frozen at save time |
| journalNotes | Journal | `missing` — UI creates this | User-entered |
| evidenceRefs | Journal | `missing` — UI creates this | File references |
| resultSnapshot | Review | `missing` — UI creates this (later) | Post-trade capture |

### 3.4 Review Surface Fields

| Field | Used By | Status | Notes |
|---|---|---|---|
| review_patterns | Review | `missing` | Not yet produced by backend — stub required |
| override_frequency | Review | `missing` | Derivable from saved snapshots once journal exists |
| gate_failure_clusters | Review | `missing` | Derivable from saved snapshots once journal exists |

---

## 4. Adapter Register

| Adapter | Purpose | Input | Output |
|---|---|---|---|
| `triageAdapter` | Maps `MultiAnalystOutput` → triage card shape | `MultiAnalystOutput` JSON | `TriageItem` |
| `journeyBootstrapAdapter` | Maps `MultiAnalystOutput` + `ExplainabilityBlock` + `MacroSnapshot` → journey bootstrap | Multiple JSON files | `JourneyBootstrap` |
| `gatesSeedAdapter` | Derives initial gate states from `StructureDigest` + `CausalChain` | Digest + CausalChain | `GateState[]` |
| `marketFeaturesAdapter` | Placeholder — `MarketPacketV2` not persisted as standalone JSON | None | Stub with `requires_adapter` flag |

---

## 5. v1 Contract Freeze

The following shapes are frozen for v1 frontend consumption. The frontend service layer may depend on these field names and types.

### Frozen backend shapes (read-only, do not modify):
- `MultiAnalystOutput.to_dict()` — top-level container
- `ExplainabilityBlock.to_dict()` — explanation container
- `StructureDigest.to_dict()` — structure state
- `ArbiterDecision.to_dict()` — arbiter synthesis
- `PersonaVerdict.to_dict()` — per-persona output
- `AnalystVerdict.to_dict()` — final verdict
- `ReasoningBlock.to_dict()` — reasoning text
- `SignalInfluenceRanking.to_dict()` — ranked signals
- `PersonaDominance.to_dict()` — persona influence
- `ConfidenceProvenance.to_dict()` — confidence trace
- `CausalChain.to_dict()` — no-trade/caution drivers

### New UI-owned shapes (defined in Phase 1):
- `TriageItem` — derived from MultiAnalystOutput
- `JourneyState` — full journey domain object
- `GateCheckItem` — per-gate row state
- `SystemVerdict` — system recommendation (read from backend)
- `UserDecision` — human commitment (UI-created)
- `ExecutionPlan` — trade execution details (UI-created)
- `DecisionSnapshot` — frozen at save time
- `ProvenanceTag` — field-level provenance tracking

---

## 6. Gaps and Uncertainties

1. **MarketPacketV2** is not persisted as a standalone JSON file. Market features for the overview stage will use a stub adapter until a persistence path is established.
2. **Review patterns** are not yet produced by any backend service. The review surface will use explicit stubs.
3. **Mini-charts** for triage cards have no data source. Placeholder treatment in v1.
4. The macro snapshot format (`app/data/macro_snapshot.json`) is a feeder contract, not a dedicated journey contract. An adapter will normalize it for the macro alignment stage.
