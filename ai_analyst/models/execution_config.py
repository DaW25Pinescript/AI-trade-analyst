from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class AnalystDelivery(Enum):
    API = "api"       # automated via LiteLLM
    MANUAL = "manual" # user pastes prompt, returns JSON


class AnalystConfig(BaseModel):
    analyst_id: str
    persona: "PersonaType"           # imported at use-site to avoid circular import
    delivery: AnalystDelivery
    model: Optional[str] = None      # required if delivery == API
    api_key_env_var: Optional[str] = None  # e.g. "OPENAI_API_KEY"


class ExecutionConfig(BaseModel):
    mode: str  # "manual" | "hybrid" | "automated"
    analysts: list[AnalystConfig]

    @property
    def has_api_analysts(self) -> bool:
        return any(a.delivery == AnalystDelivery.API for a in self.analysts)

    @property
    def has_manual_analysts(self) -> bool:
        return any(a.delivery == AnalystDelivery.MANUAL for a in self.analysts)

    @property
    def api_analysts(self) -> list[AnalystConfig]:
        return [a for a in self.analysts if a.delivery == AnalystDelivery.API]

    @property
    def manual_analysts(self) -> list[AnalystConfig]:
        return [a for a in self.analysts if a.delivery == AnalystDelivery.MANUAL]


# ---------------------------------------------------------------------------
# Run State Machine
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    CREATED = "CREATED"
    PROMPTS_GENERATED = "PROMPTS_GENERATED"
    AWAITING_RESPONSES = "AWAITING_RESPONSES"
    RESPONSES_COLLECTED = "RESPONSES_COLLECTED"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    ARBITER_COMPLETE = "ARBITER_COMPLETE"
    VERDICT_ISSUED = "VERDICT_ISSUED"
    ERROR = "ERROR"


class RunState(BaseModel):
    run_id: str
    status: RunStatus
    mode: str
    instrument: str
    session: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    analysts_pending: list[str] = []   # analyst_ids not yet responded
    analysts_complete: list[str] = []  # analyst_ids with validated responses
    prompt_pack_dir: Optional[str] = None
    error: Optional[str] = None
