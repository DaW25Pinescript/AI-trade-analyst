"""
Asset sensitivity matrix.

Maps (event_category, direction) → per-asset base bias values in [-1.0, +1.0].
Positive = bullish pressure on that asset.
Negative = bearish pressure on that asset.

Directions:
  monetary_policy : "hawkish" | "dovish"
  inflation       : "hot" | "cool"
  employment      : "strong" | "weak"
  growth          : "strong" | "weak"
  geopolitical    : "escalation" | "de_escalation"
  systemic_risk   : "stress" | "relief"
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


_MATRIX: Dict[Tuple[str, str], Dict[str, float]] = {
    # ── Monetary Policy ────────────────────────────────────────────────────
    ("monetary_policy", "hawkish"): {
        "USD": 0.85,
        "SPX": -0.70,
        "NQ": -0.80,
        "T10Y": 0.75,   # yields rise
        "GOLD": -0.65,
        "OIL": -0.30,
        "VIX": 0.40,
    },
    ("monetary_policy", "dovish"): {
        "USD": -0.80,
        "SPX": 0.75,
        "NQ": 0.80,
        "T10Y": -0.70,  # yields fall
        "GOLD": 0.70,
        "OIL": 0.25,
        "VIX": -0.35,
    },
    # ── Inflation ──────────────────────────────────────────────────────────
    ("inflation", "hot"): {
        "USD": 0.50,    # ambiguous: implies hawkish Fed but erodes real value
        "SPX": -0.75,
        "NQ": -0.80,
        "T10Y": 0.65,
        "GOLD": 0.40,   # mild support as real-yield hedge
        "OIL": 0.30,    # often a cause of inflation
        "VIX": 0.45,
    },
    ("inflation", "cool"): {
        "USD": -0.45,
        "SPX": 0.65,
        "NQ": 0.70,
        "T10Y": -0.60,
        "GOLD": -0.35,
        "OIL": -0.25,
        "VIX": -0.30,
    },
    # ── Employment ────────────────────────────────────────────────────────
    ("employment", "strong"): {
        "USD": 0.70,
        "SPX": 0.40,    # growth positive but hawkish risk offsets
        "NQ": 0.35,
        "T10Y": 0.55,
        "GOLD": -0.40,
        "OIL": 0.20,
        "VIX": -0.25,
    },
    ("employment", "weak"): {
        "USD": -0.65,
        "SPX": -0.50,
        "NQ": -0.55,
        "T10Y": -0.45,
        "GOLD": 0.35,
        "OIL": -0.30,
        "VIX": 0.50,
    },
    # ── Growth ────────────────────────────────────────────────────────────
    ("growth", "strong"): {
        "USD": 0.55,
        "SPX": 0.70,
        "NQ": 0.65,
        "T10Y": 0.40,
        "GOLD": -0.30,
        "OIL": 0.45,
        "VIX": -0.40,
    },
    ("growth", "weak"): {
        "USD": -0.40,
        "SPX": -0.65,
        "NQ": -0.70,
        "T10Y": -0.35,
        "GOLD": 0.50,
        "OIL": -0.40,
        "VIX": 0.60,
    },
    # ── Geopolitical ──────────────────────────────────────────────────────
    ("geopolitical", "escalation"): {
        "USD": 0.60,    # safe haven
        "SPX": -0.55,
        "NQ": -0.60,
        "T10Y": -0.30,  # flight to bonds (yields fall)
        "GOLD": 0.80,
        "OIL": 0.65,
        "VIX": 0.75,
    },
    ("geopolitical", "de_escalation"): {
        "USD": -0.35,
        "SPX": 0.50,
        "NQ": 0.55,
        "T10Y": 0.20,
        "GOLD": -0.50,
        "OIL": -0.40,
        "VIX": -0.55,
    },
    # ── Systemic Risk ─────────────────────────────────────────────────────
    ("systemic_risk", "stress"): {
        "USD": 0.75,    # dollar wrecking ball
        "SPX": -0.90,
        "NQ": -0.90,
        "T10Y": -0.50,  # flight to treasuries
        "GOLD": 0.60,
        "OIL": -0.55,
        "VIX": 0.95,
    },
    ("systemic_risk", "relief"): {
        "USD": -0.45,
        "SPX": 0.80,
        "NQ": 0.80,
        "T10Y": 0.30,
        "GOLD": -0.40,
        "OIL": 0.35,
        "VIX": -0.80,
    },
}


class AssetSensitivityMatrix:
    def get_base_bias(self, category: str, direction: str) -> Dict[str, float]:
        """Return base asset biases for a given event category + direction."""
        return dict(_MATRIX.get((category, direction), {}))

    def apply_surprise_multiplier(
        self, base: Dict[str, float], factor: float
    ) -> Dict[str, float]:
        """Scale base biases by a surprise magnitude factor."""
        return {k: v * factor for k, v in base.items()}

    def supported_directions(self, category: str) -> list[str]:
        return [d for (c, d) in _MATRIX if c == category]

    @staticmethod
    def all_categories() -> list[str]:
        seen: list[str] = []
        for c, _ in _MATRIX:
            if c not in seen:
                seen.append(c)
        return seen
