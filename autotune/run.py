"""AutoTune Runner / Orchestrator — single-iteration tuning loop.

Loads config, runs evaluator (baseline + candidate), applies acceptance
policy, updates manifest if accepted, writes experiment log.

Atomic: either completes fully (log + optional manifest update) or
produces nothing on error.
"""

import argparse
import copy
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autotune import data_loader
from autotune.evaluator import evaluate, load_eval_config, load_manifest, get_instance_config, get_instance_params

logger = logging.getLogger(__name__)

AUTOTUNE_DIR = Path(__file__).parent
MANIFEST_PATH = AUTOTUNE_DIR / "instance_manifest.json"
EVAL_CONFIG_PATH = AUTOTUNE_DIR / "eval_config.json"
LOGS_DIR = AUTOTUNE_DIR / "logs"
SESSIONS_DIR = AUTOTUNE_DIR / "sessions"

HARNESS_VERSION = "v1.0"

# Acceptance policy constants
MIN_RESOLVE_RATE = 0.70
MIN_RESOLVED_CALLS_RATIO = 0.80


def validate_proposal(manifest: dict, instance_id: str, param: str, value) -> None:
    """Validate a proposed parameter change against manifest bounds.

    Raises ValueError on any violation.
    """
    if instance_id not in manifest:
        raise ValueError(f"Instance '{instance_id}' not in manifest")

    inst = manifest[instance_id]
    params = inst.get("parameters", {})

    if param not in params:
        raise ValueError(
            f"Parameter '{param}' not found in instance '{instance_id}'. "
            f"Available: {list(params.keys())}"
        )

    pdef = params[param]
    if not pdef.get("mutable", False):
        raise ValueError(f"Parameter '{param}' is not mutable")

    pmin = pdef["min"]
    pmax = pdef["max"]
    step = pdef["step"]

    # Type coercion
    if isinstance(pmin, int) and isinstance(pmax, int) and isinstance(step, int):
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"Parameter '{param}' expects int, got {type(value).__name__}")
    else:
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Parameter '{param}' expects numeric, got {type(value).__name__}")

    if value < pmin or value > pmax:
        raise ValueError(
            f"Value {value} for '{param}' outside bounds [{pmin}, {pmax}]"
        )

    # Step grid check
    offset = value - pmin
    if isinstance(step, int):
        if offset % step != 0:
            raise ValueError(
                f"Value {value} for '{param}' not on step grid "
                f"(min={pmin}, step={step}, offset={offset})"
            )
    else:
        remainder = offset % step
        if remainder > 1e-9 and abs(remainder - step) > 1e-9:
            raise ValueError(
                f"Value {value} for '{param}' not on step grid "
                f"(min={pmin}, step={step})"
            )

    return value


def apply_acceptance_policy(
    baseline_metrics: dict, candidate_metrics: dict
) -> tuple[bool, list[str]]:
    """Apply the three acceptance conditions.

    Returns (accepted: bool, rejection_reasons: list[str]).
    """
    reasons = []

    # Condition 1: strict improvement in accuracy
    if candidate_metrics["accuracy"] <= baseline_metrics["accuracy"]:
        delta = candidate_metrics["accuracy"] - baseline_metrics["accuracy"]
        reasons.append(
            f"accuracy not strictly improved: {baseline_metrics['accuracy']:.6f} -> "
            f"{candidate_metrics['accuracy']:.6f} (delta={delta:.6f})"
        )

    # Condition 2: minimum resolve rate
    if candidate_metrics["resolve_rate"] < MIN_RESOLVE_RATE:
        reasons.append(
            f"resolve_rate {candidate_metrics['resolve_rate']:.3f} < {MIN_RESOLVE_RATE}"
        )

    # Condition 3: minimum resolved calls (80% of baseline)
    min_resolved = MIN_RESOLVED_CALLS_RATIO * baseline_metrics["resolved_calls"]
    if candidate_metrics["resolved_calls"] < min_resolved:
        reasons.append(
            f"resolved_calls {candidate_metrics['resolved_calls']} < "
            f"{min_resolved:.0f} (80% of baseline {baseline_metrics['resolved_calls']})"
        )

    accepted = len(reasons) == 0
    return accepted, reasons


