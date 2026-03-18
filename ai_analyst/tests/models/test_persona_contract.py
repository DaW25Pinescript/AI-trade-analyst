"""Tests for PersonaContract schema and v1 contract instances.

Covers: AC-16 (JSON round-trip), contract shape, constraint validation.
"""

import pytest

from ai_analyst.models.persona import PersonaType
from ai_analyst.models.persona_contract import (
    ConstraintRule,
    PersonaContract,
    DEFAULT_ANALYST_CONTRACT,
    RISK_OFFICER_CONTRACT,
)


class TestDefaultAnalystContract:
    def test_instantiates_with_all_fields(self):
        c = DEFAULT_ANALYST_CONTRACT
        assert c.persona_id == PersonaType.DEFAULT_ANALYST
        assert c.version == "v1.0"
        assert c.display_name == "Default Analyst"
        assert c.primary_stance == "balanced"
        assert c.temperature_override is None
        assert c.model_profile_override is None
        assert isinstance(c.must_enforce, list)
        assert isinstance(c.soft_constraints, list)
        assert isinstance(c.constraints, list)
        assert isinstance(c.validator_rules, list)
        assert len(c.constraints) == 3
        assert len(c.validator_rules) == 5


class TestRiskOfficerContract:
    def test_instantiates_with_all_fields(self):
        c = RISK_OFFICER_CONTRACT
        assert c.persona_id == PersonaType.RISK_OFFICER
        assert c.version == "v1.0"
        assert c.display_name == "Risk Officer"
        assert c.primary_stance == "risk_averse"
        assert c.temperature_override is None
        assert c.model_profile_override is None
        assert isinstance(c.must_enforce, list)
        assert isinstance(c.soft_constraints, list)
        assert isinstance(c.constraints, list)
        assert isinstance(c.validator_rules, list)
        assert len(c.constraints) == 3
        assert len(c.validator_rules) == 6


class TestContractJsonRoundTrip:
    """AC-16: PersonaContract round-trips through JSON without data loss."""

    def test_default_analyst_roundtrip(self):
        original = DEFAULT_ANALYST_CONTRACT
        json_str = original.model_dump_json()
        restored = PersonaContract.model_validate_json(json_str)
        assert restored == original

    def test_risk_officer_roundtrip(self):
        original = RISK_OFFICER_CONTRACT
        json_str = original.model_dump_json()
        restored = PersonaContract.model_validate_json(json_str)
        assert restored == original

    def test_roundtrip_preserves_all_fields(self):
        """Verify every field survives the round-trip by checking dict equality."""
        for contract in [DEFAULT_ANALYST_CONTRACT, RISK_OFFICER_CONTRACT]:
            original_dict = contract.model_dump()
            json_str = contract.model_dump_json()
            restored_dict = PersonaContract.model_validate_json(json_str).model_dump()
            assert original_dict == restored_dict


class TestValidatorRulesAreStrings:
    def test_default_analyst_rules_are_strings(self):
        for rule in DEFAULT_ANALYST_CONTRACT.validator_rules:
            assert isinstance(rule, str)
            assert not callable(rule)

    def test_risk_officer_rules_are_strings(self):
        for rule in RISK_OFFICER_CONTRACT.validator_rules:
            assert isinstance(rule, str)
            assert not callable(rule)


class TestAllV1ConstraintsSoftLevel:
    def test_default_analyst_all_soft(self):
        for constraint in DEFAULT_ANALYST_CONTRACT.constraints:
            assert constraint.level == "soft"

    def test_risk_officer_all_soft(self):
        for constraint in RISK_OFFICER_CONTRACT.constraints:
            assert constraint.level == "soft"


class TestPersonaIdUsesEnum:
    def test_default_analyst_uses_persona_type(self):
        assert DEFAULT_ANALYST_CONTRACT.persona_id is PersonaType.DEFAULT_ANALYST

    def test_risk_officer_uses_persona_type(self):
        assert RISK_OFFICER_CONTRACT.persona_id is PersonaType.RISK_OFFICER


class TestConstraintRuleValidation:
    def test_valid_soft_constraint(self):
        c = ConstraintRule(rule="test rule", level="soft")
        assert c.level == "soft"

    def test_valid_moderate_constraint(self):
        c = ConstraintRule(rule="test rule", level="moderate")
        assert c.level == "moderate"

    def test_valid_hard_constraint(self):
        c = ConstraintRule(rule="test rule", level="hard")
        assert c.level == "hard"

    def test_invalid_constraint_level_rejected(self):
        with pytest.raises(Exception):
            ConstraintRule(rule="test rule", level="critical")
