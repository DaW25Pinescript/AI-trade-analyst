# AI Trade Analyst — Analysis Engine Architecture Spec

**Document:** `ANALYSIS_ENGINE_SPEC_v1.0.md`
**Status:** Approved — Ready for Implementation
**Version:** v1.2 (final — all hardening complete, PR-AE-1 ready)
**Date:** 2026-03-18
**Repo:** `github.com/DaW25Pinescript/AI-trade-analyst`
**Supersedes:** `PERSONA_REFINEMENT_PLAN_v0.2.md` (archived — see Section 1.2)
**Production path:** `ai_analyst/` (LangGraph + FastAPI)

---

## Strategic Context

> "This is a structural pivot — not a persona upgrade."

The refinement plan correctly diagnosed three implementation problems (weak persona differentiation, governance language exceeding governance reality, split observability) but proposed fixing them inside an architecture that cannot support them. The correct response is to build the right foundation.

This spec defines that foundation: an evidence-first, deterministic Analysis Engine in which every trade indication is traceable from raw price data through structured lens evidence, typed persona interpretation, and deterministic governance — with every claim tied to an explicit, auditable field.

---

## 1. Purpose

### 1.1 What This Phase Answers

Can the AI Trade Analyst produce a trade indication that is fully traceable from raw price data through structured evidence, persona interpretation, and deterministic governance — with every claim tied to an explicit, auditable evidence field?

### 1.2 Archived Document — Key Insights Carried Forward

`PERSONA_REFINEMENT_PLAN_v0.2.md` is archived to `docs/archive/`. Insights carried forward:

| Insight | Location in this spec |
|---|---|
| Four-concern separation: identity / behavior / governance / observability | Section 3.4 |
| Named validator registry pattern (serialisable list[str], not list[Callable]) | Section 6.4 |
| Typed GovernanceSummary with veto_applied separate from consensus_level | Section 7.4 |
| Constraint enforcement levels: soft / moderate / hard | Section 6.4 |
| Gate discipline | Section 12.2 |
| Risk register | Section 14 |
| Open unknowns blocking design | Section 15 |

Archive header to add to old document:
```
> ARCHIVED 2026-03-18. Superseded by ANALYSIS_ENGINE_SPEC_v1.0.md.
> Retained for diagnostic insights. Do not use as an implementation guide.
```

### 1.3 Movement: FROM => TO

| Layer | FROM | TO |
|---|---|---|
| Evidence | Implicit in LLM reasoning prose | Deterministic lens outputs in typed schemas |
| Personas | Prompt-labeled LLM calls, no evidence contract | Structured interpreters of a shared immutable snapshot |
| Governance | Prompt-mediated narrative synthesis | Deterministic pre-LLM resolution with typed conflict detection |
| Observability | Split across run_record.json and audit JSONL | Single run object with full pipeline stack trace |
| Debuggability | "Why did the system do that?" — unanswerable | Decision Audit: dominant evidence, conflicts, veto reason, cap reason |

---

## 2. Scope

### 2.1 In Scope (v1)

- Lens Engine: Structure Lens, Trend Lens, Momentum Lens — deterministic, from OHLCV
- Lens Registry and per-run lens config storage
- Evidence Snapshot Builder with failure-aware metadata and derived alignment signals
- Persona Engine rewrite: Default Analyst + Risk Officer with evidence-citing contracts
- Persona validator registry with named, serialisable validator rules
- Governance Layer: deterministic resolution, typed conflict detection, veto logic, Decision Audit block
- Lens Control Room: configuration panel + readable output preview + raw JSON toggle
- Analysis Result View: Decision Audit panel + persona panels + evidence snapshot viewer
- Run object: replay-ready artifact storing full pipeline outputs with run_status
- Backend wiring into existing ai_analyst/ LangGraph path

### 2.2 Out of Scope (v1 hard constraints)

- Multi-timeframe lens execution
- Additional lenses beyond Structure, Trend, Momentum
- Additional personas beyond Default Analyst and Risk Officer
- User-authored lens code or freeform parameter editing
- Chart overlays or visual signal rendering on price charts
- Batch / watchlist execution mode
- Learning loops or evidence performance tracking
- Dynamic persona weight adjustment
- Persona studio or user-editable trait UI
- Any new top-level module outside ai_analyst/
- SQLite or new database layer
- LLM-led arbiter synthesis as the primary governance mechanism

---

## 3. Architecture Overview

### 3.1 Pipeline

```
Market Data (OHLCV via API / yfinance)
        |
        v
Data Normalisation Layer
  [clean OHLCV only — no calculations]
        |
        v
Lens Engine
  Structure Lens  -> LensOutput (status: success | failed)
  Trend Lens      -> LensOutput (status: success | failed)
  Momentum Lens   -> LensOutput (status: success | failed)
  [each lens: valid schema OR clean failure — never partial]
        |
        v
Evidence Snapshot Builder
  [namespace + validate + derive alignment signals + meta]
        |
        v
Evidence Snapshot  <--- immutable source of truth
  [context + lenses + derived + meta]
        |
        v
Persona Engine
  Default Analyst  -> AnalystOutput (8 fields, min 2 evidence)
  Risk Officer     -> AnalystOutput (8 fields, min 2 evidence)
  [validators run post-output against PersonaContract]
        |
        v
Governance Layer
  [aggregation -> alignment -> conflict detection -> veto -> ceiling -> decision -> audit]
        |
        v
GovernanceSummary + DecisionAudit
        |
        v
Run Object  <--- persisted, replay-ready
  [run_status: SUCCESS | DEGRADED | FAILED]
        |
        v
Analysis Result View (UI)
```

### 3.2 Data Flow Rules (non-negotiable — enforced in code)

1. Lenses read normalised price data only — never persona outputs or governance state
2. The Evidence Snapshot is immutable once built — no downstream component mutates it
3. Personas read the Evidence Snapshot only — never other persona outputs directly
4. Governance reads persona outputs + snapshot only — never modifies either
5. The Run Object is written once after governance completes — never incrementally patched
6. A lens must never partially return data — either a valid complete schema or a clean failure
7. Personas must never reference lenses absent from meta.active_lenses

### 3.3 Workspace Structure

```
Analysis Workspace
|-- Lens Control Room     <- evidence generation: configure, run, inspect
|-- Analysis Result View  <- decision output: personas, governance, audit
```

These are separate views. The Control Room is the entry point. The Result View is the output. Never combined.

### 3.4 Four-Concern Separation (carried from refinement plan)

| Concern | Definition | Lives in |
|---|---|---|
| Persona identity | What lens this analyst represents | PersonaContract (name, stance, domain) |
| Persona behavior | How that stance constrains output — enforced by validators | Named validator registry in persona_validators.py |
| Governance authority | How much weight or veto power this analyst has | GovernanceSummary + governance policy module |
| Observability | How behavior is logged, surfaced, and replayed | Run object + Analysis Result View + Reflect (later) |

