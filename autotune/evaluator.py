"""AutoTune Windowed Evaluator — score a lens configuration against historical data.

Deterministic: same config + same data = same result, every time.
Owns data format adaptation from DataFrame to lens input format.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add repo root to path for production imports
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_analyst.lenses.structure import StructureLens
from autotune.shims.structure_shim import AutoTuneStructureLens
from autotune import data_loader

logger = logging.getLogger(__name__)

AUTOTUNE_DIR = Path(__file__).parent
EVAL_CONFIG_PATH = AUTOTUNE_DIR / "eval_config.json"
MANIFEST_PATH = AUTOTUNE_DIR / "instance_manifest.json"

VALID_DIRECTIONS = {"bullish", "bearish", "ranging"}
SCORED_DIRECTIONS = {"bullish", "bearish"}


def dataframe_to_lens_input(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Convert a pandas DataFrame to the dict[str, np.ndarray] format lenses expect.

    Replicates the output shape of ohlcv_response_to_lens_input() without
    requiring an OHLCVResponse object.
    """
    ts = pd.to_datetime(df["timestamp"])
    return {
        "timestamp": (ts.astype(np.int64) // 10**9).to_numpy(dtype=np.float64),
        "open": df["open"].to_numpy(dtype=np.float64),
        "high": df["high"].to_numpy(dtype=np.float64),
        "low": df["low"].to_numpy(dtype=np.float64),
        "close": df["close"].to_numpy(dtype=np.float64),
        "volume": df["volume"].to_numpy(dtype=np.float64),
    }


def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                period: int = 14) -> np.ndarray:
    """Compute ATR using Wilder's smoothed moving average.

    Returns an array of length len(highs) with NaN for indices < period.
    ATR[period-1] = simple mean of TR[0..period-1].
    ATR[i] for i >= period = ((ATR[i-1] * (period-1)) + TR[i]) / period
    """
    n = len(highs)
    tr = np.empty(n, dtype=np.float64)
    tr[0] = highs[0] - lows[0]  # No previous close for first bar
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

    atr = np.full(n, np.nan, dtype=np.float64)
    if n < period:
        return atr

    # Initial ATR: simple mean of first `period` TRs
    atr[period - 1] = np.mean(tr[:period])

    # Wilder's smoothing
    for i in range(period, n):
        atr[i] = ((atr[i - 1] * (period - 1)) + tr[i]) / period

    return atr


def classify_outcome(
    direction: str,
    close_t: float,
    highs_forward: np.ndarray,
    lows_forward: np.ndarray,
    confirm_threshold: float,
    invalid_threshold: float,
) -> str:
    """Sequential bar-by-bar scan to classify outcome.

    Checks adverse BEFORE favorable within each bar (invalidation-first).
    Returns: 'confirmed', 'invalidated', or 'unresolved'.
    """
    for i in range(len(highs_forward)):
        if direction == "bullish":
            favorable = highs_forward[i] - close_t
            adverse = close_t - lows_forward[i]
        else:  # bearish
            favorable = close_t - lows_forward[i]
            adverse = highs_forward[i] - close_t

        # Adverse checked FIRST (invalidation-first rule)
        if adverse >= invalid_threshold:
            return "invalidated"
        if favorable >= confirm_threshold:
            return "confirmed"

    return "unresolved"


def load_eval_config() -> dict:
    """Load and validate eval_config.json."""
    if not EVAL_CONFIG_PATH.exists():
        raise FileNotFoundError(f"eval_config.json not found at {EVAL_CONFIG_PATH}")

    with open(EVAL_CONFIG_PATH) as f:
        config = json.load(f)

    # Validate required top-level keys
    required = ["meta", "train_date_range", "validation_date_range"]
    for key in required:
        if key not in config:
            raise ValueError(f"eval_config.json missing required key: '{key}'")

    return config


