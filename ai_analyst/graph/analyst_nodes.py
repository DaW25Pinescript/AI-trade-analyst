"""
Parallel fan-out node: runs N analysts concurrently with no cross-talk (design rule #2).
Each analyst is a separate vision-capable model call with its own lens + persona.
"""
import asyncio
from litellm import acompletion
from pydantic import ValidationError

from ..models.persona import PersonaType
from ..models.analyst_output import AnalystOutput
from ..core.analyst_prompt_builder import build_analyst_prompt, build_messages
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
    Call one analyst model and validate the response against the AnalystOutput schema.
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


async def parallel_analyst_node(state: GraphState) -> GraphState:
    """
    Fan-out: run all analyst configs in parallel, collect valid responses.
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
            print(f"[WARN] Analyst '{model}' returned schema-invalid output: {result}")
        else:
            print(f"[WARN] Analyst '{model}' failed with error: {result}")

    if len(valid_outputs) < MINIMUM_VALID_ANALYSTS:
        raise RuntimeError(
            f"Insufficient analyst responses: {len(valid_outputs)} valid out of "
            f"{len(ANALYST_CONFIGS)} attempted. Minimum required: {MINIMUM_VALID_ANALYSTS}."
        )

    state["analyst_outputs"] = valid_outputs
    return state
