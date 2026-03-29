# Session Briefing Engine — Architecture Design

**Status:** Draft — brainstorming phase
**Date:** 29 March 2026
**Origin:** Fresh-estate design session — designing from infrastructure forward, not retrofitting existing analysis pipeline

---

## Governing Principle

> **Truth is deterministic. Expression is optional.**

The system produces a deterministic evidence state that is testable, reproducible, and complete enough to stand on its own. An optional LLM layer can narrate that state into human-readable briefings, but it never invents fields that don't exist in the compiled state, and the deterministic object remains the source of truth for all downstream uses.

---

## 1. The Estate Map

### What exists (infrastructure — built, tested, operational)

```
TDP (Trading Data Pipeline)
├── PriceStore — 7 instruments, 3M+ candles, multi-timeframe OHLCV
├── MacroStore (COT lane) — 5,845 records, TFF + Disaggregated, 2010–2026
└── MacroStore (FRED lane) — 5 series, 13,093 observations

Macro Data Lab
├── COT Engine — Decomposer → Normaliser → Momentum → Divergence → Regime
├── FRED Context — yield curve slope, VIX, fed funds, M2 growth
├── Treasury Curve Context — 18 columns, full nominal/real/breakeven structure
├── Stress Context — STLFSI4 + elevated flag
└── Output Contracts — COTEvidenceProfile (29 cols), MacroRegimeReport (9 cols),
                        FREDContextProfile (7 cols), TreasuryCurveContextProfile (18 cols),
                        StressContextProfile (2 cols)
```

### What we're designing (the buildings on the estate)

```
Session Briefing Engine (this design)
├── Evidence Compiler (deterministic — Phase A)
│   ├── Layer 1: Macro Frame (slow — weekly refresh)
│   ├── Layer 2: Price Structure Frame (medium — HTF candle refresh)
│   └── Compiled Session Evidence State (the core artifact)
├── Briefing Narrator (optional LLM — Phase B)
│   └── Human-readable session brief from compiled state
└── Watchtower (live reference — Phase C, future)
    └── "Has something meaningful changed within the existing frame?"
```

---

## 2. The Three-Layer Evidence Hierarchy

This is the central design concept. The layers have a **power hierarchy**, not a democratic relationship.

### Layer 1 — Macro Frame (the weather)

**Cadence:** Weekly (COT release cycle). Refreshes when new Lab outputs are available.
**Role:** Sets the context for everything below. Tells you what kind of environment you're operating in.
**Source:** Macro Data Lab output contracts.

**What it answers:**
- What are institutions doing? (COT positioning, percentiles, momentum)
- Is positioning crowded, divergent, or neutral? (regime labels, divergence flags)
- What is the macro backdrop? (yield curve, stress, rates, money supply)
- Are there structural tensions? (spec vs institutional divergence, curve inversion + stress)

**What it does NOT answer:**
- Where to enter. Where to exit. When to trade. What the setup is.

**Hierarchy rule:** Macro can suppress or elevate. It can say "this is a hostile environment for longs" or "positioning is extremely supportive of the current trend." It cannot say "buy here" or "sell now."

### Layer 2 — Price Structure Frame (the terrain)

**Cadence:** Updates when new HTF candles arrive (4H, 1H, Daily). Not tick-by-tick.
**Role:** Defines where you can walk — levels, structure, trend, conditions.
**Source:** OHLCV data from PriceStore, computed through deterministic analysis.

**What it answers:**
- What is the current market structure? (HH/HL, LH/LL, BOS, MSS)
- Where are the key levels? (support, resistance, liquidity pools)
- What is the trend state? (bullish, bearish, ranging — per timeframe)
- What is the volatility context? (ATR-based, session-relative)

