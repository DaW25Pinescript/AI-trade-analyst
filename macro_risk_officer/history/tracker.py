"""
Outcome tracker — MRO-P3 implementation.

Records MacroContext snapshots alongside the Arbiter verdict for each run.
Provides an audit report summarising regime distribution, decision
breakdown, and confidence statistics across all recorded runs.

No price-outcome tracking in this phase — that requires a live price feed.
The recorded data is sufficient for:
  - Human review of macro context quality over time
  - Identifying systematic bias (e.g. always risk_off when instrument is XAUUSD)
  - Confidence distribution analysis
  - Pre-flight for future price-outcome integration (the schema is forward-ready)

Storage: SQLite at macro_risk_officer/data/outcomes.db (auto-created).
The DB path can be overridden via constructor for testing.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from macro_risk_officer.core.models import MacroContext

if TYPE_CHECKING:
    from ai_analyst.models.arbiter_output import FinalVerdict

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "outcomes.db"

_CREATE_TABLE = """
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
    risk_override        INTEGER
);
"""


class OutcomeTracker:
    """
    Persists MacroContext + Arbiter verdict snapshots to SQLite and
    generates an audit report from the accumulated history.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path: Path = db_path or _DEFAULT_DB
        self._init_db()

    # ── Public interface ────────────────────────────────────────────────────

    def record(
        self,
        context: MacroContext,
        run_id: str,
        instrument: str = "UNKNOWN",
        verdict: Optional[FinalVerdict] = None,
    ) -> None:
        """
        Persist a MacroContext snapshot alongside the Arbiter verdict summary.

        Arguments:
            context    : The MacroContext produced for this run.
            run_id     : Unique run identifier from GroundTruthPacket.
            instrument : Trading instrument (e.g. "XAUUSD").
            verdict    : FinalVerdict from the Arbiter (optional — may be None
                         if the run errored before the Arbiter stage).
        """
        now = datetime.now(timezone.utc).isoformat()

        decision = None
        overall_conf = None
        analyst_agreement = None
        risk_override = None

        if verdict is not None:
            decision = getattr(verdict, "decision", None)
            overall_conf = getattr(verdict, "overall_confidence", None)
            analyst_agreement = getattr(verdict, "analyst_agreement_pct", None)
            risk_ov = getattr(verdict, "risk_override_applied", None)
            risk_override = int(risk_ov) if risk_ov is not None else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, instrument, recorded_at, regime, vol_bias,
                    conflict_score, confidence, time_horizon_days,
                    active_event_ids, explanation,
                    decision, overall_confidence, analyst_agreement, risk_override
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    instrument,
                    now,
                    context.regime,
                    context.vol_bias,
                    context.conflict_score,
                    context.confidence,
                    context.time_horizon_days,
                    json.dumps(context.active_event_ids),
                    json.dumps(context.explanation),
                    decision,
                    overall_conf,
                    analyst_agreement,
                    risk_override,
                ),
            )

    def audit_report(self) -> str:
        """
        Generate a human-readable audit report from the recorded run history.
        Returns an empty-state message if no runs have been recorded.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

            if total == 0:
                return (
                    "=== MRO AUDIT REPORT ===\n"
                    "No runs recorded yet. Runs are recorded automatically\n"
                    "each time the full analysis pipeline completes.\n"
                )

            regime_rows = conn.execute(
                "SELECT regime, COUNT(*) AS n FROM runs GROUP BY regime ORDER BY n DESC"
            ).fetchall()

            vol_rows = conn.execute(
                "SELECT vol_bias, COUNT(*) AS n FROM runs GROUP BY vol_bias ORDER BY n DESC"
            ).fetchall()

            decision_rows = conn.execute(
                "SELECT decision, COUNT(*) AS n FROM runs "
                "WHERE decision IS NOT NULL GROUP BY decision ORDER BY n DESC"
            ).fetchall()

            conf_rows = conn.execute(
                "SELECT regime, "
                "  ROUND(AVG(confidence), 3)         AS macro_conf, "
                "  ROUND(AVG(overall_confidence), 3) AS arbiter_conf, "
                "  ROUND(AVG(conflict_score), 3)     AS avg_conflict "
                "FROM runs GROUP BY regime ORDER BY regime"
            ).fetchall()

            recent = conn.execute(
                "SELECT run_id, instrument, recorded_at, regime, decision "
                "FROM runs ORDER BY id DESC LIMIT 5"
            ).fetchall()

        lines = [
            f"=== MRO AUDIT REPORT ({total} runs) ===",
            "",
            "── REGIME DISTRIBUTION ──────────────────────────────",
        ]
        for row in regime_rows:
            pct = 100.0 * row["n"] / total
            lines.append(f"  {row['regime']:<12} {row['n']:>5} runs  ({pct:.0f}%)")

        lines += ["", "── VOLATILITY BIAS ──────────────────────────────────"]
        for row in vol_rows:
            pct = 100.0 * row["n"] / total
            lines.append(f"  {row['vol_bias']:<12} {row['n']:>5} runs  ({pct:.0f}%)")

        if decision_rows:
            lines += ["", "── DECISION BREAKDOWN ───────────────────────────────"]
            for row in decision_rows:
                pct = 100.0 * row["n"] / total
                label = row["decision"] or "N/A"
                lines.append(f"  {label:<30} {row['n']:>4} runs  ({pct:.0f}%)")

        lines += ["", "── CONFIDENCE BY REGIME ─────────────────────────────"]
        lines.append(
            f"  {'Regime':<12} {'MRO conf':>10} {'Arbiter conf':>14} {'Conflict':>10}"
        )
        for row in conf_rows:
            arb = f"{row['arbiter_conf']:.3f}" if row["arbiter_conf"] is not None else "     N/A"
            lines.append(
                f"  {row['regime']:<12} {row['macro_conf']:>10.3f} "
                f"{arb:>14} {row['avg_conflict']:>10.3f}"
            )

        lines += ["", "── MOST RECENT 5 RUNS ───────────────────────────────"]
        for row in recent:
            decision_label = row["decision"] or "N/A"
            lines.append(
                f"  {row['run_id'][:8]}…  {row['instrument']:<8}  "
                f"{row['regime']:<10}  {decision_label}"
            )

        return "\n".join(lines)

    # ── Private ─────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_CREATE_TABLE)
