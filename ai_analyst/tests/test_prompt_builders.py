"""
Prompt builder tests.

Tests for Phase 1 (build_analyst_prompt) and Phase 2 (build_overlay_delta_prompt).

Design rules verified:
- Phase 1 prompts must never reference or anticipate indicator overlays.
- Phase 2 uses a separate, isolated API call — clean chart images are excluded.
- Evidence hierarchy is explicit: clean price = ground truth, overlay = interpretive aid.
- Phase 2 system prompt forbids silent merging of clean and overlay interpretations.
- Delta report schema (all 4 fields) is declared in the Phase 2 system prompt.
- Phase 2 only attaches the overlay image, never the clean charts.
- build_overlay_delta_prompt raises ValueError if no overlay is present in ground truth.
- build_messages produces the correct LiteLLM message list format with vision blocks.
"""
import pytest
from ..core.analyst_prompt_builder import (
    build_analyst_prompt,
    build_overlay_delta_prompt,
    build_messages,
)
from ..models.ground_truth import (
    GroundTruthPacket,
    RiskConstraints,
    MarketContext,
    ScreenshotMetadata,
)
from ..models.lens_config import LensConfig
from ..models.persona import PersonaType
from ..models.analyst_output import AnalystOutput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lens() -> LensConfig:
    return LensConfig(ICT_ICC=True, MarketStructure=True)


def _overlay_meta(**overrides) -> ScreenshotMetadata:
    base = dict(
        timeframe="M15",
        lens="ICT",
        evidence_type="indicator_overlay",
        indicator_claims=["FVG", "OrderBlock", "SessionLiquidity"],
        indicator_source="TradingView",
        settings_locked=True,
    )
    base.update(overrides)
    return ScreenshotMetadata(**base)


def _make_ground_truth(with_overlay: bool = False, **overrides) -> GroundTruthPacket:
    base: dict = {
        "instrument": "XAUUSD",
        "session": "NY",
        "timeframes": ["H4", "M15", "M5"],
        "charts": {"H4": "b64h4data", "M15": "b64m15data", "M5": "b64m5data"},
        "screenshot_metadata": [
            ScreenshotMetadata(timeframe="H4",  lens="NONE", evidence_type="price_only"),
            ScreenshotMetadata(timeframe="M15", lens="NONE", evidence_type="price_only"),
            ScreenshotMetadata(timeframe="M5",  lens="NONE", evidence_type="price_only"),
        ],
        "risk_constraints": RiskConstraints(),
        "context": MarketContext(account_balance=10000.0),
    }
    if with_overlay:
        base["m15_overlay"] = "b64overlaydata"
        base["m15_overlay_metadata"] = _overlay_meta()
    base.update(overrides)
    return GroundTruthPacket(**base)


def _clean_analyst_output() -> AnalystOutput:
    return AnalystOutput(
        htf_bias="bearish",
        structure_state="continuation",
        key_levels={"premium": ["1950–1955"], "discount": ["1910–1915"]},
        setup_valid=True,
        setup_type="liquidity_sweep_reversal",
        entry_model="Pullback to FVG on 15m",
        invalidation="Close above 1955",
        disqualifiers=[],
        confidence=0.72,
        rr_estimate=2.8,
        notes="Clean sweep + displacement. HTF and LTF aligned bearish.",
        recommended_action="SHORT",
    )


# ---------------------------------------------------------------------------
# Phase 1 — build_analyst_prompt
# ---------------------------------------------------------------------------

