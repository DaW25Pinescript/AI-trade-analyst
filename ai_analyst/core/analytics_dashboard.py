"""
Phase 8a — Advanced Analytics Dashboard.

Builds a rich, self-contained HTML analytics dashboard with:
  1. Regime accuracy bar chart
  2. Confidence calibration curve
  3. Persona dominance heatmap
  4. Outcome trends over time (cumulative P&L, win-rate rolling)
  5. Decision distribution donut chart
  6. Instrument breakdown

Uses Chart.js (CDN) for client-side chart rendering.  Data is injected as
JSON into the page at build time — no additional API calls required.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent.parent / "macro_risk_officer" / "data" / "outcomes.db"
_RUNS_DIR = Path(__file__).parent.parent / "output" / "runs"


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class RegimeChartData:
    """Bar chart data: regime → accuracy + no-trade rate."""
    labels: list[str] = field(default_factory=list)
    accuracy: list[float] = field(default_factory=list)
    no_trade_pct: list[float] = field(default_factory=list)
    totals: list[int] = field(default_factory=list)


@dataclass
class CalibrationPoint:
    bucket: str
    expected_accuracy: float  # midpoint of bucket
    actual_accuracy: float
    count: int


@dataclass
class PersonaHeatmapEntry:
    persona: str
    dominance_pct: float
    match_count: int
    total_runs: int
    flagged: bool


@dataclass
class OutcomeTrendPoint:
    """Single point on the outcome timeline."""
    date: str  # ISO date
    cumulative_pnl_pct: float  # sum of pct_change_24h for correct calls
    rolling_win_rate: float  # rolling 10-run win rate
    run_count: int


@dataclass
class AnalyticsDashboardData:
    """All data needed to render the analytics dashboard."""
    regime_chart: RegimeChartData = field(default_factory=RegimeChartData)
    calibration: list[CalibrationPoint] = field(default_factory=list)
    persona_heatmap: list[PersonaHeatmapEntry] = field(default_factory=list)
    outcome_trends: list[OutcomeTrendPoint] = field(default_factory=list)
    decision_distribution: dict[str, int] = field(default_factory=dict)
    instrument_distribution: dict[str, int] = field(default_factory=dict)
    total_runs: int = 0
    priced_runs: int = 0
    overall_accuracy: float = 0.0
    avg_confidence: float = 0.0
    no_trade_rate: float = 0.0


# ── Data builder ─────────────────────────────────────────────────────────────

_CONFIDENCE_BUCKETS = [
    ("low (0–0.3)", 0.0, 0.3, 0.15),
    ("mid (0.3–0.6)", 0.3, 0.6, 0.45),
    ("high (0.6–1.0)", 0.6, 1.01, 0.80),
]


def build_analytics_data(
    db_path: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
) -> AnalyticsDashboardData:
    """Build the full analytics dataset from the outcomes DB and run files."""
    db = db_path or _DEFAULT_DB
    rd = runs_dir or _RUNS_DIR

    data = AnalyticsDashboardData()

    if not db.exists():
        return data

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row

        data.total_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        data.priced_runs = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE pct_change_24h IS NOT NULL"
        ).fetchone()[0]

        data.regime_chart = _build_regime_chart(conn)
        data.calibration = _build_calibration(conn)
        data.outcome_trends = _build_outcome_trends(conn)
        data.decision_distribution = _build_distribution(conn, "decision")
        data.instrument_distribution = _build_distribution(conn, "instrument")

        # Overall stats
        stats = conn.execute(
            "SELECT AVG(overall_confidence) AS avg_conf, "
            "SUM(CASE WHEN decision = 'NO_TRADE' THEN 1 ELSE 0 END) AS nt "
            "FROM runs WHERE decision IS NOT NULL"
        ).fetchone()
        if stats and data.total_runs > 0:
            data.avg_confidence = round(stats["avg_conf"] or 0, 3)
            data.no_trade_rate = round(100.0 * (stats["nt"] or 0) / data.total_runs, 1)

        # Overall accuracy
        acc_row = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN (predicted_direction > 0 AND pct_change_24h > 0) "
            "         OR  (predicted_direction < 0 AND pct_change_24h < 0) "
            "    THEN 1 ELSE 0 END) AS correct "
            "FROM runs "
            "WHERE pct_change_24h IS NOT NULL AND predicted_direction != 0"
        ).fetchone()
        if acc_row and acc_row["total"] > 0:
            data.overall_accuracy = round(100.0 * acc_row["correct"] / acc_row["total"], 1)

    data.persona_heatmap = _build_persona_heatmap(rd)

    return data


def _build_regime_chart(conn: sqlite3.Connection) -> RegimeChartData:
    rows = conn.execute(
        """
        SELECT
            regime,
            COUNT(*) AS total,
            SUM(CASE WHEN pct_change_24h IS NOT NULL AND predicted_direction != 0
                     AND ((predicted_direction > 0 AND pct_change_24h > 0)
                       OR (predicted_direction < 0 AND pct_change_24h < 0))
                THEN 1 ELSE 0 END) AS correct,
            SUM(CASE WHEN pct_change_24h IS NOT NULL AND predicted_direction != 0
                THEN 1 ELSE 0 END) AS priced_directional,
            SUM(CASE WHEN decision = 'NO_TRADE' THEN 1 ELSE 0 END) AS no_trade
        FROM runs
        GROUP BY regime
        ORDER BY total DESC
        """
    ).fetchall()

    chart = RegimeChartData()
    for row in rows:
        chart.labels.append(row["regime"])
        priced = row["priced_directional"] or 0
        acc = (100.0 * row["correct"] / priced) if priced > 0 else 0.0
        nt_pct = (100.0 * row["no_trade"] / row["total"]) if row["total"] > 0 else 0.0
        chart.accuracy.append(round(acc, 1))
        chart.no_trade_pct.append(round(nt_pct, 1))
        chart.totals.append(row["total"])
    return chart


def _build_calibration(conn: sqlite3.Connection) -> list[CalibrationPoint]:
    rows = conn.execute(
        "SELECT overall_confidence, pct_change_24h, predicted_direction "
        "FROM runs "
        "WHERE pct_change_24h IS NOT NULL "
        "  AND predicted_direction != 0 "
        "  AND overall_confidence IS NOT NULL"
    ).fetchall()

    buckets: dict[str, list[bool]] = {}
    for label, _, _, _ in _CONFIDENCE_BUCKETS:
        buckets[label] = []

    for row in rows:
        conf = row["overall_confidence"]
        correct = (
            (row["predicted_direction"] > 0 and row["pct_change_24h"] > 0)
            or (row["predicted_direction"] < 0 and row["pct_change_24h"] < 0)
        )
        for label, lo, hi, _ in _CONFIDENCE_BUCKETS:
            if lo <= conf < hi:
                buckets[label].append(correct)
                break

    results = []
    for label, _, _, expected in _CONFIDENCE_BUCKETS:
        items = buckets[label]
        total = len(items)
        correct_count = sum(items)
        actual = (100.0 * correct_count / total) if total > 0 else 0.0
        results.append(CalibrationPoint(
            bucket=label,
            expected_accuracy=round(expected * 100, 1),
            actual_accuracy=round(actual, 1),
            count=total,
        ))
    return results


def _build_outcome_trends(conn: sqlite3.Connection) -> list[OutcomeTrendPoint]:
    rows = conn.execute(
        "SELECT recorded_at, pct_change_24h, predicted_direction "
        "FROM runs "
        "WHERE pct_change_24h IS NOT NULL "
        "  AND predicted_direction != 0 "
        "ORDER BY recorded_at ASC"
    ).fetchall()

    if not rows:
        return []

    points: list[OutcomeTrendPoint] = []
    cum_pnl = 0.0
    results_window: list[bool] = []

    for i, row in enumerate(rows):
        correct = (
            (row["predicted_direction"] > 0 and row["pct_change_24h"] > 0)
            or (row["predicted_direction"] < 0 and row["pct_change_24h"] < 0)
        )
        pnl_delta = abs(row["pct_change_24h"]) if correct else -abs(row["pct_change_24h"])
        cum_pnl += pnl_delta

        results_window.append(correct)
        if len(results_window) > 10:
            results_window.pop(0)

        rolling_wr = (100.0 * sum(results_window) / len(results_window))

        date_str = row["recorded_at"][:10] if row["recorded_at"] else ""
        points.append(OutcomeTrendPoint(
            date=date_str,
            cumulative_pnl_pct=round(cum_pnl, 3),
            rolling_win_rate=round(rolling_wr, 1),
            run_count=i + 1,
        ))

    return points


def _build_distribution(conn: sqlite3.Connection, column: str) -> dict[str, int]:
    if column not in ("decision", "instrument"):
        return {}
    rows = conn.execute(
        f"SELECT {column}, COUNT(*) AS n FROM runs "
        f"WHERE {column} IS NOT NULL GROUP BY {column} ORDER BY n DESC"
    ).fetchall()
    return {row[column]: row["n"] for row in rows}


def _build_persona_heatmap(runs_dir: Path) -> list[PersonaHeatmapEntry]:
    if not runs_dir.exists():
        return []

    persona_matches: dict[str, int] = {}
    persona_totals: dict[str, int] = {}

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue

        verdict_path = run_dir / "final_verdict.json"
        analyst_dir = run_dir / "analyst_outputs"

        if not verdict_path.exists() or not analyst_dir.exists():
            continue

        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
            final_decision = verdict.get("decision")
            if not final_decision:
                continue
        except (json.JSONDecodeError, OSError):
            continue

        decision_to_action = {
            "ENTER_LONG": "LONG",
            "ENTER_SHORT": "SHORT",
            "WAIT_FOR_CONFIRMATION": "WAIT",
            "NO_TRADE": "NO_TRADE",
        }
        expected_action = decision_to_action.get(final_decision, final_decision)

        for analyst_file in sorted(analyst_dir.glob("*.json")):
            try:
                ao = json.loads(analyst_file.read_text(encoding="utf-8"))
                persona = analyst_file.stem
                action = ao.get("recommended_action")
                if action is None:
                    continue
                persona_totals[persona] = persona_totals.get(persona, 0) + 1
                if action == expected_action:
                    persona_matches[persona] = persona_matches.get(persona, 0) + 1
            except (json.JSONDecodeError, OSError):
                continue

    results = []
    for persona in sorted(persona_totals.keys()):
        total = persona_totals[persona]
        matches = persona_matches.get(persona, 0)
        dom_pct = (100.0 * matches / total) if total > 0 else 0.0
        results.append(PersonaHeatmapEntry(
            persona=persona,
            dominance_pct=round(dom_pct, 1),
            match_count=matches,
            total_runs=total,
            flagged=dom_pct > 80.0 and total >= 3,
        ))
    return results


# ── HTML renderer ────────────────────────────────────────────────────────────


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_analytics_dashboard(data: AnalyticsDashboardData) -> str:
    """Render the analytics dashboard as a self-contained HTML page."""

    regime_labels = json.dumps(data.regime_chart.labels)
    regime_accuracy = json.dumps(data.regime_chart.accuracy)
    regime_no_trade = json.dumps(data.regime_chart.no_trade_pct)
    regime_totals = json.dumps(data.regime_chart.totals)

    cal_labels = json.dumps([c.bucket for c in data.calibration])
    cal_expected = json.dumps([c.expected_accuracy for c in data.calibration])
    cal_actual = json.dumps([c.actual_accuracy for c in data.calibration])
    cal_counts = json.dumps([c.count for c in data.calibration])

    persona_names = json.dumps([p.persona for p in data.persona_heatmap])
    persona_dom = json.dumps([p.dominance_pct for p in data.persona_heatmap])
    persona_flagged = json.dumps([p.flagged for p in data.persona_heatmap])

    trend_dates = json.dumps([t.date for t in data.outcome_trends])
    trend_pnl = json.dumps([t.cumulative_pnl_pct for t in data.outcome_trends])
    trend_wr = json.dumps([t.rolling_win_rate for t in data.outcome_trends])

    dec_labels = json.dumps(list(data.decision_distribution.keys()))
    dec_values = json.dumps(list(data.decision_distribution.values()))

    inst_labels = json.dumps(list(data.instrument_distribution.keys()))
    inst_values = json.dumps(list(data.instrument_distribution.values()))

    # Persona heatmap rows
    persona_rows = ""
    for p in data.persona_heatmap:
        flag_cls = ' class="flagged"' if p.flagged else ""
        persona_rows += (
            f"<tr{flag_cls}>"
            f"<td>{_esc(p.persona)}</td>"
            f"<td>{p.match_count}</td>"
            f"<td>{p.total_runs}</td>"
            f"<td>{p.dominance_pct:.1f}%</td>"
            f"<td>{'YES' if p.flagged else ''}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>AI Trade Analyst \u2014 Advanced Analytics Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'IBM Plex Mono', 'Menlo', monospace; background: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }}
  h1 {{ color: #38bdf8; font-size: 1.4rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; }}
  .kpi .label {{ color: #94a3b8; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .kpi .value {{ color: #f1f5f9; font-size: 1.6rem; font-weight: 700; margin-top: 4px; }}
  .kpi .sub {{ color: #64748b; font-size: 0.72rem; margin-top: 4px; }}
  .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr)); gap: 20px; margin-bottom: 28px; }}
  .chart-card {{ background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }}
  .chart-card h2 {{ color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 16px 0; }}
  .chart-container {{ position: relative; height: 280px; }}
  .section {{ margin-bottom: 28px; }}
  .section h2 {{ color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  th {{ text-align: left; color: #64748b; padding: 8px 12px; border-bottom: 1px solid #334155; font-weight: 500; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover {{ background: #1e293b; }}
  tr.flagged {{ background: #451a03; }}
  tr.flagged:hover {{ background: #5c2007; }}
  .status-good {{ color: #22c55e; }}
  .status-warn {{ color: #f59e0b; }}
  .status-bad {{ color: #ef4444; }}
  .no-data {{ color: #64748b; text-align: center; padding: 40px; }}
  @media (max-width: 640px) {{
    .chart-grid {{ grid-template-columns: 1fr; }}
    .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  }}
</style>
</head>
<body>
<h1>AI Trade Analyst \u2014 Advanced Analytics</h1>
<div class="subtitle">Phase 8 Analytics Dashboard | {data.total_runs} total runs | {data.priced_runs} priced | Auto-refresh 60s</div>

<div class="kpi-grid">
  <div class="kpi">
    <div class="label">Total Runs</div>
    <div class="value">{data.total_runs}</div>
    <div class="sub">{data.priced_runs} with price data</div>
  </div>
  <div class="kpi">
    <div class="label">Overall Accuracy</div>
    <div class="value {'status-good' if data.overall_accuracy >= 55 else 'status-warn' if data.overall_accuracy >= 45 else 'status-bad'}">{data.overall_accuracy:.1f}%</div>
    <div class="sub">24h directional</div>
  </div>
  <div class="kpi">
    <div class="label">Avg Confidence</div>
    <div class="value">{data.avg_confidence:.1%}</div>
    <div class="sub">Arbiter output</div>
  </div>
  <div class="kpi">
    <div class="label">NO_TRADE Rate</div>
    <div class="value">{data.no_trade_rate:.1f}%</div>
    <div class="sub">of all decisions</div>
  </div>
</div>

<div class="chart-grid">
  <div class="chart-card">
    <h2>Regime Accuracy &amp; NO_TRADE Rate</h2>
    <div class="chart-container"><canvas id="regimeChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Confidence Calibration</h2>
    <div class="chart-container"><canvas id="calibrationChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Decision Distribution</h2>
    <div class="chart-container"><canvas id="decisionChart"></canvas></div>
  </div>
  <div class="chart-card">
    <h2>Instrument Breakdown</h2>
    <div class="chart-container"><canvas id="instrumentChart"></canvas></div>
  </div>
</div>

<div class="chart-grid">
  <div class="chart-card" style="grid-column: 1 / -1;">
    <h2>Outcome Trends (Cumulative P&amp;L % &amp; Rolling Win Rate)</h2>
    <div class="chart-container" style="height: 320px;"><canvas id="trendChart"></canvas></div>
  </div>
</div>

<div class="section">
  <h2>Persona Dominance Heatmap</h2>
  <div class="chart-card">
    {"<table><thead><tr><th>Persona</th><th>Matches</th><th>Total</th><th>Dominance</th><th>Flagged</th></tr></thead><tbody>" + persona_rows + "</tbody></table>" if persona_rows else '<div class="no-data">No persona data available yet. Run analyses to collect data.</div>'}
  </div>
</div>

<script>
const chartDefaults = {{
  color: '#94a3b8',
  borderColor: '#334155',
}};
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

// 1. Regime Accuracy
new Chart(document.getElementById('regimeChart'), {{
  type: 'bar',
  data: {{
    labels: {regime_labels},
    datasets: [
      {{
        label: 'Accuracy %',
        data: {regime_accuracy},
        backgroundColor: '#3b82f6',
        borderRadius: 4,
      }},
      {{
        label: 'NO_TRADE %',
        data: {regime_no_trade},
        backgroundColor: '#6b728080',
        borderRadius: 4,
      }}
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      tooltip: {{
        callbacks: {{
          afterLabel: function(ctx) {{
            const totals = {regime_totals};
            return 'Sample: ' + totals[ctx.dataIndex] + ' runs';
          }}
        }}
      }}
    }},
    scales: {{
      y: {{ beginAtZero: true, max: 100, ticks: {{ callback: v => v + '%' }} }}
    }}
  }}
}});

// 2. Confidence Calibration
new Chart(document.getElementById('calibrationChart'), {{
  type: 'bar',
  data: {{
    labels: {cal_labels},
    datasets: [
      {{
        label: 'Expected Accuracy',
        data: {cal_expected},
        backgroundColor: '#64748b60',
        borderColor: '#64748b',
        borderWidth: 2,
        borderRadius: 4,
      }},
      {{
        label: 'Actual Accuracy',
        data: {cal_actual},
        backgroundColor: '#22c55e80',
        borderColor: '#22c55e',
        borderWidth: 2,
        borderRadius: 4,
      }}
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    scales: {{
      y: {{ beginAtZero: true, max: 100, ticks: {{ callback: v => v + '%' }} }}
    }},
    plugins: {{
      tooltip: {{
        callbacks: {{
          afterLabel: function(ctx) {{
            const counts = {cal_counts};
            return 'Sample: ' + counts[ctx.dataIndex] + ' runs';
          }}
        }}
      }}
    }}
  }}
}});

// 3. Decision Distribution (Donut)
const decColors = {{
  'ENTER_LONG': '#22c55e',
  'ENTER_SHORT': '#ef4444',
  'NO_TRADE': '#6b7280',
  'WAIT_FOR_CONFIRMATION': '#3b82f6',
}};
const decLabels = {dec_labels};
new Chart(document.getElementById('decisionChart'), {{
  type: 'doughnut',
  data: {{
    labels: decLabels,
    datasets: [{{
      data: {dec_values},
      backgroundColor: decLabels.map(l => decColors[l] || '#8b5cf6'),
      borderWidth: 0,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'right', labels: {{ padding: 12, usePointStyle: true }} }}
    }}
  }}
}});

// 4. Instrument Breakdown (Horizontal bar)
new Chart(document.getElementById('instrumentChart'), {{
  type: 'bar',
  data: {{
    labels: {inst_labels},
    datasets: [{{
      label: 'Runs',
      data: {inst_values},
      backgroundColor: '#8b5cf6',
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    scales: {{ x: {{ beginAtZero: true }} }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});

// 5. Outcome Trends (Dual axis)
const trendDates = {trend_dates};
if (trendDates.length > 0) {{
  new Chart(document.getElementById('trendChart'), {{
    type: 'line',
    data: {{
      labels: trendDates,
      datasets: [
        {{
          label: 'Cumulative P&L %',
          data: {trend_pnl},
          borderColor: '#22c55e',
          backgroundColor: '#22c55e20',
          fill: true,
          tension: 0.3,
          yAxisID: 'y',
          pointRadius: 2,
        }},
        {{
          label: 'Rolling Win Rate %',
          data: {trend_wr},
          borderColor: '#f59e0b',
          borderDash: [5, 5],
          tension: 0.3,
          yAxisID: 'y1',
          pointRadius: 2,
        }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      scales: {{
        y: {{
          type: 'linear',
          position: 'left',
          title: {{ display: true, text: 'Cumulative P&L %' }}
        }},
        y1: {{
          type: 'linear',
          position: 'right',
          title: {{ display: true, text: 'Win Rate %' }},
          min: 0,
          max: 100,
          grid: {{ drawOnChartArea: false }}
        }}
      }}
    }}
  }});
}} else {{
  document.getElementById('trendChart').parentElement.innerHTML =
    '<div class="no-data">No outcome trend data yet. Run analyses and backfill prices.</div>';
}}
</script>
</body>
</html>"""
