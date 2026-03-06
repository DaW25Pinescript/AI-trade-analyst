"""
Reasoning Engine — aggregates MacroEvents into a MacroContext.

No ML. Pure rule-based heuristics with auditable calculations.
All tunable constants are loaded from config/thresholds.yaml and
config/weights.yaml at instantiation time (MRO-P3: no more hardcoded values).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from macro_risk_officer.config.loader import load_thresholds, load_weights
from macro_risk_officer.core.decay_manager import DecayManager
from macro_risk_officer.core.models import AssetPressure, MacroContext, MacroEvent
from macro_risk_officer.core.sensitivity_matrix import AssetSensitivityMatrix
from macro_risk_officer.utils.explanations import build_explanation


class ReasoningEngine:
    def __init__(self) -> None:
        self.matrix = AssetSensitivityMatrix()
        self.decay = DecayManager()

        thresholds = load_thresholds()
        weights = load_weights()

        # Surprise normalisation cap
        self._surprise_cap: float = thresholds["surprise"]["cap"]

        # Tier weight amplifiers
        tw = weights["tier_weights"]
        self._tier_weight: Dict[int, float] = {
            1: tw["tier_1"],
            2: tw["tier_2"],
            3: tw["tier_3"],
        }

        # Regime classification thresholds
        reg = thresholds["regime"]
        self._regime_risk_off: float = reg["risk_off_threshold"]
        self._regime_risk_on: float = reg["risk_on_threshold"]

        # Volatility bias thresholds
        vol = thresholds["volatility"]
        self._vol_expanding: float = vol["expanding_threshold"]
        self._vol_contracting: float = vol["contracting_threshold"]

        # Regime composite weights (SPX, VIX, GOLD contributions)
        rw = weights["regime_weights"]
        self._spx_w: float = rw["spx_weight"]
        self._vix_w: float = rw["vix_weight"]
        self._gold_w: float = rw["gold_weight"]
        self._regime_denom: float = self._spx_w + self._vix_w + self._gold_w

        # Vol composite weights
        vw = weights["vol_weights"]
        self._vix_press_w: float = vw["vix_pressure"]
        self._conflict_mag_w: float = vw["conflict_magnitude"]

        # Confidence scaling
        conf = weights["confidence"]
        self._conf_scale: float = conf["scale_factor"]
        self._conf_max: float = conf["max"]

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
            tier_weight = self._tier_weight.get(event.tier, 1.0)
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

        return pair[0] if surprise > 0 else pair[1]

    def _surprise_multiplier(self, event: MacroEvent) -> float:
        """Normalise surprise magnitude into a [0.5, 2.0] multiplier.

        MED-2 fix: when forecast is zero (e.g. GDELT events where actual
        already encodes signal magnitude), use abs(actual) directly instead
        of short-circuiting to 1.0.  This lets the tone-magnitude scaling
        in GdeltClient._tone_to_event propagate into the combined weight.
        """
        surprise = event.surprise
        if surprise is None:
            return 1.0
        if event.forecast == 0:
            if event.actual is None or event.actual == 0:
                return 1.0
            magnitude = abs(event.actual)
        else:
            try:
                magnitude = abs(surprise / event.forecast)
            except ZeroDivisionError:
                magnitude = abs(surprise)
        capped = min(magnitude, self._surprise_cap)
        return 0.5 + (capped / self._surprise_cap) * 1.5

    def _derive_regime(self, normalised: Dict[str, float]) -> str:
        spx = normalised.get("SPX", 0.0)
        gold = normalised.get("GOLD", 0.0)
        vix = normalised.get("VIX", 0.0)
        composite = (
            spx * self._spx_w - vix * self._vix_w - gold * self._gold_w
        ) / self._regime_denom
        if composite < self._regime_risk_off:
            return "risk_off"
        if composite > self._regime_risk_on:
            return "risk_on"
        return "neutral"

    def _derive_vol_bias(
        self, normalised: Dict[str, float], conflict_score: float
    ) -> str:
        vix_pressure = normalised.get("VIX", 0.0)
        composite = (
            vix_pressure * self._vix_press_w
            + abs(conflict_score) * self._conflict_mag_w
        )
        if composite > self._vol_expanding:
            return "expanding"
        if composite < self._vol_contracting:
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
        n = len(technical_exposures)
        return max(-1.0, min(1.0, total / n))

    def _confidence(self, events: List[MacroEvent]) -> float:
        """Confidence scales with number and tier of events, capped at conf_max."""
        if not events:
            return 0.0
        score = sum(self._tier_weight.get(e.tier, 1.0) for e in events)
        return round(min(self._conf_max, score / self._conf_scale), 2)

    def _time_horizon(self, events: List[MacroEvent]) -> int:
        """Horizon driven by highest-tier event present."""
        if any(e.tier == 1 for e in events):
            return 45
        if any(e.tier == 2 for e in events):
            return 14
        return 3
