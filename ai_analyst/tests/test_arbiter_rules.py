"""
Arbiter rule tests.

Tests the prompt template and business logic enforcement rules from the spec:

1. NO_TRADE propagation: if any analyst returns NO_TRADE with confidence >= 0.6,
   the arbiter prompt states the final decision must be NO_TRADE.
2. HTF bias disagreement: arbiter prompt tells model to downgrade confidence by 30%.
3. RR threshold rejection: setups below min_rr must not be approved.
4. Open positions: tighten confidence threshold to 0.65.

Since the Arbiter logic executes inside an LLM (not in code), these tests verify:
  a) The arbiter prompt template contains the exact rule text.
  b) The arbiter prompt builder injects the correct values.
  c) The FinalVerdict schema enforces structural constraints.

Integration tests with live LLM calls belong in tests/fixtures/ based scenarios.
"""
import json
import pytest
from ..core.arbiter_prompt_builder import build_arbiter_prompt
from ..core.lens_loader import load_arbiter_template
from ..models.analyst_output import AnalystOutput, OverlayDeltaReport
from ..models.ground_truth import RiskConstraints
from macro_risk_officer.core.models import AssetPressure, MacroContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analyst(recommended_action: str, confidence: float, htf_bias: str = "bearish") -> AnalystOutput:
    return AnalystOutput(
        htf_bias=htf_bias,
        structure_state="continuation" if recommended_action != "NO_TRADE" else "undefined",
        key_levels={"premium": [], "discount": []},
        setup_valid=recommended_action != "NO_TRADE",
        setup_type="sweep_reversal" if recommended_action != "NO_TRADE" else None,
        entry_model="Pullback to FVG" if recommended_action != "NO_TRADE" else None,
        invalidation="Close above 1955" if recommended_action != "NO_TRADE" else None,
        disqualifiers=[] if recommended_action != "NO_TRADE" else ["no sweep"],
        confidence=confidence,
        rr_estimate=2.5 if recommended_action != "NO_TRADE" else None,
        notes="Test analyst output.",
        recommended_action=recommended_action,
    )


# ---------------------------------------------------------------------------
# Template content tests
# ---------------------------------------------------------------------------

class TestArbiterTemplateRules:
    """Verify the arbiter template encodes the non-negotiable rules."""

    def setup_method(self):
        self.template = load_arbiter_template()

    def test_no_trade_propagation_rule_present(self):
        """Rule 2: if ANY analyst returns NO_TRADE with confidence >= 0.6 → NO_TRADE."""
        assert "NO_TRADE" in self.template
        assert "0.6" in self.template

    def test_htf_bias_disagreement_rule_present(self):
        """Rule 3: HTF bias disagreement → downgrade confidence by 30%."""
        assert "30%" in self.template or "30" in self.template
        assert "HTF bias" in self.template or "htf" in self.template.lower()

    def test_rr_threshold_rule_present(self):
        """Rule 4: setups require median confidence >= 0.55 AND rr_estimate >= min_rr."""
        assert "0.55" in self.template
        assert "min_rr" in self.template or "rr_estimate" in self.template

    def test_open_positions_tighter_threshold_rule_present(self):
        """Rule 5: open positions → tighten confidence threshold to 0.65."""
        assert "0.65" in self.template
        assert "open_positions" in self.template or "open positions" in self.template.lower()

    def test_capital_preservation_rule_present(self):
        """Rule 1: Risk Officer persona always overrides opportunity."""
        assert "capital preservation" in self.template.lower()

    def test_no_prose_rule_present(self):
        """Output must be raw JSON only."""
        assert "Raw JSON only" in self.template or "raw JSON" in self.template.lower()


# ---------------------------------------------------------------------------
# Prompt builder injection tests
# ---------------------------------------------------------------------------

