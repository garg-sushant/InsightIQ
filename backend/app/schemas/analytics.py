"""Analytics contract.

Every number in this module is produced by SQL/Pandas in
``app.services.analytics``. Nothing here is ever written or adjusted by the AI
layer — the LLM only reads these values and writes prose about them.

Money is exposed as ``float`` rounded to 2dp at the boundary (charts and JSON
want numbers, not strings); it is *stored and summed* as ``Decimal`` throughout
the engine, so the rounding happens exactly once, at the edge.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from app.models.analysis_run import AnalysisStatus
from app.schemas.common import APIModel


class Granularity(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"


class DimensionKey(StrEnum):
    REGION = "region"
    CATEGORY = "category"
    SUB_CATEGORY = "sub_category"
    SEGMENT = "segment"
    STATE = "state"
    SHIP_MODE = "ship_mode"


class ComparisonMode(StrEnum):
    #: Immediately preceding window of identical length.
    PREVIOUS_PERIOD = "previous_period"
    #: Same window, one year earlier.
    PREVIOUS_YEAR = "previous_year"
    NONE = "none"


class AnalyticsFilters(APIModel):
    """Global dashboard filters. Every chart on the page is driven by one of these."""

    date_from: date | None = None
    date_to: date | None = None
    regions: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    sub_categories: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)
    granularity: Granularity = Granularity.MONTH
    comparison: ComparisonMode = ComparisonMode.PREVIOUS_PERIOD
    top_n: int = Field(default=10, ge=1, le=50)


class MetricValue(APIModel):
    """A KPI with its comparison-period counterpart and both deltas."""

    current: float
    previous: float | None = None
    delta_abs: float | None = None
    delta_pct: float | None = Field(
        default=None,
        description="Percent change vs the comparison period. Null when previous is 0 or absent.",
    )


class KpiSet(APIModel):
    revenue: MetricValue
    profit: MetricValue
    margin_pct: MetricValue
    orders: MetricValue
    aov: MetricValue = Field(description="Average order value = revenue / distinct orders.")
    units: MetricValue
    return_rate_pct: MetricValue
    customers: MetricValue
    new_customers: MetricValue
    repeat_customers: MetricValue
    repeat_rate_pct: MetricValue
    avg_discount_pct: MetricValue


class TimeSeriesPoint(APIModel):
    period: str = Field(description="ISO date of the bucket start, e.g. '2024-03-01'.")
    revenue: float
    profit: float
    margin_pct: float
    orders: int
    units: int
    revenue_ma: float | None = Field(
        default=None, description="Centred-trailing moving average of revenue."
    )
    profit_ma: float | None = None
    revenue_pop_pct: float | None = Field(
        default=None, description="Period-over-period revenue change, percent."
    )


class TimeSeries(APIModel):
    granularity: Granularity
    moving_average_window: int
    points: list[TimeSeriesPoint]


class BreakdownItem(APIModel):
    key: str
    label: str
    revenue: float
    profit: float
    margin_pct: float
    orders: int
    units: int
    revenue_share_pct: float
    previous_revenue: float | None = None
    revenue_delta_pct: float | None = None


class Breakdown(APIModel):
    dimension: str
    items: list[BreakdownItem]


class ProductPerformance(APIModel):
    product_ref: str
    name: str
    category: str | None = None
    sub_category: str | None = None
    revenue: float
    profit: float
    margin_pct: float
    units: int
    orders: int


class AnomalySeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnomalyPoint(APIModel):
    period: str
    metric: Literal["revenue", "margin_pct", "profit"]
    value: float
    expected: float
    deviation_pct: float
    z_score: float | None = None
    severity: AnomalySeverity
    direction: Literal["spike", "drop"]
    method: Literal["isolation_forest", "zscore_rule"]
    description: str


class AnomalyReport(APIModel):
    granularity: Granularity
    points_analysed: int
    contamination: float
    anomalies: list[AnomalyPoint]
    #: Populated when there were too few points for Isolation Forest to be
    #: meaningful; the rule-based detector still runs.
    note: str | None = None


class CustomerSegment(APIModel):
    """A K-means cluster over RFM scores, with a business-readable label."""

    cluster_id: int
    label: str
    customer_count: int
    customer_share_pct: float
    revenue: float
    revenue_share_pct: float
    avg_recency_days: float
    avg_frequency: float
    avg_monetary: float
    avg_rfm_score: float


class RfmSummary(APIModel):
    customers_scored: int
    clusters: int
    segments: list[CustomerSegment]
    note: str | None = None


class RiskLevel(StrEnum):
    OK = "ok"
    WATCH = "watch"
    ELEVATED = "elevated"
    CRITICAL = "critical"


class RiskIndicator(APIModel):
    key: str
    label: str
    level: RiskLevel
    value: float
    threshold: float
    unit: Literal["percent", "ratio", "count", "currency"]
    description: str
    evidence: dict[str, float] = Field(default_factory=dict)


class BusinessHealth(APIModel):
    """0-100 composite. Deterministic — a weighted blend of the risk indicators."""

    score: int = Field(ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"]
    level: RiskLevel
    indicators: list[RiskIndicator]
    headline: str


class PeriodInfo(APIModel):
    start: date
    end: date
    days: int
    comparison_start: date | None = None
    comparison_end: date | None = None
    comparison_mode: ComparisonMode


class ReturnsView(APIModel):
    returned_orders: int
    total_orders: int
    return_rate_pct: float
    revenue_at_risk: float = Field(
        description="Revenue on returned orders, in the selected period."
    )
    by_category: list[BreakdownItem] = Field(default_factory=list)
    by_region: list[BreakdownItem] = Field(default_factory=list)
    trend: list[TimeSeriesPoint] = Field(default_factory=list)


class AnalyticsResult(APIModel):
    """The complete, deterministic analytics payload for one filter set."""

    period: PeriodInfo
    filters: AnalyticsFilters
    row_count: int = Field(description="Order lines included after filtering.")
    kpis: KpiSet
    timeseries: TimeSeries
    breakdowns: dict[str, Breakdown] = Field(
        description="Keyed by DimensionKey, e.g. 'region', 'category'."
    )
    top_products: list[ProductPerformance]
    bottom_products: list[ProductPerformance]
    anomalies: AnomalyReport
    rfm: RfmSummary
    returns: ReturnsView
    health: BusinessHealth
    computed_at: datetime


class AnalysisRunOut(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    status: AnalysisStatus
    period_start: date
    period_end: date
    comparison_start: date | None = None
    comparison_end: date | None = None
    source_row_count: int
    duration_ms: int | None = None
    created_at: datetime
    created_by_user_id: uuid.UUID | None = None
    error_message: str | None = None


class AnalysisRunDetailOut(AnalysisRunOut):
    result: AnalyticsResult | None = None


class FilterOptionsOut(APIModel):
    """Distinct dimension values present in the tenant's data, for filter menus."""

    regions: list[str]
    categories: list[str]
    sub_categories: list[str]
    segments: list[str]
    date_min: date | None = None
    date_max: date | None = None


__all__ = [
    "AnalysisRunDetailOut",
    "AnalysisRunOut",
    "AnalyticsFilters",
    "AnalyticsResult",
    "AnomalyPoint",
    "AnomalyReport",
    "AnomalySeverity",
    "Breakdown",
    "BreakdownItem",
    "BusinessHealth",
    "ComparisonMode",
    "CustomerSegment",
    "DimensionKey",
    "FilterOptionsOut",
    "Granularity",
    "KpiSet",
    "MetricValue",
    "PeriodInfo",
    "ProductPerformance",
    "ReturnsView",
    "RfmSummary",
    "RiskIndicator",
    "RiskLevel",
    "TimeSeries",
    "TimeSeriesPoint",
]
