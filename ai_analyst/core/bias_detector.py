"""
Phase 7 — Bias Detection in Analyst Outputs.

Post-processing step that the Arbiter can invoke to flag low-diversity
consensus or single-persona dominance BEFORE the final verdict is rendered.

Detection heuristics:
  1. Unanimous consensus with high confidence — all analysts agree on the same
     action AND average confidence > 0.7. Flag as potential groupthink.
  2. Single-persona dominance — one analyst's output is an outlier while all
     others cluster. Not necessarily bad, but worth flagging.
  3. Low HTF-bias diversity — if all analysts report the exact same htf_bias,
     there is no genuine disagreement. Flag when all match and confidence
     spread is narrow (< 0.1 range).
  4. Confidence clustering — if all confidences are within 0.05 of each other,
     analysts may be anchoring to similar reasoning.

Output: a BiasReport injected into the arbiter prompt as advisory evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.analyst_output import AnalystOutput


@dataclass
class BiasFlag:
    """A single bias detection finding."""
    code: str          # machine-readable identifier
    severity: str      # "info", "warning", "critical"
    description: str   # human-readable explanation


@dataclass
class BiasReport:
    """Collection of bias flags for a single arbiter run."""
    analyst_count: int
    flags: list[BiasFlag] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity in ("warning", "critical") for f in self.flags)

    @property
    def highest_severity(self) -> str:
        if any(f.severity == "critical" for f in self.flags):
            return "critical"
        if any(f.severity == "warning" for f in self.flags):
            return "warning"
        if self.flags:
            return "info"
        return "clean"

    def format_for_arbiter(self) -> str:
        """Format as a text block for injection into the arbiter prompt."""
        if not self.flags:
            return (
                "=== BIAS DETECTION ===\n"
                "bias_check: clean\n"
                "No diversity concerns detected across analyst outputs."
            )

        lines = [
            "=== BIAS DETECTION ===",
            f"bias_check: {self.highest_severity}",
            f"flags_found: {len(self.flags)}",
            "",
        ]
        for i, f in enumerate(self.flags, 1):
            lines.append(f"{i}. [{f.severity.upper()}] {f.code}: {f.description}")

        lines.extend([
            "",
            "=== BIAS MITIGATION RULES ===",
            "1. If bias_check is 'critical', reduce overall_confidence by at least 0.15.",
            "2. If bias_check is 'warning', note the flags in arbiter_notes and consider "
            "whether the consensus is genuinely warranted by the evidence.",
            "3. A unanimous high-confidence consensus should be treated with EXTRA scrutiny, "
            "not less — verify each analyst cited independent evidence.",
            "4. If groupthink is flagged, prefer a more cautious decision "
            "(WAIT_FOR_CONFIRMATION over directional entry).",
        ])
        return "\n".join(lines)


# ── Detection engine ──────────────────────────────────────────────────────────


def detect_bias(analyst_outputs: list[AnalystOutput]) -> BiasReport:
    """
    Run all bias detection heuristics against the analyst outputs.

    Args:
        analyst_outputs: The list of Phase 1 (Round 1) analyst Evidence Objects.

    Returns:
        BiasReport with zero or more flags.
    """
    report = BiasReport(analyst_count=len(analyst_outputs))

    if len(analyst_outputs) < 2:
        return report

    _check_unanimous_consensus(analyst_outputs, report)
    _check_htf_bias_diversity(analyst_outputs, report)
    _check_confidence_clustering(analyst_outputs, report)
    _check_action_outlier(analyst_outputs, report)

    return report


def _check_unanimous_consensus(
    outputs: list[AnalystOutput], report: BiasReport
) -> None:
    """Flag when all analysts recommend the same action with high confidence."""
    actions = [o.recommended_action for o in outputs]
    confidences = [o.confidence for o in outputs]

    if len(set(actions)) == 1 and len(actions) >= 2:
        avg_conf = sum(confidences) / len(confidences)
        if avg_conf > 0.7:
            report.flags.append(BiasFlag(
                code="UNANIMOUS_HIGH_CONF",
                severity="warning",
                description=(
                    f"All {len(outputs)} analysts recommend '{actions[0]}' with "
                    f"avg confidence {avg_conf:.2f}. Potential groupthink — verify "
                    f"each analyst cited independent evidence."
                ),
            ))
        elif actions[0] != "NO_TRADE":
            report.flags.append(BiasFlag(
                code="UNANIMOUS_DIRECTIONAL",
                severity="info",
                description=(
                    f"All {len(outputs)} analysts recommend '{actions[0]}' "
                    f"(avg confidence {avg_conf:.2f}). Consensus may be genuine "
                    f"but warrants additional scrutiny."
                ),
            ))


def _check_htf_bias_diversity(
    outputs: list[AnalystOutput], report: BiasReport
) -> None:
    """Flag when all analysts report identical HTF bias with narrow confidence spread."""
    biases = [o.htf_bias for o in outputs]
    confidences = [o.confidence for o in outputs]

    if len(set(biases)) == 1 and len(biases) >= 2:
        conf_range = max(confidences) - min(confidences)
        if conf_range < 0.1:
            report.flags.append(BiasFlag(
                code="LOW_HTF_DIVERSITY",
                severity="warning",
                description=(
                    f"All analysts agree on htf_bias='{biases[0]}' with confidence "
                    f"spread of only {conf_range:.2f}. Low analytical diversity — "
                    f"analysts may be echoing the same reasoning."
                ),
            ))


def _check_confidence_clustering(
    outputs: list[AnalystOutput], report: BiasReport
) -> None:
    """Flag when all confidences cluster within a very narrow range."""
    confidences = [o.confidence for o in outputs]
    conf_range = max(confidences) - min(confidences)

    if conf_range < 0.05 and len(confidences) >= 3:
        avg = sum(confidences) / len(confidences)
        report.flags.append(BiasFlag(
            code="CONFIDENCE_CLUSTERING",
            severity="info",
            description=(
                f"All {len(outputs)} analyst confidences cluster within "
                f"{conf_range:.3f} range (avg {avg:.2f}). Analysts may be "
                f"anchoring to similar heuristics."
            ),
        ))


def _check_action_outlier(
    outputs: list[AnalystOutput], report: BiasReport
) -> None:
    """Flag when exactly one analyst disagrees with all others."""
    if len(outputs) < 3:
        return

    actions = [o.recommended_action for o in outputs]
    action_counts: dict[str, int] = {}
    for a in actions:
        action_counts[a] = action_counts.get(a, 0) + 1

    # Find actions held by exactly one analyst where all others agree
    minority_actions = [a for a, c in action_counts.items() if c == 1]
    majority_actions = [a for a, c in action_counts.items() if c == len(outputs) - 1]

    if len(minority_actions) == 1 and len(majority_actions) == 1:
        minority = minority_actions[0]
        majority = majority_actions[0]

        # Find the outlier analyst index
        outlier_idx = actions.index(minority)
        outlier_conf = outputs[outlier_idx].confidence

        report.flags.append(BiasFlag(
            code="SINGLE_DISSENTER",
            severity="info",
            description=(
                f"Analyst {outlier_idx + 1} recommends '{minority}' (conf {outlier_conf:.2f}) "
                f"while all others recommend '{majority}'. "
                f"The dissenting view may contain valuable contrarian signal."
            ),
        ))
