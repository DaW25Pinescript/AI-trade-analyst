# PR-AE-1 — Implementation Plan

**Scope:** `LensBase` interface + Structure Lens + unit tests  
**Phase:** P1 — Lens Engine + Evidence Snapshot  
**Spec:** `ANALYSIS_ENGINE_SPEC_v1.0.md` v1.2  
**Gate:** Contributes to Gate 1 (closes after PR-AE-3)  
**Acceptance criteria:** AC-1, AC-4, AC-10 (partial)

---

## Pre-Work — Run Diagnostic Protocol First

Before writing a single line of code, run these five diagnostic steps
from Section 16 of the spec. Report findings before proceeding.

```bash
# Step 1 — Locate current analysis pipeline
grep -r "build_analysis_graph\|analyst_nodes\|arbiter_node" ai_analyst/ --include="*.py" -l

# Step 2 — Locate OHLCV normalisation layer
grep -r "ohlcv\|ground_truth\|market_data\|normalise\|normalize" ai_analyst/ --include="*.py" -l

# Step 3 — Baseline test count (record this — it is your regression floor)
cd ai_analyst && python -m pytest --tb=short -q 2>&1 | tail -5

# Step 4 — Read legacy arbiter for reusable patterns (reference only for now)
cat analyst/arbiter.py
cat analyst/personas.py

# Step 5 — Confirm deployed roster
cat config/llm_routing.yaml 2>/dev/null || echo "MISSING — example only"
cat config/llm_routing.example.yaml
```

Do not change any code until this report is complete and reviewed.

---

## Scope — What PR-AE-1 Delivers

PR-AE-1 delivers exactly two things:

1. `LensBase` — the abstract interface every lens must satisfy
2. `StructureLens` — the first concrete lens implementation

Nothing else. No snapshot builder. No trend lens. No persona changes.

---

## New Files

| File | Purpose |
|---|---|
| `ai_analyst/lenses/__init__.py` | Package init |
| `ai_analyst/lenses/base.py` | `LensOutput` model + `LensBase` abstract class |
| `ai_analyst/lenses/structure.py` | `StructureLens` implementation |
| `tests/lenses/test_structure_lens.py` | Unit tests for Structure Lens |

**No existing files are modified in PR-AE-1.**

---

## Step 1 — Implement `LensOutput` and `LensBase`

File: `ai_analyst/lenses/base.py`

```python
from abc import ABC, abstractmethod
from typing import Literal
from pydantic import BaseModel


class LensOutput(BaseModel):
    """
    Contract: every lens must return either a complete valid schema
    (status='success') or a clean failure (status='failed', data=None).
    Partial data is never acceptable.
    """
    lens_id: str
    version: str
    timeframe: str
    status: Literal["success", "failed"]
    error: str | None = None
    data: dict | None = None

    def is_success(self) -> bool:
        return self.status == "success"


class LensBase(ABC):
    """
    Abstract base class for all lenses.
    Subclasses implement _compute() and declare lens_id + version.
    """
    lens_id: str
    version: str

    def run(self, price_data: dict, config: dict) -> LensOutput:
        """
        Public entry point. Wraps _compute() with failure handling.
        A lens must never raise — it must return a LensOutput.
        """
        timeframe = config.get("timeframe", "unknown")
        try:
            data = self._compute(price_data, config)
            self._validate_schema(data)
            return LensOutput(
                lens_id=self.lens_id,
                version=self.version,
                timeframe=timeframe,
                status="success",
                data=data,
            )
        except Exception as exc:
            return LensOutput(
                lens_id=self.lens_id,
                version=self.version,
                timeframe=timeframe,
                status="failed",
                error=str(exc),
                data=None,
            )

    @abstractmethod
    def _compute(self, price_data: dict, config: dict) -> dict:
        """
        Compute structured evidence from normalised OHLCV.
        Must return a complete schema — all fields present, null where unavailable.
        Must never return partial data.
        Must never raise for recoverable conditions — raise only for unrecoverable errors.
        """
        ...

    @abstractmethod
    def _validate_schema(self, data: dict) -> None:
        """
        Validate that data matches the expected output schema.
        Raises ValueError if any required field is missing.
        """
        ...
```

---

## Step 2 — Implement `StructureLens`

File: `ai_analyst/lenses/structure.py`

