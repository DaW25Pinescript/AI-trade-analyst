"""
Two-phase analyst fan-out + v2.1b deliberation round:

Phase 1 — parallel_analyst_node (mandatory):
  Runs all analysts against CLEAN price charts only. No overlay.
  Produces AnalystOutput per analyst.
  Pushes per-analyst progress events to progress_store if registered (v2.2).

Phase 2 — overlay_delta_node (conditional, only when 15M overlay provided):
  Runs all analysts against the 15M ICT overlay screenshot.
  Each analyst receives its own Phase 1 output as context.
  Produces OverlayDeltaReport per analyst.
  Uses SEPARATE API calls with ISOLATED context — prevents anchoring.
  Pushes progress events to progress_store if registered (v2.2).

Phase 3 — deliberation_node (optional, v2.1b, only when enable_deliberation=True):
  Runs all analysts again with anonymized peer Round 1 outputs as context.
  Each analyst may revise or reaffirm its Phase 1 analysis.
  Produces a second list of AnalystOutput objects (deliberation_outputs).
  Pushes progress events to progress_store if registered (v2.2).
"""
import asyncio
import logging
import os
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def _dev_diagnostics_enabled() -> bool:
    import os
    return (
        os.getenv("AI_ANALYST_DEV_DIAGNOSTICS", "").lower() == "true"
        or os.getenv("DEBUG", "").lower() == "true"
    )

_TRIAGE_SMOKE_MODE = os.getenv("TRIAGE_SMOKE_MODE", "").lower() == "true"

from ..models.persona import PersonaType
from ..models.analyst_output import AnalystOutput, OverlayDeltaReport
from ..core.analyst_prompt_builder import (
    build_analyst_prompt,
    build_overlay_delta_prompt,
    build_deliberation_prompt,
    build_messages,
)
from ..core.run_paths import get_run_dir
from ..core.usage_meter import acompletion_metered
from ..core import progress_store
from ..core.json_extractor import extract_json
from ..llm_router import router
from ..llm_router.router import resolve_profile_route
from ..llm_router.task_types import ANALYST_REASONING
from .state import GraphState

# Analyst roster — loaded from config/llm_routing.yaml (analyst_roster section).
# Falls back to hardcoded defaults if the YAML key is absent.
# To change models, edit the YAML — no code changes needed.
ANALYST_CONFIGS: list[dict] = router.get_analyst_roster()

MINIMUM_VALID_ANALYSTS = 2   # design rule #6


async def run_analyst(config: dict, prompt: dict, run_id: str) -> AnalystOutput:
    """
    Phase 1: Call one analyst model and validate the response against the AnalystOutput schema.
    Pushes a progress event to the run's queue (if registered) on completion.
    Raises on model error or schema validation failure — caller handles exceptions.
    """
    import os as _os
    route = resolve_profile_route(config["profile"])

    # Smoke-path instrumentation — log LLM call details (never the key value)
    _triage_debug = _os.getenv("TRIAGE_DEBUG", "").lower() == "true"
    if _triage_debug:
        _api_key_env = "OPENAI_API_KEY"  # default; actual source depends on config
        _key_val = route.api_key or ""
        logger.info(
            "[run_analyst] LLM call — model=%s base_url=%s api_key_env=%s key_present=%s persona=%s",
            route.model,
            route.api_base,
            _api_key_env,
            bool(_key_val and len(str(_key_val)) > 0),
            config["persona"].value,
        )

    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=per_analyst_start payload=%s", run_id, {"persona": config["persona"].value, "phase": "phase1"})
    messages = build_messages(prompt)
    try:
        response = await acompletion_metered(
            run_dir=get_run_dir(run_id),
            run_id=run_id,
            stage="phase1_analyst",
            node=config["persona"].value,
            model=route.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,   # low temperature for determinism
            max_tokens=1500,
            **route.to_call_kwargs(),
        )
        raw: str = response.choices[0].message.content
        raw = extract_json(raw)
        result = AnalystOutput.model_validate_json(raw)
    except Exception as exc:
        if _dev_diagnostics_enabled():
            logger.warning("[dev-stage] request_id=%s stage=per_analyst_fail payload=%s", run_id, {"persona": config["persona"].value, "phase": "phase1", "error": str(exc)[:300]})
        raise

    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=per_analyst_success payload=%s", run_id, {"persona": config["persona"].value, "phase": "phase1", "action": result.recommended_action})

    # v2.2 — push progress event so SSE/CLI consumers can display live progress
    await progress_store.push_event(run_id, {
        "type": "analyst_done",
        "stage": "phase1",
        "persona": config["persona"].value,
        "model": route.model,
        "action": result.recommended_action,
        "confidence": result.confidence,
    })
    return result