def load_manifest() -> dict:
    """Load and validate instance_manifest.json."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"instance_manifest.json not found at {MANIFEST_PATH}")

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)

    return manifest


def get_instance_config(eval_config: dict, instance_id: str) -> dict:
    """Extract instance-specific evaluator config."""
    if instance_id not in eval_config:
        raise ValueError(
            f"Instance '{instance_id}' not found in eval_config.json. "
            f"Available: {[k for k in eval_config if k not in ('meta', 'train_date_range', 'validation_date_range')]}"
        )
    return eval_config[instance_id]


def get_instance_params(manifest: dict, instance_id: str) -> dict:
    """Extract current parameter values for an instance."""
    if instance_id not in manifest:
        raise ValueError(
            f"Instance '{instance_id}' not found in instance_manifest.json"
        )
    inst = manifest[instance_id]
    params = {}
    for pname, pdef in inst["parameters"].items():
        params[pname] = pdef["current"]
    return params


def build_lens_config(params: dict, timeframe: str = "1H") -> dict:
    """Build a config dict suitable for the Structure lens."""
    return {
        "timeframe": timeframe,
        "lookback_bars": params["lookback_bars"],
        "swing_sensitivity": "medium",  # placeholder — shim overrides pivot_window
    }


def evaluate(
    df: pd.DataFrame,
    instance_id: str,
    params: dict,
    eval_instance_config: dict,
) -> dict:
    """Run the evaluation loop over historical data.

    Returns dict with 'metrics' and 'diagnostics' keys.
    """
    horizon_bars = eval_instance_config["horizon_bars"]
    step_bars = eval_instance_config["step_bars"]
    atr_period = eval_instance_config["atr_period"]
    confirm_mult = eval_instance_config["confirmation_atr_mult"]
    invalid_mult = eval_instance_config["invalidation_atr_mult"]

    lookback_bars = params["lookback_bars"]
    pivot_window = params["pivot_window"]

    # Convert full dataset to lens input arrays
    full_data = dataframe_to_lens_input(df)
    n_bars = len(full_data["close"])

    # Compute ATR over full dataset
    atr_array = compute_atr(
        full_data["high"], full_data["low"], full_data["close"], atr_period
    )

    # Create lens instance (with shim for numeric pivot_window)
    lens = AutoTuneStructureLens()

    # Warmup: first valid index
    t_start = max(lookback_bars, atr_period + 1)

    # Counters
    total_calls = 0
    confirmed = 0
    invalidated = 0
    unresolved = 0
    ranging_calls = 0
    bullish_calls = 0
    bearish_calls = 0
    lens_errors = 0
    total_steps = 0
    atr_at_calls = []

    t = t_start
    while t < n_bars:
        total_steps += 1

        # Check enough future bars
        if t + horizon_bars >= n_bars:
            break

        # Slice data up to T (inclusive) — lens cannot see future
        sliced = {k: v[:t + 1] for k, v in full_data.items()}

        # Get ATR at bar T
        atr_t = atr_array[t]
        if np.isnan(atr_t):
            t += step_bars
            continue

        # Build lens config with current params
        config = build_lens_config(params)
        config["_pivot_window_override"] = pivot_window

        # Run lens
        output = lens.run(sliced, config)

        # Check lens status
        if output.status != "success":
            lens_errors += 1
            # Check 5% error threshold
            if lens_errors > 0.05 * total_steps:
                raise RuntimeError(
                    f"Lens error rate exceeded 5%: {lens_errors}/{total_steps} "
                    f"({lens_errors/total_steps:.1%}). Config likely invalid. Halting."
                )
            t += step_bars
            continue

        # Extract direction
        trend_data = output.data.get("trend", {})
        direction = trend_data.get("local_direction")

        if direction not in VALID_DIRECTIONS:
            lens_errors += 1
            logger.warning("Invalid direction '%s' at step %d", direction, t)
            if lens_errors > 0.05 * total_steps:
                raise RuntimeError(
                    f"Lens error rate exceeded 5%: {lens_errors}/{total_steps}. Halting."
                )
            t += step_bars
            continue

        # Ranging — skip scoring
        if direction == "ranging":
            ranging_calls += 1
            t += step_bars
            continue

        # Scored call
        total_calls += 1
        if direction == "bullish":
            bullish_calls += 1
        else:
            bearish_calls += 1

        atr_at_calls.append(atr_t)

        # Compute thresholds
        confirm_threshold = confirm_mult * atr_t
        invalid_threshold = invalid_mult * atr_t

        # Forward window arrays
        highs_fwd = full_data["high"][t + 1: t + 1 + horizon_bars]
        lows_fwd = full_data["low"][t + 1: t + 1 + horizon_bars]

        # Classify outcome
        outcome = classify_outcome(
            direction, full_data["close"][t],
            highs_fwd, lows_fwd,
            confirm_threshold, invalid_threshold,
        )

        if outcome == "confirmed":
            confirmed += 1
        elif outcome == "invalidated":
            invalidated += 1
        else:
            unresolved += 1

        t += step_bars

    # Final error rate check
    if total_steps > 0 and lens_errors > 0.05 * total_steps:
        raise RuntimeError(
            f"Lens error rate exceeded 5%: {lens_errors}/{total_steps}. Halting."
        )

    resolved_calls = confirmed + invalidated
    all_directional = total_calls + ranging_calls + lens_errors

    # Compute date range string
    ts = pd.to_datetime(df["timestamp"])
    data_range = f"{ts.iloc[0].strftime('%Y-%m-%d')} to {ts.iloc[-1].strftime('%Y-%m-%d')}"

    metrics = {
        "total_calls": total_calls,
        "confirmed": confirmed,
        "invalidated": invalidated,
        "unresolved": unresolved,
        "resolved_calls": resolved_calls,
        "accuracy": confirmed / resolved_calls if resolved_calls > 0 else 0.0,
        "resolve_rate": resolved_calls / total_calls if total_calls > 0 else 0.0,
    }

    diagnostics = {
        "ranging_calls": ranging_calls,
        "ranging_pct": ranging_calls / all_directional if all_directional > 0 else 0.0,
        "bullish_calls": bullish_calls,
        "bearish_calls": bearish_calls,
        "lens_errors": lens_errors,
        "mean_atr_at_call": float(np.mean(atr_at_calls)) if atr_at_calls else 0.0,
        "data_range": data_range,
        "total_steps": total_steps,
    }

    return {"metrics": metrics, "diagnostics": diagnostics}


def main():
    parser = argparse.ArgumentParser(description="AutoTune Evaluator")
    parser.add_argument("--instance", required=True, help="Instance ID (e.g., structure_short)")
    parser.add_argument("--split", default="train", choices=["train", "validation"],
                        help="Data split to evaluate on")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    eval_config = load_eval_config()
    manifest = load_manifest()

    instance_config = get_instance_config(eval_config, args.instance)
    params = get_instance_params(manifest, args.instance)

    # Load data
    df, ticker = data_loader.fetch_ohlcv()

    # Select split
    if args.split == "train":
        date_range = eval_config["train_date_range"]
    else:
        date_range = eval_config["validation_date_range"]

    df_split = data_loader.slice_by_date(df, date_range["start"], date_range["end"])
    if len(df_split) == 0:
        raise RuntimeError(
            f"No data for {args.split} split ({date_range['start']} to {date_range['end']})"
        )

    logger.info(
        "Evaluating %s on %s split: %d bars (%s to %s)",
        args.instance, args.split, len(df_split),
        date_range["start"], date_range["end"],
    )

    result = evaluate(df_split, args.instance, params, instance_config)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
