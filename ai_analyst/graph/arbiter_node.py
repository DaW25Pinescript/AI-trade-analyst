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
import re
import time

from ..models.arbiter_output import FinalVerdict
from ..core.arbiter_prompt_builder import build_arbiter_prompt
from ..core.run_paths import get_run_dir
from ..core.usage_meter import acompletion_metered
from ..llm_router import router
from ..llm_router.router import resolve_task_route
from ..llm_router.task_types import ARBITER_DECISION
from .state import GraphState

logger = logging.getLogger(__name__)


def _dev_diagnostics_enabled() -> bool:
    import os
    return (
        os.getenv("AI_ANALYST_DEV_DIAGNOSTICS", "").lower() == "true"
        or os.getenv("DEBUG", "").lower() == "true"
    )


def _safe_excerpt(raw: str, max_chars: int = 256) -> str:
    excerpt = (raw or "").replace("\n", " ").strip()
    return excerpt[:max_chars]


# Pattern to strip markdown code fences that LLMs commonly wrap JSON in.
_MD_JSON_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)


def _extract_json(raw: str) -> str:
    """Best-effort extraction of a JSON object from an LLM response.

    Handles two common failure modes:
      1. Response wrapped in markdown fences: ```json ... ```
      2. JSON object embedded in surrounding prose.
    Returns the extracted string (caller still needs json.loads).
    """
    stripped = raw.strip()
    # Fast path: already looks like raw JSON
    if stripped.startswith("{"):
        return stripped

    # Try stripping markdown fences
    m = _MD_JSON_RE.search(raw)
    if m:
        return m.group(1).strip()

    # Last resort: find the outermost { ... } substring
    start = raw.find("{")
    if start != -1:
        end = raw.rfind("}")
        if end > start:
            return raw[start : end + 1]

    return stripped


def _fallback_verdict(
    run_id: str,
    reason: str,
    analysts_received: int = 0,
    analysts_valid: int = 0,
) -> FinalVerdict:
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
            "analysts_received": analysts_received,
            "analysts_valid": analysts_valid,
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
    logger.info(
        "[DEBUG] arbiter_node ENTRY: len(analyst_outputs)=%d",
        len(analyst_outputs),
    )
    ground_truth = state["ground_truth"]
    overlay_delta_reports = state.get("overlay_delta_reports") or []
    overlay_was_provided = ground_truth.m15_overlay is not None
    macro_context = state.get("macro_context")
    # v2.1b — deliberation outputs (None when deliberation was not enabled)
    deliberation_outputs = state.get("deliberation_outputs") or []

    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=arbiter_start payload=%s", ground_truth.run_id, {"analyst_count": len(analyst_outputs)})
    prompt = build_arbiter_prompt(
        analyst_outputs=analyst_outputs,
        risk_constraints=ground_truth.risk_constraints,
        run_id=ground_truth.run_id,
        overlay_delta_reports=overlay_delta_reports,
        overlay_was_provided=overlay_was_provided,
        macro_context=macro_context,
        deliberation_outputs=deliberation_outputs if deliberation_outputs else None,
    )

    route = resolve_task_route(ARBITER_DECISION)
    _arbiter_t0 = time.perf_counter()

    try:
        response = await acompletion_metered(
        run_dir=get_run_dir(ground_truth.run_id),
        run_id=ground_truth.run_id,
        stage="arbiter",
        node="arbiter_node",
        model=route.model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
        **route.to_call_kwargs(),
    )

        raw: str = response.choices[0].message.content
    except Exception as exc:
        if _dev_diagnostics_enabled():
            logger.warning("[dev-stage] request_id=%s stage=arbiter_fail payload=%s", ground_truth.run_id, {"error": str(exc)[:300]})
        raise

    n_analysts = len(analyst_outputs)
    try:
        cleaned = _extract_json(raw)
        payload = json.loads(cleaned)
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
            analysts_received=n_analysts,
            analysts_valid=n_analysts,
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
                analysts_received=n_analysts,
                analysts_valid=n_analysts,
            )

    # Ensure overlay_was_provided reflects ground truth — cannot be contradicted by model output.
    if overlay_was_provided and not verdict.overlay_was_provided:
        verdict = verdict.model_copy(update={"overlay_was_provided": True})

    # Enforce audit_log analyst counts from Python-side truth.
    # The LLM populates these fields in its JSON output, but may miscount
    # (especially in smoke mode where N=1).  Python len(analyst_outputs) is
    # the authoritative source.
    audit_update = {
        "analysts_received": n_analysts,
        "analysts_valid": n_analysts,
    }
    if (verdict.audit_log.analysts_received != n_analysts
            or verdict.audit_log.analysts_valid != n_analysts):
        logger.info(
            "Arbiter audit_log analyst counts corrected: received %d->%d valid %d->%d",
            verdict.audit_log.analysts_received, n_analysts,
            verdict.audit_log.analysts_valid, n_analysts,
        )
        updated_log = verdict.audit_log.model_copy(update=audit_update)
        verdict = verdict.model_copy(update={"audit_log": updated_log})

    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=arbiter_success payload=%s", ground_truth.run_id, {"decision": verdict.decision})
    state["final_verdict"] = verdict
    # Observability Phase 1 — arbiter metadata for run record assembly
    state["_arbiter_meta"] = {
        "model": route.model,
        "provider": route.provider,
        "duration_ms": round((time.perf_counter() - _arbiter_t0) * 1000),
    }
    return state
