"""
Logging node: writes the full audit trail for every run.
Executes after the Arbiter — no run exits the graph without a log entry.

MRO-P3: also records the MacroContext + verdict to the OutcomeTracker
SQLite database so the `python -m macro_risk_officer audit` command can
report regime distribution and confidence statistics over time.

Phase 3: records pipeline metrics (cost, latency, agreement) to the
in-memory metrics store for the operator health dashboard.
"""
import logging
from datetime import datetime, timezone
from time import perf_counter

from ..core.logger import log_run
from ..core.pipeline_metrics import metrics_store, RunMetrics
from ..core.usage_meter import summarize_usage
from ..core.run_paths import get_run_dir
from .state import GraphState

logger = logging.getLogger(__name__)


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

    return state
