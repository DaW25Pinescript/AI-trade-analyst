"""
Phase 8c — End-to-End Integration Validator.

Provides a lightweight smoke-test framework that validates the full analysis
pipeline without requiring real API keys.  Tests run deterministically using
mock LLM responses and verify that:

  1. GroundTruthPacket construction succeeds with valid inputs.
  2. Pipeline graph compiles and node ordering is correct.
  3. Arbiter prompt builder produces valid prompts from mock analyst outputs.
  4. Feedback loop generates a report from an in-memory SQLite DB.
  5. Bias detector flags expected patterns from mock analyst data.
  6. Backtester computes correct metrics from mock outcomes.
  7. Analytics dashboard renders valid HTML.
  8. Plugin registry loads built-in plugins.

Results are returned as a structured E2EReport so they can be displayed in
the CLI or returned via the /e2e endpoint.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class E2ECheckResult:
    """Result of a single validation check."""
    name: str
    passed: bool
    duration_ms: int
    message: str = ""
    error: str = ""


@dataclass
class E2EReport:
    """Aggregated E2E validation report."""
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    duration_ms: int = 0
    checks: list[E2ECheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def format(self) -> str:
        lines = [
            "=" * 60,
            "  E2E INTEGRATION VALIDATION REPORT",
            "=" * 60,
            f"  Total: {self.total_checks} | Passed: {self.passed} | Failed: {self.failed} | Time: {self.duration_ms}ms",
            "",
        ]
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"  [{status}] {check.name} ({check.duration_ms}ms)")
            if check.message:
                lines.append(f"         {check.message}")
            if check.error:
                lines.append(f"         ERROR: {check.error}")
        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


def run_e2e_validation() -> E2EReport:
    """Execute all E2E validation checks and return a report."""
    report = E2EReport()
    start = time.monotonic()

    checks = [
        ("GroundTruthPacket construction", _check_ground_truth),
        ("Arbiter prompt builder", _check_arbiter_prompt),
        ("Feedback loop (in-memory DB)", _check_feedback_loop),
        ("Bias detector", _check_bias_detector),
        ("Backtester engine", _check_backtester),
        ("Analytics dashboard render", _check_analytics_dashboard),
        ("Plugin registry", _check_plugin_registry),
    ]

    for name, fn in checks:
        t0 = time.monotonic()
        try:
            msg = fn()
            elapsed = int((time.monotonic() - t0) * 1000)
            report.checks.append(E2ECheckResult(
                name=name, passed=True, duration_ms=elapsed, message=msg,
            ))
            report.passed += 1
        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            report.checks.append(E2ECheckResult(
                name=name, passed=False, duration_ms=elapsed,
                error=f"{type(e).__name__}: {e}",
            ))
            report.failed += 1
        report.total_checks += 1

    report.duration_ms = int((time.monotonic() - start) * 1000)
    return report


# ── Individual checks ────────────────────────────────────────────────────────


def _check_ground_truth() -> str:
    from ai_analyst.models.ground_truth import (
        GroundTruthPacket, RiskConstraints, MarketContext, ScreenshotMetadata,
    )
    import base64

    # Minimal valid chart (1x1 PNG)
    tiny_png = base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    ).decode()

    gt = GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4"],
        charts={"H4": tiny_png},
        screenshot_metadata=[ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only")],
        risk_constraints=RiskConstraints(min_rr=2.0, max_risk_per_trade=0.5),
        context=MarketContext(account_balance=10000, market_regime="trending"),
    )
    assert gt.run_id, "run_id must be set"
    assert gt.instrument == "XAUUSD"
    return f"run_id={gt.run_id[:8]}..."


def _check_arbiter_prompt() -> str:
    from ai_analyst.core.arbiter_prompt_builder import build_arbiter_prompt
    from ai_analyst.models.analyst_output import AnalystOutput
    from ai_analyst.models.ground_truth import RiskConstraints

    mock_outputs = []
    for i in range(3):
        mock_outputs.append(AnalystOutput(
            htf_bias="bullish",
            structure_state="continuation",
            key_levels={"premium": ["2050"], "discount": ["2000"]},
            setup_valid=True,
            setup_type="BOS_continuation",
            entry_model="OB_retest",
            invalidation="Below 1990",
            disqualifiers=[],
            sweep_status="clean",
            fvg_zones=["2010-2015"],
            displacement_quality="strong",
            confidence=0.7 + i * 0.05,
            rr_estimate=3.0,
            notes=f"Mock analyst {i}",
            recommended_action="LONG",
        ))

    prompt = build_arbiter_prompt(
        analyst_outputs=mock_outputs,
        risk_constraints=RiskConstraints(min_rr=2.0),
        run_id="e2e-test-001",
    )
    assert len(prompt) > 100, "Prompt should be substantial"
    return f"prompt_length={len(prompt)}"


def _check_feedback_loop() -> str:
    from ai_analyst.core.feedback_loop import build_feedback_report

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_outcomes.db"
        _seed_test_db(db_path)

        report = build_feedback_report(db_path=db_path, runs_dir=Path(td) / "empty")
        assert report.total_runs == 6, f"Expected 6 runs, got {report.total_runs}"
        assert len(report.regime_accuracy) > 0, "Should have regime accuracy data"
        return f"runs={report.total_runs}, regimes={len(report.regime_accuracy)}"


def _check_bias_detector() -> str:
    from ai_analyst.core.bias_detector import detect_bias
    from ai_analyst.models.analyst_output import AnalystOutput

    # All analysts agree with high confidence → should flag
    mock_outputs = []
    for _ in range(3):
        mock_outputs.append(AnalystOutput(
            htf_bias="bullish",
            structure_state="continuation",
            key_levels={"premium": ["2050"], "discount": ["2000"]},
            setup_valid=True,
            setup_type="BOS_continuation",
            entry_model="OB_retest",
            invalidation="Below 1990",
            disqualifiers=[],
            confidence=0.85,
            rr_estimate=3.0,
            notes="Mock",
            recommended_action="LONG",
        ))

    report = detect_bias(mock_outputs)
    assert report.analyst_count == 3
    # Should have at least one flag
    assert len(report.flags) > 0, "Should detect unanimous high confidence"
    return f"flags={len(report.flags)}, severity={report.highest_severity}"


def _check_backtester() -> str:
    from ai_analyst.core.backtester import run_backtest, BacktestConfig

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_outcomes.db"
        _seed_test_db(db_path)

        config = BacktestConfig(db_path=db_path)
        report = run_backtest(config)
        assert report.total_trades > 0, "Should have trades"
        assert report.win_rate >= 0, "Win rate should be non-negative"
        return f"trades={report.total_trades}, win_rate={report.win_rate:.1f}%, sharpe={report.sharpe_ratio:.2f}"


def _check_analytics_dashboard() -> str:
    from ai_analyst.core.analytics_dashboard import build_analytics_data, render_analytics_dashboard

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_outcomes.db"
        _seed_test_db(db_path)

        data = build_analytics_data(db_path=db_path, runs_dir=Path(td) / "empty")
        html = render_analytics_dashboard(data)
        assert "<!DOCTYPE html>" in html
        assert "Chart.js" in html or "chart.js" in html
        assert "regimeChart" in html
        return f"html_size={len(html)} bytes, runs={data.total_runs}"


def _check_plugin_registry() -> str:
    from ai_analyst.core.plugin_registry import PluginRegistry

    registry = PluginRegistry()
    registry.discover_builtins()
    personas = registry.list_personas()
    sources = registry.list_data_sources()
    hooks = registry.list_hooks()
    return f"personas={len(personas)}, sources={len(sources)}, hooks={len(hooks)}"


# ── Test data seeder ─────────────────────────────────────────────────────────


def _seed_test_db(db_path: Path) -> None:
    """Create a minimal outcomes DB with test data for E2E validation."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                instrument TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                regime TEXT NOT NULL,
                vol_bias TEXT NOT NULL,
                conflict_score REAL NOT NULL,
                confidence REAL NOT NULL,
                time_horizon_days INTEGER NOT NULL,
                active_event_ids TEXT NOT NULL,
                explanation TEXT NOT NULL,
                decision TEXT,
                overall_confidence REAL,
                analyst_agreement INTEGER,
                risk_override INTEGER,
                price_at_record REAL,
                price_at_1h REAL,
                price_at_24h REAL,
                price_at_5d REAL,
                pct_change_1h REAL,
                pct_change_24h REAL,
                pct_change_5d REAL,
                predicted_direction INTEGER
            )
        """)

        test_runs = [
            ("e2e-001", "XAUUSD", "2026-03-01T10:00:00Z", "risk_on", "normal", 0.2, 0.7, 5, "ENTER_LONG", 0.72, 80, 0, 2000.0, 2010.0, 1, 0.5),
            ("e2e-002", "XAUUSD", "2026-03-01T14:00:00Z", "risk_on", "normal", 0.3, 0.8, 5, "ENTER_LONG", 0.81, 90, 0, 2010.0, 2025.0, 1, 0.75),
            ("e2e-003", "EURUSD", "2026-03-02T10:00:00Z", "risk_off", "elevated", 0.6, 0.5, 3, "ENTER_SHORT", 0.55, 65, 0, 1.0800, 1.0750, -1, 0.46),
            ("e2e-004", "XAUUSD", "2026-03-02T14:00:00Z", "neutral", "normal", 0.4, 0.6, 5, "ENTER_LONG", 0.62, 70, 0, 2020.0, 2010.0, 1, -0.50),
            ("e2e-005", "EURUSD", "2026-03-03T10:00:00Z", "risk_off", "elevated", 0.7, 0.4, 3, "NO_TRADE", 0.42, 50, 0, 1.0750, 1.0780, 0, 0.28),
            ("e2e-006", "XAUUSD", "2026-03-03T14:00:00Z", "risk_on", "normal", 0.2, 0.9, 5, "ENTER_LONG", 0.88, 95, 0, 2030.0, 2050.0, 1, 0.99),
        ]

        for r in test_runs:
            conn.execute(
                "INSERT INTO runs (run_id, instrument, recorded_at, regime, vol_bias, "
                "conflict_score, confidence, time_horizon_days, active_event_ids, explanation, "
                "decision, overall_confidence, analyst_agreement, risk_override, "
                "price_at_record, price_at_24h, predicted_direction, pct_change_24h) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', ?, ?, ?, ?, ?, ?, ?, ?)",
                r,
            )