class TestBuildAnalystPrompt:
    def test_returns_required_keys(self):
        """Prompt dict must contain system, developer, user, and images."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        assert "system" in prompt
        assert "developer" in prompt
        assert "user" in prompt
        assert "images" in prompt

    def test_images_contains_only_clean_charts(self):
        """Phase 1 images must contain only clean charts — the overlay must be excluded."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        images = prompt["images"]
        assert "M15_overlay" not in images
        assert set(images.keys()) == {"H4", "M15", "M5"}

    def test_system_prompt_declares_phase_1(self):
        """Phase 1 system prompt must identify itself as clean price analysis only."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        assert "PHASE 1" in prompt["system"]

    def test_system_prompt_forbids_overlay_reference(self):
        """Phase 1 must explicitly tell the model not to reference indicator overlays."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        system = prompt["system"]
        # The exact wording in analyst_prompt_builder.py
        assert "Do NOT reference" in system

    def test_user_message_notes_overlay_analysed_separately(self):
        """When overlay is present, Phase 1 user message notes it will be analysed in Phase 2."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        user_msg = prompt["user"]
        assert "Phase 2" in user_msg
        assert "Do not anticipate" in user_msg

    def test_user_message_silent_when_no_overlay(self):
        """When no overlay is present, the Phase 1 user message must not mention it."""
        gt = _make_ground_truth(with_overlay=False)
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        # overlay-specific note must not appear when there is no overlay
        assert "Phase 2" not in prompt["user"]
        assert "Do not anticipate" not in prompt["user"]

    def test_system_prompt_includes_no_trade_hard_rule(self):
        """The NO_TRADE hard rule (confidence threshold 0.45) must appear in Phase 1."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        system = prompt["system"]
        assert "HARD RULE" in system
        assert "0.45" in system
        assert "NO_TRADE" in system

    def test_system_prompt_includes_output_schema_fields(self):
        """Phase 1 prompt must include the required AnalystOutput schema fields."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        system = prompt["system"]
        assert "recommended_action" in system
        assert "confidence" in system
        assert "htf_bias" in system


# ---------------------------------------------------------------------------
# Phase 2 — build_overlay_delta_prompt
# ---------------------------------------------------------------------------

class TestBuildOverlayDeltaPrompt:
    def test_raises_when_no_overlay_in_ground_truth(self):
        """build_overlay_delta_prompt must raise ValueError when no overlay is present."""
        gt = _make_ground_truth(with_overlay=False)
        with pytest.raises(ValueError, match="m15_overlay is None"):
            build_overlay_delta_prompt(gt, _clean_analyst_output())

    def test_returns_required_keys(self):
        """Phase 2 prompt dict must contain system, user, and images."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        assert "system" in prompt
        assert "user" in prompt
        assert "images" in prompt

    def test_images_contains_only_overlay(self):
        """
        Phase 2 images must contain ONLY the overlay image.
        Clean charts (H4, M15 clean, M5) must be excluded — this enforces
        the isolated context design rule (no cross-contamination between phases).
        """
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        images = prompt["images"]
        assert "M15_overlay" in images
        # Clean charts must NOT be in Phase 2 images
        assert "H4" not in images
        assert "M5" not in images
        # The overlay key, not the clean M15
        assert len(images) == 1

    def test_system_prompt_declares_phase_2_overlay_delta(self):
        """Phase 2 system prompt must identify itself as overlay delta analysis."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        system = prompt["system"]
        assert "PHASE 2" in system
        assert "OVERLAY DELTA" in system.upper()

    def test_system_prompt_enforces_evidence_hierarchy(self):
        """
        Phase 2 must state the evidence hierarchy explicitly:
        clean price = GROUND TRUTH (primary), overlay = INTERPRETIVE AID (secondary).
        """
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        system = prompt["system"]
        assert "GROUND TRUTH" in system
        assert "primary authority" in system
        assert "INTERPRETIVE AID" in system
        assert "secondary authority" in system

    def test_system_prompt_forbids_silent_merging(self):
        """Phase 2 must explicitly forbid silent merging of clean and indicator interpretations."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        system = prompt["system"]
        assert "Silent merging is FORBIDDEN" in system

    def test_phase1_baseline_embedded_in_user_message(self):
        """The Phase 1 clean analysis JSON must appear in the Phase 2 user message."""
        gt = _make_ground_truth(with_overlay=True)
        clean_output = _clean_analyst_output()
        prompt = build_overlay_delta_prompt(gt, clean_output)
        user_msg = prompt["user"]
        # Phase 1 htf_bias must be in the embedded baseline JSON
        assert "bearish" in user_msg
        # The baseline section header must be present
        assert "PHASE 1 CLEAN-PRICE BASELINE" in user_msg

    def test_delta_schema_all_four_fields_declared(self):
        """All four required delta report fields must be declared in the Phase 2 system prompt."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        system = prompt["system"]
        assert "confirms" in system
        assert "refines" in system
        assert "contradicts" in system
        assert "indicator_only_claims" in system

    def test_overlay_indicator_claims_named_in_system_prompt(self):
        """The overlay's indicator_claims must be referenced in the Phase 2 system prompt."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        system = prompt["system"]
        # All three claims from _overlay_meta() must appear
        assert "FVG" in system
        assert "OrderBlock" in system
        assert "SessionLiquidity" in system

    def test_overlay_source_referenced_in_system_prompt(self):
        """The indicator source (e.g. TradingView) must appear in the Phase 2 system prompt."""
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        assert "TradingView" in prompt["system"]

    def test_contradicts_field_framing(self):
        """
        Phase 2 must tell the model that contradictions between overlay and price
        must be reported in 'contradicts' — never silently resolved.
        This is the safeguard against the adversarial failure mode.
        """
        gt = _make_ground_truth(with_overlay=True)
        prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        system = prompt["system"]
        assert "contradicts" in system
        assert "never silently resolve" in system or "FORBIDDEN" in system