async def run_overlay_delta(
    config: dict,
    prompt: dict,
    run_id: str,
) -> OverlayDeltaReport:
    """
    Phase 2: Call one analyst model for overlay delta analysis.
    Uses a separate API call with isolated context (no Phase 1 contamination).
    Validates response against OverlayDeltaReport schema.
    Pushes a progress event to the run's queue (if registered) on completion.
    Raises on model error or schema validation failure.
    """
    route = resolve_profile_route(config["profile"])
    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=per_analyst_start payload=%s", run_id, {"persona": config["persona"].value, "phase": "phase2_overlay"})
    messages = build_messages(prompt)
    try:
        response = await acompletion_metered(
            run_dir=get_run_dir(run_id),
            run_id=run_id,
            stage="phase2_overlay",
            node=config["persona"].value,
            model=route.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1000,
            **route.to_call_kwargs(),
        )
        raw: str = response.choices[0].message.content
        raw = extract_json(raw)
        result = OverlayDeltaReport.model_validate_json(raw)
    except Exception as exc:
        if _dev_diagnostics_enabled():
            logger.warning("[dev-stage] request_id=%s stage=per_analyst_fail payload=%s", run_id, {"persona": config["persona"].value, "phase": "phase2_overlay", "error": str(exc)[:300]})
        raise

    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=per_analyst_success payload=%s", run_id, {"persona": config["persona"].value, "phase": "phase2_overlay"})

    # v2.2 — push progress event
    await progress_store.push_event(run_id, {
        "type": "analyst_done",
        "stage": "phase2_overlay",
        "persona": config["persona"].value,
        "model": route.model,
        "contradictions": len(result.contradicts),
    })
    return result


async def run_deliberation_round(
    config: dict,
    own_output: AnalystOutput,
    peer_outputs: list[AnalystOutput],
    run_id: str,
) -> AnalystOutput:
    """
    v2.1b — Phase 3: Run one analyst through the deliberation round.
    The analyst receives its own Round 1 output plus anonymized peer outputs.
    Produces a revised or reaffirmed AnalystOutput.
    Pushes a progress event to the run's queue (if registered) on completion.
    Raises on model error or schema validation failure.
    """
    route = resolve_profile_route(config["profile"])
    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=per_analyst_start payload=%s", run_id, {"persona": config["persona"].value, "phase": "deliberation"})
    prompt = build_deliberation_prompt(
        own_round1_output=own_output,
        peer_round1_outputs=peer_outputs,
        persona=config["persona"],
    )
    messages = build_messages(prompt)
    try:
        response = await acompletion_metered(
            run_dir=get_run_dir(run_id),
            run_id=run_id,
            stage="phase3_deliberation",
            node=config["persona"].value,
            model=route.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1500,
            **route.to_call_kwargs(),
        )
        raw: str = response.choices[0].message.content
        raw = extract_json(raw)
        result = AnalystOutput.model_validate_json(raw)
    except Exception as exc:
        if _dev_diagnostics_enabled():
            logger.warning("[dev-stage] request_id=%s stage=per_analyst_fail payload=%s", run_id, {"persona": config["persona"].value, "phase": "deliberation", "error": str(exc)[:300]})
        raise

    if _dev_diagnostics_enabled():
        logger.info("[dev-stage] request_id=%s stage=per_analyst_success payload=%s", run_id, {"persona": config["persona"].value, "phase": "deliberation", "action": result.recommended_action})

    # v2.2 — push progress event
    await progress_store.push_event(run_id, {
        "type": "analyst_done",
        "stage": "deliberation",
        "persona": config["persona"].value,
        "model": route.model,
        "action": result.recommended_action,
        "confidence": result.confidence,
    })
    return result


