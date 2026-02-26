# Intentionally minimal — pipeline.py requires langgraph which is an optional
# heavy dependency not needed by the CLI/manual-mode paths.
# Consumers that need build_analysis_graph import directly from graph.pipeline.
# Consumers that need GraphState import directly from graph.state.
from .state import GraphState

__all__ = ["GraphState"]
