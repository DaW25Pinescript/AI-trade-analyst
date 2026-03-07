# OBJECTIVE.md

# AI Trade Analyst – Objective
Version: 1.0

## 1. Primary Objective

Transform AI Trade Analyst from a static analysis form into a guided **Trade Ideation Journey**: a stage-based trading workspace that pre-loads market, macro, and structure intelligence, triages assets by relevance, and guides the user through a disciplined, auditable trade-construction flow.

---

## 2. Product Outcome

The app should no longer feel like a blank page waiting for manual setup.

It should feel like:
- a live market workspace
- a triage-first analyst desk
- a controlled decision pipeline
- a journal-ready decision system
- a transparent review engine foundation

---

## 3. Specific Objectives

### 3.1 Replace blank-form entry with pre-loaded intelligence
The landing experience should open into a useful market overview where each asset answers: **Why should I care about this right now?**

### 3.2 Introduce a staged ideation workflow
The selected asset should enter a structured journey with explicit stages for context, structure, macro alignment, gate review, verdict, and journal capture.

### 3.3 Preserve auditability
The system must preserve a frozen decision record that captures what the system recommended, what the user decided, and what execution plan was committed.

### 3.4 Enable later review and self-critique
The architecture must support transparent review flows such as override analysis, gate failure patterns, rule refinement, and planned-vs-actual comparison.

### 3.5 Ground the UI in repo reality
Before major UI implementation, complete a formal interface audit so the frontend builds against real repo inputs/outputs rather than guessed payloads.

---

## 4. Success Criteria

This objective is achieved when:
- the product has a triage-first landing surface
- the journey stages are coherent and auditable
- gate checks behave like a control boundary
- system verdict and user decision are distinct and persisted separately
- a decision snapshot can be saved and reviewed later
- the UI contract layer is derived from audited repo interfaces

---

## 5. Stage-by-Stage Delivery Objective

### Phase 0
Complete the interface audit and freeze v1 contracts.

### Phase 1
Define the journey domain model, shared types, and store API.

### Phase 2
Build the shell, routes, and step navigation.

### Phase 3
Build the landing triage board.

### Phase 4
Build context, structure/liquidity, and macro alignment screens.

### Phase 5
Implement gate checks as a strict discipline checkpoint.

### Phase 6
Implement verdict separation and execution planning.

### Phase 7
Implement journal capture and frozen decision snapshot persistence.

### Phase 8
Add the first review engine surface.

### Phase 9
Harden contracts, resolve adapter gaps, clean placeholder drift, and stabilise the review surface.

Outputs:
- contract conformance tests for each stage
- resolved or explicitly deferred `requires_adapter` fields
- no silent mock values remaining in production paths
- review surface traceable to saved `decisionSnapshot` and `ExplainabilityBlock` fields
- transport pattern locked and consistent across all service calls

---

## 6. Long-Term Direction

The long-term intent is not just a nicer frontend. It is a controlled trading decision environment where:
- intelligence is pre-loaded
- decisions are staged and reviewable
- human overrides are measurable
- policy refinement is possible without black-box claims
