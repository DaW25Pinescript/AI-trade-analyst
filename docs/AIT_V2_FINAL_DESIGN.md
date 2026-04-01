# AI Trade Analyst v2 — Consolidated Design (Final)

**Generated:** 2026-04-01  
**Status:** Amended and ready for PROJECT_AIM.md promotion  
**Origin:** Three-round design session + critical review + amendment pass  
**Supersedes:** AIT_V2_DESIGN_BRAINSTORM.md, AIT_V2_DESIGN_REVISION.md, AIT_V2_AMENDMENT_NOTE.md

---

## 1. The Problem

AIT v1 was built around "show chart screenshot to LLM persona." The estate
now produces actual numerical evidence:

- **TDP** — canonical OHLCV + macro facts (239 tests)
- **Macro Data Lab** — deterministic macro evidence profiles (253 tests)
- **BOS Structure Analyser** — break-of-structure events, chains, stats (205 tests)
- **MTF Trendline Analyser** — trendline break events, HTF confluence (285 tests)
- **SBE** — compiled `SessionEvidenceState` per instrument per session (590 tests)

AIT v1 cannot consume any of this. 13 agents unavailable, 39 runs at 100%
NO_TRADE, evidence foundation obsolete. AIT v2 is a full rebuild that
cherry-picks working elements and rebuilds around the data-first evidence
foundation.

---

## 2. Locked Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D-28 | SBE owns evidence semantics only. No doctrine-named objects. | SBE defines vocabulary; AIT defines how to read it. |
| D-29 | Lens Chamber (attention + interpretation) lives in AIT v2. | Keeps SBE clean as infrastructure. |
| D-30 | SC-13 reinterpreted as "lens-ready consumer contract proof." | SBE proves consumability; doesn't ship the chamber. |
| D-31 | Four-part decomposition: Evidence State (SBE), Lens Definition (AIT), Lens Run (AIT), Governance (AIT). | Clean fact/attention/interpretation/verdict separation. |
| D-32 | Agent = doctrine-bearing interpreter of structured evidence. | Not a roleplay wrapper around a screenshot. |
| D-33 | C-prime: typed, governed `EvidenceExtension` slot on `SessionEvidenceState`. | Specialist evidence rides alongside core without SBE schema expansion. |
| D-34 | Extension promotion rule: graduates to first-class SBE frame only if broadly reused, stable, operationally central, no longer doctrine-specific. | Prevents premature canonisation. |
| D-35 | Unified evidence namespace: `core.*`, `ext.<type>.meta.*`, `ext.<type>.data.*`. | Single addressing scheme across the full evidence surface. |
| D-36 | Triage tile priority: evidence quality → directional lean → tension count → narrator headline. | Evidence quality is the first thing the trader sees. |
| D-37 | Two-tier extension validation: SBE validates envelope, consumer-side registry validates payloads. | SBE stays clean; payload governance is the consumer's responsibility. |
| D-38 | Hard vetoes are typed `VetoPredicate` structs. Governed operator set: 8 operators (see §6.2). | No hidden expression parser. Every veto is inspectable/testable/auditable. |
| D-39 | Extension namespace split: `ext.<type>.meta.*` for envelope, `ext.<type>.data.*` for payload. | Eliminates ambiguity between envelope metadata and payload fields. |
| D-40 | AIT v2 uses SBE's shipped vocabulary exactly. No invented values. Registration-time validation. | Prevents contract drift between producer and consumer. |
| D-41 | Triage Board shows deterministic readiness only. No lens execution on tile load. Chamber output on drill-down. | Keeps triage fast, cheap, trustworthy. |
| D-42 | `LensDefinition` (deterministic config) separate from `LensPersona` (LLM rendering config). | Independently testable and versionable. |
| D-43 | SBE validates extension-type shape, not family membership. No `GOVERNED_EXTENSION_TYPES` in SBE. | Prevents SBE re-coupling to specific specialist evidence families. |
| D-44 | Namespace resolver uses `MISSING` sentinel with `TypeError`-raising `__bool__`. `(found, value)` return. | Prevents misclassification of valid falsey evidence as absent. Forces correct usage. |
| D-45 | Unknown extensions are ignorable. Registry only errors when a lens actively requires an unregistered family. | Forward-compatible packets. |
| D-46 | Three-layer output: deterministic `LensAssessment` → LLM-derived `LensInterpretation` → optional `LensNarrative`. | Assessment is governance truth. Interpretation is structured opinion. Narrative is disposable prose. |
| D-47 | `LensAssessment` contains ONLY mechanically derivable fields. No `directional_view`, no `confidence`, no `key_observations`. | Assessment layer must be producible with zero LLM calls. |
| D-48 | `LensInterpretation` is honest about its provenance: LLM-derived, structured, validated, but not deterministic. | Interpretive fields live where they belong. |
| D-49 | Chamber orchestrator never emits `LensInterpretation` for a lens whose `LensAssessment.outcome_type == "abstain"`. | Assessment gates interpretation. Mechanical truth gates opinion. |
| D-50 | Extension payloads deep-frozen via `MappingProxyType` + recursive tuple conversion. `EvidenceExtension.create()` is canonical constructor. | Real immutability, not just attribute-reassignment prevention. |
| D-51 | One extension per `extension_type` per packet. Duplicates rejected at envelope validation. | No silent first-match-wins. Multi-instance requires explicit future design. |
| D-52 | Veto operators: `==`, `!=`, `in`, `not_in`, `contains`, `not_contains`, `is_true`, `is_false`. 8 total. | `contains`/`not_contains` handle collection membership checks. |
| D-53 | Resolver distinguishes optional zones (macro, price) from required zones (alignment, quality). `None` on required = `ValueError`. | Type violations surface, not hide behind MISSING. |
| D-54 | `compute_lens_readiness` collects ALL blockers with specific paths. No early-break. | Operator gets full diagnostic picture on triage board. |
| D-55 | Resolver uses `try/except AttributeError`, not `hasattr`. | Non-attribute errors propagate instead of being silently swallowed. |
| D-56 | `MISSING.__bool__` raises `TypeError`. | Forces callers to use the `found` flag, not truthiness. |

