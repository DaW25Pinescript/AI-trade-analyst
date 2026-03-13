"""Agent Operations — Roster projection service.

Derives the static agent roster from durable structural truth:
- analyst/personas.py persona definitions
- analyst/arbiter.py arbiter role
- ai_analyst/models/persona.py PersonaType enum (analyst_roster config)
- market_data_officer/ and macro_risk_officer/ officer directories
- config/llm_routing.example.yaml analyst_roster section

The roster is config-derived, not runtime-derived (§4.2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ai_analyst.api.models.ops import (
    AgentRosterResponse,
    AgentSummary,
    DepartmentKey,
    EntityRelationship,
)

# ── Contract version ─────────────────────────────────────────────────────────

_CONTRACT_VERSION = "2026.03"

# ── Static entity definitions ────────────────────────────────────────────────
# Derived from:
#   - analyst/personas.py: PERSONA_TECHNICAL_STRUCTURE, PERSONA_EXECUTION_TIMING
#   - analyst/arbiter.py: Arbiter deterministic consensus + LLM synthesis
#   - ai_analyst/models/persona.py: PersonaType enum (default_analyst,
#     risk_officer, prosecutor, ict_purist, skeptical_quant)
#   - config/llm_routing.example.yaml: analyst_roster section
#   - market_data_officer/ directory: Market Data Officer subsystem
#   - macro_risk_officer/ directory: Macro Risk Officer subsystem

# -- Governance layer (§4.7: 2 governance-layer entities) ---------------------

_ARBITER = AgentSummary(
    id="arbiter",
    display_name="ARBITER",
    type="arbiter",
    role="Final Verdict Arbiter",
    capabilities=["CONSENSUS", "SYNTHESIS", "OVERRIDE"],
    supports_verdict=True,
    initials="AB",
    visual_family="governance",
    orb_color="teal",
)

_GOVERNANCE_SYNTHESIS = AgentSummary(
    id="governance_synthesis",
    display_name="GOVERNANCE SYNTHESIS",
    type="subsystem",
    role="Governance-Level Synthesis Pipeline",
    capabilities=["DELIBERATION", "ESCALATION"],
    supports_verdict=False,
    initials="GS",
    visual_family="governance",
    orb_color="teal",
)

# -- Officer layer (§4.7: 2 officer-layer entities) ---------------------------

_MARKET_DATA_OFFICER = AgentSummary(
    id="market_data_officer",
    display_name="MARKET DATA OFFICER",
    type="officer",
    role="Market Data Ingestion & Freshness",
    capabilities=["SCHEDULING", "FRESHNESS", "MARKET_STATE"],
    supports_verdict=False,
    initials="MDO",
    visual_family="officer",
    orb_color="amber",
)

_MACRO_RISK_OFFICER = AgentSummary(
    id="macro_risk_officer",
    display_name="MACRO RISK OFFICER",
    type="officer",
    role="Macro Event Ingestion & Risk Assessment",
    capabilities=["FEEDER_INGEST", "REGIME", "VOL_BIAS"],
    supports_verdict=False,
    initials="MRO",
    visual_family="officer",
    orb_color="amber",
)

# -- Department: TECHNICAL_ANALYSIS -------------------------------------------
# Personas from analyst/personas.py and ai_analyst/models/persona.py

_DEFAULT_ANALYST = AgentSummary(
    id="persona_default_analyst",
    display_name="DEFAULT ANALYST",
    type="persona",
    department=DepartmentKey.TECHNICAL_ANALYSIS,
    role="Senior Analyst",
    capabilities=["DIRECTIONAL", "BIAS", "STRUCTURE"],
    supports_verdict=True,
    initials="DA",
    visual_family="technical",
    orb_color="teal",
)

_ICT_PURIST = AgentSummary(
    id="persona_ict_purist",
    display_name="ICT PURIST",
    type="persona",
    department=DepartmentKey.TECHNICAL_ANALYSIS,
    role="ICT Structure Specialist",
    capabilities=["ICT", "STRUCTURE", "LIQUIDITY"],
    supports_verdict=True,
    initials="IP",
    visual_family="technical",
    orb_color="teal",
)

_TECHNICAL_STRUCTURE = AgentSummary(
    id="persona_technical_structure",
    display_name="TECHNICAL STRUCTURE",
    type="persona",
    department=DepartmentKey.TECHNICAL_ANALYSIS,
    role="Technical Structure Analyst",
    capabilities=["HTF_REGIME", "BOS_MSS", "FVG"],
    supports_verdict=True,
    initials="TS",
    visual_family="technical",
    orb_color="teal",
)

# -- Department: RISK_CHALLENGE -----------------------------------------------

_RISK_OFFICER = AgentSummary(
    id="persona_risk_officer",
    display_name="RISK OFFICER",
    type="persona",
    department=DepartmentKey.RISK_CHALLENGE,
    role="Risk Challenge Analyst",
    capabilities=["RISK", "CHALLENGE", "GATE"],
    supports_verdict=True,
    initials="RO",
    visual_family="risk",
    orb_color="red",
)

_PROSECUTOR = AgentSummary(
    id="persona_prosecutor",
    display_name="PROSECUTOR",
    type="persona",
    department=DepartmentKey.RISK_CHALLENGE,
    role="Devil's Advocate Analyst",
    capabilities=["CHALLENGE", "COUNTER_ARGUMENT"],
    supports_verdict=True,
    initials="PR",
    visual_family="risk",
    orb_color="red",
)

_SKEPTICAL_QUANT = AgentSummary(
    id="persona_skeptical_quant",
    display_name="SKEPTICAL QUANT",
    type="persona",
    department=DepartmentKey.RISK_CHALLENGE,
    role="Quantitative Skeptic",
    capabilities=["QUANTITATIVE", "SKEPTICISM"],
    supports_verdict=True,
    initials="SQ",
    visual_family="risk",
    orb_color="red",
)

# -- Department: REVIEW_GOVERNANCE --------------------------------------------

_EXECUTION_TIMING = AgentSummary(
    id="persona_execution_timing",
    display_name="EXECUTION TIMING",
    type="persona",
    department=DepartmentKey.REVIEW_GOVERNANCE,
    role="Execution & Timing Analyst",
    capabilities=["TIMING", "EXECUTION", "ENTRY_QUALITY"],
    supports_verdict=True,
    initials="ET",
    visual_family="review",
    orb_color="amber",
)

# -- Department: INFRA_HEALTH -------------------------------------------------

_MDO_SCHEDULER = AgentSummary(
    id="mdo_scheduler",
    display_name="MDO SCHEDULER",
    type="subsystem",
    department=DepartmentKey.INFRA_HEALTH,
    role="Market Data Scheduling Subsystem",
    capabilities=["CRON", "REFRESH", "STALENESS"],
    supports_verdict=False,
    initials="MS",
    visual_family="infra",
    orb_color="amber",
)

_FEEDER_INGEST = AgentSummary(
    id="feeder_ingest",
    display_name="FEEDER INGEST",
    type="subsystem",
    department=DepartmentKey.INFRA_HEALTH,
    role="Macro Feeder Ingestion Subsystem",
    capabilities=["INGEST", "MAPPING", "VALIDATION"],
    supports_verdict=False,
    initials="FI",
    visual_family="infra",
    orb_color="amber",
)

# ── Aggregate collections ────────────────────────────────────────────────────

_GOVERNANCE_LAYER: list[AgentSummary] = [_ARBITER, _GOVERNANCE_SYNTHESIS]
_OFFICER_LAYER: list[AgentSummary] = [_MARKET_DATA_OFFICER, _MACRO_RISK_OFFICER]
_DEPARTMENTS: dict[DepartmentKey, list[AgentSummary]] = {
    DepartmentKey.TECHNICAL_ANALYSIS: [
        _DEFAULT_ANALYST,
        _ICT_PURIST,
        _TECHNICAL_STRUCTURE,
    ],
    DepartmentKey.RISK_CHALLENGE: [
        _RISK_OFFICER,
        _PROSECUTOR,
        _SKEPTICAL_QUANT,
    ],
    DepartmentKey.REVIEW_GOVERNANCE: [
        _EXECUTION_TIMING,
    ],
    DepartmentKey.INFRA_HEALTH: [
        _MDO_SCHEDULER,
        _FEEDER_INGEST,
    ],
}

# ── Relationships (§4.5) ─────────────────────────────────────────────────────
# Explicit edges between entities — drives frontend hierarchy arrows.

_RELATIONSHIPS: list[EntityRelationship] = [
    # Governance synthesizes from officer outputs
    EntityRelationship(from_="arbiter", to="governance_synthesis", type="synthesizes"),
    # Officers feed into governance
    EntityRelationship(from_="market_data_officer", to="arbiter", type="feeds"),
    EntityRelationship(from_="macro_risk_officer", to="arbiter", type="feeds"),
    # Technical analysis personas support arbiter
    EntityRelationship(from_="persona_default_analyst", to="arbiter", type="supports"),
    EntityRelationship(from_="persona_ict_purist", to="arbiter", type="supports"),
    EntityRelationship(from_="persona_technical_structure", to="arbiter", type="supports"),
    # Risk challenge personas challenge arbiter
    EntityRelationship(from_="persona_risk_officer", to="arbiter", type="challenges"),
    EntityRelationship(from_="persona_prosecutor", to="arbiter", type="challenges"),
    EntityRelationship(from_="persona_skeptical_quant", to="arbiter", type="challenges"),
    # Review governance persona supports governance synthesis
    EntityRelationship(from_="persona_execution_timing", to="governance_synthesis", type="supports"),
    # Infra subsystems feed officers
    EntityRelationship(from_="mdo_scheduler", to="market_data_officer", type="feeds"),
    EntityRelationship(from_="feeder_ingest", to="macro_risk_officer", type="feeds"),
]


def get_all_roster_ids() -> set[str]:
    """Return the set of all entity IDs in the roster."""
    ids: set[str] = set()
    for agent in _GOVERNANCE_LAYER:
        ids.add(agent.id)
    for agent in _OFFICER_LAYER:
        ids.add(agent.id)
    for agents in _DEPARTMENTS.values():
        for agent in agents:
            ids.add(agent.id)
    return ids


# ── Public projection function ───────────────────────────────────────────────


def project_roster() -> AgentRosterResponse:
    """Build the complete agent roster response.

    Returns the static roster derived from config/code structural truth.
    Raises RuntimeError if the roster is unexpectedly empty (should never
    happen with the static definitions above, but satisfies §4.8).
    """
    all_entities = (
        list(_GOVERNANCE_LAYER)
        + list(_OFFICER_LAYER)
        + [a for dept in _DEPARTMENTS.values() for a in dept]
    )
    if not all_entities:
        raise RuntimeError("Roster is empty — cannot serve agent roster")

    # Validate all relationship IDs reference known entities
    roster_ids = get_all_roster_ids()
    for rel in _RELATIONSHIPS:
        if rel.from_ not in roster_ids:
            raise RuntimeError(
                f"Relationship from={rel.from_!r} not in roster"
            )
        if rel.to not in roster_ids:
            raise RuntimeError(
                f"Relationship to={rel.to!r} not in roster"
            )

    return AgentRosterResponse(
        version=_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_state="live",
        source_of_truth="roster_config",
        governance_layer=list(_GOVERNANCE_LAYER),
        officer_layer=list(_OFFICER_LAYER),
        departments=dict(_DEPARTMENTS),
        relationships=list(_RELATIONSHIPS),
    )
