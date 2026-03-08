"""Chart-analysis orchestration nodes for the LangGraph runtime."""
from __future__ import annotations

from .analyst_nodes import parallel_analyst_node
from .state import GraphState
from ..core.chart_analysis_runtime import resolve_chart_lenses


async def chart_base_node(state: GraphState) -> dict:
    """
    Stage marker for loading chart-analysis base contract.

    Returns a partial state dict (Phase 4: parallel fan-out safe — only writes
    chart_analysis_runtime so it does not conflict with macro_context_node).
    """
    return {
        "chart_analysis_runtime": {
            "base_loaded": True,
            "auto_detect_ran": False,
        }
    }


async def chart_auto_detect_node(state: GraphState) -> dict:
    """
    Resolve the runtime lens set while respecting explicit CLI overrides.

    Returns a partial state dict (Phase 4: only writes chart_analysis_runtime).
    """
    runtime = dict(state.get("chart_analysis_runtime") or {})
    runtime["auto_detect_ran"] = True
    runtime["selected_lenses"] = resolve_chart_lenses(
        state["ground_truth"], state["lens_config"]
    )
    return {"chart_analysis_runtime": runtime}


async def chart_setup_node(state: GraphState) -> dict:
    """
    Phase 4 combined chart-setup node used in the parallel pipeline.

    Merges chart_base_node and chart_auto_detect_node into a single atomic
    node so that the parallel fan-out (macro_context ∥ chart_setup) writes to
    different state keys — no LangGraph merge conflict.

    Returns a partial state dict (only chart_analysis_runtime).
    """
    selected_lenses = resolve_chart_lenses(
        state["ground_truth"], state["lens_config"]
    )
    return {
        "chart_analysis_runtime": {
            "base_loaded": True,
            "auto_detect_ran": True,
            "selected_lenses": selected_lenses,
        }
    }


async def chart_lenses_node(state: GraphState) -> dict:
    """Run selected chart-analysis lenses via the existing parallel analyst fan-out.

    Returns a PARTIAL state dict (only changed keys) so the LangGraph fan-in
    merge after the macro_context ∥ chart_setup parallel branches applies
    analyst results cleanly without overwriting unrelated state keys.
    """
    result_state = await parallel_analyst_node(state)
    update: dict = {
        "analyst_outputs": result_state["analyst_outputs"],
        "analyst_configs_used": result_state.get("analyst_configs_used", []),
    }
    # Smoke mode: propagate captured error if the analyst LLM failed
    if "_smoke_error" in result_state:
        update["_smoke_error"] = result_state["_smoke_error"]
    return update


async def pinekraft_bridge_node(state: GraphState) -> GraphState:
    """Optional post-arbiter bridge stage; no-op unless downstream tooling consumes it."""
    runtime = state.get("chart_analysis_runtime") or {}
    runtime["pinekraft_bridge_ran"] = True
    state["chart_analysis_runtime"] = runtime
    return state
