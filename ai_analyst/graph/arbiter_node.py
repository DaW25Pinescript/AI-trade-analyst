"""
Arbiter node: the final decision layer.
The Arbiter receives ONLY structured JSON Evidence Objects — never chart images (design rule #3).
A cheaper text-only model is used here.

When a 15M overlay was provided, the arbiter also receives the overlay delta reports
and applies the lens-aware weighting rules (agreement, refinement, contradiction,
indicator-only, risk override, no-trade priority).
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

    Injects overlay delta reports when available and sets overlay-related
    fields in the FinalVerdict (overlay_was_provided, indicator_dependent,
    indicator_dependency_notes).
    """
    analyst_outputs = state["analyst_outputs"]
    ground_truth = state["ground_truth"]
    overlay_delta_reports = state.get("overlay_delta_reports") or []
    overlay_was_provided = ground_truth.m15_overlay is not None
    macro_context = state.get("macro_context")

    prompt = build_arbiter_prompt(
        analyst_outputs=analyst_outputs,
        risk_constraints=ground_truth.risk_constraints,
        run_id=ground_truth.run_id,
        overlay_delta_reports=overlay_delta_reports,
        overlay_was_provided=overlay_was_provided,
        macro_context=macro_context,
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

    # Ensure overlay_was_provided reflects ground truth — cannot be contradicted by model output.
    if overlay_was_provided and not verdict.overlay_was_provided:
        verdict = verdict.model_copy(update={"overlay_was_provided": True})

    state["final_verdict"] = verdict
    return state
