"""
Two-phase analyst fan-out:

Phase 1 — parallel_analyst_node (mandatory):
  Runs all analysts against CLEAN price charts only. No overlay.
  Produces AnalystOutput per analyst.

Phase 2 — overlay_delta_node (conditional, only when 15M overlay provided):
  Runs all analysts against the 15M ICT overlay screenshot.
  Each analyst receives its own Phase 1 output as context.
  Produces OverlayDeltaReport per analyst.
  Uses SEPARATE API calls with ISOLATED context — prevents anchoring.
"""
import asyncio
from litellm import acompletion
from pydantic import ValidationError

from ..models.persona import PersonaType
from ..models.analyst_output import AnalystOutput, OverlayDeltaReport
from ..core.analyst_prompt_builder import (
    build_analyst_prompt,
    build_overlay_delta_prompt,
    build_messages,
)
from .state import GraphState

# Analyst roster — model names routed through LiteLLM.
# Update model identifiers here as new versions become available.
ANALYST_CONFIGS: list[dict] = [
    {"model": "gpt-4o",                     "persona": PersonaType.DEFAULT_ANALYST},
    {"model": "claude-sonnet-4-6",           "persona": PersonaType.RISK_OFFICER},
    {"model": "gemini/gemini-1.5-pro",       "persona": PersonaType.PROSECUTOR},
    {"model": "grok/grok-4-vision",          "persona": PersonaType.ICT_PURIST},
]

MINIMUM_VALID_ANALYSTS = 2   # design rule #6


async def run_analyst(config: dict, prompt: dict) -> AnalystOutput:
    """
    Phase 1: Call one analyst model and validate the response against the AnalystOutput schema.
    Raises on model error or schema validation failure — caller handles exceptions.
    """
    response = await acompletion(
        model=config["model"],
        messages=build_messages(prompt),
        response_format={"type": "json_object"},
        temperature=0.1,   # low temperature for determinism
        max_tokens=1500,
    )
    raw: str = response.choices[0].message.content
    return AnalystOutput.model_validate_json(raw)


async def run_overlay_delta(
    config: dict,
    prompt: dict,
) -> OverlayDeltaReport:
    """
    Phase 2: Call one analyst model for overlay delta analysis.
    Uses a separate API call with isolated context (no Phase 1 contamination).
    Validates response against OverlayDeltaReport schema.
    Raises on model error or schema validation failure.
    """
    response = await acompletion(
        model=config["model"],
        messages=build_messages(prompt),
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1000,
    )
    raw: str = response.choices[0].message.content
    return OverlayDeltaReport.model_validate_json(raw)


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
        )
        for config in ANALYST_CONFIGS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid_outputs: list[AnalystOutput] = []
    for i, result in enumerate(results):
        model = ANALYST_CONFIGS[i]["model"]
        if isinstance(result, AnalystOutput):
            valid_outputs.append(result)
        elif isinstance(result, ValidationError):
            print(f"[WARN] Analyst '{model}' Phase 1 returned schema-invalid output: {result}")
        else:
            print(f"[WARN] Analyst '{model}' Phase 1 failed with error: {result}")

    if len(valid_outputs) < MINIMUM_VALID_ANALYSTS:
        raise RuntimeError(
            f"Insufficient analyst responses: {len(valid_outputs)} valid out of "
            f"{len(ANALYST_CONFIGS)} attempted. Minimum required: {MINIMUM_VALID_ANALYSTS}."
        )

    state["analyst_outputs"] = valid_outputs
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

    if not ground_truth.m15_overlay:
        # Should not happen — pipeline only routes here when overlay is present
        print("[WARN] overlay_delta_node called but no m15_overlay in ground_truth. Skipping.")
        state["overlay_delta_reports"] = []
        return state

    print(f"[INFO] Phase 2 — overlay delta analysis for {len(analyst_outputs)} analysts.")

    tasks = [
        run_overlay_delta(
            ANALYST_CONFIGS[i % len(ANALYST_CONFIGS)],
            build_overlay_delta_prompt(ground_truth, analyst_output),
        )
        for i, analyst_output in enumerate(analyst_outputs)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    delta_reports: list[OverlayDeltaReport] = []
    for i, result in enumerate(results):
        model = ANALYST_CONFIGS[i % len(ANALYST_CONFIGS)]["model"]
        if isinstance(result, OverlayDeltaReport):
            delta_reports.append(result)
        elif isinstance(result, ValidationError):
            print(f"[WARN] Analyst '{model}' Phase 2 returned schema-invalid delta report: {result}")
        else:
            print(f"[WARN] Analyst '{model}' Phase 2 failed with error: {result}")

    if not delta_reports:
        print(
            "[WARN] No valid overlay delta reports produced. "
            "Arbiter will proceed with clean analysis only."
        )

    state["overlay_delta_reports"] = delta_reports
    return state
