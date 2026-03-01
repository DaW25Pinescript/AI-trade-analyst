"""
Loads lens contracts and persona prompts from the versioned prompt library.
All prompts are loaded from disk at runtime — never hardcoded in Python.
"""
from pathlib import Path
from ..models.lens_config import LensConfig
from ..models.persona import PersonaType

PROMPT_LIBRARY_VERSION = "v1.2"
_PROMPT_LIBRARY_ROOT = Path(__file__).parent.parent / "prompt_library"

PROMPT_LIBRARY_DIR = _PROMPT_LIBRARY_ROOT / PROMPT_LIBRARY_VERSION

LENS_DIR = PROMPT_LIBRARY_DIR / "lenses"
PERSONA_DIR = PROMPT_LIBRARY_DIR / "personas"
ARBITER_DIR = PROMPT_LIBRARY_DIR / "arbiter"

# Maps LensConfig field names to their prompt file names
LENS_FILE_MAP: dict[str, str] = {
    "ICT_ICC": "ict_icc.txt",
    "MarketStructure": "market_structure.txt",
    "OrderflowLite": "orderflow_lite.txt",
    "Trendlines": "trendlines.txt",
    "ClassicalIndicators": "classical_indicators.txt",
    "Harmonic": "harmonic.txt",
    "SMT_Divergence": "smt_divergence.txt",
    "VolumeProfile": "volume_profile.txt",
}


def load_active_lens_contracts(
    lens_config: LensConfig,
    version: str = PROMPT_LIBRARY_VERSION,
) -> str:
    """
    Return the concatenated content of all enabled lens prompt files.
    Each lens block is separated by a horizontal rule.

    Args:
        lens_config: Which lenses to enable.
        version: Prompt library version directory to load from (e.g. "v1.1", "v1.2").
                 Defaults to PROMPT_LIBRARY_VERSION. Pass an explicit value to load a
                 specific version without changing the module-level default.
    """
    lens_dir = _PROMPT_LIBRARY_ROOT / version / "lenses"
    config_dict = lens_config.model_dump()
    active_blocks: list[str] = []

    for field_name, filename in LENS_FILE_MAP.items():
        if not config_dict.get(field_name, False):
            continue
        lens_path = lens_dir / filename
        if not lens_path.exists():
            raise FileNotFoundError(
                f"Lens file '{filename}' not found at {lens_path}. "
                f"Check prompt_library/{version}/lenses/."
            )
        active_blocks.append(lens_path.read_text(encoding="utf-8").strip())

    if not active_blocks:
        raise ValueError("At least one lens must be enabled in LensConfig.")

    return "\n\n---\n\n".join(active_blocks)


def load_persona_prompt(persona: PersonaType) -> str:
    """Return the persona prompt text for the given persona type."""
    filename = f"{persona.value}.txt"
    persona_path = PERSONA_DIR / filename
    if not persona_path.exists():
        raise FileNotFoundError(
            f"Persona file '{filename}' not found at {persona_path}."
        )
    return persona_path.read_text(encoding="utf-8").strip()


def load_arbiter_template() -> str:
    """Return the raw arbiter prompt template (with {N}, {analyst_outputs_json} placeholders)."""
    template_path = ARBITER_DIR / "arbiter_v1.1.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Arbiter template not found at {template_path}.")
    return template_path.read_text(encoding="utf-8")
