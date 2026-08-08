"""Period bucketing, moving averages and period-over-period deltas."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from app.schemas.analytics import Granularity, TimeSeries, TimeSeriesPoint
from app.services.analytics.numeric import (
    ZERO,
    decimal_sum,
    money,
    optional_rate,
    percent_change,
    rate,
    ratio_pct,
)

#: Moving-average window per granularity: one week, one month, one quarter,
#: one half-year respectively.
MA_WINDOWS: dict[Granularity, int] = {
    Granularity.DAY: 7,
    Granularity.WEEK: 4,
    Granularity.MONTH: 3,
    Granularity.QUARTER: 2,
}

_PERIOD_FREQ: dict[Granularity, str] = {
    Granularity.DAY: "D",
    Granularity.WEEK: "W-MON",
    Granularity.MONTH: "MS",
    Granularity.QUARTER: "QS",
}


def bucket_key(frame: pd.DataFrame, granularity: Granularity) -> pd.Series:
    """Map each order date onto the start of its bucket."""
    dates = frame["order_date"]
    if granularity is Granularity.DAY:
        return dates.dt.normalize()
    if granularity is Granularity.WEEK:
        # Weeks start Monday; ``to_period`` then ``start_time`` gives the Monday.
        return dates.dt.to_period("W-MON").dt.start_time
    if granularity is Granularity.QUARTER:
        return dates.dt.to_period("Q").dt.start_time
    return dates.dt.to_period("M").dt.start_time


def aggregate_periods(frame: pd.DataFrame, granularity: Granularity) -> pd.DataFrame:
    """Group the fact frame into period buckets with exact currency sums."""
    if frame.empty:
        return pd.DataFrame(
            columns=["period", "revenue", "profit", "orders", "units"]
        )

    working = frame.copy()
    working["__bucket"] = bucket_key(working, granularity)

    records = []
    for bucket, group in working.groupby("__bucket", sort=True):
        records.append(
            {
                "period": bucket,
                "revenue": decimal_sum(group["sales"]),
                "profit": decimal_sum(group["profit"]),
                "orders": int(group["order_ref"].nunique()),
                "units": int(group["quantity"].sum()),
            }
        )
    return pd.DataFrame(records)


def fill_missing_periods(
    aggregated: pd.DataFrame, granularity: Granularity
) -> pd.DataFrame:
    """Insert zero rows for gaps.

    A month with no sales is information, not an absence of information — the
    trend line must show the hole rather than joining across it.
    """
    if aggregated.empty or len(aggregated) < 2:
        return aggregated

    full_index = pd.date_range(
        start=aggregated["period"].min(),
        end=aggregated["period"].max(),
        freq=_PERIOD_FREQ[granularity],
    )
    indexed = aggregated.set_index("period").reindex(full_index)
    indexed["revenue"] = indexed["revenue"].apply(lambda v: v if isinstance(v, Decimal) else ZERO)
    indexed["profit"] = indexed["profit"].apply(lambda v: v if isinstance(v, Decimal) else ZERO)
    indexed["orders"] = indexed["orders"].fillna(0).astype(int)
    indexed["units"] = indexed["units"].fillna(0).astype(int)
    return indexed.rename_axis("period").reset_index()


def build_timeseries(frame: pd.DataFrame, granularity: Granularity) -> TimeSeries:
    """Bucketed series with a trailing moving average and PoP deltas."""
    window = MA_WINDOWS[granularity]
    aggregated = fill_missing_periods(aggregate_periods(frame, granularity), granularity)

    if aggregated.empty:
        return TimeSeries(granularity=granularity, moving_average_window=window, points=[])

    revenue_float = aggregated["revenue"].astype(float)
    profit_float = aggregated["profit"].astype(float)
    # min_periods=1 so the line starts at the first point instead of after a gap.
    revenue_ma = revenue_float.rolling(window=window, min_periods=1).mean()
    profit_ma = profit_float.rolling(window=window, min_periods=1).mean()

    points: list[TimeSeriesPoint] = []
    previous_revenue: Decimal | None = None
    for position, record in aggregated.iterrows():
        revenue = record["revenue"]
        profit = record["profit"]
        points.append(
            TimeSeriesPoint(
                period=pd.Timestamp(record["period"]).date().isoformat(),
                revenue=money(revenue),
                profit=money(profit),
                margin_pct=rate(ratio_pct(profit, revenue) or ZERO),
                orders=int(record["orders"]),
                units=int(record["units"]),
                revenue_ma=money(Decimal(str(revenue_ma.iloc[position]))),
                profit_ma=money(Decimal(str(profit_ma.iloc[position]))),
                revenue_pop_pct=optional_rate(percent_change(revenue, previous_revenue)),
            )
        )
        previous_revenue = revenue

    return TimeSeries(granularity=granularity, moving_average_window=window, points=points)


def choose_anomaly_granularity(day_count: int) -> Granularity:
    """Daily detection for short windows, weekly for long ones.

    Beyond roughly six months a daily series is dominated by weekday
    seasonality, which produces a flood of uninteresting "anomalies".
    """
    return Granularity.DAY if day_count <= 180 else Granularity.WEEK


__all__ = [
    "MA_WINDOWS",
    "aggregate_periods",
    "bucket_key",
    "build_timeseries",
    "choose_anomaly_granularity",
    "fill_missing_periods",
]
