import pytest

from ai_analyst.models.ground_truth import (
    GroundTruthPacket,
    MarketContext,
    RiskConstraints,
    ScreenshotMetadata,
)
from ai_analyst.models.lens_config import LensConfig


@pytest.fixture
def sample_ground_truth() -> GroundTruthPacket:
    return GroundTruthPacket(
        instrument="XAUUSD",
        session="NY",
        timeframes=["H4", "M15"],
        charts={
            "H4": "base64-h4",
            "M15": "base64-m15",
        },
        screenshot_metadata=[
            ScreenshotMetadata(timeframe="H4", lens="NONE", evidence_type="price_only"),
            ScreenshotMetadata(timeframe="M15", lens="NONE", evidence_type="price_only"),
        ],
        risk_constraints=RiskConstraints(),
        context=MarketContext(account_balance=10000.0),
    )


@pytest.fixture
def sample_ground_truth_with_overlay(sample_ground_truth: GroundTruthPacket) -> GroundTruthPacket:
    return sample_ground_truth.model_copy(
        update={
            "m15_overlay": "base64-overlay",
            "m15_overlay_metadata": ScreenshotMetadata(
                timeframe="M15",
                lens="ICT",
                evidence_type="indicator_overlay",
                indicator_claims=["Fair value gap boundary from ICT tool"],
                indicator_source="TradingView ICT tool",
                settings_locked=True,
            ),
        }
    )


@pytest.fixture
def sample_lens_config() -> LensConfig:
    return LensConfig()
