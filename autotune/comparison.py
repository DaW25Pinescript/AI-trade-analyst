"""Phase A3 Comparison Layer — side-by-side structure_short vs structure_medium analysis.

Runs both tuned lens instances on the same historical data (rolling, 1-bar step)
and produces:
  - Agreement matrix
  - Accuracy by agreement state
  - Transition analysis
  - Signal value summary
  - Raw comparison CSV

Deterministic: same data = same output.
"""

import argparse
import csv
import json
import logging
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autotune import data_loader
from autotune.evaluator import (
    compute_atr,
    dataframe_to_lens_input,
    load_eval_config,
    load_manifest,
    get_instance_config,
    get_instance_params,
    build_lens_config,
)
from autotune.shims.structure_shim import AutoTuneStructureLens

logger = logging.getLogger(__name__)

AUTOTUNE_DIR = Path(__file__).parent
RESULTS_DIR = AUTOTUNE_DIR / "results"

DIRECTIONS = ("bullish", "bearish", "ranging")


def run_lens_at_bar(lens, full_data, t, params):
    """Run lens on data sliced up to bar t. Returns direction string or None on error."""
    sliced = {k: v[: t + 1] for k, v in full_data.items()}
    config = build_lens_config(params)
    config["_pivot_window_override"] = params["pivot_window"]
    output = lens.run(sliced, config)
    if output.status != "success":
        return None
    trend = output.data.get("trend", {})
    direction = trend.get("local_direction")
    if direction not in DIRECTIONS:
        return None
    return direction


def compute_forward_return(closes, t, horizon):
    """Compute forward percentage return from bar t over horizon bars."""
    if t + horizon >= len(closes):
        return None
    return (closes[t + horizon] - closes[t]) / closes[t] * 100.0


def run_comparison(split: str):
    """Run the full comparison on the specified split."""
    eval_config = load_eval_config()
    manifest = load_manifest()

    # Get configs and params for both instances
    short_config = get_instance_config(eval_config, "structure_short")
    medium_config = get_instance_config(eval_config, "structure_medium")
    short_params = get_instance_params(manifest, "structure_short")
    medium_params = get_instance_params(manifest, "structure_medium")

    short_horizon = short_config["horizon_bars"]   # 4
    medium_horizon = medium_config["horizon_bars"]  # 12
    atr_period = short_config["atr_period"]  # 14 (same for both)

    logger.info("Short params: %s (horizon=%d)", short_params, short_horizon)
    logger.info("Medium params: %s (horizon=%d)", medium_params, medium_horizon)

    # Load data
    df, ticker = data_loader.fetch_ohlcv()

    if split == "train":
        date_range = eval_config["train_date_range"]
    else:
        date_range = eval_config["validation_date_range"]

    df_split = data_loader.slice_by_date(df, date_range["start"], date_range["end"])
    if len(df_split) == 0:
        raise RuntimeError(f"No data for {split} split")

    logger.info("Split: %s, bars: %d", split, len(df_split))

    full_data = dataframe_to_lens_input(df_split)
    n_bars = len(full_data["close"])
    closes = full_data["close"]
    timestamps = pd.to_datetime(df_split["timestamp"])

    # ATR for context
    atr_array = compute_atr(full_data["high"], full_data["low"], closes, atr_period)

    # Warmup: start at max of both lookbacks and ATR period
    t_start = max(
        short_params["lookback_bars"],
        medium_params["lookback_bars"],
        atr_period + 1,
    )

    # Create lens instances
    lens_short = AutoTuneStructureLens()
    lens_medium = AutoTuneStructureLens()

    # Rolling comparison — step by 1 bar
    records = []
    for t in range(t_start, n_bars):
        dir_short = run_lens_at_bar(lens_short, full_data, t, short_params)
        dir_medium = run_lens_at_bar(lens_medium, full_data, t, medium_params)

        if dir_short is None or dir_medium is None:
            continue

        agreement = dir_short == dir_medium
        fwd_4bar = compute_forward_return(closes, t, short_horizon)
        fwd_12bar = compute_forward_return(closes, t, medium_horizon)

        records.append({
            "timestamp": timestamps.iloc[t],
            "direction_short": dir_short,
            "direction_medium": dir_medium,
            "agreement": agreement,
            "forward_4bar_pct": fwd_4bar,
            "forward_12bar_pct": fwd_12bar,
        })

    logger.info("Comparison complete: %d records", len(records))
    return records, short_params, medium_params, short_horizon, medium_horizon, split


