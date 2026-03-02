"""
Outcome tracker — MRO-P3/P4 implementation.

Records MacroContext snapshots alongside the Arbiter verdict for each run.
In MRO-P4, price outcome columns are added (via schema migration) so that
`update-outcomes` can backfill T+1h/T+24h/T+5d prices and compute regime
accuracy scores visible in the audit report.

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
    risk_override        INTEGER,
    -- MRO-P4: price outcomes (backfilled by update-outcomes command)
    price_at_record      REAL,
    price_at_1h          REAL,
    price_at_24h         REAL,
    price_at_5d          REAL,
    pct_change_1h        REAL,
    pct_change_24h       REAL,
    pct_change_5d        REAL,
    predicted_direction  INTEGER
);
"""

# Columns added in MRO-P4 that may be absent in existing DBs
_P4_COLUMNS = [
    "price_at_record     REAL",
    "price_at_1h         REAL",
    "price_at_24h        REAL",
    "price_at_5d         REAL",
    "pct_change_1h       REAL",
    "pct_change_24h      REAL",
    "pct_change_5d       REAL",
    "predicted_direction INTEGER",
]


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
            verdict    : FinalVerdict from the Arbiter (optional).
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

            # MRO-P4: price outcome accuracy (only for priced runs where predicted_direction != 0)
            accuracy_rows = conn.execute(
                "SELECT regime, "
                "  COUNT(*) AS total, "
                "  SUM(CASE WHEN (predicted_direction > 0 AND pct_change_24h > 0) "
                "           OR  (predicted_direction < 0 AND pct_change_24h < 0) "
                "      THEN 1 ELSE 0 END) AS correct "
                "FROM runs "
                "WHERE pct_change_24h IS NOT NULL AND predicted_direction != 0 "
                "GROUP BY regime ORDER BY regime"
            ).fetchall()

            priced_count = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE price_at_record IS NOT NULL"
            ).fetchone()[0]

            recent = conn.execute(
                "SELECT run_id, instrument, recorded_at, regime, decision "
                "FROM runs ORDER BY id DESC LIMIT 5"
            ).fetchall()

        lines = [
            f"=== MRO AUDIT REPORT ({total} runs, {priced_count} priced) ===",
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

        # MRO-P4: regime accuracy section (only shown when price data exists)
        if accuracy_rows:
            lines += ["", "── REGIME ACCURACY (24h direction, priced runs) ─────"]
            lines.append(
                f"  {'Regime':<12} {'Correct':>9} {'Total':>7} {'Accuracy':>10}"
            )
            all_correct = sum(r["correct"] for r in accuracy_rows)
            all_total   = sum(r["total"]   for r in accuracy_rows)
            for row in accuracy_rows:
                acc = 100.0 * row["correct"] / row["total"] if row["total"] else 0.0
                lines.append(
                    f"  {row['regime']:<12} {row['correct']:>9} {row['total']:>7} {acc:>9.0f}%"
                )
            if all_total > 0:
                overall_acc = 100.0 * all_correct / all_total
                lines.append(
                    f"  {'Overall':<12} {all_correct:>9} {all_total:>7} {overall_acc:>9.0f}%"
                )
            lines.append(
                "  (run `python -m macro_risk_officer update-outcomes` to backfill prices)"
            )
        elif priced_count == 0 and total > 0:
            lines += [
                "",
                "── REGIME ACCURACY ──────────────────────────────────",
                "  No price data yet.",
                "  Run: python -m macro_risk_officer update-outcomes",
            ]

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
            self._migrate_db(conn)

    def _migrate_db(self, conn: sqlite3.Connection) -> None:
        """Add MRO-P4 columns to existing DBs that pre-date Phase 4."""
        for col_def in _P4_COLUMNS:
            col_name = col_def.split()[0]
            try:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass  # Column already exists — normal for fresh DBs