---

## 3. Estate Flow (v2)

```
TDP (wire service)
  └─→ PriceStore + MacroStore

Macro Data Lab (research — macro)       BOS Analyser (correspondent — structure)
  └─→ COTEvidenceProfile                  └─→ BOS events + chains + profiles
  └─→ MacroRegimeReport                 Trendline Analyser (correspondent — trendlines)
  └─→ FREDContextProfile                  └─→ TL break events + HTF state
  └─→ TreasuryCurveContextProfile
  └─→ StressContextProfile

Session Briefing Engine (editorial briefing)
  └─→ SessionEvidenceState
         ├── core: MacroFrame + PriceFrame + Alignment + Quality
         └── extensions: tuple[EvidenceExtension, ...]  (caller-attached, deep-frozen)
  └─→ SessionBrief (narrator — optional)

AI Trade Analyst v2 (opinion desk + editor's desk)
  ├─ Extension Schema Registry (payload validation)
  ├─ Namespace Resolver (field lookup with MISSING semantics)
  ├─ Lens Chamber
  │   ├─ LensDefinition registry (deterministic attention + vetoes)
  │   ├─ LensPersona registry (LLM rendering config)
  │   ├─ Chamber Orchestrator
  │   │     └─→ per lens:
  │   │           LensAssessment (deterministic governance trace)
  │   │             └─→ if ready:
  │   │                   LensInterpretation (structured LLM opinion)
  │   │                     └─→ optionally:
  │   │                           LensNarrative (disposable prose)
  │   └─ Trust hierarchy: Assessment ▸ overrides ▸ Interpretation ▸ overrides ▸ Narrative
  ├─ Governance / Arbitration (consumes LensInterpretations across lenses)
  ├─ Triage Board (evidence state + deterministic readiness only)
  ├─ Journal (decision tracking against evidence packets)
  └─ Reflect (pattern detection over interpretation history)

Human (editor / decision room)
```

---

## 4. EvidenceExtension (SBE-side)

### 4.1 Extension-Type Shape Validation (D-43)

SBE does NOT maintain a governed set of extension types. It validates shape:

```python
import re

EXTENSION_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,49}$")

def validate_extension_type(ext_type: str) -> bool:
    """SBE validates shape, not family membership."""
    return bool(EXTENSION_TYPE_PATTERN.match(ext_type))
```

### 4.2 Model Shape (D-50)

```python
import types
from typing import Any

GOVERNED_FRESHNESS_STATES = frozenset({"fresh", "stale", "unknown"})
GOVERNED_TRUST_STATES = frozenset({"verified", "unverified", "degraded"})


def _deep_freeze(obj: Any) -> Any:
    """Recursively freeze a dict/list structure for immutable storage."""
    if isinstance(obj, dict):
        return types.MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


@dataclass(frozen=True)
class EvidenceExtension:
    """A typed specialist evidence insert attached to a SessionEvidenceState."""

    # Identity
    extension_id: str
    extension_type: str             # shape-validated, not family-governed
    producer: str
    version: str

    # Provenance
    generated_at: datetime
    data_age_minutes: int | None

    # Trust
    freshness_state: str            # governed: "fresh" | "stale" | "unknown"
    trust_state: str                # governed: "verified" | "unverified" | "degraded"

    # Payload — deep-frozen, opaque to SBE, validated by consumer-side registry
    payload: types.MappingProxyType

    @staticmethod
    def create(
        extension_id: str,
        extension_type: str,
        producer: str,
        version: str,
        generated_at: datetime,
        data_age_minutes: int | None,
        freshness_state: str,
        trust_state: str,
        payload: dict,
    ) -> "EvidenceExtension":
        """Factory that deep-freezes the payload at construction time."""
        return EvidenceExtension(
            extension_id=extension_id,
            extension_type=extension_type,
            producer=producer,
            version=version,
            generated_at=generated_at,
            data_age_minutes=data_age_minutes,
            freshness_state=freshness_state,
            trust_state=trust_state,
            payload=_deep_freeze(payload),
        )
```

### 4.3 Updated SessionEvidenceState

```python
@dataclass(frozen=True)
class SessionEvidenceState:
    instrument: str
    compiled_at: datetime

    macro_frame: MacroFrame | None
    price_frame: PriceFrame | None
    alignment: AlignmentAssessment
    evidence_quality: EvidenceQuality

    # C-prime extension slot (D-33, D-50, D-51)
    extensions: tuple[EvidenceExtension, ...] = ()
```

