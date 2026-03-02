"""Unit tests for ReasoningEngine — no external API calls."""

from datetime import datetime, timezone

import pytest

from macro_risk_officer.core.models import MacroEvent
from macro_risk_officer.core.reasoning_engine import ReasoningEngine


def _fed_surprise(tier: int = 1, actual: float = 5.5, forecast: float = 5.25) -> MacroEvent:
    return MacroEvent(
        event_id="fed-hawkish-test",
        category="monetary_policy",
        tier=tier,
        timestamp=datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc),
        actual=actual,
        forecast=forecast,
        previous=forecast,
        description="Fed rate decision (hawkish surprise)",
        source="test",
    )


def _geopolitical_escalation(tier: int = 2) -> MacroEvent:
    return MacroEvent(
        event_id="geo-escalation-test",
        category="geopolitical",
        tier=tier,
        timestamp=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        actual=1.0,
        forecast=0.0,
        previous=0.0,
        description="Geopolitical escalation event",
        source="test",
    )


class TestReasoningEngine:
    def setup_method(self):
        self.engine = ReasoningEngine()

    def test_hawkish_fed_produces_risk_off(self):
        events = [_fed_surprise()]
        ctx = self.engine.generate_context(events)
        assert ctx.regime in ("risk_off", "neutral")

    def test_hawkish_fed_pressures_nq(self):
        events = [_fed_surprise()]
        ctx = self.engine.generate_context(events)
        assert ctx.asset_pressure.NQ < 0

    def test_hawkish_fed_supports_usd(self):
        events = [_fed_surprise()]
        ctx = self.engine.generate_context(events)
        assert ctx.asset_pressure.USD > 0

    def test_negative_conflict_when_long_gold_in_risk_off(self):
        events = [_fed_surprise()]
        # Long GOLD / Short USD exposure conflicts with hawkish (USD up, GOLD down)
        exposures = {"GOLD": 1.0, "USD": -0.5}
        ctx = self.engine.generate_context(events, exposures)
        # Hawkish → GOLD pressured (negative). Long GOLD = conflict → negative score
        assert ctx.conflict_score < 0

    def test_positive_conflict_when_short_gold_in_risk_off(self):
        events = [_fed_surprise()]
        exposures = {"GOLD": -1.0, "USD": 0.5}
        ctx = self.engine.generate_context(events, exposures)
        assert ctx.conflict_score > 0

    def test_empty_events_returns_neutral(self):
        ctx = self.engine.generate_context([])
        assert ctx.regime == "neutral"
        assert ctx.confidence == 0.0

    def test_explanation_generated(self):
        events = [_fed_surprise()]
        ctx = self.engine.generate_context(events)
        assert len(ctx.explanation) > 0
        assert any("hawkish" in exp for exp in ctx.explanation)

    def test_active_event_ids_populated(self):
        events = [_fed_surprise(), _geopolitical_escalation()]
        ctx = self.engine.generate_context(events)
        assert "fed-hawkish-test" in ctx.active_event_ids
        assert "geo-escalation-test" in ctx.active_event_ids

    def test_tier1_event_sets_45d_horizon(self):
        events = [_fed_surprise(tier=1)]
        ctx = self.engine.generate_context(events)
        assert ctx.time_horizon_days == 45

    def test_tier3_only_sets_3d_horizon(self):
        events = [_fed_surprise(tier=3)]
        ctx = self.engine.generate_context(events)
        assert ctx.time_horizon_days == 3

    def test_vol_bias_expanding_with_geopolitical_stress(self):
        events = [_geopolitical_escalation(tier=1)]
        ctx = self.engine.generate_context(events)
        # Escalation → VIX up → vol expanding
        assert ctx.vol_bias in ("expanding", "neutral")

    def test_dovish_produces_risk_on(self):
        dovish = MacroEvent(
            event_id="fed-dovish-test",
            category="monetary_policy",
            tier=1,
            timestamp=datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc),
            actual=4.75,
            forecast=5.25,
            previous=5.25,
            description="Fed rate cut (dovish surprise)",
            source="test",
        )
        ctx = self.engine.generate_context([dovish])
        assert ctx.regime in ("risk_on", "neutral")
        assert ctx.asset_pressure.SPX > 0
