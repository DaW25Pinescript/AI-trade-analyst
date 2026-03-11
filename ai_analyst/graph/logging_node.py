"""
Logging node: writes the full audit trail for every run.
Executes after the Arbiter — no run exits the graph without a log entry.

MRO-P3: also records the MacroContext + verdict to the OutcomeTracker
SQLite database so the `python -m macro_risk_officer audit` command can
report regime distribution and confidence statistics over time.

Phase 3: records pipeline metrics (cost, latency, agreement) to the
in-memory metrics store for the operator health dashboard.

Observability Phase 1: assembles a structured run_record.json per run and
emits a concise stdout summary for operator visibility.
"""
import json as _json
import logging
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ..core.logger import log_run
from ..core.pipeline_metrics import metrics_store, RunMetrics
from ..core.usage_meter import summarize_usage
from ..core.run_paths import get_run_dir
from .state import GraphState

logger = logging.getLogger(__name__)


def _build_run_record(state: GraphState, usage: dict, total_latency_ms: int) -> dict:
    """Assemble the canonical run record from accumulated state + usage summary."""
    gt = state["ground_truth"]
    final_verdict = state.get("final_verdict")
    analyst_results = state.get("_analyst_results") or []
    arbiter_meta = state.get("_arbiter_meta") or {}
    node_timings = state.get("_node_timings") or {}
    run_dir = get_run_dir(gt.run_id)

    now = datetime.now(timezone.utc).isoformat()

    # Build stage trace from _node_timings (populated by validate_input_node)
    stage_order = [
        "validate_input", "macro_context", "chart_setup",
        "analyst_execution", "arbiter", "logging",
    ]
    # Map node names to stage names for known nodes
    node_to_stage = {
        "validate_input_node": "validate_input",
        "macro_context_node": "macro_context",
        "chart_setup_node": "chart_setup",
        "chart_lenses_node": "analyst_execution",
        "arbiter_node": "arbiter",
        "logging_node": "logging",
    }
    stages = []
    for stage_name in stage_order:
        # Find timing from node_timings via reverse mapping
        timing_ms = None
        for node_name, mapped_stage in node_to_stage.items():
            if mapped_stage == stage_name and node_name in node_timings:
                timing_ms = node_timings[node_name]
                break
        entry: dict = {"stage": stage_name, "status": "ok"}
        if timing_ms is not None:
            entry["duration_ms"] = timing_ms
        stages.append(entry)

    # Separate ran / skipped / failed analysts
    analysts_ran = [r for r in analyst_results if r.get("status") == "success"]
    analysts_skipped = [r for r in analyst_results if r.get("status") == "skipped"]
    analysts_failed = [r for r in analyst_results if r.get("status") == "failed"]

    # Arbiter section
    arbiter_ran = final_verdict is not None
    arbiter_record: dict = {"ran": arbiter_ran}
    if arbiter_ran:
        arbiter_record["verdict"] = final_verdict.decision
        arbiter_record["confidence"] = final_verdict.overall_confidence
        if arbiter_meta:
            arbiter_record["model"] = arbiter_meta.get("model")
            arbiter_record["provider"] = arbiter_meta.get("provider")
            arbiter_record["duration_ms"] = arbiter_meta.get("duration_ms")

    record = {
        "run_id": gt.run_id,
        "timestamp": now,
        "duration_ms": total_latency_ms,
        "request": {
            "instrument": gt.instrument,
            "session": gt.session,
            "timeframes": gt.timeframes,
            "smoke_mode": state.get("smoke_mode", False),
        },
        "stages": stages,
        "analysts": analysts_ran,
        "analysts_skipped": analysts_skipped,
        "analysts_failed": analysts_failed,
        "arbiter": arbiter_record,
        "artifacts": {
            "run_record": str(run_dir / "run_record.json"),
            "usage_jsonl": str(run_dir / "usage.jsonl"),
        },
        "usage_summary": usage,
        "warnings": [],
        "errors": [],
    }

    # Populate warnings / errors from state
    if state.get("error"):
        record["errors"].append(state["error"])
    if analysts_failed:
        for af in analysts_failed:
            record["warnings"].append(f"analyst_failed: {af.get('persona')} — {af.get('reason', 'unknown')}")

    return record


