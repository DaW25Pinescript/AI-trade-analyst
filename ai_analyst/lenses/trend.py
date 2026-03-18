"""Trend Lens v1.0 — directional bias and trend quality from OHLCV.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 4.4

Determines directional bias using EMA alignment, price position, and slope.
Provides directional context — NOT entry signals. Deterministic, no LLM.

Configuration (v1):
    timeframe:       str   e.g. "1H"
    ema_fast:        int   default 20
    ema_slow:        int   default 50
    slope_lookback:  int   default 10

Output schema — all fields always present, null where unavailable:
    timeframe, direction, strength, state
"""

import numpy as np

from .base import LensBase

# ── Field value contracts ───────────────────────────────────────────────────

EMA_ALIGNMENT_VALUES = {"bullish", "bearish", "neutral"}
PRICE_VS_EMA_VALUES = {"above", "below", "mixed"}
OVERALL_DIRECTION_VALUES = {"bullish", "bearish", "ranging"}
SLOPE_VALUES = {"positive", "negative", "flat"}
TREND_QUALITY_VALUES = {"strong", "moderate", "weak"}
PHASE_VALUES = {"continuation", "pullback", "transition"}
CONSISTENCY_VALUES = {"aligned", "conflicting"}


class TrendLens(LensBase):
    """Deterministic trend lens computing EMA alignment, slope, and phase."""

    lens_id = "trend"
    version = "v1.0"

    def _compute(self, price_data: dict, config: dict) -> dict:
        closes = np.asarray(price_data["close"], dtype=np.float64)
        timeframe = config.get("timeframe", "unknown")
        ema_fast_period = config.get("ema_fast", 20)
        ema_slow_period = config.get("ema_slow", 50)
        slope_lookback = config.get("slope_lookback", 10)

        if len(closes) < ema_slow_period + slope_lookback:
            raise ValueError(
                f"Insufficient data: need at least {ema_slow_period + slope_lookback} "
                f"bars, got {len(closes)}"
            )

        # 1. Compute EMAs
        ema_fast = self._ema(closes, ema_fast_period)
        ema_slow = self._ema(closes, ema_slow_period)

        current_close = float(closes[-1])
        current_fast = float(ema_fast[-1])
        current_slow = float(ema_slow[-1])

        # 2. EMA alignment
        ema_alignment = self._classify_alignment(current_fast, current_slow)

        # 3. Price vs EMA
        price_vs_ema = self._classify_price_position(
            current_close, current_fast, current_slow
        )

        # 4. Overall direction
        overall = self._classify_overall(ema_alignment, price_vs_ema)

        # 5. Slope of slow EMA
        slope = self._classify_slope(ema_slow, slope_lookback)

        # 6. Trend quality
        trend_quality = self._classify_quality(
            ema_slow, slope_lookback, ema_fast, ema_alignment
        )

        # 7. Phase
        phase = self._classify_phase(closes, ema_fast, ema_slow)

        # 8. Consistency
        consistency = self._classify_consistency(
            ema_alignment, price_vs_ema, slope
        )

        return {
            "timeframe": timeframe,
            "direction": {
                "ema_alignment": ema_alignment,
                "price_vs_ema": price_vs_ema,
                "overall": overall,
            },
            "strength": {
                "slope": slope,
                "trend_quality": trend_quality,
            },
            "state": {
                "phase": phase,
                "consistency": consistency,
            },
        }

    def _validate_schema(self, data: dict) -> None:
        required_top = ["timeframe", "direction", "strength", "state"]
        for key in required_top:
            if key not in data:
                raise ValueError(
                    f"TrendLens output missing required field: '{key}'"
                )

        for parent, children in [
            ("direction", ["ema_alignment", "price_vs_ema", "overall"]),
            ("strength", ["slope", "trend_quality"]),
            ("state", ["phase", "consistency"]),
        ]:
            for child in children:
                if child not in data[parent]:
                    raise ValueError(
                        f"TrendLens output missing '{parent}.{child}'"
                    )

        # Validate enum values
        alignment = data["direction"]["ema_alignment"]
        if alignment not in EMA_ALIGNMENT_VALUES:
            raise ValueError(f"Invalid ema_alignment: {alignment}")

        pvs = data["direction"]["price_vs_ema"]
        if pvs not in PRICE_VS_EMA_VALUES:
            raise ValueError(f"Invalid price_vs_ema: {pvs}")

        overall = data["direction"]["overall"]
        if overall not in OVERALL_DIRECTION_VALUES:
            raise ValueError(f"Invalid overall direction: {overall}")

        slope = data["strength"]["slope"]
        if slope not in SLOPE_VALUES:
            raise ValueError(f"Invalid slope: {slope}")

        quality = data["strength"]["trend_quality"]
        if quality not in TREND_QUALITY_VALUES:
            raise ValueError(f"Invalid trend_quality: {quality}")

        phase = data["state"]["phase"]
        if phase not in PHASE_VALUES:
            raise ValueError(f"Invalid phase: {phase}")

        consistency = data["state"]["consistency"]
        if consistency not in CONSISTENCY_VALUES:
            raise ValueError(f"Invalid consistency: {consistency}")

    # ── Private computation methods ─────────────────────────────────────────

    @staticmethod
    def _ema(data: np.ndarray, period: int) -> np.ndarray:
        """Compute exponential moving average."""
        alpha = 2.0 / (period + 1)
        ema = np.empty_like(data, dtype=np.float64)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        return ema

    @staticmethod
    def _classify_alignment(fast: float, slow: float) -> str:
        """Fast > slow = bullish, fast < slow = bearish, ~equal = neutral."""
        if slow == 0:
            return "neutral"
        pct_diff = (fast - slow) / abs(slow) * 100
        if pct_diff > 0.05:
            return "bullish"
        elif pct_diff < -0.05:
            return "bearish"
        return "neutral"

    @staticmethod
    def _classify_price_position(
        close: float, fast: float, slow: float
    ) -> str:
        """Price above both = above, below both = below, between = mixed."""
        if close > fast and close > slow:
            return "above"
        elif close < fast and close < slow:
            return "below"
        return "mixed"

    @staticmethod
    def _classify_overall(alignment: str, price_vs: str) -> str:
        """Derive overall direction from alignment + price position."""
        if alignment == "bullish" and price_vs == "above":
            return "bullish"
        elif alignment == "bearish" and price_vs == "below":
            return "bearish"
        return "ranging"

    @staticmethod
    def _classify_slope(ema_slow: np.ndarray, lookback: int) -> str:
        """Measure slow EMA slope over lookback bars."""
        if len(ema_slow) < lookback + 1:
            return "flat"
        recent = ema_slow[-1]
        past = ema_slow[-lookback - 1]
        if past == 0:
            return "flat"
        pct_change_per_bar = ((recent - past) / abs(past) * 100) / lookback
        if pct_change_per_bar > 0.01:
            return "positive"
        elif pct_change_per_bar < -0.01:
            return "negative"
        return "flat"

    @staticmethod
    def _classify_quality(
        ema_slow: np.ndarray,
        slope_lookback: int,
        ema_fast: np.ndarray,
        alignment: str,
    ) -> str:
        """Trend quality from slope magnitude + alignment consistency."""
        if len(ema_slow) < slope_lookback + 1:
            return "weak"

        recent = ema_slow[-1]
        past = ema_slow[-slope_lookback - 1]
        if past == 0:
            return "weak"
        slope_mag = abs((recent - past) / abs(past) * 100) / slope_lookback

        # Check alignment consistency over recent bars
        consistent = True
        check_bars = min(slope_lookback, len(ema_fast))
        for i in range(1, check_bars + 1):
            if alignment == "bullish" and ema_fast[-i] < ema_slow[-i]:
                consistent = False
                break
            elif alignment == "bearish" and ema_fast[-i] > ema_slow[-i]:
                consistent = False
                break

        if slope_mag > 0.03 and consistent:
            return "strong"
        elif slope_mag > 0.01:
            return "moderate"
        return "weak"

    @staticmethod
    def _classify_phase(
        closes: np.ndarray,
        ema_fast: np.ndarray,
        ema_slow: np.ndarray,
    ) -> str:
        """Determine trend phase from price/EMA relationships."""
        lookback = min(5, len(closes) - 1)
        current_close = closes[-1]

        above_both_now = current_close > ema_fast[-1] and current_close > ema_slow[-1]
        below_both_now = current_close < ema_fast[-1] and current_close < ema_slow[-1]

        # Check recent history
        above_both_recent = 0
        below_both_recent = 0
        for i in range(1, lookback + 1):
            if closes[-i] > ema_fast[-i] and closes[-i] > ema_slow[-i]:
                above_both_recent += 1
            if closes[-i] < ema_fast[-i] and closes[-i] < ema_slow[-i]:
                below_both_recent += 1

        # Continuation: price consistently on one side of both EMAs
        if above_both_now and above_both_recent >= lookback - 1:
            return "continuation"
        if below_both_now and below_both_recent >= lookback - 1:
            return "continuation"

        # Pullback: price crossed below fast but still above slow (or inverse)
        between_emas = (
            (ema_slow[-1] < current_close < ema_fast[-1])
            or (ema_fast[-1] < current_close < ema_slow[-1])
        )
        if between_emas:
            return "pullback"

        return "transition"

    @staticmethod
    def _classify_consistency(
        alignment: str, price_vs: str, slope: str
    ) -> str:
        """Check if all direction signals agree."""
        bullish_signals = (
            alignment == "bullish",
            price_vs == "above",
            slope == "positive",
        )
        bearish_signals = (
            alignment == "bearish",
            price_vs == "below",
            slope == "negative",
        )
        if all(bullish_signals) or all(bearish_signals):
            return "aligned"
        return "conflicting"
