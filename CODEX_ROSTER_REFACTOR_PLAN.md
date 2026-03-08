# Analyst Roster Refactor: Claude-First Architecture

## Architecture Decision

Refactor the analyst system from vendor-labeled roster slots to a **persona-based roster** with **config-driven runtime model profiles**.

**Core principle:** Analyst diversity comes from persona/prompt/lens — not provider labels. Runtime model binding is a separate, config-driven concern.

### Refinement Notes (Approved Adjustments)

1. **Keep runtime transport config (base_url, auth) separate from the profile registry** unless diagnostics prove per-profile endpoints are required. The profile registry owns model identity and tier — the router/config layer owns transport.
2. **The profile registry is the single source of truth for model identity strings.** Model IDs are defined there and nowhere else — this is the chosen pattern. Tests assert profile semantics (valid profile, correct tier, model string contains expected family name) — not brittle exact-version literals. If environment-specific variation is needed later, add env/config loading **inside the profile registry file itself** so it remains the sole source of truth. Do not create a second source of truth elsewhere. Do not mix this pattern with "model strings from external config" — pick one, and the decision is: the registry owns them.
3. **Preserve existing persona identifiers exactly** unless a rename is explicitly required by a failing test or repo contract. Do not invent new persona names.
4. **Add a consolidated roster-schema invariant test** that checks persona/profile presence, valid profile references, and absence of legacy raw `model` fields — all in one place so regressions are caught immediately.

### Codex Implementation Directive

```
Final refinements (apply before implementation):
1. Be explicit about where the exact Claude model strings live — the profile
   registry IS the source of truth. Model strings are defined there and only
   there. Do not mix this with "load from external config." If env variation
   is needed later, add loading inside the registry file itself.
2. Preserve existing persona identifiers exactly; example persona names in
   this plan are illustrative only. Never rename a persona during this refactor.
3. Add one consolidated roster-schema invariant test covering persona/profile
   presence, valid profiles, and absence of legacy raw model fields.
```

---

## Current State (Broken)

The merge flattened `ANALYST_CONFIGS` so multiple analysts now point to `openai/claude-sonnet-4-6`, breaking two test invariants:

| Test | Expected | Got |
|------|----------|-----|
| `test_single_survivor_uses_its_original_config` | `gemini/gemini-1.5-pro` (index 2) | `openai/claude-sonnet-4-6` |
| `test_analyst_configs_grok_model_is_xai_prefixed` | `xai/...` prefix (ICT_PURIST) | `openai/claude-sonnet-4-6` |

**Historical roster** (confirmed from runtime logs before the merge):

| Index | Model String | Role |
|-------|-------------|------|
| 0 | `openai/claude-sonnet-4-6` | — |
| 1 | `gpt-4o` | — |
| 2 | `gemini/gemini-1.5-pro` | — |
| 3 | `xai/grok-vision-beta` | ICT_PURIST |

This multi-vendor roster is no longer the active runtime contract. The system now uses Claude exclusively via CLIProxyAPI.

---

## Target State

### New Contract

- **All standard analyst personas** → `claude-sonnet-4-6`
- **Higher-order synthesis / Arbiter** → `claude-opus-4-6`
- **Persona identity** remains distinct per analyst slot
- **Runtime model binding** is resolved through a centralized profile registry
- **Future non-Claude providers** remain possible through config, but are not the active contract

### Execution Model

| Tier | Profile Name | Model ID | Used By |
|------|-------------|----------|---------|
| Heavy lifter | `claude_opus` | `claude-opus-4-6` | Arbiter, final synthesis, conflict resolution, higher-order review |
| Grunt / Worker | `claude_sonnet` | `claude-sonnet-4-6` | All standard analyst personas, first-pass reasoning, structure extraction, confluence summarization |

---

## Implementation Plan

### Phase 1 — Audit Current State

**Action:** Inspect and document the current configuration.

1. Open `ai_analyst/graph/analyst_nodes.py` and locate `ANALYST_CONFIGS`
2. Document the current roster (persona names, model strings, any metadata)
3. Search the codebase for all references to the old vendor-specific model strings:
   - `gemini/gemini-1.5-pro`
   - `xai/grok-vision-beta`
   - `gpt-4o`
   - Any hardcoded model string literals