### 4.4 SBE Envelope Validation

SBE's consumer contract validates extensions at the envelope level only:

- `extension_id`: non-empty string
- `extension_type`: matches `EXTENSION_TYPE_PATTERN` (shape, not family — D-43)
- `freshness_state`: in `GOVERNED_FRESHNESS_STATES`
- `trust_state`: in `GOVERNED_TRUST_STATES`
- `generated_at`: valid datetime
- `version`: non-empty string
- `payload`: is a dict or `MappingProxyType` (type check only)
- **No duplicate `extension_type` values per packet** (D-51)

### 4.5 Two-Tier Validation (D-37)

```
Tier 1 — SBE boundary:
  Validates envelope (identity, provenance, trust vocabulary, uniqueness).
  Does NOT import or inspect payload.

Tier 2 — Consumer boundary (shared package or AIT):
  ExtensionSchemaRegistry dispatches per-family payload validators.
  Unknown-but-unused extension types are ignored (D-45).
  Only errors when a lens requires or references an unregistered family.
```

### 4.6 Consumer-Side Schema Registry

```python
from typing import Protocol, Any


class ExtensionPayloadValidator(Protocol):
    """Contract for per-family payload validators."""

    def validate(self, payload: dict, version: str) -> list[str]:
        """Return validation errors. Empty list = valid."""
        ...

    @property
    def extension_type(self) -> str: ...


class ExtensionSchemaRegistry:
    """Dispatches payload validation by extension_type."""

    def __init__(self) -> None:
        self._validators: dict[str, ExtensionPayloadValidator] = {}

    def register(self, validator: ExtensionPayloadValidator) -> None:
        self._validators[validator.extension_type] = validator

    def is_known(self, extension_type: str) -> bool:
        return extension_type in self._validators

    def validate(self, extension: EvidenceExtension) -> list[str]:
        """Validate payload. Unknown types return empty (D-45)."""
        validator = self._validators.get(extension.extension_type)
        if validator is None:
            return []   # unknown-but-unused: ignorable
        return validator.validate(extension.payload, extension.version)

    def validate_required(self, extension: EvidenceExtension) -> list[str]:
        """Validate payload for a lens-required extension.
        Unknown types are errors here — lens needs it but we can't validate."""
        validator = self._validators.get(extension.extension_type)
        if validator is None:
            return [f"No validator for required type '{extension.extension_type}'"]
        return validator.validate(extension.payload, extension.version)
```

### 4.7 Extension Payload Contracts

Each extension type has a governed payload schema. These live in the
consumer-side schema package, not in SBE.

**`extension_type: "bos"` — BOS Structure Evidence**

```python
{
    "timeframes": {
        "<TF>": {                                   # "1H" | "4H" | "D" | "W"
            "last_bos_direction": "bull" | "bear" | None,
            "last_bos_bars_ago": int | None,
            "active_chain_direction": "bull" | "bear" | None,
            "active_chain_depth": int,
            "break_context_type": str | None,
            "displacement_bucket": str | None,       # "strong" | "moderate" | "weak"
        },
    },
    "htf_alignment": "aligned_bull" | "aligned_bear" | "mixed" | "insufficient",
    "chain_momentum": "extending" | "stalling" | "reversing" | "no_chain",
    "statistical_profile": {
        "retrace_incidence_qualified": float,
        "median_retrace_depth_pct": float,
        "mean_mfe_atr": float,
        "mean_chain_length": float,
        "bos_rate_per_1k": float,
    },
}
```

**`extension_type: "trendline"` — Trendline Evidence**

```python
{
    "htf_state": {
        "<TF>": {                                   # "D" | "W"
            "resistance_found": bool,
            "resistance_slope": float | None,
            "resistance_touches": int | None,
            "support_found": bool,
            "support_slope": float | None,
            "support_touches": int | None,
        },
    },
    "recent_breaks": {
        "<TF>": {                                   # "1H" | "4H"
            "direction": "bull" | "bear" | None,
            "line_role": "resistance" | "support" | None,
            "quality_tier": str | None,
            "break_strength_atr": float | None,
            "bars_ago": int | None,
            "htf_geom_score": float | None,
        },
    },
    "statistical_profile": {
        "mean_mfe_atr_all": float,
        "mean_mfe_atr_htf_geom_1": float | None,
        "event_count": int,
        "htf_geom_1_count": int | None,
    },
}
```

---

## 5. Namespace Resolution (D-35, D-39, D-44, D-53, D-55, D-56)

### 5.1 Full Namespace Scheme

```
core.macro.<field>                    → MacroFrame attribute
core.price.<field>                    → PriceFrame top-level attribute
core.price.<tf>.<field>               → TimeframeAnalysis for H1/H4/D/W
core.price.key_levels                 → tuple[KeyLevel, ...]
core.alignment.<field>                → AlignmentAssessment attribute
core.quality.<field>                  → EvidenceQuality attribute

ext.<type>.meta.<field>               → EvidenceExtension envelope attribute
ext.<type>.data.<path>                → payload traversal (MappingProxyType)
```

### 5.2 MISSING Sentinel (D-44, D-56)

