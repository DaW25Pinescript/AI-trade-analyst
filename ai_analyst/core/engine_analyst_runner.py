"""Engine Analyst Runner — async runner for one persona against one snapshot.

Spec reference: Sections 6.5, 6.6, 6.8

Executes a single persona contract against an evidence snapshot via LLM,
validates the output, and returns both the parsed output and validator results.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from ai_analyst.core.engine_prompt_builder import build_engine_prompt
from ai_analyst.core.json_extractor import extract_json
from ai_analyst.core.persona_validators import (
    ValidationResult,
    check_degraded_confidence_cap,
    run_validators_with_snapshot,
)
from ai_analyst.core.run_paths import get_run_dir
from ai_analyst.core.usage_meter import acompletion_metered
from ai_analyst.core import progress_store
from ai_analyst.llm_router.router import resolve_profile_route
from ai_analyst.llm_router.task_types import ANALYST_REASONING
from ai_analyst.models.engine_output import AnalysisEngineOutput
from ai_analyst.models.persona_contract import PersonaContract

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineAnalystRunResult:
    """Bundle of validated output + validator results from one persona run."""
    output: AnalysisEngineOutput
    validator_results: list[ValidationResult]


async def run_engine_analyst(
    persona_contract: PersonaContract,
    snapshot: dict,
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"],
    run_id: str,
    macro_context: dict | None = None,
) -> EngineAnalystRunResult:
    """Run one Analysis Engine persona against an evidence snapshot.

    1. Build prompt via engine_prompt_builder
    2. Call LLM via acompletion_metered
    3. Parse and validate output
    4. Run validators with snapshot awareness
    5. Check degraded confidence cap
    6. Push progress event
    7. Return EngineAnalystRunResult

    On exception: logs and re-raises. Caller handles retry/skip policy.
    """
    persona_id = persona_contract.persona_id

    # 1. Build prompt
    prompt = build_engine_prompt(
        snapshot=snapshot,
        persona_contract=persona_contract,
        run_status=run_status,
        macro_context=macro_context,
    )

    # 2. Resolve LLM profile route
    if persona_contract.model_profile_override:
        route = resolve_profile_route(persona_contract.model_profile_override)
    else:
        route = resolve_profile_route(ANALYST_REASONING)

    # 3. Build messages — system = merged system + persona, user = prompt user section
    system_content = prompt["system"] + "\n\n" + prompt["persona"]
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt["user"]},
    ]

    # 4. Call LLM
    temperature = persona_contract.temperature_override if persona_contract.temperature_override is not None else 0.1

    try:
        response = await acompletion_metered(
            run_dir=get_run_dir(run_id),
            run_id=run_id,
            stage="engine_analyst",
            node=persona_id.value,
            model=route.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=1500,
            **route.to_call_kwargs(),
        )
        raw: str = response.choices[0].message.content
        raw = extract_json(raw)

        # 5. Validate output schema
        output = AnalysisEngineOutput.model_validate_json(raw)

    except Exception as exc:
        logger.error(
            "Engine analyst '%s' failed: %s",
            persona_id.value,
            str(exc)[:300],
        )
        raise

    # 6. Run validators with snapshot awareness
    validator_results = run_validators_with_snapshot(
        output=output,
        validator_names=persona_contract.validator_rules,
        snapshot=snapshot,
    )

    # 7. Check degraded confidence cap — surface as a ValidationResult
    degraded = run_status == "DEGRADED"
    cap_result = check_degraded_confidence_cap(output, degraded)
    if cap_result is True:
        validator_results.append(ValidationResult(
            validator_name="engine.degraded_confidence_cap",
            passed=True,
        ))
    else:
        validator_results.append(ValidationResult(
            validator_name="engine.degraded_confidence_cap",
            passed=False,
            message=cap_result,
        ))

    # 8. Push progress event
    await progress_store.push_event(run_id, {
        "type": "engine_analyst_done",
        "persona": persona_id.value,
        "model": route.model,
        "action": output.recommended_action,
        "confidence": output.confidence,
        "run_status": run_status,
    })

    # 9. Return bundle
    return EngineAnalystRunResult(
        output=output,
        validator_results=validator_results,
    )
