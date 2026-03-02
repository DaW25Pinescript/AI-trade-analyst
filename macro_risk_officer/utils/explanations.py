"""Human-readable explanation builder for macro events."""

from __future__ import annotations

from macro_risk_officer.core.models import MacroEvent

_DIRECTION_LABELS = {
    ("monetary_policy", "hawkish"): "hawkish surprise",
    ("monetary_policy", "dovish"): "dovish surprise",
    ("inflation", "hot"): "hotter-than-expected inflation",
    ("inflation", "cool"): "cooler-than-expected inflation",
    ("employment", "strong"): "stronger-than-expected employment",
    ("employment", "weak"): "weaker-than-expected employment",
    ("growth", "strong"): "stronger-than-expected growth",
    ("growth", "weak"): "weaker-than-expected growth",
    ("geopolitical", "escalation"): "geopolitical escalation",
    ("geopolitical", "de_escalation"): "geopolitical de-escalation",
    ("systemic_risk", "stress"): "systemic stress",
    ("systemic_risk", "relief"): "systemic risk relief",
}

_ASSET_EFFECTS = {
    ("monetary_policy", "hawkish"): "tighter liquidity → USD supported, equities pressured",
    ("monetary_policy", "dovish"): "looser liquidity → USD under pressure, equities bid",
    ("inflation", "hot"): "real yield uncertainty → equities risk-off, bonds sold",
    ("inflation", "cool"): "disinflation signal → rate cut hopes, equities bid",
    ("employment", "strong"): "Fed hawkish path reinforced → yields up, USD supported",
    ("employment", "weak"): "recession risk rising → equities lower, gold bid",
    ("growth", "strong"): "risk-on tone → equities and oil bid",
    ("growth", "weak"): "demand slowdown → risk-off, safe havens bid",
    ("geopolitical", "escalation"): "flight to safety → gold and USD bid, equities lower",
    ("geopolitical", "de_escalation"): "risk appetite returns → equities bid, gold offered",
    ("systemic_risk", "stress"): "systemic flight to safety → VIX spike, dollar wrecking ball",
    ("systemic_risk", "relief"): "risk-on recovery → equities rally, volatility collapses",
}


def build_explanation(
    event: MacroEvent, direction: str, surprise_multiplier: float
) -> str:
    label = _DIRECTION_LABELS.get((event.category, direction), direction)
    effect = _ASSET_EFFECTS.get((event.category, direction), "")
    tier_label = f"Tier-{event.tier}"
    surprise_str = ""
    if event.surprise is not None:
        surprise_str = f" (surprise: {event.surprise:+.3g})"

    parts = [f"{tier_label} {label}{surprise_str}"]
    if effect:
        parts.append(f"→ {effect}")
    if surprise_multiplier > 1.5:
        parts.append(f"[amplified ×{surprise_multiplier:.1f}]")

    return " ".join(parts)