```python
class _MissingSentinel:
    """Singleton sentinel for absent evidence fields."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        raise TypeError(
            "Do not use truthiness on MISSING. "
            "Check the 'found' flag from resolve_field() instead."
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _MissingSentinel)

    def __hash__(self) -> int:
        return hash("MISSING_SENTINEL")


MISSING = _MissingSentinel()
```

### 5.3 Resolver (D-53, D-55)

```python
import types
from typing import Any

OPTIONAL_CORE_ZONES = {"macro", "price"}
REQUIRED_CORE_ZONES = {"alignment", "quality"}


def resolve_field(state: SessionEvidenceState, path: str) -> tuple[bool, Any]:
    """Resolve a namespace path against an evidence packet.

    Returns (found, value):
      - (True, <value>)   — field exists, value may be None/False/0/()
      - (False, MISSING)  — field does not exist or optional parent is absent
    Raises ValueError if a required core zone is None (malformed state).
    """
    parts = path.split(".")

    if parts[0] == "core":
        return _resolve_core(state, parts[1:])
    elif parts[0] == "ext":
        return _resolve_ext(state, parts[1:])
    else:
        return (False, MISSING)


def _resolve_core(state: SessionEvidenceState, parts: list[str]) -> tuple[bool, Any]:
    if not parts:
        return (False, MISSING)

    zone = parts[0]
    remainder = parts[1:]

    zone_map = {
        "macro": state.macro_frame,
        "price": state.price_frame,
        "alignment": state.alignment,
        "quality": state.evidence_quality,
    }

    if zone not in zone_map:
        return (False, MISSING)

    obj = zone_map[zone]

    if obj is None:
        if zone in REQUIRED_CORE_ZONES:
            raise ValueError(
                f"Core zone '{zone}' is None but is required. "
                f"SessionEvidenceState is malformed."
            )
        return (False, MISSING)

    return _traverse_object(obj, remainder)


def _resolve_ext(state: SessionEvidenceState, parts: list[str]) -> tuple[bool, Any]:
    if len(parts) < 2:
        return (False, MISSING)

    ext_type = parts[0]
    sub_zone = parts[1]
    remainder = parts[2:]

    ext = None
    for e in state.extensions:
        if e.extension_type == ext_type:
            ext = e
            break

    if ext is None:
        return (False, MISSING)

    if sub_zone == "meta":
        return _traverse_object(ext, remainder)
    elif sub_zone == "data":
        return _traverse_dict(ext.payload, remainder)
    else:
        return (False, MISSING)


def _traverse_object(obj: Any, parts: list[str]) -> tuple[bool, Any]:
    """Traverse a dataclass/object by attribute names. (D-55)"""
    if not parts:
        return (True, obj)

    current = obj
    for part in parts:
        try:
            current = getattr(current, part)
        except AttributeError:
            return (False, MISSING)

    return (True, current)


def _traverse_dict(d: Any, parts: list[str]) -> tuple[bool, Any]:
    """Traverse a nested dict/MappingProxyType by key path."""
    if not parts:
        return (True, d)

    current = d
    for part in parts:
        if isinstance(current, (dict, types.MappingProxyType)) and part in current:
            current = current[part]
        else:
            return (False, MISSING)

    return (True, current)
```

### 5.4 Resolution Rules

1. `core.*` → attribute lookup on sub-objects. Optional zones (`macro`, `price`)
   return `(False, MISSING)` when `None`. Required zones (`alignment`, `quality`)
   raise `ValueError` when `None` — this is a malformed state, not legitimate absence.

2. `ext.<type>.meta.*` → attribute lookup on the `EvidenceExtension` envelope.

3. `ext.<type>.data.*` → key traversal inside the extension's frozen payload.

4. **Missing-path veto rule:** If a veto predicate references a path that
   resolves to `(False, MISSING)`, the veto does NOT fire. Absence ≠ violation.
   Missing required extensions are handled by the `required_extensions` mechanism.

5. **Falsey-but-present:** `(True, False)`, `(True, 0)`, `(True, ())` are all
   valid present values. Only `(False, MISSING)` means absent. Using truthiness
   on `MISSING` raises `TypeError`.

### 5.5 V1 Limitation: Collection Traversal Boundary

> The namespace resolver returns collections (tuples, lists, MappingProxyType)
> as atomic values. There is no indexing, filtering, or querying inside
> collections. Lenses that need specific elements from `core.price.key_levels`
> or `core.alignment.tensions` must post-process the resolved value in lens
> evaluation code. A collection query syntax may be added in a future version
> if multiple lenses demonstrate the need.

---

## 6. LensDefinition (AIT v2 — Deterministic Config)

### 6.1 Attention + Governance Layer

