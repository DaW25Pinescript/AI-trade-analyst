from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime


class RiskConstraints(BaseModel):
    min_rr: float = 2.0
    max_risk_per_trade: float = 0.5   # percent of account
    max_daily_risk: float = 2.0        # percent of account
    no_trade_windows: list[str] = ["FOMC", "NFP"]


class MarketContext(BaseModel):
    market_regime: str = "unknown"     # trending | ranging | unknown
    news_risk: str = "none_noted"
    account_balance: float
    open_positions: list = []


class GroundTruthPacket(BaseModel):
    version: str = "1.1"
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    instrument: str                    # e.g. "XAUUSD"
    session: str                       # e.g. "NY", "London", "Asia"
    timeframes: list[str]              # e.g. ["D1", "H4", "H1", "M15"]
    charts: dict[str, str]            # timeframe -> base64-encoded image
    risk_constraints: RiskConstraints
    context: MarketContext
    generated_by: str = "api"

    model_config = {"frozen": True}   # immutable after creation — see design rule #1