4. Locate the "single survivor" code path (likely in `analyst_nodes.py` or `arbiter_node.py`) — the logic that picks one analyst and returns their config
5. Identify all affected test files, especially:
   - `test_overlay_delta_config_alignment.py`
   - `test_v202_fixes.py`
   - Any other test that asserts specific model strings

**Deliverable:** Short audit summary listing every file and line that needs to change.

---

### Phase 2 — Create the Profile Registry

**Action:** Introduce a centralized model profile registry.

**New file:** `ai_analyst/llm_router/model_profiles.py` (or add to an existing config module if more appropriate)

```python
"""
Centralized runtime model profiles — the SINGLE SOURCE OF TRUTH for model identity.

Model ID strings are defined here and ONLY here. No other file in the codebase
should contain hardcoded model strings. All consumers resolve model identity
through resolve_profile().

Analyst diversity comes from persona/prompt/lens, not provider labels.
Transport config (base_url, auth) is owned by the router/config layer, not here.

Current baseline: Claude-first via local proxy.
Future providers can be added as new profiles without touching the roster.

If environment-specific model string variation is needed later (e.g. different
model versions in dev vs prod), add env/config loading HERE so this file remains
the sole source of truth. Do not create a second source of truth elsewhere.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelProfile:
    """Runtime model identity. Transport config lives in the router layer."""
    model: str          # Model ID string for the API/proxy
    tier: str           # "heavy" or "standard" — describes execution tier
    description: str    # Human-readable purpose


# --- Profile Registry ---
# Single source of truth for runtime model identity.
# To add a new provider: add a profile here, then assign it in ANALYST_CONFIGS.
# Transport config (base_url, auth, timeouts) is NOT stored here — that belongs
# in the router/config layer so it can vary by environment without touching profiles.

MODEL_PROFILES: Dict[str, ModelProfile] = {
    "claude_opus": ModelProfile(
        model="claude-opus-4-6",
        tier="heavy",
        description="Heavy lifter — arbiter, synthesis, conflict resolution",
    ),
    "claude_sonnet": ModelProfile(
        model="claude-sonnet-4-6",
        tier="standard",
        description="Grunt — standard analyst passes, extraction, structured output",
    ),
}


def resolve_profile(profile_name: str) -> ModelProfile:
    """Resolve a profile name to its runtime model identity.

    Raises KeyError with a clear message if the profile is not registered.
    """
    if profile_name not in MODEL_PROFILES:
        available = ", ".join(sorted(MODEL_PROFILES.keys()))
        raise KeyError(
            f"Unknown model profile '{profile_name}'. "
            f"Available profiles: {available}"
        )
    return MODEL_PROFILES[profile_name]
```

**Key constraints:**
- This file is the **single source of truth** for runtime model identity strings — no model strings should appear anywhere else in the codebase
- **Transport config (base_url, auth, timeouts) stays in the router/config layer** — do not put it here
- If environment-specific model string variation is needed later, add env/config loading **inside this file** so it remains the sole source of truth — do not create a second source of truth elsewhere
- The pattern is: profile registry owns model identity, router/config owns transport — these never overlap

**Critical decision: model string format.**
Earlier runtime paths used `openai/`-prefixed model names (e.g. `openai/claude-sonnet-4-6`), while the proxy itself exposes raw model IDs (e.g. `claude-sonnet-4-6`). The profile registry must store whichever format the consuming code actually sends to the API/proxy. Codex must determine during the Phase 1 audit which format the current execution path expects and use that consistently. Specifically:
- If the router/client sends the model string directly to the local proxy → use the raw proxy IDs: `claude-sonnet-4-6`, `claude-opus-4-6`
- If the router/client goes through a LiteLLM or OpenAI-compatible wrapper that expects a provider prefix → use the prefixed IDs: `openai/claude-sonnet-4-6`, `openai/claude-opus-4-6`

**Do not leave this implicit.** Document the chosen format in a comment in the profile registry file.

---

### Phase 3 — Refactor the Analyst Roster

**Action:** Update `ANALYST_CONFIGS` in `ai_analyst/graph/analyst_nodes.py`.

**Before** (broken — flattened to Claude):
```python
ANALYST_CONFIGS = [
    {"model": "openai/claude-sonnet-4-6", ...},
    {"model": "openai/claude-sonnet-4-6", ...},
    {"model": "openai/claude-sonnet-4-6", ...},  # was gemini
    {"model": "openai/claude-sonnet-4-6", ...},  # was xai/grok
]
```

