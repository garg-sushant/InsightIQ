"""Exact-arithmetic helpers.

Money is summed as :class:`~decimal.Decimal` and only converted to ``float`` at
the very edge, when a value is placed into a response schema. Ratios derived
from money are computed in Decimal too, so a margin percentage is never the
result of two lossy divisions.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import pandas as pd

ZERO = Decimal(0)
HUNDRED = Decimal(100)

#: Output precision for currency values placed in API responses.
MONEY_PLACES = Decimal("0.01")
#: Output precision for percentages and ratios.
RATE_PLACES = Decimal("0.0001")


def to_decimal(value: Any) -> Decimal:
    """Coerce anything numeric-ish to Decimal, defaulting to zero."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    try:
        if pd.isna(value):
            return ZERO
    except (TypeError, ValueError):
        pass
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, ArithmeticError):
        return ZERO


def decimal_sum(values: Iterable[Any]) -> Decimal:
    """Exact sum. Used for every currency aggregation in the engine."""
    total = ZERO
    for value in values:
        total += to_decimal(value)
    return total


def safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Division that yields ``None`` rather than raising or returning inf."""
    if denominator == ZERO:
        return None
    try:
        return numerator / denominator
    except (ArithmeticError, InvalidOperation):
        return None


def ratio_pct(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    result = safe_divide(numerator, denominator)
    return None if result is None else result * HUNDRED


def money(value: Decimal | float | None) -> float:
    """Round a currency amount to 2dp for the API boundary."""
    if value is None:
        return 0.0
    decimal_value = value if isinstance(value, Decimal) else to_decimal(value)
    return float(decimal_value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP))


def rate(value: Decimal | float | None, places: int = 2) -> float:
    """Round a percentage/ratio for the API boundary."""
    if value is None:
        return 0.0
    decimal_value = value if isinstance(value, Decimal) else to_decimal(value)
    quantum = Decimal(1).scaleb(-places)
    return float(decimal_value.quantize(quantum, rounding=ROUND_HALF_UP))


def optional_rate(value: Decimal | float | None, places: int = 2) -> float | None:
    return None if value is None else rate(value, places)


def optional_money(value: Decimal | float | None) -> float | None:
    return None if value is None else money(value)


def percent_change(current: Decimal, previous: Decimal | None) -> Decimal | None:
    """Relative change vs a baseline.

    Returns ``None`` when the baseline is zero or missing — a "percent change
    from nothing" is undefined, and reporting it as +100% or ∞ would be a lie
    the AI layer might then narrate.
    """
    if previous is None or previous == ZERO:
        return None
    return ((current - previous) / abs(previous)) * HUNDRED


__all__ = [
    "HUNDRED",
    "MONEY_PLACES",
    "RATE_PLACES",
    "ZERO",
    "decimal_sum",
    "money",
    "optional_money",
    "optional_rate",
    "percent_change",
    "rate",
    "ratio_pct",
    "safe_divide",
    "to_decimal",
]
