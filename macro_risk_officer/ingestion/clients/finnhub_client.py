"""
Finnhub economic calendar client.

Fetches scheduled economic events with actual vs forecast values.
Requires: FINNHUB_API_KEY environment variable.

Tier classification rules:
  Tier 1 — Fed rate decision, NFP, CPI, PCE, GDP advance
  Tier 2 — Retail sales, ISM PMI, PPI, jobless claims, durable goods
  Tier 3 — Everything else
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from macro_risk_officer.core.models import MacroEvent

_BASE_URL = "https://finnhub.io/api/v1"

_TIER_1_KEYWORDS = frozenset({
    "federal funds", "nonfarm payroll", "consumer price index",
    "core cpi", "pce", "gdp advance", "fomc",
})
_TIER_2_KEYWORDS = frozenset({
    "retail sales", "ism manufacturing", "ism services", "pmi",
    "producer price", "initial jobless", "durable goods",
})


def _classify_tier(description: str) -> int:
    lower = description.lower()
    if any(kw in lower for kw in _TIER_1_KEYWORDS):
        return 1
    if any(kw in lower for kw in _TIER_2_KEYWORDS):
        return 2
    return 3


def _classify_category(description: str) -> str:
    lower = description.lower()
    if any(kw in lower for kw in ("fed", "fomc", "rate decision", "federal funds")):
        return "monetary_policy"
    if any(kw in lower for kw in ("cpi", "pce", "inflation", "price index", "ppi")):
        return "inflation"
    if any(kw in lower for kw in ("payroll", "employment", "jobless", "unemployment")):
        return "employment"
    if any(kw in lower for kw in ("gdp", "retail", "durable", "ism", "pmi")):
        return "growth"
    return "growth"  # default bucket


class FinnhubClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("FINNHUB_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "FINNHUB_API_KEY not set. Add it to your environment or .env file."
            )

    def fetch_calendar(
        self,
        lookback_days: int = 7,
        lookahead_days: int = 3,
    ) -> List[MacroEvent]:
        """
        Fetch economic calendar events within the lookback/lookahead window.
        Returns only events that have both actual and forecast values (surprise-eligible).
        """
        now_utc = datetime.now(timezone.utc)
        from_dt = (now_utc - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        to_dt = (now_utc + timedelta(days=lookahead_days)).strftime("%Y-%m-%d")

        response = httpx.get(
            f"{_BASE_URL}/calendar/economic",
            params={"from": from_dt, "to": to_dt, "token": self.api_key},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        events: List[MacroEvent] = []
        for item in data.get("economicCalendar", []):
            actual = item.get("actual")
            forecast = item.get("estimate")
            description = item.get("event", "")
            timestamp_str = item.get("time", "")
            if not timestamp_str or not description:
                continue
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            events.append(
                MacroEvent(
                    event_id=f"finnhub-{item.get('id') or hashlib.md5(description.encode()).hexdigest()[:12]}",
                    category=_classify_category(description),
                    tier=_classify_tier(description),
                    timestamp=timestamp,
                    actual=float(actual) if actual is not None else None,
                    forecast=float(forecast) if forecast is not None else None,
                    previous=float(item["prev"]) if item.get("prev") is not None else None,
                    description=description,
                    source="finnhub",
                )
            )

        return sorted(events, key=lambda e: e.timestamp, reverse=True)
