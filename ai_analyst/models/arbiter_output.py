from pydantic import BaseModel
from typing import Optional, Literal


class ApprovedSetup(BaseModel):
    type: str
    entry_zone: str
    stop: str
    targets: list[str]
    rr_estimate: float
    confidence: float


class AuditLog(BaseModel):
    run_id: str
    analysts_received: int
    analysts_valid: int
    htf_consensus: bool
    setup_consensus: bool
    risk_override: bool


class FinalVerdict(BaseModel):
    final_bias: str
    decision: Literal["ENTER_LONG", "ENTER_SHORT", "WAIT_FOR_CONFIRMATION", "NO_TRADE"]
    approved_setups: list[ApprovedSetup]
    no_trade_conditions: list[str]
    overall_confidence: float
    analyst_agreement_pct: int
    risk_override_applied: bool
    arbiter_notes: str
    audit_log: AuditLog
