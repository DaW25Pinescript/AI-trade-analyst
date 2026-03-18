"""Evidence Snapshot Builder — assembles lens outputs into an immutable snapshot.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Sections 4.6, 5, 8.1

Responsibilities:
- Collect LensOutput objects from v1 lenses
- Namespace successful lens data under lenses.<lens_id>
- Record failed lenses in meta.failed_lenses / meta.lens_errors
- Record inactive lenses in meta.inactive_lenses
- Compute derived alignment_score, conflict_score, signal_state
- Generate deterministic snapshot_id from content hash
- Derive run_status (SUCCESS / DEGRADED / FAILED)
"""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel

from ai_analyst.lenses.base import LensOutput
from ai_analyst.lenses.registry import get_enabled_lens_ids, get_inactive_lens_ids, get_registry_snapshot


class SnapshotBuildResult(BaseModel):
    snapshot: dict | None
    run_status: Literal["SUCCESS", "DEGRADED", "FAILED"]
    error: str | None = None


# Spec Section 5 — deterministic direction mapping
DIRECTION_MAP: dict[str, int] = {
    "bullish": +1, "positive": +1, "above": +1, "expanding": +1,
    "bearish": -1, "negative": -1, "below": -1, "reversing": -1,
    "neutral": 0, "flat": 0, "mixed": 0, "unknown": 0,
    "ranging": 0,
}

# Primary directional field paths per lens
_DIRECTION_PATHS: dict[str, tuple[str, ...]] = {
    "structure": ("trend", "local_direction"),
    "trend": ("direction", "overall"),
    "momentum": ("direction", "state"),
}


def _extract_direction(lens_id: str, data: dict) -> str:
    """Extract the primary direction string from lens data."""
    path = _DIRECTION_PATHS.get(lens_id)
    if path is None:
        return "unknown"
    node = data
    for key in path:
        if not isinstance(node, dict):
            return "unknown"
        node = node.get(key, "unknown")
    return str(node) if node is not None else "unknown"


def _compute_derived(successful_lenses: dict[str, dict]) -> dict:
    """Compute derived alignment/conflict signals from successful lens data."""
    direction_values: list[int] = []
    for lens_id, data in successful_lenses.items():
        raw = _extract_direction(lens_id, data)
        direction_values.append(DIRECTION_MAP.get(raw, 0))

    if not direction_values or all(v == 0 for v in direction_values):
        alignment_score = 0.0
        conflict_score = 0.0
        signal_state = "NO_SIGNAL"
    else:
        mean = sum(direction_values) / len(direction_values)
        alignment_score = abs(mean)
        conflict_score = 1.0 - alignment_score
        signal_state = "SIGNAL"

    return {
        "alignment_score": alignment_score,
        "conflict_score": conflict_score,
        "signal_state": signal_state,
        "coverage": None,
        "persona_agreement_score": None,
    }


def _compute_snapshot_id(snapshot: dict) -> str:
    """Compute deterministic SHA-256 hash of snapshot content."""
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_evidence_snapshot(
    *,
    instrument: str,
    timeframe: str,
    timestamp: str,
    lens_outputs: list[LensOutput],
    lens_registry: list[dict] | None = None,
) -> SnapshotBuildResult:
    """Build an immutable evidence snapshot from lens outputs.

    Args:
        instrument: Trading instrument (e.g. "XAUUSD").
        timeframe: Analysis timeframe (e.g. "1H").
        timestamp: ISO-8601 timestamp of the analysis.
        lens_outputs: List of LensOutput objects from v1 lenses.
        lens_registry: Optional override for the lens registry (list of dicts).
            Defaults to the canonical v1 registry.

    Returns:
        SnapshotBuildResult with snapshot dict, run_status, and optional error.
    """
    if lens_registry is None:
        lens_registry = get_registry_snapshot()

    enabled_ids = [e["id"] for e in lens_registry if e.get("enabled", True)]
    inactive_ids = [e["id"] for e in lens_registry if not e.get("enabled", True)]

    # Index lens outputs by lens_id
    output_by_id: dict[str, LensOutput] = {lo.lens_id: lo for lo in lens_outputs}

    # Classify lenses
    successful_lenses: dict[str, dict] = {}
    active_lens_ids: list[str] = []
    failed_lens_ids: list[str] = []
    lens_errors: dict[str, str] = {}

    for lens_id in enabled_ids:
        lo = output_by_id.get(lens_id)
        if lo is None:
            # Enabled lens with no output — treat as failed
            failed_lens_ids.append(lens_id)
            lens_errors[lens_id] = "no output provided"
            continue

        if lo.status == "success" and lo.data is not None:
            successful_lenses[lens_id] = lo.data
            active_lens_ids.append(lens_id)
        else:
            failed_lens_ids.append(lens_id)
            lens_errors[lens_id] = lo.error or "unknown error"

    # Determine run_status
    if len(successful_lenses) == 0:
        run_status: Literal["SUCCESS", "DEGRADED", "FAILED"] = "FAILED"
    elif len(failed_lens_ids) > 0:
        run_status = "DEGRADED"
    else:
        run_status = "SUCCESS"

    # Build snapshot
    context = {
        "instrument": instrument,
        "timeframe": timeframe,
        "timestamp": timestamp,
    }

    derived = _compute_derived(successful_lenses)

    meta = {
        "active_lenses": active_lens_ids,
        "inactive_lenses": inactive_ids,
        "failed_lenses": failed_lens_ids,
        "lens_errors": lens_errors,
        "evidence_version": "v1.0",
        "snapshot_id": "",
    }

    snapshot: dict = {
        "context": context,
        "lenses": dict(successful_lenses),
        "derived": derived,
        "meta": meta,
    }

    # Compute and backfill snapshot_id
    snapshot["meta"]["snapshot_id"] = _compute_snapshot_id(snapshot)

    return SnapshotBuildResult(
        snapshot=snapshot,
        run_status=run_status,
    )