**After** (persona + profile):
```python
# ══════════════════════════════════════════════════════════════════════
# ⚠️  HARD RULE: The persona names below are PLACEHOLDERS ONLY.
# Codex MUST discover the actual persona identifiers from the existing
# codebase during Phase 1 audit and use those EXACTLY. Do NOT invent
# new names, rename existing personas, or use these placeholder strings.
# A careless rename will create avoidable fallout across prompts, tests,
# and UI references.
# ══════════════════════════════════════════════════════════════════════
ANALYST_CONFIGS = [
    {
        "persona": "<EXISTING_PERSONA_0>",   # use actual name from repo
        "profile": "claude_sonnet",
        # ... preserve any other existing fields (system_prompt, lens, etc.)
    },
    {
        "persona": "<EXISTING_PERSONA_1>",   # use actual name from repo
        "profile": "claude_sonnet",
    },
    {
        "persona": "<EXISTING_PERSONA_2>",   # use actual name from repo
        "profile": "claude_sonnet",
    },
    {
        "persona": "<EXISTING_PERSONA_3>",   # use actual name from repo
        "profile": "claude_sonnet",
    },
]
```

**For the Arbiter** (likely in `arbiter_node.py`):
```python
ARBITER_CONFIG = {
    "persona": "<EXISTING_ARBITER_PERSONA>",  # use actual name from repo
    "profile": "claude_opus",
    # ... preserve existing fields
}
```

**Important:**
- **HARD RULE: Preserve existing persona identifiers exactly as they currently exist in the codebase.** All persona names shown in this plan (including `macro_analyst`, `trend_analyst`, `ict_purist`, etc.) are **placeholders only**. Codex must read the actual persona names from the repo during the Phase 1 audit and use those names verbatim. Do not rename any persona during this refactor unless a failing test or explicit repo contract requires it. A careless rename creates avoidable fallout across prompts, tests, and UI references.
- Preserve all existing metadata fields (system prompts, lenses, etc.)
- The only structural change is replacing the `model` field with `profile`
- Update any code that reads `config["model"]` to instead resolve through `resolve_profile(config["profile"]).model`

---

### Phase 4 — Fix the Survivor Path

**Action:** Ensure the "single survivor" code path preserves the original persona/profile config.

Locate the logic (search for `survivor`, `single_survivor`, or the filtering/selection path). The current bug may be:
- The survivor path is overwriting the selected analyst's config with a default model
- Or the static roster itself was the only problem

**Required behavior:**
- When one analyst survives filtering, its `persona` and `profile` are returned unchanged
- No default-model rewrite occurs
- The survivor's full config dict passes through intact

---

### Phase 5 — Rewrite Tests

**Action:** Replace vendor-specific assertions with persona/profile contract assertions.

#### Tests to Remove or Replace

**Remove:**
- `test_single_survivor_uses_its_original_config` — the old assertion checking for `gemini/gemini-1.5-pro`
- `test_analyst_configs_grok_model_is_xai_prefixed` — the old assertion checking for `xai/` prefix

**Replace with these new tests:**

