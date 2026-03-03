from pydantic import BaseModel


class LLMUsageEntry(BaseModel):
    run_id: str
    ts_utc: str
    stage: str
    node: str | None = None
    backend: str
    model: str
    provider: str | None = None
    success: bool
    attempts: int
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    error: str | None = None
