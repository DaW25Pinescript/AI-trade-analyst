"""AutoTune Structure Lens Shim — numeric pivot_window injection.

Outcome A: Subclass override of _detect_swings() to accept a numeric
pivot_window value directly, bypassing the swing_sensitivity enum mapping.

The production StructureLens maps swing_sensitivity ("low"/"medium"/"high")
to pivot window integers (3/5/8) inside _detect_swings(). This shim
overrides that method to use a numeric value from config when available,
enabling continuous pivot_window search in AutoTune.

No monkeypatching. No production code edits. Pure subclass override.
"""

import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_analyst.lenses.structure import StructureLens, _SENSITIVITY_WINDOW


class AutoTuneStructureLens(StructureLens):
    """StructureLens with numeric pivot_window injection.

    If config contains '_pivot_window_override' (int), uses that value
    directly as the pivot detection window. Otherwise falls back to the
    production enum mapping.
    """

    def _compute(self, price_data: dict, config: dict) -> dict:
        """Override to inject numeric pivot_window into swing detection."""
        # Store the override so _detect_swings can access it
        self._pivot_window_override = config.get("_pivot_window_override")
        return super()._compute(price_data, config)

    def _detect_swings(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        sensitivity: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Pivot-based swing detection with numeric window override.

        If _pivot_window_override is set (from config), uses that value
        directly. Otherwise delegates to parent's enum-based mapping.
        """
        override = getattr(self, "_pivot_window_override", None)
        if override is not None and isinstance(override, int):
            window = override
        else:
            window = _SENSITIVITY_WINDOW.get(sensitivity, 5)

        swing_highs: list[float] = []
        swing_lows: list[float] = []

        for i in range(window, len(highs) - window):
            local_highs = highs[i - window: i + window + 1]
            if highs[i] == np.max(local_highs):
                swing_highs.append(float(highs[i]))

            local_lows = lows[i - window: i + window + 1]
            if lows[i] == np.min(local_lows):
                swing_lows.append(float(lows[i]))

        return np.array(swing_highs), np.array(swing_lows)