class TestArbiterPromptBuilder:
    def _build(self, analysts: list[AnalystOutput], min_rr: float = 2.0) -> str:
        return build_arbiter_prompt(
            analyst_outputs=analysts,
            risk_constraints=RiskConstraints(min_rr=min_rr),
            run_id="test-run-001",
        )

    def test_analyst_count_injected(self):
        analysts = [_make_analyst("SHORT", 0.7), _make_analyst("NO_TRADE", 0.65)]
        prompt = self._build(analysts)
        assert "2" in prompt   # N=2 injected

    def test_analyst_outputs_json_embedded(self):
        analysts = [_make_analyst("SHORT", 0.7)]
        prompt = self._build(analysts)
        # The analyst's data should appear in the prompt
        assert "SHORT" in prompt
        assert "bearish" in prompt

    def test_min_rr_injected(self):
        analysts = [_make_analyst("SHORT", 0.7)]
        prompt = self._build(analysts, min_rr=3.5)
        assert "3.5" in prompt

    def test_risk_constraints_embedded(self):
        analysts = [_make_analyst("NO_TRADE", 0.3)]
        prompt = self._build(analysts)
        assert "min_rr" in prompt or "2.0" in prompt

    def test_no_trade_analyst_embedded_in_prompt(self):
        """A NO_TRADE analyst's output is visible in the evidence section."""
        analysts = [_make_analyst("NO_TRADE", 0.65)]
        prompt = self._build(analysts)
        assert "NO_TRADE" in prompt

    def test_prompt_is_string(self):
        analysts = [_make_analyst("SHORT", 0.72), _make_analyst("LONG", 0.55)]
        prompt = self._build(analysts)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


# ---------------------------------------------------------------------------
# Minimum analyst quorum test (pipeline rule #6)
# ---------------------------------------------------------------------------

class TestMinimumAnalystQuorum:
    def test_quorum_constant_is_two(self):
        from ..graph.analyst_nodes import MINIMUM_VALID_ANALYSTS
        assert MINIMUM_VALID_ANALYSTS == 2, (
            "Design rule #6 requires minimum 2 valid analyst responses."
        )


# ---------------------------------------------------------------------------
# Overlay section injection tests
# Tests that the arbiter prompt correctly injects delta reports and
# weighting rules when a 15M ICT overlay was provided.
# ---------------------------------------------------------------------------