---

## 4. Lens System

### 4.1 What a Lens Is

A lens is a deterministic, code-defined analysis module that computes structured evidence from normalised OHLCV price data. It does not interpret. It does not opine. It computes and emits.

### 4.2 Lens Contract (enforced for every lens)

Every lens must satisfy this contract. Two developers implementing the same lens must produce identical output schemas.

```python
class LensOutput(BaseModel):
    lens_id: str                    # e.g. "structure", "trend", "momentum"
    version: str                    # e.g. "v1.0"
    timeframe: str                  # e.g. "1H"
    status: Literal["success", "failed"]
    error: str | None               # null on success; error message on failure
    data: dict | None               # full output schema on success; null on failure
```

Lens contract rules:
- Return either complete schema with status "success" OR status "failed" with error and data=null
- Partial data is a contract violation — treated as failure
- All fields in data must always be present; use null for unavailable values, never absent keys
- Lens logic is fixed in v1 — only parameters are user-configurable
- Schema must be multi-timeframe-ready without breaking downstream consumers

### 4.3 Structure Lens

Purpose: Detect and describe market structure — key levels, swing context, breakout/rejection state.

Configuration (v1):
```yaml
lens: structure
timeframe: 1H
lookback_bars: 100
swing_sensitivity: medium   # low | medium | high
level_method: pivot         # pivot only in v1
breakout_rule: close        # close | wick (wick future)
```

Output Schema:
```json
{
  "timeframe": "1H",
  "levels": { "support": 2000.0, "resistance": 2100.0 },
  "distance": { "to_support": 0.8, "to_resistance": 1.5 },
  "swings": { "recent_high": 2095.0, "recent_low": 2010.0 },
  "trend": { "local_direction": "bullish", "structure_state": "HH_HL" },
  "breakout": { "status": "holding", "level_broken": "resistance" },
  "rejection": { "at_support": false, "at_resistance": true }
}
```

Field value contracts:
- trend.local_direction: bullish | bearish | ranging
- trend.structure_state: HH_HL | LH_LL | mixed
- breakout.status: none | breakout_up | breakout_down | holding | failed
- breakout.level_broken: support | resistance | null

Interpretation contract:
- Bullish: structure_state=HH_HL AND (breakout.status=holding OR rejection.at_support=true)
- Bearish: structure_state=LH_LL AND (breakout.status=breakout_down OR rejection.at_resistance=true)
- Neutral: structure_state=mixed OR no breakout OR equidistant from levels

### 4.4 Trend Lens

Purpose: Determine directional bias and trend quality using EMA alignment, price position, and slope.

Configuration (v1):
```yaml
lens: trend
timeframe: 1H
ema_fast: 20
ema_slow: 50
slope_lookback: 10
```

Output Schema:
```json
{
  "timeframe": "1H",
  "direction": {
    "ema_alignment": "bullish",
    "price_vs_ema": "above",
    "overall": "bullish"
  },
  "strength": { "slope": "positive", "trend_quality": "strong" },
  "state": { "phase": "continuation", "consistency": "aligned" }
}
```

Field value contracts:
- direction.ema_alignment: bullish | bearish | neutral
- direction.price_vs_ema: above | below | mixed
- direction.overall: bullish | bearish | ranging
- strength.slope: positive | negative | flat
- strength.trend_quality: strong | moderate | weak
- state.phase: continuation | pullback | transition
- state.consistency: aligned | conflicting

Important rule: Trend Lens provides directional context — not entry signals.

### 4.5 Momentum Lens

Purpose: Detect price impulse strength, acceleration/decay, and exhaustion/chop risk.

Configuration (v1):
```yaml
lens: momentum
timeframe: 1H
roc_lookback: 10
momentum_smoothing: 5
signal_mode: roc   # roc only in v1
```

Output Schema:
```json
{
  "timeframe": "1H",
  "direction": { "state": "bullish", "roc_sign": "positive" },
  "strength": { "impulse": "strong", "acceleration": "rising" },
  "state": { "phase": "expanding", "trend_alignment": "aligned" },
  "risk": { "exhaustion": false, "chop_warning": false }
}
```

Field value contracts:
- direction.state: bullish | bearish | neutral
- direction.roc_sign: positive | negative | flat
- strength.impulse: strong | moderate | weak
- strength.acceleration: rising | falling | flat
- state.phase: expanding | fading | reversing | flat
- state.trend_alignment: aligned | conflicting | unknown

Role: confluence amplifier and caution signal — not a primary entry trigger.

### 4.6 Lens Registry

```json
{
  "lens_registry": [
    {"id": "structure", "version": "v1.0", "enabled": true},
    {"id": "trend",     "version": "v1.0", "enabled": true},
    {"id": "momentum",  "version": "v1.0", "enabled": true}
  ]
}
```

---

## 5. Evidence Snapshot

### 5.1 Purpose

Combine all active lens outputs into a single, immutable, structured object — the shared truth layer. Every downstream component reads only this object.

### 5.2 Full Schema

```json
{
  "context": {
    "instrument": "XAUUSD",
    "timeframe": "1H",
    "timestamp": "2026-03-18T10:30:00Z"
  },
  "lenses": {
    "structure": { "...full structure lens output..." },
    "trend": { "...full trend lens output..." },
    "momentum": { "...full momentum lens output..." }
  },
  "derived": {
    "alignment_score": 0.85,
    "conflict_score": 0.10,
    "signal_state": "SIGNAL",
    "coverage": 0.66,
    "persona_agreement_score": null
  },
  "note": "coverage and persona_agreement_score are populated in the run object after personas complete — not in the snapshot itself (snapshot is built before personas run)",
  "meta": {
    "active_lenses": ["structure", "trend", "momentum"],
    "inactive_lenses": [],
    "failed_lenses": [],
    "lens_errors": {},
    "evidence_version": "v1.0",
    "snapshot_id": "sha256-hash-of-content"
  }
}
```

### 5.3 Derived Signals

Computed deterministically by the Snapshot Builder — never by personas.

| Field | Range | Meaning |
|---|---|---|
| alignment_score | 0.0-1.0 | Degree of directional agreement across active lenses |
| conflict_score | 0.0-1.0 | Degree of contradictory signals across active lenses |
| coverage | 0.0-1.0 | Fraction of available evidence fields actually cited by personas |
| persona_agreement_score | 0.0-1.0 | Percentage of personas sharing the same bias |

**Exact calculation formulas (v1 — deterministic):**