# ---------------------------------------------------------------------------
# build_messages — LiteLLM format
# ---------------------------------------------------------------------------

class TestBuildMessages:
    def test_returns_list_of_dicts(self):
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        messages = build_messages(prompt)
        assert isinstance(messages, list)
        assert all(isinstance(m, dict) for m in messages)

    def test_system_role_is_first(self):
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        messages = build_messages(prompt)
        assert messages[0]["role"] == "system"

    def test_user_role_present(self):
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        messages = build_messages(prompt)
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert len(user_msgs) == 1

    def test_clean_chart_images_embedded_as_image_url_blocks(self):
        """Three clean charts must be embedded as vision image_url blocks in the user message."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.DEFAULT_ANALYST)
        messages = build_messages(prompt)
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert isinstance(user_content, list)
        image_blocks = [c for c in user_content if c.get("type") == "image_url"]
        assert len(image_blocks) == 3  # H4, M15, M5

    def test_persona_merged_into_system_message(self):
        """Persona content must be merged into the system message, not sent separately."""
        gt = _make_ground_truth()
        prompt = build_analyst_prompt(gt, _lens(), PersonaType.RISK_OFFICER)
        messages = build_messages(prompt)
        system_content = messages[0]["content"]
        assert "ANALYST PERSONA" in system_content

    def test_overlay_image_block_in_phase2_messages(self):
        """Phase 2 build_messages must embed the overlay as a single image_url block."""
        gt = _make_ground_truth(with_overlay=True)
        phase2_prompt = build_overlay_delta_prompt(gt, _clean_analyst_output())
        messages = build_messages(phase2_prompt)
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        image_blocks = [c for c in user_content if c.get("type") == "image_url"]
        assert len(image_blocks) == 1  # only the overlay


class TestBuildMessagesChartReaderEngine:
    def test_prepends_chart_reader_engine_when_images_exist(self):
        prompt = {
            "system": "SYSTEM CORE",
            "developer": "PERSONA",
            "user": "USER",
            "images": {"H1": "b64img"},
        }

        messages = build_messages(prompt)

        system_content = messages[0]["content"]
        assert system_content.startswith("# CHART READER ENGINE v1")
        assert "SYSTEM CORE" in system_content
        assert "=== ANALYST PERSONA ===\nPERSONA" in system_content

    def test_skips_chart_reader_engine_when_no_images_exist(self):
        prompt = {
            "system": "SYSTEM CORE",
            "developer": "PERSONA",
            "user": "USER",
            "images": {},
        }

        messages = build_messages(prompt)

        system_content = messages[0]["content"]
        assert system_content.startswith("SYSTEM CORE")
        assert "CHART READER ENGINE" not in system_content
