"""
Builds the Arbiter prompt by injecting structured analyst evidence into the template.
The Arbiter never sees chart images — only structured Evidence Objects (JSON).
"""
import json
from ..models.analyst_output import AnalystOutput
from ..models.ground_truth import RiskConstraints
from .lens_loader import load_arbiter_template


def build_arbiter_prompt(
    analyst_outputs: list[AnalystOutput],
    risk_constraints: RiskConstraints,
    run_id: str,
) -> str:
    """
    Load the arbiter template and inject:
      - N               : number of analysts
      - analyst_outputs_json : JSON array of all analyst evidence objects
      - risk_constraints_json: JSON of the risk constraints
      - min_rr          : minimum acceptable R:R from risk constraints
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

    return template.format(
        N=len(analyst_outputs),
        analyst_outputs_json=analyst_outputs_json,
        risk_constraints_json=risk_constraints_json,
        min_rr=risk_constraints.min_rr,
        run_id=run_id,
    )