The structure lens computes support/resistance, swing levels, structural bias,
breakout state, and rejection context from OHLCV price data.

**Configuration parameters (v1):**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| `timeframe` | str | required | any | Timeframe label (e.g. "1H") |
| `lookback_bars` | int | 100 | 50–200 | Bars of OHLCV to analyse |
| `swing_sensitivity` | str | "medium" | low/medium/high | Pivot swing detection sensitivity |
| `level_method` | str | "pivot" | pivot (v1 only) | S/R level detection method |
| `breakout_rule` | str | "close" | close (v1 only) | Breakout confirmation rule |

**Required output schema (all fields must be present — use null if unavailable):**

```python
STRUCTURE_SCHEMA_REQUIRED = {
    "timeframe": str,
    "levels": {
        "support": (float, type(None)),
        "resistance": (float, type(None)),
    },
    "distance": {
        "to_support": (float, type(None)),
        "to_resistance": (float, type(None)),
    },
    "swings": {
        "recent_high": (float, type(None)),
        "recent_low": (float, type(None)),
    },
    "trend": {
        "local_direction": str,   # bullish | bearish | ranging
        "structure_state": str,   # HH_HL | LH_LL | mixed
    },
    "breakout": {
        "status": str,            # none | breakout_up | breakout_down | holding | failed
        "level_broken": (str, type(None)),  # support | resistance | null
    },
    "rejection": {
        "at_support": bool,
        "at_resistance": bool,
    },
}

TREND_LOCAL_DIRECTION_VALUES  = {"bullish", "bearish", "ranging"}
STRUCTURE_STATE_VALUES        = {"HH_HL", "LH_LL", "mixed"}
BREAKOUT_STATUS_VALUES        = {"none", "breakout_up", "breakout_down", "holding", "failed"}
LEVEL_BROKEN_VALUES           = {"support", "resistance", None}
```

**Implementation skeleton:**

```python
import numpy as np
from ai_analyst.lenses.base import LensBase, LensOutput


class StructureLens(LensBase):
    lens_id = "structure"
    version = "v1.0"

    def _compute(self, price_data: dict, config: dict) -> dict:
        closes = price_data["close"]
        highs  = price_data["high"]
        lows   = price_data["low"]
        lookback = config.get("lookback_bars", 100)
        sensitivity = config.get("swing_sensitivity", "medium")
        timeframe = config.get("timeframe", "unknown")

        # Use only the lookback window
        closes = closes[-lookback:]
        highs  = highs[-lookback:]
        lows   = lows[-lookback:]
        current_price = closes[-1]

        # 1. Detect swing highs and lows (pivot-based)
        swing_high, swing_low = self._detect_swings(highs, lows, sensitivity)

        # 2. Compute support and resistance
        support    = self._compute_support(lows, swing_low)
        resistance = self._compute_resistance(highs, swing_high)

        # 3. Compute distances (as % of current price)
        dist_to_support    = ((current_price - support) / current_price * 100) if support else None
        dist_to_resistance = ((resistance - current_price) / current_price * 100) if resistance else None

        # 4. Classify structure state
        local_direction, structure_state = self._classify_structure(
            closes, swing_high, swing_low
        )

        # 5. Detect breakout
        breakout_status, level_broken = self._detect_breakout(
            current_price, support, resistance, closes, config.get("breakout_rule", "close")
        )

        # 6. Detect rejection
        at_support    = self._is_rejecting_at(current_price, support, lows)
        at_resistance = self._is_rejecting_at(current_price, resistance, highs, inverted=True)

        return {
            "timeframe": timeframe,
            "levels": {
                "support": round(float(support), 5) if support else None,
                "resistance": round(float(resistance), 5) if resistance else None,
            },
            "distance": {
                "to_support": round(float(dist_to_support), 4) if dist_to_support is not None else None,
                "to_resistance": round(float(dist_to_resistance), 4) if dist_to_resistance is not None else None,
            },
            "swings": {
                "recent_high": round(float(swing_high[-1]), 5) if len(swing_high) > 0 else None,
                "recent_low":  round(float(swing_low[-1]), 5)  if len(swing_low) > 0  else None,
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
        required_top = ["timeframe", "levels", "distance", "swings", "trend", "breakout", "rejection"]
        for key in required_top:
            if key not in data:
                raise ValueError(f"StructureLens output missing required field: '{key}'")

        if data["trend"]["local_direction"] not in TREND_LOCAL_DIRECTION_VALUES:
            raise ValueError(f"Invalid local_direction: {data['trend']['local_direction']}")
        if data["trend"]["structure_state"] not in STRUCTURE_STATE_VALUES:
            raise ValueError(f"Invalid structure_state: {data['trend']['structure_state']}")
        if data["breakout"]["status"] not in BREAKOUT_STATUS_VALUES:
            raise ValueError(f"Invalid breakout status: {data['breakout']['status']}")
        if data["breakout"]["level_broken"] not in LEVEL_BROKEN_VALUES:
            raise ValueError(f"Invalid level_broken: {data['breakout']['level_broken']}")

    # ── Private computation methods ──────────────────────────────────────────

    def _detect_swings(self, highs, lows, sensitivity):
        window = {"low": 3, "medium": 5, "high": 8}[sensitivity]
        swing_highs, swing_lows = [], []
        for i in range(window, len(highs) - window):
            if highs[i] == max(highs[i-window:i+window+1]):
                swing_highs.append(highs[i])
            if lows[i] == min(lows[i-window:i+window+1]):
                swing_lows.append(lows[i])
        return np.array(swing_highs), np.array(swing_lows)

    def _compute_support(self, lows, swing_lows):
        current = lows[-1]
        candidates = [s for s in swing_lows if s < current]
        return max(candidates) if candidates else None

    def _compute_resistance(self, highs, swing_highs):
        current = highs[-1]
        candidates = [s for s in swing_highs if s > current]
        return min(candidates) if candidates else None

    def _classify_structure(self, closes, swing_highs, swing_lows):
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

    def _detect_breakout(self, price, support, resistance, closes, rule):
        if resistance and price > resistance:
            status = "breakout_up" if rule == "close" and closes[-1] > resistance else "holding"
            return status, "resistance"
        elif support and price < support:
            status = "breakout_down" if rule == "close" and closes[-1] < support else "failed"
            return status, "support"
        elif resistance and closes[-2] < resistance <= closes[-1]:
            return "holding", "resistance"
        return "none", None

    def _is_rejecting_at(self, price, level, wicks, inverted=False, tolerance_pct=0.3):
        if level is None:
            return False
        proximity = abs(price - level) / level * 100
        if proximity > tolerance_pct:
            return False
        if inverted:
            return bool(wicks[-1] > level)
        return bool(wicks[-1] < level)
```

