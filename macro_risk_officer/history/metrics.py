"""
MRO Phase 4 — Scheduler KPI telemetry.

SchedulerMetrics  — in-process counters for one scheduler lifetime:
  cache_hit_ratio        = hits / (hits + misses)       [0.0 – 1.0]
  macro_availability_pct = successes / (successes + failures) * 100

FetchLog  — SQLite-backed telemetry for cross-invocation KPI reporting.
  Each attempted refresh is logged as a row so that the `kpi` CLI command
  can compute availability % from the full history, not just the current
  scheduler instance.

KpiReport — computes and formats the Phase-4 release-gate KPI table from
  a combination of in-process metrics and the persistent fetch log.

Usage (from MacroScheduler):
    self._metrics = SchedulerMetrics()
    self._fetch_log = FetchLog()          # writes to shared SQLite DB

Usage (from CLI `kpi` command):
    report = KpiReport.from_db()
    print(report.format())
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "outcomes.db"

_CREATE_FETCH_LOG = """
CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    attempted_at TEXT    NOT NULL,
    success      INTEGER NOT NULL,   -- 1 = context returned, 0 = failed/empty
    source_mask  TEXT,               -- comma-separated sources that contributed, e.g. "finnhub,fred"
    event_count  INTEGER,            -- number of events after normalisation (NULL on failure)
    error_hint   TEXT                -- short error class name or NULL on success
);
"""


# ── In-process counters ────────────────────────────────────────────────────────


@dataclass
class SchedulerMetrics:
    """
    Lightweight counters maintained for the lifetime of one MacroScheduler instance.

    The scheduler increments these on every get_context() call so that a
    long-lived process (e.g., the FastAPI server) can inspect hit/miss and
    availability ratios at any point.
    """

    cache_hits: int = 0
    cache_misses: int = 0
    fetch_successes: int = 0
    fetch_failures: int = 0
    last_fetch_epoch: float = field(default_factory=lambda: 0.0)

    @property
    def cache_hit_ratio(self) -> Optional[float]:
        """Fraction of get_context() calls served from cache. None if no calls yet."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else None

    @property
    def macro_availability_pct(self) -> Optional[float]:
        """Percentage of refresh attempts that returned a valid MacroContext."""
        total = self.fetch_successes + self.fetch_failures
        return 100.0 * self.fetch_successes / total if total > 0 else None

    def context_age_seconds(self) -> Optional[float]:
        """Seconds since the last successful refresh, or None if never fetched."""
        if self.last_fetch_epoch == 0.0:
            return None
        return time.monotonic() - self.last_fetch_epoch


# ── Persistent fetch log ───────────────────────────────────────────────────────


