"""Risk indicators and the composite business-health score.

Every threshold is an explicit constant with a stated rationale, and the score
is a deterministic weighted sum. Nothing here is learned, sampled or generated
— the AI layer explains this score, it never produces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from app.schemas.analytics import (
    BusinessHealth,
    RiskIndicator,
    RiskLevel,
    TimeSeries,
)
from app.services.analytics.breakdowns import revenue_concentration, top_decile_customer_share
from app.services.analytics.kpis import CoreMetrics
from app.services.analytics.numeric import ZERO, rate


@dataclass(frozen=True)
class Threshold:
    """Escalation ladder for one indicator.

    ``higher_is_worse`` flips the comparison for indicators such as repeat-rate
    decline, where a *falling* number is the problem.
    """

    watch: float
    elevated: float
    critical: float
    higher_is_worse: bool = True

    def level_for(self, value: float) -> RiskLevel:
        if self.higher_is_worse:
            if value >= self.critical:
                return RiskLevel.CRITICAL
            if value >= self.elevated:
                return RiskLevel.ELEVATED
            if value >= self.watch:
                return RiskLevel.WATCH
        else:
            if value <= self.critical:
                return RiskLevel.CRITICAL
            if value <= self.elevated:
                return RiskLevel.ELEVATED
            if value <= self.watch:
                return RiskLevel.WATCH
        return RiskLevel.OK


# --- Thresholds -------------------------------------------------------------
# Margin erosion: percentage points of margin lost across the period.
MARGIN_EROSION = Threshold(watch=2.0, elevated=5.0, critical=10.0)
# Revenue concentration: share of revenue from the top decile of customers.
CUSTOMER_CONCENTRATION = Threshold(watch=50.0, elevated=65.0, critical=80.0)
# Revenue concentration: share of revenue from the ten largest products.
PRODUCT_CONCENTRATION = Threshold(watch=30.0, elevated=45.0, critical=60.0)
# Return rate increase in percentage points versus the comparison period.
RETURN_RATE_RISE = Threshold(watch=1.0, elevated=3.0, critical=5.0)
# Repeat-purchase rate change in percentage points; falling is bad.
REPEAT_RATE_DECLINE = Threshold(
    watch=-2.0, elevated=-5.0, critical=-10.0, higher_is_worse=False
)
# Average line discount.
DISCOUNT_DEPENDENCY = Threshold(watch=15.0, elevated=25.0, critical=35.0)
# Share of revenue coming from loss-making lines.
LOSS_MAKING_REVENUE = Threshold(watch=10.0, elevated=20.0, critical=30.0)

#: Penalty applied to the 100-point health score per indicator level, scaled by
#: each indicator's weight.
_LEVEL_PENALTY: dict[RiskLevel, float] = {
    RiskLevel.OK: 0.0,
    RiskLevel.WATCH: 4.0,
    RiskLevel.ELEVATED: 9.0,
    RiskLevel.CRITICAL: 16.0,
}

#: Relative importance. Profitability outranks concentration, which outranks
#: the softer behavioural signals.
_WEIGHTS: dict[str, float] = {
    "margin_erosion": 1.4,
    "loss_making_revenue": 1.3,
    "return_rate_rise": 1.1,
    "customer_concentration": 1.0,
    "repeat_rate_decline": 1.0,
    "discount_dependency": 0.9,
    "product_concentration": 0.8,
}


def _margin_trend_pp(timeseries: TimeSeries) -> float:
    """Margin percentage points lost from the first third to the last third.

    Thirds rather than first-vs-last point: a single freak period should not
    declare an erosion crisis.
    """
    points = timeseries.points
    if len(points) < 3:
        return 0.0
    third = max(1, len(points) // 3)
    opening = sum(p.margin_pct for p in points[:third]) / third
    closing = sum(p.margin_pct for p in points[-third:]) / third
    return closing - opening


def build_risk_indicators(
    *,
    frame: pd.DataFrame,
    current: CoreMetrics,
    previous: CoreMetrics | None,
    timeseries: TimeSeries,
) -> list[RiskIndicator]:
    indicators: list[RiskIndicator] = []

    # 1. Margin erosion -----------------------------------------------------
    margin_change = _margin_trend_pp(timeseries)
    erosion = -margin_change  # positive number = margin lost
    indicators.append(
        RiskIndicator(
            key="margin_erosion",
            label="Margin erosion",
            level=MARGIN_EROSION.level_for(erosion),
            value=round(erosion, 2),
            threshold=MARGIN_EROSION.watch,
            unit="percent",
            description=(
                f"Margin moved {margin_change:+.1f} pp from the start to the end of "
                "the period (comparing the first and last thirds of the trend)."
            ),
            evidence={"margin_change_pp": round(margin_change, 2)},
        )
    )

    # 2. Loss-making revenue ------------------------------------------------
    loss_share = 0.0
    if current.revenue != ZERO:
        loss_share = float(current.negative_margin_revenue / current.revenue * 100)
    indicators.append(
        RiskIndicator(
            key="loss_making_revenue",
            label="Revenue from loss-making sales",
            level=LOSS_MAKING_REVENUE.level_for(loss_share),
            value=round(loss_share, 2),
            threshold=LOSS_MAKING_REVENUE.watch,
            unit="percent",
            description=(
                f"{loss_share:.1f}% of revenue comes from order lines that lost money."
            ),
            evidence={"loss_making_revenue": float(current.negative_margin_revenue)},
        )
    )

    # 3. Return-rate rise ---------------------------------------------------
    return_rise = 0.0
    if previous is not None and current.return_rate_pct is not None:
        previous_rate = previous.return_rate_pct or ZERO
        return_rise = float(current.return_rate_pct - previous_rate)
    indicators.append(
        RiskIndicator(
            key="return_rate_rise",
            label="Rising return rate",
            level=RETURN_RATE_RISE.level_for(return_rise),
            value=round(return_rise, 2),
            threshold=RETURN_RATE_RISE.watch,
            unit="percent",
            description=(
                f"Return rate moved {return_rise:+.1f} pp versus the comparison period "
                f"(now {rate(current.return_rate_pct or ZERO):.1f}%)."
            ),
            evidence={
                "current_return_rate_pct": rate(current.return_rate_pct or ZERO),
                "returned_orders": float(current.returned_orders),
            },
        )
    )

    # 4. Customer concentration --------------------------------------------
    customer_share = float(top_decile_customer_share(frame))
    indicators.append(
        RiskIndicator(
            key="customer_concentration",
            label="Customer revenue concentration",
            level=CUSTOMER_CONCENTRATION.level_for(customer_share),
            value=round(customer_share, 2),
            threshold=CUSTOMER_CONCENTRATION.watch,
            unit="percent",
            description=(
                f"The top 10% of customers account for {customer_share:.1f}% of revenue."
            ),
            evidence={"active_customers": float(current.customers)},
        )
    )

    # 5. Repeat-rate decline ------------------------------------------------
    repeat_change = 0.0
    if previous is not None and current.repeat_rate_pct is not None:
        repeat_change = float(current.repeat_rate_pct - (previous.repeat_rate_pct or ZERO))
    indicators.append(
        RiskIndicator(
            key="repeat_rate_decline",
            label="Repeat-purchase rate",
            level=REPEAT_RATE_DECLINE.level_for(repeat_change),
            value=round(repeat_change, 2),
            threshold=REPEAT_RATE_DECLINE.watch,
            unit="percent",
            description=(
                f"Repeat-customer share moved {repeat_change:+.1f} pp versus the "
                f"comparison period (now {rate(current.repeat_rate_pct or ZERO):.1f}%)."
            ),
            evidence={
                "repeat_customers": float(current.repeat_customers),
                "new_customers": float(current.new_customers),
            },
        )
    )

    # 6. Discount dependency ------------------------------------------------
    discount = rate(current.avg_discount_pct or ZERO)
    indicators.append(
        RiskIndicator(
            key="discount_dependency",
            label="Discount dependency",
            level=DISCOUNT_DEPENDENCY.level_for(discount),
            value=discount,
            threshold=DISCOUNT_DEPENDENCY.watch,
            unit="percent",
            description=f"Average discount across order lines is {discount:.1f}%.",
            evidence={},
        )
    )

    # 7. Product concentration ---------------------------------------------
    product_share = float(revenue_concentration(frame, "product_id", top=10))
    indicators.append(
        RiskIndicator(
            key="product_concentration",
            label="Product revenue concentration",
            level=PRODUCT_CONCENTRATION.level_for(product_share),
            value=round(product_share, 2),
            threshold=PRODUCT_CONCENTRATION.watch,
            unit="percent",
            description=(
                f"The ten largest products account for {product_share:.1f}% of revenue."
            ),
            evidence={},
        )
    )

    return indicators


def build_business_health(indicators: list[RiskIndicator]) -> BusinessHealth:
    """Weighted 0-100 score. Fully deterministic."""
    penalty = 0.0
    weight_total = 0.0
    for indicator in indicators:
        weight = _WEIGHTS.get(indicator.key, 1.0)
        penalty += _LEVEL_PENALTY[indicator.level] * weight
        weight_total += weight

    # Normalise so the ladder does not depend on how many indicators exist.
    normalised = penalty / weight_total * len(indicators) if weight_total else 0.0
    score = int(max(0, min(100, round(100 - normalised))))

    if score >= 85:
        grade, level = "A", RiskLevel.OK
    elif score >= 70:
        grade, level = "B", RiskLevel.WATCH
    elif score >= 55:
        grade, level = "C", RiskLevel.WATCH
    elif score >= 40:
        grade, level = "D", RiskLevel.ELEVATED
    else:
        grade, level = "F", RiskLevel.CRITICAL

    flagged = [i for i in indicators if i.level is not RiskLevel.OK]
    critical = [i for i in indicators if i.level is RiskLevel.CRITICAL]

    if not flagged:
        headline = "All monitored risk indicators are within healthy thresholds."
    elif critical:
        headline = (
            f"{len(critical)} indicator(s) at critical level: "
            + ", ".join(i.label.lower() for i in critical[:3])
            + "."
        )
    else:
        headline = (
            f"{len(flagged)} indicator(s) need attention: "
            + ", ".join(i.label.lower() for i in flagged[:3])
            + "."
        )

    return BusinessHealth(
        score=score,
        grade=grade,  # type: ignore[arg-type]
        level=level,
        indicators=indicators,
        headline=headline,
    )


__all__ = [
    "CUSTOMER_CONCENTRATION",
    "DISCOUNT_DEPENDENCY",
    "LOSS_MAKING_REVENUE",
    "MARGIN_EROSION",
    "PRODUCT_CONCENTRATION",
    "REPEAT_RATE_DECLINE",
    "RETURN_RATE_RISE",
    "Threshold",
    "build_business_health",
    "build_risk_indicators",
]
