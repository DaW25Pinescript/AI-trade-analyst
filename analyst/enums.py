"""Canonical enum/choice-set definitions for the analyst pipeline.

This module is the single source of truth for bounded choice sets used
across analyst, personas, arbiter, and explainability modules.

Values here are contract-locked — do not change without checking
downstream consumers and docs/ui/UI_CONTRACT.md.

TD-5 centralisation: created to eliminate duplicated validation sets
and helper logic that was hand-maintained in multiple modules.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Verdict values
# ---------------------------------------------------------------------------

VALID_VERDICTS: frozenset[str] = frozenset({
    "long_bias",
    "short_bias",
    "no_trade",
    "conditional",
    "no_data",
})

# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

VALID_CONFIDENCES: frozenset[str] = frozenset({
    "high",
    "moderate",
    "low",
    "none",
})

# ---------------------------------------------------------------------------
# Directional biases
# ---------------------------------------------------------------------------

VALID_DIRECTIONAL_BIASES: frozenset[str] = frozenset({
    "bullish",
    "bearish",
    "neutral",
    "none",
})

# ---------------------------------------------------------------------------
# LTF structure alignment values
# ---------------------------------------------------------------------------

VALID_LTF_ALIGNMENTS: frozenset[str] = frozenset({
    "aligned",
    "mixed",
    "conflicted",
    "unknown",
})

# ---------------------------------------------------------------------------
# Confidence ordering (used by arbiter and explainability)
# ---------------------------------------------------------------------------

CONFIDENCE_ORDER: dict[str, int] = {
    "high": 3,
    "moderate": 2,
    "low": 1,
    "none": 0,
}


def lower_confidence(a: str, b: str) -> str:
    """Return the lower of two confidence levels.

    Falls back to 0 for unknown values (defensive, matches prior
    explainability behavior).
    """
    return a if CONFIDENCE_ORDER.get(a, 0) <= CONFIDENCE_ORDER.get(b, 0) else b


# ---------------------------------------------------------------------------
# Verdict → directional bias mapping
# ---------------------------------------------------------------------------

VERDICT_TO_BIAS: dict[str, str] = {
    "long_bias": "bullish",
    "short_bias": "bearish",
    "no_trade": "none",
    "conditional": "neutral",
    "no_data": "none",
}
