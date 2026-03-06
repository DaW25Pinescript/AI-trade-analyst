"""Chart two-step analysis flow: extract → interpret.

Analogy (from CLAUDE.md):
  chart_extract  = the witness gives only observable facts under oath
  chart_interpret = the analyst reasons from those facts

These are two SEPARATE LLM calls. Never collapse them.

chart_extract  → Opus  (higher vision fidelity; image ambiguity is highest here)
chart_interpret → Sonnet (text reasoning from structured input; Opus not needed)
"""
import json
import logging
from pathlib import Path

from ..llm_router import router
from ..llm_router.task_types import CHART_EXTRACT, CHART_INTERPRET
from .run_paths import get_run_dir
from .usage_meter import acompletion_metered

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

CHART_EXTRACT_SYSTEM_PROMPT = """\
You are the Chart Extraction Engine. Your ONLY job is to report observable \
facts from the chart image. You are a witness under oath — report what you see, \
nothing more.

RULES:
- Report ONLY observable facts from the chart/image.
- List: visible timeframe, price labels, zones/boxes/lines, annotations, structure.
- Use explicit uncertainty markers when something cannot be reliably read:
  "cannot determine", "partially visible", "obscured by overlay".
- NEVER invent numeric values not clearly shown in the image.
- NEVER interpret, speculate, or give trading recommendations.
- If a value is not readable, say so — do not estimate.

OUTPUT FORMAT (JSON):
{
  "timeframe": "<visible timeframe label or 'cannot determine'>",
  "instrument": "<visible instrument label or 'cannot determine'>",
  "price_scale_readable": true/false,
  "visible_price_labels": ["<list of clearly readable price values>"],
  "structure": {
    "trend_direction": "<up/down/sideways/cannot determine>",
    "key_levels": ["<list of clearly labeled support/resistance levels>"],
    "zones": ["<list of visible zones/boxes with labels if readable>"],
    "annotations": ["<list of visible text annotations on chart>"]
  },
  "candle_observations": "<brief factual description of recent candle pattern>",
  "overlays_present": ["<list of visible overlays/indicators>"],
  "uncertainty_notes": ["<list of anything partially visible or unreadable>"]
}
"""

CHART_INTERPRET_SYSTEM_PROMPT = """\
You are the Chart Interpretation Analyst. You receive EXTRACTED FACTS from a \
chart (produced by the extraction step) — NOT the raw image.

Your job is to reason from the extracted facts to produce a trading analysis.

RULES:
- Reason ONLY from the extracted facts provided. Do not assume data not present.
- Flag low-confidence conclusions when the extraction contains uncertainty markers
  ("cannot determine", "partially visible", etc.).
- Reference specific extracted values when making claims.
- If the extraction data is insufficient for a conclusion, state that explicitly.

OUTPUT FORMAT (JSON):
{
  "bias": "<bullish/bearish/neutral>",
  "bias_confidence": "<high/medium/low>",
  "key_observations": ["<list of analytical observations derived from facts>"],
  "support_levels": ["<derived from extracted data>"],
  "resistance_levels": ["<derived from extracted data>"],
  "trade_setup": {
    "valid": true/false,
    "reason": "<why setup is or is not valid>",
    "entry_zone": "<if determinable from data>",
    "stop_loss": "<if determinable from data>",
    "targets": ["<if determinable from data>"]
  },
  "low_confidence_flags": ["<conclusions affected by extraction uncertainty>"],
  "insufficient_data": ["<what could not be determined and why>"]
}
"""


async def chart_extract(
    *,
    run_id: str,
    image_messages: list[dict],
    extra_context: str = "",
) -> dict:
    """Step 1: Extract observable facts from a chart image using Opus.

    Args:
        run_id: Pipeline run identifier.
        image_messages: Messages list containing the chart image
            (vision-compatible format).
        extra_context: Optional additional context to prepend.

    Returns:
        Parsed extraction dict from the model response.
    """
    route = router.resolve(CHART_EXTRACT)

    system_msg = CHART_EXTRACT_SYSTEM_PROMPT
    if extra_context:
        system_msg = f"{extra_context}\n\n{system_msg}"

    messages = [
        {"role": "system", "content": system_msg},
        *image_messages,
    ]

    logger.info(
        "[chart_two_step] extract: model=%s run_id=%s",
        route["model"], run_id,
    )

    response = await acompletion_metered(
        run_dir=get_run_dir(run_id),
        run_id=run_id,
        stage="chart_extract",
        node="chart_extract",
        model=route["model"],
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
        api_base=route["base_url"],
        api_key=route["api_key"],
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[chart_two_step] extract returned non-JSON: %s", raw[:256])
        return {"raw_text": raw, "parse_error": True}


async def chart_interpret(
    *,
    run_id: str,
    extraction: dict,
) -> dict:
    """Step 2: Interpret extracted chart facts using Sonnet.

    Args:
        run_id: Pipeline run identifier.
        extraction: The extraction dict from chart_extract step 1.

    Returns:
        Parsed interpretation dict from the model response.
    """
    route = router.resolve(CHART_INTERPRET)

    extraction_text = json.dumps(extraction, indent=2)

    messages = [
        {"role": "system", "content": CHART_INTERPRET_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here are the extracted facts from the chart analysis:\n\n"
                f"```json\n{extraction_text}\n```\n\n"
                "Please provide your interpretation and trading analysis "
                "based on these extracted facts."
            ),
        },
    ]

    logger.info(
        "[chart_two_step] interpret: model=%s run_id=%s",
        route["model"], run_id,
    )

    response = await acompletion_metered(
        run_dir=get_run_dir(run_id),
        run_id=run_id,
        stage="chart_interpret",
        node="chart_interpret",
        model=route["model"],
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=2000,
        api_base=route["base_url"],
        api_key=route["api_key"],
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[chart_two_step] interpret returned non-JSON: %s", raw[:256])
        return {"raw_text": raw, "parse_error": True}


async def chart_two_step_analysis(
    *,
    run_id: str,
    image_messages: list[dict],
    extra_context: str = "",
) -> dict:
    """Run the full two-step chart analysis: extract then interpret.

    Returns a dict with both extraction and interpretation results.
    """
    extraction = await chart_extract(
        run_id=run_id,
        image_messages=image_messages,
        extra_context=extra_context,
    )

    interpretation = await chart_interpret(
        run_id=run_id,
        extraction=extraction,
    )

    return {
        "extraction": extraction,
        "interpretation": interpretation,
    }
