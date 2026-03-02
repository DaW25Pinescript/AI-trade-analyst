"""
Outcome tracker — MRO-P3 stub.

Records MacroContext snapshots alongside post-event price moves for
confidence calibration. SQLite backend to be added in MRO-P3.

No weight updates — outcome data is used for auditable confidence tuning only.
"""

from __future__ import annotations

from macro_risk_officer.core.models import MacroContext


class OutcomeTracker:
    """Stub — full SQLite implementation in MRO-P3."""

    def record(self, context: MacroContext, run_id: str) -> None:
        # TODO (MRO-P3): persist snapshot + run_id to SQLite
        # Track price moves at 1h / 24h / 5d after context timestamp
        pass

    def audit_report(self) -> str:
        # TODO (MRO-P3): compare predicted regime vs observed price direction
        return "Outcome tracking not yet implemented (MRO-P3)."