class TestArbiterOverlaySection:
    """
    Tests for the overlay section injected into the arbiter prompt.

    The spec defines 6 non-negotiable weighting rules that must be present
    in the arbiter prompt whenever an overlay was submitted. This class
    verifies that:
    1. The overlay section correctly declares overlay_was_provided.
    2. Delta report content is embedded verbatim in the prompt.
    3. All 6 weighting rules are present.
    4. The no-overlay fallback is correct when no overlay was submitted.
    5. The adversarial contradiction case is surfaced to the arbiter —
       this is the failure mode the spec explicitly warns against.
    """

    def _build_with_overlay(
        self,
        analysts: list[AnalystOutput],
        delta_reports: list[OverlayDeltaReport],
        min_rr: float = 2.0,
    ) -> str:
        return build_arbiter_prompt(
            analyst_outputs=analysts,
            risk_constraints=RiskConstraints(min_rr=min_rr),
            run_id="test-overlay-run-001",
            overlay_delta_reports=delta_reports,
            overlay_was_provided=True,
        )

    def _build_without_overlay(self, analysts: list[AnalystOutput]) -> str:
        return build_arbiter_prompt(
            analyst_outputs=analysts,
            risk_constraints=RiskConstraints(),
            run_id="test-no-overlay-run",
        )

    def test_overlay_section_declares_provided_true(self):
        """Prompt must state overlay_was_provided: true when overlay is provided."""
        delta = [OverlayDeltaReport(
            confirms=["FVG aligns with displacement"], refines=[], contradicts=[], indicator_only_claims=[],
        )]
        prompt = self._build_with_overlay([_make_analyst("SHORT", 0.7)], delta)
        assert "overlay_was_provided: true" in prompt

    def test_delta_content_embedded_in_prompt(self):
        """Delta report content (confirms, refines, indicator_only_claims) must be visible."""
        delta = [OverlayDeltaReport(
            confirms=["discount FVG aligns with price impulse"],
            refines=["order block boundary narrower than estimate"],
            contradicts=[],
            indicator_only_claims=["minor OB not visible in price"],
        )]
        prompt = self._build_with_overlay([_make_analyst("SHORT", 0.7)], delta)
        assert "discount FVG aligns with price impulse" in prompt
        assert "order block boundary narrower" in prompt
        assert "minor OB not visible in price" in prompt

    def test_all_six_weighting_rules_present(self):
        """All 6 overlay weighting rules must appear in the prompt when overlay is provided."""
        delta = [OverlayDeltaReport(confirms=[], refines=[], contradicts=[], indicator_only_claims=[])]
        prompt = self._build_with_overlay([_make_analyst("SHORT", 0.7)], delta)
        assert "AGREEMENT RULE" in prompt
        assert "REFINEMENT RULE" in prompt
        assert "CONTRADICTION RULE" in prompt
        assert "INDICATOR-ONLY RULE" in prompt
        assert "RISK OVERRIDE" in prompt
        assert "NO-TRADE PRIORITY" in prompt

    def test_delta_report_count_reported(self):
        """The prompt must report the number of delta reports received."""
        delta = [
            OverlayDeltaReport(confirms=["x"], refines=[], contradicts=[], indicator_only_claims=[]),
            OverlayDeltaReport(confirms=[], refines=["y"], contradicts=[], indicator_only_claims=[]),
        ]
        prompt = self._build_with_overlay(
            [_make_analyst("SHORT", 0.7), _make_analyst("WAIT", 0.55)], delta
        )
        assert "delta_reports_received: 2" in prompt

    def test_no_overlay_section_declares_provided_false(self):
        """When no overlay is provided, prompt must state overlay_was_provided: false."""
        prompt = self._build_without_overlay([_make_analyst("SHORT", 0.7)])
        assert "overlay_was_provided: false" in prompt

    def test_no_overlay_section_states_clean_price_only(self):
        """No-overlay prompt must tell the arbiter to rely on clean price only."""
        prompt = self._build_without_overlay([_make_analyst("SHORT", 0.7)])
        assert "No overlay was provided" in prompt

    def test_weighting_rules_absent_when_no_overlay(self):
        """Weighting rules must not appear in the prompt when there is no overlay."""
        prompt = self._build_without_overlay([_make_analyst("SHORT", 0.7)])
        assert "AGREEMENT RULE" not in prompt
        assert "CONTRADICTION RULE" not in prompt

    def test_adversarial_contradiction_case(self):
        """
        Adversarial case from the spec: indicator overlay strongly suggests a trade
        that clean price analysis contradicts.

        This is the failure mode the spec explicitly warns against — the system
        must never silently resolve the contradiction in favour of the indicator.

        Verifies that the arbiter prompt receives:
        - The clean price NO_TRADE verdict (from the analyst Phase 1 output)
        - The explicit contradiction from the overlay delta report
        - The CONTRADICTION RULE that mandates downgrading, not silent acceptance
        - The INDICATOR-ONLY RULE for setups not visible in price
        """
        # Clean price analysis: NO_TRADE (high-confidence, triggers Rule 2)
        clean_analyst = _make_analyst("NO_TRADE", 0.65, htf_bias="bearish")

        # Overlay delta: indicator contradicts clean price
        adversarial_delta = OverlayDeltaReport(
            confirms=[],
            refines=[],
            contradicts=["overlay marks bullish FVG but price shows no displacement above trigger level"],
            indicator_only_claims=["bullish order block visible only in overlay — not supported by price structure"],
        )

        prompt = self._build_with_overlay([clean_analyst], [adversarial_delta])

        # Clean price NO_TRADE evidence must be visible to the arbiter
        assert "NO_TRADE" in prompt
        # Overlay contradiction must be in the prompt (not silently dropped)
        assert "overlay marks bullish FVG" in prompt
        assert "bullish order block visible only in overlay" in prompt
        # Both the contradiction and indicator-only rules must be present
        assert "CONTRADICTION RULE" in prompt
        assert "INDICATOR-ONLY RULE" in prompt