**What it does NOT answer:**
- Whether the trend is fighting institutional flow (that's Layer 1 + Layer 2 together).
- Intraday entry timing (that's Layer 3).

### Layer 3 — Execution Surface (the ground)

**Cadence:** Continuous / intraday. Updates with every relevant candle.
**Role:** Where you actually trade. Triggers, entries, invalidations.
**Status:** Future scope — not part of this design. Included for completeness.

**Hierarchy interaction:**

```
Layer 1 (Macro Frame)
   │
   │ FRAMES  ──→  "What kind of day is it? What's favoured?"
   │
   ▼
Layer 2 (Price Structure)
   │
   │ DEFINES  ──→  "Where are the setups? What's the structure?"
   │
   ▼
Layer 3 (Execution)
              ──→  "When do I pull the trigger?"
```

**The key rule: higher layers constrain lower layers, not vice versa.**

A beautiful price setup into resistance means nothing if institutional money is
aggressively long and accelerating. A crowded short regime makes a technical
bounce more likely. The macro frame changes what the price structure *means*.

---

## 3. The Compiled Session Evidence State

This is the core artifact — the thing everything else builds on.

### 3.1 Design principles

1. **One object per instrument per session** — not per timeframe, not per run
2. **Deterministic and reproducible** — same inputs always produce same state
3. **Layered, not flat** — macro frame and price frame are separate sections with explicit hierarchy
4. **Self-contained** — the state carries enough context to be useful without external lookups
5. **Machine-readable** — structured dict/dataclass, not prose
6. **Timestamped** — every section carries its data freshness so consumers know what's current

### 3.2 Proposed schema (conceptual — field names are illustrative)

```python
@dataclass
class SessionEvidenceState:
    """Core artifact: compiled evidence for one instrument, one session."""

    # ── Identity ────────────────────────────────────────────────────
    instrument: str                    # e.g. "XAUUSD"
    session: str                       # e.g. "NY", "London", "Asia"
    compiled_at: datetime              # when this state was built
    compiler_version: str              # for reproducibility

    # ── Layer 1: Macro Frame ────────────────────────────────────────
    macro_frame: MacroFrame

    # ── Layer 2: Price Structure Frame ──────────────────────────────
    price_frame: PriceFrame

    # ── Derived: Cross-Layer Alignment ──────────────────────────────
    alignment: AlignmentAssessment

    # ── Metadata ────────────────────────────────────────────────────
    evidence_quality: EvidenceQuality   # what's present, what's missing
```

### 3.3 MacroFrame (Layer 1 — all deterministic)

```python
@dataclass
class MacroFrame:
    """Weekly macro context framing the session."""

    as_of_week: date                   # release_date_estimated from Lab
    data_age_days: int                 # how old is this data today

    # COT Positioning
    regime_label: str                  # from Lab: SPEC_MONEY_EXTREME_LONG, etc.
    spec_money_pct: float              # speculative-money percentile (0–100)
    inst_money_pct: float              # institutional percentile (0–100)
    spec_momentum_wow: float           # week-over-week change
    spec_momentum_4w: float            # 4-week momentum
    divergence_flag: bool              # spec vs institutional conflict
    divergence_score: float            # 0–1 magnitude

    # Positioning description (deterministic, factual — no "favours" language)
    positioning_lean: str              # "long" | "short" | "neutral"
                                       # factual: where is net positioning pointed?
    positioning_intensity: str         # "extreme" | "strong" | "moderate" | "weak"
                                       # factual: how far from historical center?
    positioning_momentum_dir: str      # "accelerating" | "decelerating" | "flat"
                                       # factual: is positioning moving toward or away from extreme?

    # Macro Backdrop
    yield_curve_slope: float           # 2s10s spread
    curve_inverted: bool
    vix_level: float
    stress_elevated: bool
    fed_funds_rate: float
    m2_growth_rate: float | None

    # Macro environment classification (deterministic — needs §8 Q2 pressure-test)
    macro_environment: str             # "risk_on" | "risk_off" | "transitional" | "neutral"
                                       # NOTE: may need field classification exercise.
                                       # "risk_on" vs "risk_off" could be doctrine-dependent.
    rate_regime: str                   # "tightening" | "easing" | "hold" | "ambiguous"
                                       # Derived from fed_funds_rate trajectory.

    # Factual condition flags (deterministic — no "favours" or "headwind" language)
    caution_flags: list[str]           # e.g. ["positioning_extreme", "stress_elevated",
                                       #        "curve_inverted", "momentum_decelerating"]
                                       # GOVERNANCE: same rule as conditions_present —
                                       # must be factual, not doctrinal.
```

### 3.4 PriceFrame (Layer 2 — all deterministic)

```python
@dataclass
class PriceFrame:
    """Current price structure across analysis timeframes."""

    as_of: datetime                    # timestamp of most recent candle used
    timeframes_analysed: list[str]     # e.g. ["4H", "1H", "15M"]

    # Per-timeframe structure (list of TimeframeStructure)
    structures: list[TimeframeStructure]

    # Cross-timeframe synthesis (deterministic)
    htf_bias: str                      # "bullish" | "bearish" | "ranging"
    trend_alignment: str               # "aligned" | "mixed" | "conflicted"
    key_levels: list[KeyLevel]         # sorted by proximity to current price
    volatility_state: str              # "expanding" | "contracting" | "normal"
    current_price: float

@dataclass
class TimeframeStructure:
    timeframe: str
    trend_direction: str               # "bullish" | "bearish" | "ranging"
    structure_state: str               # "HH_HL" | "LH_LL" | "mixed"
    last_bos_direction: str | None     # "bullish" | "bearish" | None
    atr_value: float
    candle_count: int                  # how many candles were analysed

@dataclass
class KeyLevel:
    price: float
    level_type: str                    # "support" | "resistance" | "liquidity"
    source_timeframe: str
    distance_atr: float                # distance from current price in ATR units
    tested_count: int
```

### 3.5 AlignmentAssessment (cross-layer — all deterministic)

This is where the hierarchy manifests. The alignment assessment is computed
from Layer 1 + Layer 2 together, with Layer 1 framing Layer 2.

**Design principle (locked):**
> The compiler answers: "What is the state of the world?"
> The narrator answers: "What does this mean for you today?"

Every field in this section was pressure-tested via the field classification
exercise (see `docs/ALIGNMENT_FIELD_CLASSIFICATION.md`). Fields that encoded
trading doctrine (favoured/suppressed play types, "favours" language,
"conviction" language) were removed or renamed to factual descriptions.

```python
@dataclass
class AlignmentAssessment:
    """Deterministic assessment of macro-price alignment.

    Rules:
    - All fields describe STATE, not MEANING
    - No field uses "favour", "suppress", "conviction", or "recommend"
    - The narrator (optional LLM layer) owns interpretation
    - Doctrine must not leak into the compiler disguised as helpful structure
    """

    # DERIVED FACTS — directional comparison
    macro_price_alignment: str         # "aligned" | "conflicted" | "neutral"
                                       # aligned = positioning lean matches structure lean
                                       # conflicted = they point opposite directions
                                       # neutral = one or both are directionless
                                       # NOTE: "aligned" is directional agreement,
                                       # NOT a quality judgment. Whether alignment is
                                       # good (supportive) or bad (crowded) is doctrine.

    macro_positioning_lean: str        # "long" | "short" | "neutral"
                                       # factual: where is net positioning pointed?
    macro_positioning_intensity: str   # "extreme" | "strong" | "moderate" | "weak"
                                       # factual: how far from center?
    price_structure_lean: str          # "bullish" | "bearish" | "ranging"
                                       # factual: what direction does structure point?

    # DERIVED FACTS — cross-layer observations
    tensions: list[str]                # Factual conflict descriptions.
                                       # e.g. ["price_bearish_positioning_long",
                                       #        "momentum_decelerating_trend_up",
                                       #        "positioning_extreme_with_stress_elevated"]
                                       # Vocabulary must describe states, not implications.
                                       # See governance note on conditions_present below.

    conditions_present: list[str]      # Factual state descriptions.
                                       # e.g. ["macro_price_conflict",
                                       #        "institutional_long_extreme",
                                       #        "price_trending_up",
                                       #        "structure_range_bound"]
                                       # GOVERNANCE: vocabulary must be rigorously
                                       # descriptive. Test: would two traders with
                                       # different styles agree this condition IS present,
                                       # even if they disagree on what it MEANS?
                                       # Forbidden: "trend_continuation_setup",
                                       # "short_squeeze_risk", "mean_reversion_opportunity"

    # DERIVED FACT — internal evidence agreement
    evidence_coherence: str            # "strong" | "moderate" | "weak" | "conflicted"
                                       # Measures how much evidence layers agree.
                                       # NOT trading confidence. NOT conviction.
                                       # strong = layers point same direction strongly
                                       # conflicted = layers point opposite directions

    # CONSTRAINTS — frame dependencies
    invalidation_triggers: list[str]   # Conditions that would change the frame.
                                       # e.g. ["COT regime shifts to DIVERGENT_SPLIT",
                                       #        "4H structure breaks below 2340",
                                       #        "VIX crosses above 25"]
```

**Removed from compiler (moved to narrator territory):**
- `macro_favours` / `price_favours` → replaced by factual lean + intensity
- `favoured_play_types` → doctrine; different frameworks disagree
- `suppressed_play_types` → doctrine; different frameworks disagree
- `conviction_context` → renamed to `evidence_coherence` (internal agreement, not trading confidence)

### 3.6 EvidenceQuality (metadata — what's present, what's missing)

Same philosophy as T3 trust integrity — don't claim more than you have.

```python
@dataclass
class EvidenceQuality:
    """What evidence is present, what's missing, what's stale."""

    macro_frame_available: bool
    macro_frame_age_days: int
    macro_frame_quality: str           # "full" | "partial" | "unavailable"

    price_frame_available: bool
    price_frame_age_minutes: int
    price_frame_quality: str           # "full" | "partial" | "unavailable"

    alignment_computable: bool         # False if either frame unavailable
    missing_evidence: list[str]        # e.g. ["stress_data", "treasury_curves"]

    overall_confidence: str            # "high" | "moderate" | "low" | "insufficient"
```

---

## 4. The Briefing Narrator (Phase B — optional LLM)

### 4.1 Contract

The narrator receives a compiled `SessionEvidenceState` and produces a
`SessionBrief` — human-readable, prioritised, actionable.

```python
@dataclass
class SessionBrief:
    """Optional LLM-generated briefing from compiled evidence."""

    instrument: str
    session: str
    generated_at: datetime

    # The brief
    headline: str                      # One sentence: the most important thing
    macro_summary: str                 # 2–3 sentences: what the macro frame says
    structure_summary: str             # 2–3 sentences: what price structure shows
    alignment_summary: str             # 2–3 sentences: how they interact
    favoured_approach: str             # What kind of trading is favoured today
    key_cautions: list[str]            # What to watch out for
    change_of_mind: str                # What would flip the thesis

    # Provenance
    evidence_state_hash: str           # Links back to the exact compiled state
    narrator_model: str                # Which LLM produced this
```

### 4.2 Rules

1. The narrator reads the compiled state — it does NOT access raw data directly
2. Every claim in the brief must be traceable to a field in the evidence state
3. The narrator may prioritise, emphasise, and rephrase — it may NOT invent
4. The compiled state is the source of truth — if the brief contradicts the state, the state wins
5. The brief is disposable — the state is persistent. Regenerating the brief from the same state should produce a substantially similar output

---

## 5. Where Things Live (Estate Architecture)

### Option A — New standalone repo: `session-briefing-engine`

```
session-briefing-engine/
├── src/
│   ├── compiler/          # Deterministic evidence compiler
│   │   ├── macro_frame.py     # Reads Lab outputs → MacroFrame
│   │   ├── price_frame.py     # Reads PriceStore → PriceFrame
│   │   ├── alignment.py       # Computes cross-layer alignment
│   │   └── compiler.py        # Orchestrates → SessionEvidenceState
│   ├── narrator/          # Optional LLM briefing layer
│   │   └── briefing.py        # Compiled state → SessionBrief
│   ├── models/            # Dataclasses / Pydantic models
│   └── config/            # Instrument registry, thresholds
├── tests/
└── docs/
```

This consumes from TDP (PriceStore) and Macro Data Lab (output contracts)
as external dependencies. Clean boundary. Own test suite. Own release cycle.

### Option B — Inside AI Trade Analyst repo

```
ai_analyst/
├── briefing/              # New package
│   ├── compiler/
│   ├── narrator/
│   └── models/
```

Tighter coupling to the existing API surface, persona system, and UI.
Faster to wire into the existing Agent Ops and Reflect workspaces.

### Recommendation: Option A (new repo)

Reasons:
- The briefing engine is a **core estate building**, not a feature of the analysis pipeline
- It should be usable without the AI Trade Analyst's persona/arbiter system
- Clean dependency direction: TDP → Lab → Briefing Engine → (consumers)
- The existing AI Trade Analyst can be one consumer of the briefing engine, not its owner
- Follows the same pattern as TDP → Lab: each layer has its own repo, tests, and contracts

---

## 6. What to Build First

### Phase 1 — Macro Frame Compiler

Build the `MacroFrame` dataclass and the compiler that reads Lab output contracts
and produces it. This is the "weather station" — it doesn't need price data at all.

**Inputs:** Lab COTEvidenceProfile, MacroRegimeReport, FREDContextProfile,
TreasuryCurveContextProfile, StressContextProfile
**Output:** `MacroFrame` per instrument

**Why first:** The macro frame is the slowest-changing, most infrastructure-dependent
layer. It exercises the Lab → Briefing Engine data flow. And it answers questions
that are immediately useful: "What is the positioning context for XAUUSD this week?"

### Phase 2 — Price Frame Compiler

Build the `PriceFrame` dataclass and the compiler that reads PriceStore OHLCV
and computes multi-timeframe structure.

**Inputs:** PriceStore candles (multi-TF)
**Output:** `PriceFrame` per instrument

### Phase 3 — Alignment + Evidence Quality

Build the `AlignmentAssessment` and `EvidenceQuality` layers that combine
Layer 1 and Layer 2 into the full `SessionEvidenceState`.

### Phase 4 — Briefing Narrator (optional)

Build the LLM narrator that reads a compiled state and produces a `SessionBrief`.

---

## 7. What This Means for the Existing AI Trade Analyst

The existing AI Trade Analyst (lenses, personas, arbiter) becomes ONE POSSIBLE
CONSUMER of the Session Briefing Engine, not the center of the estate.

Future options:
- The personas receive the `SessionEvidenceState` instead of raw lens outputs
- The arbiter references the `AlignmentAssessment` as framing context
- The Reflect workspace evaluates trades against the macro frame
- The MacroContext UI workspace (backlog item) renders the compiled state
- Or: an entirely different interface consumes the briefing engine directly

The estate metaphor holds: TDP is the utilities, Lab is the treatment plant,
Briefing Engine is the main house, and AI Trade Analyst is one room in that house.

---

## 8. Open Design Questions (to resolve before implementation)

1. **Positioning bias rules:** What specific percentile thresholds map to
   "supportive_of_longs" vs "crowded_long" vs "neutral"? These need to be
   defined as a configurable rule set, not hardcoded.

2. **Macro environment classification:** What combination of VIX + stress +
   curve shape + rate regime = "risk_on" vs "risk_off"? This is a deterministic
   rule but the rule itself needs trading-domain expertise to define.

3. **Alignment computation:** How exactly does "institutions are 87th percentile
   long" + "price structure is bearish" = "conflicted"? The alignment rules
   are the heart of the system and need careful, experience-driven design.

4. **Play-type vocabulary:** What are the canonical play types?
   (trend_continuation, pullback, reversal, breakout, etc.) These need to
   be a closed vocabulary that the narrator can reference.

5. **Update semantics:** When price data arrives, does only Layer 2 + alignment
   refresh? Or does the macro frame also re-check for new Lab data?

6. **Instrument-specific rules:** Does XAUUSD have different alignment logic
   than EURUSD? Gold responds to macro differently than forex.
