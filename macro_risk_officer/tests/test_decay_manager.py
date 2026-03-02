"""Unit tests for DecayManager."""

from datetime import datetime, timedelta, timezone

import pytest

from macro_risk_officer.core.decay_manager import DecayManager
from macro_risk_officer.core.models import MacroEvent


def _event_aged(hours: float, tier: int = 1) -> MacroEvent:
    ts = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(hours=hours)
    return MacroEvent(
        event_id=f"decay-test-{tier}-{hours}h",
        category="monetary_policy",
        tier=tier,
        timestamp=ts,
        actual=5.5,
        forecast=5.25,
        previous=5.25,
        description="Test event",
        source="test",
    )


class TestDecayManager:
    def setup_method(self):
        self.dm = DecayManager()

    def test_fresh_event_near_1(self):
        event = _event_aged(0.1)
        factor = self.dm.get_decay_factor(event)
        assert factor > 0.99

    def test_old_tier1_still_has_weight(self):
        event = _event_aged(336, tier=1)  # 2 weeks
        factor = self.dm.get_decay_factor(event)
        assert factor > 0.05

    def test_tier3_decays_faster_than_tier1(self):
        event_t1 = _event_aged(48, tier=1)
        event_t3 = _event_aged(48, tier=3)
        assert self.dm.get_decay_factor(event_t1) > self.dm.get_decay_factor(event_t3)

    def test_min_floor_enforced(self):
        event = _event_aged(10000, tier=3)  # ancient
        factor = self.dm.get_decay_factor(event)
        assert factor >= 0.05

    def test_decay_monotonically_decreases(self):
        ages = [1, 12, 24, 48, 96]
        factors = [self.dm.get_decay_factor(_event_aged(h)) for h in ages]
        for i in range(len(factors) - 1):
            assert factors[i] > factors[i + 1]