def get_or_create_session(
    instance_id: str,
    manifest: dict,
    eval_config: dict,
    df: pd.DataFrame,
    ticker: str,
    new_session: bool = False,
) -> dict:
    """Get active session or create new one.

    Returns session_meta dict.
    """
    session_dir = SESSIONS_DIR / instance_id / "active"
    meta_path = session_dir / "session_meta.json"

    if not new_session and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            if meta.get("target_instance") == instance_id:
                logger.info("Resuming session: %s", meta["session_id"])
                return meta
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt session_meta.json, creating new session")

    # Create new session
    now = datetime.now(timezone.utc)
    session_id = f"{instance_id}_{now.strftime('%Y%m%d_%H%M%S')}"

    # Compute data stats
    train_range = eval_config["train_date_range"]
    train_df = data_loader.slice_by_date(df, train_range["start"], train_range["end"])
    actual_bars, expected_bars, _ = data_loader.validate_coverage(train_df)

    ts = pd.to_datetime(df["timestamp"])

    # Compute eval_config hash
    config_hash = hashlib.sha256(
        json.dumps(eval_config, sort_keys=True).encode()
    ).hexdigest()

    meta = {
        "session_id": session_id,
        "started_utc": now.isoformat(),
        "target_instance": instance_id,
        "train_date_range": eval_config["train_date_range"],
        "seed_params": get_instance_params(manifest, instance_id),
        "eval_config_hash": config_hash,
        "harness_version": HARNESS_VERSION,
        "data_source": {
            "ticker": ticker,
            "actual_range": f"{ts.iloc[0].strftime('%Y-%m-%d')} to {ts.iloc[-1].strftime('%Y-%m-%d')}",
            "bar_count": actual_bars,
            "expected_bar_count": expected_bars,
        },
        "pivot_mode": "continuous",  # Outcome A shim
    }

    # Write session artifacts
    session_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))

    # Write seed manifest (immutable copy)
    seed_path = session_dir / "seed_manifest.json"
    seed_data = manifest.get(instance_id, {})
    seed_path.write_text(json.dumps(seed_data, indent=2))

    logger.info("Created session: %s", session_id)
    return meta


def get_next_experiment_id(session_id: str) -> str:
    """Generate next experiment ID for this session."""
    log_path = LOGS_DIR / "experiment_log.jsonl"
    max_num = 0

    if log_path.exists():
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("session_id") == session_id:
                        exp_id = entry.get("experiment_id", "")
                        # Extract NNN from {session_id}_EXP{NNN}
                        suffix = exp_id.replace(f"{session_id}_EXP", "")
                        try:
                            num = int(suffix)
                            max_num = max(max_num, num)
                        except ValueError:
                            pass
                except json.JSONDecodeError:
                    continue

    return f"{session_id}_EXP{max_num + 1:03d}"


def get_iteration_number(session_id: str) -> int:
    """Get the next iteration number for this session."""
    log_path = LOGS_DIR / "experiment_log.jsonl"
    count = 0

    if log_path.exists():
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("session_id") == session_id:
                        count += 1
                except json.JSONDecodeError:
                    continue

    return count + 1


