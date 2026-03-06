"""Task type constants for LLM routing.

All task type references throughout the codebase MUST use these constants.
No magic strings — import from here.
"""

ANALYST_REASONING = "analyst_reasoning"
CHART_EXTRACT = "chart_extract"
CHART_INTERPRET = "chart_interpret"
ARBITER_DECISION = "arbiter_decision"
JSON_REPAIR = "json_repair"

ALL_TASK_TYPES = frozenset({
    ANALYST_REASONING,
    CHART_EXTRACT,
    CHART_INTERPRET,
    ARBITER_DECISION,
    JSON_REPAIR,
})
