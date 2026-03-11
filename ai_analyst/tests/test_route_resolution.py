"""Deterministic tests for LLM route resolution and ResolvedRoute contract.

These tests verify:
- ResolvedRoute shape and immutability
- resolve_task_route() returns correct provider/model for all task types
- resolve_profile_route() returns correct provider/model for all profiles
- to_call_kwargs() produces the expected keyword arguments
- Provider flows through the resolved contract, not from hardcoding

No live LLM provider dependency — all tests use the config loader's
fallback to llm_routing.example.yaml.
"""
import pytest

from ai_analyst.llm_router.router import (
    ResolvedRoute,
    resolve_task_route,
    resolve_profile_route,
)
from ai_analyst.llm_router.model_profiles import MODEL_PROFILES, resolve_profile
from ai_analyst.llm_router.task_types import (
    ALL_TASK_TYPES,
    ANALYST_REASONING,
    ARBITER_DECISION,
    CHART_EXTRACT,
    CHART_INTERPRET,
    JSON_REPAIR,
)


class TestResolvedRouteContract:
    """Verify the ResolvedRoute dataclass shape and behavior."""

    def test_resolved_route_has_required_fields(self):
        route = ResolvedRoute(
            provider="openai",
            model="claude-sonnet-4-6",
            api_base="http://127.0.0.1:8317/v1",
            api_key="test-key",
            retries=1,
        )
        assert route.provider == "openai"
        assert route.model == "claude-sonnet-4-6"
        assert route.api_base == "http://127.0.0.1:8317/v1"
        assert route.api_key == "test-key"
        assert route.retries == 1
        assert route.fallback_provider is None
        assert route.fallback_model is None

    def test_resolved_route_is_frozen(self):
        route = ResolvedRoute(
            provider="openai",
            model="claude-sonnet-4-6",
            api_base=None,
            api_key=None,
            retries=1,
        )
        with pytest.raises(AttributeError):
            route.provider = "anthropic"  # type: ignore[misc]

    def test_to_call_kwargs_shape(self):
        route = ResolvedRoute(
            provider="openai",
            model="claude-sonnet-4-6",
            api_base="http://127.0.0.1:8317/v1",
            api_key="test-key",
            retries=1,
        )
        kwargs = route.to_call_kwargs()
        assert kwargs == {
            "custom_llm_provider": "openai",
            "api_base": "http://127.0.0.1:8317/v1",
            "api_key": "test-key",
        }

    def test_to_call_kwargs_does_not_include_model(self):
        """model is passed separately to acompletion_metered, not via kwargs."""
        route = ResolvedRoute(
            provider="openai",
            model="claude-sonnet-4-6",
            api_base=None,
            api_key=None,
            retries=1,
        )
        kwargs = route.to_call_kwargs()
        assert "model" not in kwargs


class TestResolveTaskRoute:
    """Verify resolve_task_route returns correct contracts for all task types."""

    def test_analyst_reasoning_uses_sonnet(self):
        route = resolve_task_route(ANALYST_REASONING)
        assert route.model == "claude-sonnet-4-6"
        assert route.provider == "openai"
        assert isinstance(route, ResolvedRoute)

    def test_arbiter_decision_uses_opus(self):
        route = resolve_task_route(ARBITER_DECISION)
        assert route.model == "claude-opus-4-6"
        assert route.provider == "openai"

    def test_chart_extract_resolves(self):
        route = resolve_task_route(CHART_EXTRACT)
        assert route.provider == "openai"
        assert route.model == "claude-sonnet-4-6"

    def test_chart_interpret_resolves(self):
        route = resolve_task_route(CHART_INTERPRET)
        assert route.provider == "openai"
        assert route.model == "claude-sonnet-4-6"

    def test_json_repair_resolves(self):
        route = resolve_task_route(JSON_REPAIR)
        assert route.provider == "openai"
        assert route.model == "claude-sonnet-4-6"

    def test_all_task_types_resolve_without_error(self):
        for task_type in ALL_TASK_TYPES:
            route = resolve_task_route(task_type)
            assert route.provider, f"No provider for task {task_type}"
            assert route.model, f"No model for task {task_type}"
            assert isinstance(route, ResolvedRoute)

    def test_unknown_task_type_raises(self):
        with pytest.raises(ValueError, match="Unknown task type"):
            resolve_task_route("nonexistent_task")

    def test_api_base_is_populated(self):
        route = resolve_task_route(ANALYST_REASONING)
        assert route.api_base is not None
        assert "8317" in route.api_base  # local proxy port

    def test_retries_is_positive(self):
        route = resolve_task_route(ANALYST_REASONING)
        assert route.retries >= 1


class TestResolveProfileRoute:
    """Verify resolve_profile_route returns correct contracts for all profiles."""

    def test_claude_sonnet_profile(self):
        route = resolve_profile_route("claude_sonnet")
        assert route.model == "claude-sonnet-4-6"
        assert route.provider == "openai"
        assert isinstance(route, ResolvedRoute)

    def test_claude_opus_profile(self):
        route = resolve_profile_route("claude_opus")
        assert route.model == "claude-opus-4-6"
        assert route.provider == "openai"

    def test_all_profiles_resolve_without_error(self):
        for profile_name in MODEL_PROFILES:
            route = resolve_profile_route(profile_name)
            assert route.provider, f"No provider for profile {profile_name}"
            assert route.model, f"No model for profile {profile_name}"
            assert isinstance(route, ResolvedRoute)

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError, match="Unknown model profile"):
            resolve_profile_route("nonexistent_profile")

    def test_profile_route_provider_matches_profile(self):
        """Provider on route must match provider on the underlying ModelProfile."""
        for profile_name, profile in MODEL_PROFILES.items():
            route = resolve_profile_route(profile_name)
            assert route.provider == profile.provider
            assert route.model == profile.model


class TestModelProfileProvider:
    """Verify ModelProfile now includes provider."""

    def test_all_profiles_have_provider(self):
        for name, profile in MODEL_PROFILES.items():
            assert hasattr(profile, "provider"), f"Profile {name} missing provider"
            assert profile.provider, f"Profile {name} has empty provider"

    def test_resolve_profile_returns_provider(self):
        profile = resolve_profile("claude_sonnet")
        assert profile.provider == "openai"

    def test_profile_is_frozen(self):
        profile = resolve_profile("claude_sonnet")
        with pytest.raises(AttributeError):
            profile.provider = "anthropic"  # type: ignore[misc]


class TestProviderConsistency:
    """Verify provider flows consistently through the resolution chain."""

    def test_task_route_and_profile_route_agree(self):
        """For profile-backed tasks, task route and profile route must agree."""
        task_route = resolve_task_route(ANALYST_REASONING)
        profile_route = resolve_profile_route("claude_sonnet")
        assert task_route.provider == profile_route.provider
        assert task_route.model == profile_route.model

    def test_arbiter_task_route_matches_opus_profile(self):
        task_route = resolve_task_route(ARBITER_DECISION)
        profile_route = resolve_profile_route("claude_opus")
        assert task_route.provider == profile_route.provider
        assert task_route.model == profile_route.model
