"""Chart-analysis orchestration nodes for the LangGraph runtime."""
from __future__ import annotations

from .analyst_nodes import parallel_analyst_node
from .state import GraphState
from ..core.chart_analysis_runtime import resolve_chart_lenses


async def chart_base_node(state: GraphState) -> GraphState:
    """Stage marker for loading chart-analysis base contract."""
    state["chart_analysis_runtime"] = {
        "base_loaded": True,
        "auto_detect_ran": False,
    }
    return state


async def chart_auto_detect_node(state: GraphState) -> GraphState:
    """Resolve the runtime lens set while respecting explicit CLI overrides."""
    runtime = state.get("chart_analysis_runtime") or {}
    runtime["auto_detect_ran"] = True
    runtime["selected_lenses"] = resolve_chart_lenses(
        state["ground_truth"], state["lens_config"]
    )
    state["chart_analysis_runtime"] = runtime
    return state


async def chart_lenses_node(state: GraphState) -> GraphState:
    """Run selected chart-analysis lenses via the existing parallel analyst fan-out."""
    return await parallel_analyst_node(state)


async def pinekraft_bridge_node(state: GraphState) -> GraphState:
    """Optional post-arbiter bridge stage; no-op unless downstream tooling consumes it."""
    runtime = state.get("chart_analysis_runtime") or {}
    runtime["pinekraft_bridge_ran"] = True
    state["chart_analysis_runtime"] = runtime
    return state
