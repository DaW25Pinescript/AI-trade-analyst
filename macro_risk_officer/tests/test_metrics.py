"""
Unit tests for MRO Phase 4 KPI telemetry:
  - SchedulerMetrics (in-process counters)
  - FetchLog (SQLite-backed persistent telemetry)
  - KpiReport (KPI computation and formatting)
  - MacroScheduler metrics integration (wired counters)

All SQLite tests use tmp_path-scoped DBs to avoid touching the real data/ DB.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from macro_risk_officer.history.metrics import FetchLog, KpiReport, SchedulerMetrics


# ── SchedulerMetrics ───────────────────────────────────────────────────────────


class TestSchedulerMetrics:
    def test_initial_state(self):
        m = SchedulerMetrics()
        assert m.cache_hits == 0
        assert m.cache_misses == 0
        assert m.fetch_successes == 0
        assert m.fetch_failures == 0

    def test_cache_hit_ratio_none_when_no_calls(self):
        m = SchedulerMetrics()
        assert m.cache_hit_ratio is None

    def test_cache_hit_ratio_all_hits(self):
        m = SchedulerMetrics(cache_hits=8, cache_misses=0)
        # 8/(8+0) — but misses=0 so ratio=1.0
        assert m.cache_hit_ratio == pytest.approx(1.0)

    def test_cache_hit_ratio_mixed(self):
        m = SchedulerMetrics(cache_hits=3, cache_misses=1)
        assert m.cache_hit_ratio == pytest.approx(0.75)

    def test_macro_availability_none_when_no_fetches(self):
        m = SchedulerMetrics()
        assert m.macro_availability_pct is None

    def test_macro_availability_all_success(self):
        m = SchedulerMetrics(fetch_successes=10, fetch_failures=0)
        assert m.macro_availability_pct == pytest.approx(100.0)

    def test_macro_availability_partial(self):
        m = SchedulerMetrics(fetch_successes=4, fetch_failures=1)
        assert m.macro_availability_pct == pytest.approx(80.0)

    def test_context_age_none_when_never_fetched(self):
        m = SchedulerMetrics()
        assert m.context_age_seconds() is None

    def test_context_age_positive_after_fetch(self):
        m = SchedulerMetrics()
        m.last_fetch_epoch = time.monotonic() - 5.0
        age = m.context_age_seconds()
        assert age is not None
        assert age >= 4.0  # at least ~5 s since set

    def test_increment_pattern(self):
        m = SchedulerMetrics()
        m.cache_hits += 1
        m.cache_misses += 1
        m.fetch_successes += 1
        assert m.cache_hit_ratio == pytest.approx(0.5)
        assert m.macro_availability_pct == pytest.approx(100.0)


# ── FetchLog ──────────────────────────────────────────────────────────────────


class TestFetchLog:
    def test_table_created_on_init(self, tmp_path: Path):
        log = FetchLog(db_path=tmp_path / "test.db")
        import sqlite3
        conn = sqlite3.connect(tmp_path / "test.db")
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        assert any("fetch_log" in t[0] for t in tables)

    def test_record_success_writes_row(self, tmp_path: Path):
        log = FetchLog(db_path=tmp_path / "test.db")
        log.record_success(source_mask="fred,gdelt", event_count=7)

        import sqlite3
        conn = sqlite3.connect(tmp_path / "test.db")
        row = conn.execute("SELECT * FROM fetch_log").fetchone()
        conn.close()
        assert row is not None
        # success=1, source_mask="fred,gdelt", event_count=7
        assert row[2] == 1
        assert row[3] == "fred,gdelt"
        assert row[4] == 7

    def test_record_failure_writes_row(self, tmp_path: Path):
        log = FetchLog(db_path=tmp_path / "test.db")
        log.record_failure("RuntimeError")

        import sqlite3
        conn = sqlite3.connect(tmp_path / "test.db")
        row = conn.execute("SELECT * FROM fetch_log").fetchone()
        conn.close()
        assert row[2] == 0
        assert row[5] == "RuntimeError"

    def test_multiple_records(self, tmp_path: Path):
        log = FetchLog(db_path=tmp_path / "test.db")
        log.record_success("finnhub,fred", 5)
        log.record_success("fred", 3)
        log.record_failure("ConnectError")

        import sqlite3
        conn = sqlite3.connect(tmp_path / "test.db")
        count = conn.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0]
        conn.close()
        assert count == 3

    def test_error_hint_truncated_at_120_chars(self, tmp_path: Path):
        log = FetchLog(db_path=tmp_path / "test.db")
        long_hint = "X" * 200
        log.record_failure(long_hint)

        import sqlite3
        conn = sqlite3.connect(tmp_path / "test.db")
        hint = conn.execute("SELECT error_hint FROM fetch_log").fetchone()[0]
        conn.close()
        assert len(hint) <= 120

    def test_creates_parent_directories(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "c" / "test.db"
        assert not nested.parent.exists()
        log = FetchLog(db_path=nested)
        log.record_success("gdelt", 1)
        assert nested.exists()


# ── KpiReport ─────────────────────────────────────────────────────────────────


class TestKpiReport:
    def _log_with_data(self, tmp_path: Path, successes: int, failures: int) -> Path:
        db = tmp_path / "test.db"
        log = FetchLog(db_path=db)
        for i in range(successes):
            log.record_success(f"source{i % 2}", i + 1)
        for _ in range(failures):
            log.record_failure("SomeError")
        return db

    def test_from_db_no_data(self, tmp_path: Path):
        db = tmp_path / "empty.db"
        report = KpiReport.from_db(db_path=db)
        assert report.total == 0
        assert report.successes == 0
        assert report.availability_pct is None

    def test_from_db_all_success(self, tmp_path: Path):
        db = self._log_with_data(tmp_path, successes=5, failures=0)
        report = KpiReport.from_db(db_path=db)
        assert report.total == 5
        assert report.successes == 5
        assert report.availability_pct == pytest.approx(100.0)

    def test_from_db_partial_success(self, tmp_path: Path):
        db = self._log_with_data(tmp_path, successes=4, failures=1)
        report = KpiReport.from_db(db_path=db)
        assert report.total == 5
        assert report.availability_pct == pytest.approx(80.0)

    def test_format_contains_availability(self, tmp_path: Path):
        db = self._log_with_data(tmp_path, successes=8, failures=2)
        report = KpiReport.from_db(db_path=db)
        text = report.format()
        assert "Macro availability" in text
        assert "80.0%" in text

    def test_format_gate_pass(self, tmp_path: Path):
        db = self._log_with_data(tmp_path, successes=9, failures=1)
        report = KpiReport.from_db(db_path=db)
        text = report.format()
        assert "PASS" in text

    def test_format_gate_fail(self, tmp_path: Path):
        db = self._log_with_data(tmp_path, successes=3, failures=7)
        report = KpiReport.from_db(db_path=db)
        text = report.format()
        assert "FAIL" in text

    def test_format_pending_when_no_data(self, tmp_path: Path):
        db = tmp_path / "empty.db"
        report = KpiReport.from_db(db_path=db)
        text = report.format()
        assert "PENDING" in text

    def test_format_contains_freshness(self, tmp_path: Path):
        db = self._log_with_data(tmp_path, successes=1, failures=0)
        report = KpiReport.from_db(db_path=db)
        text = report.format()
        assert "freshness" in text.lower() or "FRESH" in text or "STALE" in text

    def test_error_breakdown_present_on_failures(self, tmp_path: Path):
        db = tmp_path / "test.db"
        log = FetchLog(db_path=db)
        log.record_failure("ConnectionError")
        log.record_failure("ConnectionError")
        log.record_failure("TimeoutError")
        report = KpiReport.from_db(db_path=db)
        text = report.format()
        assert "FAILURE CAUSES" in text
        assert "ConnectionError" in text


# ── MacroScheduler metrics integration ────────────────────────────────────────


class TestSchedulerMetricsIntegration:
    """Verify MacroScheduler properly increments metrics on each get_context() path."""

    def _mock_context(self):
        from macro_risk_officer.core.models import AssetPressure, MacroContext
        return MacroContext(
            regime="neutral",
            vol_bias="neutral",
            asset_pressure=AssetPressure(),
            conflict_score=0.0,
            confidence=0.5,
            time_horizon_days=30,
            explanation=["test"],
            active_event_ids=["test-001"],
        )

    def test_cache_miss_on_first_call(self):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        ctx = self._mock_context()
        with patch.object(scheduler, "_refresh", return_value=(ctx, "test", 1)):
            scheduler.get_context()
        assert scheduler.metrics.cache_misses == 1
        assert scheduler.metrics.cache_hits == 0

    def test_cache_hit_on_second_call(self):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        ctx = self._mock_context()
        with patch.object(scheduler, "_refresh", return_value=(ctx, "test", 1)):
            scheduler.get_context()
            scheduler.get_context()
        assert scheduler.metrics.cache_hits == 1
        assert scheduler.metrics.cache_misses == 1

    def test_fetch_success_incremented(self):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        ctx = self._mock_context()
        with patch.object(scheduler, "_refresh", return_value=(ctx, "test", 1)):
            scheduler.get_context()
        assert scheduler.metrics.fetch_successes == 1
        assert scheduler.metrics.fetch_failures == 0

    def test_fetch_failure_incremented_when_refresh_raises(self):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        with patch.object(scheduler, "_refresh", side_effect=RuntimeError("no sources")):
            result = scheduler.get_context()
        assert result is None
        assert scheduler.metrics.fetch_failures == 1
        assert scheduler.metrics.fetch_successes == 0

    def test_fetch_log_written_on_success(self, tmp_path: Path):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        db = tmp_path / "test.db"
        scheduler = MacroScheduler(enable_fetch_log=False)
        scheduler._fetch_log = FetchLog(db_path=db)
        ctx = self._mock_context()
        with patch.object(scheduler, "_refresh", return_value=(ctx, "fred", 3)):
            scheduler.get_context()

        import sqlite3
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT success, source_mask, event_count FROM fetch_log").fetchone()
        conn.close()
        assert row[0] == 1
        assert row[1] == "fred"
        assert row[2] == 3

    def test_fetch_log_written_on_failure(self, tmp_path: Path):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        db = tmp_path / "test.db"
        scheduler = MacroScheduler(enable_fetch_log=False)
        scheduler._fetch_log = FetchLog(db_path=db)
        with patch.object(scheduler, "_refresh", side_effect=RuntimeError("no events")):
            scheduler.get_context()

        import sqlite3
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT success, error_hint FROM fetch_log").fetchone()
        conn.close()
        assert row[0] == 0
        assert "RuntimeError" in row[1]

    def test_metrics_property_returns_same_instance(self):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        assert scheduler.metrics is scheduler._metrics

    def test_invalidate_causes_cache_miss(self):
        from macro_risk_officer.ingestion.scheduler import MacroScheduler

        scheduler = MacroScheduler(enable_fetch_log=False)
        ctx = self._mock_context()
        with patch.object(scheduler, "_refresh", return_value=(ctx, "test", 1)):
            scheduler.get_context()   # miss → success
            scheduler.invalidate()
            scheduler.get_context()   # miss again after invalidate
        assert scheduler.metrics.cache_misses == 2
        assert scheduler.metrics.fetch_successes == 2


# ── CLI kpi command smoke ─────────────────────────────────────────────────────


class TestKpiCommand:
    def test_cmd_kpi_prints_report_header(self, capsys, tmp_path: Path):
        from macro_risk_officer.main import cmd_kpi
        from macro_risk_officer.history.metrics import FetchLog, KpiReport

        # Seed a fetch log entry so we get a non-empty report
        db = tmp_path / "outcomes.db"
        log = FetchLog(db_path=db)
        log.record_success("fred", 3)

        # Patch at the correct import location (inside history.metrics)
        with patch(
            "macro_risk_officer.history.metrics.KpiReport.from_db",
            return_value=KpiReport.from_db(db_path=db),
        ):
            cmd_kpi()

        captured = capsys.readouterr()
        assert "MRO KPI REPORT" in captured.out
        assert "RELEASE GATE" in captured.out

    def test_module_kpi_subcommand_help(self):
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "macro_risk_officer", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "kpi" in result.stdout