def write_log_entry(entry: dict) -> None:
    """Append one experiment log entry to experiment_log.jsonl."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "experiment_log.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def update_manifest(instance_id: str, param: str, value) -> None:
    """Update a parameter's current value in the manifest."""
    manifest = load_manifest()
    manifest[instance_id]["parameters"][param]["current"] = value
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def run_iteration(
    instance_id: str,
    param: str,
    value,
    split: str = "train",
    reasoning: str = "",
    new_session: bool = False,
) -> dict:
    """Execute one iteration of the tuning loop.

    Returns a result summary dict.
    """
    # 1. Load and validate configs
    eval_config = load_eval_config()
    manifest = load_manifest()

    instance_config = get_instance_config(eval_config, instance_id)
    current_params = get_instance_params(manifest, instance_id)

    # 2. Validate proposed change
    validated_value = validate_proposal(manifest, instance_id, param, value)
    old_value = current_params[param]

    if validated_value == old_value:
        raise ValueError(
            f"Proposed value {validated_value} for '{param}' is the same as current value"
        )

    # 3. Load data
    df, ticker = data_loader.fetch_ohlcv()

    # 4. Select split
    if split == "train":
        date_range = eval_config["train_date_range"]
    else:
        date_range = eval_config["validation_date_range"]

    df_split = data_loader.slice_by_date(df, date_range["start"], date_range["end"])
    if len(df_split) == 0:
        raise RuntimeError(
            f"No data for {split} split ({date_range['start']} to {date_range['end']})"
        )

    logger.info("Data: %d bars for %s split", len(df_split), split)

    # 5. Run baseline evaluation (current params)
    logger.info("Running baseline evaluation with current params: %s", current_params)
    baseline_result = evaluate(df_split, instance_id, current_params, instance_config)
    baseline_metrics = baseline_result["metrics"]
    logger.info("Baseline accuracy: %.6f", baseline_metrics["accuracy"])

    # 6. Build candidate params
    candidate_params = dict(current_params)
    candidate_params[param] = validated_value

    # 7. Run candidate evaluation
    logger.info("Running candidate evaluation: %s=%s", param, validated_value)
    candidate_result = evaluate(df_split, instance_id, candidate_params, instance_config)
    candidate_metrics = candidate_result["metrics"]
    logger.info("Candidate accuracy: %.6f", candidate_metrics["accuracy"])

    # 8. For validation split: read-only, no acceptance, no manifest update
    if split == "validation":
        print(f"\n=== VALIDATION RUN (read-only) ===")
        print(f"Instance: {instance_id}")
        print(f"Change: {param} {old_value} -> {validated_value}")
        print(f"Baseline accuracy: {baseline_metrics['accuracy']:.6f}")
        print(f"Candidate accuracy: {candidate_metrics['accuracy']:.6f}")
        print(f"Delta: {candidate_metrics['accuracy'] - baseline_metrics['accuracy']:.6f}")
        print(json.dumps(candidate_result, indent=2))
        return {
            "split": "validation",
            "baseline": baseline_result,
            "candidate": candidate_result,
        }

    # 9. Session management (train split only)
    session_meta = get_or_create_session(
        instance_id, manifest, eval_config, df, ticker, new_session
    )
    session_id = session_meta["session_id"]

    # 10. Apply acceptance policy
    accepted, rejection_reasons = apply_acceptance_policy(baseline_metrics, candidate_metrics)

    decision = "accepted" if accepted else "rejected"
    accuracy_delta = candidate_metrics["accuracy"] - baseline_metrics["accuracy"]

    logger.info("Decision: %s (delta=%.6f)", decision, accuracy_delta)
    if rejection_reasons:
        for r in rejection_reasons:
            logger.info("  Rejection reason: %s", r)

    # 11. Build log entry
    experiment_id = get_next_experiment_id(session_id)
    iteration = get_iteration_number(session_id)

    log_entry = {
        "experiment_id": experiment_id,
        "instance_id": instance_id,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session_id": session_id,
        "iteration": iteration,
        "change": {
            "parameter": param,
            "old_value": old_value,
            "new_value": validated_value,
        },
        "params_snapshot": candidate_params,
        "metrics": candidate_metrics,
        "diagnostics": candidate_result["diagnostics"],
        "decision": decision,
        "rejection_reasons": rejection_reasons,
        "accuracy_before": baseline_metrics["accuracy"],
        "accuracy_after": candidate_metrics["accuracy"],
        "accuracy_delta": accuracy_delta,
        "agent_reasoning": reasoning,
    }

    # 12. Atomic writes: log first, then manifest
    write_log_entry(log_entry)

    if accepted:
        update_manifest(instance_id, param, validated_value)
        logger.info("Manifest updated: %s.%s = %s", instance_id, param, validated_value)

    # 13. Print summary
    print(f"\n=== ITERATION RESULT ===")
    print(f"Experiment: {experiment_id}")
    print(f"Instance: {instance_id}")
    print(f"Change: {param} {old_value} -> {validated_value}")
    print(f"Decision: {decision}")
    print(f"Accuracy: {baseline_metrics['accuracy']:.6f} -> {candidate_metrics['accuracy']:.6f} (delta={accuracy_delta:.6f})")
    print(f"Resolve rate: {candidate_metrics['resolve_rate']:.3f}")
    print(f"Resolved calls: {candidate_metrics['resolved_calls']}")
    if rejection_reasons:
        print(f"Rejection reasons:")
        for r in rejection_reasons:
            print(f"  - {r}")

    return {
        "experiment_id": experiment_id,
        "decision": decision,
        "baseline": baseline_result,
        "candidate": candidate_result,
        "log_entry": log_entry,
    }


def main():
    parser = argparse.ArgumentParser(description="AutoTune Runner")
    parser.add_argument("--instance", required=True, help="Instance ID")
    parser.add_argument("--param", required=True, help="Parameter to change")
    parser.add_argument("--value", required=True, help="New value")
    parser.add_argument("--split", default="train", choices=["train", "validation"])
    parser.add_argument("--reasoning", default="", help="Agent reasoning for this change")
    parser.add_argument("--new-session", action="store_true", help="Force new session")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Coerce value to appropriate type
    try:
        value = int(args.value)
    except ValueError:
        try:
            value = float(args.value)
        except ValueError:
            value = args.value

    run_iteration(
        instance_id=args.instance,
        param=args.param,
        value=value,
        split=args.split,
        reasoning=args.reasoning,
        new_session=args.new_session,
    )


if __name__ == "__main__":
    main()