```python
# --- Consolidated roster-schema invariant test ---
# This single test catches all structural regressions in one place.

def test_roster_schema_invariants():
    """
    Consolidated invariant: every analyst config and the arbiter config
    conform to the post-migration schema.

    Checks:
    - Every analyst config has 'persona' and 'profile' keys
    - No analyst config retains the legacy raw 'model' field
    - Every referenced profile exists in the profile registry
    - Arbiter config has 'persona' and 'profile' keys
    - Arbiter config has no legacy 'model' field
    - Arbiter profile exists in the registry
    """
    for i, config in enumerate(ANALYST_CONFIGS):
        label = f"ANALYST_CONFIGS[{i}]"
        assert "persona" in config, f"{label} missing 'persona' key"
        assert "profile" in config, f"{label} missing 'profile' key"
        assert "model" not in config, (
            f"{label} (persona: {config.get('persona', '?')}) still contains "
            f"legacy 'model' field. Use 'profile' instead."
        )
        # Will raise KeyError if profile is not registered
        profile = resolve_profile(config["profile"])
        assert profile.model, f"{label} profile '{config['profile']}' resolved to empty model string"

    assert "persona" in ARBITER_CONFIG, "ARBITER_CONFIG missing 'persona' key"
    assert "profile" in ARBITER_CONFIG, "ARBITER_CONFIG missing 'profile' key"
    assert "model" not in ARBITER_CONFIG, (
        "ARBITER_CONFIG still contains legacy 'model' field. Use 'profile' instead."
    )
    arbiter_profile = resolve_profile(ARBITER_CONFIG["profile"])
    assert arbiter_profile.model, "Arbiter profile resolved to empty model string"


# --- Roster contract tests ---

def test_analyst_configs_have_required_personas():
    """Every required persona must exist in the roster."""
    persona_names = [c["persona"] for c in ANALYST_CONFIGS]
    # ⚠️  PLACEHOLDER NAMES — replace with the actual persona identifiers from the repo.
    for required in ["<EXISTING_PERSONA_0>", "<EXISTING_PERSONA_1>", "<EXISTING_PERSONA_2>", "<EXISTING_PERSONA_3>"]:
        assert required in persona_names, f"Missing required persona: {required}"


def test_analyst_configs_have_valid_profiles():
    """Every analyst config must reference a profile that exists in the registry."""
    for config in ANALYST_CONFIGS:
        assert "profile" in config, f"Analyst {config.get('persona', '?')} missing 'profile' key"
        # This will raise KeyError if profile is not registered
        resolve_profile(config["profile"])


def test_standard_analysts_use_sonnet():
    """Current contract: all standard analyst personas use claude_sonnet."""
    for config in ANALYST_CONFIGS:
        assert config["profile"] == "claude_sonnet", (
            f"Analyst '{config['persona']}' uses profile '{config['profile']}', "
            f"expected 'claude_sonnet'"
        )


def test_arbiter_uses_opus():
    """Current contract: arbiter uses claude_opus for higher-order synthesis."""
    assert ARBITER_CONFIG["profile"] == "claude_opus"


# --- Profile registry tests ---

def test_profile_registry_contains_required_profiles():
    """The registry must contain the baseline Claude profiles."""
    assert "claude_sonnet" in MODEL_PROFILES
    assert "claude_opus" in MODEL_PROFILES


def test_claude_sonnet_profile_resolves_to_sonnet():
    """claude_sonnet profile resolves to a valid Claude Sonnet model string."""
    profile = resolve_profile("claude_sonnet")
    assert profile.model, "claude_sonnet model string must be non-empty"
    assert "sonnet" in profile.model.lower(), (
        f"claude_sonnet profile should resolve to a Sonnet model, got '{profile.model}'"
    )
    assert profile.tier == "standard"


def test_claude_opus_profile_resolves_to_opus():
    """claude_opus profile resolves to a valid Claude Opus model string."""
    profile = resolve_profile("claude_opus")
    assert profile.model, "claude_opus model string must be non-empty"
    assert "opus" in profile.model.lower(), (
        f"claude_opus profile should resolve to an Opus model, got '{profile.model}'"
    )
    assert profile.tier == "heavy"


def test_invalid_profile_raises():
    """Requesting a non-existent profile raises KeyError."""
    import pytest
    with pytest.raises(KeyError):
        resolve_profile("nonexistent_profile")


# --- Survivor path tests ---

def test_single_survivor_preserves_persona():
    """When one analyst survives, its persona is preserved unchanged."""
    # Simulate the survivor selection with a known config
    original_config = ANALYST_CONFIGS[0].copy()
    # ... run the survivor selection logic ...
    # Assert the result preserves persona and profile
    assert result["persona"] == original_config["persona"]
    assert result["profile"] == original_config["profile"]


def test_single_survivor_preserves_profile():
    """The survivor path does not rewrite the profile to a default."""
    # For each analyst config, verify that if it were the sole survivor,
    # its profile would be preserved as-is
    for config in ANALYST_CONFIGS:
        # ... run survivor logic with only this config ...
        assert result["profile"] == config["profile"]
```

**Notes to Codex:**
- The survivor test bodies above are illustrative pseudo-code. Codex **must** bind these assertions to the actual survivor-selection function/API discovered during the Phase 1 audit. Do not create a fake helper or test-only wrapper solely to satisfy these tests — wire them directly into the real function signatures. If the survivor-selection path does not exist as a clean callable, document that in the audit and propose the minimal extraction needed.
- **HARD RULE on persona names:** Every persona name used in tests must be discovered from the codebase during Phase 1 audit. The placeholder strings `<EXISTING_PERSONA_0>` etc. must be replaced with the actual identifiers. Never rename personas during this refactor — a careless rename creates avoidable fallout across prompts, tests, and UI references.
- The consolidated `test_roster_schema_invariants` is the single structural regression gate. All other tests assert specific contract semantics.

