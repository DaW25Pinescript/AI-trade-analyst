"""Reflect aggregation API response models (PR-REFLECT-1)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from ai_analyst.api.models.ops import ResponseMeta

ArtifactState = Literal["present", "missing", "malformed"]


class ScanBounds(BaseModel):
    max_runs: int
    inspected_dirs: int
    valid_runs: int
    skipped_runs: int


class PersonaStats(BaseModel):
    persona: str
    participation_count: int
    skip_count: int
    fail_count: int
    participation_rate: float
    override_count: int
    override_rate: Optional[float] = None
    stance_alignment: Optional[float] = None
    avg_confidence: Optional[float] = None
    flagged: bool = False


class PersonaPerformanceResponse(ResponseMeta):
    threshold: int = 10
    threshold_met: bool
    scan_bounds: ScanBounds
    stats: list[PersonaStats]


class VerdictCount(BaseModel):
    verdict: str
    count: int


class PatternBucket(BaseModel):
    instrument: str
    session: str
    run_count: int
    threshold_met: bool
    verdict_distribution: list[VerdictCount]
    no_trade_rate: Optional[float] = None
    flagged: bool = False


class PatternSummaryResponse(ResponseMeta):
    threshold: int = 10
    scan_bounds: ScanBounds
    buckets: list[PatternBucket]


class ArtifactStatus(BaseModel):
    run_record: ArtifactState
    usage_jsonl: ArtifactState
    usage_json: ArtifactState


class RunBundleResponse(ResponseMeta):
    run_id: str
    artifact_status: ArtifactStatus
    run_record: dict = Field(default_factory=dict)
    usage_summary: Optional[dict] = None
    usage_jsonl: list[dict] = Field(default_factory=list)
