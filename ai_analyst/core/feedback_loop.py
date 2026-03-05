"""
Phase 7 — Feedback Loop: Outcomes → Prompt Refinement.

Reads AAR outcome data from the MRO SQLite DB (OutcomeTracker) and the
per-run usage/verdict JSONL files to surface patterns that inform prompt
improvement.

Patterns detected:
  1. Decision accuracy by regime — which regimes produce correct vs. incorrect
     directional calls? Low-accuracy regimes need persona calibration.
  2. Confidence calibration — are high-confidence verdicts actually more accurate?
     If not, the arbiter prompt over-weights certain evidence types.
  3. Persona dominance — do certain personas always "win" the arbiter? If one
     persona's recommended_action matches the final decision > 80% of the time,
     the prompt ensemble is under-diversified.
  4. No-trade rate by regime — high no-trade in benign regimes suggests
     over-conservative prompts; low no-trade in risk-off regimes suggests
     under-conservative prompts.

Output: a FeedbackReport dataclass that can be printed to the console or
serialised to JSON for downstream tooling.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path(__file__).parent.parent.parent / "macro_risk_officer" / "data" / "outcomes.db"
_RUNS_DIR = Path(__file__).parent.parent / "output" / "runs"


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class RegimeAccuracy:
    regime: str
    total: int
    correct: int
    accuracy_pct: float
    no_trade_count: int
    no_trade_pct: float


@dataclass
class ConfidenceBucket:
    bucket: str  # e.g. "0.0–0.3", "0.3–0.6", "0.6–1.0"
    total: int
    correct: int
    accuracy_pct: float


@dataclass
class PersonaDominance:
    """Tracks how often a persona's action matches the final verdict."""
    persona: str
    match_count: int
    total_runs: int
    dominance_pct: float
    flagged: bool  # True if dominance > 80%


@dataclass
class FeedbackReport:
    """Aggregated feedback report for prompt refinement."""
    total_runs: int
    priced_runs: int
    regime_accuracy: list[RegimeAccuracy] = field(default_factory=list)
    confidence_calibration: list[ConfidenceBucket] = field(default_factory=list)
    persona_dominance: list[PersonaDominance] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def format(self) -> str:
        """Human-readable report."""
        lines = [
            f"=== FEEDBACK LOOP REPORT ({self.total_runs} runs, {self.priced_runs} priced) ===",
            "",
        ]

        # Regime accuracy
        if self.regime_accuracy:
            lines.append("── DECISION ACCURACY BY REGIME ──────────────────────")
            lines.append(f"  {'Regime':<14} {'Correct':>8} {'Total':>6} {'Acc%':>6} {'NoTrade%':>9}")
            for ra in self.regime_accuracy:
                lines.append(
                    f"  {ra.regime:<14} {ra.correct:>8} {ra.total:>6} "
                    f"{ra.accuracy_pct:>5.0f}% {ra.no_trade_pct:>8.0f}%"
                )
            lines.append("")

        # Confidence calibration
        if self.confidence_calibration:
            lines.append("── CONFIDENCE CALIBRATION ───────────────────────────")
            lines.append(f"  {'Bucket':<14} {'Correct':>8} {'Total':>6} {'Acc%':>6}")
            for cb in self.confidence_calibration:
                lines.append(
                    f"  {cb.bucket:<14} {cb.correct:>8} {cb.total:>6} {cb.accuracy_pct:>5.0f}%"
                )
            lines.append("")

        # Persona dominance
        if self.persona_dominance:
            lines.append("── PERSONA DOMINANCE ────────────────────────────────")
            lines.append(f"  {'Persona':<20} {'Match':>6} {'Total':>6} {'Dom%':>6} {'Flag':>6}")
            for pd in self.persona_dominance:
                flag = " ⚠" if pd.flagged else ""
                lines.append(
                    f"  {pd.persona:<20} {pd.match_count:>6} {pd.total_runs:>6} "
                    f"{pd.dominance_pct:>5.0f}%{flag}"
                )
            lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("── RECOMMENDATIONS ─────────────────────────────────")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"  {i}. {rec}")
            lines.append("")

        if not any([self.regime_accuracy, self.confidence_calibration, self.persona_dominance]):
            lines.append("  No outcome data available yet.")
            lines.append("  Run `python -m macro_risk_officer update-outcomes` to backfill prices,")
            lines.append("  then re-run this report.")
            lines.append("")

        return "\n".join(lines)


# ── Report builder ────────────────────────────────────────────────────────────


_CONFIDENCE_BUCKETS = [
    ("low (0–0.3)", 0.0, 0.3),
    ("mid (0.3–0.6)", 0.3, 0.6),
    ("high (0.6–1.0)", 0.6, 1.01),
]


def build_feedback_report(
    db_path: Optional[Path] = None,
    runs_dir: Optional[Path] = None,
) -> FeedbackReport:
    """
    Build a FeedbackReport from the MRO outcomes DB and per-run output files.

    Args:
        db_path:  Path to outcomes.db (defaults to macro_risk_officer/data/outcomes.db).
        runs_dir: Path to ai_analyst/output/runs/ (for per-run verdict files).
    """
    db = db_path or _DEFAULT_DB
    rd = runs_dir or _RUNS_DIR

    if not db.exists():
        return FeedbackReport(total_runs=0, priced_runs=0,
                              recommendations=["No outcomes database found. Run analyses first."])

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        priced = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE pct_change_24h IS NOT NULL"
        ).fetchone()[0]

        regime_acc = _regime_accuracy(conn)
        conf_cal = _confidence_calibration(conn)

    persona_dom = _persona_dominance(rd)
    recs = _generate_recommendations(regime_acc, conf_cal, persona_dom)

    return FeedbackReport(
        total_runs=total,
        priced_runs=priced,
        regime_accuracy=regime_acc,
        confidence_calibration=conf_cal,
        persona_dominance=persona_dom,
        recommendations=recs,
    )


