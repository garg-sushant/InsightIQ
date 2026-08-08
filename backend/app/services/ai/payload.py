"""THE privacy boundary between business data and the LLM.

``build_ai_payload`` is the only function in this codebase permitted to turn
analytics output into something an AI provider sees. It emits aggregates only:
KPIs, deltas, segment rollups, anomaly flags, trend descriptors and risk levels.

Structurally excluded, by construction rather than by filtering:

* row-level records of any kind (orders, customers, products, returns),
* names, emails, addresses, postal codes, phone numbers,
* database identifiers (UUIDs, order refs, customer refs, product refs),
* the organization's own name,
* individual product names (an SKU can identify a tenant and is never needed
  to explain why a number moved — category rollups carry that signal).

The output type is :class:`~app.schemas.ai.AIPayload`, which is declared with
``extra="forbid"``; adding a leaky field therefore requires a deliberate schema
change, not an accidental dict key. ``tests/test_ai_payload.py`` asserts all of
the above against a fixture containing planted PII.
"""

from __future__ import annotations

from app.schemas.ai import (
    AIPayload,
    PayloadAnomaly,
    PayloadContext,
    PayloadMetric,
    PayloadRisk,
    PayloadSegmentProfile,
    PayloadSegmentRollup,
    PayloadTrend,
)
from app.schemas.analytics import (
    AnalyticsResult,
    KpiSet,
    MetricValue,
    TimeSeries,
)

#: (attribute, label, unit, higher_is_better)
_METRIC_SPECS: tuple[tuple[str, str, str, bool], ...] = (
    ("revenue", "Revenue", "currency", True),
    ("profit", "Profit", "currency", True),
    ("margin_pct", "Profit margin", "percent", True),
    ("orders", "Orders", "count", True),
    ("aov", "Average order value", "currency", True),
    ("units", "Units sold", "count", True),
    ("return_rate_pct", "Return rate", "percent", False),
    ("customers", "Active customers", "count", True),
    ("new_customers", "New customers", "count", True),
    ("repeat_customers", "Repeat customers", "count", True),
    ("repeat_rate_pct", "Repeat-purchase rate", "percent", True),
    ("avg_discount_pct", "Average discount", "percent", False),
)

#: Dimensions safe to roll up. Note the absence of anything customer- or
#: product-identifying; these are categorical business dimensions only.
_SAFE_ROLLUP_DIMENSIONS = ("region", "segment")
_CATEGORY_DIMENSIONS = ("category", "sub_category")

#: Caps keep the prompt bounded and cheap regardless of dataset breadth.
MAX_ROLLUPS_PER_DIMENSION = 8
MAX_ANOMALIES = 10
MAX_RISKS = 10


def _direction(delta_pct: float | None) -> str:
    if delta_pct is None or abs(delta_pct) < 0.5:
        return "flat"
    return "up" if delta_pct > 0 else "down"


def _favourable(delta_pct: float | None, higher_is_better: bool) -> bool | None:
    if delta_pct is None or abs(delta_pct) < 0.5:
        return None
    improving = delta_pct > 0
    return improving is higher_is_better


def _metric(key: str, label: str, unit: str, higher_is_better: bool, value: MetricValue):
    return PayloadMetric(
        key=key,
        label=label,
        value=value.current,
        unit=unit,  # type: ignore[arg-type]
        previous_value=value.previous,
        delta_pct=value.delta_pct,
        direction=_direction(value.delta_pct),  # type: ignore[arg-type]
        favourable=_favourable(value.delta_pct, higher_is_better),
    )


def _build_metrics(kpis: KpiSet) -> list[PayloadMetric]:
    return [
        _metric(key, label, unit, higher_is_better, getattr(kpis, key))
        for key, label, unit, higher_is_better in _METRIC_SPECS
    ]


def _describe_trend(series: TimeSeries, metric: str) -> PayloadTrend | None:
    """Reduce a raw series to a *description*.

    The model receives "revenue rose 18% over 12 months, volatile, weakest
    period 2024-07" — never the underlying points. That keeps the payload small
    and stops the model from attempting its own arithmetic on the series.
    """
    points = series.points
    if len(points) < 2:
        return None

    values = [getattr(point, metric) for point in points]
    first, last = values[0], values[-1]
    change_pct = ((last - first) / abs(first) * 100) if first else 0.0

    mean = sum(values) / len(values)
    if mean:
        spread = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
        volatility = abs(spread / mean * 100)
    else:
        volatility = 0.0

    if volatility > 45:
        direction = "volatile"
    elif change_pct > 5:
        direction = "rising"
    elif change_pct < -5:
        direction = "falling"
    else:
        direction = "flat"

    best = max(points, key=lambda p: getattr(p, metric))
    worst = min(points, key=lambda p: getattr(p, metric))
    label = metric.replace("_pct", "").replace("_", " ")

    return PayloadTrend(
        metric=metric,
        granularity=series.granularity.value,
        periods=len(points),
        direction=direction,  # type: ignore[arg-type]
        change_pct=round(change_pct, 2),
        volatility_pct=round(volatility, 2),
        best_period=best.period,
        worst_period=worst.period,
        description=(
            f"{label.capitalize()} is {direction} across {len(points)} "
            f"{series.granularity.value} periods, a {change_pct:+.1f}% change from "
            f"first to last period, with {volatility:.0f}% relative volatility. "
            f"Strongest period {best.period}, weakest {worst.period}."
        ),
    )


