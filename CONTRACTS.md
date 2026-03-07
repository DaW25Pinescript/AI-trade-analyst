# CONTRACTS.md

# AI Trade Analyst – Contract Direction
Version: 1.0

## 1. Contract Philosophy

The Trade Ideation Journey frontend must be backed by explicit contracts. Contract work begins with an interface audit of existing repo producers and only then introduces a narrow v1 contract layer the UI is allowed to depend on.

This document does **not** assume all desired backend shapes already exist. It defines how contracts should be discovered, frozen, and consumed.

---

## 2. Contract Lifecycle

### Stage A — Interface Audit
Inventory existing producers and consumers.

Audit:
- request/response models
- JSON schemas
- saved artifacts
- officer outputs
- arbiter outputs
- current app export/import shapes
- CLI and batch outputs that may influence UI state

### Stage B — Availability Classification
For each required field, classify:
- `available_now`
- `derivable_now`
- `missing`
- `unstable`
- `deprecated`
- `requires_adapter`

### Stage C — v1 Contract Freeze
Define the minimal, stable UI-facing contract layer for the first journey release.

### Stage D — Adapter Layer
Where repo reality and UI needs do not line up, use explicit adapters rather than silently widening the frontend model.

### Stage E — Conformance Testing
Ensure the frontend service layer and backend producers satisfy the frozen contracts.

---

## 3. Required Contract Artifacts

The audit/freeze phase should leave behind these artifacts:

### 3.1 Interface Inventory
A machine- and human-readable list of upstream producers and downstream consumers.

Suggested fields:
- contract name
- source file/module
- producer owner
- consumer owner
- transport type
- schema/model reference
- status
- notes

### 3.2 Availability Matrix
A field-level matrix for all journey-critical data.

Suggested columns:
- field name
- used by screen/stage
- current source
- status
- type confidence
- notes

### 3.3 v1 Contract Freeze
A frontend-safe contract definition for the journey.

### 3.4 Adapter Register
List of fields/endpoints that require transformation before the UI can consume them safely.

---

## 4. Journey Domain Contract Surface

The frontend journey contract should cover, at minimum, these domain objects:

### 4.1 Triage Item
Intent:
- describe an asset on the landing board

Must support concepts such as:
- symbol
- triage status
- why-interesting tags
- regime/bias hint
- mini-chart reference or placeholder
- rationale summary

### 4.2 Journey Bootstrap
Intent:
- deliver the initial state needed to open a journey for a selected asset

Must support concepts such as:
- selected asset metadata
- stage-prefill blocks
- macro summary
- structure summary
- gate seed state
- system context summary

### 4.3 Journey Update Payload
Intent:
- update the staged journey draft without committing the final decision snapshot

Must support concepts such as:
- current stage
- partial stage data
- notes
- overrides
- evidence references
- gate changes

### 4.4 Ticket / Decision Commit Payload
Intent:
- commit the final decision record

Must support concepts such as:
- frozen decision snapshot
- system verdict
- user decision
- execution plan
- provenance metadata
- save timestamp

### 4.5 Result Snapshot Payload
Intent:
- attach actual outcome data later for review

Must support concepts such as:
- outcome status
- result notes
- post-trade evidence
- realized metrics
- review tags

### 4.6 Review Pattern Response
Intent:
- power transparent review surfaces

Must support concepts such as:
- planned vs actual comparisons
- override frequency patterns
- gate failure clusters
- policy refinement suggestions

---

## 5. Suggested Endpoint Direction

These are architectural endpoint targets, pending audit and ownership confirmation:
- `GET /watchlist/triage`
- `GET /journey/:asset/bootstrap`
- `POST /journey/update`
- `POST /tickets/create`
- `POST /journal/result`
- `GET /review/patterns`

These are not permission to invent payloads. They are routing intentions that must be grounded in real backend capabilities.

**Known backend sources to map against during audit:**

| Endpoint intent | Known backend producer | Artifact location |
|---|---|---|
| Journey bootstrap — structure/verdict state | `MultiAnalystOutput` | `analyst/output/{instrument}_multi_analyst_output.json` |
| Journey bootstrap — explainability | `ExplainabilityBlock` | `analyst/output/{instrument}_multi_analyst_explainability.json` |
| Journey bootstrap — market features | `MarketPacketV2` | `market_data_officer/officer/contracts.py` |
| Triage board — per-asset summary | Derivable from `MultiAnalystOutput.arbiter_decision` + `StructureDigest` | Adapter required |
| Review patterns | Not yet produced | Missing — stub required |

The transport pattern (file-based vs API wrapper) must be confirmed during the audit before any endpoint is implemented.

---

## 6. Frontend Contract Rules

### 6.1 Services own transport details
Components should consume typed service methods, not raw fetch logic or guessed JSON.

### 6.2 UI types must map to frozen contracts
Frontend types may enrich local interaction state, but backend-backed fields must remain traceable to audited contract shapes.

### 6.3 Provenance is a contract concern
Field provenance is not just UI decoration. It must be carried in the domain model where relevant.

### 6.4 Snapshots are immutable artifacts
A `decisionSnapshot` should be treated as a frozen artifact once saved, not a mutable draft object.

---

## 7. Contract Exit Criteria

The contract layer is considered ready when:
- journey-critical fields have a known source or explicit adapter
- frontend service methods are typed against frozen shapes
- missing fields are documented rather than guessed
- acceptance tests can validate contract conformance at phase boundaries