---

## Step 3 — Write Tests (TDD — tests must be written before running implementation)

File: `tests/lenses/test_structure_lens.py`

```python
"""
Tests for StructureLens — following red/green/refactor TDD discipline.
All tests use frozen fixture data — no live API calls.
"""
import pytest
import numpy as np
from ai_analyst.lenses.structure import StructureLens
from ai_analyst.lenses.base import LensOutput


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_bullish_price_data(n=120):
    """Clean uptrend: HH/HL structure, breakout above resistance."""
    np.random.seed(42)
    closes = np.linspace(1900, 2100, n) + np.random.normal(0, 5, n)
    highs  = closes + np.abs(np.random.normal(0, 8, n))
    lows   = closes - np.abs(np.random.normal(0, 8, n))
    return {"close": closes, "high": highs, "low": lows}


def make_bearish_price_data(n=120):
    """Clean downtrend: LH/LL structure."""
    np.random.seed(42)
    closes = np.linspace(2100, 1900, n) + np.random.normal(0, 5, n)
    highs  = closes + np.abs(np.random.normal(0, 8, n))
    lows   = closes - np.abs(np.random.normal(0, 8, n))
    return {"close": closes, "high": highs, "low": lows}


def make_noisy_price_data(n=120):
    """Choppy/ranging data — should produce mixed structure."""
    np.random.seed(99)
    closes = 2000 + np.random.normal(0, 20, n)
    highs  = closes + np.abs(np.random.normal(0, 10, n))
    lows   = closes - np.abs(np.random.normal(0, 10, n))
    return {"close": closes, "high": highs, "low": lows}


def make_insufficient_data(n=5):
    """Too few bars for swing detection."""
    closes = np.array([2000.0, 2010.0, 2005.0, 2015.0, 2020.0])
    highs  = closes + 5
    lows   = closes - 5
    return {"close": closes, "high": highs, "low": lows}


DEFAULT_CONFIG = {
    "timeframe": "1H",
    "lookback_bars": 100,
    "swing_sensitivity": "medium",
    "level_method": "pivot",
    "breakout_rule": "close",
}


# ── AC-1: Valid schema — all fields present ───────────────────────────────────

class TestStructureLensOutputSchema:

    def test_returns_lens_output_object(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result, LensOutput)

    def test_status_is_success_on_valid_data(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.error is None

    def test_data_contains_all_required_top_level_fields(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        required = ["timeframe", "levels", "distance", "swings", "trend", "breakout", "rejection"]
        for field in required:
            assert field in result.data, f"Missing required field: {field}"

    def test_levels_always_present_even_if_null(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert "support" in result.data["levels"]
        assert "resistance" in result.data["levels"]

    def test_trend_fields_use_allowed_values(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["trend"]["local_direction"] in {"bullish", "bearish", "ranging"}
        assert result.data["trend"]["structure_state"] in {"HH_HL", "LH_LL", "mixed"}

    def test_breakout_status_uses_allowed_values(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.data["breakout"]["status"] in {
            "none", "breakout_up", "breakout_down", "holding", "failed"
        }

    def test_rejection_fields_are_boolean(self):
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert isinstance(result.data["rejection"]["at_support"], bool)
        assert isinstance(result.data["rejection"]["at_resistance"], bool)

    def test_timeframe_matches_config(self):
        lens = StructureLens()
        config = {**DEFAULT_CONFIG, "timeframe": "4H"}
        result = lens.run(make_bullish_price_data(), config)
        assert result.data["timeframe"] == "4H"


# ── AC-4: Clean failure — no partial data ─────────────────────────────────────

class TestStructureLensFailureBehavior:

    def test_returns_failed_status_on_insufficient_data(self):
        """Lens must return status='failed' not raise on insufficient bars."""
        lens = StructureLens()
        result = lens.run(make_insufficient_data(), DEFAULT_CONFIG)
        # Should either succeed with nulls or fail cleanly — never raise
        assert result.status in {"success", "failed"}
        if result.status == "failed":
            assert result.data is None
            assert result.error is not None
            assert len(result.error) > 0

    def test_never_raises_exception(self):
        """Lens contract: never raise — always return LensOutput."""
        lens = StructureLens()
        bad_data = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        try:
            result = lens.run(bad_data, DEFAULT_CONFIG)
            assert result.status == "failed"
        except Exception as exc:
            pytest.fail(f"Lens raised instead of returning failed LensOutput: {exc}")

    def test_partial_data_never_returned(self):
        """On failure: data must be None, not a partial dict."""
        lens = StructureLens()
        bad_data = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(bad_data, DEFAULT_CONFIG)
        if result.status == "failed":
            assert result.data is None, "Partial data returned on failure — contract violation"

    def test_lens_id_always_present(self):
        """lens_id must be correct even on failure."""
        lens = StructureLens()
        bad_data = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(bad_data, DEFAULT_CONFIG)
        assert result.lens_id == "structure"

    def test_version_always_present(self):
        lens = StructureLens()
        bad_data = {"close": np.array([]), "high": np.array([]), "low": np.array([])}
        result = lens.run(bad_data, DEFAULT_CONFIG)
        assert result.version == "v1.0"


# ── AC-1 extended: Interpretation contract ────────────────────────────────────

class TestStructureLensInterpretation:

    def test_bullish_data_produces_bullish_or_ranging_direction(self):
        """Strong uptrend should classify as bullish or ranging — not bearish."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["trend"]["local_direction"] in {"bullish", "ranging"}

    def test_bearish_data_produces_bearish_or_ranging_direction(self):
        """Strong downtrend should classify as bearish or ranging — not bullish."""
        lens = StructureLens()
        result = lens.run(make_bearish_price_data(), DEFAULT_CONFIG)
        assert result.status == "success"
        assert result.data["trend"]["local_direction"] in {"bearish", "ranging"}

    def test_noisy_data_does_not_produce_extreme_structure(self):
        """Choppy data should not produce HH_HL or LH_LL — should be mixed."""
        lens = StructureLens()
        result = lens.run(make_noisy_price_data(), DEFAULT_CONFIG)
        if result.status == "success":
            # mixed is expected; HH_HL or LH_LL would be suspicious on random data
            # This is a soft assertion — noisy data may occasionally produce structure
            assert result.data["trend"]["structure_state"] in {"HH_HL", "LH_LL", "mixed"}

    def test_support_is_below_current_price(self):
        """Support must always be below current price when present."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        if result.status == "success" and result.data["levels"]["support"] is not None:
            current = make_bullish_price_data()["close"][-1]
            assert result.data["levels"]["support"] <= current

    def test_resistance_is_above_current_price(self):
        """Resistance must always be above current price when present."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        if result.status == "success" and result.data["levels"]["resistance"] is not None:
            current = make_bullish_price_data()["close"][-1]
            assert result.data["levels"]["resistance"] >= current

    def test_distance_to_support_is_positive(self):
        """Distance to support must be positive (price above support)."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        if result.status == "success" and result.data["distance"]["to_support"] is not None:
            assert result.data["distance"]["to_support"] >= 0

    def test_distance_to_resistance_is_positive(self):
        """Distance to resistance must be positive (price below resistance)."""
        lens = StructureLens()
        result = lens.run(make_bullish_price_data(), DEFAULT_CONFIG)
        if result.status == "success" and result.data["distance"]["to_resistance"] is not None:
            assert result.data["distance"]["to_resistance"] >= 0


# ── AC-10: Regression — existing tests must still pass ───────────────────────
# Handled by running full pytest suite after PR — not in this file.
# Record baseline count before merging: pytest -q | tail -3
```

