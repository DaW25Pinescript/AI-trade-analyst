"""
Phase 3 — Pipeline metrics collection.

Collects per-run metrics (cost, latency, analyst agreement, node timings)
and exposes them via an in-memory store for the /metrics endpoint and
operator health dashboard.

Metrics are append-only and bounded (configurable max entries) to prevent
unbounded memory growth in long-running server processes.

Usage:
    from ..core.pipeline_metrics import metrics_store

    # Record a completed run
    metrics_store.record_run(run_summary)

    # Read aggregated metrics
    snapshot = metrics_store.snapshot()
"""
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class RunMetrics:
    """Metrics for a single completed pipeline run."""
    run_id: str
    timestamp: str                        # ISO 8601 UTC
    instrument: str
    session: str
    total_latency_ms: int                 # wall-clock time for entire pipeline
    llm_cost_usd: float                   # total LLM spend
    llm_calls: int                        # total LLM API calls
    llm_calls_failed: int                 # failed LLM calls
    analyst_count: int                    # valid analyst outputs
    analyst_agreement_pct: int            # from FinalVerdict
    decision: str                         # ENTER_LONG, ENTER_SHORT, etc.
    overall_confidence: float
    overlay_provided: bool
    deliberation_enabled: bool
    macro_context_available: bool
    node_timings: dict = field(default_factory=dict)  # node_name → ms


@dataclass
class MetricsSnapshot:
    """Aggregated metrics snapshot for the operator dashboard."""
    total_runs: int
    total_cost_usd: float
    avg_cost_per_run_usd: float
    avg_latency_ms: float
    avg_analyst_agreement_pct: float
    decision_distribution: dict           # decision → count
    instrument_distribution: dict         # instrument → count
    runs_last_hour: int
    runs_last_24h: int
    last_run_at: Optional[str]
    error_rate: float                     # failed_calls / total_calls
    recent_runs: list                     # last N RunMetrics as dicts


class MetricsStore:
    """
    Thread-safe in-memory metrics store with bounded history.

    Designed for single-process deployments. For multi-worker setups,
    each worker maintains its own store (acceptable for operator dashboards).
    """

    def __init__(self, max_entries: int = 500):
        self._lock = threading.Lock()
        self._runs: deque[RunMetrics] = deque(maxlen=max_entries)
        self._started_at: str = datetime.now(timezone.utc).isoformat()

    def record_run(self, metrics: RunMetrics) -> None:
        """Append a completed run's metrics."""
        with self._lock:
            self._runs.append(metrics)

    def snapshot(self) -> MetricsSnapshot:
        """Compute an aggregated snapshot from all recorded runs."""
        with self._lock:
            runs = list(self._runs)

        if not runs:
            return MetricsSnapshot(
                total_runs=0,
                total_cost_usd=0.0,
                avg_cost_per_run_usd=0.0,
                avg_latency_ms=0.0,
                avg_analyst_agreement_pct=0.0,
                decision_distribution={},
                instrument_distribution={},
                runs_last_hour=0,
                runs_last_24h=0,
                last_run_at=None,
                error_rate=0.0,
                recent_runs=[],
            )

        now = time.time()
        total_cost = sum(r.llm_cost_usd for r in runs)
        total_calls = sum(r.llm_calls for r in runs)
        failed_calls = sum(r.llm_calls_failed for r in runs)

        # Decision distribution
        decisions: dict[str, int] = {}
        for r in runs:
            decisions[r.decision] = decisions.get(r.decision, 0) + 1

        # Instrument distribution
        instruments: dict[str, int] = {}
        for r in runs:
            instruments[r.instrument] = instruments.get(r.instrument, 0) + 1

        # Time-windowed counts
        runs_1h = 0
        runs_24h = 0
        for r in runs:
            try:
                ts = datetime.fromisoformat(r.timestamp).timestamp()
                age = now - ts
                if age <= 3600:
                    runs_1h += 1
                if age <= 86400:
                    runs_24h += 1
            except (ValueError, OSError):
                pass

        n = len(runs)
        return MetricsSnapshot(
            total_runs=n,
            total_cost_usd=round(total_cost, 6),
            avg_cost_per_run_usd=round(total_cost / n, 6) if n else 0.0,
            avg_latency_ms=round(sum(r.total_latency_ms for r in runs) / n, 1) if n else 0.0,
            avg_analyst_agreement_pct=round(
                sum(r.analyst_agreement_pct for r in runs) / n, 1
            ) if n else 0.0,
            decision_distribution=decisions,
            instrument_distribution=instruments,
            runs_last_hour=runs_1h,
            runs_last_24h=runs_24h,
            last_run_at=runs[-1].timestamp if runs else None,
            error_rate=round(failed_calls / total_calls, 4) if total_calls else 0.0,
            recent_runs=[asdict(r) for r in list(runs)[-10:]],
        )

    @property
    def started_at(self) -> str:
        return self._started_at

    @property
    def run_count(self) -> int:
        with self._lock:
            return len(self._runs)


# Module-level singleton
metrics_store = MetricsStore()
