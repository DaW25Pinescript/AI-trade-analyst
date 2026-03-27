# ADR: Harness Engineering Patterns for AE v1 Pipeline

**Status:** Seed (forward-looking — not scheduled for implementation)
**Date:** 2026-03-22
**Author:** David (architecture), Claude (drafting)
**Context:** Brainstorm from AI Automators Ep6 harness engineering video mapped against existing AE v1 pipeline

---

## 1. The Core Insight

The AE v1 pipeline (lenses → Evidence Snapshot → persona runs → arbiter → validators) **is already a harness** — a deterministic software layer controlling how LLM calls interact with tools, state, and outputs. The term "harness engineering" gives us shared vocabulary for patterns we've built intuitively and, more importantly, names the gaps we haven't addressed yet.

### Analogy

Think of the pipeline as a trading desk:
- **Lenses** = research analysts producing independent reports (deterministic, no LLM)
- **Evidence Snapshot** = the briefing packet circulated to the desk (immutable artifact)
- **Persona runs** = individual traders forming independent views
- **Arbiter** = the desk head synthesising views into a single call
- **Validators** = compliance checking the output before it leaves the desk

Harness engineering asks: are the Chinese walls between traders real, or are they just suggestions?

---

## 2. Mapping: AE v1 → Harness Taxonomy