alignment_score:
```python
# Map each active lens to a directional value
DIRECTION_MAP = {
    "bullish": +1, "positive": +1, "above": +1, "expanding": +1,
    "bearish": -1, "negative": -1, "below": -1, "reversing": -1,
    "neutral": 0, "flat": 0, "mixed": 0, "unknown": 0
}

# Extract primary directional field per lens:
#   structure -> lenses.structure.trend.local_direction
#   trend     -> lenses.trend.direction.overall
#   momentum  -> lenses.momentum.direction.state

direction_values = [DIRECTION_MAP.get(lens_primary_direction, 0)
                    for lens in active_lenses]

# Edge case: all lenses neutral = no signal, not conflict
if all(v == 0 for v in direction_values):
    alignment_score = 0.0
    conflict_score  = 0.0
    signal_state    = "NO_SIGNAL"   # stored in derived — personas must acknowledge
else:
    alignment_score = abs(mean(direction_values))  # 0.0 = full conflict, 1.0 = full agreement
    conflict_score  = 1.0 - alignment_score
    signal_state    = "SIGNAL"
```

coverage (computed after personas run — stored in run object, not snapshot):
```python
all_cited_paths = set()
for output in persona_outputs:
    all_cited_paths.update(output.evidence_used)

available_key_fields = _get_key_fields_from_snapshot(evidence_snapshot)
coverage = len(all_cited_paths.intersection(available_key_fields)) / len(available_key_fields)
```

persona_agreement_score (computed by Governance):
```python
dominant_bias = bias_counts.most_common(1)[0][0]
persona_agreement_score = bias_counts[dominant_bias] / len(persona_outputs)
```

### 5.4 Failure Handling

A failed lens is recorded in meta.failed_lenses + meta.lens_errors. The snapshot remains valid for remaining lenses. run_status is set to DEGRADED.

```json
"meta": {
  "active_lenses": ["structure", "trend"],
  "failed_lenses": ["momentum"],
  "lens_errors": { "momentum": "insufficient bars for ROC calculation" }
}
```

Personas must acknowledge missing evidence. They must not fabricate fields from failed lenses.

### 5.5 Evidence Reference Standard

Personas and governance cite evidence by full dot-path from lenses.*:

```
lenses.structure.trend.structure_state
lenses.structure.breakout.status
lenses.structure.distance.to_resistance
lenses.trend.direction.overall
lenses.trend.strength.trend_quality
lenses.momentum.state.phase
lenses.momentum.risk.exhaustion
```

String references like "structure looks bullish" are contract violations.

### 5.6 Future-Proofing

V1: "lenses": { "structure": { ... } }
V2 (no breaking change): "lenses": { "structure": { "1H": { ... }, "4H": { ... } } }

### 5.7 Snapshot Builder Responsibilities

Standalone component at ai_analyst/core/snapshot_builder.py:
1. Collect all LensOutput objects from the Lens Engine
2. Validate each against its lens contract schema
3. Populate meta (active/inactive/failed lenses, errors, version, snapshot_id)
4. Compute derived.alignment_score and derived.conflict_score
5. Assemble and return the immutable snapshot object

---

## 6. Persona Engine

### 6.1 Active Personas (v1)

| Persona | Primary stance | Governance authority |
|---|---|---|
| default_analyst | Balanced — reads all evidence equally | Standard vote |
| risk_officer | Risk-averse — prioritises invalidation and proximity risk | Deterministic veto authority |

### 6.2 Persona Role Definition

Personas are evidence interpreters, prioritizers, and explainers — not market analysts. Their job:
1. Read the evidence snapshot
2. Select what matters according to their contract and stance
3. Form a directional judgment
4. Explain that judgment by citing specific evidence dot-paths
5. Surface uncertainty, counterpoints, and invalidation conditions explicitly

What personas must NOT do:
- Invent data not present in the snapshot
- Reference lenses absent from meta.active_lenses
- Use vague prose not tied to evidence fields ("structure looks strong" = violation)
- Force a directional output when evidence is insufficient
- Contradict their evidence_used in their reasoning text

### 6.3 Confidence Definition (formally defined)

Confidence = the degree to which active evidence is internally aligned, cross-lens consistent, and free of contradictions.

Confidence bands — personas must stay within these:

| Band | Range | Meaning |
|---|---|---|
| Weak | 0.0-0.35 | Evidence mixed, conflicted, or insufficient. Lean toward NEUTRAL / NO_TRADE. |
| Moderate | 0.36-0.65 | Some alignment but meaningful conflicts or gaps present. |
| Strong | 0.66-1.00 | Evidence clearly aligned across multiple lenses with minimal contradiction. |

Calibration rules:
- Confidence >= 0.66 requires >= 2 lens families agreeing directionally
- Confidence >= 0.80 requires counterpoints citing specific limited-risk evidence
- When meta.failed_lenses is non-empty: maximum persona confidence capped at 0.65

### 6.4 Persona Contract Schema

```python
class PersonaContract(BaseModel):
    persona_id: PersonaType
    version: str
    display_name: str
    primary_stance: Literal["balanced", "risk_averse", "adversarial", "method_pure", "skeptical_prob"]
    temperature_override: float | None
    model_profile_override: str | None
    must_enforce: list[str]
    soft_constraints: list[str]
    constraints: list[dict]     # {"rule": str, "level": "soft|moderate|hard"}
    validator_rules: list[str]  # named references into VALIDATOR_REGISTRY — NOT inline Callables
```

Constraint enforcement levels:
| Level | Behavior |
|---|---|
| soft | Log violation only |
| moderate | Log + downgrade confidence by 0.10 |
| hard | Invalidate output — treated as failed analyst |

Validator registry (ai_analyst/core/persona_validators.py):
```python
VALIDATOR_REGISTRY: dict[str, Callable[[AnalystOutput], bool | str]] = {
    "risk_officer.no_aggressive_buy_without_confidence": lambda o: (
        True if o.recommended_action != "STRONG_BUY" or o.confidence >= 0.75
        else "risk_officer: STRONG_BUY requires confidence >= 0.75"
    ),
    "default_analyst.requires_two_evidence_fields": lambda o: (
        True if len(o.evidence_used) >= 2
        else "default_analyst: minimum 2 evidence fields required"
    ),
    "all_personas.no_evidence_contradiction": lambda o: (
        True if _reasoning_consistent_with_evidence(o)
        else "reasoning contradicts declared evidence_used fields"
    ),
}
```

All v1 validators start at soft level. Promoting requires contract version bump — not a code change.

### 6.5 Persona Output Schema (v1)

```json
{
  "persona_id": "default_analyst",
  "bias": "BULLISH",
  "recommended_action": "BUY",
  "confidence": 0.72,
  "reasoning": "Bullish because structure shows HH/HL continuation (lenses.structure.trend.structure_state = HH_HL) with breakout holding (lenses.structure.breakout.status = holding). Trend EMA bullish (lenses.trend.direction.overall = bullish). Momentum expanding (lenses.momentum.state.phase = expanding).",
  "evidence_used": [
    "lenses.structure.trend.structure_state",
    "lenses.structure.breakout.status",
    "lenses.trend.direction.overall",
    "lenses.momentum.state.phase"
  ],
  "counterpoints": [
    "Price within 1.5% of resistance — reversal risk elevated (lenses.structure.distance.to_resistance = 1.5)",
    "Momentum acceleration slowing — continuation not guaranteed"
  ],
  "what_would_change_my_mind": [
    "Close below structure support at lenses.structure.levels.support",
    "Momentum phase flips to fading with bearish structure_state"
  ]
}
```

