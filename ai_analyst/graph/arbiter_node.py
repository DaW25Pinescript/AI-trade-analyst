"""
Arbiter node: the final decision layer.
The Arbiter receives ONLY structured JSON Evidence Objects — never chart images (design rule #3).
A cheaper text-only model is used here.

When a 15M overlay was provided, the arbiter also receives the overlay delta reports
and applies the lens-aware weighting rules (agreement, refinement, contradiction,
indicator-only, risk override, no-trade priority).

v2.1b: When deliberation ran, the arbiter also receives the Round 2 (deliberation)
analyst outputs and applies deliberation weighting rules (Round 2 weighted at 1.5x Round 1).
"""
import json
import logging

from ..models.arbiter_output import FinalVerdict
from ..core.arbiter_prompt_builder import build_arbiter_prompt
from ..core.run_paths import get_run_dir
from ..core.usage_meter import acompletion_metered
from ..llm_router import router
from ..llm_router.task_types import ARBITER_DECISION
from .state import GraphState

logger = logging.getLogger(__name__)


def _safe_excerpt(raw: str, max_chars: int = 256) -> str:
    excerpt = (raw or "").replace("\n", " ").strip()
    return excerpt[:max_chars]


def _fallback_verdict(run_id: str, reason: str) -> FinalVerdict:
    return FinalVerdict.model_validate({
        "final_bias": "neutral",
        "decision": "NO_TRADE",
        "approved_setups": [],
        "no_trade_conditions": [reason],
        "overall_confidence": 0.0,
        "analyst_agreement_pct": 0,
        "risk_override_applied": False,
        "arbiter_notes": reason,
        "audit_log": {
            "run_id": run_id,
            "analysts_received": 0,
            "analysts_valid": 0,
            "htf_consensus": False,
            "setup_consensus": False,
            "risk_override": False,
        },
    })


async def arbiter_node(state: GraphState) -> GraphState:
    """
    Build the arbiter prompt from structured evidence, call the Arbiter model,
    and validate the response against the FinalVerdict schema.

    Injects overlay delta reports when available and sets overlay-related
    fields in the FinalVerdict (overlay_was_provided, indicator_dependent,
    indicator_dependency_notes).

    v2.1b: Injects deliberation_outputs when deliberation ran so the arbiter
    can apply peer-informed weighting (Round 2 outputs weighted at 1.5x Round 1).
    """
    analyst_outputs = state["analyst_outputs"]
    ground_truth = state["ground_truth"]
    overlay_delta_reports = state.get("overlay_delta_reports") or []
    overlay_was_provided = ground_truth.m15_overlay is not None
    macro_context = state.get("macro_context")
    # v2.1b — deliberation outputs (None when deliberation was not enabled)
    deliberation_outputs = state.get("deliberation_outputs") or []

    prompt = build_arbiter_prompt(
        analyst_outputs=analyst_outputs,
        risk_constraints=ground_truth.risk_constraints,
        run_id=ground_truth.run_id,
        overlay_delta_reports=overlay_delta_reports,
        overlay_was_provided=overlay_was_provided,
        macro_context=macro_context,
        deliberation_outputs=deliberation_outputs if deliberation_outputs else None,
    )

    route = router.resolve(ARBITER_DECISION)

    response = await acompletion_metered(
        run_dir=get_run_dir(ground_truth.run_id),
        run_id=ground_truth.run_id,
        stage="arbiter",
        node="arbiter_node",
        model=route["model"],
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
        api_base=route["base_url"],
        api_key=route["api_key"],
    )

    raw: str = response.choices[0].message.content
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        error_obj = {
            "error_type": "JSON_DECODE_ERROR",
            "code": "ARBITER_MALFORMED_JSON",
            "response_excerpt": _safe_excerpt(raw),
        }
        logger.warning("Arbiter returned malformed JSON: %s", error_obj)
        state["error"] = json.dumps(error_obj)
        verdict = _fallback_verdict(
            run_id=ground_truth.run_id,
            reason="Arbiter response malformed; defaulting to NO_TRADE.",
        )
    else:
        if not payload.get("decision"):
            logger.warning(
                "Arbiter verdict decision missing/empty; defaulting to NO_TRADE for run_id=%s",
                ground_truth.run_id,
            )
            payload["decision"] = "NO_TRADE"

        try:
            verdict = FinalVerdict.model_validate(payload)
        except Exception:
            error_obj = {
                "error_type": "VERDICT_SCHEMA_ERROR",
                "code": "ARBITER_INVALID_SCHEMA",
                "response_excerpt": _safe_excerpt(raw),
            }
            logger.warning("Arbiter verdict schema validation failed: %s", error_obj)
            state["error"] = json.dumps(error_obj)
            verdict = _fallback_verdict(
                run_id=ground_truth.run_id,
                reason="Arbiter response invalid; defaulting to NO_TRADE.",
            )

    # Ensure overlay_was_provided reflects ground truth — cannot be contradicted by model output.
    if overlay_was_provided and not verdict.overlay_was_provided:
        verdict = verdict.model_copy(update={"overlay_was_provided": True})

    state["final_verdict"] = verdict
    return state
