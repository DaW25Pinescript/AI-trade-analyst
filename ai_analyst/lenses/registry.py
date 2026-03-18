"""Canonical v1 lens registry.

Spec: ANALYSIS_ENGINE_SPEC_v1.2.md Section 12.3

The registry defines which lenses exist, their versions, and whether
they are enabled.  v1 is a static list — no plugin architecture.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LensRegistryEntry:
    id: str
    version: str
    enabled: bool = True


V1_LENS_REGISTRY: tuple[LensRegistryEntry, ...] = (
    LensRegistryEntry(id="structure", version="v1.0", enabled=True),
    LensRegistryEntry(id="trend", version="v1.0", enabled=True),
    LensRegistryEntry(id="momentum", version="v1.0", enabled=True),
)


def get_registry_snapshot(
    registry: tuple[LensRegistryEntry, ...] | None = None,
) -> list[dict]:
    """Return the registry as a list of plain dicts."""
    entries = registry if registry is not None else V1_LENS_REGISTRY
    return [{"id": e.id, "version": e.version, "enabled": e.enabled} for e in entries]


def get_enabled_lens_ids(
    registry: tuple[LensRegistryEntry, ...] | None = None,
) -> list[str]:
    """Return ordered list of enabled lens IDs."""
    entries = registry if registry is not None else V1_LENS_REGISTRY
    return [e.id for e in entries if e.enabled]


def get_inactive_lens_ids(
    registry: tuple[LensRegistryEntry, ...] | None = None,
) -> list[str]:
    """Return ordered list of disabled (inactive) lens IDs."""
    entries = registry if registry is not None else V1_LENS_REGISTRY
    return [e.id for e in entries if not e.enabled]
