"""
Assembles the prompts for each analysis phase:

Phase 1 (mandatory):  clean price analysis
  build_analyst_prompt() → system + developer + user + images (clean charts only)

Phase 2 (conditional): overlay delta analysis — only when 15M ICT overlay is provided
  build_overlay_delta_prompt() → system + user + overlay image

The two phases use SEPARATE API calls with ISOLATED context to prevent the model
from anchoring on indicator data during the clean price analysis phase.
"""
import json
from pathlib import Path
from ..models.ground_truth import GroundTruthPacket
from ..models.lens_config import LensConfig
from ..models.persona import PersonaType
from ..models.analyst_output import AnalystOutput
from .lens_loader import load_active_lens_contracts, load_persona_prompt
from .chart_analysis_runtime import load_chart_analysis_component, resolve_chart_lenses

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
  "notes": "<max 200 chars — include explicit uncertainty statements about what cannot be determined from price alone>",
  "recommended_action": "WAIT | LONG | SHORT | NO_TRADE"
}"""

OVERLAY_DELTA_SCHEMA = """{
  "confirms": ["array of items where the overlay confirms the clean-price reading"],
  "refines": ["array of items where the overlay refines without contradicting"],
  "contradicts": ["array of items where the overlay contradicts the clean-price reading"],
  "indicator_only_claims": ["array of constructs visible only in the overlay, not in price"]
}"""

CHART_READER_ENGINE_PATH = (
    Path(__file__).parent.parent / "prompt_library" / "00_chart_reader_engine_v1.md"
)


def load_chart_reader_engine() -> str:
    """Load the strict chart-reader grounding contract used when images are attached."""
    if not CHART_READER_ENGINE_PATH.exists():
        raise FileNotFoundError(
            f"Chart Reader Engine prompt not found at {CHART_READER_ENGINE_PATH}."
        )
    return CHART_READER_ENGINE_PATH.read_text(encoding="utf-8").strip()


def build_analyst_prompt(
    ground_truth: GroundTruthPacket,
    lens_config: LensConfig,
    persona: PersonaType,
) -> dict:
    """
    Phase 1 — Clean Price Analysis.

    Returns a dict with keys: system, developer, user, images.
    The 'images' key holds the CLEAN charts only (no overlay).
    This is the only phase that runs when no overlay is provided.

    Critical: this prompt must never reference or anticipate indicator overlays.
    The overlay delta is handled by build_overlay_delta_prompt() in a separate call.
    """
    active_lenses = load_active_lens_contracts(lens_config)
    selected_chart_lenses = resolve_chart_lenses(ground_truth, lens_config)
    chart_runtime = load_chart_analysis_component("runtime_orchestrator")
    chart_base = load_chart_analysis_component("base")
    chart_auto_detect = load_chart_analysis_component("auto_detect")
    chart_arbiter = load_chart_analysis_component("arbiter")
    chart_lens_blocks = "\n\n---\n\n".join(
        load_chart_analysis_component(lens_name) for lens_name in selected_chart_lenses
    )
    persona_prompt = load_persona_prompt(persona)

    system_prompt = f"""You are a professional trading analyst.
You MUST follow all lens contracts below and output ONLY valid JSON. No prose. No markdown. Raw JSON only.

=== PHASE 1 — CLEAN PRICE ANALYSIS ONLY ===
Analyse ONLY the clean price charts provided. These are bare price charts with no indicator overlays.
Your analysis must be based EXCLUSIVELY on raw price action.
Do NOT reference, anticipate, or infer any indicator overlays — they are not present.
In your notes field, explicitly state what CANNOT be determined from price alone.
This baseline is used as ground truth before any indicator input is considered.

=== ACTIVE LENS CONTRACTS ===
{active_lenses}

=== MODULAR CHART ANALYSIS RUNTIME (BASE → AUTO-DETECT → SELECTED LENSES → ARBITER) ===
{chart_runtime}

Selected chart-analysis lenses (resolved from CLI overrides + typed metadata): {', '.join(selected_chart_lenses)}

=== CHART BASE ===
{chart_base}

=== CHART AUTO-DETECT HEURISTICS ===
{chart_auto_detect}

=== CHART SELECTED LENS CONTRACTS ===
{chart_lens_blocks}

=== CHART ARBITER CONTRACT ===
{chart_arbiter}

=== OUTPUT SCHEMA ===
You must return a JSON object matching this schema exactly.