Field rules (enforced by validators):
- `bias`: Must be `BULLISH | BEARISH | NEUTRAL`. `NEUTRAL` is allowed ONLY IF `derived.alignment_score < 0.2` OR `run_status = DEGRADED`. Under strong signal conditions, outputting `NEUTRAL` is a validator violation — persona must take a directional stance or explicitly abstain via `NO_TRADE`.
- evidence_used: minimum 2 entries; must be valid snapshot dot-paths under lenses.*
- reasoning: must reference at least 2 evidence field values explicitly — no vague prose
- counterpoints: minimum 1 entry unless confidence >= 0.80 and evidence overwhelmingly one-sided
- what_would_change_my_mind: minimum 1 entry — makes reasoning falsifiable

### 6.6 Hard Persona Discipline Rules (validator-enforced)

1. Minimum evidence citation: every directional conclusion cites >= 2 evidence dot-paths
2. No external data: may not reference anything outside the snapshot
3. No absent lens citation: may not cite fields from failed or inactive lenses
4. No reasoning contradiction: reasoning must be consistent with evidence_used
5. Counterpoint enforcement: >= 1 counterpoint required unless confidence > 0.80
6. Evidence path validation: every path in evidence_used must be validated

**Evidence path validation rule (validator: all_personas.evidence_paths_exist):**
```python
def validate_evidence_paths(output: AnalystOutput, snapshot: EvidenceSnapshot) -> bool | str:
    for path in output.evidence_used:
        # path format: "lenses.structure.trend.structure_state"
        parts = path.split(".")
        if parts[0] != "lenses":
            return f"Invalid path prefix '{parts[0]}' — must start with 'lenses'"
        lens_name = parts[1]
        if lens_name not in snapshot.meta.active_lenses:
            return f"Path '{path}' references lens '{lens_name}' not in active_lenses"
        # Traverse the snapshot data structure
        node = snapshot.lenses.get(lens_name)
        for part in parts[2:]:
            if not isinstance(node, dict) or part not in node:
                return f"Path '{path}' does not resolve in snapshot"
            node = node[part]
        # node is now the resolved value — null is explicitly allowed
    return True
```

### 6.7 Prompt Template Architecture

Fixed sections (shared across all personas):
- System role: you interpret structured evidence; you do not invent facts
- Hard rules: cite evidence dot-paths; minimum 2 fields; no vague prose; abstain if unclear
- Input definition: context + evidence snapshot + persona contract
- Reasoning process: identify evidence -> interpret -> evaluate strength -> consider risk -> conclude
- Output schema: strict JSON with all 8 required fields

Persona-specific blocks (only this changes per persona):

Default Analyst:
```
PERSONA ROLE: Balanced Analyst
STANCE: Consider all evidence equally. Do not overcommit unless clearly aligned.
Prefer clarity over aggression. Summarise strongest directional case and main risk.
```

Risk Officer:
```
PERSONA ROLE: Risk Officer
STANCE: Prioritise downside risk, proximity to adverse levels, unstable structure.
Be skeptical of strong directional bias near key levels.
Prefer NO_TRADE if risk is elevated, evidence is split, or momentum is fading.
Apply veto-ready output if structural invalidation present and confidence >= 0.60.
```

Hard prompt rule for all personas:
Every directional claim must cite at least 2-3 explicit evidence dot-paths.
"lenses.structure.trend.structure_state" is correct.
"price action looks strong" is a contract violation.

### 6.8 Graceful Degradation

If a lens fails, personas must:
- Cite only fields from meta.active_lenses
- Cap confidence at 0.65
- Add to counterpoints: "[lens_name] lens failed — [evidence_family] context unavailable"

---

## 7. Governance Layer

### 7.1 Purpose

Receive all persona outputs and the evidence snapshot. Resolve them into a single, deterministic decision with a fully auditable rationale.

Governance is a resolution engine — not another opinion. All decision logic is deterministic Python.

### 7.2 Inputs

1. evidence_snapshot — ground truth; used for conflict validation and derived signals
2. persona_outputs — list[AnalystOutput] from all active personas

### 7.3 Governance Stages (deterministic, sequential)

Stage 1 — Vote Aggregation:
```python
bias_counts    = Counter(o.bias for o in persona_outputs)
action_counts  = Counter(o.recommended_action for o in persona_outputs)
mean_confidence = mean(o.confidence for o in persona_outputs)
min_confidence  = min(o.confidence for o in persona_outputs)
```

Stage 2 — Alignment Classification:
- unanimous: all personas same bias AND same action
- strong_majority: >= 75% same bias direction
- split: no bias holds >= 75%
- insufficient: fewer than MINIMUM_VALID_ANALYSTS valid outputs

**MINIMUM_VALID_ANALYSTS = 1 (v1)**
```python
MINIMUM_VALID_ANALYSTS = 1  # configurable in future phases

valid_outputs = [o for o in persona_outputs if o is not None and _passes_schema(o)]
if len(valid_outputs) == 0:
    run_status = "FAILED"
    # Do not proceed to governance — store partial run record and exit
elif len(valid_outputs) < MINIMUM_VALID_ANALYSTS:
    consensus_type = "insufficient"
    # Governance still runs but produces NO_TRADE
```

Stage 3 — Typed Conflict Detection:
```python
class ConflictRecord(BaseModel):
    type: Literal["direction_conflict", "risk_conflict", "evidence_conflict"]
    summary: str
```
- direction_conflict: bias_counts contains both BULLISH and BEARISH
- risk_conflict: at least one BUY/SELL while another has NO_TRADE
- evidence_conflict: exact rule below

**evidence_conflict detection (v1):**
```python
# Collect evidence paths per persona with their associated bias
path_to_biases: dict[str, set[str]] = defaultdict(set)
for output in persona_outputs:
    for path in output.evidence_used:
        path_to_biases[path].add(output.bias)

# evidence_conflict fires when the same path is cited by personas with opposing bias
OPPOSING_PAIRS = {("BULLISH", "BEARISH"), ("BEARISH", "BULLISH")}

for path, biases in path_to_biases.items():
    for pair in OPPOSING_PAIRS:
        if set(pair).issubset(biases):
            conflicts.append(ConflictRecord(
                type="evidence_conflict",
                summary=f"Path '{path}' cited by both BULLISH and BEARISH personas"
            ))
            break
```

Stage 4 — Deterministic Veto Logic:
```python
VETO_CONFIDENCE_THRESHOLD = 0.60

veto_applied = False
if (
    risk_officer_output.recommended_action == "NO_TRADE"
    and risk_officer_output.confidence >= VETO_CONFIDENCE_THRESHOLD
):
    veto_applied = True
    veto_source = "risk_officer"
    veto_reason = f"NO_TRADE at confidence {risk_officer_output.confidence:.2f} >= threshold {VETO_CONFIDENCE_THRESHOLD}"
    final_decision = "NO_TRADE"
```