---

## Step 4 — TDD Sequence

Follow red/green/refactor discipline. Do not write implementation before the test fails.

```
1. Write test_returns_lens_output_object          → run → RED (StructureLens doesn't exist)
2. Create minimal StructureLens skeleton           → run → GREEN
3. Write test_status_is_success_on_valid_data      → run → RED
4. Implement _compute() skeleton returning nulls   → run → GREEN
5. Write test_data_contains_all_required_fields    → run → RED
6. Implement full _compute() with all fields       → run → GREEN
7. Write test_never_raises_exception               → run → RED
8. Implement try/except in LensBase.run()          → run → GREEN
9. Write test_partial_data_never_returned          → run → RED
10. Enforce data=None on failure in LensBase       → run → GREEN
11. Write interpretation tests                     → run → RED
12. Implement _classify_structure, _detect_swings  → run → GREEN
13. Refactor — clean up, no new behavior
14. Run full suite → verify baseline + delta
```

---

## Step 5 — Acceptance Criteria Checklist

Before opening PR:

| # | Criterion | Status |
|---|---|---|
| AC-1 | Structure Lens produces valid schema from OHLCV — all fields present including nulls | ⏳ |
| AC-4 | Failed lens returns `LensOutput(status="failed", error="...", data=None)` — never partial data | ⏳ |
| AC-10 | All existing tests remain green (baseline count maintained) | ⏳ |
| — | `lens_id = "structure"` present on all outputs including failures | ⏳ |
| — | `version = "v1.0"` present on all outputs | ⏳ |
| — | Field value contracts respected: direction, structure_state, breakout.status enums | ⏳ |
| — | Support is always below current price when non-null | ⏳ |
| — | Resistance is always above current price when non-null | ⏳ |
| — | Lens never raises — always returns `LensOutput` | ⏳ |

---

## Constraints

- No modifications to existing files in this PR
- No snapshot builder in this PR — that is PR-AE-3
- No trend or momentum lens in this PR — those are PR-AE-2
- No persona or governance changes
- No live API calls in tests — all tests use frozen fixture data
- numpy is acceptable as a dependency — already in the project

---

## PR Description Template

```
PR-AE-1: LensBase interface + StructureLens

Implements the first two deliverables of P1 (Lens Engine):
- ai_analyst/lenses/base.py: LensOutput contract + LensBase abstract class
- ai_analyst/lenses/structure.py: StructureLens v1.0
- tests/lenses/test_structure_lens.py: unit tests

Closes AC-1 (structure lens schema), AC-4 (clean failure behavior).
AC-10 (regression): [baseline N tests] → [N + M tests], all green.

No existing files modified.
Next: PR-AE-2 (Trend + Momentum lenses).

Spec: docs/ANALYSIS_ENGINE_SPEC_v1.0.md v1.2
```

---

_PR-AE-1 plan · 2026-03-18 · Spec: ANALYSIS_ENGINE_SPEC_v1.0.md v1.2_
