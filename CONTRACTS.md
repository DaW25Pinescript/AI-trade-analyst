# CONTRACTS.md — Phase 3E: StructureDigest, AnalystVerdict, ReasoningBlock

## StructureDigest dataclass

`analyst/contracts.py`:

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LiquidityRef:
    type: str                  # e.g. "prior_day_high"
    price: float
    scope: str                 # "external_liquidity" | "internal_liquidity" | "unclassified"
    status: str                # "active" | "swept"

@dataclass
class StructureDigest:
    """
    Deterministic, compact summary of structure block state.
    Produced by pre_filter.py. Consumed by prompt_builder.py and analyst.py.
    Never produced by the LLM.
    """
    instrument: str
    as_of_utc: str
    structure_available: bool

    # Gate
    structure_gate: str              # "pass" | "fail" | "no_data" | "mixed"
    gate_reason: Optional[str]       # human-readable reason for gate result

    # Regime
    htf_bias: Optional[str]          # "bullish" | "bearish" | "neutral" | None
    htf_source_timeframe: Optional[str]
    last_bos: Optional[str]          # "bullish" | "bearish" | None
    last_mss: Optional[str]          # "bullish" | "bearish" | None
    bos_mss_alignment: Optional[str] # "aligned" | "conflicted" | "incomplete" | None

    # Liquidity
    nearest_liquidity_above: Optional[LiquidityRef]
    nearest_liquidity_below: Optional[LiquidityRef]
    liquidity_bias: Optional[str]    # "above_closer" | "below_closer" | "balanced" | None

    # FVG
    active_fvg_context: Optional[str]  # "discount_bullish" | "premium_bearish" | "at_fvg" | "none"
    active_fvg_count: int

    # Sweep/reclaim
    recent_sweep_signal: Optional[str] # "bullish_reclaim" | "bearish_reclaim" | "accepted_beyond" | "none"

    # Signal lists
    structure_supports: list[str] = field(default_factory=list)
    structure_conflicts: list[str] = field(default_factory=list)

    # Flags
    no_trade_flags: list[str] = field(default_factory=list)
    caution_flags: list[str] = field(default_factory=list)

    def has_hard_no_trade(self) -> bool:
        return len(self.no_trade_flags) > 0

    def to_prompt_dict(self) -> dict:
        """Compact dict for LLM prompt injection. Excludes raw packet data."""
        ...
```

---

## AnalystVerdict dataclass

```python
@dataclass
class AnalystVerdict:
    """
    Structured machine-readable verdict. Produced by LLM, parsed by analyst.py.
    Authoritative contract for downstream systems.
    """
    instrument: str
    as_of_utc: str

    verdict: str                     # "long_bias" | "short_bias" | "no_trade" | "conditional" | "no_data"
    confidence: str                  # "high" | "moderate" | "low" | "none"

    structure_gate: str              # echoed from digest
    htf_bias: Optional[str]
    ltf_structure_alignment: str     # "aligned" | "mixed" | "conflicted" | "unknown"
    active_fvg_context: Optional[str]
    recent_sweep_signal: Optional[str]

    structure_supports: list[str]
    structure_conflicts: list[str]
    no_trade_flags: list[str]
    caution_flags: list[str]

    def is_actionable(self) -> bool:
        """True if verdict is long_bias or short_bias with at least moderate confidence."""
        return (
            self.verdict in ("long_bias", "short_bias")
            and self.confidence in ("high", "moderate")
            and not self.no_trade_flags
        )
```

---

## ReasoningBlock dataclass

```python
@dataclass
class ReasoningBlock:
    """
    Human-readable explanation of how structure influenced the verdict.
    Produced by LLM alongside AnalystVerdict.
    """
    summary: str              # 2-4 sentence overall verdict explanation
    htf_context: str          # regime, BOS/MSS direction
    liquidity_context: str    # nearest levels, liquidity bias
    fvg_context: str          # active zones, discount/premium
    sweep_context: str        # sweep/reclaim signal
    verdict_rationale: str    # why verdict and confidence were assigned
```

---

## AnalystOutput — top-level container

```python
@dataclass
class AnalystOutput:
    verdict: AnalystVerdict
    reasoning: ReasoningBlock
    digest: StructureDigest    # preserved for audit/replay

    def to_dict(self) -> dict:
        ...
