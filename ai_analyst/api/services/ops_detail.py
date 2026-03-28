"""Agent Operations — Detail projection service (PR-OPS-4b).

Projects entity-level detail from multiple read-side sources:
  - Roster (identity, department, visual_family, capabilities)
  - Profile registry (purpose, responsibilities, type_specific variant)
  - Health snapshot (run_state, health_state via app_state or direct item)
  - Recent participation scan (bounded: max 20 dirs or 7 days, capped at 5)

Graceful degradation: health unavailable → degraded data_state, not 500.
No pipeline changes. No new persistence. Read-only projection.

Spec: docs/PR_OPS_4_SPEC_FINAL.md §7
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from ai_analyst.api.models.ops import (
    AgentHealthItem,
    DepartmentKey,
    RelationshipType,
)
from ai_analyst.api.models.ops_detail import (
    AgentDetailResponse,
    EntityDependency,
    EntityIdentity,
    EntityStatus,
    RecentParticipation,
)
from ai_analyst.api.services.ops_profile_registry import get_entity_profile
from ai_analyst.api.services.ops_roster import (
    get_all_roster_ids,
    get_entity_lookup,
    get_relationships,
    persona_to_roster_id,
)

logger = logging.getLogger(__name__)

_CONTRACT_VERSION = "2026.03"

# ── Bounded scan limits (§7) ────────────────────────────────────────────────

_MAX_RUN_DIRS = 20
_MAX_RUN_AGE_DAYS = 7
_MAX_RECENT_PARTICIPATION = 5
_MAX_CONTRIBUTION_SUMMARY_LEN = 500


class DetailProjectionError(Exception):
    """Raised when detail projection encounters unrecoverable errors."""


# ── Internal helpers ────────────────────────────────────────────────────────


def _build_dependencies(entity_id: str) -> list[EntityDependency]:
    """Derive upstream/downstream dependencies from roster relationships."""
    roster = get_entity_lookup()
    deps: list[EntityDependency] = []
    for rel in get_relationships():
        if rel.from_ == entity_id:
            # This entity feeds/supports/challenges the target → downstream
            target = roster.get(rel.to)
            if target:
                deps.append(EntityDependency(
                    entity_id=rel.to,
                    display_name=target.display_name,
                    direction="downstream",
                    relationship_type=rel.type,
                ))
        elif rel.to == entity_id:
            # Something feeds/supports/challenges this entity → upstream
            source = roster.get(rel.from_)
            if source:
                deps.append(EntityDependency(
                    entity_id=rel.from_,
                    display_name=source.display_name,
                    direction="upstream",
                    relationship_type=rel.type,
                ))
    return deps


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, appending '…' if truncated."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _scan_recent_participation(
    entity_id: str,
    run_base: Path | None = None,
) -> list[RecentParticipation]:
    """Scan recent run artifacts for entity participation.

    Bounded: max 20 run dirs or 7 days lookback, whichever smaller.
    Returns at most 5 entries, most recent first.
    """
    if run_base is None:
        run_base = Path("ai_analyst/output/runs")

    if not run_base.is_dir():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=_MAX_RUN_AGE_DAYS)
    entries: list[RecentParticipation] = []

    # Sort run dirs by name descending (most recent first by convention)
    try:
        run_dirs = sorted(run_base.iterdir(), reverse=True)
    except OSError:
        return []

    scanned = 0
    for run_dir in run_dirs:
        if scanned >= _MAX_RUN_DIRS:
            break
        if not run_dir.is_dir():
            continue
        scanned += 1

        rr_path = run_dir / "run_record.json"
        if not rr_path.is_file():
            continue

        try:
            rr = json.loads(rr_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        # Check timestamp age
        ts_str = rr.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                pass

        run_id = rr.get("run_id", run_dir.name)

        # Check if entity participated in this run
        participation = _extract_participation(entity_id, rr)
        if participation is not None:
            participation_entry = RecentParticipation(
                run_id=run_id,
                run_completed_at=rr.get("timestamp"),
                verdict_direction=participation.get("verdict_direction"),
                was_overridden=participation.get("was_overridden", False),
                contribution_summary=_truncate(
                    participation.get("summary", "Participated in run"),
                    _MAX_CONTRIBUTION_SUMMARY_LEN,
                ),
            )
            entries.append(participation_entry)

        if len(entries) >= _MAX_RECENT_PARTICIPATION:
            break

    return entries


def _extract_participation(entity_id: str, rr: dict) -> dict | None:
    """Extract participation info for an entity from a run_record.

    Returns a dict with verdict_direction, was_overridden, summary — or None.
    """
    # Arbiter participation
    if entity_id == "arbiter":
        arbiter = rr.get("arbiter", {})
        if arbiter.get("ran"):
            verdict = arbiter.get("verdict")
            direction = None
            if verdict:
                v_lower = verdict.lower()
                if v_lower in ("bullish", "bearish", "neutral", "abstain"):
                    direction = v_lower
                elif "no_trade" in v_lower or "no trade" in v_lower:
                    direction = "neutral"
            return {
                "verdict_direction": direction,
                "was_overridden": False,
                "summary": f"Arbiter verdict: {verdict or 'unknown'}",
            }
        return None

    # Persona participation — check analysts array
    analysts = rr.get("analysts", [])
    for analyst in analysts:
        persona = analyst.get("persona", "")
        roster_id = persona_to_roster_id(persona)
        if roster_id == entity_id:
            status = analyst.get("status", "unknown")
            return {
                "verdict_direction": None,  # Need audit log for stance
                "was_overridden": False,
                "summary": f"Analyst {persona}: {status}",
            }

    # Check skipped/failed analysts
    for analyst in rr.get("analysts_skipped", []):
        persona = analyst.get("persona", "")
        if persona_to_roster_id(persona) == entity_id:
            reason = analyst.get("reason", "unknown")
            return {
                "verdict_direction": None,
                "was_overridden": False,
                "summary": f"Skipped: {reason}",
            }

    for analyst in rr.get("analysts_failed", []):
        persona = analyst.get("persona", "")
        if persona_to_roster_id(persona) == entity_id:
            reason = analyst.get("reason", "unknown")
            return {
                "verdict_direction": None,
                "was_overridden": False,
                "summary": f"Failed: {reason}",
            }

    # Officers / subsystems — check stage presence as proxy
    if entity_id == "market_data_officer":
        stages = rr.get("stages", [])
        for stage in stages:
            if stage.get("stage") == "chart_setup":
                return {
                    "verdict_direction": None,
                    "was_overridden": False,
                    "summary": f"Chart setup: {stage.get('status', 'unknown')}",
                }

    if entity_id == "macro_risk_officer":
        stages = rr.get("stages", [])
        for stage in stages:
            if stage.get("stage") == "macro_context":
                return {
                    "verdict_direction": None,
                    "was_overridden": False,
                    "summary": f"Macro context: {stage.get('status', 'unknown')}",
                }

    return None


# ── Public projection function ──────────────────────────────────────────────


def project_detail(
    entity_id: str,
    health_item: AgentHealthItem | None = None,
    run_base: Path | None = None,
) -> AgentDetailResponse:
    """Build the entity detail response.

    Parameters
    ----------
    entity_id : str
        Plain slug entity ID (e.g. "persona_default_analyst", "arbiter").
    health_item : AgentHealthItem | None
        Pre-projected health item for this entity. If None, status uses
        unavailable defaults and data_state degrades.
    run_base : Path | None
        Override for run artifact base directory (for testing).

    Returns
    -------
    AgentDetailResponse

    Raises
    ------
    DetailProjectionError
        If entity_id is not found in both roster and profile registry.
    """
    # 1. Roster lookup
    roster_entity = get_entity_lookup().get(entity_id)
    if roster_entity is None:
        raise DetailProjectionError(
            f"Entity '{entity_id}' not found in roster"
        )

    # 2. Profile lookup
    profile = get_entity_profile(entity_id)
    if profile is None:
        raise DetailProjectionError(
            f"Entity '{entity_id}' not found in profile registry"
        )

    # 3. Build identity from roster + profile
    identity = EntityIdentity(
        purpose=profile.purpose,
        role=roster_entity.role,
        visual_family=roster_entity.visual_family,
        capabilities=roster_entity.capabilities,
        responsibilities=profile.responsibilities,
        initials=roster_entity.initials,
    )

    # 4. Build status from health item (graceful degradation)
    data_state = "live"
    if health_item is not None:
        status = EntityStatus(
            run_state=health_item.run_state,
            health_state=health_item.health_state,
            last_active_at=health_item.last_active_at,
            last_run_id=health_item.last_run_id,
            health_summary=health_item.health_summary,
        )
        if health_item.health_state in ("stale", "degraded"):
            data_state = "stale"
    else:
        # No health data — degrade gracefully
        status = EntityStatus(
            run_state="idle",
            health_state="unavailable",
            health_summary="No health signals available",
        )
        data_state = "stale"

    # 5. Build dependencies
    dependencies = _build_dependencies(entity_id)

    # 6. Scan recent participation
    recent = _scan_recent_participation(entity_id, run_base=run_base)

    # 7. Assemble warnings (empty for now — no runtime warning source)
    recent_warnings: list[str] = []

    # 8. Build response
    return AgentDetailResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state=data_state,
        source_of_truth="roster+profile+health",
        entity_id=entity_id,
        entity_type=roster_entity.type,
        display_name=roster_entity.display_name,
        department=roster_entity.department,
        identity=identity,
        status=status,
        dependencies=dependencies,
        recent_participation=recent,
        recent_warnings=recent_warnings,
        type_specific=profile.type_specific,
    )
