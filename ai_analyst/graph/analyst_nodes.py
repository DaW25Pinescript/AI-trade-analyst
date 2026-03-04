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
from pydantic import ValidationError

logger = logging.getLogger(__name__)

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
from .state import GraphState

# Analyst roster — model names routed through LiteLLM.
# Update model identifiers here as new versions become available.
ANALYST_CONFIGS: list[dict] = [
    {"model": "gpt-4o",                     "persona": PersonaType.DEFAULT_ANALYST},
    {"model": "claude-sonnet-4-6",           "persona": PersonaType.RISK_OFFICER},
    {"model": "gemini/gemini-1.5-pro",       "persona": PersonaType.PROSECUTOR},
    {"model": "xai/grok-vision-beta",         "persona": PersonaType.ICT_PURIST},
]

MINIMUM_VALID_ANALYSTS = 2   # design rule #6


async def run_analyst(config: dict, prompt: dict, run_id: str) -> AnalystOutput:
    """
    Phase 1: Call one analyst model and validate the response against the AnalystOutput schema.
    Pushes a progress event to the run's queue (if registered) on completion.
    Raises on model error or schema validation failure — caller handles exceptions.
    """
    messages = build_messages(prompt)
    response = await acompletion_metered(
        run_dir=get_run_dir(run_id),
        run_id=run_id,
        stage="phase1_analyst",
        node=config["persona"].value,
        model=config["model"],
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,   # low temperature for determinism
        max_tokens=1500,
    )
    raw: str = response.choices[0].message.content
    result = AnalystOutput.model_validate_json(raw)

    # v2.2 — push progress event so SSE/CLI consumers can display live progress
    await progress_store.push_event(run_id, {
        "type": "analyst_done",
        "stage": "phase1",
        "persona": config["persona"].value,
        "model": config["model"],
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
    messages = build_messages(prompt)
    response = await acompletion_metered(
        run_dir=get_run_dir(run_id),
        run_id=run_id,
        stage="phase2_overlay",
        node=config["persona"].value,
        model=config["model"],
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1000,
    )
    raw: str = response.choices[0].message.content
    result = OverlayDeltaReport.model_validate_json(raw)

    # v2.2 — push progress event
    await progress_store.push_event(run_id, {
        "type": "analyst_done",
        "stage": "phase2_overlay",
        "persona": config["persona"].value,
        "model": config["model"],
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
    prompt = build_deliberation_prompt(
        own_round1_output=own_output,
        peer_round1_outputs=peer_outputs,
        persona=config["persona"],
    )
    messages = build_messages(prompt)
    response = await acompletion_metered(
        run_dir=get_run_dir(run_id),
        run_id=run_id,
        stage="phase3_deliberation",
        node=config["persona"].value,
        model=config["model"],
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1500,
    )
    raw: str = response.choices[0].message.content
    result = AnalystOutput.model_validate_json(raw)

    # v2.2 — push progress event
    await progress_store.push_event(run_id, {
        "type": "analyst_done",
        "stage": "deliberation",
        "persona": config["persona"].value,
        "model": config["model"],
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
    """
    ground_truth = state["ground_truth"]
    lens_config = state["lens_config"]

    tasks = [
        run_analyst(
            config,
            build_analyst_prompt(ground_truth, lens_config, config["persona"]),
            ground_truth.run_id,
        )
        for config in ANALYST_CONFIGS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_outputs: list[AnalystOutput] = []
    configs_used: list[dict] = []
    for i, result in enumerate(results):
        config = ANALYST_CONFIGS[i]
        model = config["model"]
        if isinstance(result, AnalystOutput):
            valid_outputs.append(result)
            configs_used.append(config)
        elif isinstance(result, ValidationError):
            logger.warning("Analyst '%s' Phase 1 returned schema-invalid output: %s", model, result)
        else:
            logger.warning("Analyst '%s' Phase 1 failed with error: %s", model, result)

    if len(valid_outputs) < MINIMUM_VALID_ANALYSTS:
        raise RuntimeError(
            f"Insufficient analyst responses: {len(valid_outputs)} valid out of "
            f"{len(ANALYST_CONFIGS)} attempted. Minimum required: {MINIMUM_VALID_ANALYSTS}."
        )

    state["analyst_outputs"] = valid_outputs
    state["analyst_configs_used"] = configs_used
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
        model = configs_used[i]["model"]
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
        model = configs_used[i]["model"]
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
