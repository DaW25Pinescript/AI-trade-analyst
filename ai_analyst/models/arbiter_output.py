from pydantic import BaseModel
from typing import Optional, Literal


class ApprovedSetup(BaseModel):
    type: str
    entry_zone: str
    stop: str
    targets: list[str]
    rr_estimate: float
    confidence: float
    indicator_dependent: bool = False  # True if setup relies primarily on indicator claims


class AuditLog(BaseModel):
    run_id: str
    analysts_received: int
    analysts_valid: int
    htf_consensus: bool
    setup_consensus: bool
    risk_override: bool
    overlay_provided: bool = False          # was the 15M ICT overlay submitted?
    indicator_dependent_setups: int = 0    # count of setups that primarily rely on indicator claims


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
    overlay_was_provided: bool = False          # was the 15M ICT overlay submitted?
    indicator_dependent: bool = False           # does the verdict primarily rely on indicator claims?
    indicator_dependency_notes: Optional[str] = None  # which claims are indicator-sourced