Veto is a Python gate — not a prompt instruction.

Stage 5 — Confidence Ceiling:
```python
SPLIT_CONFIDENCE_CAP   = 0.60
DEGRADED_RUN_CAP       = 0.55

# Confidence source of truth — applied sequentially:
raw_confidence = mean_confidence               # Step 1: start from mean of persona confidences
final_confidence = raw_confidence              # Step 2: apply veto rules (set in Stage 4 if veto fired)
confidence_cap_reason = None

if consensus_type in ("split", "insufficient"):  # Step 3: apply split cap
    final_confidence = min(final_confidence, SPLIT_CONFIDENCE_CAP)
    confidence_cap_reason = f"Split consensus — capped at {SPLIT_CONFIDENCE_CAP}"

if run_status == "DEGRADED":                     # Step 4: apply degraded cap
    final_confidence = min(final_confidence, DEGRADED_RUN_CAP)
    confidence_cap_reason = (confidence_cap_reason or "") + " + DEGRADED run"
# final_confidence is the canonical confidence value used in GovernanceSummary
```

Stage 6 — Decision Resolution:
```python
if veto_applied:
    final_decision = "NO_TRADE"
elif consensus_type == "insufficient":
    final_decision = "NO_TRADE"
elif consensus_type == "split":
    # Tie-break: low agreement score = NO_TRADE with confidence penalty
    if persona_agreement_score < 0.6:
        final_decision   = "NO_TRADE"
        final_confidence = min_confidence * 0.5  # hard penalty — communicates low-quality resolution
        confidence_cap_reason = (confidence_cap_reason or "") + " + split tie-break penalty (agreement < 0.6)"
    # else: agreement >= 0.6 despite split classification — fall through to majority resolution
elif action_counts.most_common(1)[0][0] == "BUY" and final_confidence >= 0.40:
    final_decision = "BUY"
elif action_counts.most_common(1)[0][0] == "SELL" and final_confidence >= 0.40:
    final_decision = "SELL"
else:
    final_decision = "NO_TRADE"
```

**Tie-break rationale:** `persona_agreement_score < 0.6` means no meaningful majority exists. Forcing direction from disagreement is worse than abstaining. The `min_confidence * 0.5` penalty ensures the GovernanceSummary clearly communicates the low-quality resolution to Reflect and the UI.

Stage 7 — Decision Audit Block:
```python
class DecisionAudit(BaseModel):
    why_taken: str          # explicit reason the chosen decision was made
    why_not_opposite: str   # explicit reason the opposing decision was rejected
    risk_notes: str         # specific risk conditions present at decision time
```

### 7.4 GovernanceSummary Output Schema

```json
{
  "final_decision": "NO_TRADE",
  "confidence": 0.55,
  "run_status": "DEGRADED",
  "consensus": {
    "type": "split",
    "bias_counts": { "BULLISH": 1, "NEUTRAL": 1 },
    "action_counts": { "BUY": 1, "NO_TRADE": 1 },
    "mean_confidence": 0.685,
    "min_confidence": 0.65
  },
  "conflicts": [
    {
      "type": "risk_conflict",
      "summary": "default_analyst BUY vs risk_officer NO_TRADE — proximity to resistance + momentum exhaustion"
    }
  ],
  "veto": {
    "applied": true,
    "source": "risk_officer",
    "reason": "NO_TRADE at confidence 0.65 >= threshold 0.60"
  },
  "dominant_evidence": [
    "lenses.structure.distance.to_resistance",
    "lenses.momentum.risk.exhaustion"
  ],
  "ignored_evidence": [
    "lenses.structure.breakout.status"
  ],
  "confidence_cap_reason": "Split consensus capped at 0.60 + DEGRADED run (momentum lens failed)",
  "decision_audit": {
    "why_taken": "Veto applied by risk_officer (confidence 0.65 >= 0.60). Risk conflict: default_analyst BUY vs risk_officer NO_TRADE.",
    "why_not_opposite": "BUY rejected — risk_officer veto overrides majority directional vote per deterministic governance rules.",
    "risk_notes": "Price 1.5% from resistance. Momentum exhaustion active. Split consensus. Momentum lens failed (DEGRADED run)."
  }
}
```

Key design decisions:
- veto.applied is separate from consensus.type — a unanimous vote can still have a veto applied
- conflicts is a typed list — not a prose blob — making it machine-inspectable
- ignored_evidence surfaces what was available but not weighted — critical for Reflect later
- confidence_cap_reason always present (null if no cap applied)
- decision_audit makes decision rationale machine-readable for Reflect comparison

---

## 8. Run Object

### 8.1 Run Status

**run_status is determined at the Snapshot Builder stage and propagated forward — not set by governance.**

```python
# Determined immediately after Lens Engine completes:
successful_lenses = [l for l in lens_outputs if l.status == "success"]
failed_lenses     = [l for l in lens_outputs if l.status == "failed"]

if len(successful_lenses) == 0:
    run_status = "FAILED"      # All lenses failed — do not proceed to personas
elif len(failed_lenses) > 0:
    run_status = "DEGRADED"    # At least one lens failed, at least one succeeded
else:
    run_status = "SUCCESS"     # All lenses succeeded

# Governance may further set run_status = "FAILED" if:
# - valid_persona_count == 0 (both personas failed schema validation)
# run_status is never upgraded (DEGRADED cannot become SUCCESS after governance)
```

| Status | Set by | Condition |
|---|---|---|
| SUCCESS | Snapshot Builder | All lenses ran successfully |
| DEGRADED | Snapshot Builder | >= 1 lens failed AND >= 1 succeeded |
| FAILED | Snapshot Builder or Governance | All lenses failed, OR 0 valid persona outputs |

DEGRADED runs are valid and inspectable. FAILED runs are stored with a partial record and error field.

### 8.2 Run Object Schema

```json
{
  "run_id": "uuid-string",
  "instrument": "XAUUSD",
  "timeframe": "1H",
  "timestamp": "2026-03-18T10:30:00Z",
  "run_status": "SUCCESS",
  "lens_config": {
    "setup_name": "Core v1",
    "lens_registry_snapshot": [
      {"id": "structure", "version": "v1.0", "enabled": true},
      {"id": "trend",     "version": "v1.0", "enabled": true},
      {"id": "momentum",  "version": "v1.0", "enabled": true}
    ],
    "lens_params": {
      "structure": { "lookback_bars": 100, "swing_sensitivity": "medium" },
      "trend":     { "ema_fast": 20, "ema_slow": 50 },
      "momentum":  { "roc_lookback": 10 }
    }
  },
  "evidence_snapshot": { "...full snapshot..." },
  "persona_outputs": [ { "...AnalystOutput..." }, { "...AnalystOutput..." } ],
  "governance_output": { "...GovernanceSummary..." },
  "final_decision": "NO_TRADE",
  "final_confidence": 0.55,
  "meta": {
    "persona_package_version": "v1.0",
    "evidence_version": "v1.0",
    "prompt_manifest": {
      "default_analyst": { "file": "personas/default_analyst.txt", "sha256": "abc123..." },
      "risk_officer":    { "file": "personas/risk_officer.txt",    "sha256": "def456..." }
    },
    "run_duration_ms": 3420
  },
  "decision_id": "sha256(governance_output_canonical + snapshot_id)"
}

Note: decision_id = hash(canonical JSON of governance_output + snapshot_id).
Enables deduplication, caching, and tracking of identical decisions across runs.
```

