"""PersonaContract schema and v1 contract instances.

Spec reference: Section 6.4
"""

from pydantic import BaseModel
from typing import Literal

from ai_analyst.models.persona import PersonaType


class ConstraintRule(BaseModel):
    rule: str
    level: Literal["soft", "moderate", "hard"]


class PersonaContract(BaseModel):
    persona_id: PersonaType
    version: str
    display_name: str
    primary_stance: Literal[
        "balanced", "risk_averse", "adversarial",
        "method_pure", "skeptical_prob"
    ]
    temperature_override: float | None = None
    model_profile_override: str | None = None
    must_enforce: list[str]
    soft_constraints: list[str]
    constraints: list[ConstraintRule]
    validator_rules: list[str]  # named references into VALIDATOR_REGISTRY


DEFAULT_ANALYST_CONTRACT = PersonaContract(
    persona_id=PersonaType.DEFAULT_ANALYST,
    version="v1.0",
    display_name="Default Analyst",
    primary_stance="balanced",
    temperature_override=None,
    model_profile_override=None,
    must_enforce=[],
    soft_constraints=[],
    constraints=[
        ConstraintRule(rule="minimum 2 evidence fields", level="soft"),
        ConstraintRule(rule="minimum 1 counterpoint", level="soft"),
        ConstraintRule(rule="minimum 1 what_would_change_my_mind", level="soft"),
    ],
    validator_rules=[
        "default_analyst.requires_two_evidence_fields",
        "all_personas.no_evidence_contradiction",
        "all_personas.evidence_paths_exist",
        "all_personas.counterpoint_required",
        "all_personas.falsifiable_required",
    ],
)

RISK_OFFICER_CONTRACT = PersonaContract(
    persona_id=PersonaType.RISK_OFFICER,
    version="v1.0",
    display_name="Risk Officer",
    primary_stance="risk_averse",
    temperature_override=None,
    model_profile_override=None,
    must_enforce=[],
    soft_constraints=[],
    constraints=[
        ConstraintRule(rule="minimum 2 evidence fields", level="soft"),
        ConstraintRule(rule="no aggressive buy without high confidence", level="soft"),
        ConstraintRule(rule="minimum 1 counterpoint", level="soft"),
    ],
    validator_rules=[
        "default_analyst.requires_two_evidence_fields",
        "risk_officer.no_aggressive_buy_without_confidence",
        "all_personas.no_evidence_contradiction",
        "all_personas.evidence_paths_exist",
        "all_personas.counterpoint_required",
        "all_personas.falsifiable_required",
    ],
)
