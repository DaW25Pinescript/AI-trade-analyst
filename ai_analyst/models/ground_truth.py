from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
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


class ScreenshotMetadata(BaseModel):
    """
    Typed evidence metadata for a single screenshot.
    Every screenshot in the Ground Truth Packet must have a corresponding metadata entry.
    Submissions with missing or malformed metadata are rejected before analysis.
    """
    timeframe: str                                     # e.g. "H4", "H1", "M15", "M5"
    lens: Literal["NONE", "ICT"] = "NONE"
    evidence_type: Literal["price_only", "indicator_overlay"] = "price_only"
    indicator_claims: Optional[list[str]] = None       # only for indicator_overlay
    indicator_source: Optional[str] = None             # only for indicator_overlay
    settings_locked: Optional[bool] = None             # only for indicator_overlay

    @model_validator(mode="after")
    def validate_overlay_fields(self) -> "ScreenshotMetadata":
        if self.evidence_type == "indicator_overlay":
            if self.lens == "NONE":
                raise ValueError(
                    "indicator_overlay evidence_type requires a non-NONE lens."
                )
            if not self.indicator_claims:
                raise ValueError(
                    "indicator_overlay evidence_type requires indicator_claims to be populated."
                )
        if self.evidence_type == "price_only" and self.lens != "NONE":
            raise ValueError(
                "price_only evidence_type must have lens=NONE."
            )
        return self


# ─── Allowed clean-chart timeframes (per architecture spec) ────────────────
ALLOWED_CLEAN_TIMEFRAMES: frozenset[str] = frozenset({"H4", "H1", "M15", "M5"})
OVERLAY_TIMEFRAME = "M15"
OVERLAY_LENS = "ICT"
MAX_SCREENSHOTS = 4


class GroundTruthPacket(BaseModel):
    version: str = "1.2"
    timestamp_utc: datetime = Field(default_factory=datetime.utcnow)
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_ticket_id: Optional[str] = None  # v2.0: originating app ticket ID for traceability
    instrument: str                    # e.g. "XAUUSD"
    session: str                       # e.g. "NY", "London", "Asia"
    timeframes: list[str]              # e.g. ["H4", "M15", "M5"]
    charts: dict[str, str]            # timeframe -> base64-encoded image (clean charts only)
    screenshot_metadata: list[ScreenshotMetadata]  # one entry per clean chart, ordered to match charts
    m15_overlay: Optional[str] = None              # base64-encoded 15M ICT overlay image (optional)
    m15_overlay_metadata: Optional[ScreenshotMetadata] = None  # required if m15_overlay is provided
    risk_constraints: RiskConstraints
    context: MarketContext
    generated_by: str = "api"

    model_config = {"frozen": True}   # immutable after creation — see design rule #1

    @model_validator(mode="after")
    def validate_screenshot_architecture(self) -> "GroundTruthPacket":
        """
        Enforces the lens-aware screenshot architecture constraints:
        - Max 4 screenshots total (3 clean + 1 overlay).
        - Clean charts must use allowed timeframes only.
        - Overlay slot is bound to M15 with lens=ICT only.
        - Metadata count must match clean chart count.
        - m15_overlay_metadata required when overlay is provided.
        - Rejects submissions with missing or malformed metadata.
        """
        clean_count = len(self.charts)
        overlay_count = 1 if self.m15_overlay else 0
        total = clean_count + overlay_count

        if total > MAX_SCREENSHOTS:
            raise ValueError(
                f"Maximum {MAX_SCREENSHOTS} screenshots allowed "
                f"(3 clean + 1 overlay). Got {total}."
            )

        # Validate clean chart timeframes
        for tf in self.charts:
            if tf not in ALLOWED_CLEAN_TIMEFRAMES:
                raise ValueError(
                    f"Clean chart timeframe '{tf}' is not allowed. "
                    f"Permitted: {sorted(ALLOWED_CLEAN_TIMEFRAMES)}."
                )

        # Metadata must accompany every clean chart
        if len(self.screenshot_metadata) != clean_count:
            raise ValueError(
                f"screenshot_metadata must have one entry per clean chart. "
                f"Expected {clean_count}, got {len(self.screenshot_metadata)}."
            )

        # All clean chart metadata must be price_only with lens=NONE
        for meta in self.screenshot_metadata:
            if meta.evidence_type != "price_only" or meta.lens != "NONE":
                raise ValueError(
                    f"Clean chart metadata for timeframe '{meta.timeframe}' must have "
                    f"evidence_type='price_only' and lens='NONE'."
                )

        # Overlay validation
        if self.m15_overlay:
            if not self.m15_overlay_metadata:
                raise ValueError(
                    "m15_overlay_metadata is required when m15_overlay is provided."
                )
            if self.m15_overlay_metadata.timeframe != OVERLAY_TIMEFRAME:
                raise ValueError(
                    f"Overlay metadata must have timeframe='{OVERLAY_TIMEFRAME}'. "
                    f"Got '{self.m15_overlay_metadata.timeframe}'."
                )
            if self.m15_overlay_metadata.lens != OVERLAY_LENS:
                raise ValueError(
                    f"Overlay metadata must have lens='{OVERLAY_LENS}'. "
                    f"Got '{self.m15_overlay_metadata.lens}'."
                )
            if self.m15_overlay_metadata.evidence_type != "indicator_overlay":
                raise ValueError(
                    "Overlay metadata must have evidence_type='indicator_overlay'."
                )
            # The M15 clean chart must be present if the overlay is provided
            if OVERLAY_TIMEFRAME not in self.charts:
                raise ValueError(
                    f"The {OVERLAY_TIMEFRAME} clean chart must be provided "
                    f"when the {OVERLAY_TIMEFRAME} overlay is submitted."
                )

        if not self.m15_overlay and self.m15_overlay_metadata is not None:
            raise ValueError(
                "m15_overlay_metadata was provided but m15_overlay image is missing."
            )

        return self
