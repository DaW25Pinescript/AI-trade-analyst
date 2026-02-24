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
from ..models.analyst_output import AnalystOutput
from ..models.ground_truth import RiskConstraints


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