async def parallel_analyst_node(state: GraphState) -> GraphState:
    """
    Phase 1 fan-out: run all analyst configs in parallel against clean price charts only.
    Invalid/failed analyst responses are logged as warnings and skipped,
    not silently ignored — a count is preserved in the audit log via analyst_outputs length.
    Raises RuntimeError if fewer than MINIMUM_VALID_ANALYSTS return valid output.

    TRIAGE_SMOKE_MODE: runs only the first analyst/persona and skips quorum.
    On LLM error returns an error dict in _smoke_error instead of raising.
    """
    ground_truth = state["ground_truth"]
    lens_config = state["lens_config"]

    # Effective smoke mode: per-request state flag OR module-level env var
    effective_smoke = state.get("smoke_mode", False) or _TRIAGE_SMOKE_MODE
    logger.info("[analyst_fan_out] smoke_mode: state=%s env=%s effective=%s",
                state.get("smoke_mode"), _TRIAGE_SMOKE_MODE, effective_smoke)

    configs_to_run = ANALYST_CONFIGS
    if effective_smoke:
        configs_to_run = ANALYST_CONFIGS[:1]
        logger.info("[smoke] smoke mode active — running only first analyst: %s", resolve_profile_route(configs_to_run[0]["profile"]).model)
    logger.info("[analyst_fan_out] effective analyst_count=%d", len(configs_to_run))

    tasks = [
        run_analyst(
            config,
            build_analyst_prompt(ground_truth, lens_config, config["persona"]),
            ground_truth.run_id,
        )
        for config in configs_to_run
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_outputs: list[AnalystOutput] = []
    configs_used: list[dict] = []
    for i, result in enumerate(results):
        config = configs_to_run[i]
        model = resolve_profile_route(config["profile"]).model
        # DEBUG: log the type and keys/attrs of each gather result
        logger.info(
            "[DEBUG] parallel_analyst_node result[%d]: type=%s isinstance_AnalystOutput=%s isinstance_ValidationError=%s",
            i, type(result).__name__, isinstance(result, AnalystOutput), isinstance(result, ValidationError),
        )
        if isinstance(result, AnalystOutput):
            logger.info(
                "[DEBUG] valid AnalystOutput[%d]: action=%s confidence=%s setup_valid=%s disqualifiers=%s",
                i, result.recommended_action, result.confidence, result.setup_valid, result.disqualifiers,
            )
            valid_outputs.append(result)
            configs_used.append(config)
        elif isinstance(result, ValidationError):
            logger.warning("Analyst '%s' Phase 1 returned schema-invalid output: %s", model, result)
        else:
            logger.warning("Analyst '%s' Phase 1 failed with error: %s", model, result)

    if effective_smoke:
        logger.info("[smoke] quorum bypass active — skipping quorum enforcement")
        if not valid_outputs:
            # In smoke mode, capture the error instead of raising
            err = results[0] if results else Exception("no results")
            logger.info("[smoke] first analyst result/error before aggregation: %s", err)
            smoke_route = resolve_profile_route(configs_to_run[0]["profile"])
            smoke_error = {
                "error_type": type(err).__name__,
                "status_code": getattr(err, "status_code", None),
                "model_attempted": smoke_route.model,
                "base_url_attempted": smoke_route.api_base,
                "message": str(err)[:500],
            }
            logger.error("[smoke] LLM error captured: %s", smoke_error)
            state["_smoke_error"] = smoke_error
            state["analyst_outputs"] = []
            state["analyst_configs_used"] = []
            return state
        # Smoke mode: log first result and skip quorum check
        logger.info("[smoke] first analyst result before aggregation: action=%s confidence=%s",
                    valid_outputs[0].recommended_action, valid_outputs[0].confidence)
    elif len(valid_outputs) < MINIMUM_VALID_ANALYSTS:
        raise RuntimeError(
            f"Insufficient analyst responses: {len(valid_outputs)} valid out of "
            f"{len(ANALYST_CONFIGS)} attempted. Minimum required: {MINIMUM_VALID_ANALYSTS}."
        )

    state["analyst_outputs"] = valid_outputs
    state["analyst_configs_used"] = configs_used
    logger.info(
        "[DEBUG] parallel_analyst_node DONE: len(valid_outputs)=%d len(state['analyst_outputs'])=%d",
        len(valid_outputs), len(state["analyst_outputs"]),
    )
    return state


async def overlay_delta_node(state: GraphState) -> GraphState:
    """
    Phase 2 fan-out: run overlay delta analysis for all analysts that completed Phase 1.

    Each analyst receives:
    - Its own Phase 1 AnalystOutput as context (clean-price baseline)
    - The 15M ICT overlay image

    This is a SEPARATE API call with ISOLATED context for each analyst.
    Cross-contamination between phases is not possible by design.

    Only called when ground_truth.m15_overlay is not None.
    If fewer valid delta reports come back than Phase 1 outputs, a warning is logged
    but the pipeline continues — the arbiter will note reduced overlay coverage.
    """
    ground_truth = state["ground_truth"]
    analyst_outputs = state["analyst_outputs"]
    configs_used = state["analyst_configs_used"]

    if not ground_truth.m15_overlay:
        # Should not happen — pipeline only routes here when overlay is present
        logger.warning("overlay_delta_node called but no m15_overlay in ground_truth. Skipping.")
        state["overlay_delta_reports"] = []
        return state

    logger.info("Phase 2 — overlay delta analysis for %d analysts.", len(analyst_outputs))

    tasks = [
        run_overlay_delta(
            configs_used[i],
            build_overlay_delta_prompt(ground_truth, analyst_output),
            ground_truth.run_id,
        )
        for i, analyst_output in enumerate(analyst_outputs)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    delta_reports: list[OverlayDeltaReport] = []
    for i, result in enumerate(results):
        model = resolve_profile_route(configs_used[i]["profile"]).model
        if isinstance(result, OverlayDeltaReport):
            delta_reports.append(result)
        elif isinstance(result, ValidationError):
            logger.warning(
                "Analyst '%s' Phase 2 returned schema-invalid delta report: %s", model, result
            )
        else:
            logger.warning("Analyst '%s' Phase 2 failed with error: %s", model, result)

    if not delta_reports:
        logger.warning(
            "No valid overlay delta reports produced. "
            "Arbiter will proceed with clean analysis only."
        )

    state["overlay_delta_reports"] = delta_reports
    return state


async def deliberation_node(state: GraphState) -> GraphState:
    """
    v2.1b — Phase 3 deliberation fan-out.

    Each analyst that completed Phase 1 reviews anonymized peer outputs and may
    revise or reaffirm its analysis. Only called when state["enable_deliberation"] is True.

    Peer outputs are anonymized (labelled A/B/C/D) — no model names exposed.
    Cross-analyst contamination is limited to text summaries, never chart images.

    If a deliberation call fails schema validation, that analyst's Round 1 output
    is retained in analyst_outputs; a warning is logged but the pipeline continues.
    """
    ground_truth = state["ground_truth"]
    analyst_outputs = state["analyst_outputs"]
    configs_used = state["analyst_configs_used"]

    logger.info(
        "Phase 3 — deliberation round for %d analysts.", len(analyst_outputs)
    )

    tasks = [
        run_deliberation_round(
            config=configs_used[i],
            own_output=analyst_outputs[i],
            peer_outputs=[analyst_outputs[j] for j in range(len(analyst_outputs)) if j != i],
            run_id=ground_truth.run_id,
        )
        for i in range(len(analyst_outputs))
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    delib_outputs: list[AnalystOutput] = []
    for i, result in enumerate(results):
        model = resolve_profile_route(configs_used[i]["profile"]).model
        if isinstance(result, AnalystOutput):
            delib_outputs.append(result)
        elif isinstance(result, ValidationError):
            logger.warning(
                "Analyst '%s' deliberation returned schema-invalid output: %s", model, result
            )
        else:
            logger.warning("Analyst '%s' deliberation failed with error: %s", model, result)

    state["deliberation_outputs"] = delib_outputs
    return state