# ---------------------------------------------------------------------------
# Macro section injection tests (MRO Phase 2)
# ---------------------------------------------------------------------------

class TestArbiterMacroSection:
    """
    Tests for the macro risk section injected into the arbiter prompt.

    When macro_context is provided, the arbiter receives the full arbiter_block()
    text with regime, vol_bias, conflict_score, and explanations.
    When macro_context is None (MRO unavailable), the prompt states so explicitly.
    """

    def _sample_context(self, conflict_score: float = -0.45) -> MacroContext:
        return MacroContext(
            regime="risk_off",
            vol_bias="expanding",
            asset_pressure=AssetPressure(USD=0.7, GOLD=0.5, SPX=-0.6),
            conflict_score=conflict_score,
            confidence=0.72,
            time_horizon_days=45,
            explanation=["Tier-1 hawkish Fed surprise → tighter liquidity, equities pressured."],
            active_event_ids=["finnhub-fed-2026-03"],
        )

    def _build(self, macro_context=None) -> str:
        return build_arbiter_prompt(
            analyst_outputs=[_make_analyst("SHORT", 0.7)],
            risk_constraints=RiskConstraints(),
            run_id="macro-test-run",
            macro_context=macro_context,
        )

    def test_macro_section_present_when_context_provided(self):
        """Arbiter prompt contains MACRO RISK CONTEXT header when context is given."""
        prompt = self._build(self._sample_context())
        assert "MACRO RISK CONTEXT" in prompt

    def test_regime_visible_in_prompt(self):
        """Regime value from MacroContext appears in the prompt."""
        prompt = self._build(self._sample_context())
        assert "risk_off" in prompt

    def test_vol_bias_visible_in_prompt(self):
        """Vol bias from MacroContext appears in the prompt."""
        prompt = self._build(self._sample_context())
        assert "expanding" in prompt

    def test_conflict_score_visible_in_prompt(self):
        """Negative conflict_score appears formatted in the prompt."""
        prompt = self._build(self._sample_context(conflict_score=-0.62))
        assert "-0.62" in prompt

    def test_advisory_rule_embedded_in_prompt(self):
        """The 'advisory only' enforcement rule appears in the macro section."""
        prompt = self._build(self._sample_context())
        assert "advisory only" in prompt

    def test_price_structure_precedence_rule_present(self):
        """Arbiter rule that price structure takes precedence is in the prompt."""
        prompt = self._build(self._sample_context())
        assert "price structure" in prompt.lower()

    def test_mro_unavailable_section_when_none(self):
        """When macro_context=None, prompt explicitly states MRO unavailable."""
        prompt = self._build(macro_context=None)
        assert "MRO unavailable" in prompt
        assert "macro_context_available: false" in prompt

    def test_mro_unavailable_does_not_contain_regime(self):
        """The unavailability notice must not invent a regime value."""
        prompt = self._build(macro_context=None)
        assert "risk_off" not in prompt
        assert "risk_on" not in prompt

    def test_macro_section_does_not_break_overlay_section(self):
        """
        Regression: adding macro_section must not corrupt the overlay section.
        The no-overlay text must still appear alongside the macro section.
        """
        prompt = self._build(macro_context=None)
        assert "No overlay was provided" in prompt
        assert "overlay_was_provided: false" in prompt

    def test_explanation_text_in_prompt(self):
        """The MacroContext explanation list appears in the prompt."""
        ctx = self._sample_context()
        prompt = self._build(ctx)
        assert "hawkish Fed surprise" in prompt
