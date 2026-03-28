"""Agent Operations — Trace projection service (PR-OPS-4a).

Projects a run-level agent trace from existing read-side artifacts:
  - Primary: run_record.json (stage ordering, participation, arbiter verdict)
  - Secondary: logs/runs/{run_id}.jsonl (analyst stances, override details)

No pipeline changes. No new persistence. Read-only projection.

Spec: docs/PR_OPS_4_SPEC_FINAL.md §6
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ai_analyst.api.models.ops import DepartmentKey
from ai_analyst.api.models.ops_trace import (
    AgentTraceResponse,
    ArbiterTraceSummary,
    ArtifactRef,
    ParticipantContribution,
    TraceSummary,
    TraceEdge,
    TraceParticipant,
    TraceStage,
)
from ai_analyst.api.services.ops_roster import get_entity_lookup, persona_to_roster_id

logger = logging.getLogger(__name__)

_CONTRACT_VERSION = "2026.03"

# ── Bounded payload limits (§6.11) ──────────────────────────────────────────

_MAX_SUMMARY_LEN = 500
_MAX_OVERRIDE_REASON_LEN = 300
_MAX_DISSENT_SUMMARY_LEN = 500
_MAX_EDGE_SUMMARY_LEN = 300
_MAX_TRACE_EDGES = 50


def _truncate(text: Optional[str], max_len: int) -> str:
    """Truncate text to max_len, appending '…' if truncated."""
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


# ── Stage vocabulary (§6.6b — locked) ──────────────────────────────────────

_STAGE_ORDER = [
    "validate_input",
    "macro_context",
    "chart_setup",
    "analyst_execution",
    "arbiter",
    "logging",
]

# Which roster entities participate in each stage (static mapping)
_STAGE_PARTICIPANTS: dict[str, list[str]] = {
    "validate_input": [],
    "macro_context": ["market_data_officer", "macro_risk_officer"],
    "chart_setup": [],
    "analyst_execution": [],  # dynamic — populated from run_record analysts
    "arbiter": ["arbiter"],
    "logging": [],
}


# ── Audit log reader ────────────────────────────────────────────────────────


def _read_audit_log(run_id: str) -> Optional[dict]:
    """Read the audit log entry for a run. Returns None if unavailable."""
    log_path = Path("ai_analyst/logs/runs") / f"{run_id}.jsonl"
    if not log_path.exists():
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("run_id") == run_id:
                    return entry
        return None
    except Exception as exc:
        logger.warning("Failed to read audit log for %s: %s", run_id, exc)
        return None


# ── Public projection function ──────────────────────────────────────────────


class TraceProjectionError(Exception):
    """Raised when run artifacts exist but cannot be parsed."""

    pass


def project_trace(
    run_id: str,
    run_record_path: Optional[Path] = None,
    audit_log_path: Optional[Path] = None,
) -> AgentTraceResponse:
    """Project an AgentTraceResponse from run artifacts.

    Args:
        run_id: The run identifier.
        run_record_path: Override path to run_record.json (for testing).
        audit_log_path: Override path to audit log (for testing).

    Returns:
        AgentTraceResponse with trace projection.

    Raises:
        FileNotFoundError: If run_record.json does not exist.
        TraceProjectionError: If artifacts exist but cannot be parsed.
    """
    # Resolve run_record path
    if run_record_path is None:
        from ai_analyst.core.run_paths import get_run_dir
        run_record_path = get_run_dir(run_id) / "run_record.json"

    if not run_record_path.exists():
        raise FileNotFoundError(f"No run artifacts for run_id={run_id}")

    try:
        raw = json.loads(run_record_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TraceProjectionError(f"Malformed run_record.json: {exc}")

    # Read audit log (secondary — optional)
    audit_entry: Optional[dict] = None
    if audit_log_path is not None:
        if audit_log_path.exists():
            try:
                with open(audit_log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        if entry.get("run_id") == run_id:
                            audit_entry = entry
                            break
            except Exception as exc:
                logger.warning("Audit log read failed: %s", exc)
    else:
        audit_entry = _read_audit_log(run_id)

    has_audit = audit_entry is not None
    data_state = "live" if has_audit else "stale"

    roster = get_entity_lookup()
    request = raw.get("request", {})

    # ── Determine run_status ────────────────────────────────────────────
    arbiter_block = raw.get("arbiter", {})
    errors = raw.get("errors", [])
    if errors:
        run_status = "failed"
    elif not arbiter_block.get("ran", False):
        run_status = "partial"
    else:
        run_status = "completed"

    # ── Build stages (§6.6) ─────────────────────────────────────────────
    raw_stages = raw.get("stages", [])
    analysts_ran = raw.get("analysts", [])
    analysts_skipped = raw.get("analysts_skipped", [])
    analysts_failed = raw.get("analysts_failed", [])

    # Analyst participant IDs for the analyst_execution stage
    analyst_participant_ids = [
        persona_to_roster_id(a["persona"]) for a in analysts_ran
    ]

    stages: list[TraceStage] = []
    for idx, raw_stage in enumerate(raw_stages):
        stage_key = raw_stage.get("stage", "unknown")
        raw_status = raw_stage.get("status", "ok")

        # Map run_record status to trace status
        if raw_status == "ok":
            stage_status = "completed"
        elif raw_status == "failed":
            stage_status = "failed"
        else:
            stage_status = "skipped"

        # Determine participants for this stage
        if stage_key == "analyst_execution":
            pids = list(analyst_participant_ids)
        elif stage_key in _STAGE_PARTICIPANTS:
            pids = list(_STAGE_PARTICIPANTS[stage_key])
        else:
            pids = []

        stages.append(TraceStage(
            stage_key=stage_key,
            stage_index=idx + 1,
            status=stage_status,
            duration_ms=raw_stage.get("duration_ms"),
            participant_ids=pids,
        ))

    # ── Build participants (§6.7) ───────────────────────────────────────
    # Get analyst outputs from audit log for stance/confidence enrichment
    audit_analyst_outputs = []
    if has_audit:
        audit_analyst_outputs = audit_entry.get("analyst_outputs", [])

    audit_verdict = None
    if has_audit:
        audit_verdict = audit_entry.get("final_verdict", {})

    # Override-assessment evidence class: heuristic when audit log present,
    # default when absent — applies to ALL participants (absence of override
    # is also inferred, not proven).
    contrib_evidence_class = "heuristic" if has_audit else "default"

    participants: list[TraceParticipant] = []

    # Successful analysts
    for i, analyst in enumerate(analysts_ran):
        entity_id = persona_to_roster_id(analyst["persona"])
        agent = roster.get(entity_id)

        # Enrich from audit log if available
        stance = None
        confidence = None
        summary = f"Analyst {analyst['persona']} completed analysis."
        if i < len(audit_analyst_outputs):
            ao = audit_analyst_outputs[i]
            bias = ao.get("htf_bias")
            if bias in ("bullish", "bearish", "neutral"):
                stance = bias
            elif bias == "ranging":
                stance = "neutral"
            confidence = ao.get("confidence")
            notes = ao.get("notes", "")
            summary = _truncate(notes, _MAX_SUMMARY_LEN) if notes else summary

        # Check override status from arbiter
        was_overridden = False
        override_reason = None
        if audit_verdict and audit_verdict.get("risk_override_applied", False):
            # V1 best-effort: if arbiter applied risk override and analyst
            # had a directional bias that doesn't match arbiter's final call,
            # mark as overridden
            arbiter_decision = audit_verdict.get("decision", "")
            if stance in ("bullish", "bearish") and arbiter_decision == "NO_TRADE":
                was_overridden = True
                override_reason = _truncate(
                    "Risk override applied — arbiter suppressed directional action.",
                    _MAX_OVERRIDE_REASON_LEN,
                )

        participants.append(TraceParticipant(
            entity_id=entity_id,
            entity_type=agent.type if agent else "persona",
            display_name=agent.display_name if agent else analyst["persona"].upper(),
            department=agent.department if agent else None,
            participated=True,
            contribution=ParticipantContribution(
                stance=stance,
                confidence=confidence,
                role=agent.type if agent else "analyst",
                summary=summary,
                was_overridden=was_overridden,
                override_reason=override_reason,
                evidence_class=contrib_evidence_class,
            ),
            status="completed",
        ))

    # Skipped analysts
    for analyst in analysts_skipped:
        entity_id = persona_to_roster_id(analyst["persona"])
        agent = roster.get(entity_id)
        reason = analyst.get("reason", "Skipped")
        participants.append(TraceParticipant(
            entity_id=entity_id,
            entity_type=agent.type if agent else "persona",
            display_name=agent.display_name if agent else analyst["persona"].upper(),
            department=agent.department if agent else None,
            participated=False,
            contribution=ParticipantContribution(
                role=agent.type if agent else "analyst",
                summary=_truncate(reason, _MAX_SUMMARY_LEN),
                was_overridden=False,
                evidence_class=contrib_evidence_class,
            ),
            status="skipped",
        ))

    # Failed analysts
    for analyst in analysts_failed:
        entity_id = persona_to_roster_id(analyst["persona"])
        agent = roster.get(entity_id)
        reason = analyst.get("reason", "Failed")
        participants.append(TraceParticipant(
            entity_id=entity_id,
            entity_type=agent.type if agent else "persona",
            display_name=agent.display_name if agent else analyst["persona"].upper(),
            department=agent.department if agent else None,
            participated=False,
            contribution=ParticipantContribution(
                role=agent.type if agent else "analyst",
                summary=_truncate(reason, _MAX_SUMMARY_LEN),
                was_overridden=False,
                evidence_class=contrib_evidence_class,
            ),
            status="failed",
        ))

    # Arbiter as participant (if ran)
    if arbiter_block.get("ran", False):
        arbiter_agent = roster.get("arbiter")
        arbiter_bias = None
        arbiter_conf = arbiter_block.get("confidence")
        arbiter_summary_text = f"Verdict: {arbiter_block.get('verdict', 'unknown')}"
        if audit_verdict:
            fb = audit_verdict.get("final_bias")
            if fb in ("bullish", "bearish", "neutral"):
                arbiter_bias = fb
            notes = audit_verdict.get("arbiter_notes", "")
            if notes:
                arbiter_summary_text = _truncate(notes, _MAX_SUMMARY_LEN)

        participants.append(TraceParticipant(
            entity_id="arbiter",
            entity_type="arbiter",
            display_name=arbiter_agent.display_name if arbiter_agent else "ARBITER",
            department=arbiter_agent.department if arbiter_agent else None,
            participated=True,
            contribution=ParticipantContribution(
                stance=arbiter_bias,
                confidence=arbiter_conf,
                role="arbiter",
                summary=arbiter_summary_text,
                was_overridden=False,
                evidence_class=contrib_evidence_class,
            ),
            status="completed",
        ))

    # ── Build trace edges (§6.8) ────────────────────────────────────────
    edges: list[TraceEdge] = []

    # Ran analysts → arbiter: considered_by_arbiter
    if arbiter_block.get("ran", False):
        for analyst in analysts_ran:
            entity_id = persona_to_roster_id(analyst["persona"])
            edges.append(TraceEdge(
                from_=entity_id,
                to="arbiter",
                type="considered_by_arbiter",
            ))

    # Skipped analysts: skipped_before_arbiter
    for analyst in analysts_skipped:
        entity_id = persona_to_roster_id(analyst["persona"])
        edges.append(TraceEdge(
            from_=entity_id,
            to="arbiter",
            type="skipped_before_arbiter",
            summary=_truncate(analyst.get("reason"), _MAX_EDGE_SUMMARY_LEN),
        ))

    # Failed analysts: failed_before_arbiter
    for analyst in analysts_failed:
        entity_id = persona_to_roster_id(analyst["persona"])
        edges.append(TraceEdge(
            from_=entity_id,
            to="arbiter",
            type="failed_before_arbiter",
            summary=_truncate(analyst.get("reason"), _MAX_EDGE_SUMMARY_LEN),
        ))

    # Override edges
    overridden_ids: list[str] = []
    for p in participants:
        if p.contribution.was_overridden:
            overridden_ids.append(p.entity_id)
            edges.append(TraceEdge(
                from_="arbiter",
                to=p.entity_id,
                type="override",
                summary=_truncate(
                    p.contribution.override_reason,
                    _MAX_EDGE_SUMMARY_LEN,
                ),
            ))

    # Enforce edge limit (§6.11)
    edges = edges[:_MAX_TRACE_EDGES]

    # ── Build arbiter summary (§6.9) ────────────────────────────────────
    arbiter_trace_summary: Optional[ArbiterTraceSummary] = None
    if arbiter_block.get("ran", False):
        override_applied = False
        override_type = None
        override_count = 0
        synthesis_approach = None
        dissent_summary = None
        arb_summary_text = f"Verdict: {arbiter_block.get('verdict', 'unknown')}"

        if audit_verdict:
            override_applied = audit_verdict.get("risk_override_applied", False)
            if override_applied:
                override_type = "risk_override"
            override_count = len(overridden_ids)
            notes = audit_verdict.get("arbiter_notes", "")
            if notes:
                arb_summary_text = _truncate(notes, _MAX_SUMMARY_LEN)

            # Build dissent summary from overridden participants
            if overridden_ids:
                dissent_parts = []
                for oid in overridden_ids:
                    for p in participants:
                        if p.entity_id == oid and p.contribution.stance:
                            dissent_parts.append(
                                f"{p.display_name} ({p.contribution.stance})"
                            )
                if dissent_parts:
                    dissent_summary = _truncate(
                        f"Overridden: {', '.join(dissent_parts)}",
                        _MAX_DISSENT_SUMMARY_LEN,
                    )

        arbiter_trace_summary = ArbiterTraceSummary(
            entity_id="arbiter",
            override_applied=override_applied,
            override_type=override_type,
            override_count=override_count,
            overridden_entity_ids=list(overridden_ids),
            synthesis_approach=synthesis_approach,
            final_bias=arbiter_bias if arbiter_block.get("ran") else None,
            confidence=arbiter_block.get("confidence"),
            dissent_summary=dissent_summary,
            summary=arb_summary_text,
        )

    # ── Build summary (§6.5) ────────────────────────────────────────────
    active_participants = [p for p in participants if p.participated]
    final_bias = None
    final_decision = None
    arbiter_override = False
    if audit_verdict:
        fb = audit_verdict.get("final_bias")
        if fb in ("bullish", "bearish", "neutral"):
            final_bias = fb
        final_decision = audit_verdict.get("decision")
        arbiter_override = audit_verdict.get("risk_override_applied", False)
    elif arbiter_block.get("ran"):
        final_decision = arbiter_block.get("verdict")
        arbiter_override = bool(overridden_ids)

    trace_summary = TraceSummary(
        entity_count=len(active_participants),
        stage_count=len(stages),
        arbiter_override=arbiter_override,
        final_bias=final_bias,
        final_decision=final_decision,
    )

    # ── Build artifact refs (§6.10) ─────────────────────────────────────
    artifact_refs = [
        ArtifactRef(artifact_type="run_record", artifact_key="run_record.json"),
    ]
    artifacts = raw.get("artifacts", {})
    if "usage_jsonl" in artifacts:
        artifact_refs.append(
            ArtifactRef(artifact_type="usage_log", artifact_key="usage.jsonl")
        )

    # Compute finished_at from started_at + duration_ms
    started_at = raw.get("timestamp")
    finished_at = None
    duration_ms = raw.get("duration_ms")
    if started_at and duration_ms is not None:
        try:
            from datetime import timedelta
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(milliseconds=duration_ms)
            finished_at = end_dt.isoformat().replace("+00:00", "Z")
        except (ValueError, TypeError):
            pass

    # Compute projection quality and missing fields
    # "full" is reserved for future pipeline work — not reachable in v1
    if not has_audit:
        projection_quality = "partial"
        missing_fields: list[str] = [
            "analyst_stances",
            "confidence_scores",
            "override_attribution",
        ]
    else:
        projection_quality = "heuristic"
        missing_fields = ["explicit_override_metadata"]

    return AgentTraceResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state=data_state,
        source_of_truth="run_artifacts",
        run_id=run_id,
        run_status=run_status,
        instrument=request.get("instrument"),
        session=request.get("session"),
        started_at=started_at,
        finished_at=finished_at,
        summary=trace_summary,
        stages=stages,
        participants=participants,
        trace_edges=edges,
        arbiter_summary=arbiter_trace_summary,
        artifact_refs=artifact_refs,
        projection_quality=projection_quality,
        missing_fields=missing_fields,
    )
