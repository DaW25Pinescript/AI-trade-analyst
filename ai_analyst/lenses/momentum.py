"""Momentum Lens v1.0 — price impulse and acceleration from OHLCV.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 4.5

Detects price impulse strength, acceleration/decay, and exhaustion/chop risk.
Confluence amplifier and caution signal — NOT a primary entry trigger.

Configuration (v1):
    timeframe:           str   e.g. "1H"
    roc_lookback:        int   default 10
    momentum_smoothing:  int   default 5
    signal_mode:         str   "roc" (v1 only)

Output schema — all fields always present, null where unavailable:
    timeframe, direction, strength, state, risk
"""

import numpy as np

from .base import LensBase

# ── Field value contracts ───────────────────────────────────────────────────

DIRECTION_STATE_VALUES = {"bullish", "bearish", "neutral"}
ROC_SIGN_VALUES = {"positive", "negative", "flat"}
IMPULSE_VALUES = {"strong", "moderate", "weak"}
ACCELERATION_VALUES = {"rising", "falling", "flat"}
PHASE_VALUES = {"expanding", "fading", "reversing", "flat"}
TREND_ALIGNMENT_VALUES = {"aligned", "conflicting", "unknown"}


class MomentumLens(LensBase):
    """Deterministic momentum lens computing ROC impulse, acceleration, and risk."""

    lens_id = "momentum"
    version = "v1.0"

    def _compute(self, price_data: dict, config: dict) -> dict:
        closes = np.asarray(price_data["close"], dtype=np.float64)
        timeframe = config.get("timeframe", "unknown")
        roc_lookback = config.get("roc_lookback", 10)
        smoothing = config.get("momentum_smoothing", 5)

        min_bars = roc_lookback + smoothing + 10
        if len(closes) < min_bars:
            raise ValueError(
                f"Insufficient data: need at least {min_bars} bars, got {len(closes)}"
            )

        # 1. Compute ROC series
        roc_series = self._compute_roc_series(closes, roc_lookback)

        # 2. Smooth ROC
        smoothed = self._sma(roc_series, smoothing)

        # 3. Direction state
        current_smoothed = float(smoothed[-1])
        direction_state = self._classify_direction(current_smoothed)

        # 4. ROC sign (raw)
        raw_roc = float(roc_series[-1])
        roc_sign = self._classify_roc_sign(raw_roc)

        # 5. Impulse strength
        impulse = self._classify_impulse(current_smoothed)

        # 6. Acceleration
        acceleration = self._classify_acceleration(smoothed, roc_lookback)

        # 7. Phase
        phase = self._classify_phase(
            impulse, acceleration, roc_series, roc_lookback
        )

        # 8. Trend alignment
        trend_alignment = self._classify_trend_alignment(
            roc_sign, closes, smoothing
        )

        # 9. Exhaustion
        exhaustion = self._detect_exhaustion(
            roc_series, roc_lookback, acceleration
        )

        # 10. Chop warning
        chop_warning = self._detect_chop(roc_series)

        return {
            "timeframe": timeframe,
            "direction": {
                "state": direction_state,
                "roc_sign": roc_sign,
            },
            "strength": {
                "impulse": impulse,
                "acceleration": acceleration,
            },
            "state": {
                "phase": phase,
                "trend_alignment": trend_alignment,
            },
            "risk": {
                "exhaustion": exhaustion,
                "chop_warning": chop_warning,
            },
        }

    def _validate_schema(self, data: dict) -> None:
        required_top = ["timeframe", "direction", "strength", "state", "risk"]
        for key in required_top:
            if key not in data:
                raise ValueError(
                    f"MomentumLens output missing required field: '{key}'"
                )

        for parent, children in [
            ("direction", ["state", "roc_sign"]),
            ("strength", ["impulse", "acceleration"]),
            ("state", ["phase", "trend_alignment"]),
            ("risk", ["exhaustion", "chop_warning"]),
        ]:
            for child in children:
                if child not in data[parent]:
                    raise ValueError(
                        f"MomentumLens output missing '{parent}.{child}'"
                    )

        # Validate enum values
        ds = data["direction"]["state"]
        if ds not in DIRECTION_STATE_VALUES:
            raise ValueError(f"Invalid direction.state: {ds}")

        rs = data["direction"]["roc_sign"]
        if rs not in ROC_SIGN_VALUES:
            raise ValueError(f"Invalid roc_sign: {rs}")

        imp = data["strength"]["impulse"]
        if imp not in IMPULSE_VALUES:
            raise ValueError(f"Invalid impulse: {imp}")

        acc = data["strength"]["acceleration"]
        if acc not in ACCELERATION_VALUES:
            raise ValueError(f"Invalid acceleration: {acc}")

        ph = data["state"]["phase"]
        if ph not in PHASE_VALUES:
            raise ValueError(f"Invalid phase: {ph}")

        ta = data["state"]["trend_alignment"]
        if ta not in TREND_ALIGNMENT_VALUES:
            raise ValueError(f"Invalid trend_alignment: {ta}")

        # Boolean checks
        if not isinstance(data["risk"]["exhaustion"], bool):
            raise ValueError("exhaustion must be boolean")
        if not isinstance(data["risk"]["chop_warning"], bool):
            raise ValueError("chop_warning must be boolean")

    # ── Private computation methods ─────────────────────────────────────────

    @staticmethod
    def _compute_roc_series(closes: np.ndarray, lookback: int) -> np.ndarray:
        """Compute ROC series: (close[i] - close[i-lookback]) / close[i-lookback] * 100."""
        roc = np.empty(len(closes) - lookback, dtype=np.float64)
        for i in range(lookback, len(closes)):
            past = closes[i - lookback]
            if past == 0:
                roc[i - lookback] = 0.0
            else:
                roc[i - lookback] = (closes[i] - past) / past * 100
        return roc

    @staticmethod
    def _sma(data: np.ndarray, period: int) -> np.ndarray:
        """Simple moving average."""
        if len(data) < period:
            return data.copy()
        kernel = np.ones(period) / period
        # Use valid convolution to avoid edge effects
        smoothed = np.convolve(data, kernel, mode="valid")
        return smoothed

    @staticmethod
    def _classify_direction(smoothed_roc: float) -> str:
        """Smoothed ROC > threshold = bullish, < -threshold = bearish."""
        threshold = 0.2
        if smoothed_roc > threshold:
            return "bullish"
        elif smoothed_roc < -threshold:
            return "bearish"
        return "neutral"

    @staticmethod
    def _classify_roc_sign(raw_roc: float) -> str:
        """Raw ROC positive/negative/flat."""
        threshold = 0.1
        if raw_roc > threshold:
            return "positive"
        elif raw_roc < -threshold:
            return "negative"
        return "flat"

    @staticmethod
    def _classify_impulse(smoothed_roc: float) -> str:
        """Impulse strength from smoothed ROC magnitude."""
        magnitude = abs(smoothed_roc)
        if magnitude > 1.5:
            return "strong"
        elif magnitude > 0.5:
            return "moderate"
        return "weak"

    @staticmethod
    def _classify_acceleration(
        smoothed: np.ndarray, lookback: int
    ) -> str:
        """Compare current vs past smoothed ROC."""
        compare_idx = min(lookback, len(smoothed) - 1)
        if compare_idx < 1:
            return "flat"
        current = abs(float(smoothed[-1]))
        past = abs(float(smoothed[-compare_idx]))
        diff = current - past
        threshold = 0.1
        if diff > threshold:
            return "rising"
        elif diff < -threshold:
            return "falling"
        return "flat"

    @staticmethod
    def _classify_phase(
        impulse: str,
        acceleration: str,
        roc_series: np.ndarray,
        lookback: int,
    ) -> str:
        """Determine momentum phase."""
        # Expanding: impulse strong/moderate AND acceleration rising
        if impulse in ("strong", "moderate") and acceleration == "rising":
            return "expanding"

        # Reversing: ROC sign flipped recently
        check_bars = min(lookback, len(roc_series) - 1)
        if check_bars >= 2:
            recent_sign = roc_series[-1] > 0
            past_sign = roc_series[-check_bars] > 0
            if recent_sign != past_sign:
                return "reversing"

        # Fading: impulse was stronger, now declining
        if acceleration == "falling" and impulse in ("moderate", "weak"):
            return "fading"

        # Flat: weak impulse and flat acceleration
        if impulse == "weak" and acceleration == "flat":
            return "flat"

        # Default cases
        if impulse == "strong":
            return "expanding"
        if acceleration == "falling":
            return "fading"

        return "flat"

    @staticmethod
    def _classify_trend_alignment(
        roc_sign: str, closes: np.ndarray, smoothing: int
    ) -> str:
        """Compare momentum direction to short-term price trend."""
        if len(closes) < smoothing + 1:
            return "unknown"

        short_mean = float(np.mean(closes[-smoothing:]))
        current = float(closes[-1])

        price_above_mean = current > short_mean

        if roc_sign == "positive" and price_above_mean:
            return "aligned"
        elif roc_sign == "negative" and not price_above_mean:
            return "aligned"
        elif roc_sign == "flat":
            return "unknown"
        return "conflicting"

    @staticmethod
    def _detect_exhaustion(
        roc_series: np.ndarray,
        lookback: int,
        acceleration: str,
    ) -> bool:
        """Exhaustion: ROC extreme (> 2 std) AND acceleration falling."""
        if len(roc_series) < lookback:
            return False
        window = roc_series[-lookback:]
        mean = float(np.mean(window))
        std = float(np.std(window))
        if std == 0:
            return False
        current = float(roc_series[-1])
        z_score = abs(current - mean) / std
        return z_score > 2.0 and acceleration == "falling"

    @staticmethod
    def _detect_chop(roc_series: np.ndarray, window: int = 10) -> bool:
        """Chop warning: 3+ sign changes in last N bars."""
        if len(roc_series) < window:
            return False
        recent = roc_series[-window:]
        signs = np.sign(recent)
        sign_changes = int(np.sum(np.abs(np.diff(signs)) > 0))
        return sign_changes >= 3