{OUTPUT_SCHEMA}

HARD RULE: If setup_valid == false OR confidence < 0.45 OR disqualifiers list is non-empty
→ recommended_action MUST be "NO_TRADE". No exceptions."""

    return {
        "system": system_prompt,
        "developer": persona_prompt,
        "user": build_user_message(ground_truth),
        "images": ground_truth.charts,  # clean charts only — never includes overlay
    }


def build_overlay_delta_prompt(
    ground_truth: GroundTruthPacket,
    clean_analysis: AnalystOutput,
) -> dict:
    """
    Phase 2 — Overlay Delta Analysis (15M only, conditional).

    Only called when ground_truth.m15_overlay is provided.
    Receives the analyst's Phase 1 clean analysis as context.
    Returns a structured delta report comparing overlay interpretation
    against the clean-price baseline.

    Returns a dict with keys: system, user, images.
    The 'images' key contains ONLY the 15M overlay image.
    """
    if not ground_truth.m15_overlay:
        raise ValueError(
            "build_overlay_delta_prompt called but ground_truth.m15_overlay is None. "
            "This function must only be called when an overlay is provided."
        )

    overlay_meta = ground_truth.m15_overlay_metadata
    claims_str = ", ".join(overlay_meta.indicator_claims) if overlay_meta and overlay_meta.indicator_claims else "unspecified"
    source_str = overlay_meta.indicator_source if overlay_meta and overlay_meta.indicator_source else "unspecified"

    clean_analysis_json = json.dumps(clean_analysis.model_dump(), indent=2)

    system_prompt = f"""You are a professional trading analyst performing an overlay delta analysis.

=== PHASE 2 — OVERLAY DELTA ANALYSIS ===
You have already completed a clean price analysis (Phase 1 baseline).
You are now examining a 15M ICT indicator overlay screenshot.

OVERLAY DETAILS:
- Timeframe: 15M (15-minute)
- Lens: ICT
- Indicator constructs claimed: {claims_str}
- Source: {source_str}

YOUR TASK:
Compare the overlay interpretation against your Phase 1 clean-price baseline.
Produce a structured delta report. Silent merging is FORBIDDEN.

EVIDENCE HIERARCHY (non-negotiable):
- Clean price is GROUND TRUTH (primary authority).
- The overlay is an INTERPRETIVE AID (secondary authority).
- When the overlay contradicts price, report it in "contradicts" — never silently resolve it.
- Setups visible ONLY in the overlay (not in price) must be reported in "indicator_only_claims".

=== OUTPUT SCHEMA ===
Return ONLY valid JSON. No prose. No markdown.

{OVERLAY_DELTA_SCHEMA}

All four fields are REQUIRED. Empty arrays are valid. Omitted fields are not."""

    phase1_summary = f"""=== PHASE 1 CLEAN-PRICE BASELINE ===
{clean_analysis_json}

=== OVERLAY IMAGE ===
The 15M ICT overlay screenshot is attached. Compare it against the baseline above.
Return ONLY valid JSON matching the delta report schema."""

    return {
        "system": system_prompt,
        "developer": None,
        "user": phase1_summary,
        "images": {"M15_overlay": ground_truth.m15_overlay},  # only the overlay
    }


def build_user_message(ground_truth: GroundTruthPacket) -> str:
    """Serialise the Ground Truth Packet as JSON (charts excluded — passed as vision attachments)."""
    gt_dict = ground_truth.model_dump(exclude={"charts", "m15_overlay"})
    # datetime objects are not JSON-serialisable by default
    gt_json = json.dumps(gt_dict, indent=2, default=str)
    chart_list = ", ".join(ground_truth.charts.keys()) if ground_truth.charts else "none"

    overlay_note = ""
    if ground_truth.m15_overlay:
        overlay_note = (
            "\nNOTE: A 15M ICT overlay exists but is NOT provided here. "
            "It will be analysed separately in Phase 2. "
            "Do not anticipate or reference it in this analysis."
        )

    return f"""=== GROUND TRUTH PACKET ===
{gt_json}

=== CHART IMAGES ===
{len(ground_truth.charts)} clean price chart(s) attached: {chart_list}
{overlay_note}
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
    if any(img_data for img_data in (prompt.get("images") or {}).values()):
        chart_reader_engine = load_chart_reader_engine()
        system_content = f"{chart_reader_engine}\n\n{system_content}"

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
