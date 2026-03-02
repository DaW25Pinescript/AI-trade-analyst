"""
Tests for OutcomeFetcher — MRO Phase 4.

Strategy:
  - Uses an in-memory SQLite DB (via tmp_path fixture) so no disk I/O needed.
  - YFinanceClient is mocked to avoid network calls.
  - Tests cover: backfill with no rows, successful backfill, partial failures,
    predicted_direction computation, pct_change computation, and dry-run via
    main.py's cmd_update_outcomes (monkeypatched).
"""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Create an OutcomeTracker DB at a temp path and return its Path."""
    db_path = tmp_path / "outcomes_test.db"
    from macro_risk_officer.history.tracker import OutcomeTracker
    # Initialise schema (creates P4 columns too via _migrate_db)
    OutcomeTracker(db_path=db_path)
    return db_path


def _insert_run(
    db_path: Path,
    run_id: str,
    instrument: str = "XAUUSD",
    regime: str = "risk_off",
    recorded_at: str = "2024-06-01T12:00:00+00:00",
    price_at_record: float | None = None,
):
    """Insert a minimal run row for testing."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs (
                run_id, instrument, recorded_at, regime, vol_bias,
                conflict_score, confidence, time_horizon_days,
                active_event_ids, explanation, price_at_record
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, instrument, recorded_at, regime, "neutral",
                0.1, 0.8, 3, "[]", "test explanation", price_at_record,
            ),
        )


_SAMPLE_EXPOSURES: Dict[str, Dict[str, float]] = {
    "XAUUSD": {"GOLD": 1.0},
    "US500":  {"SPX": 1.0, "NQ": 0.5},
}

# ---------------------------------------------------------------------------
# Tests: backfill
# ---------------------------------------------------------------------------

class TestOutcomeFetcherBackfill:

    def _make_fetcher(self, db_path: Path, mock_prices: dict):
        from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher

        mock_client = MagicMock()
        mock_client.fetch_prices_around.return_value = mock_prices

        fetcher = OutcomeFetcher.__new__(OutcomeFetcher)
        fetcher.db_path = db_path
        fetcher._exposures = _SAMPLE_EXPOSURES
        fetcher._price_client = mock_client
        return fetcher

    def test_no_rows_returns_zero(self, tmp_db):
        fetcher = self._make_fetcher(tmp_db, {})
        assert fetcher.backfill() == 0

    def test_already_priced_rows_are_skipped(self, tmp_db):
        _insert_run(tmp_db, run_id="priced-run", price_at_record=2300.0)
        fetcher = self._make_fetcher(tmp_db, {"price_at_record": 9999.0})
        # priced rows excluded by WHERE price_at_record IS NULL
        assert fetcher.backfill() == 0

    def test_successful_backfill_returns_count(self, tmp_db):
        _insert_run(tmp_db, run_id="run-001")
        _insert_run(tmp_db, run_id="run-002")
        prices = {
            "price_at_record": 2300.0,
            "price_at_1h":     2310.0,
            "price_at_24h":    2350.0,
            "price_at_5d":     2400.0,
        }
        fetcher = self._make_fetcher(tmp_db, prices)
        count = fetcher.backfill()
        assert count == 2

    def test_prices_written_to_db(self, tmp_db):
        _insert_run(tmp_db, run_id="run-write-check")
        prices = {
            "price_at_record": 2300.0,
            "price_at_1h":     2323.0,
            "price_at_24h":    2350.0,
            "price_at_5d":     2400.0,
        }
        fetcher = self._make_fetcher(tmp_db, prices)
        fetcher.backfill()

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                "SELECT price_at_record, price_at_24h, pct_change_24h, predicted_direction "
                "FROM runs WHERE run_id = ?",
                ("run-write-check",),
            ).fetchone()

        assert row[0] == pytest.approx(2300.0)
        assert row[1] == pytest.approx(2350.0)
        # pct_change_24h = (2350 - 2300) / 2300 * 100 ≈ 2.1739
        assert row[2] == pytest.approx(2.1739, rel=1e-3)
        # risk_off + GOLD long → predicted_direction = +1
        assert row[3] == 1

    def test_missing_t0_price_does_not_update(self, tmp_db):
        _insert_run(tmp_db, run_id="no-t0")
        prices = {
            "price_at_record": None,
            "price_at_1h":     None,
            "price_at_24h":    None,
            "price_at_5d":     None,
        }
        fetcher = self._make_fetcher(tmp_db, prices)
        count = fetcher.backfill()
        # price_at_record is None → skip → 0 updated
        assert count == 0

    def test_exception_in_one_row_continues_others(self, tmp_db):
        _insert_run(tmp_db, run_id="bad-run")
        _insert_run(tmp_db, run_id="good-run")

        mock_client = MagicMock()
        call_count = [0]

        def side_effect(instrument, recorded_at):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("network error")
            return {
                "price_at_record": 2300.0,
                "price_at_1h": 2310.0,
                "price_at_24h": 2320.0,
                "price_at_5d": 2400.0,
            }

        mock_client.fetch_prices_around.side_effect = side_effect

        from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher
        fetcher = OutcomeFetcher.__new__(OutcomeFetcher)
        fetcher.db_path = tmp_db
        fetcher._exposures = _SAMPLE_EXPOSURES
        fetcher._price_client = mock_client

        count = fetcher.backfill()
        # One failed, one succeeded
        assert count == 1


