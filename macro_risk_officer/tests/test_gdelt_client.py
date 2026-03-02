"""
Unit tests for GdeltClient — no real HTTP calls.

All httpx.get calls are monkeypatched with a MagicMock response.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from macro_risk_officer.ingestion.clients.gdelt_client import (
    GdeltClient,
    _ESCALATION_THRESHOLD,
    _DE_ESCALATION_THRESHOLD,
    _MIN_ARTICLES,
)
from macro_risk_officer.core.models import MacroEvent


def _make_articles(count: int, tone: float) -> list[dict]:
    return [{"url": f"http://example.com/{i}", "tone": tone, "title": f"Article {i}"}
            for i in range(count)]


def _mock_response(articles: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"articles": articles}
    resp.raise_for_status.return_value = None
    return resp


class TestGdeltClientFetch:
    def setup_method(self):
        self.client = GdeltClient()

    def test_escalation_tone_returns_event(self):
        """Tone well below threshold → escalation MacroEvent returned."""
        articles = _make_articles(10, _ESCALATION_THRESHOLD - 2.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events(lookback_days=3)
        assert len(events) == 1
        assert events[0].category == "geopolitical"
        assert events[0].actual > events[0].forecast   # escalation = positive surprise

    def test_deescalation_tone_returns_event(self):
        """Tone well above threshold → de-escalation MacroEvent returned."""
        articles = _make_articles(10, _DE_ESCALATION_THRESHOLD + 2.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events(lookback_days=3)
        assert len(events) == 1
        assert events[0].actual < events[0].forecast   # de-escalation = negative surprise

    def test_neutral_tone_returns_empty(self):
        """Tone within noise floor → no event emitted."""
        articles = _make_articles(10, 0.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events()
        assert events == []

    def test_too_few_articles_returns_empty(self):
        """Fewer than _MIN_ARTICLES → signal not trusted, no event."""
        articles = _make_articles(_MIN_ARTICLES - 1, _ESCALATION_THRESHOLD - 5.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events()
        assert events == []

    def test_http_error_returns_empty(self):
        """HTTP errors are caught and return an empty list without raising."""
        import httpx
        with patch("httpx.get", side_effect=httpx.HTTPError("timeout")):
            events = self.client.fetch_geopolitical_events()
        assert events == []

    def test_missing_articles_key_returns_empty(self):
        """Response with no 'articles' key returns empty list."""
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status.return_value = None
        with patch("httpx.get", return_value=resp):
            events = self.client.fetch_geopolitical_events()
        assert events == []

    def test_event_id_is_stable_for_same_day(self):
        """Event ID is deterministic within the same calendar day."""
        articles = _make_articles(10, _ESCALATION_THRESHOLD - 1.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events1 = self.client.fetch_geopolitical_events(lookback_days=3)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events2 = self.client.fetch_geopolitical_events(lookback_days=3)
        assert events1[0].event_id == events2[0].event_id

    def test_event_source_is_gdelt(self):
        """Returned event has source='gdelt'."""
        articles = _make_articles(10, _ESCALATION_THRESHOLD - 1.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events()
        assert events[0].source == "gdelt"

    def test_event_tier_is_2(self):
        """GDELT events are classified as Tier 2."""
        articles = _make_articles(10, _ESCALATION_THRESHOLD - 1.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events()
        assert events[0].tier == 2

    def test_articles_missing_tone_field_are_skipped(self):
        """Articles without a numeric tone field are excluded from averaging."""
        # 4 articles without tone (below _MIN_ARTICLES) + bad tone values
        articles = [{"url": f"http://example.com/{i}", "title": "no tone"} for i in range(20)]
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = self.client.fetch_geopolitical_events()
        assert events == []  # no valid tones → skipped


class TestGdeltIntegrationWithReasoningEngine:
    """Verify GDELT events flow correctly through the ReasoningEngine."""

    def test_escalation_event_bids_gold(self):
        """Geopolitical escalation from GDELT should pressure GOLD upward."""
        from macro_risk_officer.core.reasoning_engine import ReasoningEngine
        from macro_risk_officer.ingestion.normalizer import normalise_events

        client = GdeltClient()
        articles = _make_articles(10, _ESCALATION_THRESHOLD - 2.0)
        with patch("httpx.get", return_value=_mock_response(articles)):
            events = client.fetch_geopolitical_events()

        normalised = normalise_events(events)
        engine = ReasoningEngine()
        ctx = engine.generate_context(normalised)

        assert ctx.asset_pressure.GOLD > 0
        assert ctx.asset_pressure.VIX > 0
