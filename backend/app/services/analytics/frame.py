"""Builds the in-memory analysis frame that every metric is derived from.

There is exactly one shaping step, here, so a filter applied to the KPI cards
is by construction the same filter applied to the charts, the breakdowns, the
anomaly detector and the AI payload.

Two representations of each money column coexist on purpose:

* ``sales`` / ``profit`` — ``Decimal``, used for every reported aggregate.
* ``sales_f`` / ``profit_f`` — ``float``, used only for statistics and ML
  (Isolation Forest, K-means, moving averages) where exactness is irrelevant
  and NumPy needs a native dtype.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

from app.services.analytics.numeric import to_decimal

FRAME_COLUMNS = (
    "order_date",
    "order_ref",
    "customer_id",
    "product_id",
    "region",
    "state",
    "segment",
    "category",
    "sub_category",
    "ship_mode",
    "quantity",
    "unit_price",
    "discount",
    "sales",
    "profit",
)

_DIMENSIONS = ("region", "state", "segment", "category", "sub_category", "ship_mode")

#: Shown wherever a dimension value is missing, so a null never silently
#: disappears from a breakdown chart.
UNKNOWN_LABEL = "Unspecified"


def build_frame(rows: Sequence[dict[str, Any]]) -> pd.DataFrame:
    """Normalise raw repository rows into the analysis frame."""
    if not rows:
        return empty_frame()

    frame = pd.DataFrame(list(rows))
    for column in FRAME_COLUMNS:
        if column not in frame.columns:
            frame[column] = None

    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce")
    frame = frame[frame["order_date"].notna()]
    if frame.empty:
        return empty_frame()

    for column in ("sales", "profit", "discount", "unit_price"):
        frame[column] = frame[column].map(to_decimal)

    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0).astype("int64")

    for column in _DIMENSIONS:
        frame[column] = (
            frame[column].astype("object").where(frame[column].notna(), UNKNOWN_LABEL)
        )
        frame[column] = frame[column].replace({"": UNKNOWN_LABEL}).astype(str)

    frame["sales_f"] = frame["sales"].astype(float)
    frame["profit_f"] = frame["profit"].astype(float)
    frame["discount_f"] = frame["discount"].astype(float)

    return frame.reset_index(drop=True)


def empty_frame() -> pd.DataFrame:
    """A correctly-typed zero-row frame, so downstream code needs no null checks."""
    frame = pd.DataFrame({column: pd.Series(dtype="object") for column in FRAME_COLUMNS})
    frame["order_date"] = pd.Series(dtype="datetime64[ns]")
    frame["quantity"] = pd.Series(dtype="int64")
    for column in ("sales_f", "profit_f", "discount_f"):
        frame[column] = pd.Series(dtype="float64")
    return frame


def slice_period(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Inclusive date-range slice."""
    if frame.empty:
        return frame
    mask = (frame["order_date"] >= pd.Timestamp(start)) & (
        frame["order_date"] <= pd.Timestamp(end)
    )
    return frame[mask]


def dimension_values(frame: pd.DataFrame, dimension: str) -> list[str]:
    if frame.empty or dimension not in frame.columns:
        return []
    return sorted(set(frame[dimension].dropna().astype(str)) - {UNKNOWN_LABEL})


__all__ = [
    "FRAME_COLUMNS",
    "UNKNOWN_LABEL",
    "build_frame",
    "dimension_values",
    "empty_frame",
    "slice_period",
]
