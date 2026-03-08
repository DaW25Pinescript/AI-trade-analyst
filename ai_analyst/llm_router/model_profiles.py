"""Centralized runtime model profiles.

This module is the single source of truth for runtime model identity strings.
Model IDs are defined here and resolved by profile name at call sites.

Transport configuration (base_url, api_key, retries, etc.) remains in the
router/config layer and is intentionally not part of these profile records.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    tier: str


MODEL_PROFILES: dict[str, ModelProfile] = {
    "claude_sonnet": ModelProfile(
        name="claude_sonnet",
        model="claude-sonnet-4-6",
        tier="worker",
    ),
    "claude_opus": ModelProfile(
        name="claude_opus",
        model="claude-opus-4-6",
        tier="heavy",
    ),
}


def resolve_profile(profile_name: str) -> ModelProfile:
    """Resolve a profile name to a ModelProfile.

    Raises:
        ValueError: if the provided profile name is unknown.
    """
    profile = MODEL_PROFILES.get(profile_name)
    if profile is None:
        raise ValueError(
            f"Unknown model profile '{profile_name}'. Valid profiles: {sorted(MODEL_PROFILES)}"
        )
    return profile