### 8.3 Replay Design

Replay = load run object -> re-run Governance only (frozen persona_outputs + evidence_snapshot).

Enables: what-if governance policy changes, Reflect comparison, arbiter narrative update without re-running analysts.

Replay endpoint: POST /reflect/replay — accepts run_id, returns new GovernanceSummary.

---

## 9. Error Handling in the Run Flow

| Scenario | System response | run_status |
|---|---|---|
| One lens fails at runtime | Record in meta.failed_lenses + lens_errors. Build snapshot with remaining lenses. Continue. | DEGRADED |
| All lenses fail | Mark FAILED. Store partial record. Do not proceed to persona engine. | FAILED |
| Persona output fails schema validation | Treat as failed analyst. Reduce quorum count. | DEGRADED if quorum met; FAILED if not |
| Both personas fail | Mark FAILED. Store partial record. No governance call. | FAILED |
| Governance cannot resolve | Force NO_TRADE. Record reason. | SUCCESS (NO_TRADE is valid) |
| Persona cites failed lens | Validator flags soft violation. Confidence downgraded. Counterpoint required. | No change to run_status |

DEGRADED run governance rules:
- Maximum confidence = DEGRADED_RUN_CAP (0.55)
- decision_audit.risk_notes must reference the degraded state
- Analysis Result View displays DEGRADED badge in run header

---

## 10. Lens Control Room (UI)

### 10.1 Purpose

Operational entry point. Configure lenses, inspect outputs, trigger runs. Evidence generation only — not decision review.

### 10.2 V1 Included

- Enable/disable lens slots
- Edit lens parameters (controlled list — not freeform code)
- Run single analysis
- Readable per-lens output preview (field list)
- Raw JSON toggle per lens
- Merged evidence snapshot preview with derived scores
- DEGRADED state indicator per lens

### 10.3 V1 Excluded

Freeform code editing, drag-and-drop builders, multi-run comparison, version history UI, batch execution.

### 10.4 Lens Config Data Model

| Object | Purpose |
|---|---|
| LensDefinition | What the lens is (structure / trend / momentum) |
| LensInstanceConfig | How this run uses it (timeframe, lookback, sensitivity) |
| LensSetup | A named group of lens configs ("Core v1", "Trend-heavy") |

---

## 11. Analysis Result View (UI)

### 11.1 Purpose

Present the full pipeline output — lens evidence, persona interpretations, governance decision — in a structured, inspectable layout. Separate route from Lens Control Room.

### 11.2 Sections (top to bottom)

1. Run Summary Header: instrument, timeframe, run_id, run_status (with DEGRADED badge), decision, confidence, consensus
2. Decision Audit Panel: final decision + confidence, veto applied/reason, confidence cap/reason, conflicts (typed), why_taken, why_not_opposite, risk_notes, dominant_evidence, ignored_evidence
3. Persona Output Panels: each persona shows all 8 fields — bias, action, confidence, reasoning, evidence_used, counterpoints, what_would_change_my_mind
4. Evidence Snapshot Viewer: per-lens readable field list, derived scores, failed lens error display, raw JSON toggle

### 11.3 Design Principles

- No hidden logic — every value derives from stored run object
- DEGRADED badge displayed prominently whenever run_status = DEGRADED
- Deterministic reload — reloading a run produces identical display every time
- Inspectability over aesthetics in v1

---

## 12. Phase Breakdown & Acceptance Criteria

### 12.1 Sequence

```
P1 Lens Engine + Snapshot -> [Gate 1] -> P2 Persona Rebuild -> [Gate 2]
-> P3 Governance Layer -> [Gate 3] -> P4 UI -> [Gate 4]
-> P5 Run Object + Observability -> [Gate 5]
```

### 12.2 Hard Gates

| Gate | Closes after | Must have before proceeding |
|---|---|---|
| Gate 1 | P1 complete | All 3 lenses produce valid schema or clean failures; snapshot meta correct; derived signals computed; all existing tests green |
| Gate 2 | P2 complete | Both personas produce valid 8-field AnalystOutput; evidence_used min 2; counterpoints min 1; validators registered and tested; no hallucination on degraded snapshot |
| Gate 3 | P3 complete | Governance produces GovernanceSummary deterministically; veto path deterministic Python; typed conflicts; decision_audit populated; no LLM in governance test loop |
| Gate 4 | P4 complete | Control Room shows lens output preview + DEGRADED state; Result View shows Decision Audit; all persona fields visible |
| Gate 5 | P5 complete | Run object persisted; replay endpoint functional; prompt_manifest stored; persona_package_version on all runs |

### 12.3 Phase P1 — Lens Engine + Evidence Snapshot

Key new files:
- ai_analyst/lenses/base.py — LensOutput contract + LensBase interface
- ai_analyst/lenses/structure.py — Structure Lens
- ai_analyst/lenses/trend.py — Trend Lens
- ai_analyst/lenses/momentum.py — Momentum Lens
- ai_analyst/lenses/registry.py — Lens registry
- ai_analyst/core/snapshot_builder.py — Snapshot Builder + derived signals

Acceptance criteria:
- AC-1: Structure Lens produces valid schema from OHLCV — all fields present including nulls
- AC-2: Trend Lens produces valid schema — all fields present
- AC-3: Momentum Lens produces valid schema — all fields present
- AC-4: Failed lens produces LensOutput(status="failed", error="...", data=null) — never partial data
- AC-5: Snapshot Builder namespaces lens outputs under lenses.*
- AC-6: Failed lens in meta.failed_lenses + error in meta.lens_errors
- AC-7: Inactive lens in meta.inactive_lenses — absent from lenses.*
- AC-8: derived.alignment_score and derived.conflict_score computed, in 0.0-1.0 range
- AC-9: snapshot_id is unique per run (hash of content)
- AC-10: All existing tests remain green after P1

### 12.4 Phase P2 — Persona Engine Rebuild

