# CONSTRAINTS.md — Phase 3E Hard Rules

## RULE 1 — LLM never receives raw structure block

The LLM prompt must never contain:
- The raw `structure` block from `MarketPacketV2`
- Raw structure JSON arrays (`swings`, `events`, `liquidity`, `imbalance`)
- Direct structure packet file contents

It receives only:
- `StructureDigest.to_prompt_dict()` — the pre-digested summary
- Selected scalar fields from `features.core` and `state_summary`

```python
# Correct
prompt = build_prompt(digest=digest, features=packet.features.core, summary=packet.state_summary)

# Wrong
prompt = build_prompt(raw_structure=packet.structure)  # never
```

---

## RULE 2 — LLM must not re-derive structure

The system prompt must explicitly state: "You do not re-derive structure from raw price data."

If the LLM produces structural claims (e.g. "I can see price broke above X") that are not present in the digest, that is a prompt failure. The system prompt is the guard.

---

## RULE 3 — Hard no-trade flags are not overridable

If `digest.has_hard_no_trade()` is True:
- The prompt must state the constraint explicitly
- The post-parse validator must assert `verdict.verdict == "no_trade"`
- The validator must assert `verdict.confidence == "none"`
- If the LLM overrides this, raise `ValueError` — do not silently accept

```python
def validate_verdict(verdict: AnalystVerdict, digest: StructureDigest) -> None:
    if digest.has_hard_no_trade():
        if verdict.verdict != "no_trade":
            raise ValueError(
                f"LLM overrode hard no-trade flag. "
                f"Flags: {digest.no_trade_flags}. Verdict: {verdict.verdict}"
            )
        if verdict.confidence != "none":
            raise ValueError("no_trade verdict must have confidence=none")
```

---

## RULE 4 — Pre-filter is deterministic and LLM-free

`pre_filter.py` must produce identical output for identical input every time. It must not:
- Make LLM calls
- Use random logic
- Have side effects

Test it independently with `pytest` — no mocking of LLM required.

---

## RULE 5 — Verdict schema is enforced post-parse

After the LLM response is parsed, validate:
- `verdict` is one of the allowed values
- `confidence` is one of the allowed values
- `structure_gate` matches digest value
- `no_trade_flags` from digest are echoed in verdict
- `structure_supports` and `structure_conflicts` are non-null lists

If any field is missing or invalid, raise `ValueError` rather than silently propagating bad output.

---

## RULE 6 — HTF gate logic is Python-only

The HTF gate computation happens entirely in `pre_filter.py`. The LLM does not compute the gate — it only receives and echoes the result.

Gate values and when each is emitted:

| Gate value | Condition |
|---|---|
| `pass` | Structure available, HTF regime has directional bias, no 4h/1h conflict |
| `fail` | Structure available AND a proposed direction exists AND HTF regime explicitly contradicts it |
| `mixed` | HTF regime is neutral, OR 4h and 1h regimes conflict with each other |
| `no_data` | `structure.available` is False, or regime block is missing/null |

**Important:** `fail` is only emitted when there is both a known HTF bias AND a proposed trade direction to contradict. In the no-direction-yet workflow (analyst forming a view from scratch), the gate cannot fail — it can only be `pass`, `mixed`, or `no_data`. `fail` becomes relevant when the analyst is evaluating a specific directional setup passed in from outside (e.g. a trade plan under review).

Gate logic:
```python
def compute_structure_gate(structure: StructureBlock) -> tuple[str, str]:
    """Returns (gate_status, gate_reason)."""
    if not structure.available:
        return "no_data", "structure block unavailable"

    regime = structure.regime
    if regime is None:
        return "no_data", "regime summary missing"

    bias = regime.get("bias", "neutral")

    if bias == "neutral":
        return "mixed", "HTF regime is neutral — no directional confirmation"

    # 4h vs 1h conflict check
    packets_4h = ...  # load 4h regime
    packets_1h = ...  # load 1h regime
    if packets_4h and packets_1h:
        if packets_4h["bias"] != packets_1h["bias"] and \
           packets_1h["bias"] != "neutral":
            return "mixed", f"4h={packets_4h['bias']} conflicts with 1h={packets_1h['bias']}"

    return "pass", f"HTF regime {bias} — no contradiction"
```

---

## RULE 7 — Output is always written to file

After every successful run, `AnalystOutput.to_dict()` must be written to:
```
analyst/output/{instrument}_analyst_output.json
```

Write atomically. Do not leave partial files on LLM API error.

---

## RULE 8 — Feed, Officer, and Structure Engine untouched

```bash
git diff --name-only HEAD | grep -E "feed/|officer/|structure/"
# Must return no output
```

The analyst layer is entirely new code in `analyst/`.

---

## RULE 9 — Single persona only in 3E

Do not build a multi-persona routing system. One analyst, one verdict, one reasoning block per run. Multi-persona is Phase 3F.

---

## RULE 10 — FVG context classification rules

```python
def classify_fvg_context(active_zones: list, current_price: float) -> str:
    """
    discount_bullish = price at or below a bullish FVG zone
    premium_bearish  = price at or above a bearish FVG zone
    at_fvg           = price inside any active zone
    none             = no active zones
    """
    if not active_zones:
        return "none"

    for zone in active_zones:
        if zone["zone_low"] <= current_price <= zone["zone_high"]:
            return "at_fvg"

    bullish_below = [z for z in active_zones
                     if z["fvg_type"] == "bullish_fvg"
                     and current_price < z["zone_low"]]
    bearish_above = [z for z in active_zones
                     if z["fvg_type"] == "bearish_fvg"
                     and current_price > z["zone_high"]]

    if bullish_below:
        return "discount_bullish"
    if bearish_above:
        return "premium_bearish"
    return "none"
```

---

## Common failure modes to avoid

| Failure | Guard |
|---|---|
| LLM invents structure not in digest | System prompt + post-parse check for digest consistency |
| Hard no-trade overridden by LLM | `validate_verdict()` raises on mismatch |
| Pre-filter non-deterministic | Pure Python, no randomness, full pytest coverage |
| Gate logic runs inside LLM | `structure_gate` in prompt is pre-computed value, not a question |
| Verdict fields missing after parse | Schema validation before returning AnalystOutput |
| Output file partially written on error | Atomic write pattern — write to temp, rename |
| structure_supports / conflicts empty lists vs None | Always initialise as `[]`, never `None` |
