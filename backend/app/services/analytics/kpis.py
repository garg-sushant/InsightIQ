"""Headline KPI computation.

Definitions, stated once so the dashboard, the reports and the AI narrative all
mean the same thing:

* **revenue** — sum of line ``sales`` (already net of discount).
* **profit** — sum of line ``profit``.
* **margin %** — profit / revenue * 100.
* **orders** — count of *distinct* ``order_ref`` (not order lines).
* **AOV** — revenue / distinct orders.
* **units** — sum of ``quantity``.
* **return rate %** — distinct returned orders / distinct orders * 100, where
  a return marks a whole order.
* **new customer** — a customer whose first-ever order in the workspace falls
  inside the window. Judged against the customer's whole history, not just the
  loaded window, so a long-standing customer is never mislabelled as new.
* **repeat customers** — active customers in the window minus new ones.
* **avg discount %** — unweighted mean of line discount * 100.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from app.schemas.analytics import KpiSet, MetricValue
from app.services.analytics.numeric import (
    ZERO,
    decimal_sum,
    money,
    optional_money,
    optional_rate,
    percent_change,
    rate,
    ratio_pct,
    safe_divide,
)


@dataclass(frozen=True)
class CoreMetrics:
    """Exact metric values for one window. Currency stays Decimal throughout."""

    revenue: Decimal
    profit: Decimal
    margin_pct: Decimal | None
    orders: int
    aov: Decimal | None
    units: int
    returned_orders: int
    return_rate_pct: Decimal | None
    customers: int
    new_customers: int
    repeat_customers: int
    repeat_rate_pct: Decimal | None
    avg_discount_pct: Decimal | None
    negative_margin_revenue: Decimal
    line_count: int


def compute_core_metrics(
    frame: pd.DataFrame,
    *,
    returned_order_refs: set[str],
    customer_first_order: dict[uuid.UUID, date],
    period_start: date,
) -> CoreMetrics:
    """Compute every headline metric for a single window."""
    if frame.empty:
        return CoreMetrics(
            revenue=ZERO,
            profit=ZERO,
            margin_pct=None,
            orders=0,
            aov=None,
            units=0,
            returned_orders=0,
            return_rate_pct=None,
            customers=0,
            new_customers=0,
            repeat_customers=0,
            repeat_rate_pct=None,
            avg_discount_pct=None,
            negative_margin_revenue=ZERO,
            line_count=0,
        )

    revenue = decimal_sum(frame["sales"])
    profit = decimal_sum(frame["profit"])
    units = int(frame["quantity"].sum())

    order_refs = set(frame["order_ref"].astype(str))
    orders = len(order_refs)
    returned_orders = len(order_refs & returned_order_refs)

    customer_ids = set(frame["customer_id"].dropna())
    customers = len(customer_ids)
    new_customers = sum(
        1
        for customer_id in customer_ids
        if (first := customer_first_order.get(customer_id)) is not None
        and first >= period_start
    )
    repeat_customers = customers - new_customers

    discounts = frame["discount"]
    avg_discount = (
        (decimal_sum(discounts) / Decimal(len(discounts))) * Decimal(100)
        if len(discounts)
        else None
    )

    negative_margin_revenue = decimal_sum(frame.loc[frame["profit_f"] < 0, "sales"])

    return CoreMetrics(
        revenue=revenue,
        profit=profit,
        margin_pct=ratio_pct(profit, revenue),
        orders=orders,
        aov=safe_divide(revenue, Decimal(orders)) if orders else None,
        units=units,
        returned_orders=returned_orders,
        return_rate_pct=ratio_pct(Decimal(returned_orders), Decimal(orders)) if orders else None,
        customers=customers,
        new_customers=new_customers,
        repeat_customers=repeat_customers,
        repeat_rate_pct=(
            ratio_pct(Decimal(repeat_customers), Decimal(customers)) if customers else None
        ),
        avg_discount_pct=avg_discount,
        negative_margin_revenue=negative_margin_revenue,
        line_count=len(frame),
    )


def _currency_metric(current: Decimal, previous: Decimal | None) -> MetricValue:
    return MetricValue(
        current=money(current),
        previous=optional_money(previous),
        delta_abs=optional_money(current - previous) if previous is not None else None,
        delta_pct=optional_rate(percent_change(current, previous)),
    )


def _count_metric(current: int, previous: int | None) -> MetricValue:
    current_decimal = Decimal(current)
    previous_decimal = Decimal(previous) if previous is not None else None
    return MetricValue(
        current=float(current),
        previous=float(previous) if previous is not None else None,
        delta_abs=float(current - previous) if previous is not None else None,
        delta_pct=optional_rate(percent_change(current_decimal, previous_decimal)),
    )


def _rate_metric(current: Decimal | None, previous: Decimal | None) -> MetricValue:
    """Percentage metric.

    ``delta_abs`` is the *percentage-point* difference (the honest way to
    compare two rates); ``delta_pct`` is the relative change, kept for callers
    that want it. The UI labels rate deltas with "pp" for exactly this reason.
    """
    current_value = current if current is not None else ZERO
    return MetricValue(
        current=rate(current_value),
        previous=optional_rate(previous),
        delta_abs=(
            optional_rate(current_value - previous) if previous is not None else None
        ),
        delta_pct=optional_rate(percent_change(current_value, previous)),
    )


def build_kpi_set(current: CoreMetrics, previous: CoreMetrics | None) -> KpiSet:
    """Assemble the API-facing KPI block from one or two computed windows."""
    return KpiSet(
        revenue=_currency_metric(current.revenue, previous.revenue if previous else None),
        profit=_currency_metric(current.profit, previous.profit if previous else None),
        margin_pct=_rate_metric(current.margin_pct, previous.margin_pct if previous else None),
        orders=_count_metric(current.orders, previous.orders if previous else None),
        aov=_currency_metric(
            current.aov or ZERO, (previous.aov if previous else None)
        ),
        units=_count_metric(current.units, previous.units if previous else None),
        return_rate_pct=_rate_metric(
            current.return_rate_pct, previous.return_rate_pct if previous else None
        ),
        customers=_count_metric(current.customers, previous.customers if previous else None),
        new_customers=_count_metric(
            current.new_customers, previous.new_customers if previous else None
        ),
        repeat_customers=_count_metric(
            current.repeat_customers, previous.repeat_customers if previous else None
        ),
        repeat_rate_pct=_rate_metric(
            current.repeat_rate_pct, previous.repeat_rate_pct if previous else None
        ),
        avg_discount_pct=_rate_metric(
            current.avg_discount_pct, previous.avg_discount_pct if previous else None
        ),
    )


__all__ = ["CoreMetrics", "build_kpi_set", "compute_core_metrics"]
