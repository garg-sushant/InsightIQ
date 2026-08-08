"""Dimension rollups and product performance tables."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pandas as pd

from app.schemas.analytics import (
    Breakdown,
    BreakdownItem,
    DimensionKey,
    ProductPerformance,
)
from app.services.analytics.numeric import (
    ZERO,
    decimal_sum,
    money,
    optional_money,
    optional_rate,
    percent_change,
    rate,
    ratio_pct,
)

#: Dimensions rolled up on every run and surfaced on the dashboard.
DEFAULT_DIMENSIONS: tuple[DimensionKey, ...] = (
    DimensionKey.REGION,
    DimensionKey.CATEGORY,
    DimensionKey.SUB_CATEGORY,
    DimensionKey.SEGMENT,
)

DIMENSION_LABELS: dict[str, str] = {
    "region": "Region",
    "category": "Category",
    "sub_category": "Sub-category",
    "segment": "Customer segment",
    "state": "State",
    "ship_mode": "Ship mode",
}


def _aggregate_by(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    records = []
    for key, group in frame.groupby(column, sort=False, dropna=False):
        records.append(
            {
                "key": str(key),
                "revenue": decimal_sum(group["sales"]),
                "profit": decimal_sum(group["profit"]),
                "orders": int(group["order_ref"].nunique()),
                "units": int(group["quantity"].sum()),
            }
        )
    return pd.DataFrame(records)


def build_breakdown(
    frame: pd.DataFrame,
    dimension: str,
    *,
    comparison_frame: pd.DataFrame | None = None,
    limit: int | None = None,
) -> Breakdown:
    """Revenue/profit rollup for one dimension, sorted by revenue descending."""
    if frame.empty or dimension not in frame.columns:
        return Breakdown(dimension=dimension, items=[])

    aggregated = _aggregate_by(frame, dimension)
    total_revenue = decimal_sum(aggregated["revenue"])

    previous_by_key: dict[str, Decimal] = {}
    if comparison_frame is not None and not comparison_frame.empty:
        previous = _aggregate_by(comparison_frame, dimension)
        previous_by_key = {
            str(row["key"]): row["revenue"] for _, row in previous.iterrows()
        }

    aggregated["__sort"] = aggregated["revenue"].astype(float)
    aggregated = aggregated.sort_values("__sort", ascending=False)
    if limit is not None:
        aggregated = aggregated.head(limit)

    items: list[BreakdownItem] = []
    for _, record in aggregated.iterrows():
        revenue = record["revenue"]
        profit = record["profit"]
        previous_revenue = previous_by_key.get(record["key"])
        items.append(
            BreakdownItem(
                key=record["key"],
                label=record["key"],
                revenue=money(revenue),
                profit=money(profit),
                margin_pct=rate(ratio_pct(profit, revenue) or ZERO),
                orders=int(record["orders"]),
                units=int(record["units"]),
                revenue_share_pct=rate(ratio_pct(revenue, total_revenue) or ZERO),
                previous_revenue=optional_money(previous_revenue),
                revenue_delta_pct=optional_rate(percent_change(revenue, previous_revenue)),
            )
        )
    return Breakdown(dimension=dimension, items=items)


def build_all_breakdowns(
    frame: pd.DataFrame,
    *,
    comparison_frame: pd.DataFrame | None = None,
    top_n: int = 10,
) -> dict[str, Breakdown]:
    """The standard dimension set. Sub-category is capped; the rest are small."""
    breakdowns: dict[str, Breakdown] = {}
    for dimension in DEFAULT_DIMENSIONS:
        limit = top_n if dimension is DimensionKey.SUB_CATEGORY else None
        breakdowns[dimension.value] = build_breakdown(
            frame, dimension.value, comparison_frame=comparison_frame, limit=limit
        )
    return breakdowns


def build_product_performance(
    frame: pd.DataFrame,
    product_meta: dict[uuid.UUID, dict[str, str | None]],
    *,
    top_n: int = 10,
) -> tuple[list[ProductPerformance], list[ProductPerformance]]:
    """Best and worst products by profit.

    Ranking on profit rather than revenue is deliberate: the interesting story
    in retail is almost always the high-revenue product that loses money, and a
    revenue ranking hides exactly that.
    """
    if frame.empty:
        return [], []

    records = []
    for product_id, group in frame.groupby("product_id", sort=False):
        revenue = decimal_sum(group["sales"])
        profit = decimal_sum(group["profit"])
        meta = product_meta.get(product_id, {})
        records.append(
            {
                "product_ref": meta.get("product_ref") or str(product_id),
                "name": meta.get("name") or "Unknown product",
                "category": meta.get("category"),
                "sub_category": meta.get("sub_category"),
                "revenue": revenue,
                "profit": profit,
                "margin_pct": ratio_pct(profit, revenue) or ZERO,
                "units": int(group["quantity"].sum()),
                "orders": int(group["order_ref"].nunique()),
                "__sort": float(profit),
            }
        )

    table = pd.DataFrame(records).sort_values("__sort", ascending=False)

    def _rows(subset: pd.DataFrame) -> list[ProductPerformance]:
        return [
            ProductPerformance(
                product_ref=str(record["product_ref"]),
                name=str(record["name"]),
                category=record["category"],
                sub_category=record["sub_category"],
                revenue=money(record["revenue"]),
                profit=money(record["profit"]),
                margin_pct=rate(record["margin_pct"]),
                units=int(record["units"]),
                orders=int(record["orders"]),
            )
            for _, record in subset.iterrows()
        ]

    top = _rows(table.head(top_n))
    bottom = _rows(table.tail(top_n).sort_values("__sort", ascending=True))
    return top, bottom


def revenue_concentration(frame: pd.DataFrame, column: str, *, top: int) -> Decimal:
    """Share of revenue held by the top ``n`` entities of a column, as a percent."""
    if frame.empty or column not in frame.columns:
        return ZERO
    grouped = frame.groupby(column, sort=False)["sales"].apply(decimal_sum)
    if grouped.empty:
        return ZERO
    total = decimal_sum(grouped.values)
    if total == ZERO:
        return ZERO
    ordered = sorted(grouped.values, key=float, reverse=True)[:top]
    return ratio_pct(decimal_sum(ordered), total) or ZERO


def top_decile_customer_share(frame: pd.DataFrame) -> Decimal:
    """Revenue share of the top 10% of customers — a classic concentration risk."""
    if frame.empty:
        return ZERO
    grouped = frame.groupby("customer_id", sort=False)["sales"].apply(decimal_sum)
    count = len(grouped)
    if count == 0:
        return ZERO
    top_count = max(1, round(count * 0.1))
    return revenue_concentration(frame, "customer_id", top=top_count)


__all__ = [
    "DEFAULT_DIMENSIONS",
    "DIMENSION_LABELS",
    "build_all_breakdowns",
    "build_breakdown",
    "build_product_performance",
    "revenue_concentration",
    "top_decile_customer_share",
]
