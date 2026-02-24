"""
Assembles the three-part prompt for each analyst:
  1. system  — lens contracts + output schema enforcement
  2. developer — persona rules
  3. user    — Ground Truth Packet JSON + chart images
"""
import json
from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.persona import PersonaType
from .lens_loader import load_active_lens_contracts, load_persona_prompt

OUTPUT_SCHEMA = """{
  "htf_bias": "bullish | bearish | neutral | ranging",
  "structure_state": "continuation | reversal | range | undefined",
  "key_levels": {
    "premium": ["list of price zones"],
    "discount": ["list of price zones"],
    "invalid_below": <float or null>,
    "invalid_above": <float or null>
  },
  "setup_valid": true | false,
  "setup_type": "<string or null>",
  "entry_model": "<string describing LTF entry trigger>",
  "invalidation": "<specific price/condition that kills the trade>",
  "disqualifiers": ["array of strings — reasons against this setup"],
  "sweep_status": "<from ICT lens if active>",
  "fvg_zones": ["<from ICT lens if active>"],
  "displacement_quality": "strong | medium | weak | none",
  "confidence": <0.0-1.0>,
  "rr_estimate": <float>,
  "notes": "<max 200 chars>",
  "recommended_action": "WAIT | LONG | SHORT | NO_TRADE"
}"""


def build_analyst_prompt(
    ground_truth: GroundTruthPacket,
    lens_config: LensConfig,
    persona: PersonaType,
) -> dict:
    """
    Returns a dict with keys: system, developer, user, images.
    The 'images' key holds the charts dict (timeframe -> base64) for vision attachment.
    """
    active_lenses = load_active_lens_contracts(lens_config)
    persona_prompt = load_persona_prompt(persona)

    system_prompt = f"""You are a professional trading analyst.
You MUST follow all lens contracts below and output ONLY valid JSON. No prose. No markdown. Raw JSON only.

=== ACTIVE LENS CONTRACTS ===
{active_lenses}

=== OUTPUT SCHEMA ===
You must return a JSON object matching this schema exactly.

{OUTPUT_SCHEMA}

HARD RULE: If setup_valid == false OR confidence < 0.45 OR disqualifiers list is non-empty
→ recommended_action MUST be "NO_TRADE". No exceptions."""

    return {
        "system": system_prompt,
        "developer": persona_prompt,
        "user": build_user_message(ground_truth),
        "images": ground_truth.charts,
    }


def build_user_message(ground_truth: GroundTruthPacket) -> str:
    """Serialise the Ground Truth Packet as JSON (charts excluded — passed as vision attachments)."""
    gt_dict = ground_truth.model_dump(exclude={"charts"})
    # datetime objects are not JSON-serialisable by default
    gt_json = json.dumps(gt_dict, indent=2, default=str)
    chart_list = ", ".join(ground_truth.charts.keys()) if ground_truth.charts else "none"

    return f"""=== GROUND TRUTH PACKET ===
{gt_json}

=== CHART IMAGES ===
{len(ground_truth.charts)} chart(s) attached: {chart_list}

Analyse ONLY the data provided in this packet and the attached chart images.
Do not infer or add information not present in the input.
Return ONLY valid JSON matching the specified output schema."""


def build_messages(prompt: dict) -> list[dict]:
    """
    Convert the analyst prompt dict into the LiteLLM messages list format.
    Embeds base64 chart images as vision content blocks.
    """
    # Merge persona into system prompt
    system_content = prompt["system"]
    if prompt.get("developer"):
        system_content += f"\n\n=== ANALYST PERSONA ===\n{prompt['developer']}"

    messages: list[dict] = [{"role": "system", "content": system_content}]

    # Build user content — text + optional vision image blocks
    user_content: list[dict] = [{"type": "text", "text": prompt["user"]}]

    images: dict[str, str] = prompt.get("images") or {}
    for timeframe, img_data in images.items():
        if img_data:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_data}"},
            })

    messages.append({"role": "user", "content": user_content})
    return messages
