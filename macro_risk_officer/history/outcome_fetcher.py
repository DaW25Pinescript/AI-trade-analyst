"""
OutcomeFetcher — MRO Phase 4.

Backfills price outcome data for runs that have been recorded in the
OutcomeTracker DB but do not yet have price snapshots.

Usage (via CLI):
    python -m macro_risk_officer update-outcomes

Design:
  - Queries the DB for all runs where price_at_record IS NULL.
  - For each, calls YFinanceClient.fetch_prices_around().
  - Computes pct_change columns from fetched prices.
  - Computes predicted_direction based on regime + instrument exposures.
  - Updates the DB row in-place.
  - Fails silently per run — one unavailable symbol never blocks the others.

Regime accuracy scoring:
  A "correct" prediction is when the sign of pct_change_24h matches
  predicted_direction (+1=up, -1=down). Neutral (0) predictions are
  excluded from accuracy calculations.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Expected asset pressure direction per regime.
# +1 = asset tends to rise; -1 = asset tends to fall.
_REGIME_ASSET_PRESSURE: Dict[str, Dict[str, int]] = {
    "risk_off": {
        "SPX": -1, "NQ": -1, "GOLD": +1,
        "USD": +1, "OIL": -1, "VIX": +1, "T10Y": +1,
    },
    "risk_on": {
        "SPX": +1, "NQ": +1, "GOLD": -1,
        "USD": -1, "OIL": +1, "VIX": -1, "T10Y": -1,
    },
    "neutral": {},
}

_DIRECTION_THRESHOLD = 0.05   # ignore near-zero predicted scores


def predicted_direction(
    regime: str, exposures: Dict[str, float]
) -> int:
    """
    Return +1 (expect up), -1 (expect down), or 0 (ambiguous) for an instrument
    in the given macro regime.

    Args:
        regime    : "risk_off", "risk_on", or "neutral".
        exposures : {asset: directional_exposure} from weights.yaml
                    (e.g. {"GOLD": 1.0, "USD": -0.5} for XAUUSD long).
    """
    asset_pressure = _REGIME_ASSET_PRESSURE.get(regime, {})
    score = sum(
        asset_pressure.get(asset, 0) * weight
        for asset, weight in exposures.items()
    )
    if score > _DIRECTION_THRESHOLD:
        return +1
    if score < -_DIRECTION_THRESHOLD:
        return -1
    return 0


class OutcomeFetcher:
    """
    Backfills price outcomes for un-priced runs in the OutcomeTracker DB.
    """

    def __init__(self, db_path: Path, instrument_exposures: Dict[str, Dict[str, float]]) -> None:
        self.db_path = db_path
        self._exposures = instrument_exposures

        # Lazy import to keep yfinance a soft dependency
        from macro_risk_officer.ingestion.clients.price_client import YFinanceClient
        self._price_client = YFinanceClient()

    def backfill(self) -> int:
        """
        Fetch prices for all runs missing price_at_record.

        Returns:
            Number of rows successfully updated.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT run_id, instrument, recorded_at, regime "
                "FROM runs WHERE price_at_record IS NULL"
            ).fetchall()

        updated = 0
        for row in rows:
            try:
                n = self._process_row(
                    run_id=row["run_id"],
                    instrument=row["instrument"],
                    recorded_at_iso=row["recorded_at"],
                    regime=row["regime"],
                )
                updated += n
            except Exception as exc:
                logger.warning(
                    "OutcomeFetcher: failed for run_id=%s (%s)", row["run_id"][:8], exc
                )

        return updated

    # ── Private ──────────────────────────────────────────────────────────────

    def _process_row(
        self, run_id: str, instrument: str, recorded_at_iso: str, regime: str
    ) -> int:
        """Fetch prices, compute metrics, update DB. Returns 1 on success, 0 on skip."""
        recorded_at = datetime.fromisoformat(recorded_at_iso)
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)

        prices = self._price_client.fetch_prices_around(instrument, recorded_at)

        p0 = prices.get("price_at_record")
        if p0 is None:
            logger.debug("No T+0 price for run_id=%s instrument=%s", run_id[:8], instrument)
            return 0

        p1h  = prices.get("price_at_1h")
        p24h = prices.get("price_at_24h")
        p5d  = prices.get("price_at_5d")

        def pct(px: Optional[float]) -> Optional[float]:
            if px is None or p0 == 0:
                return None
            return round((px - p0) / p0 * 100, 4)

        pct_1h  = pct(p1h)
        pct_24h = pct(p24h)
        pct_5d  = pct(p5d)

        exposures = self._exposures.get(instrument.upper(), {})
        pred_dir = predicted_direction(regime, exposures)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE runs SET
                    price_at_record    = ?,
                    price_at_1h        = ?,
                    price_at_24h       = ?,
                    price_at_5d        = ?,
                    pct_change_1h      = ?,
                    pct_change_24h     = ?,
                    pct_change_5d      = ?,
                    predicted_direction = ?
                WHERE run_id = ?
                """,
                (p0, p1h, p24h, p5d, pct_1h, pct_24h, pct_5d, pred_dir, run_id),
            )

        logger.info(
            "MRO outcome: run=%s %s regime=%s pred=%+d pct_24h=%s",
            run_id[:8], instrument, regime, pred_dir,
            f"{pct_24h:+.2f}%" if pct_24h is not None else "N/A",
        )
        return 1