---

### Phase 6 — Update Integration Points

**Action:** Find and update every place that reads the old `model` field from analyst configs.

Search patterns:
```
config["model"]
config.get("model")
analyst.model
.model
```

Each should be updated to resolve through the profile registry:
```python
from ai_analyst.llm_router.model_profiles import resolve_profile

profile = resolve_profile(config["profile"])
model_string = profile.model
# base_url and auth come from the router/config layer, NOT from the profile
```

---

### Phase 7 — Update Documentation

**Action:** Add or update comments/docs to reflect the new contract.

Suggested docstring for the roster module:

```
AI Trade Analyst uses a persona-based multi-analyst architecture with
config-driven runtime model profiles.

Current baseline: Claude-first via local proxy.
- Standard analysts: claude_sonnet (claude-sonnet-4-6)
- Arbiter / synthesis: claude_opus (claude-opus-4-6)

Multi-provider support remains future-capable through the profile registry
in model_profiles.py. To add a new provider, register a profile there and
assign it to the desired analyst persona(s).
```

---

## Acceptance Criteria

All of the following must be true before this refactor is complete:

- [ ] `ANALYST_CONFIGS` uses persona + profile, not raw model strings
- [ ] No analyst config retains the legacy raw `model` field (consolidated schema invariant test passes)
- [ ] All standard analyst personas resolve to `claude_sonnet`
- [ ] Arbiter resolves to `claude_opus`
- [ ] Profile registry is centralized in one file and owns only model identity (not transport)
- [ ] Transport config (base_url, auth) remains in the router/config layer
- [ ] No hardcoded model strings remain outside the profile registry
- [ ] Existing persona identifiers are preserved exactly (no casual renames)
- [ ] Survivor path preserves original persona/profile unchanged
- [ ] Old Gemini/xAI/GPT-specific tests are replaced with persona/profile tests
- [ ] All new contract tests pass
- [ ] Full test suite passes (no regressions)
- [ ] No auth/proxy behavior changed
- [ ] Adding a future provider requires only: (1) new profile entry, (2) assign to persona

---

## Constraints

- **Do not** redesign the graph topology
- **Do not** change auth/proxy behavior unless required for profile resolution
- **Do not** flatten all personas into one generic analyst — personas stay distinct
- **Do not** change the transport layer (CLIProxyAPI / local proxy setup)
- **Do not** put transport config (base_url, auth, timeouts) in the profile registry — that belongs in the router/config layer
- **Do not** rename existing persona identifiers unless explicitly required
- **Do** keep runtime profile resolution separate from persona identity
- **Do** treat the profile registry as the single source of truth for model strings — if the exact runtime string varies by environment, add config/env loading inside the registry, not elsewhere

---

## File Targets (Likely in Scope)

| File | Change |
|------|--------|
| `ai_analyst/graph/analyst_nodes.py` | Refactor `ANALYST_CONFIGS` to persona + profile |
| `ai_analyst/graph/arbiter_node.py` | Refactor arbiter config to use `claude_opus` profile |
| `ai_analyst/llm_router/model_profiles.py` | **New** — centralized profile registry |
| `ai_analyst/llm_router/config_loader.py` | **Only if** current model resolution path cannot consume `profile → model` cleanly without change |
| `ai_analyst/llm_router/router.py` | **Only if** it reads model strings directly and cannot resolve through the profile registry as-is |
| `tests/test_overlay_delta_config_alignment.py` | Replace Gemini slot assertion |
| `tests/test_v202_fixes.py` | Replace xAI prefix assertion |
| Any file reading `config["model"]` | Update to `resolve_profile(config["profile"])` |

---

## Summary

> **Before:** Analyst roster pretended to be multi-vendor at the identity level while actually routing everything through Claude. Tests enforced the old vendor labels. Merge broke them.
>
> **After:** Analyst roster is persona-based. Runtime model binding is config-driven through a centralized profile registry. Claude Sonnet for grunt work, Claude Opus for heavy lifting. Future providers slot in cleanly without touching persona logic.