```

---

## Full AnalystOutput JSON

```json
{
  "verdict": {
    "instrument": "EURUSD",
    "as_of_utc": "2026-03-07T10:15:00Z",
    "verdict": "long_bias",
    "confidence": "moderate",
    "structure_gate": "pass",
    "htf_bias": "bullish",
    "ltf_structure_alignment": "mixed",
    "active_fvg_context": "discount_bullish",
    "recent_sweep_signal": "bullish_reclaim",
    "structure_supports": [
      "bullish 4h regime",
      "active discount FVG at 1.08475",
      "bullish BOS on 1h",
      "bullish reclaim of equal_lows"
    ],
    "structure_conflicts": [
      "bearish MSS on 15m against HTF bullish regime"
    ],
    "no_trade_flags": [],
    "caution_flags": ["ltf_mss_conflict"]
  },

  "reasoning": {
    "summary": "Bullish bias on EURUSD with moderate confidence. HTF 4h regime is bullish with recent bullish BOS on 1h confirming directional momentum. LTF 15m shows a bearish MSS which introduces short-term conflict but does not override HTF alignment.",
    "htf_context": "4h regime: bullish. Last BOS: bullish (1h). Last MSS: bearish (15m) — minor conflict present.",
    "liquidity_context": "Nearest above: prior_day_high at 1.08720 (external). Nearest below: equal_lows at 1.08410 (internal). Liquidity draw is toward the prior_day_high above.",
    "fvg_context": "Active bullish FVG at 1.08475–1.08620 (1h, open). Price approaching from above — discount zone in play for potential continuation.",
    "sweep_context": "Recent bullish reclaim of equal_lows. Supportive of bullish continuation narrative.",
    "verdict_rationale": "Long bias with moderate confidence. HTF gate passes. LTF MSS conflict noted as caution. No hard no-trade flags present."
  },

  "digest": {
    "instrument": "EURUSD",
    "as_of_utc": "2026-03-07T10:15:00Z",
    "structure_available": true,
    "structure_gate": "pass",
    "gate_reason": "4h regime bullish, no contradiction",
    "htf_bias": "bullish",
    "htf_source_timeframe": "4h",
    "last_bos": "bullish",
    "last_mss": "bearish",
    "bos_mss_alignment": "conflicted",
    "nearest_liquidity_above": {
      "type": "prior_day_high", "price": 1.08720,
      "scope": "external_liquidity", "status": "active"
    },
    "nearest_liquidity_below": {
      "type": "equal_lows", "price": 1.08410,
      "scope": "internal_liquidity", "status": "active"
    },
    "liquidity_bias": "above_closer",
    "active_fvg_context": "discount_bullish",
    "active_fvg_count": 2,
    "recent_sweep_signal": "bullish_reclaim",
    "structure_supports": ["bullish 4h regime", "active discount FVG at 1.08475", "bullish BOS on 1h", "bullish reclaim of equal_lows"],
    "structure_conflicts": ["bearish MSS on 15m against HTF bullish regime"],
    "no_trade_flags": [],
    "caution_flags": ["ltf_mss_conflict"]
  }
}
```

---

## LLM prompt contract

### System prompt (locked — do not deviate)

```
You are a disciplined ICT-style market analyst. You reason over structured market state only.
You do not re-derive structure from raw price data. You do not interpret charts.
Your structural knowledge comes exclusively from the structure digest provided.

Your output must always contain two parts:
1. A JSON verdict block matching the AnalystVerdict schema exactly.
2. A JSON reasoning block matching the ReasoningBlock schema exactly.

Output only valid JSON. No preamble. No markdown. No commentary outside the JSON.
```

### User prompt shape

```
Instrument: {instrument}
As of: {as_of_utc}

--- STRUCTURE DIGEST ---
{digest.to_prompt_dict() as formatted JSON}

--- MARKET CONTEXT ---
Session: {state_summary.session_context}
Volatility: {state_summary.volatility_regime}
Momentum: {state_summary.momentum_state}
ATR (14): {features.core.atr_14}
MA50 / MA200: {features.core.ma_50} / {features.core.ma_200}

--- HARD CONSTRAINTS ---
{if digest.has_hard_no_trade():}
  HARD NO-TRADE FLAGS PRESENT: {digest.no_trade_flags}
  You must set verdict = "no_trade" and confidence = "none".
  Do not override this constraint.

Produce the AnalystVerdict and ReasoningBlock JSON now.
```

### Hard constraint enforcement

If `digest.has_hard_no_trade()` is True:
- The prompt must explicitly state the no-trade constraint
- The LLM must set `verdict = "no_trade"` and `confidence = "none"`
- The post-parse validator must assert this — if the LLM overrides it, raise a `ValueError`

---

## Output file path

```
analyst/output/{instrument}_analyst_output.json
```

One file per instrument. Overwritten on each run. Preserved for audit alongside the digest.