def _emit_stdout_summary(record: dict) -> str:
    """Build and print a concise structured summary. Returns the formatted string."""
    req = record.get("request", {})
    arb = record.get("arbiter", {})
    n_ran = len(record.get("analysts", []))
    n_skipped = len(record.get("analysts_skipped", []))
    n_failed = len(record.get("analysts_failed", []))
    duration_s = (record.get("duration_ms") or 0) / 1000.0

    lines = [
        "═══ Run Complete ═══════════════════════════════════════",
        f"  run_id:      {record.get('run_id', '?')}",
        f"  instrument:  {req.get('instrument', '?')} | session: {req.get('session', '?')} | timeframes: {', '.join(req.get('timeframes') or ['?'])}",
        f"  mode:        smoke={req.get('smoke_mode', False)}",
        f"  duration:    {duration_s:.1f}s",
        "─── Pipeline ───────────────────────────────────────────",
    ]
    for s in record.get("stages", []):
        dur = f"  {s['duration_ms']}ms" if s.get("duration_ms") is not None else ""
        extra = ""
        if s["stage"] == "analyst_execution":
            extra = f"  [{n_ran} ran, {n_skipped} skipped, {n_failed} failed]"
        lines.append(f"  {s['stage']:<22} {s['status']:<9}{dur}{extra}")

    lines.append("─── Verdict ────────────────────────────────────────────")
    if arb.get("ran"):
        lines.append(f"  decision:    {arb.get('verdict', '?')}")
        lines.append(f"  confidence:  {arb.get('confidence', '?')}")
    else:
        lines.append("  arbiter:     did not run")

    # Models section from usage_summary
    usage = record.get("usage_summary", {})
    calls_by_model = usage.get("calls_by_model", {})
    if calls_by_model:
        lines.append("─── Models ─────────────────────────────────────────────")
        for model_name, count in calls_by_model.items():
            lines.append(f"  {model_name} × {count}")

    lines.append("─── Artifacts ──────────────────────────────────────────")
    artifacts = record.get("artifacts", {})
    for label, path in artifacts.items():
        lines.append(f"  {label:<14} {path}")
    lines.append("════════════════════════════════════════════════════════")

    output = "\n".join(lines)
    print(output)
    return output


async def logging_node(state: GraphState) -> GraphState:
    """
    Persist the full run record. Returns state unchanged so the graph can reach END.

    Phase 3: also records RunMetrics to the in-memory metrics store.
    """
    ground_truth = state["ground_truth"]
    analyst_outputs = state.get("analyst_outputs", [])
    final_verdict = state.get("final_verdict")

    if final_verdict is None:
        logger.warning("logging_node called with no final_verdict in state")
        return state

    log_path = log_run(ground_truth, analyst_outputs, final_verdict)
    logger.info("Run %s logged to %s", ground_truth.run_id, log_path)

    # MRO-P3: record MacroContext snapshot to OutcomeTracker (fail-silent)
    macro_context = state.get("macro_context")
    if macro_context is not None:
        try:
            from macro_risk_officer.history.tracker import OutcomeTracker
            tracker = OutcomeTracker()
            tracker.record(
                context=macro_context,
                run_id=ground_truth.run_id,
                instrument=ground_truth.instrument,
                verdict=final_verdict,
            )
            logger.debug("MRO outcome recorded for run %s", ground_truth.run_id)
        except Exception as exc:
            logger.warning("MRO outcome recording failed (%s) — audit log unaffected.", exc)

    # Phase 3: record pipeline metrics (fail-silent — never blocks the pipeline)
    try:
        pipeline_start = state.get("_pipeline_start_ts")
        total_latency_ms = int((perf_counter() - pipeline_start) * 1000) if pipeline_start else 0

        usage = summarize_usage(get_run_dir(ground_truth.run_id))

        run_metrics = RunMetrics(
            run_id=ground_truth.run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            instrument=ground_truth.instrument,
            session=ground_truth.session,
            total_latency_ms=total_latency_ms,
            llm_cost_usd=usage.get("total_cost_usd", 0.0),
            llm_calls=usage.get("total_calls", 0),
            llm_calls_failed=usage.get("failed_calls", 0),
            analyst_count=len(analyst_outputs),
            analyst_agreement_pct=final_verdict.analyst_agreement_pct,
            decision=final_verdict.decision,
            overall_confidence=final_verdict.overall_confidence,
            overlay_provided=final_verdict.overlay_was_provided,
            deliberation_enabled=bool(state.get("enable_deliberation")),
            macro_context_available=macro_context is not None,
            node_timings=state.get("_node_timings") or {},
        )
        metrics_store.record_run(run_metrics)
        logger.info(
            "[Metrics] Run %s: latency=%dms cost=$%.4f analysts=%d agreement=%d%% decision=%s",
            ground_truth.run_id,
            total_latency_ms,
            run_metrics.llm_cost_usd,
            run_metrics.analyst_count,
            run_metrics.analyst_agreement_pct,
            run_metrics.decision,
        )
    except Exception as exc:
        logger.warning("[Metrics] Failed to record run metrics (%s) — audit log unaffected.", exc)

    # Observability Phase 1: assemble and persist run_record.json + stdout summary
    try:
        run_record = _build_run_record(state, usage, total_latency_ms)
        run_dir = get_run_dir(ground_truth.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        record_path = run_dir / "run_record.json"
        record_path.write_text(_json.dumps(run_record, indent=2, default=str), encoding="utf-8")
        logger.info("[RunRecord] Written to %s", record_path)
        _emit_stdout_summary(run_record)
    except Exception as exc:
        logger.warning("[RunRecord] Failed to write run record (%s) — pipeline unaffected.", exc)

    return state
