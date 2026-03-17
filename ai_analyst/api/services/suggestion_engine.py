"""Rules-based suggestion engine v0 (PR-REFLECT-3).

Pure functions — no side effects, no persistence, no mutation paths.
Two rules only: OVERRIDE_FREQ_HIGH and NO_TRADE_CONCENTRATION.
"""

from __future__ import annotations

from ai_analyst.api.models.reflect import (
    PatternBucket,
    PersonaStats,
    Suggestion,
    SuggestionEvidence,
)

# ---- Constants ----

OVERRIDE_RATE_THRESHOLD = 0.5
NO_TRADE_RATE_THRESHOLD = 0.8
PERSONA_MIN_PARTICIPATION = 10


# ---- Helpers ----

def humanise_persona(raw: str) -> str:
    """Convert machine-style persona string to operator-facing display."""
    return raw.replace("_", " ").title()


def compute_navigable_entity_id(persona: str | None) -> str | None:
    """Deterministic mapping: persona → Agent Ops entity_id."""
    if not persona:
        return None
    return f"persona_{persona}"


def _no_trade_count_from_verdict_distribution(
    verdict_distribution: list | None,
) -> int | None:
    """Extract NO_TRADE count from verdict_distribution.

    Returns None if verdict_distribution is malformed or null (suppresses suggestion).
    Returns 0 if present but no NO_TRADE entry.
    """
    if verdict_distribution is None:
        return None
    if not isinstance(verdict_distribution, list):
        return None
    total = 0
    for entry in verdict_distribution:
        if not isinstance(entry, dict) and not hasattr(entry, "verdict"):
            # Pydantic models have attributes; dicts have keys
            continue
        try:
            verdict = entry.verdict if hasattr(entry, "verdict") else entry.get("verdict")
            count = entry.count if hasattr(entry, "count") else entry.get("count")
            if verdict is None or count is None:
                return None  # malformed entry → suppress
            if not isinstance(verdict, str) or not isinstance(count, int):
                return None  # malformed entry → suppress
            if verdict == "NO_TRADE":
                total += count
        except Exception:
            return None
    return total


# ---- Rule functions ----

def _check_override_freq_high(stat: PersonaStats) -> Suggestion | None:
    """Rule 1: OVERRIDE_FREQ_HIGH."""
    if stat.override_rate is None:
        return None
    if stat.participation_count < PERSONA_MIN_PARTICIPATION:
        return None
    if stat.override_rate <= OVERRIDE_RATE_THRESHOLD:
        return None

    persona_humanised = humanise_persona(stat.persona)
    override_rate_pct = round(stat.override_rate * 100)

    message = (
        f"{persona_humanised} was overridden in {stat.override_count} of "
        f"{stat.participation_count} recent runs (override rate {override_rate_pct}%) "
        f"— consider reviewing its analysis focus or prompt configuration"
    )

    return Suggestion(
        rule_id="OVERRIDE_FREQ_HIGH",
        severity="warning",
        category="persona",
        target=persona_humanised,
        message=message,
        evidence=SuggestionEvidence(
            metric_name="override_rate",
            metric_value=stat.override_rate,
            threshold=OVERRIDE_RATE_THRESHOLD,
            sample_size=stat.participation_count,
        ),
    )


def _check_no_trade_concentration(bucket: PatternBucket) -> Suggestion | None:
    """Rule 2: NO_TRADE_CONCENTRATION."""
    if not bucket.threshold_met:
        return None
    if bucket.no_trade_rate is None:
        return None
    if bucket.no_trade_rate <= NO_TRADE_RATE_THRESHOLD:
        return None

    no_trade_count = _no_trade_count_from_verdict_distribution(
        bucket.verdict_distribution,
    )
    if no_trade_count is None:
        return None  # malformed → suppress

    no_trade_rate_pct = round(bucket.no_trade_rate * 100)
    target = f"{bucket.instrument} × {bucket.session}"

    message = (
        f"{bucket.instrument} {bucket.session} session produced NO_TRADE in "
        f"{no_trade_count} of {bucket.run_count} recent runs ({no_trade_rate_pct}%) "
        f"— confidence threshold may be too high for this instrument/session combination"
    )

    return Suggestion(
        rule_id="NO_TRADE_CONCENTRATION",
        severity="warning",
        category="pattern",
        target=target,
        message=message,
        evidence=SuggestionEvidence(
            metric_name="no_trade_rate",
            metric_value=bucket.no_trade_rate,
            threshold=NO_TRADE_RATE_THRESHOLD,
            sample_size=bucket.run_count,
        ),
    )


# ---- Aggregation ----

def _dedup_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Keep unique (rule_id, target) pairs; on collision keep higher sample_size."""
    seen: dict[tuple[str, str], Suggestion] = {}
    for s in suggestions:
        key = (s.rule_id, s.target)
        existing = seen.get(key)
        if existing is None or s.evidence.sample_size > existing.evidence.sample_size:
            seen[key] = s
    return list(seen.values())


def _sort_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Sort: descending metric_value, then ascending target."""
    return sorted(
        suggestions,
        key=lambda s: (-s.evidence.metric_value, s.target),
    )


def generate_persona_suggestions(stats: list[PersonaStats]) -> list[Suggestion]:
    """Generate suggestions for persona performance response."""
    suggestions: list[Suggestion] = []
    for stat in stats:
        result = _check_override_freq_high(stat)
        if result is not None:
            suggestions.append(result)
    return _sort_suggestions(_dedup_suggestions(suggestions))


def generate_pattern_suggestions(buckets: list[PatternBucket]) -> list[Suggestion]:
    """Generate suggestions for pattern summary response."""
    suggestions: list[Suggestion] = []
    for bucket in buckets:
        result = _check_no_trade_concentration(bucket)
        if result is not None:
            suggestions.append(result)
    return _sort_suggestions(_dedup_suggestions(suggestions))