| Harness Concept | AE v1 Equivalent | Status |
|---|---|---|
| Programmatic phase (deterministic) | Lens computations (Structure, Trend, Momentum) | ✅ Built |
| Workspace file / intermediate artifact | Evidence Snapshot (immutable dict) | ✅ Built |
| LLM single-agent phase | Persona runs with v2.0 typed prompts | ✅ Built |
| Post-harness synthesiser | Arbiter node (Opus) | ✅ Built |
| Validation gates (blocking) | Validators exist but are **soft-level only** (flag, don't block) | ⚠️ Gap |
| Workspace input isolation | **Not implemented** — GraphState is shared bag | 🔴 Gap |
| Phase-level checkpointing | **Not implemented** — no resume-from-failure | 🔴 Gap |
| Parallel sub-agent execution | **Not implemented** — personas run sequentially | 🔴 Gap |
| Human-in-the-loop mid-pipeline | **Not implemented** — user kicks off run and waits | 🔴 Gap |
| State machine (phase tracking) | LangGraph topology is fixed but no `harness_runs` recovery table | 🔴 Gap |
| Model mixing by cost/capability | Sonnet for personas, Opus for arbiter | ✅ Built |
| Programmatic output generation | AnalysisEngineOutput is structured data (not free-form LLM) | ✅ Built |

---

## 3. Priority Gap: Context Isolation (Input Envelopes)

### 3.1 Problem Statement

Currently, `analyst_nodes.py` persona functions pull from `GraphState`, which is a shared mutable bag. Any persona node can technically read:
- Other personas' partial results (during fan-in merge)
- Raw lens computation internals (not just the snapshot)
- Pipeline metadata unrelated to their analytical mandate

This is the **open-outcry floor problem**: personas can hear each other before forming independent views. Convergence in this architecture is ambiguous — you can't distinguish "strong consensus from diverse lenses" from "groupthink from shared context."

### 3.2 The Pattern: Input Envelopes

Each persona run receives a **sealed, typed, read-only envelope** containing only what that persona is authorised to see. The persona function receives the envelope, never the full `GraphState`.

```
┌─────────────────────────────────────────────┐
│                 GraphState                   │
│  (full pipeline state — shared, mutable)     │
└──────────────────┬──────────────────────────┘
                   │
          build_persona_envelope()
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐   ┌────────┐   ┌────────┐
│Envelope│   │Envelope│   │Envelope│   ... (one per persona)
│  risk  │   │  ict   │   │  quant │
│officer │   │ purist │   │        │
└────────┘   └────────┘   └────────┘
    │              │              │
    ▼              ▼              ▼
  [Run]          [Run]          [Run]
    │              │              │
    └──────────────┼──────────────┘
                   ▼
            Arbiter (Opus)
```

### 3.3 Envelope Contract (Draft)

```python
@dataclass(frozen=True)
class PersonaInputEnvelope:
    """Immutable input for a single persona run.
    
    Design rule: No persona run shall receive as input any artifact
    produced by another persona run within the same analysis cycle.
    """
    # What the persona analyses
    evidence_snapshot: dict          # Immutable lens outputs
    instrument_context: InstrumentConfig  # Read-only instrument metadata
    
    # How the persona thinks
    persona_id: str                  # Registry key
    persona_prompt: str              # v2.0 typed prompt from registry
    
    # What the persona DOES NOT receive:
    # - Other personas' outputs (isolation boundary)
    # - Raw lens internals beyond the snapshot
    # - Arbiter configuration or prior arbiter outputs
    # - Pipeline metadata (stage traces, timing, etc.)
    # - Validator results from prior runs
```

### 3.4 The Isolation Boundary Rule

> **No persona run shall receive as input any artifact produced by another persona run within the same analysis cycle.**

This is the Chinese wall. It's the single sentence that governs information flow in every future spec that touches persona execution.

### 3.5 Acceptance Test (Build-Time)

When this is eventually implemented, the verification is:

1. Mock one persona (e.g., `prosecutor`) to return garbage output.
2. Run the full pipeline.
3. Assert the other four personas produce **identical output** to a control run where all five succeed.
4. If outputs differ → there is context leakage across the isolation boundary.

### 3.6 Why This Matters for Three Pending Decisions

**Convergence experiment (dual-temperature, N=100):**
Running the experiment on shared-state architecture means results carry an asterisk. Isolation-first gives clean signal. Not a blocker — but the experiment's conclusions are stronger with isolation in place.

**PR-AE-6 Governance Layer:**
Context isolation reframes governance from "audit outputs after the fact" to "control inputs before execution." Governance defines the envelope schema per persona, not just the validator rules post-output.

**Parallel persona execution:**
Isolated envelopes with no shared mutable state = fan-out in LangGraph with zero concurrency risk. Parallelisation becomes a topology change, not an architecture change. Estimated speedup: 5x (sequential 15-25s → parallel 3-5s).

---

## 4. Other Harness Patterns to Plant (Lower Priority)

### 4.1 Validator Gates (Blocking)

**Current state:** All v1 validators are soft-level (flag, don't block).
**Future state:** Promote critical validators to hard gates between persona output and arbiter input. A persona response with zero evidence references gets rejected and retried, not passed through.

**Analogy:** Your validators are currently a stop-loss drawn on the chart but not wired to your broker. Wiring them means they execute automatically.

**Seed decision:** When building this, distinguish between:
- **Structural validators** (response has required fields, references snapshot data) → hard gate, auto-retry
- **Quality validators** (response shows analytical depth, avoids generic language) → soft flag, human review

### 4.2 Phase-Level Checkpointing

**Current state:** If persona 3/5 fails (API timeout), the entire run restarts.
**Future state:** A `harness_runs` record tracking `current_phase`, `phase_results`, `status` enables resume-from-failure.

**Implementation sketch:**
```python
# Conceptual — not for implementation now
harness_run = {
    "run_id": "...",
    "current_phase": "persona_runs",
    "completed_phases": {
        "lens_computation": {"status": "complete", "result_ref": "snapshot_abc"},
        "persona:risk_officer": {"status": "complete", "result_ref": "..."},
        "persona:ict_purist": {"status": "complete", "result_ref": "..."},
        "persona:prosecutor": {"status": "failed", "error": "timeout"},
    },
    "resume_from": "persona:prosecutor"
}
```

### 4.3 HITL Injection Point

**Current state:** User kicks off a run and waits for results. No mid-pipeline input.
**Future state:** After Evidence Snapshot is computed but before persona runs, optionally pause for user context: directional bias, news events, "NFP in 30 minutes", etc.

**Design note:** This maps to the MacroLens gap. The MacroLens was scoped as Alpha Vantage data (formatting only), but the harness pattern suggests a richer option: a pause point where human context enters as a first-class input alongside the snapshot. These could coexist — MacroLens for automated macro data, HITL for discretionary trader context.

---

## 5. What NOT to Import from the Harness Pattern

Not everything from the Ep6 video applies. Explicitly deprioritised:

- **DOCX/PDF deliverable generation:** Output consumers are the UI and journal, not a boardroom. Low leverage.
- **DAG-based dynamic planning:** The AE v1 pipeline has a fixed, known topology. Dynamic replanning is overkill.
- **Virtual file system:** The Evidence Snapshot already serves as the intermediate artifact. A full VFS adds complexity without clear benefit at current scale.
- **Deep Mode (LLM-controlled flow):** The pipeline is deterministic-first by design. LLM-controlled flow contradicts the evidence-first architecture decision.

---

## 6. Vocabulary Lock

For consistency across future specs, adopt this terminology:

| Term | Meaning in AE Context |
|---|---|
| **Harness** | The deterministic software layer controlling the AE v1 pipeline end-to-end |
| **Phase** | A discrete step in the pipeline (lens computation, persona run, arbiter, validation) |
| **Input Envelope** | The sealed, typed, read-only input a persona receives |
| **Isolation Boundary** | The rule preventing cross-persona information leakage |
| **Hard Gate** | A validator that blocks phase advancement on failure (auto-retry) |
| **Soft Flag** | A validator that reports but does not block (current v1 behaviour) |
| **Checkpoint** | A persisted record of completed phases enabling resume-from-failure |
| **HITL Injection** | A pause point for human input mid-pipeline |

---

## 7. Next Actions (When Ready)

1. **Before convergence experiment:** Decide whether to implement Input Envelopes first for clean signal, or accept the asterisk and run on current architecture.
2. **During PR-AE-6 spec:** Use the Isolation Boundary Rule and Envelope Contract as inputs to governance layer design.
3. **When parallel execution becomes a priority:** Input Envelopes are the prerequisite — build isolation first, fan-out second.
4. **When validator promotion is needed:** Classify each validator as hard gate vs soft flag using the structural/quality distinction.

---

*This document is a seed — architectural intent, not implementation commitment. Revisit when picking up the AI Trade Analyst project.*