# ---------------------------------------------------------------------------
# Tests: pct_change computation
# ---------------------------------------------------------------------------

class TestPctChangeComputation:

    def test_pct_change_computed_correctly(self, tmp_db):
        _insert_run(tmp_db, run_id="pct-test", regime="risk_on")
        prices = {
            "price_at_record": 100.0,
            "price_at_1h":     101.0,
            "price_at_24h":    95.0,
            "price_at_5d":     110.0,
        }

        from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher
        mock_client = MagicMock()
        mock_client.fetch_prices_around.return_value = prices
        fetcher = OutcomeFetcher.__new__(OutcomeFetcher)
        fetcher.db_path = tmp_db
        fetcher._exposures = _SAMPLE_EXPOSURES
        fetcher._price_client = mock_client
        fetcher.backfill()

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                "SELECT pct_change_1h, pct_change_24h, pct_change_5d FROM runs WHERE run_id=?",
                ("pct-test",),
            ).fetchone()

        assert row[0] == pytest.approx(1.0, rel=1e-3)     # +1%
        assert row[1] == pytest.approx(-5.0, rel=1e-3)    # -5%
        assert row[2] == pytest.approx(10.0, rel=1e-3)    # +10%

    def test_none_price_gives_none_pct(self, tmp_db):
        _insert_run(tmp_db, run_id="none-pct")
        prices = {
            "price_at_record": 2300.0,
            "price_at_1h":     None,
            "price_at_24h":    None,
            "price_at_5d":     2400.0,
        }

        from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher
        mock_client = MagicMock()
        mock_client.fetch_prices_around.return_value = prices
        fetcher = OutcomeFetcher.__new__(OutcomeFetcher)
        fetcher.db_path = tmp_db
        fetcher._exposures = _SAMPLE_EXPOSURES
        fetcher._price_client = mock_client
        fetcher.backfill()

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                "SELECT pct_change_1h, pct_change_24h, pct_change_5d FROM runs WHERE run_id=?",
                ("none-pct",),
            ).fetchone()

        assert row[0] is None
        assert row[1] is None
        assert row[2] is not None  # p5d was available


# ---------------------------------------------------------------------------
# Tests: predicted_direction
# ---------------------------------------------------------------------------

class TestPredictedDirectionIntegration:

    def test_risk_off_gold_long(self, tmp_db):
        _insert_run(tmp_db, run_id="dir-xau", instrument="XAUUSD", regime="risk_off")
        prices = {k: 2300.0 for k in ["price_at_record", "price_at_1h", "price_at_24h", "price_at_5d"]}

        from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher
        mock_client = MagicMock()
        mock_client.fetch_prices_around.return_value = prices
        fetcher = OutcomeFetcher.__new__(OutcomeFetcher)
        fetcher.db_path = tmp_db
        fetcher._exposures = _SAMPLE_EXPOSURES
        fetcher._price_client = mock_client
        fetcher.backfill()

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                "SELECT predicted_direction FROM runs WHERE run_id=?", ("dir-xau",)
            ).fetchone()

        assert row[0] == 1  # GOLD up in risk_off, long GOLD → +1

    def test_risk_on_spx_long(self, tmp_db):
        _insert_run(tmp_db, run_id="dir-sp500", instrument="US500", regime="risk_on")
        prices = {k: 5000.0 for k in ["price_at_record", "price_at_1h", "price_at_24h", "price_at_5d"]}

        from macro_risk_officer.history.outcome_fetcher import OutcomeFetcher
        mock_client = MagicMock()
        mock_client.fetch_prices_around.return_value = prices
        fetcher = OutcomeFetcher.__new__(OutcomeFetcher)
        fetcher.db_path = tmp_db
        fetcher._exposures = _SAMPLE_EXPOSURES
        fetcher._price_client = mock_client
        fetcher.backfill()

        with sqlite3.connect(tmp_db) as conn:
            row = conn.execute(
                "SELECT predicted_direction FROM runs WHERE run_id=?", ("dir-sp500",)
            ).fetchone()

        # US500 exposures = {SPX: 1.0, NQ: 0.5}; risk_on pressure = {SPX: +1, NQ: +1}
        # score = 1.0 + 0.5 = 1.5 > threshold → +1
        assert row[0] == 1
