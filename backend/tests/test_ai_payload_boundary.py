"""Proves the AI payload boundary: no PII, no row-level data, ever.

The fixture analytics result below has planted "leaks" — a customer name in a
product name field, an email-shaped string, a raw UUID rendered as a string —
positioned exactly where a careless payload builder would forward them. The
test asserts none of it survives into ``build_ai_payload``'s output.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, date, datetime

import pytest

from app.schemas.ai import AIPayload
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsResult,
    AnomalyReport,
    Breakdown,
    BreakdownItem,
    BusinessHealth,
    ComparisonMode,
    CustomerSegment,
    Granularity,
    KpiSet,
    MetricValue,
    PeriodInfo,
    ProductPerformance,
    ReturnsView,
    RfmSummary,
    RiskIndicator,
    RiskLevel,
    TimeSeries,
    TimeSeriesPoint,
)
from app.services.ai.payload import build_ai_payload

PLANTED_EMAIL = "leak.customer@example-secret.com"
PLANTED_NAME = "Jane Q. Confidential"
PLANTED_UUID = str(uuid.uuid4())
PLANTED_ORDER_REF = "SECRET-ORDER-99182"
PLANTED_CUSTOMER_REF = "CUST-LEAK-001"

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _metric(current: float, previous: float | None = None) -> MetricValue:
    delta_pct = None
    delta_abs = None
    if previous is not None and previous != 0:
        delta_abs = current - previous
        delta_pct = (current - previous) / abs(previous) * 100
    return MetricValue(current=current, previous=previous, delta_abs=delta_abs, delta_pct=delta_pct)


@pytest.fixture
def leaky_result() -> AnalyticsResult:
    """An AnalyticsResult with planted PII/row-level data in tempting spots.

    Product names, which are legitimately excluded from the AI payload, carry
    the planted name/email/ref values; this simulates what would leak if a
    future contributor accidentally included product-level detail or a
    customer-identifying field in a rollup.
    """
    kpis = KpiSet(
        revenue=_metric(10000.0, 9000.0),
        profit=_metric(1500.0, 1200.0),
        margin_pct=_metric(15.0, 13.3),
        orders=_metric(120, 100),
        aov=_metric(83.3, 90.0),
        units=_metric(500, 480),
        return_rate_pct=_metric(4.2, 3.1),
        customers=_metric(80, 75),
        new_customers=_metric(20, 15),
        repeat_customers=_metric(60, 60),
        repeat_rate_pct=_metric(75.0, 80.0),
        avg_discount_pct=_metric(12.0, 10.0),
    )

    timeseries = TimeSeries(
        granularity=Granularity.MONTH,
        moving_average_window=3,
        points=[
            TimeSeriesPoint(
                period="2024-01-01", revenue=4000, profit=500, margin_pct=12.5,
                orders=40, units=180, revenue_ma=4000, profit_ma=500, revenue_pop_pct=None,
            ),
            TimeSeriesPoint(
                period="2024-02-01", revenue=6000, profit=1000, margin_pct=16.7,
                orders=80, units=320, revenue_ma=5000, profit_ma=750, revenue_pop_pct=50.0,
            ),
        ],
    )

    breakdown_items = [
        BreakdownItem(
            key="East", label="East", revenue=6000, profit=900, margin_pct=15.0,
            orders=70, units=300, revenue_share_pct=60.0,
            previous_revenue=5000, revenue_delta_pct=20.0,
        ),
        BreakdownItem(
            key="West", label="West", revenue=4000, profit=600, margin_pct=15.0,
            orders=50, units=200, revenue_share_pct=40.0,
            previous_revenue=4000, revenue_delta_pct=0.0,
        ),
    ]

    breakdowns = {
        "region": Breakdown(dimension="region", items=breakdown_items),
        "category": Breakdown(dimension="category", items=breakdown_items),
        "sub_category": Breakdown(dimension="sub_category", items=[]),
        "segment": Breakdown(dimension="segment", items=breakdown_items),
    }

    # Planted leak: top products carry a customer-identifying name and a raw ref.
    top_products = [
        ProductPerformance(
            product_ref=PLANTED_CUSTOMER_REF, name=f"Gift for {PLANTED_NAME} <{PLANTED_EMAIL}>",
            category="Office Supplies", sub_category="Binders",
            revenue=2000, profit=400, margin_pct=20.0, units=50, orders=20,
        ),
    ]

    anomalies = AnomalyReport(
        granularity=Granularity.MONTH, points_analysed=2, contamination=0.05,
        anomalies=[], note=None,
    )

    rfm = RfmSummary(
        customers_scored=80, clusters=2,
        segments=[
            CustomerSegment(
                cluster_id=0, label="Champions",
                customer_count=20, customer_share_pct=25.0, revenue=5000,
                revenue_share_pct=50.0, avg_recency_days=10.0, avg_frequency=3.0,
                avg_monetary=250.0, avg_rfm_score=13.0,
            ),
        ],
        note=None,
    )

    returns = ReturnsView(
        returned_orders=5, total_orders=120, return_rate_pct=4.2, revenue_at_risk=800.0,
    )

    indicators = [
        RiskIndicator(
            key="margin_erosion", label="Margin erosion", level=RiskLevel.WATCH,
            value=2.5, threshold=2.0, unit="percent",
            description="Margin moved -2.5 pp from the start to the end of the period.",
            evidence={},
        ),
    ]
    health = BusinessHealth(score=78, grade="B", level=RiskLevel.WATCH, indicators=indicators,
                            headline="Healthy with a margin watch item.")

    return AnalyticsResult(
        period=PeriodInfo(
            start=date(2024, 1, 1), end=date(2024, 2, 29), days=60,
            comparison_start=date(2023, 11, 1), comparison_end=date(2023, 12, 30),
            comparison_mode=ComparisonMode.PREVIOUS_PERIOD,
        ),
        filters=AnalyticsFilters(),
        row_count=500,
        kpis=kpis,
        timeseries=timeseries,
        breakdowns=breakdowns,
        top_products=top_products,
        bottom_products=[],
        anomalies=anomalies,
        rfm=rfm,
        returns=returns,
        health=health,
        computed_at=datetime.now(UTC),
    )


def test_payload_excludes_planted_pii_and_identifiers(leaky_result: AnalyticsResult) -> None:
    payload = build_ai_payload(leaky_result, industry="Retail")
    serialised = json.dumps(payload.model_dump(mode="json"))

    assert PLANTED_EMAIL not in serialised
    assert PLANTED_NAME not in serialised
    assert PLANTED_UUID not in serialised
    assert PLANTED_ORDER_REF not in serialised
    assert PLANTED_CUSTOMER_REF not in serialised

    # No email-shaped or UUID-shaped strings anywhere in the payload, planted
    # or otherwise — this is a structural guarantee, not just a spot check.
    assert not _EMAIL_RE.search(serialised)
    assert not _UUID_RE.search(serialised)


def test_payload_excludes_product_level_detail(leaky_result: AnalyticsResult) -> None:
    """Product names/refs are row-level in spirit (an SKU can be tenant-identifying)
    and must never appear, even though category/sub-category rollups do."""
    payload = build_ai_payload(leaky_result)
    serialised = json.dumps(payload.model_dump(mode="json"))

    assert "product_ref" not in serialised
    assert "Gift for" not in serialised


def test_payload_excludes_organization_name(leaky_result: AnalyticsResult) -> None:
    payload = build_ai_payload(leaky_result, industry="Retail")
    serialised = json.dumps(payload.model_dump(mode="json"))
    assert "Acme" not in serialised
    # Industry is allowed through explicitly.
    assert payload.context.industry == "Retail"


def test_payload_schema_forbids_extra_fields(leaky_result: AnalyticsResult) -> None:
    """extra='forbid' means a leaky field addition fails fast at construction,
    not silently at serialization."""
    payload = build_ai_payload(leaky_result)
    dumped = payload.model_dump(mode="json")
    dumped["row_level_leak"] = {"customer_email": PLANTED_EMAIL}
    with pytest.raises(Exception):
        AIPayload.model_validate(dumped)


def test_payload_only_contains_aggregate_fields(leaky_result: AnalyticsResult) -> None:
    """Every numeric field in the payload must be an aggregate (share/avg/total),
    never a bare per-record value. Sanity-checks structure, not just content."""
    payload = build_ai_payload(leaky_result)

    for rollup in payload.segment_rollups + payload.category_performance:
        assert rollup.revenue_share_pct is not None
        assert 0 <= rollup.revenue_share_pct <= 100.001

    for segment in payload.customer_segments:
        assert segment.customer_count >= 1
        assert 0 <= segment.customer_share_pct <= 100.001

    assert payload.context.observation_count == 500
    assert payload.health_score == 78