class FetchLog:
    """
    Appends one row per refresh attempt to the `fetch_log` SQLite table.

    Shares the same DB file as OutcomeTracker so there is a single data/
    directory to back up or inspect.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path: Path = db_path or _DEFAULT_DB
        self._init_table()

    def record_success(
        self,
        source_mask: str,
        event_count: int,
    ) -> None:
        """Log a successful refresh."""
        self._insert(success=1, source_mask=source_mask, event_count=event_count, error_hint=None)

    def record_failure(self, error_hint: str) -> None:
        """Log a failed refresh (no context produced)."""
        self._insert(success=0, source_mask=None, event_count=None, error_hint=error_hint[:120])

    # ── Private ─────────────────────────────────────────────────────────────

    def _init_table(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(_CREATE_FETCH_LOG)

    def _insert(
        self,
        success: int,
        source_mask: Optional[str],
        event_count: Optional[int],
        error_hint: Optional[str],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO fetch_log (attempted_at, success, source_mask, event_count, error_hint)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, success, source_mask, event_count, error_hint),
            )


# ── KPI report ────────────────────────────────────────────────────────────────


class KpiReport:
    """
    Reads from the persistent fetch_log table to compute Phase-4 release-gate KPIs.

    Release-gate criteria (non-blocking — informational only at P4):
      ✓ Macro availability  ≥ 80 %   (at least 4 in 5 refresh attempts succeed)
      ✓ Cache hit ratio     ≥ 60 %   (in-process; not tracked across invocations)
      ✓ Context freshness   < stale threshold (from thresholds.yaml scheduler.stale_threshold_seconds)
    """

    def __init__(
        self,
        total: int,
        successes: int,
        failures: int,
        last_attempt_at: Optional[str],
        source_breakdown: dict[str, int],
        error_breakdown: dict[str, int],
        stale_threshold_seconds: int = 3600,
    ) -> None:
        self.total = total
        self.successes = successes
        self.failures = failures
        self.last_attempt_at = last_attempt_at
        self.source_breakdown = source_breakdown
        self.error_breakdown = error_breakdown
        self.stale_threshold_seconds = stale_threshold_seconds

    @classmethod
    def from_db(
        cls,
        db_path: Optional[Path] = None,
        stale_threshold_seconds: int = 3600,
    ) -> "KpiReport":
        """Load telemetry from SQLite and construct a KpiReport."""
        path = db_path or _DEFAULT_DB
        path.parent.mkdir(parents=True, exist_ok=True)

        # Ensure table exists (first run before any fetch)
        with sqlite3.connect(path) as conn:
            conn.execute(_CREATE_FETCH_LOG)
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                "SELECT COUNT(*) AS n, "
                "  SUM(success) AS s, "
                "  MAX(attempted_at) AS last_at "
                "FROM fetch_log"
            ).fetchone()
            total = row["n"] or 0
            successes = int(row["s"] or 0)
            last_at = row["last_at"]

            # Source breakdown (successful fetches only)
            source_rows = conn.execute(
                "SELECT source_mask, COUNT(*) AS n FROM fetch_log "
                "WHERE success = 1 AND source_mask IS NOT NULL "
                "GROUP BY source_mask ORDER BY n DESC LIMIT 10"
            ).fetchall()
            source_breakdown = {r["source_mask"]: r["n"] for r in source_rows}

            # Error breakdown (failed fetches)
            error_rows = conn.execute(
                "SELECT error_hint, COUNT(*) AS n FROM fetch_log "
                "WHERE success = 0 AND error_hint IS NOT NULL "
                "GROUP BY error_hint ORDER BY n DESC LIMIT 10"
            ).fetchall()
            error_breakdown = {r["error_hint"]: r["n"] for r in error_rows}

        return cls(
            total=total,
            successes=successes,
            failures=total - successes,
            last_attempt_at=last_at,
            source_breakdown=source_breakdown,
            error_breakdown=error_breakdown,
            stale_threshold_seconds=stale_threshold_seconds,
        )

    @property
    def availability_pct(self) -> Optional[float]:
        if self.total == 0:
            return None
        return 100.0 * self.successes / self.total

    def _freshness_status(self) -> str:
        if not self.last_attempt_at:
            return "UNKNOWN (no fetch history)"
        try:
            last_dt = datetime.fromisoformat(self.last_attempt_at)
            age_s = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if age_s < self.stale_threshold_seconds:
                return f"FRESH  ({age_s / 60:.0f} min ago; threshold {self.stale_threshold_seconds // 60} min)"
            return (
                f"STALE  ({age_s / 60:.0f} min ago; threshold {self.stale_threshold_seconds // 60} min) ⚠"
            )
        except Exception:
            return f"UNKNOWN ({self.last_attempt_at!r})"

    def _gate(self, value: Optional[float], threshold: float, label: str) -> str:
        if value is None:
            return f"  {label:<30} N/A   (no data yet)"
        ok = "✓" if value >= threshold else "✗"
        return f"  {label:<30} {value:5.1f}%  (gate ≥ {threshold:.0f}%)  {ok}"

    def format(self) -> str:
        lines = [
            "=== MRO KPI REPORT — PHASE-4 RELEASE GATE ===",
            "",
            f"  Total refresh attempts : {self.total}",
            f"  Successes              : {self.successes}",
            f"  Failures               : {self.failures}",
            "",
            "── RELEASE-GATE KPIs ─────────────────────────────────",
            self._gate(self.availability_pct, 80.0, "Macro availability %"),
            f"  {'Context freshness':<30} {self._freshness_status()}",
            "",
            "  Note: Cache hit ratio is in-process only and resets on",
            "  each CLI invocation. Run `python -m macro_risk_officer status`",
            "  in a long-lived process to observe the cache ratio.",
        ]

        if self.source_breakdown:
            lines += ["", "── SUCCESSFUL-FETCH SOURCE MIX ───────────────────────"]
            for mask, count in self.source_breakdown.items():
                pct = 100.0 * count / self.successes if self.successes else 0.0
                lines.append(f"  {mask:<35} {count:>4} ({pct:.0f}%)")

        if self.error_breakdown:
            lines += ["", "── FAILURE CAUSES ────────────────────────────────────"]
            for hint, count in self.error_breakdown.items():
                lines.append(f"  {hint:<55} {count:>4}")

        avail = self.availability_pct
        if avail is None:
            verdict = "PENDING — no fetch history yet"
        elif avail >= 80.0:
            verdict = "PASS"
        else:
            verdict = "FAIL — macro availability below 80% gate"

        lines += ["", f"  Gate verdict: {verdict}", ""]
        return "\n".join(lines)
