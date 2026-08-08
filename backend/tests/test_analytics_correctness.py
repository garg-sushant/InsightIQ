"""Analytics correctness against a hand-computed fixture.

Every expected value here was computed by hand (see the docstring below) so
that a regression in the analytics engine fails a test instead of silently
surfacing as a wrong number on the dashboard.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.services.analytics.frame import build_frame, slice_period
from app.services.analytics.kpis import compute_core_metrics
from app.services.analytics.timeseries import build_timeseries
from app.schemas.analytics import Granularity

CUSTOMER_A = uuid.uuid4()
CUSTOMER_B = uuid.uuid4()
PRODUCT_X = uuid.uuid4()
PRODUCT_Y = uuid.uuid4()


def _rows() -> list[dict]:
    """
    Hand-computed fixture:

    Order A (2024-01-05, customer A, 2 lines):
      line 1: product X, qty 2, sales 100.00, profit 20.00
      line 2: product Y, qty 1, sales 200.00, profit 40.00
    Order B (2024-01-20, customer B, 1 line):
      line 1: product X, qty 3, sales 150.00, profit -10.00   (loss-making)
    Order C (2024-02-10, customer A, 1 line):
      line 1: product Y, qty 5, sales 500.00, profit 100.00

    Whole-period (Jan 1 - Feb 28) expected values:
      revenue = 100 + 200 + 150 + 500 = 950.00
      profit  = 20 + 40 - 10 + 100    = 150.00
      margin% = 150 / 950 * 100       = 15.7894736842...
      orders (distinct order_ref)     = 3
      units                            = 2 + 1 + 3 + 5 = 11
      aov = 950 / 3                    = 316.6666...
      negative_margin_revenue          = 150.00 (order B's line)
    """
    return [
        dict(
            order_date=date(2024, 1, 5), order_ref="A", customer_id=CUSTOMER_A,
            product_id=PRODUCT_X, region="East", state="NY", segment="Consumer",
            category="Office Supplies", sub_category="Binders", ship_mode="Standard",
            quantity=2, unit_price=Decimal("50.00"), discount=Decimal("0"),
            sales=Decimal("100.00"), profit=Decimal("20.00"),
        ),
        dict(
            order_date=date(2024, 1, 5), order_ref="A", customer_id=CUSTOMER_A,
            product_id=PRODUCT_Y, region="East", state="NY", segment="Consumer",
            category="Office Supplies", sub_category="Paper", ship_mode="Standard",
            quantity=1, unit_price=Decimal("200.00"), discount=Decimal("0"),
            sales=Decimal("200.00"), profit=Decimal("40.00"),
        ),
        dict(
            order_date=date(2024, 1, 20), order_ref="B", customer_id=CUSTOMER_B,
            product_id=PRODUCT_X, region="West", state="CA", segment="Corporate",
            category="Office Supplies", sub_category="Binders", ship_mode="Standard",
            quantity=3, unit_price=Decimal("50.00"), discount=Decimal("0"),
            sales=Decimal("150.00"), profit=Decimal("-10.00"),
        ),
        dict(
            order_date=date(2024, 2, 10), order_ref="C", customer_id=CUSTOMER_A,
            product_id=PRODUCT_Y, region="East", state="NY", segment="Consumer",
            category="Office Supplies", sub_category="Paper", ship_mode="Standard",
            quantity=5, unit_price=Decimal("100.00"), discount=Decimal("0"),
            sales=Decimal("500.00"), profit=Decimal("100.00"),
        ),
    ]


@pytest.fixture
def frame() -> pd.DataFrame:
    return build_frame(_rows())


def test_kpi_revenue_profit_margin_exact(frame: pd.DataFrame) -> None:
    period = slice_period(frame, date(2024, 1, 1), date(2024, 2, 28))
    metrics = compute_core_metrics(
        period,
        returned_order_refs=set(),
        customer_first_order={CUSTOMER_A: date(2024, 1, 5), CUSTOMER_B: date(2024, 1, 20)},
        period_start=date(2024, 1, 1),
    )

    assert metrics.revenue == Decimal("950.00")
    assert metrics.profit == Decimal("150.00")
    assert metrics.orders == 3
    assert metrics.units == 11
    assert metrics.negative_margin_revenue == Decimal("150.00")

    # Margin: 150/950 * 100 = 15.7894736842...
    assert metrics.margin_pct is not None
    assert abs(metrics.margin_pct - Decimal("15.7894736842")) < Decimal("0.0001")

    # AOV: 950/3 = 316.6666...
    assert metrics.aov is not None
    assert abs(metrics.aov - Decimal("316.6666666667")) < Decimal("0.0001")


def test_new_vs_repeat_customers(frame: pd.DataFrame) -> None:
    """Customer A's first order is in Jan; ordering again in Feb makes them a
    repeat customer in the Feb window, not new."""
    period = slice_period(frame, date(2024, 2, 1), date(2024, 2, 28))
    metrics = compute_core_metrics(
        period,
        returned_order_refs=set(),
        customer_first_order={CUSTOMER_A: date(2024, 1, 5), CUSTOMER_B: date(2024, 1, 20)},
        period_start=date(2024, 2, 1),
    )
    assert metrics.customers == 1
    assert metrics.new_customers == 0
    assert metrics.repeat_customers == 1


def test_new_customer_labelled_correctly_on_first_order(frame: pd.DataFrame) -> None:
    period = slice_period(frame, date(2024, 1, 1), date(2024, 1, 31))
    metrics = compute_core_metrics(
        period,
        returned_order_refs=set(),
        customer_first_order={CUSTOMER_A: date(2024, 1, 5), CUSTOMER_B: date(2024, 1, 20)},
        period_start=date(2024, 1, 1),
    )
    # Both A and B ordered for the first time in January.
    assert metrics.new_customers == 2
    assert metrics.repeat_customers == 0


def test_return_rate_counts_distinct_orders(frame: pd.DataFrame) -> None:
    period = slice_period(frame, date(2024, 1, 1), date(2024, 2, 28))
    metrics = compute_core_metrics(
        period,
        returned_order_refs={"B"},
        customer_first_order={CUSTOMER_A: date(2024, 1, 5), CUSTOMER_B: date(2024, 1, 20)},
        period_start=date(2024, 1, 1),
    )
    assert metrics.returned_orders == 1
    assert metrics.orders == 3
    assert metrics.return_rate_pct is not None
    assert abs(metrics.return_rate_pct - Decimal("33.3333333333")) < Decimal("0.0001")


def test_timeseries_monthly_buckets_sum_correctly(frame: pd.DataFrame) -> None:
    ts = build_timeseries(frame, Granularity.MONTH)
    by_period = {point.period: point for point in ts.points}

    # January contains both order A (300 revenue, 60 profit) and order B
    # (150 revenue, -10 profit): 300+150=450 revenue, 60-10=50 profit.
    assert by_period["2024-01-01"].revenue == pytest.approx(450.0)
    assert by_period["2024-01-01"].profit == pytest.approx(50.0)
    assert by_period["2024-01-01"].orders == 2

    assert by_period["2024-02-01"].revenue == pytest.approx(500.0)
    assert by_period["2024-02-01"].profit == pytest.approx(100.0)
    assert by_period["2024-02-01"].orders == 1


def test_empty_frame_produces_zeroed_metrics() -> None:
    empty = build_frame([])
    metrics = compute_core_metrics(
        empty, returned_order_refs=set(), customer_first_order={}, period_start=date(2024, 1, 1)
    )
    assert metrics.revenue == Decimal("0")
    assert metrics.orders == 0
    assert metrics.margin_pct is None
    assert metrics.aov is None