```python
@dataclass(frozen=True)
class FieldWeight:
    """How much a lens cares about a specific evidence field."""
    field_path: str             # full namespace path
    weight: str                 # "critical" | "heavy" | "moderate" | "low" | "ignore"
    rationale: str              # auditable reason


GOVERNED_WEIGHT_VALUES = frozenset({
    "critical", "heavy", "moderate", "low", "ignore"
})


@dataclass(frozen=True)
class VetoPredicate:
    """A typed rule that forces lens abstention. (D-38, D-52)"""
    field_path: str
    operator: str               # governed set below
    value: str | tuple[str, ...] | bool | None
    reason: str                 # human-readable


GOVERNED_VETO_OPERATORS = frozenset({
    "==", "!=",
    "in", "not_in",               # scalar ∈ collection (predicate.value is a collection)
    "contains", "not_contains",   # collection ∋ scalar (predicate.value is a scalar)
    "is_true", "is_false",
})


@dataclass(frozen=True)
class LensDefinition:
    """Static, auditable declaration of a doctrine-bearing interpreter.

    Pure config. No LLM. No interpretation. Declares what the lens
    pays attention to and when it abstains.
    """
    # Identity
    lens_id: str
    lens_name: str
    lens_family: str            # "structure" | "trend" | "macro" | "risk"
    version: str

    # Attention
    field_weights: tuple[FieldWeight, ...]
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]

    # Extension requirements
    required_extensions: tuple[str, ...]
    optional_extensions: tuple[str, ...]

    # Governance (typed predicates — D-38)
    hard_vetoes: tuple[VetoPredicate, ...]
    minimum_evidence_quality: str       # "high" | "moderate" | "low"
    minimum_extension_freshness: str    # "fresh" | "stale"

    # Output contract
    allowed_outputs: tuple[str, ...]
    abstention_reasons: tuple[str, ...]
```

### 6.2 Veto Evaluation (D-52)

```python
def evaluate_veto(predicate: VetoPredicate, evidence_value: Any) -> bool:
    """Returns True if the veto fires (lens should abstain).
    Pure function. No side effects."""
    match predicate.operator:
        case "==":
            return evidence_value == predicate.value
        case "!=":
            return evidence_value != predicate.value
        case "in":
            return evidence_value in predicate.value
        case "not_in":
            return evidence_value not in predicate.value
        case "contains":
            if not isinstance(evidence_value, (tuple, list, frozenset, set)):
                return False
            return predicate.value in evidence_value
        case "not_contains":
            if not isinstance(evidence_value, (tuple, list, frozenset, set)):
                return True
            return predicate.value not in evidence_value
        case "is_true":
            return evidence_value is True
        case "is_false":
            return evidence_value is False
        case _:
            raise ValueError(f"Unknown veto operator: {predicate.operator}")
```

**Operator semantics:**

| Operator | Reads as | Evidence type | Predicate value type |
|----------|----------|---------------|---------------------|
| `==` | evidence equals value | scalar | scalar |
| `!=` | evidence does not equal value | scalar | scalar |
| `in` | evidence is in collection | scalar | tuple of allowed values |
| `not_in` | evidence is not in collection | scalar | tuple of forbidden values |
| `contains` | evidence collection contains value | tuple/list | scalar to find |
| `not_contains` | evidence collection does not contain value | tuple/list | scalar that should be absent |
| `is_true` | evidence is True | bool | None (unused) |
| `is_false` | evidence is False | bool | None (unused) |

---

## 7. LensPersona (AIT v2 — LLM Rendering Config)

Separate from LensDefinition so that attention maps are auditable without
LLM involvement, and prompts can be iterated without touching deterministic
config. (D-42)

```python
@dataclass(frozen=True)
class LensPersona:
    """LLM rendering configuration for a lens."""

    lens_id: str                        # must match a LensDefinition.lens_id
    persona_description: str
    interpretation_prompt_template: str  # template consuming weighted evidence
    model_preference: str               # e.g. "claude-sonnet-4-20250514"
    max_tokens: int
    temperature: float                  # typically 0.0–0.3

    # Output governance
    forbidden_language: frozenset[str]
    required_output_fields: tuple[str, ...]
```

**Analogy:** LensDefinition is the written law (what evidence is admissible,
what triggers a mistrial). LensPersona is how the judge speaks (voice, style).
Audit the law without reading the speeches. Iterate the speeches without
rewriting the law.

### 7.1 V1 Limitation: Forbidden Language Superset Convention

> `LensPersona.forbidden_language` is expected to be a superset of SBE's
> `NARRATOR_FORBIDDEN_LANGUAGE` but this is not enforced at registration
> time. For v1, this is documented convention. A future version may add a
> factory or registration-time check that automatically merges the base set.

---

## 8. Chamber Output: Three-Layer Model (D-46, D-47, D-48, D-49)

```
LensAssessment           — what we KNOW deterministically
  │                        (evidence usage, vetoes, abstention, provenance)
  │
  ▼  (only if outcome_type == "ready_for_interpretation")
LensInterpretation       — what the LLM CONCLUDES given weighted evidence
  │                        (directional_view, confidence, key_observations)
  │
  ▼  (optional)
LensNarrative            — how the LLM EXPLAINS its conclusion
                           (prose, disposable)

Trust hierarchy: Assessment ▸ overrides ▸ Interpretation ▸ overrides ▸ Narrative
```

### 8.1 LensAssessment (Deterministic — D-47)

Contains ONLY fields derivable by mechanical evaluation. No LLM. The litmus
test: can you produce this with zero API calls? If yes, it belongs here.

