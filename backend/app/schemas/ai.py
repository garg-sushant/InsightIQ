"""AI layer contract.

``AIPayload`` is the *only* structure that crosses from analytics into the LLM
boundary. It is defined with ``extra="forbid"`` and composed exclusively of
scalars and aggregate rollups — there is no field on it that can carry a
row-level record, a person's name, an email, or an internal identifier.

See ``app.services.ai.payload.build_ai_payload`` for the single construction
site, and ``tests/test_ai_payload.py`` for the enforcement tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.ai_insight import InsightType
from app.schemas.common import APIModel

#: Bumped whenever the payload shape changes in a way prompts must know about.
AI_PAYLOAD_VERSION = "1.0"


class PayloadMetric(APIModel):
    """One KPI, pre-formatted so the model never has to do arithmetic."""

    key: str
    label: str
    value: float
    unit: Literal["currency", "percent", "count"]
    previous_value: float | None = None
    delta_pct: float | None = None
    direction: Literal["up", "down", "flat"] = "flat"
    #: True when movement in this metric is good for the business.
    favourable: bool | None = None


class PayloadSegmentRollup(APIModel):
    """An aggregate slice: never fewer than the whole group, never a single row."""

    dimension: str
    key: str
    revenue: float
    revenue_share_pct: float
    margin_pct: float
    revenue_delta_pct: float | None = None


class PayloadTrend(APIModel):
    """A described trend, not a raw series."""

    metric: str
    granularity: str
    periods: int
    direction: Literal["rising", "falling", "flat", "volatile"]
    change_pct: float
    volatility_pct: float
    best_period: str | None = None
    worst_period: str | None = None
    description: str


class PayloadAnomaly(APIModel):
    period: str
    metric: str
    direction: Literal["spike", "drop"]
    deviation_pct: float
    severity: str
    description: str


class PayloadRisk(APIModel):
    key: str
    label: str
    level: str
    value: float
    threshold: float
    unit: str
    description: str


class PayloadSegmentProfile(APIModel):
    """Customer-cluster rollup. Counts and averages only — never a customer."""

    label: str
    customer_count: int
    customer_share_pct: float
    revenue_share_pct: float
    avg_recency_days: float
    avg_frequency: float
    avg_monetary: float


class PayloadContext(APIModel):
    period_start: str
    period_end: str
    period_days: int
    comparison_start: str | None = None
    comparison_end: str | None = None
    comparison_mode: str
    granularity: str
    #: Industry label only. The organization *name* is intentionally excluded —
    #: it is tenant-identifying and the narrative does not need it.
    industry: str | None = None
    currency: str = "USD"
    #: Order-line count, so the model can caveat conclusions on thin data.
    observation_count: int


class AIPayload(APIModel):
    """The complete, sanitised input to any AI provider call."""

    payload_version: str = AI_PAYLOAD_VERSION
    context: PayloadContext
    metrics: list[PayloadMetric]
    segment_rollups: list[PayloadSegmentRollup]
    trends: list[PayloadTrend]
    anomalies: list[PayloadAnomaly]
    risks: list[PayloadRisk]
    customer_segments: list[PayloadSegmentProfile]
    #: Product *category/sub-category* performance. Individual product names are
    #: excluded: an SKU name can be tenant-identifying and is not needed to
    #: explain a movement.
    category_performance: list[PayloadSegmentRollup]
    health_score: int
    health_grade: str
    concentration: dict[str, float] = Field(
        default_factory=dict,
        description="Aggregate concentration ratios, e.g. top-10 customer revenue share.",
    )


class RecommendationItem(APIModel):
    title: str
    rationale: str
    priority: Literal["high", "medium", "low"]
    impact: Literal["high", "medium", "low"]
    effort: Literal["high", "medium", "low"]
    owner: str | None = None
    metric_to_watch: str | None = None


class RootCauseItem(APIModel):
    metric: str
    movement: str
    hypothesis: str
    supporting_evidence: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class InsightOut(APIModel):
    id: uuid.UUID
    analysis_run_id: uuid.UUID
    insight_type: InsightType
    content: str
    structured: dict[str, object] | None = None
    provider: str
    model: str
    prompt_version: str
    is_fallback: bool
    latency_ms: int | None = None
    created_at: datetime


class InsightBundle(APIModel):
    """All four narrative sections for one analysis run."""

    analysis_run_id: uuid.UUID
    provider: str
    model: str
    #: True when any section came from the mock/fallback path. The dashboard
    #: renders a prominent badge when this is set.
    degraded: bool
    degraded_reason: str | None = None
    executive_summary: InsightOut | None = None
    root_cause: InsightOut | None = None
    recommendations: InsightOut | None = None
    risks: InsightOut | None = None
    generated_at: datetime


class GenerateInsightsRequest(APIModel):
    analysis_run_id: uuid.UUID
    #: Force a regeneration even if cached insights exist for this run.
    refresh: bool = False


class AIStatusOut(APIModel):
    provider: str
    model: str
    configured: bool
    #: True when running on MockProvider — the UI labels output as placeholder.
    is_mock: bool
    message: str


__all__ = [
    "AI_PAYLOAD_VERSION",
    "AIPayload",
    "AIStatusOut",
    "GenerateInsightsRequest",
    "InsightBundle",
    "InsightOut",
    "PayloadAnomaly",
    "PayloadContext",
    "PayloadMetric",
    "PayloadRisk",
    "PayloadSegmentProfile",
    "PayloadSegmentRollup",
    "PayloadTrend",
    "RecommendationItem",
    "RootCauseItem",
]
