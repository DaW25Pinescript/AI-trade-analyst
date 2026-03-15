"""Agent Operations — Static profile registry (PR-OPS-4b).

Provides extended entity metadata not present in the roster:
purpose, responsibilities, and type-specific detail fields.

Config-derived, parallel to ops_roster.py. Source: hardcoded per entity.
"""

from __future__ import annotations

from ai_analyst.api.models.ops_detail import (
    ArbiterDetail,
    OfficerDetail,
    PersonaDetail,
    SubsystemDetail,
    TypeSpecific,
)


class EntityProfile:
    """Extended profile metadata for a single entity."""

    __slots__ = ("purpose", "responsibilities", "type_specific")

    def __init__(
        self,
        purpose: str,
        responsibilities: list[str],
        type_specific: TypeSpecific,
    ):
        self.purpose = purpose
        self.responsibilities = responsibilities
        self.type_specific = type_specific


# ── Profile definitions ─────────────────────────────────────────────────────

_PROFILES: dict[str, EntityProfile] = {
    # -- Governance layer --
    "arbiter": EntityProfile(
        purpose="Synthesizes analyst outputs into a final governed verdict.",
        responsibilities=[
            "final verdict generation",
            "confidence normalization",
            "policy override enforcement",
        ],
        type_specific=ArbiterDetail(
            synthesis_method="weighted_consensus",
            veto_gates=["quorum_not_met", "confidence_below_threshold"],
            quorum_rule="minimum 2 of 3 analysts must contribute",
            override_capable=True,
            policy_summary=(
                "May suppress directional action when consensus or "
                "setup quality is insufficient."
            ),
        ),
    ),
    "governance_synthesis": EntityProfile(
        purpose="Governance-level synthesis pipeline for deliberation and escalation.",
        responsibilities=[
            "deliberation round orchestration",
            "escalation decision",
        ],
        type_specific=SubsystemDetail(
            subsystem_type="governance_pipeline",
            monitored_resources=["deliberation_round", "escalation_state"],
            health_check_method="pipeline_status",
            runtime_role="Deliberation and escalation orchestration",
        ),
    ),
    # -- Officer layer --
    "market_data_officer": EntityProfile(
        purpose="Manages market data ingestion, scheduling, and freshness monitoring.",
        responsibilities=[
            "market data feed scheduling",
            "data freshness monitoring",
            "market state classification",
        ],
        type_specific=OfficerDetail(
            officer_domain="market_data",
            data_sources=["yfinance", "tradingview"],
            monitored_surfaces=["feed_freshness", "market_hours", "staleness_threshold"],
            update_cadence="15m",
        ),
    ),
    "macro_risk_officer": EntityProfile(
        purpose="Ingests macro event data and provides risk assessment context.",
        responsibilities=[
            "macro event ingestion",
            "regime classification",
            "volatility bias assessment",
        ],
        type_specific=OfficerDetail(
            officer_domain="macro_risk",
            data_sources=["feeder_ingest", "macro_event_feeds"],
            monitored_surfaces=["regime_state", "vol_bias", "event_risk"],
            update_cadence="on_demand",
        ),
    ),
    # -- TECHNICAL_ANALYSIS personas --
    "persona_default_analyst": EntityProfile(
        purpose="Senior analyst providing directional bias and structure assessment.",
        responsibilities=[
            "HTF bias determination",
            "structure state classification",
            "setup validation",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["DIRECTIONAL", "BIAS", "STRUCTURE"],
            verdict_style="Balanced directional assessment with structure confirmation",
            department_role="Senior Analyst — primary directional view",
            typical_outputs=["htf_bias", "structure_state", "setup_valid", "confidence"],
        ),
    ),
    "persona_ict_purist": EntityProfile(
        purpose="ICT structure specialist focusing on liquidity and displacement.",
        responsibilities=[
            "ICT structure analysis",
            "liquidity sweep detection",
            "FVG zone identification",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["ICT", "STRUCTURE", "LIQUIDITY"],
            verdict_style="ICT-strict structure validation with displacement quality",
            department_role="ICT Structure Specialist",
            typical_outputs=["sweep_status", "fvg_zones", "displacement_quality", "confidence"],
        ),
    ),
    "persona_technical_structure": EntityProfile(
        purpose="Technical structure analyst focusing on HTF regime and BOS/MSS patterns.",
        responsibilities=[
            "HTF regime analysis",
            "BOS/MSS pattern detection",
            "FVG context analysis",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["HTF_REGIME", "BOS_MSS", "FVG"],
            verdict_style="Structure-first regime analysis with pattern confirmation",
            department_role="Technical Structure Analyst",
            typical_outputs=["structure_state", "key_levels", "setup_type", "confidence"],
        ),
    ),
    # -- RISK_CHALLENGE personas --
    "persona_risk_officer": EntityProfile(
        purpose="Risk challenge analyst providing risk-gated validation of setups.",
        responsibilities=[
            "risk gate enforcement",
            "disqualifier identification",
            "risk/reward validation",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["RISK", "CHALLENGE", "GATE"],
            verdict_style="Risk-first challenge with disqualifier enforcement",
            department_role="Risk Challenge Analyst",
            typical_outputs=["disqualifiers", "rr_estimate", "setup_valid", "confidence"],
        ),
    ),
    "persona_prosecutor": EntityProfile(
        purpose="Devil's advocate analyst challenging consensus positions.",
        responsibilities=[
            "counter-argument generation",
            "consensus challenge",
            "bias detection",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["CHALLENGE", "COUNTER_ARGUMENT"],
            verdict_style="Adversarial challenge to dominant thesis",
            department_role="Devil's Advocate Analyst",
            typical_outputs=["disqualifiers", "notes", "recommended_action", "confidence"],
        ),
    ),
    "persona_skeptical_quant": EntityProfile(
        purpose="Quantitative skeptic applying statistical rigor to setup claims.",
        responsibilities=[
            "quantitative validation",
            "statistical skepticism",
            "confidence calibration",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["QUANTITATIVE", "SKEPTICISM"],
            verdict_style="Quantitative skepticism with evidence-based confidence",
            department_role="Quantitative Skeptic",
            typical_outputs=["confidence", "rr_estimate", "disqualifiers", "notes"],
        ),
    ),
    # -- REVIEW_GOVERNANCE personas --
    "persona_execution_timing": EntityProfile(
        purpose="Execution and timing analyst assessing entry quality and timing windows.",
        responsibilities=[
            "entry timing assessment",
            "execution quality evaluation",
            "timing window identification",
        ],
        type_specific=PersonaDetail(
            analysis_focus=["TIMING", "EXECUTION", "ENTRY_QUALITY"],
            verdict_style="Timing-focused execution readiness assessment",
            department_role="Execution & Timing Analyst",
            typical_outputs=["entry_model", "setup_type", "confidence", "notes"],
        ),
    ),
    # -- INFRA_HEALTH subsystems --
    "mdo_scheduler": EntityProfile(
        purpose="Market data scheduling subsystem managing feed refresh cycles.",
        responsibilities=[
            "cron-based feed scheduling",
            "refresh cycle management",
            "staleness detection",
        ],
        type_specific=SubsystemDetail(
            subsystem_type="scheduler",
            monitored_resources=["apscheduler_jobs", "feed_refresh_cycles"],
            health_check_method="scheduler_heartbeat",
            runtime_role="Market data feed scheduling and refresh",
        ),
    ),
    "feeder_ingest": EntityProfile(
        purpose="Macro feeder ingestion subsystem managing event data pipeline.",
        responsibilities=[
            "event data ingestion",
            "field mapping and validation",
            "staleness recovery detection",
        ],
        type_specific=SubsystemDetail(
            subsystem_type="data_pipeline",
            monitored_resources=["feeder_events", "mapping_tables", "ingest_queue"],
            health_check_method="last_ingest_timestamp",
            runtime_role="Macro event data ingestion and normalization",
        ),
    ),
}


def get_entity_profile(entity_id: str) -> EntityProfile | None:
    """Return the extended profile for an entity, or None if not registered."""
    return _PROFILES.get(entity_id)


def get_all_profile_ids() -> set[str]:
    """Return the set of all entity IDs in the profile registry."""
    return set(_PROFILES.keys())