```python
@dataclass(frozen=True)
class EvidenceUsage:
    """What evidence a lens actually consumed."""
    core_fields_used: tuple[str, ...]
    core_fields_missing: tuple[str, ...]
    extensions_used: tuple[str, ...]
    extensions_missing: tuple[str, ...]
    extensions_stale: tuple[str, ...]


@dataclass(frozen=True)
class LensAssessment:
    """Deterministic governance output. Every field is mechanically derived.

    Answers: "Can this lens run? What did it see? Why did it abstain?"
    No interpretation. No opinion.
    """
    # Identity
    lens_id: str
    lens_version: str
    instrument: str
    session: str
    assessed_at: datetime

    # Evidence provenance
    evidence_state_compiled_at: datetime
    evidence_usage: EvidenceUsage

    # Readiness
    ready: bool

    # Outcome type
    outcome_type: str               # "ready_for_interpretation" | "abstain"

    # Abstention (deterministic)
    abstention_reason: str | None
    abstention_detail: str | None

    # Governance trace
    hard_veto_triggered: bool
    hard_veto_detail: str | None
    vetoes_evaluated: int
    evidence_quality_at_run: str
```

### 8.2 LensInterpretation (LLM-Derived, Structured — D-48)

Contains interpretive fields that require an LLM to derive. Honest about
provenance. Only produced when `LensAssessment.outcome_type == "ready_for_interpretation"` (D-49).

```python
@dataclass(frozen=True)
class LensInterpretation:
    """Structured LLM-derived interpretation. Validated but not deterministic.

    Answers: "What does this doctrine conclude from the evidence?"
    """
    # Link
    lens_id: str
    instrument: str
    session: str
    interpreted_at: datetime

    # Structured LLM output
    directional_view: str               # "bullish" | "bearish" | "neutral"
    confidence: str                     # "high" | "moderate" | "low"
    key_observations: tuple[str, ...]   # top 3-5 factual observations
    reasoning_summary: str              # 1-3 sentence structured summary

    # Provenance (honest about derivation)
    model_used: str
    weighted_fields_provided: tuple[str, ...]
    prompt_version: str

    # Governance
    forbidden_language_clean: bool
    fields_referenced: tuple[str, ...]
```

### 8.3 LensNarrative (Optional Prose)

```python
@dataclass(frozen=True)
class LensNarrative:
    """Optional LLM-rendered prose. Disposable.

    If narrative contradicts interpretation, interpretation wins.
    If interpretation contradicts assessment, assessment wins.
    """
    lens_id: str
    instrument: str
    session: str
    rendered_at: datetime

    reasoning_prose: str
    narrator_mode: str              # "llm" | "template" | "skipped"
    model_used: str | None
    tokens_used: int | None

    forbidden_language_clean: bool
    fields_referenced_in_prose: tuple[str, ...]
```

### 8.4 Why Three Layers, Not Two

- **Assessment** is mechanical truth that downstream systems consume programmatically
  (readiness checks, veto enforcement, governance audit).
- **Interpretation** is structured opinion that the arbiter compares across lenses
  (`directional_view` from lens A vs lens B — no prose parsing needed).
- **Narrative** is human-readable prose for the trader's UI.

If you collapse Interpretation into Narrative, the arbiter has to parse prose
to find directional views. That was AIT v1's mistake.

### 8.5 Future Option: Rule-Derived Stance

If a future version wants deterministic stance in `LensAssessment`, it needs:
numeric field weights, a defined scoring function, explicit thresholds.
This is a legitimate Phase N enhancement. The design does not pretend it exists
before the scoring engine is designed and tested.

---

## 9. Lens Readiness (Deterministic — D-41, D-54)

```python
GOVERNED_BLOCKING_PREFIXES = frozenset({
    "required_field_missing:",
    "required_extension_missing:",
    "required_extension_stale:",
    "required_extension_degraded:",
    "evidence_quality_below_minimum",
    "hard_veto_would_fire:",
})


@dataclass(frozen=True)
class LensReadiness:
    """Deterministic availability check. No lens execution. No LLM."""
    lens_id: str
    ready: bool
    blocking_reasons: tuple[str, ...]   # prefixed with specific paths


def compute_lens_readiness(
    lens: LensDefinition,
    state: SessionEvidenceState,
) -> LensReadiness:
    """Pure function. No LLM. No side effects. Deterministic.
    Collects ALL blockers — no early break (D-54)."""
    blockers: list[str] = []

    # Check ALL required fields
    for field_path in lens.required_fields:
        found, _ = resolve_field(state, field_path)
        if not found:
            blockers.append(f"required_field_missing:{field_path}")

    # Check ALL required extensions
    ext_by_type = {e.extension_type: e for e in state.extensions}
    for ext_type in lens.required_extensions:
        ext = ext_by_type.get(ext_type)
        if ext is None:
            blockers.append(f"required_extension_missing:{ext_type}")
        elif ext.freshness_state == "stale" and lens.minimum_extension_freshness == "fresh":
            blockers.append(f"required_extension_stale:{ext_type}")
        elif ext.trust_state == "degraded":
            blockers.append(f"required_extension_degraded:{ext_type}")

    # Check evidence quality
    quality_rank = {"high": 3, "moderate": 2, "low": 1, "insufficient": 0}
    actual = quality_rank.get(state.evidence_quality.overall_confidence, 0)
    required = quality_rank.get(lens.minimum_evidence_quality, 0)
    if actual < required:
        blockers.append("evidence_quality_below_minimum")

    # Check ALL hard vetoes
    for veto in lens.hard_vetoes:
        found, value = resolve_field(state, veto.field_path)
        if found and evaluate_veto(veto, value):
            blockers.append(f"hard_veto_would_fire:{veto.field_path}")

    return LensReadiness(
        lens_id=lens.lens_id,
        ready=len(blockers) == 0,
        blocking_reasons=tuple(blockers),
    )
```