def generate_report(records, short_params, medium_params, short_horizon, medium_horizon, split):
    """Generate the Phase A3 comparison report from records."""
    if not records:
        raise RuntimeError("No comparison records generated")

    # Filter to records with forward data for accuracy analysis
    records_with_4bar = [r for r in records if r["forward_4bar_pct"] is not None]
    records_with_12bar = [r for r in records if r["forward_12bar_pct"] is not None]

    # --- 1. Agreement Matrix ---
    agreement_matrix = Counter()
    for r in records:
        agreement_matrix[(r["direction_short"], r["direction_medium"])] += 1

    total = len(records)

    # --- 2. Accuracy by agreement state ---
    def directional_accuracy(subset, direction, fwd_key):
        """Compute accuracy: % of calls where forward move confirms the direction."""
        relevant = [r for r in subset if r[fwd_key] is not None]
        if not relevant:
            return None, 0
        if direction == "bullish":
            correct = sum(1 for r in relevant if r[fwd_key] > 0)
        elif direction == "bearish":
            correct = sum(1 for r in relevant if r[fwd_key] < 0)
        else:
            return None, len(relevant)
        return correct / len(relevant) if relevant else None, len(relevant)

    # Both bullish
    both_bullish = [r for r in records if r["direction_short"] == "bullish" and r["direction_medium"] == "bullish"]
    both_bullish_acc_4, both_bullish_n_4 = directional_accuracy(both_bullish, "bullish", "forward_4bar_pct")
    both_bullish_acc_12, both_bullish_n_12 = directional_accuracy(both_bullish, "bullish", "forward_12bar_pct")

    # Both bearish
    both_bearish = [r for r in records if r["direction_short"] == "bearish" and r["direction_medium"] == "bearish"]
    both_bearish_acc_4, both_bearish_n_4 = directional_accuracy(both_bearish, "bearish", "forward_4bar_pct")
    both_bearish_acc_12, both_bearish_n_12 = directional_accuracy(both_bearish, "bearish", "forward_12bar_pct")

    # Short bullish / medium bearish
    sb_mb = [r for r in records if r["direction_short"] == "bullish" and r["direction_medium"] == "bearish"]
    sb_mb_bull_acc_4, sb_mb_n_4 = directional_accuracy(sb_mb, "bullish", "forward_4bar_pct")
    sb_mb_bear_acc_4, _ = directional_accuracy(sb_mb, "bearish", "forward_4bar_pct")
    sb_mb_bull_acc_12, sb_mb_n_12 = directional_accuracy(sb_mb, "bullish", "forward_12bar_pct")
    sb_mb_bear_acc_12, _ = directional_accuracy(sb_mb, "bearish", "forward_12bar_pct")

    # Short bearish / medium bullish
    sbe_mb = [r for r in records if r["direction_short"] == "bearish" and r["direction_medium"] == "bullish"]
    sbe_mb_bull_acc_4, sbe_mb_n_4 = directional_accuracy(sbe_mb, "bullish", "forward_4bar_pct")
    sbe_mb_bear_acc_4, _ = directional_accuracy(sbe_mb, "bearish", "forward_4bar_pct")
    sbe_mb_bull_acc_12, sbe_mb_n_12 = directional_accuracy(sbe_mb, "bullish", "forward_12bar_pct")
    sbe_mb_bear_acc_12, _ = directional_accuracy(sbe_mb, "bearish", "forward_12bar_pct")

    # Ranging combinations
    short_ranging_medium_view = [r for r in records if r["direction_short"] == "ranging" and r["direction_medium"] != "ranging"]
    medium_ranging_short_view = [r for r in records if r["direction_medium"] == "ranging" and r["direction_short"] != "ranging"]

    # When short says ranging but medium has a view: does medium's view hold?
    sr_mv_bull = [r for r in short_ranging_medium_view if r["direction_medium"] == "bullish"]
    sr_mv_bear = [r for r in short_ranging_medium_view if r["direction_medium"] == "bearish"]
    sr_mv_bull_acc_4, sr_mv_bull_n_4 = directional_accuracy(sr_mv_bull, "bullish", "forward_4bar_pct")
    sr_mv_bull_acc_12, sr_mv_bull_n_12 = directional_accuracy(sr_mv_bull, "bullish", "forward_12bar_pct")
    sr_mv_bear_acc_4, sr_mv_bear_n_4 = directional_accuracy(sr_mv_bear, "bearish", "forward_4bar_pct")
    sr_mv_bear_acc_12, sr_mv_bear_n_12 = directional_accuracy(sr_mv_bear, "bearish", "forward_12bar_pct")

    # When medium says ranging but short has a view
    mr_sv_bull = [r for r in medium_ranging_short_view if r["direction_short"] == "bullish"]
    mr_sv_bear = [r for r in medium_ranging_short_view if r["direction_short"] == "bearish"]
    mr_sv_bull_acc_4, mr_sv_bull_n_4 = directional_accuracy(mr_sv_bull, "bullish", "forward_4bar_pct")
    mr_sv_bull_acc_12, mr_sv_bull_n_12 = directional_accuracy(mr_sv_bull, "bullish", "forward_12bar_pct")
    mr_sv_bear_acc_4, mr_sv_bear_n_4 = directional_accuracy(mr_sv_bear, "bearish", "forward_4bar_pct")
    mr_sv_bear_acc_12, mr_sv_bear_n_12 = directional_accuracy(mr_sv_bear, "bearish", "forward_12bar_pct")

    # --- 3. Transition Analysis ---
    short_flips_medium_steady = 0
    medium_flips_short_steady = 0
    both_flip = 0
    neither_flip = 0

    # Track short flips against medium direction
    short_flip_against_medium_bullish_fwd = []
    short_flip_against_medium_bearish_fwd = []

    for i in range(1, len(records)):
        prev = records[i - 1]
        curr = records[i]
        short_flipped = prev["direction_short"] != curr["direction_short"]
        medium_flipped = prev["direction_medium"] != curr["direction_medium"]

        if short_flipped and not medium_flipped:
            short_flips_medium_steady += 1
            # Track: does the short flip predict a reversal (align with short's new direction)?
            if curr["forward_4bar_pct"] is not None:
                if curr["direction_short"] == "bullish":
                    short_flip_against_medium_bullish_fwd.append(curr["forward_4bar_pct"])
                elif curr["direction_short"] == "bearish":
                    short_flip_against_medium_bearish_fwd.append(curr["forward_4bar_pct"])
        elif medium_flipped and not short_flipped:
            medium_flips_short_steady += 1
        elif short_flipped and medium_flipped:
            both_flip += 1
        else:
            neither_flip += 1

    total_transitions = len(records) - 1

    # Short flip accuracy: does the new short direction predict forward movement?
    short_flip_bullish_correct = sum(1 for f in short_flip_against_medium_bullish_fwd if f > 0)
    short_flip_bearish_correct = sum(1 for f in short_flip_against_medium_bearish_fwd if f < 0)
    short_flip_total = len(short_flip_against_medium_bullish_fwd) + len(short_flip_against_medium_bearish_fwd)
    short_flip_correct = short_flip_bullish_correct + short_flip_bearish_correct
    short_flip_acc = short_flip_correct / short_flip_total if short_flip_total > 0 else None

    # --- 4. Signal Value Summary ---
    # Overall accuracy of each instance alone (directional calls only)
    short_directional = [r for r in records_with_4bar if r["direction_short"] in ("bullish", "bearish")]
    medium_directional = [r for r in records_with_12bar if r["direction_medium"] in ("bullish", "bearish")]

    short_alone_correct = sum(
        1 for r in short_directional
        if (r["direction_short"] == "bullish" and r["forward_4bar_pct"] > 0)
        or (r["direction_short"] == "bearish" and r["forward_4bar_pct"] < 0)
    )
    short_alone_acc = short_alone_correct / len(short_directional) if short_directional else None

    medium_alone_correct = sum(
        1 for r in medium_directional
        if (r["direction_medium"] == "bullish" and r["forward_12bar_pct"] > 0)
        or (r["direction_medium"] == "bearish" and r["forward_12bar_pct"] < 0)
    )
    medium_alone_acc = medium_alone_correct / len(medium_directional) if medium_directional else None

    # Agreement directional accuracy (both agree on direction, check both horizons)
    both_agree_directional = [
        r for r in records
        if r["direction_short"] == r["direction_medium"]
        and r["direction_short"] in ("bullish", "bearish")
        and r["forward_4bar_pct"] is not None
        and r["forward_12bar_pct"] is not None
    ]
    agree_correct_4 = sum(
        1 for r in both_agree_directional
        if (r["direction_short"] == "bullish" and r["forward_4bar_pct"] > 0)
        or (r["direction_short"] == "bearish" and r["forward_4bar_pct"] < 0)
    )
    agree_correct_12 = sum(
        1 for r in both_agree_directional
        if (r["direction_short"] == "bullish" and r["forward_12bar_pct"] > 0)
        or (r["direction_short"] == "bearish" and r["forward_12bar_pct"] < 0)
    )
    agree_acc_4 = agree_correct_4 / len(both_agree_directional) if both_agree_directional else None
    agree_acc_12 = agree_correct_12 / len(both_agree_directional) if both_agree_directional else None

    # Disagreement patterns
    disagree_opposite = [
        r for r in records
        if r["direction_short"] in ("bullish", "bearish")
        and r["direction_medium"] in ("bullish", "bearish")
        and r["direction_short"] != r["direction_medium"]
    ]

    # When they disagree, which one is more likely correct?
    disagree_short_correct_4 = sum(
        1 for r in disagree_opposite
        if r["forward_4bar_pct"] is not None
        and ((r["direction_short"] == "bullish" and r["forward_4bar_pct"] > 0)
             or (r["direction_short"] == "bearish" and r["forward_4bar_pct"] < 0))
    )
    disagree_medium_correct_12 = sum(
        1 for r in disagree_opposite
        if r["forward_12bar_pct"] is not None
        and ((r["direction_medium"] == "bullish" and r["forward_12bar_pct"] > 0)
             or (r["direction_medium"] == "bearish" and r["forward_12bar_pct"] < 0))
    )
    disagree_with_fwd_4 = sum(1 for r in disagree_opposite if r["forward_4bar_pct"] is not None)
    disagree_with_fwd_12 = sum(1 for r in disagree_opposite if r["forward_12bar_pct"] is not None)

    # Agreement rate
    agree_count = sum(1 for r in records if r["agreement"])
    agreement_rate = agree_count / total if total > 0 else 0

    def fmt_pct(val):
        return f"{val:.1%}" if val is not None else "N/A"

    def fmt_acc(val, n):
        return f"{val:.1%} (n={n})" if val is not None else f"N/A (n={n})"

    # --- Build Report ---
    lines = []
    lines.append("# Phase A3 — Structure Short vs Medium Comparison Report")
    lines.append("")
    lines.append(f"**Split**: {split}")
    lines.append(f"**Total comparison bars**: {total}")
    lines.append(f"**Short params**: lookback_bars={short_params['lookback_bars']}, pivot_window={short_params['pivot_window']} (horizon={short_horizon} bars)")
    lines.append(f"**Medium params**: lookback_bars={medium_params['lookback_bars']}, pivot_window={medium_params['pivot_window']} (horizon={medium_horizon} bars)")
    lines.append("")

    # Section 1: Agreement Matrix
    lines.append("## 1. Agreement Matrix")
    lines.append("")
    lines.append("### Counts")
    lines.append("")
    lines.append("| short \\\\ medium | bullish | bearish | ranging | **total** |")
    lines.append("|-----------------|---------|---------|---------|-----------|")
    for sd in DIRECTIONS:
        row = [agreement_matrix.get((sd, md), 0) for md in DIRECTIONS]
        row_total = sum(row)
        lines.append(f"| {sd} | {row[0]} | {row[1]} | {row[2]} | {row_total} |")
    col_totals = [sum(agreement_matrix.get((sd, md), 0) for sd in DIRECTIONS) for md in DIRECTIONS]
    lines.append(f"| **total** | {col_totals[0]} | {col_totals[1]} | {col_totals[2]} | {total} |")
    lines.append("")

    lines.append("### Percentages")
    lines.append("")
    lines.append("| short \\\\ medium | bullish | bearish | ranging |")
    lines.append("|-----------------|---------|---------|---------|")
    for sd in DIRECTIONS:
        row = [agreement_matrix.get((sd, md), 0) for md in DIRECTIONS]
        pcts = [f"{v / total:.1%}" if total > 0 else "0.0%" for v in row]
        lines.append(f"| {sd} | {pcts[0]} | {pcts[1]} | {pcts[2]} |")
    lines.append("")

    lines.append(f"**Overall agreement rate**: {fmt_pct(agreement_rate)}")
    lines.append("")

    # Section 2: Accuracy by Agreement State
    lines.append("## 2. Accuracy by Agreement State")
    lines.append("")

    lines.append("### Both Bullish")
    lines.append(f"- 4-bar forward accuracy: {fmt_acc(both_bullish_acc_4, both_bullish_n_4)}")
    lines.append(f"- 12-bar forward accuracy: {fmt_acc(both_bullish_acc_12, both_bullish_n_12)}")
    lines.append("")

    lines.append("### Both Bearish")
    lines.append(f"- 4-bar forward accuracy: {fmt_acc(both_bearish_acc_4, both_bearish_n_4)}")
    lines.append(f"- 12-bar forward accuracy: {fmt_acc(both_bearish_acc_12, both_bearish_n_12)}")
    lines.append("")

    lines.append("### Disagreement: Short Bullish / Medium Bearish")
    lines.append(f"- Count: {len(sb_mb)}")
    lines.append(f"- Short (bullish) correct at 4-bar: {fmt_acc(sb_mb_bull_acc_4, sb_mb_n_4)}")
    lines.append(f"- Medium (bearish) correct at 4-bar: {fmt_acc(sb_mb_bear_acc_4, sb_mb_n_4)}")
    lines.append(f"- Short (bullish) correct at 12-bar: {fmt_acc(sb_mb_bull_acc_12, sb_mb_n_12)}")
    lines.append(f"- Medium (bearish) correct at 12-bar: {fmt_acc(sb_mb_bear_acc_12, sb_mb_n_12)}")
    lines.append("")

    lines.append("### Disagreement: Short Bearish / Medium Bullish")
    lines.append(f"- Count: {len(sbe_mb)}")
    lines.append(f"- Short (bearish) correct at 4-bar: {fmt_acc(sbe_mb_bear_acc_4, sbe_mb_n_4)}")
    lines.append(f"- Medium (bullish) correct at 4-bar: {fmt_acc(sbe_mb_bull_acc_4, sbe_mb_n_4)}")
    lines.append(f"- Short (bearish) correct at 12-bar: {fmt_acc(sbe_mb_bear_acc_12, sbe_mb_n_12)}")
    lines.append(f"- Medium (bullish) correct at 12-bar: {fmt_acc(sbe_mb_bull_acc_12, sbe_mb_n_12)}")
    lines.append("")

    lines.append("### Short Ranging / Medium Has a View")
    lines.append(f"- Count: {len(short_ranging_medium_view)}")
    lines.append(f"- Medium bullish correct at 4-bar: {fmt_acc(sr_mv_bull_acc_4, sr_mv_bull_n_4)}")
    lines.append(f"- Medium bullish correct at 12-bar: {fmt_acc(sr_mv_bull_acc_12, sr_mv_bull_n_12)}")
    lines.append(f"- Medium bearish correct at 4-bar: {fmt_acc(sr_mv_bear_acc_4, sr_mv_bear_n_4)}")
    lines.append(f"- Medium bearish correct at 12-bar: {fmt_acc(sr_mv_bear_acc_12, sr_mv_bear_n_12)}")
    lines.append("")

    lines.append("### Medium Ranging / Short Has a View")
    lines.append(f"- Count: {len(medium_ranging_short_view)}")
    lines.append(f"- Short bullish correct at 4-bar: {fmt_acc(mr_sv_bull_acc_4, mr_sv_bull_n_4)}")
    lines.append(f"- Short bullish correct at 12-bar: {fmt_acc(mr_sv_bull_acc_12, mr_sv_bull_n_12)}")
    lines.append(f"- Short bearish correct at 4-bar: {fmt_acc(mr_sv_bear_acc_4, mr_sv_bear_n_4)}")
    lines.append(f"- Short bearish correct at 12-bar: {fmt_acc(mr_sv_bear_acc_12, mr_sv_bear_n_12)}")
    lines.append("")

    # Section 3: Transition Analysis
    lines.append("## 3. Transition Analysis")
    lines.append("")
    lines.append(f"Total bar-to-bar transitions: {total_transitions}")
    lines.append("")
    lines.append(f"| Pattern | Count | % |")
    lines.append(f"|---------|-------|---|")
    lines.append(f"| Short flips, medium steady | {short_flips_medium_steady} | {short_flips_medium_steady / total_transitions:.1%} |")
    lines.append(f"| Medium flips, short steady | {medium_flips_short_steady} | {medium_flips_short_steady / total_transitions:.1%} |")
    lines.append(f"| Both flip | {both_flip} | {both_flip / total_transitions:.1%} |")
    lines.append(f"| Neither flips | {neither_flip} | {neither_flip / total_transitions:.1%} |")
    lines.append("")

    lines.append("### Do short flips against steady medium predict reversals?")
    lines.append("")
    if short_flip_acc is not None:
        lines.append(f"When short flips direction while medium stays steady, the short's NEW direction is correct (4-bar forward) {fmt_pct(short_flip_acc)} of the time (n={short_flip_total}).")
    else:
        lines.append("Insufficient data to assess short flip predictive value.")
    lines.append("")

    # Section 4: Signal Value Summary
    lines.append("## 4. Signal Value Summary")
    lines.append("")
    lines.append("### Individual Instance Accuracy (directional calls only, rolling 1-bar)")
    lines.append("")
    lines.append(f"- **Short alone** (4-bar forward): {fmt_acc(short_alone_acc, len(short_directional))}")
    lines.append(f"- **Medium alone** (12-bar forward): {fmt_acc(medium_alone_acc, len(medium_directional))}")
    lines.append("")

    lines.append("### Agreement vs Individual Accuracy")
    lines.append("")
    lines.append(f"- **Both agree** (4-bar forward): {fmt_acc(agree_acc_4, len(both_agree_directional))}")
    lines.append(f"- **Both agree** (12-bar forward): {fmt_acc(agree_acc_12, len(both_agree_directional))}")
    lines.append("")

    if agree_acc_4 is not None and short_alone_acc is not None:
        delta_4 = agree_acc_4 - short_alone_acc
        lines.append(f"Agreement vs short alone (4-bar): {delta_4:+.1%}")
    if agree_acc_12 is not None and medium_alone_acc is not None:
        delta_12 = agree_acc_12 - medium_alone_acc
        lines.append(f"Agreement vs medium alone (12-bar): {delta_12:+.1%}")
    lines.append("")

    does_agreement_help = False
    if agree_acc_4 is not None and short_alone_acc is not None and agree_acc_4 > short_alone_acc:
        does_agreement_help = True
    if agree_acc_12 is not None and medium_alone_acc is not None and agree_acc_12 > medium_alone_acc:
        does_agreement_help = True

    lines.append(f"**Does agreement predict better accuracy than either alone?** {'Yes' if does_agreement_help else 'No'}")
    lines.append("")

    lines.append("### Disagreement Analysis")
    lines.append("")
    if disagree_with_fwd_4 > 0:
        lines.append(f"- When they disagree (opposite directional calls): short correct at 4-bar {disagree_short_correct_4}/{disagree_with_fwd_4} ({disagree_short_correct_4 / disagree_with_fwd_4:.1%})")
    if disagree_with_fwd_12 > 0:
        lines.append(f"- When they disagree: medium correct at 12-bar {disagree_medium_correct_12}/{disagree_with_fwd_12} ({disagree_medium_correct_12 / disagree_with_fwd_12:.1%})")
    lines.append("")

    lines.append("### Strongest Disagreement Patterns")
    lines.append("")
    # Compute accuracy for each disagreement pattern
    patterns = [
        ("Short bullish / Medium bearish", sb_mb, sb_mb_bull_acc_4, sb_mb_bear_acc_12, len(sb_mb)),
        ("Short bearish / Medium bullish", sbe_mb, sbe_mb_bear_acc_4, sbe_mb_bull_acc_12, len(sbe_mb)),
    ]
    for name, subset, acc_short_4, acc_medium_12, n in patterns:
        lines.append(f"- **{name}** (n={n}): short correct at 4-bar: {fmt_pct(acc_short_4)}, medium correct at 12-bar: {fmt_pct(acc_medium_12)}")
    lines.append("")

    # High confidence subset
    lines.append("### High Confidence Subset")
    lines.append("")
    lines.append("High confidence = both agree on direction (bullish or bearish).")
    lines.append(f"- Count: {len(both_agree_directional)} / {total} ({len(both_agree_directional) / total:.1%} of all bars)")
    lines.append(f"- 4-bar accuracy: {fmt_pct(agree_acc_4)}")
    lines.append(f"- 12-bar accuracy: {fmt_pct(agree_acc_12)}")
    lines.append("")

    # Section 5 reference
    lines.append("## 5. Raw Data")
    lines.append("")
    lines.append("Full bar-by-bar comparison saved to: `autotune/results/phase_a3_comparison_data.csv`")
    lines.append("")

    return "\n".join(lines)