Key new/modified files:
- ai_analyst/models/persona_contract.py — PersonaContract schema (new)
- ai_analyst/models/analyst_output.py — add counterpoints, what_would_change_my_mind (modify)
- ai_analyst/core/persona_validators.py — validator registry (new)
- ai_analyst/graph/analyst_nodes.py — rewire to consume snapshot (modify)
- ai_analyst/prompt_library/v2.0/personas/*.txt — evidence-driven prompt templates (new)

Acceptance criteria:
- AC-11: AnalystOutput includes all 8 fields
- AC-12: evidence_used minimum 2 entries — validated by test
- AC-13: counterpoints minimum 1 entry — validated by test
- AC-14: what_would_change_my_mind minimum 1 entry — validated by test
- AC-15: Confidence within defined bands; capped at 0.65 on degraded snapshot
- AC-16: PersonaContract round-trips through JSON without data loss
- AC-17: Soft validator logs violation without blocking output
- AC-18: Moderate validator downgrades confidence by 0.10
- AC-19: Persona with inactive lens does not hallucinate lens evidence — test with structure-only snapshot
- AC-20: All existing + P1 tests green

### 12.5 Phase P3 — Governance Layer

Key new/modified files:
- ai_analyst/models/governance_summary.py — GovernanceSummary + DecisionAudit models (new)
- ai_analyst/core/governance.py — governance policy module — all 7 stages (new)
- ai_analyst/graph/governance_node.py — pre-arbiter governance node (new)
- ai_analyst/graph/pipeline.py — wire governance node into graph (modify)

Acceptance criteria:
- AC-21: GovernanceSummary produced with all fields including decision_audit and confidence_cap_reason
- AC-22: Veto fires deterministically when risk_officer.confidence >= 0.60 — no LLM in test
- AC-23: Veto does NOT fire when risk_officer.confidence < 0.60 — negative test
- AC-24: direction_conflict typed correctly — opposed bias test
- AC-25: risk_conflict typed correctly — directional vs NO_TRADE test
- AC-26: evidence_conflict typed correctly — same path, opposing conclusions test
- AC-27: Confidence ceiling applies on split — does NOT apply on unanimous (negative test)
- AC-28: DEGRADED run applies additional confidence ceiling
- AC-29: dominant_evidence and ignored_evidence populated per exact selection rules below

**dominant_evidence selection rule:**
```python
# 1. Count frequency of each evidence_used path across all persona outputs
from collections import Counter
path_counts = Counter()
for output in persona_outputs:
    path_counts.update(output.evidence_used)

# 2. Sort descending by frequency, take top 3 (N=3 in v1)
dominant_evidence = [path for path, _ in path_counts.most_common(3)]
```

**ignored_evidence selection rule:**
```python
# All fields present in snapshot.lenses.* but not cited by any persona
# Limit to top 5 for display
all_snapshot_paths = _extract_all_leaf_paths(evidence_snapshot.lenses)
cited_paths = set(path_counts.keys())
ignored_evidence = list(all_snapshot_paths - cited_paths)[:5]
```
- AC-30: decision_audit.why_taken, why_not_opposite, risk_notes all non-empty
- AC-31: All existing + P1 + P2 tests green

### 12.6 Phase P4 — UI

Acceptance criteria:
- AC-32: Lens Control Room renders 3 active lens slots with expand/collapse
- AC-33: Lens output preview shows readable field list post-run
- AC-34: Raw JSON toggle works per lens
- AC-35: Evidence Snapshot preview shows merged namespaced fields + derived scores
- AC-36: DEGRADED state displays badge in run header and per-lens panel
- AC-37: Analysis Result View renders Decision Audit with veto, conflicts, dominant/ignored evidence, audit block
- AC-38: Each persona panel shows all 8 output fields
- AC-39: Analysis Result View is a separate route from Lens Control Room

### 12.7 Phase P5 — Run Object + Observability

Acceptance criteria:
- AC-40: Run object persisted after every completed run with all schema fields
- AC-41: run_status correctly set: SUCCESS / DEGRADED / FAILED
- AC-42: Run object reloadable — produces identical Analysis Result View
- AC-43: Replay endpoint accepts frozen persona_outputs and re-runs Governance only
- AC-44: persona_package_version present on all runs
- AC-45: prompt_manifest SHA-256 hashes per active persona prompt file stored per run

---

## 13. PR Sequence

| PR | Scope | Phase | Gate |
|---|---|---|---|
| PR-AE-1 | LensBase interface + Structure Lens + unit tests | P1 | — |
| PR-AE-2 | Trend Lens + Momentum Lens + unit tests | P1 | — |
| PR-AE-3 | Lens registry + Evidence Snapshot Builder + failure meta + derived signals + tests | P1 | Gate 1 |
| PR-AE-4 | PersonaContract schema + validator registry + AnalystOutput update (8 fields) | P2 | — |
| PR-AE-5 | Persona prompt rewrite (Default + Risk Officer) + evidence citation tests + confidence tests | P2 | Gate 2 |
| PR-AE-6 | GovernanceSummary + DecisionAudit models + governance policy module (all 7 stages) | P3 | — |
| PR-AE-7 | Governance node wired into pipeline + veto/conflict/ceiling/audit tests + run_status | P3 | Gate 3 |
| PR-AE-8 | Lens Control Room UI (slots + config panels + output preview + DEGRADED state) | P4 | — |
| PR-AE-9 | Analysis Result View (Decision Audit panel + persona panels + evidence viewer) | P4 | Gate 4 |
| PR-AE-10 | Run object persistence + replay endpoint + version tagging + prompt_manifest | P5 | Gate 5 |

Recommended start sequence:
PR-AE-1 -> PR-AE-2 -> PR-AE-3 -> [Gate 1] -> PR-AE-4 -> PR-AE-5 -> [Gate 2]
-> PR-AE-6 -> PR-AE-7 -> [Gate 3] -> PR-AE-8 -> PR-AE-9 -> [Gate 4]
-> PR-AE-10 -> [Gate 5]

---

## 14. Risk Register

| Risk | Why it matters | Severity | Mitigation |
|---|---|---|---|
| Lens collapse — deterministic lenses produce near-identical outputs on strongly trending markets | Undermines value of multiple lenses | Medium | Governance surfaces unanimous consensus explicitly. derived.alignment_score = 1.0 visible in Reflect. |
| Persona prompt overfit — citation becomes formatting exercise, not genuine reasoning | Personas format correctly without interpreting meaningfully | High | all_personas.no_evidence_contradiction validator. P2 divergence benchmark before trait changes. |
| Veto calibration — threshold 0.60 too low (excessive NO_TRADE) or too high (veto never fires) | Degrades utility | Medium | Make threshold configurable. Run benchmark before locking. |
| Governance complexity creep as more personas are added | Undermines determinism | Medium | Stages strictly sequential. Each stage tested independently without LLM. |
| Evidence snapshot staleness on replay | Replay produces different results than original | High | PR-AE-10 stores lens_config snapshot + hashes in run object. Replay validates against stored config. |
| Brittle validators blocking legitimate outputs | System becomes unusable | Medium | All v1 validators at soft level. Promote only with empirical evidence. |
| Legacy arbiter interference — existing arbiter_node.py conflicts with new governance node | Two governance paths in same pipeline | High | Pre-P3 diagnostic must confirm replacement strategy. Do not run both paths. |
| Confidence band inflation — personas assign high confidence without cross-lens alignment | Overstates certainty | High | Section 6.3 confidence bands enforced by validator. Governance applies ceiling on split/degraded. |
| DEGRADED run mishandled — system treats lens failure as fatal | Loses valid partial-evidence runs | Medium | run_status: DEGRADED is first-class outcome. Confidence ceiling applied. Badge in UI. |

---

## 15. Open Unknowns (must resolve before Gate 1)

| Unknown | Blocking question | Action |
|---|---|---|
| Deployed config/llm_routing.yaml | Actual production roster, model profiles, temperatures unknown | Retrieve and diff against example config before P1 |
| Normalisation layer current state | Whether a clean OHLCV normalisation step exists or must be built | P1 diagnostic Step 2 |
| Legacy analyst/arbiter.py status | Whether deterministic consensus logic is reusable in P3 | Mandatory pre-P3 review |
| Existing analyst_nodes.py coupling | Whether parallel_analyst_node can be adapted or must be replaced | P2 diagnostic |
| ExecutionRouter operational status | Unknown if live or dead code; impacts replay design | Confirm before PR-AE-10 |

---

## 16. Pre-Code Diagnostic Protocol

Run before starting P1. Report all findings before changing any code.

Step 1 — Audit current analysis pipeline:
```bash
grep -r "build_analysis_graph|analyst_nodes|arbiter_node" ai_analyst/ --include="*.py" -l
```

Step 2 — Audit data normalisation:
```bash
grep -r "ohlcv|ground_truth|market_data|normalise|normalize" ai_analyst/ --include="*.py" -l
```

Step 3 — Confirm existing test baseline:
```bash
cd ai_analyst && python -m pytest --tb=short -q 2>&1 | tail -5
```
Record exact count as regression baseline.

Step 4 — Audit legacy arbiter:
```bash
cat analyst/arbiter.py
cat analyst/personas.py
```

Step 5 — Confirm llm_routing.yaml:
```bash
cat config/llm_routing.yaml 2>/dev/null || echo "MISSING"
cat config/llm_routing.example.yaml
```

Step 6 — Propose smallest patch set:
Report: files to create (new), files to modify (one-line description), estimated line delta per PR.
Do not change any code until this report is reviewed.

---

## 17. Implementation Constraints

All new code lives within ai_analyst/. No new top-level module. No SQLite.

Hard constraints:
- Governance decision logic in Python — no LLM call changes the final decision
- All v1 validators at soft level only
- All lens output fields always present — null, never absent keys
- A lens must never partially return data — valid schema OR clean failure
- Personas must not reference lenses absent from meta.active_lenses
- Persona confidence must stay within defined bands (Section 6.3)
- Deterministic fixture/mock tests only — no live provider dependency in CI
- Live smoke is optional, manual, non-blocking

---

## 18. Success Definition

The Analysis Engine v1 is complete when:

A single run on XAUUSD 1H, initiated from the Lens Control Room, passes through all three lenses producing a complete Evidence Snapshot with derived alignment signals; is interpreted by both Default Analyst and Risk Officer with fully evidence-cited outputs including counterpoints and what_would_change_my_mind; is resolved by the deterministic Governance Layer with typed conflict detection, a veto path, and a DecisionAudit block; produces a run_status of SUCCESS or DEGRADED (never silently fails); and presents the full Decision Audit trail in the Analysis Result View — with the run object persisted and replayable from frozen persona outputs without re-running the analyst fan-out.

All 45 acceptance criteria pass. Existing test count maintained with no regressions.

---

## 19. Phase Roadmap

| Phase | Scope | PRs | Status |
|---|---|---|---|
| Phases 1-8 | Existing system — triage, analysis (legacy), journey, ops, reflect, run browser, charts | — | Complete |
| Analysis Engine v1 | This spec — structural pivot | PR-AE-1 through PR-AE-10 | Spec approved |
| Analysis Engine v2 | Multi-timeframe lenses; ICT lens; additional personas | TBD | Blocked by Gate 5 |
| Evidence Learning Layer | Evidence performance tracking; lens effectiveness metrics | TBD | Blocked by v2 |
| Reflect Integration | Persona drilldown; divergence metrics; evidence audit | TBD | Blocked by P5 |

---

## 20. Diagnostic Findings

To be populated after running the pre-code diagnostic protocol (Section 16).

---

## 21. Appendix A — Claude Code Agent Prompt

```
Read docs/ANALYSIS_ENGINE_SPEC_v1.0.md in full before starting.
Treat it as the controlling spec for this pass.

FIRST TASK ONLY — run the diagnostic protocol in Section 16 and report
findings before changing any code:

1. Audit current analysis pipeline (Section 16, Step 1)
2. Audit data normalisation layer (Step 2)
3. Run full baseline test suite — record exact count (Step 3)
4. Read legacy analyst/arbiter.py and analyst/personas.py (Step 4)
5. Confirm llm_routing.yaml — record actual roster and model profiles (Step 5)
6. Propose smallest patch set: new files, modified files, estimated line delta per PR (Step 6)
7. Report AC gap table: which of AC-1 through AC-10 are currently passing

Hard constraints (Section 17 — non-negotiable):
- No SQLite, no new top-level module
- All lens fields always present — null, never absent
- Deterministic fixture/mock tests only — no live provider in CI
- Governance decision logic in Python — LLM call never changes final decision
- All v1 validators at soft level only
- Lens must never partially return data — valid schema OR clean failure
- Personas must not reference lenses absent from meta.active_lenses
- Persona confidence within defined bands (Section 6.3)

Do not change any code until the diagnostic report is reviewed.

On completion of each phase, close the spec and update docs per Workflow E:
1. ANALYSIS_ENGINE_SPEC_v1.0.md — mark phase Complete, flip AC cells, populate Section 20
2. docs/AI_TradeAnalyst_Progress.md — dashboard-aware update (Workflow E.2)
3. Review system_architecture.md, repo_map.md, technical_debt.md, AI_ORIENTATION.md
4. Cross-document sanity check
5. Return Phase Completion Report (Workflow E.8)

Commit all doc changes on the same branch as implementation.
```

---

## 22. Appendix B — Archived Document Note

docs/archive/PERSONA_REFINEMENT_PLAN_v0.2.md

This document was superseded on 2026-03-18 by the structural pivot to the Analysis Engine Architecture. Its diagnostic findings (audit 2026-03-18), risk register, governance gap analysis, and typed contract patterns remain valid reference material. See Section 1.2 for the specific insights carried forward.

---

_Last updated: 2026-03-18 · v1.2 — 3 final fixes: neutral signal handling, NEUTRAL bias conditions, governance tie-break rule. Spec complete. Ready for PR-AE-1._