---

## 10. Triage Tile Schema

### 10.1 Model

```python
@dataclass(frozen=True)
class ExtensionPresenceIndicator:
    extension_type: str
    present: bool
    freshness_state: str | None
    trust_state: str | None


@dataclass(frozen=True)
class TriageTile:
    """One instrument's summary on the Triage Board."""

    # Identity
    instrument: str
    compiled_at: datetime

    # Priority 1 — Evidence Quality (D-36)
    overall_confidence: str             # "high" | "moderate" | "low" | "insufficient"
    macro_frame_quality: str
    price_frame_quality: str
    missing_evidence: tuple[str, ...]

    # Priority 2 — Directional Lean
    macro_positioning_lean: str         # "long" | "short" | "neutral"
    macro_positioning_intensity: str    # "extreme" | "strong" | "moderate" | "weak"
    price_structure_lean: str           # "bullish" | "bearish" | "neutral" (D-40)
    macro_price_alignment: str          # "aligned" | "conflicted" | "neutral"

    # Priority 3 — Tension Count
    tension_count: int
    top_tension: str | None
    evidence_coherence: str             # "strong" | "moderate" | "weak" | "conflicted"

    # Priority 4 — Narrator Headline
    narrator_headline: str | None

    # Extension Presence
    extensions_present: tuple[ExtensionPresenceIndicator, ...]

    # Deterministic Readiness (D-41 — no lens execution)
    lens_readiness: tuple[LensReadiness, ...]
```

### 10.2 Triage Board Contract

> The Triage Board shows:
> 1. Evidence state (from SBE — already compiled)
> 2. Extension presence (from evidence packet — already attached)
> 3. Deterministic readiness per lens (static availability check)
>
> The Triage Board does NOT:
> - Execute any lens
> - Call any LLM
> - Produce any interpretation
> - Show any directional opinion from a doctrine
>
> Chamber output appears on drill-down, not on the board.

---

## 11. Candidate Lens Roster (v1)

| Lens ID | Family | Primary Evidence Zone | Required Extensions | Notes |
|---------|--------|-----------------------|---------------------|-------|
| `ict_structure` | structure | `ext.bos.data.*`, `core.price.*` | `bos` | BOS direction, chain momentum, displacement quality, key levels |
| `trendline_confluence` | structure | `ext.trendline.data.*`, `core.price.*` | `trendline` | TL break direction, HTF confluence score, line quality |
| `macro_momentum` | macro | `core.macro.*` | none | Positioning lean/intensity, momentum, divergence, regime |
| `trend_following` | trend | `core.price.*`, `core.alignment.*` | none (bos optional) | HTF bias, trend alignment, price structure lean |
| `risk_prosecutor` | risk | `core.quality.*`, `core.alignment.*` | none | Evidence gaps, tensions, coherence. Deliberately contrarian. |

---

## 12. SC-13 Reinterpretation (SBE-side)

### Proposed SC-13 (final wording)

> **SC-13:** The `SessionEvidenceState` supports a typed `EvidenceExtension`
> slot that allows specialist evidence to be attached by the caller without
> modifying the core compiled state. Each extension carries governed envelope
> metadata (identity, provenance, freshness, trust) with extension-type
> validated by shape, not family membership. Extension payloads are deep-frozen
> at construction. Duplicate extension types per packet are rejected. The
> consumer contract validates extension envelopes without inspecting payload
> internals. Core and extension evidence are addressable through a unified
> two-zone namespace (`core.*` for compiled state, `ext.<type>.meta.*` for
> extension envelope, `ext.<type>.data.*` for extension payload), enabling
> downstream consumers to declare field-level attention maps across the full
> evidence surface. This proves the compiled state is lens-ready — consumable
> by an interpretation system without requiring SBE to understand doctrinal
> semantics.

### SC-13 Acceptance Criteria

