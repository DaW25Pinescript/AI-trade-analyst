"""Tests for ai_analyst.lenses.registry — canonical v1 lens registry.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 12.3
"""

from ai_analyst.lenses.registry import (
    LensRegistryEntry,
    V1_LENS_REGISTRY,
    get_enabled_lens_ids,
    get_inactive_lens_ids,
    get_registry_snapshot,
)


class TestLensRegistry:
    """Registry structure and content tests."""

    def test_registry_contains_three_v1_lenses(self):
        assert len(V1_LENS_REGISTRY) == 3

    def test_registry_entries_have_id_version_enabled(self):
        for entry in V1_LENS_REGISTRY:
            assert isinstance(entry.id, str) and entry.id
            assert isinstance(entry.version, str) and entry.version
            assert isinstance(entry.enabled, bool)

    def test_registry_ids_are_structure_trend_momentum(self):
        ids = [e.id for e in V1_LENS_REGISTRY]
        assert ids == ["structure", "trend", "momentum"]

    def test_registry_versions_are_v1(self):
        for entry in V1_LENS_REGISTRY:
            assert entry.version == "v1.0"

    def test_all_lenses_enabled_by_default(self):
        for entry in V1_LENS_REGISTRY:
            assert entry.enabled is True

    def test_entries_are_frozen(self):
        entry = V1_LENS_REGISTRY[0]
        try:
            entry.id = "other"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_canonical_registry_is_immutable_tuple(self):
        assert isinstance(V1_LENS_REGISTRY, tuple)


class TestRegistryHelpers:
    """Helper function tests."""

    def test_get_registry_snapshot_returns_list_of_dicts(self):
        snap = get_registry_snapshot()
        assert isinstance(snap, list)
        assert len(snap) == 3
        for d in snap:
            assert set(d.keys()) == {"id", "version", "enabled"}

    def test_get_registry_snapshot_matches_spec_shape(self):
        snap = get_registry_snapshot()
        expected = [
            {"id": "structure", "version": "v1.0", "enabled": True},
            {"id": "trend", "version": "v1.0", "enabled": True},
            {"id": "momentum", "version": "v1.0", "enabled": True},
        ]
        assert snap == expected

    def test_enabled_lens_ids_default_to_structure_trend_momentum(self):
        assert get_enabled_lens_ids() == ["structure", "trend", "momentum"]

    def test_inactive_lens_ids_empty_by_default(self):
        assert get_inactive_lens_ids() == []

    def test_inactive_lens_logic_when_one_disabled(self):
        custom = (
            LensRegistryEntry(id="structure", version="v1.0", enabled=True),
            LensRegistryEntry(id="trend", version="v1.0", enabled=False),
            LensRegistryEntry(id="momentum", version="v1.0", enabled=True),
        )
        assert get_enabled_lens_ids(custom) == ["structure", "momentum"]
        assert get_inactive_lens_ids(custom) == ["trend"]

    def test_custom_registry_does_not_mutate_canonical(self):
        custom = (
            LensRegistryEntry(id="structure", version="v1.0", enabled=False),
            LensRegistryEntry(id="trend", version="v1.0", enabled=False),
            LensRegistryEntry(id="momentum", version="v1.0", enabled=False),
        )
        assert get_enabled_lens_ids(custom) == []
        # Canonical unchanged
        assert get_enabled_lens_ids() == ["structure", "trend", "momentum"]
