from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Literal
from datetime import datetime, timezone

from .persona import PersonaType  # no circular dependency — persona.py imports nothing from here


class AnalystDelivery(Enum):
    API = "api"       # automated via LiteLLM
    MANUAL = "manual" # user pastes prompt, returns JSON


class AnalystConfig(BaseModel):
    analyst_id: str
    persona: PersonaType
    delivery: AnalystDelivery
    model: Optional[str] = None      # required if delivery == API
    api_key_env_var: Optional[str] = None  # e.g. "OPENAI_API_KEY"


class ExecutionConfig(BaseModel):
    mode: Literal["manual", "hybrid", "automated"]
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analysts_pending: list[str] = []   # analyst_ids not yet responded
    analysts_complete: list[str] = []  # analyst_ids with validated responses
    prompt_pack_dir: Optional[str] = None
    error: Optional[str] = None