def save_csv(records, path):
    """Save comparison records to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "direction_short", "direction_medium",
            "agreement", "forward_4bar_pct", "forward_12bar_pct",
        ])
        writer.writeheader()
        for r in records:
            row = dict(r)
            row["timestamp"] = row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"])
            row["agreement"] = str(row["agreement"])
            row["forward_4bar_pct"] = f"{row['forward_4bar_pct']:.6f}" if row["forward_4bar_pct"] is not None else ""
            row["forward_12bar_pct"] = f"{row['forward_12bar_pct']:.6f}" if row["forward_12bar_pct"] is not None else ""
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Phase A3 Comparison: structure_short vs structure_medium")
    parser.add_argument("--split", default="train", choices=["train", "validation"],
                        help="Data split to run comparison on")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    records, short_params, medium_params, short_horizon, medium_horizon, split = run_comparison(args.split)

    # Save CSV
    csv_path = RESULTS_DIR / "phase_a3_comparison_data.csv"
    save_csv(records, csv_path)
    logger.info("CSV saved: %s", csv_path)

    # Generate and save report
    report = generate_report(records, short_params, medium_params, short_horizon, medium_horizon, split)
    report_path = RESULTS_DIR / "phase_a3_comparison_report.md"
    report_path.write_text(report)
    logger.info("Report saved: %s", report_path)

    print(report)


if __name__ == "__main__":
    main()
