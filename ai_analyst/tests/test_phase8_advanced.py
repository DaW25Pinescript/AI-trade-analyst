"""
Phase 8 — Advanced Analytics, Backtesting, E2E Validation, and Plugin Architecture test suite.

Tests:
  8a. Analytics dashboard — data builder + HTML renderer
  8b. Backtesting engine — Sharpe, drawdown, win rate, regime breakdown
  8c. E2E integration validator — smoke tests
  8d. Plugin registry — discovery, registration, manifest loading
"""

import json
import math
import sqlite3
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Shared helpers ───────────────────────────────────────────────────────────


def _create_test_db(tmp_path: Path, runs: list[dict] | None = None) -> Path:
    """Create a test outcomes.db with default or custom run records."""
    db_path = tmp_path / "outcomes.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id               TEXT    NOT NULL UNIQUE,
            instrument           TEXT    NOT NULL,
            recorded_at          TEXT    NOT NULL,
            regime               TEXT    NOT NULL,
            vol_bias             TEXT    NOT NULL,
            conflict_score       REAL    NOT NULL,
            confidence           REAL    NOT NULL,
            time_horizon_days    INTEGER NOT NULL,
            active_event_ids     TEXT    NOT NULL,
            explanation          TEXT    NOT NULL,
            decision             TEXT,
            overall_confidence   REAL,
            analyst_agreement    INTEGER,
            risk_override        INTEGER,
            price_at_record      REAL,
            price_at_1h          REAL,
            price_at_24h         REAL,
            price_at_5d          REAL,
            pct_change_1h        REAL,
            pct_change_24h       REAL,
            pct_change_5d        REAL,
            predicted_direction  INTEGER
        )
    """)

    if runs is None:
        runs = _default_test_runs()

    for r in runs:
        conn.execute(
            "INSERT INTO runs (run_id, instrument, recorded_at, regime, vol_bias, "
            "conflict_score, confidence, time_horizon_days, active_event_ids, explanation, "
            "decision, overall_confidence, analyst_agreement, risk_override, "
            "price_at_record, price_at_24h, predicted_direction, pct_change_24h) "
            "VALUES (:run_id, :instrument, :recorded_at, :regime, :vol_bias, "
            ":conflict_score, :confidence, :time_horizon_days, '[]', '[]', "
            ":decision, :overall_confidence, :analyst_agreement, :risk_override, "
            ":price_at_record, :price_at_24h, :predicted_direction, :pct_change_24h)",
            r,
        )

    conn.commit()
    conn.close()
    return db_path


def _default_test_runs() -> list[dict]:
    return [
        {"run_id": "t-001", "instrument": "XAUUSD", "recorded_at": "2026-03-01T10:00:00Z",
         "regime": "risk_on", "vol_bias": "normal", "conflict_score": 0.2,
         "confidence": 0.7, "time_horizon_days": 5,
         "decision": "ENTER_LONG", "overall_confidence": 0.72, "analyst_agreement": 80,
         "risk_override": 0, "price_at_record": 2000.0, "price_at_24h": 2010.0,
         "predicted_direction": 1, "pct_change_24h": 0.5},
        {"run_id": "t-002", "instrument": "XAUUSD", "recorded_at": "2026-03-01T14:00:00Z",
         "regime": "risk_on", "vol_bias": "normal", "conflict_score": 0.3,
         "confidence": 0.8, "time_horizon_days": 5,
         "decision": "ENTER_LONG", "overall_confidence": 0.81, "analyst_agreement": 90,
         "risk_override": 0, "price_at_record": 2010.0, "price_at_24h": 2025.0,
         "predicted_direction": 1, "pct_change_24h": 0.75},
        {"run_id": "t-003", "instrument": "EURUSD", "recorded_at": "2026-03-02T10:00:00Z",
         "regime": "risk_off", "vol_bias": "elevated", "conflict_score": 0.6,
         "confidence": 0.5, "time_horizon_days": 3,
         "decision": "ENTER_SHORT", "overall_confidence": 0.55, "analyst_agreement": 65,
         "risk_override": 0, "price_at_record": 1.0800, "price_at_24h": 1.0750,
         "predicted_direction": -1, "pct_change_24h": -0.46},
        {"run_id": "t-004", "instrument": "XAUUSD", "recorded_at": "2026-03-02T14:00:00Z",
         "regime": "neutral", "vol_bias": "normal", "conflict_score": 0.4,
         "confidence": 0.6, "time_horizon_days": 5,
         "decision": "ENTER_LONG", "overall_confidence": 0.62, "analyst_agreement": 70,
         "risk_override": 0, "price_at_record": 2020.0, "price_at_24h": 2010.0,
         "predicted_direction": 1, "pct_change_24h": -0.50},
        {"run_id": "t-005", "instrument": "EURUSD", "recorded_at": "2026-03-03T10:00:00Z",
         "regime": "risk_off", "vol_bias": "elevated", "conflict_score": 0.7,
         "confidence": 0.4, "time_horizon_days": 3,
         "decision": "NO_TRADE", "overall_confidence": 0.42, "analyst_agreement": 50,
         "risk_override": 0, "price_at_record": 1.0750, "price_at_24h": 1.0780,
         "predicted_direction": 0, "pct_change_24h": 0.28},
        {"run_id": "t-006", "instrument": "XAUUSD", "recorded_at": "2026-03-03T14:00:00Z",
         "regime": "risk_on", "vol_bias": "normal", "conflict_score": 0.2,
         "confidence": 0.9, "time_horizon_days": 5,
         "decision": "ENTER_LONG", "overall_confidence": 0.88, "analyst_agreement": 95,
         "risk_override": 0, "price_at_record": 2030.0, "price_at_24h": 2050.0,
         "predicted_direction": 1, "pct_change_24h": 0.99},
    ]


# ==========================================================================
# 8a — Advanced Analytics Dashboard
# ==========================================================================


class TestAnalyticsDashboardData:
    """Test analytics data builder."""

    def test_build_with_data(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        assert data.total_runs == 6
        assert data.priced_runs > 0

    def test_regime_chart_populated(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        assert len(data.regime_chart.labels) > 0
        assert len(data.regime_chart.accuracy) == len(data.regime_chart.labels)
        assert len(data.regime_chart.no_trade_pct) == len(data.regime_chart.labels)

    def test_calibration_buckets(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        assert len(data.calibration) == 3  # low, mid, high
        for cal in data.calibration:
            assert 0 <= cal.actual_accuracy <= 100
            assert cal.count >= 0

    def test_outcome_trends(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        # We have 4 directional priced runs (run 5 is NO_TRADE with predicted_direction=0)
        assert len(data.outcome_trends) > 0
        # Cumulative P&L should be non-zero
        last = data.outcome_trends[-1]
        assert last.run_count > 0

    def test_decision_distribution(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        assert "ENTER_LONG" in data.decision_distribution
        assert data.decision_distribution["ENTER_LONG"] >= 3

    def test_instrument_distribution(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        assert "XAUUSD" in data.instrument_distribution
        assert "EURUSD" in data.instrument_distribution

    def test_empty_db(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        data = build_analytics_data(
            db_path=tmp_path / "nonexistent.db",
            runs_dir=tmp_path / "empty",
        )
        assert data.total_runs == 0
        assert data.priced_runs == 0

    def test_overall_stats(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")

        assert data.avg_confidence > 0
        assert 0 <= data.no_trade_rate <= 100
        assert 0 <= data.overall_accuracy <= 100


class TestAnalyticsDashboardRender:
    """Test HTML rendering of analytics dashboard."""

    def test_render_produces_valid_html(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data, render_analytics_dashboard

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")
        html = render_analytics_dashboard(data)

        assert "<!DOCTYPE html>" in html
        assert "<canvas" in html
        assert "regimeChart" in html
        assert "calibrationChart" in html
        assert "decisionChart" in html
        assert "trendChart" in html

    def test_render_contains_chart_js(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data, render_analytics_dashboard

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=tmp_path / "empty")
        html = render_analytics_dashboard(data)

        assert "chart.js" in html.lower() or "chart.umd" in html.lower()

    def test_render_empty_state(self):
        from ai_analyst.core.analytics_dashboard import AnalyticsDashboardData, render_analytics_dashboard

        data = AnalyticsDashboardData()
        html = render_analytics_dashboard(data)
        assert "<!DOCTYPE html>" in html
        assert "0" in html  # total runs = 0

    def test_render_escapes_html(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import render_analytics_dashboard, AnalyticsDashboardData, PersonaHeatmapEntry

        data = AnalyticsDashboardData(
            persona_heatmap=[PersonaHeatmapEntry(
                persona="<script>alert('xss')</script>",
                dominance_pct=50.0,
                match_count=5,
                total_runs=10,
                flagged=False,
            )]
        )
        html = render_analytics_dashboard(data)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_persona_heatmap_with_data(self, tmp_path):
        from ai_analyst.core.analytics_dashboard import build_analytics_data, render_analytics_dashboard

        # Create run dirs with analyst outputs
        runs_dir = tmp_path / "runs"
        for i in range(3):
            run_dir = runs_dir / f"run-{i:03d}"
            analyst_dir = run_dir / "analyst_outputs"
            analyst_dir.mkdir(parents=True)

            verdict = {"decision": "ENTER_LONG"}
            (run_dir / "final_verdict.json").write_text(json.dumps(verdict))

            for persona in ["default_analyst", "risk_officer"]:
                ao = {"recommended_action": "LONG" if persona == "default_analyst" else "NO_TRADE"}
                (analyst_dir / f"{persona}.json").write_text(json.dumps(ao))

        db_path = _create_test_db(tmp_path)
        data = build_analytics_data(db_path=db_path, runs_dir=runs_dir)

        assert len(data.persona_heatmap) == 2
        html = render_analytics_dashboard(data)
        assert "default_analyst" in html


# ==========================================================================
# 8b — Strategy Backtesting Engine
# ==========================================================================


class TestBacktester:
    """Test backtesting engine."""

    def test_basic_backtest(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        # 5 directional trades (t-005 excluded: predicted_direction=0 + NO_TRADE)
        assert report.total_trades == 5
        assert report.wins + report.losses == report.total_trades
        assert 0 <= report.win_rate <= 100

    def test_win_rate_calculation(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        # t-001: predicted_direction=1, pct_change_24h=0.5 → correct ✓
        # t-002: predicted_direction=1, pct_change_24h=0.75 → correct ✓
        # t-003: predicted_direction=-1, pct_change_24h=-0.46 → correct ✓
        # t-004: predicted_direction=1, pct_change_24h=-0.50 → incorrect ✗
        # t-005: excluded (predicted_direction=0)
        # t-006: predicted_direction=1, pct_change_24h=0.99 → correct ✓
        assert report.wins == 4
        assert report.losses == 1
        assert report.win_rate == 80.0

    def test_instrument_filter(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path, instrument_filter="XAUUSD")
        report = run_backtest(config)

        # XAUUSD directional: t-001, t-002, t-004, t-006
        assert report.total_trades == 4
        for t in report.trades:
            assert t.instrument == "XAUUSD"

    def test_regime_filter(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path, regime_filter="risk_on")
        report = run_backtest(config)

        for t in report.trades:
            assert t.regime == "risk_on"

    def test_min_confidence_filter(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path, min_confidence=0.7)
        report = run_backtest(config)

        for t in report.trades:
            assert t.confidence >= 0.7

    def test_sharpe_ratio(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        # Sharpe should be a real number
        assert not math.isnan(report.sharpe_ratio)
        assert not math.isinf(report.sharpe_ratio)

    def test_max_drawdown(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        assert report.max_drawdown_pct >= 0

    def test_equity_curve(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        assert len(report.equity_curve) == report.total_trades

    def test_regime_breakdown(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        regime_names = [rb.regime for rb in report.regime_breakdown]
        assert len(regime_names) > 0

    def test_profit_factor(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        assert report.profit_factor >= 0

    def test_consecutive_streaks(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        assert report.max_consecutive_wins >= 0
        assert report.max_consecutive_losses >= 0

    def test_empty_db(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        config = BacktestConfig(db_path=tmp_path / "nonexistent.db")
        report = run_backtest(config)

        assert report.total_trades == 0
        assert report.win_rate == 0.0
        assert report.sharpe_ratio == 0.0

    def test_format_report(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)
        text = report.format()

        assert "STRATEGY BACKTEST REPORT" in text
        assert "Win Rate" in text
        assert "Sharpe Ratio" in text
        assert "Max Drawdown" in text

    def test_to_dict(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        db_path = _create_test_db(tmp_path)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)
        d = report.to_dict()

        assert isinstance(d, dict)
        assert "total_trades" in d
        assert "sharpe_ratio" in d
        assert "equity_curve" in d
        assert "regime_breakdown" in d
        # Verify JSON-serializable
        json.dumps(d)

    def test_all_losers(self, tmp_path):
        """All trades lose — edge case."""
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        runs = [
            {"run_id": f"loss-{i}", "instrument": "XAUUSD", "recorded_at": f"2026-03-0{i+1}T10:00:00Z",
             "regime": "risk_off", "vol_bias": "elevated", "conflict_score": 0.5,
             "confidence": 0.5, "time_horizon_days": 5,
             "decision": "ENTER_LONG", "overall_confidence": 0.6, "analyst_agreement": 60,
             "risk_override": 0, "price_at_record": 2000.0, "price_at_24h": 1990.0,
             "predicted_direction": 1, "pct_change_24h": -0.5}
            for i in range(3)
        ]
        db_path = _create_test_db(tmp_path, runs)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        assert report.win_rate == 0.0
        assert report.profit_factor == 0.0
        assert report.total_pnl_pct < 0

    def test_all_winners(self, tmp_path):
        """All trades win — edge case."""
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        runs = [
            {"run_id": f"win-{i}", "instrument": "XAUUSD", "recorded_at": f"2026-03-0{i+1}T10:00:00Z",
             "regime": "risk_on", "vol_bias": "normal", "conflict_score": 0.2,
             "confidence": 0.8, "time_horizon_days": 5,
             "decision": "ENTER_LONG", "overall_confidence": 0.85, "analyst_agreement": 90,
             "risk_override": 0, "price_at_record": 2000.0, "price_at_24h": 2020.0,
             "predicted_direction": 1, "pct_change_24h": 1.0}
            for i in range(3)
        ]
        db_path = _create_test_db(tmp_path, runs)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        assert report.win_rate == 100.0
        assert report.profit_factor == 999.99  # inf capped
        assert report.total_pnl_pct > 0
        assert report.max_drawdown_pct == 0.0


class TestBacktesterSharpe:
    """Dedicated Sharpe ratio edge-case tests."""

    def test_single_trade(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        runs = [
            {"run_id": "single", "instrument": "XAUUSD", "recorded_at": "2026-03-01T10:00:00Z",
             "regime": "risk_on", "vol_bias": "normal", "conflict_score": 0.2,
             "confidence": 0.7, "time_horizon_days": 5,
             "decision": "ENTER_LONG", "overall_confidence": 0.72, "analyst_agreement": 80,
             "risk_override": 0, "price_at_record": 2000.0, "price_at_24h": 2010.0,
             "predicted_direction": 1, "pct_change_24h": 0.5}
        ]
        db_path = _create_test_db(tmp_path, runs)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        # Single trade → Sharpe not meaningful
        assert report.sharpe_ratio == 0.0

    def test_zero_variance(self, tmp_path):
        from ai_analyst.core.backtester import run_backtest, BacktestConfig

        runs = [
            {"run_id": f"same-{i}", "instrument": "XAUUSD", "recorded_at": f"2026-03-0{i+1}T10:00:00Z",
             "regime": "risk_on", "vol_bias": "normal", "conflict_score": 0.2,
             "confidence": 0.8, "time_horizon_days": 5,
             "decision": "ENTER_LONG", "overall_confidence": 0.85, "analyst_agreement": 90,
             "risk_override": 0, "price_at_record": 2000.0, "price_at_24h": 2010.0,
             "predicted_direction": 1, "pct_change_24h": 0.5}
            for i in range(3)
        ]
        db_path = _create_test_db(tmp_path, runs)
        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)

        # All same returns → zero std → Sharpe = 0
        assert report.sharpe_ratio == 0.0


# ==========================================================================
# 8c — E2E Integration Validator
# ==========================================================================


class TestE2EValidator:
    """Test E2E validation framework."""

    def test_ground_truth_check(self):
        from ai_analyst.core.e2e_validator import _check_ground_truth

        msg = _check_ground_truth()
        assert "run_id=" in msg

    def test_arbiter_prompt_check(self):
        from ai_analyst.core.e2e_validator import _check_arbiter_prompt

        msg = _check_arbiter_prompt()
        assert "prompt_length=" in msg

    def test_feedback_loop_check(self):
        from ai_analyst.core.e2e_validator import _check_feedback_loop

        msg = _check_feedback_loop()
        assert "runs=" in msg

    def test_bias_detector_check(self):
        from ai_analyst.core.e2e_validator import _check_bias_detector

        msg = _check_bias_detector()
        assert "flags=" in msg

    def test_backtester_check(self):
        from ai_analyst.core.e2e_validator import _check_backtester

        msg = _check_backtester()
        assert "trades=" in msg

    def test_analytics_dashboard_check(self):
        from ai_analyst.core.e2e_validator import _check_analytics_dashboard

        msg = _check_analytics_dashboard()
        assert "html_size=" in msg

    def test_plugin_registry_check(self):
        from ai_analyst.core.e2e_validator import _check_plugin_registry

        msg = _check_plugin_registry()
        assert "personas=" in msg

    def test_full_e2e_run(self):
        from ai_analyst.core.e2e_validator import run_e2e_validation

        report = run_e2e_validation()
        assert report.total_checks >= 7
        assert report.all_passed, f"E2E failures: {[c.name for c in report.checks if not c.passed]}: {[c.error for c in report.checks if not c.passed]}"

    def test_e2e_report_format(self):
        from ai_analyst.core.e2e_validator import run_e2e_validation

        report = run_e2e_validation()
        text = report.format()
        assert "E2E INTEGRATION VALIDATION REPORT" in text
        assert "PASS" in text

    def test_seed_db(self):
        from ai_analyst.core.e2e_validator import _seed_test_db

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            _seed_test_db(db_path)
            assert db_path.exists()

            conn = sqlite3.connect(db_path)
            count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            conn.close()
            assert count == 6


# ==========================================================================
# 8d — Plugin Registry
# ==========================================================================


class TestPluginRegistry:
    """Test plugin registry and discovery."""

    def test_empty_registry(self):
        from ai_analyst.core.plugin_registry import PluginRegistry

        reg = PluginRegistry()
        assert reg.total_plugins == 0
        assert reg.list_personas() == []
        assert reg.list_data_sources() == []
        assert reg.list_hooks() == []

    def test_discover_builtins(self):
        from ai_analyst.core.plugin_registry import PluginRegistry

        reg = PluginRegistry()
        count = reg.discover_builtins()
        assert count >= 7  # 4 personas + 3 data sources

        personas = reg.list_personas()
        assert len(personas) >= 4
        names = [p.name for p in personas]
        assert "default_analyst" in names
        assert "risk_officer" in names
        assert "prosecutor" in names
        assert "ict_purist" in names

    def test_builtin_data_sources(self):
        from ai_analyst.core.plugin_registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtins()

        sources = reg.list_data_sources()
        names = [s.name for s in sources]
        assert "finnhub" in names
        assert "fred" in names
        assert "gdelt" in names

    def test_register_persona(self):
        from ai_analyst.core.plugin_registry import PluginRegistry, PersonaPlugin

        reg = PluginRegistry()
        plugin = PersonaPlugin(
            name="test_persona",
            version="2.0.0",
            description="A test persona",
            specialization="testing",
        )
        reg.register_persona(plugin)

        assert reg.get_persona("test_persona") is plugin
        assert reg.get_persona("nonexistent") is None

    def test_register_data_source(self):
        from ai_analyst.core.plugin_registry import PluginRegistry, DataSourcePlugin

        reg = PluginRegistry()
        plugin = DataSourcePlugin(
            name="test_source",
            source_type="rest_api",
            base_url="https://api.example.com",
        )
        reg.register_data_source(plugin)

        assert reg.get_data_source("test_source") is plugin

    def test_register_hook(self):
        from ai_analyst.core.plugin_registry import PluginRegistry, HookPlugin, HookEvent

        reg = PluginRegistry()
        plugin = HookPlugin(
            name="test_hook",
            events=[HookEvent.POST_VERDICT],
            webhook_url="https://hooks.example.com/notify",
        )
        reg.register_hook(plugin)

        hooks = reg.get_hooks_for_event(HookEvent.POST_VERDICT)
        assert len(hooks) == 1
        assert hooks[0].name == "test_hook"

        # Event with no hooks
        assert reg.get_hooks_for_event(HookEvent.POST_AAR) == []

    def test_disabled_hook_filtered(self):
        from ai_analyst.core.plugin_registry import PluginRegistry, HookPlugin, HookEvent

        reg = PluginRegistry()
        reg.register_hook(HookPlugin(
            name="disabled_hook",
            events=[HookEvent.POST_VERDICT],
            enabled=False,
        ))

        hooks = reg.get_hooks_for_event(HookEvent.POST_VERDICT)
        assert len(hooks) == 0

    def test_discover_from_json_manifest(self, tmp_path):
        from ai_analyst.core.plugin_registry import PluginRegistry

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        manifest = {
            "name": "custom_analyst",
            "version": "1.0.0",
            "type": "persona",
            "description": "A custom analyst from a manifest",
            "config": {
                "specialization": "orderflow",
                "temperature": 0.25,
                "risk_appetite": "aggressive",
            },
        }
        (plugin_dir / "custom_analyst.plugin.json").write_text(json.dumps(manifest))

        reg = PluginRegistry()
        count = reg.discover_plugins(plugin_dir=plugin_dir)
        assert count == 1

        persona = reg.get_persona("custom_analyst")
        assert persona is not None
        assert persona.specialization == "orderflow"
        assert persona.temperature == 0.25

    def test_discover_hook_manifest(self, tmp_path):
        from ai_analyst.core.plugin_registry import PluginRegistry, HookEvent

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        manifest = {
            "name": "slack_notifier",
            "version": "1.0.0",
            "type": "hook",
            "description": "Posts verdicts to Slack",
            "config": {
                "events": ["post_verdict", "pipeline_error"],
                "webhook_url": "https://hooks.slack.com/services/xxx",
                "method": "POST",
            },
        }
        (plugin_dir / "slack_notifier.plugin.json").write_text(json.dumps(manifest))

        reg = PluginRegistry()
        count = reg.discover_plugins(plugin_dir=plugin_dir)
        assert count == 1

        hooks = reg.get_hooks_for_event(HookEvent.POST_VERDICT)
        assert len(hooks) == 1
        assert hooks[0].webhook_url == "https://hooks.slack.com/services/xxx"

    def test_discover_data_source_manifest(self, tmp_path):
        from ai_analyst.core.plugin_registry import PluginRegistry

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        manifest = {
            "name": "binance",
            "version": "1.0.0",
            "type": "data_source",
            "description": "Binance crypto data",
            "config": {
                "source_type": "websocket",
                "base_url": "wss://stream.binance.com:9443",
                "instruments": ["BTCUSDT", "ETHUSDT"],
            },
        }
        (plugin_dir / "binance.plugin.json").write_text(json.dumps(manifest))

        reg = PluginRegistry()
        count = reg.discover_plugins(plugin_dir=plugin_dir)
        assert count == 1

        source = reg.get_data_source("binance")
        assert source.source_type == "websocket"
        assert "BTCUSDT" in source.instruments

    def test_invalid_manifest_skipped(self, tmp_path):
        from ai_analyst.core.plugin_registry import PluginRegistry

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        # Invalid JSON
        (plugin_dir / "broken.plugin.json").write_text("not json")

        reg = PluginRegistry()
        count = reg.discover_plugins(plugin_dir=plugin_dir)
        assert count == 0

    def test_unknown_type_skipped(self, tmp_path):
        from ai_analyst.core.plugin_registry import PluginRegistry

        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        manifest = {"name": "weird", "type": "unknown_type", "version": "1.0.0"}
        (plugin_dir / "weird.plugin.json").write_text(json.dumps(manifest))

        reg = PluginRegistry()
        count = reg.discover_plugins(plugin_dir=plugin_dir)
        assert count == 0

    def test_idempotent_builtin_discovery(self):
        from ai_analyst.core.plugin_registry import PluginRegistry

        reg = PluginRegistry()
        count1 = reg.discover_builtins()
        count2 = reg.discover_builtins()

        # Second call should not re-register
        assert count2 == 0
        assert reg.total_plugins == count1

    def test_format_summary(self):
        from ai_analyst.core.plugin_registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtins()
        text = reg.format_summary()

        assert "PLUGIN REGISTRY" in text
        assert "PERSONAS" in text
        assert "DATA SOURCES" in text
        assert "default_analyst" in text

    def test_total_plugins(self):
        from ai_analyst.core.plugin_registry import PluginRegistry, PersonaPlugin, DataSourcePlugin, HookPlugin, HookEvent

        reg = PluginRegistry()
        reg.register_persona(PersonaPlugin(name="p1"))
        reg.register_data_source(DataSourcePlugin(name="s1"))
        reg.register_hook(HookPlugin(name="h1", events=[HookEvent.POST_VERDICT]))

        assert reg.total_plugins == 3
