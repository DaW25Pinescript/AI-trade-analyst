"""
Arbiter node: the final decision layer.
The Arbiter receives ONLY structured JSON Evidence Objects — never chart images (design rule #3).
A cheaper text-only model is used here.
"""
from litellm import acompletion
from ..models.arbiter_output import FinalVerdict
from ..core.arbiter_prompt_builder import build_arbiter_prompt
from .state import GraphState

# Text-only model for the Arbiter — cheaper, no vision needed
ARBITER_MODEL = "claude-haiku-4-5-20251001"


async def arbiter_node(state: GraphState) -> GraphState:
    """
    Build the arbiter prompt from structured evidence, call the Arbiter model,
    and validate the response against the FinalVerdict schema.
    """
    analyst_outputs = state["analyst_outputs"]
    ground_truth = state["ground_truth"]

    prompt = build_arbiter_prompt(
        analyst_outputs=analyst_outputs,
        risk_constraints=ground_truth.risk_constraints,
        run_id=ground_truth.run_id,
    )

    response = await acompletion(
        model=ARBITER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
    )

    raw: str = response.choices[0].message.content
    verdict = FinalVerdict.model_validate_json(raw)
    state["final_verdict"] = verdict
    return state
