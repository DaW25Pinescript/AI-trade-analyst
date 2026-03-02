"""
Reasoning Engine — aggregates MacroEvents into a MacroContext.

No ML. Pure rule-based heuristics with auditable calculations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from macro_risk_officer.core.decay_manager import DecayManager
from macro_risk_officer.core.models import AssetPressure, MacroContext, MacroEvent
from macro_risk_officer.core.sensitivity_matrix import AssetSensitivityMatrix
from macro_risk_officer.utils.explanations import build_explanation


# Surprise normalisation cap: surprises beyond this magnitude are capped
_SURPRISE_CAP = 3.0

# Tier weight amplifiers: Tier 1 events carry 3× the base weight
_TIER_WEIGHT = {1: 3.0, 2: 1.5, 3: 0.75}

# Regime classification thresholds
_REGIME_RISK_OFF_THRESHOLD = -0.25
_REGIME_RISK_ON_THRESHOLD = 0.25

# Volatility bias thresholds (based on VIX pressure + conflict score)
_VOL_EXPANDING_THRESHOLD = 0.20
_VOL_CONTRACTING_THRESHOLD = -0.20


class ReasoningEngine:
    def __init__(self) -> None:
        self.matrix = AssetSensitivityMatrix()
        self.decay = DecayManager()

    def generate_context(
        self,
        events: List[MacroEvent],
        technical_exposures: Dict[str, float] | None = None,
    ) -> MacroContext:
        """
        Aggregate events into a MacroContext.

        Args:
            events: List of MacroEvents sorted newest-first.
            technical_exposures: Optional dict of {asset: directional_exposure} from
                the analyst pipeline (e.g. {"GOLD": 1.0, "USD": -0.3} for XAUUSD long).
                Used to compute conflict_score. If None, defaults to zero exposure.
        """
        if technical_exposures is None:
            technical_exposures = {}

        weighted: defaultdict[str, float] = defaultdict(float)
        explanations: List[str] = []
        total_weight = 0.0

        for event in events:
            direction = self._surprise_direction(event)
            if direction is None:
                continue

            base = self.matrix.get_base_bias(event.category, direction)
            if not base:
                continue

            surprise_mult = self._surprise_multiplier(event)
            tier_weight = _TIER_WEIGHT.get(event.tier, 1.0)
            decay = self.decay.get_decay_factor(event)
            combined_weight = surprise_mult * tier_weight * decay

            adjusted = self.matrix.apply_surprise_multiplier(base, combined_weight)
            for asset, value in adjusted.items():
                weighted[asset] += value

            total_weight += combined_weight
            explanations.append(build_explanation(event, direction, surprise_mult))

        # Normalise asset pressures by total accumulated weight
        if total_weight > 0:
            normalised = {k: v / total_weight for k, v in weighted.items()}
        else:
            normalised = {}

        asset_pressure = AssetPressure(**{
            k: normalised.get(k, 0.0)
            for k in AssetPressure.model_fields
        })

        conflict_score = self._conflict_score(normalised, technical_exposures)

        return MacroContext(
            regime=self._derive_regime(normalised),
            vol_bias=self._derive_vol_bias(normalised, conflict_score),
            asset_pressure=asset_pressure,
            conflict_score=round(conflict_score, 3),
            confidence=self._confidence(events),
            time_horizon_days=self._time_horizon(events),
            explanation=explanations[:5],  # Cap at 5 most relevant
            active_event_ids=[e.event_id for e in events],
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _surprise_direction(self, event: MacroEvent) -> str | None:
        """Map event category + surprise sign to a direction string."""
        surprise = event.surprise
        if surprise is None:
            return None

        direction_map = {
            "monetary_policy": ("hawkish", "dovish"),
            "inflation": ("hot", "cool"),
            "employment": ("strong", "weak"),
            "growth": ("strong", "weak"),
            "geopolitical": ("escalation", "de_escalation"),
            "systemic_risk": ("stress", "relief"),
        }
        pair = direction_map.get(event.category)
        if pair is None:
            return None

        # For geopolitical/systemic, positive actual = escalation/stress
        return pair[0] if surprise > 0 else pair[1]

    def _surprise_multiplier(self, event: MacroEvent) -> float:
        """Normalise surprise magnitude into a [0.5, 2.0] multiplier."""
        surprise = event.surprise
        if surprise is None or event.forecast == 0:
            return 1.0
        try:
            magnitude = abs(surprise / event.forecast)
        except ZeroDivisionError:
            magnitude = abs(surprise)
        capped = min(magnitude, _SURPRISE_CAP)
        # Map [0, _SURPRISE_CAP] → [0.5, 2.0]
        return 0.5 + (capped / _SURPRISE_CAP) * 1.5

    def _derive_regime(self, normalised: Dict[str, float]) -> str:
        spx = normalised.get("SPX", 0.0)
        gold = normalised.get("GOLD", 0.0)
        vix = normalised.get("VIX", 0.0)
        # Simple composite: negative SPX + positive VIX/GOLD = risk-off
        composite = (spx - vix * 0.5 - gold * 0.3) / 1.8
        if composite < _REGIME_RISK_OFF_THRESHOLD:
            return "risk_off"
        if composite > _REGIME_RISK_ON_THRESHOLD:
            return "risk_on"
        return "neutral"

    def _derive_vol_bias(
        self, normalised: Dict[str, float], conflict_score: float
    ) -> str:
        vix_pressure = normalised.get("VIX", 0.0)
        composite = vix_pressure * 0.7 + abs(conflict_score) * 0.3
        if composite > _VOL_EXPANDING_THRESHOLD:
            return "expanding"
        if composite < _VOL_CONTRACTING_THRESHOLD:
            return "contracting"
        return "neutral"

    def _conflict_score(
        self,
        normalised: Dict[str, float],
        technical_exposures: Dict[str, float],
    ) -> float:
        """
        Dot product of macro asset pressure and technical exposures.
        Negative = macro headwind vs current technical bias.
        Positive = macro tailwind confirming technical bias.
        """
        if not technical_exposures:
            return 0.0
        total = sum(
            normalised.get(asset, 0.0) * exposure
            for asset, exposure in technical_exposures.items()
        )
        # Normalise by number of assets to keep in [-1, 1]
        n = len(technical_exposures)
        return max(-1.0, min(1.0, total / n))

    def _confidence(self, events: List[MacroEvent]) -> float:
        """Confidence scales with number and tier of events, capped at 0.95."""
        if not events:
            return 0.0
        score = sum(_TIER_WEIGHT.get(e.tier, 1.0) for e in events)
        # 3 Tier-1 events → score=9 → confidence≈0.9
        return round(min(0.95, score / 10.0), 2)

    def _time_horizon(self, events: List[MacroEvent]) -> int:
        """Horizon driven by highest-tier event present."""
        if any(e.tier == 1 for e in events):
            return 45
        if any(e.tier == 2 for e in events):
            return 14
        return 3
