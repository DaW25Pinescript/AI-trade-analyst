"""
Builds the Arbiter prompt by injecting structured analyst evidence into the template.
The Arbiter never sees chart images — only structured Evidence Objects (JSON).

When a 15M overlay was provided, the arbiter also receives the overlay delta reports
and applies the weighting rules defined in the lens-aware screenshot architecture.

When macro_context is provided (MRO Phase 2), the arbiter_block() text is injected
after the overlay section as advisory-only contextual evidence.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional
from ..models.analyst_output import AnalystOutput, OverlayDeltaReport
from ..models.ground_truth import RiskConstraints
from .lens_loader import load_arbiter_template

if TYPE_CHECKING:
    from macro_risk_officer.core.models import MacroContext


def build_arbiter_prompt(
    analyst_outputs: list[AnalystOutput],
    risk_constraints: RiskConstraints,
    run_id: str,
    overlay_delta_reports: list[OverlayDeltaReport] | None = None,
    overlay_was_provided: bool = False,
    macro_context: Optional[MacroContext] = None,
) -> str:
    """
    Load the arbiter template and inject:
      - N                       : number of analysts
      - analyst_outputs_json    : JSON array of all Phase 1 analyst evidence objects
      - risk_constraints_json   : JSON of the risk constraints
      - min_rr                  : minimum acceptable R:R from risk constraints
      - overlay_section         : overlay delta reports + weighting rules (if overlay provided)
      - macro_section           : MacroContext arbiter block, or MRO-unavailable notice
    """
    template = load_arbiter_template()

    analyst_outputs_json = json.dumps(
        [a.model_dump() for a in analyst_outputs],
        indent=2,
    )
    risk_constraints_json = json.dumps(
        risk_constraints.model_dump(),
        indent=2,
    )

    overlay_section = _build_overlay_section(overlay_delta_reports, overlay_was_provided)
    macro_section = _build_macro_section(macro_context)

    return template.format(
        N=len(analyst_outputs),
        analyst_outputs_json=analyst_outputs_json,
        risk_constraints_json=risk_constraints_json,
        min_rr=risk_constraints.min_rr,
        run_id=run_id,
        overlay_section=overlay_section,
        overlay_was_provided=str(overlay_was_provided).lower(),
        macro_section=macro_section,
    )


def _build_macro_section(macro_context: Optional[MacroContext]) -> str:
    """Build the macro risk section injected into the arbiter prompt."""
    if macro_context is None:
        return (
            "=== MACRO RISK CONTEXT ===\n"
            "MRO unavailable for this run. "
            "No macro context — base verdict on price structure and risk constraints only.\n"
            "macro_context_available: false"
        )
    return macro_context.arbiter_block()


def _build_overlay_section(
    delta_reports: list[OverlayDeltaReport] | None,
    overlay_was_provided: bool,
) -> str:
    """Build the overlay section injected into the arbiter template."""
    if not overlay_was_provided:
        return (
            "=== 15M ICT OVERLAY ===\n"
            "No overlay was provided for this run. "
            "Verdict must be based on clean price analysis only.\n"
            "overlay_was_provided: false\n"
            "indicator_dependent: false (default — no overlay input)"
        )

    reports_json = json.dumps(
        [r.model_dump() for r in (delta_reports or [])],
        indent=2,
    )

    return f"""=== 15M ICT OVERLAY DELTA REPORTS ===
overlay_was_provided: true
delta_reports_received: {len(delta_reports or [])}

{reports_json}

=== OVERLAY WEIGHTING RULES (apply these in order) ===

1. AGREEMENT RULE: If clean price analysis and overlay confirm the same interpretation
   -> Increase overall_confidence for that construct.

2. REFINEMENT RULE: If overlay refines but does not contradict clean price
   -> Acceptable — proceed, note the refinement in arbiter_notes.

3. CONTRADICTION RULE: If overlay contradicts the clean price reading
   -> Downgrade confidence for that construct or invalidate the setup.
   -> Clean price is GROUND TRUTH. The overlay is WRONG, not the price.

4. INDICATOR-ONLY RULE: If a setup exists only in the overlay and is NOT visible in price
   -> Mark that setup as speculative. Lower its priority.
   -> Set approved_setup.indicator_dependent = true.
   -> Report count in audit_log.indicator_dependent_setups.

5. RISK OVERRIDE: If the approved setup depends PRIMARILY on indicator claims
   -> Apply risk penalty (reduce confidence by at least 0.1).
   -> Set verdict.indicator_dependent = true.
   -> Explain in indicator_dependency_notes.

6. NO-TRADE PRIORITY: If ambiguity between clean price and overlay exceeds your confidence
   threshold after applying the rules above -> NO_TRADE is the preferred outcome.
   A defensible NO_TRADE is better than a speculative entry."""
