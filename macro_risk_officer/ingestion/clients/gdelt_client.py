"""
GDELT DOC 2.0 geopolitical event client — MRO Phase 2.

Uses the GDELT Document API (no API key required, public dataset) to derive
a geopolitical sentiment signal from recent news article tone.

Endpoint: https://api.gdeltproject.org/api/v2/doc/doc
  ?query=<q>&mode=ArtList&maxrecords=50&format=json&timespan=3d

Article tone ranges roughly from -100 (most negative) to +100 (most positive).
We aggregate average tone across all articles and map to a MacroEvent:
  avg_tone < ESCALATION_THRESHOLD  → geopolitical escalation (risk-off signal)
  avg_tone > DE_ESCALATION_THRESHOLD → geopolitical de-escalation (risk-on signal)
  otherwise                          → no event emitted (noise floor)

Rate-limit: GDELT allows roughly 1 request/second. The MacroScheduler's 30-minute
TTL ensures we stay well within limits.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from macro_risk_officer.core.models import MacroEvent

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Consolidated query: keywords relevant to FX/commodity macro trading
_QUERY = (
    "war OR conflict OR sanctions OR ceasefire "
    "OR geopolitical OR escalation OR military "
    "OR OPEC OR energy crisis OR trade war OR tariff"
)

# Tone thresholds — GDELT tone is typically in [-20, +20] for financial news
_ESCALATION_THRESHOLD = -3.0    # avg tone below this → escalation event
_DE_ESCALATION_THRESHOLD = 3.0  # avg tone above this → de-escalation event

# Minimum articles needed to trust the tone signal
_MIN_ARTICLES = 5


class GdeltClient:
    """
    Fetches geopolitical sentiment from the GDELT DOC 2.0 API.
    No API key required.
    """

    def fetch_geopolitical_events(self, lookback_days: int = 3) -> List[MacroEvent]:
        """
        Query GDELT for recent geopolitical news and derive a MacroEvent if the
        average article tone crosses the escalation/de-escalation thresholds.

        Returns an empty list when:
          - Tone signal is within noise floor (no strong signal)
          - HTTP request fails
          - Too few articles returned to trust the signal
        """
        timespan = f"{lookback_days}d"
        try:
            response = httpx.get(
                _BASE_URL,
                params={
                    "query": _QUERY,
                    "mode": "ArtList",
                    "maxrecords": 50,
                    "format": "json",
                    "timespan": timespan,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        articles = data.get("articles") or []
        tones = [
            float(a["tone"])
            for a in articles
            if isinstance(a.get("tone"), (int, float))
        ]

        if len(tones) < _MIN_ARTICLES:
            return []

        avg_tone = sum(tones) / len(tones)

        event = self._tone_to_event(avg_tone, lookback_days, article_count=len(tones))
        return [event] if event is not None else []

    def _tone_to_event(
        self, avg_tone: float, lookback_days: int, article_count: int
    ) -> Optional[MacroEvent]:
        """Map average GDELT tone to a MacroEvent, or None if within noise floor."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")
        # Stable event_id: changes at most once per calendar day
        event_id = f"gdelt-geo-{date_str}-{hashlib.md5(str(lookback_days).encode()).hexdigest()[:6]}"

        if avg_tone < _ESCALATION_THRESHOLD:
            direction_label = "escalation"
            actual = 1.0
            forecast = 0.0
        elif avg_tone > _DE_ESCALATION_THRESHOLD:
            direction_label = "de-escalation"
            actual = -1.0
            forecast = 0.0
        else:
            return None  # within noise floor — no actionable signal

        return MacroEvent(
            event_id=event_id,
            category="geopolitical",
            tier=2,
            timestamp=now,
            actual=actual,
            forecast=forecast,
            previous=0.0,
            description=(
                f"GDELT geopolitical {direction_label} signal "
                f"(avg tone {avg_tone:+.2f} over {article_count} articles, {lookback_days}d)"
            ),
            source="gdelt",
        )