def _regime_accuracy(conn: sqlite3.Connection) -> list[RegimeAccuracy]:
    """Decision accuracy and no-trade rate grouped by macro regime."""
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

    results = []
    for row in rows:
        priced_dir = row["priced_directional"] or 0
        acc = (100.0 * row["correct"] / priced_dir) if priced_dir > 0 else 0.0
        nt_pct = (100.0 * row["no_trade"] / row["total"]) if row["total"] > 0 else 0.0
        results.append(RegimeAccuracy(
            regime=row["regime"],
            total=row["total"],
            correct=row["correct"],
            accuracy_pct=acc,
            no_trade_count=row["no_trade"],
            no_trade_pct=nt_pct,
        ))
    return results


def _confidence_calibration(conn: sqlite3.Connection) -> list[ConfidenceBucket]:
    """Are high-confidence verdicts actually more accurate?"""
    rows = conn.execute(
        """
        SELECT overall_confidence, pct_change_24h, predicted_direction
        FROM runs
        WHERE pct_change_24h IS NOT NULL
          AND predicted_direction != 0
          AND overall_confidence IS NOT NULL
        """
    ).fetchall()

    buckets: dict[str, list[bool]] = {label: [] for label, _, _ in _CONFIDENCE_BUCKETS}

    for row in rows:
        conf = row["overall_confidence"]
        correct = (
            (row["predicted_direction"] > 0 and row["pct_change_24h"] > 0)
            or (row["predicted_direction"] < 0 and row["pct_change_24h"] < 0)
        )
        for label, lo, hi in _CONFIDENCE_BUCKETS:
            if lo <= conf < hi:
                buckets[label].append(correct)
                break

    results = []
    for label, _, _ in _CONFIDENCE_BUCKETS:
        items = buckets[label]
        total = len(items)
        correct = sum(items)
        acc = (100.0 * correct / total) if total > 0 else 0.0
        results.append(ConfidenceBucket(
            bucket=label,
            total=total,
            correct=correct,
            accuracy_pct=acc,
        ))
    return results


def _persona_dominance(runs_dir: Path) -> list[PersonaDominance]:
    """
    Check whether a single persona's recommended_action consistently matches
    the final verdict decision, suggesting under-diversification.

    Reads per-run final_verdict.json and analyst output files.
    """
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

        # Map decision to recommended_action format
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
                # Use filename as persona proxy
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
        results.append(PersonaDominance(
            persona=persona,
            match_count=matches,
            total_runs=total,
            dominance_pct=dom_pct,
            flagged=dom_pct > 80.0 and total >= 3,
        ))
    return results


def _generate_recommendations(
    regime_acc: list[RegimeAccuracy],
    conf_cal: list[ConfidenceBucket],
    persona_dom: list[PersonaDominance],
) -> list[str]:
    """Generate actionable recommendations from the analysis."""
    recs: list[str] = []

    # Low-accuracy regimes
    for ra in regime_acc:
        if ra.accuracy_pct < 50.0 and ra.total >= 3:
            recs.append(
                f"Regime '{ra.regime}' has {ra.accuracy_pct:.0f}% accuracy over "
                f"{ra.total} runs — consider adding regime-specific caution to analyst prompts."
            )

    # Over-conservative in benign regimes
    for ra in regime_acc:
        if ra.regime in ("risk_on", "neutral") and ra.no_trade_pct > 60.0 and ra.total >= 3:
            recs.append(
                f"Regime '{ra.regime}' shows {ra.no_trade_pct:.0f}% NO_TRADE rate — "
                f"prompts may be over-conservative in benign conditions."
            )

    # Under-conservative in risk-off
    for ra in regime_acc:
        if ra.regime == "risk_off" and ra.no_trade_pct < 20.0 and ra.total >= 3:
            recs.append(
                f"Regime 'risk_off' shows only {ra.no_trade_pct:.0f}% NO_TRADE rate — "
                f"consider strengthening risk-off caution in analyst prompts."
            )

    # Miscalibrated confidence
    for cb in conf_cal:
        if "high" in cb.bucket and cb.accuracy_pct < 50.0 and cb.total >= 3:
            recs.append(
                f"High-confidence verdicts ({cb.bucket}) have only {cb.accuracy_pct:.0f}% "
                f"accuracy — arbiter may be over-confident. Review confidence weighting rules."
            )

    if conf_cal and len(conf_cal) >= 2:
        low_bucket = conf_cal[0]
        high_bucket = conf_cal[-1]
        if (low_bucket.total >= 3 and high_bucket.total >= 3
                and low_bucket.accuracy_pct > high_bucket.accuracy_pct):
            recs.append(
                "Low-confidence verdicts are MORE accurate than high-confidence ones — "
                "confidence scoring is inverted. Audit the arbiter weighting rules."
            )

    # Persona dominance
    for pd in persona_dom:
        if pd.flagged:
            recs.append(
                f"Persona '{pd.persona}' matches the final decision {pd.dominance_pct:.0f}% "
                f"of the time — ensemble may be under-diversified. Consider rebalancing "
                f"persona weights or adding a contrarian lens."
            )

    if not recs:
        recs.append("No actionable issues detected. Continue collecting outcome data.")

    return recs