```
AC-1:  SessionEvidenceState has an `extensions` field typed
       tuple[EvidenceExtension, ...] with default empty tuple.
       Existing code that constructs SessionEvidenceState without
       extensions continues to work (backwards-compatible).

AC-2:  EvidenceExtension is a frozen dataclass with fields:
       extension_id, extension_type, producer, version,
       generated_at, data_age_minutes, freshness_state,
       trust_state, payload.

AC-3:  extension_type is validated by shape (lowercase alpha start,
       alphanumeric + underscore, max 50 chars). SBE does NOT maintain
       a governed set of extension families.

AC-4:  freshness_state validated against {"fresh", "stale", "unknown"}.
       trust_state validated against {"verified", "unverified", "degraded"}.

AC-5:  consumer_contract.py envelope validation covers AC-1 through AC-4.
       Zero engine imports. AST-verified (existing pattern).

AC-6:  consumer_contract.py does NOT validate payload structure.
       Payload is type-checked as dict or MappingProxyType only.

AC-7:  BriefingSerialiser handles extensions in all three output
       formats (dict, JSON, text). Extensions serialise with envelope
       metadata + payload. datetime→ISO, tuple→list normalisation
       applies to extension fields.

AC-8:  CLI `compile` and `briefing` commands pass through extensions
       when present. No CLI-specific extension logic.

AC-9:  At least one test fixture includes a SessionEvidenceState with
       populated extensions (at least 2 different extension_types).

AC-10: At least one test fixture includes a SessionEvidenceState with
       empty extensions (backwards compatibility).

AC-11: Extensions do not affect MacroFrame, PriceFrame, AlignmentAssessment,
       or EvidenceQuality compilation. The compilers are unchanged.

AC-12: Extensions do not affect narrator output. TemplateNarrator and
       LLMNarrator receive SessionEvidenceState with extensions but
       only read core fields. Narrator tests pass unchanged.

AC-13: consumer_contract.py extension validation rejects: empty extension_id,
       malformed extension_type, unknown freshness_state, unknown trust_state,
       missing generated_at, non-dict payload.

AC-14: Namespace resolution proof: a test demonstrates that field paths
       in the form core.*, ext.<type>.meta.*, and ext.<type>.data.*
       resolve correctly against a SessionEvidenceState with extensions.
       Uses (found, value) return with MISSING sentinel.

AC-15: Namespace resolution correctly returns (True, False) for a field
       whose value is False, (True, 0) for a field whose value is 0,
       and (False, MISSING) for a genuinely absent field. No falsey
       confusion.

AC-16: Envelope validation rejects duplicate extension_type values
       within a single SessionEvidenceState's extensions tuple.

AC-17: Extension payloads are deep-frozen at construction time.
       Mutation of payload contents after construction raises TypeError.
```

---

## 13. V1 Limitations

These are accepted design boundaries for v1, documented here to prevent
future surprise. Each may be revisited if operational experience demands it.

### L-1: Collection Traversal Boundary (from F5)

The namespace resolver returns collections as atomic values. No indexing,
filtering, or querying inside collections. Lenses post-process tuples
in evaluation code. A collection query syntax may be added later.

### L-2: Extension Freshness Granularity (from F9)

Each extension has a single `freshness_state` covering the entire payload.
Extensions mixing per-session current state with slow-changing statistical
profiles cannot express differential freshness. `freshness_state` reflects
the most recent compilation. Per-section freshness may be added later.

### L-3: Forbidden Language Superset Convention (from F10)

`LensPersona.forbidden_language` should be a superset of SBE's
`NARRATOR_FORBIDDEN_LANGUAGE` but is not enforced at registration time.
Documented convention for v1. Registration-time merge may be added later.

---

## 14. What Carries Forward from AIT v1

| Element | Verdict | Notes |
|---------|---------|-------|
| Multi-persona interpretation | **CARRY — reimagined** | Lenses with auditable attention maps |
| Arbiter / governance | **CARRY — rebuilt** | Consuming LensInterpretations across lenses |
| Triage Board concept | **CARRY — rebuilt** | Evidence state + deterministic readiness |
| Journal | **CARRY — rebuilt** | Tracking decisions against evidence packets |
| Reflect | **CARRY — rebuilt** | Patterns over interpretation history |
| Agent Ops workspace | **EVALUATE** | May monitor lens health |
| 13-agent roster | **DROP** | Replaced by 5-lens roster |
| Chart screenshot pipeline | **DROP** | Replaced by data-first evidence |
| MDO scheduler coupling | **DROP** | SBE/TDP handle freshness |
| Old /analyse endpoint | **DROP** | New endpoint consumes evidence state |
| React + TS + Tailwind stack | **CARRY** | Forward frontend stack locked |
| lightweight-charts | **CARRY** | Supplementary, not primary |

---

## 15. Open Questions

| # | Question | Impact |
|---|----------|--------|
| Q1 | Who compiles BOS/Trendline extensions? Adapter in AIT? Scripts in research repos? | Where extension compilation logic lives |
| Q2 | Synchronous or progressive lens execution? | Chamber orchestrator design |
| Q3 | LLM call pattern: one per lens? Batched? | Latency and cost |
| Q4 | What does "Analysis" page become post-chamber? | Page architecture |
| Q5 | New repo or major branch of existing AIT repo? | Repo governance |
| Q6 | Archive strategy for AIT v1 backend (559 tests)? | Migration |

---

## 16. Recommended Next Steps

1. **Amend SBE PROJECT_AIM.md** — update SC-13 wording, log as amendment
2. **Implement SC-13 in SBE** — EvidenceExtension, envelope validation,
   serialiser pass-through, namespace resolution proof, 17 ACs
3. **Create AIT v2 PROJECT_AIM.md** — north star + success criteria
4. **AIT v2 Phase 1** — LensDefinition registry, namespace resolver,
   VetoPredicate evaluator, deterministic readiness engine (no LLM)
5. **BOS/Trendline extension compilers** — produce extension payloads
6. **AIT v2 Phase 2** — LensPersona, LLM interpretation, LensInterpretation
7. **AIT v2 Phase 3** — Governance/arbitration, Triage Board
