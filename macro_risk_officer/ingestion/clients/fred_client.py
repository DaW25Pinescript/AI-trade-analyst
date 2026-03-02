"""
FRED (Federal Reserve Economic Data) client.

Fetches key macro time series to provide historical context alongside
Finnhub's event calendar.
Requires: FRED_API_KEY environment variable.

Series tracked:
  DFF      — Effective Federal Funds Rate (monetary policy level)
  T10Y2Y   — 10Y-2Y yield spread (inversion = recession signal)
  CPIAUCSL — CPI All Urban Consumers (inflation level)
  UNRATE   — Unemployment Rate (employment level)
  DCOILWTICO — WTI Crude Oil Price (growth/inflation proxy)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import httpx

from macro_risk_officer.core.models import MacroEvent

_BASE_URL = "https://api.stlouisfed.org/fred"

_SERIES = {
    "DFF": ("monetary_policy", 1),
    "T10Y2Y": ("systemic_risk", 2),
    "CPIAUCSL": ("inflation", 1),
    "UNRATE": ("employment", 2),
    "DCOILWTICO": ("growth", 3),
}

_SERIES_DESCRIPTIONS = {
    "DFF": "Effective Federal Funds Rate (current vs prior month)",
    "T10Y2Y": "10Y-2Y Treasury Yield Spread (inversion signal)",
    "CPIAUCSL": "CPI All Urban Consumers (inflation momentum)",
    "UNRATE": "Unemployment Rate (employment momentum)",
    "DCOILWTICO": "WTI Crude Oil Price (growth/inflation proxy)",
}


class FredClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY not set. Add it to your environment or .env file."
            )

    def fetch_latest(self, series_id: str, n_obs: int = 2) -> List[Dict]:
        """Fetch the last n observations for a FRED series."""
        response = httpx.get(
            f"{_BASE_URL}/series/observations",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": n_obs,
                "observation_end": datetime.utcnow().strftime("%Y-%m-%d"),
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json().get("observations", [])

    def fetch_macro_snapshot(self) -> Dict[str, Optional[Tuple[float, float]]]:
        """
        Return a dict of {series_id: (latest_value, previous_value)} for all
        tracked series. None if data unavailable.
        """
        snapshot: Dict[str, Optional[Tuple[float, float]]] = {}
        for series_id in _SERIES:
            try:
                obs = self.fetch_latest(series_id, n_obs=2)
                values = [
                    float(o["value"]) for o in obs if o.get("value") not in (".", None)
                ]
                if len(values) >= 2:
                    snapshot[series_id] = (values[0], values[1])
                elif len(values) == 1:
                    snapshot[series_id] = (values[0], values[0])
                else:
                    snapshot[series_id] = None
            except Exception:
                snapshot[series_id] = None
        return snapshot

    def to_macro_events(self) -> List[MacroEvent]:
        """
        Convert FRED snapshot into MacroEvents for the ReasoningEngine.

        FRED provides current vs previous readings rather than actual vs
        consensus forecast. We treat:
          actual   = current value  (most recent release)
          forecast = previous value (prior reading used as baseline)
          surprise = current - previous  (momentum direction signal)

        This is a valid macro signal — e.g. DFF rising month-on-month is a
        tightening impulse regardless of whether the market expected it.
        """
        snapshot = self.fetch_macro_snapshot()
        events: List[MacroEvent] = []
        now = datetime.utcnow()

        for series_id, pair in snapshot.items():
            if pair is None:
                continue
            current, previous = pair
            category, tier = self.series_metadata(series_id)
            events.append(
                MacroEvent(
                    event_id=f"fred-{series_id}-{now.strftime('%Y%m%d')}",
                    category=category,
                    tier=tier,
                    timestamp=datetime(now.year, now.month, 1),  # monthly release anchor
                    actual=current,
                    forecast=previous,
                    previous=previous,
                    description=_SERIES_DESCRIPTIONS.get(series_id, series_id),
                    source="fred",
                )
            )
        return events

    @staticmethod
    def series_metadata(series_id: str) -> Tuple[str, int]:
        """Return (category, tier) for a FRED series ID."""
        return _SERIES.get(series_id, ("growth", 3))
