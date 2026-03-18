"""Structure Lens v1.0 — market structure analysis from OHLCV.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 4.3

Detects and describes market structure: key levels, swing context,
breakout/rejection state. Deterministic — no LLM, no interpretation.

Configuration (v1):
    timeframe:         str   e.g. "1H"
    lookback_bars:     int   50–200, default 100
    swing_sensitivity: str   low | medium | high
    level_method:      str   "pivot" (v1 only)
    breakout_rule:     str   "close" (v1 only)

Output schema — all fields always present, null where unavailable:
    timeframe, levels, distance, swings, trend, breakout, rejection
"""

import numpy as np

from .base import LensBase

# ── Field value contracts ───────────────────────────────────────────────────

TREND_LOCAL_DIRECTION_VALUES = {"bullish", "bearish", "ranging"}
STRUCTURE_STATE_VALUES = {"HH_HL", "LH_LL", "mixed"}
BREAKOUT_STATUS_VALUES = {"none", "breakout_up", "breakout_down", "holding", "failed"}
LEVEL_BROKEN_VALUES = {"support", "resistance", None}

# ── Swing sensitivity → pivot window mapping ────────────────────────────────

_SENSITIVITY_WINDOW = {"low": 3, "medium": 5, "high": 8}


class StructureLens(LensBase):
    """Deterministic structure lens computing S/R, swings, trend, breakout."""

    lens_id = "structure"
    version = "v1.0"

    def _compute(self, price_data: dict, config: dict) -> dict:
        closes = np.asarray(price_data["close"], dtype=np.float64)
        highs = np.asarray(price_data["high"], dtype=np.float64)
        lows = np.asarray(price_data["low"], dtype=np.float64)

        lookback = config.get("lookback_bars", 100)
        sensitivity = config.get("swing_sensitivity", "medium")
        timeframe = config.get("timeframe", "unknown")

        if len(closes) == 0:
            raise ValueError("Empty price data — cannot compute structure")

        # Use only the lookback window
        closes = closes[-lookback:]
        highs = highs[-lookback:]
        lows = lows[-lookback:]
        current_price = float(closes[-1])

        # 1. Detect swing highs and lows (pivot-based)
        swing_highs, swing_lows = self._detect_swings(highs, lows, sensitivity)

        # 2. Compute support and resistance from swing levels
        support = self._compute_support(current_price, swing_lows)
        resistance = self._compute_resistance(current_price, swing_highs)

        # 3. Compute distances (as % of current price)
        dist_to_support = (
            round((current_price - support) / current_price * 100, 4)
            if support is not None
            else None
        )
        dist_to_resistance = (
            round((resistance - current_price) / current_price * 100, 4)
            if resistance is not None
            else None
        )

        # 4. Classify structure state
        local_direction, structure_state = self._classify_structure(
            swing_highs, swing_lows
        )

        # 5. Detect breakout
        breakout_status, level_broken = self._detect_breakout(
            current_price, support, resistance, closes,
            config.get("breakout_rule", "close"),
        )

        # 6. Detect rejection
        at_support = self._is_rejecting_at(
            current_price, support, lows, inverted=False,
        )
        at_resistance = self._is_rejecting_at(
            current_price, resistance, highs, inverted=True,
        )

        return {
            "timeframe": timeframe,
            "levels": {
                "support": round(float(support), 5) if support is not None else None,
                "resistance": round(float(resistance), 5) if resistance is not None else None,
            },
            "distance": {
                "to_support": dist_to_support,
                "to_resistance": dist_to_resistance,
            },
            "swings": {
                "recent_high": (
                    round(float(swing_highs[-1]), 5) if len(swing_highs) > 0 else None
                ),
                "recent_low": (
                    round(float(swing_lows[-1]), 5) if len(swing_lows) > 0 else None
                ),
            },
            "trend": {
                "local_direction": local_direction,
                "structure_state": structure_state,
            },
            "breakout": {
                "status": breakout_status,
                "level_broken": level_broken,
            },
            "rejection": {
                "at_support": at_support,
                "at_resistance": at_resistance,
            },
        }

    def _validate_schema(self, data: dict) -> None:
        required_top = [
            "timeframe", "levels", "distance", "swings",
            "trend", "breakout", "rejection",
        ]
        for key in required_top:
            if key not in data:
                raise ValueError(
                    f"StructureLens output missing required field: '{key}'"
                )

        # Validate nested required keys exist
        for parent, children in [
            ("levels", ["support", "resistance"]),
            ("distance", ["to_support", "to_resistance"]),
            ("swings", ["recent_high", "recent_low"]),
            ("trend", ["local_direction", "structure_state"]),
            ("breakout", ["status", "level_broken"]),
            ("rejection", ["at_support", "at_resistance"]),
        ]:
            for child in children:
                if child not in data[parent]:
                    raise ValueError(
                        f"StructureLens output missing '{parent}.{child}'"
                    )

        # Validate enum values
        direction = data["trend"]["local_direction"]
        if direction not in TREND_LOCAL_DIRECTION_VALUES:
            raise ValueError(f"Invalid local_direction: {direction}")

        state = data["trend"]["structure_state"]
        if state not in STRUCTURE_STATE_VALUES:
            raise ValueError(f"Invalid structure_state: {state}")

        status = data["breakout"]["status"]
        if status not in BREAKOUT_STATUS_VALUES:
            raise ValueError(f"Invalid breakout status: {status}")

        broken = data["breakout"]["level_broken"]
        if broken not in LEVEL_BROKEN_VALUES:
            raise ValueError(f"Invalid level_broken: {broken}")

    # ── Private computation methods ─────────────────────────────────────────

    def _detect_swings(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        sensitivity: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Pivot-based swing detection with configurable sensitivity window."""
        window = _SENSITIVITY_WINDOW.get(sensitivity, 5)
        swing_highs: list[float] = []
        swing_lows: list[float] = []

        for i in range(window, len(highs) - window):
            local_highs = highs[i - window : i + window + 1]
            if highs[i] == np.max(local_highs):
                swing_highs.append(float(highs[i]))

            local_lows = lows[i - window : i + window + 1]
            if lows[i] == np.min(local_lows):
                swing_lows.append(float(lows[i]))

        return np.array(swing_highs), np.array(swing_lows)

    def _compute_support(
        self, current_price: float, swing_lows: np.ndarray
    ) -> float | None:
        """Nearest swing low below the current price."""
        candidates = [s for s in swing_lows if s < current_price]
        return float(max(candidates)) if candidates else None

    def _compute_resistance(
        self, current_price: float, swing_highs: np.ndarray
    ) -> float | None:
        """Nearest swing high above the current price."""
        candidates = [s for s in swing_highs if s > current_price]
        return float(min(candidates)) if candidates else None

    def _classify_structure(
        self,
        swing_highs: np.ndarray,
        swing_lows: np.ndarray,
    ) -> tuple[str, str]:
        """Classify as HH_HL (bullish), LH_LL (bearish), or mixed."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "ranging", "mixed"

        hh = swing_highs[-1] > swing_highs[-2]
        hl = swing_lows[-1] > swing_lows[-2]
        lh = swing_highs[-1] < swing_highs[-2]
        ll = swing_lows[-1] < swing_lows[-2]

        if hh and hl:
            return "bullish", "HH_HL"
        elif lh and ll:
            return "bearish", "LH_LL"
        else:
            return "ranging", "mixed"

    def _detect_breakout(
        self,
        price: float,
        support: float | None,
        resistance: float | None,
        closes: np.ndarray,
        rule: str,
    ) -> tuple[str, str | None]:
        """Detect breakout above resistance or below support."""
        if len(closes) < 2:
            return "none", None

        prev_close = float(closes[-2])

        # Breakout above resistance
        if resistance is not None and price > resistance:
            if rule == "close" and float(closes[-1]) > resistance:
                return "breakout_up", "resistance"
            return "holding", "resistance"

        # Breakout below support
        if support is not None and price < support:
            if rule == "close" and float(closes[-1]) < support:
                return "breakout_down", "support"
            return "failed", "support"

        # Just crossed above resistance on this bar
        if resistance is not None and prev_close < resistance <= float(closes[-1]):
            return "holding", "resistance"

        return "none", None

    def _is_rejecting_at(
        self,
        price: float,
        level: float | None,
        wicks: np.ndarray,
        inverted: bool = False,
        tolerance_pct: float = 0.3,
    ) -> bool:
        """Detect price rejection at a key level via wick analysis."""
        if level is None or level == 0:
            return False
        if len(wicks) == 0:
            return False

        proximity = abs(price - level) / level * 100
        if proximity > tolerance_pct:
            return False

        if inverted:
            return bool(float(wicks[-1]) > level)
        return bool(float(wicks[-1]) < level)
