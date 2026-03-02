"""Unit tests for MRO Pydantic models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from macro_risk_officer.core.models import AssetPressure, MacroContext, MacroEvent


def _event(**kwargs) -> MacroEvent:
    defaults = dict(
        event_id="test-001",
        category="monetary_policy",
        tier=1,
        timestamp=datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc),
        actual=5.5,
        forecast=5.25,
        previous=5.25,
        description="Fed rate decision 5.5% vs 5.25% expected",
        source="finnhub",
    )
    defaults.update(kwargs)
    return MacroEvent(**defaults)


class TestMacroEvent:
    def test_surprise_positive(self):
        e = _event(actual=5.5, forecast=5.25)
        assert e.surprise == pytest.approx(0.25)

    def test_surprise_negative(self):
        e = _event(actual=5.0, forecast=5.25)
        assert e.surprise == pytest.approx(-0.25)

    def test_surprise_none_when_no_forecast(self):
        e = _event(actual=5.5, forecast=None)
        assert e.surprise is None

    def test_valid_tiers(self):
        for tier in (1, 2, 3):
            e = _event(tier=tier)
            assert e.tier == tier

    def test_invalid_tier(self):
        with pytest.raises(ValidationError):
            _event(tier=4)

    def test_valid_categories(self):
        for cat in ("monetary_policy", "inflation", "employment", "growth",
                    "geopolitical", "systemic_risk"):
            e = _event(category=cat)
            assert e.category == cat

    def test_invalid_category(self):
        with pytest.raises(ValidationError):
            _event(category="social_media")


class TestAssetPressure:
    def test_defaults_zero(self):
        ap = AssetPressure()
        assert ap.USD == 0.0
        assert ap.GOLD == 0.0

    def test_clamp_above(self):
        ap = AssetPressure(USD=2.0)
        assert ap.USD == 1.0

    def test_clamp_below(self):
        ap = AssetPressure(SPX=-5.0)
        assert ap.SPX == -1.0


class TestMacroContext:
    def _context(self, **kwargs):
        defaults = dict(
            regime="risk_off",
            vol_bias="expanding",
            asset_pressure=AssetPressure(USD=0.7, GOLD=0.5, SPX=-0.6),
            conflict_score=-0.62,
            confidence=0.72,
            time_horizon_days=45,
            explanation=["Tier-1 hawkish Fed surprise → USD supported"],
            active_event_ids=["fed-2026-03-19"],
        )
        defaults.update(kwargs)
        return MacroContext(**defaults)

    def test_valid_context(self):
        ctx = self._context()
        assert ctx.regime == "risk_off"
        assert ctx.conflict_score == -0.62

    def test_conflict_score_out_of_range(self):
        with pytest.raises(ValidationError):
            self._context(conflict_score=1.5)

    def test_arbiter_block_contains_key_fields(self):
        ctx = self._context()
        block = ctx.arbiter_block()
        assert "risk_off" in block
        assert "expanding" in block
        assert "GOLD" in block
        assert "advisory only" in block

    def test_invalid_regime(self):
        with pytest.raises(ValidationError):
            self._context(regime="unknown_regime")
