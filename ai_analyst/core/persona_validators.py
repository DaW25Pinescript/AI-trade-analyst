"""VALIDATOR_REGISTRY and run_validators() runner.

Spec reference: Sections 6.4, 6.6

Registry values return True when valid, or a violation string when invalid.
run_validators() is pure — no mutation, no side effects.
"""

from dataclasses import dataclass
from typing import Callable, Literal

from ai_analyst.models.engine_output import AnalysisEngineOutput


VALIDATOR_REGISTRY: dict[str, Callable[[AnalysisEngineOutput], bool | str]] = {
    "default_analyst.requires_two_evidence_fields": lambda o: (
        True if len(o.evidence_used) >= 2
        else "minimum 2 evidence fields required"
    ),
    "risk_officer.no_aggressive_buy_without_confidence": lambda o: (
        True if o.recommended_action != "BUY" or o.confidence >= 0.75
        else "risk_officer: BUY requires confidence >= 0.75"
    ),
    "all_personas.no_evidence_contradiction": lambda o: (
        True  # placeholder — full implementation requires reasoning text analysis
        # v1 soft-only: always passes, logs intent
    ),
    "all_personas.evidence_paths_exist": lambda o: (
        True  # placeholder — full validation requires snapshot access
        # actual path traversal implemented in PR-AE-5 with snapshot integration
    ),
    "all_personas.counterpoint_required": lambda o: (
        True if len(o.counterpoints) >= 1 or o.confidence >= 0.80
        else "minimum 1 counterpoint required when confidence < 0.80"
    ),
    "all_personas.falsifiable_required": lambda o: (
        True if len(o.what_would_change_my_mind) >= 1
        else "minimum 1 what_would_change_my_mind entry required"
    ),
}


@dataclass(frozen=True)
class ValidationResult:
    validator_name: str
    passed: bool
    message: str | None = None
    level: Literal["soft", "moderate", "hard"] = "soft"


def run_validators(
    output: AnalysisEngineOutput,
    validator_names: list[str],
    level: Literal["soft", "moderate", "hard"] = "soft",
) -> list[ValidationResult]:
    """Run named validators against an AnalysisEngineOutput.

    Returns list of ValidationResult. Does NOT modify the output.
    Caller decides enforcement:
    - soft:     log violation only
    - moderate: log + caller should downgrade confidence by 0.10
    - hard:     caller should invalidate output (treated as failed analyst)
    """
    results = []
    for name in validator_names:
        validator_fn = VALIDATOR_REGISTRY.get(name)
        if validator_fn is None:
            results.append(ValidationResult(
                validator_name=name,
                passed=False,
                message=f"Unknown validator: {name}",
                level=level,
            ))
            continue

        result = validator_fn(output)
        if result is True:
            results.append(ValidationResult(
                validator_name=name, passed=True, level=level,
            ))
        else:
            results.append(ValidationResult(
                validator_name=name, passed=False, message=result, level=level,
            ))

    return results


def check_degraded_confidence_cap(
    output: AnalysisEngineOutput,
    degraded: bool,
) -> bool | str:
    """Check that confidence does not exceed 0.65 on a degraded snapshot."""
    if degraded and output.confidence > 0.65:
        return f"confidence {output.confidence} exceeds 0.65 cap on degraded snapshot"
    return True