def _rollups(result: AnalyticsResult, dimensions: tuple[str, ...]) -> list[PayloadSegmentRollup]:
    rollups: list[PayloadSegmentRollup] = []
    for dimension in dimensions:
        breakdown = result.breakdowns.get(dimension)
        if breakdown is None:
            continue
        for item in breakdown.items[:MAX_ROLLUPS_PER_DIMENSION]:
            rollups.append(
                PayloadSegmentRollup(
                    dimension=dimension,
                    key=item.key,
                    revenue=item.revenue,
                    revenue_share_pct=item.revenue_share_pct,
                    margin_pct=item.margin_pct,
                    revenue_delta_pct=item.revenue_delta_pct,
                )
            )
    return rollups


def build_ai_payload(result: AnalyticsResult, *, industry: str | None = None) -> AIPayload:
    """Convert a computed analysis into the sanitised AI input.

    This is the single path from analytics to the AI layer. Providers accept an
    :class:`AIPayload` and nothing else.

    Args:
        result: The deterministic analytics output.
        industry: Optional industry label for context. The organization *name*
            is intentionally not accepted — it is tenant-identifying.
    """
    trends = [
        trend
        for trend in (
            _describe_trend(result.timeseries, "revenue"),
            _describe_trend(result.timeseries, "profit"),
            _describe_trend(result.timeseries, "margin_pct"),
        )
        if trend is not None
    ]

    anomalies = [
        PayloadAnomaly(
            period=anomaly.period,
            metric=anomaly.metric,
            direction=anomaly.direction,
            deviation_pct=anomaly.deviation_pct,
            severity=anomaly.severity.value,
            description=anomaly.description,
        )
        for anomaly in result.anomalies.anomalies[:MAX_ANOMALIES]
    ]

    risks = [
        PayloadRisk(
            key=indicator.key,
            label=indicator.label,
            level=indicator.level.value,
            value=indicator.value,
            threshold=indicator.threshold,
            unit=indicator.unit,
            description=indicator.description,
        )
        for indicator in result.health.indicators[:MAX_RISKS]
    ]

    customer_segments = [
        PayloadSegmentProfile(
            label=segment.label,
            customer_count=segment.customer_count,
            customer_share_pct=segment.customer_share_pct,
            revenue_share_pct=segment.revenue_share_pct,
            avg_recency_days=segment.avg_recency_days,
            avg_frequency=segment.avg_frequency,
            avg_monetary=segment.avg_monetary,
        )
        for segment in result.rfm.segments
    ]

    concentration = {
        indicator.key: indicator.value
        for indicator in result.health.indicators
        if indicator.key in {"customer_concentration", "product_concentration"}
    }
    concentration["returns_revenue_at_risk"] = result.returns.revenue_at_risk

    return AIPayload(
        context=PayloadContext(
            period_start=result.period.start.isoformat(),
            period_end=result.period.end.isoformat(),
            period_days=result.period.days,
            comparison_start=(
                result.period.comparison_start.isoformat()
                if result.period.comparison_start
                else None
            ),
            comparison_end=(
                result.period.comparison_end.isoformat()
                if result.period.comparison_end
                else None
            ),
            comparison_mode=result.period.comparison_mode.value,
            granularity=result.timeseries.granularity.value,
            industry=industry,
            observation_count=result.row_count,
        ),
        metrics=_build_metrics(result.kpis),
        segment_rollups=_rollups(result, _SAFE_ROLLUP_DIMENSIONS),
        category_performance=_rollups(result, _CATEGORY_DIMENSIONS),
        trends=trends,
        anomalies=anomalies,
        risks=risks,
        customer_segments=customer_segments,
        health_score=result.health.score,
        health_grade=result.health.grade,
        concentration=concentration,
    )


__all__ = [
    "MAX_ANOMALIES",
    "MAX_RISKS",
    "MAX_ROLLUPS_PER_DIMENSION",
    "build_ai_payload",
]
