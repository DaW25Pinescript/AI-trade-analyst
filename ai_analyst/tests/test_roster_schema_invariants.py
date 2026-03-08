from ai_analyst.graph.analyst_nodes import ANALYST_CONFIGS
from ai_analyst.graph import arbiter_node
from ai_analyst.llm_router.model_profiles import MODEL_PROFILES, resolve_profile
from ai_analyst.models.persona import PersonaType


def test_roster_schema_invariants():
    """Consolidated roster schema invariants for persona/profile architecture."""
    assert ANALYST_CONFIGS, "ANALYST_CONFIGS must not be empty"

    personas = set()
    for cfg in ANALYST_CONFIGS:
        assert "persona" in cfg
        assert "profile" in cfg
        assert "model" not in cfg
        assert isinstance(cfg["persona"], PersonaType)
        profile = resolve_profile(cfg["profile"])
        assert profile.name == cfg["profile"]
        personas.add(cfg["persona"])

    expected_personas = {
        PersonaType.DEFAULT_ANALYST,
        PersonaType.RISK_OFFICER,
        PersonaType.PROSECUTOR,
        PersonaType.ICT_PURIST,
    }
    assert expected_personas.issubset(personas)

    # Standard analysts use Sonnet profile by contract.
    assert {cfg["profile"] for cfg in ANALYST_CONFIGS} == {"claude_sonnet"}

    # Arbiter resolves to Opus profile by contract.
    route = arbiter_node.router.resolve(arbiter_node.ARBITER_DECISION)
    assert route["model"] == MODEL_PROFILES["claude_opus"].model
