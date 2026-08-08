"""Schema, type, range, duplicate and referential validation.

The contract: *nothing* is written to the database until validation has decided
which rows are acceptable. Row-level problems drop a row and are reported with
the row number, column and reason; structural problems (a missing required
column, an unusable file) reject the whole batch atomically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd

from app.schemas.dataset import (
    MAX_REPORTED_ROW_ERRORS,
    ColumnReport,
    ErrorSeverity,
    RowError,
)
from app.services.ingestion.spec import ColumnSpec, EntitySpec, FieldType

#: Internal column holding the 1-based source row number, kept alongside the
#: data so every error can point the user at a specific line of their file.
ROW_NUMBER = "__row_number"

#: A batch this badly broken is almost certainly the wrong file or the wrong
#: entity type; committing a fraction of it would be worse than refusing.
MAX_REJECT_FRACTION = 0.5

#: Sanity window for business dates. Anything outside is a data-entry error.
MIN_PLAUSIBLE_DATE = date(1990, 1, 1)
_FUTURE_SLACK = timedelta(days=730)

_CURRENCY_NOISE = re.compile(r"[^\d\-+.,eE]")
_TRUTHY = {"true", "t", "yes", "y", "1", "returned", "return", "returned_flag"}
_FALSY = {"false", "f", "no", "n", "0", "not returned", "none"}


@dataclass
class ValidationOutcome:
    """Result of validating one parsed file."""

    frame: pd.DataFrame
    """Canonical-column frame containing only the accepted rows."""

    rows_total: int
    rows_accepted: int
    rows_rejected: int
    duplicates_dropped: int
    errors: list[RowError] = field(default_factory=list)
    error_counts: dict[str, int] = field(default_factory=dict)
    errors_truncated: bool = False
    warnings: list[str] = field(default_factory=list)
    columns: list[ColumnReport] = field(default_factory=list)
    missing_required_columns: list[str] = field(default_factory=list)
    unexpected_columns: list[str] = field(default_factory=list)
    referential_issues: dict[str, int] = field(default_factory=dict)
    #: Set when the batch must be rejected atomically.
    critical_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.critical_error is None


class ErrorCollector:
    """Accumulates row errors, capping what is retained but never the counts."""

    def __init__(self, limit: int = MAX_REPORTED_ROW_ERRORS) -> None:
        self.limit = limit
        self.errors: list[RowError] = []
        self.counts: dict[str, int] = {}
        self.truncated = False

    def add(
        self,
        *,
        row_number: int,
        error_type: str,
        message: str,
        column: str | None = None,
        value: object | None = None,
        severity: ErrorSeverity = ErrorSeverity.ROW,
    ) -> None:
        self.counts[error_type] = self.counts.get(error_type, 0) + 1
        if len(self.errors) >= self.limit:
            self.truncated = True
            return
        rendered: str | None = None
        if value is not None and not _is_missing(value):
            rendered = str(value)[:80]
        self.errors.append(
            RowError(
                row_number=row_number,
                column=column,
                error_type=error_type,
                message=message,
                severity=severity,
                value=rendered,
            )
        )


def _is_real_date(value: object) -> bool:
    """True only for a genuine ``date``.

    ``pd.NaT`` subclasses ``datetime`` and therefore passes ``isinstance(v, date)``
    while raising on every comparison — it has to be excluded explicitly.
    """
    return value is not pd.NaT and isinstance(value, date) and not pd.isna(value)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    return value is pd.NaT or (isinstance(value, str) and not value.strip())


# ---------------------------------------------------------------------------
# Per-type coercion
# ---------------------------------------------------------------------------
def _clean_numeric_text(series: pd.Series) -> pd.Series:
    """Strip currency symbols and thousands separators.

    Accounting-style ``(123.45)`` is preserved as a negative, and a trailing
    ``%`` survives so :func:`_to_decimal` can divide by 100.
    """
    text = series.astype("string").str.strip()
    text = text.mask(text.eq(""), pd.NA)

    negative = text.str.match(r"^\(.*\)$", na=False)
    text = text.str.replace(r"^\((.*)\)$", r"\1", regex=True)

    percent = text.str.endswith("%", na=False)
    text = text.str.rstrip("%")

    text = text.str.replace(_CURRENCY_NOISE, "", regex=True)
    # Thousands separators only; a decimal comma is ambiguous, so we require a dot.
    text = text.str.replace(",", "", regex=False)

    needs_sign = negative & ~text.str.startswith("-", na=False) & text.notna()
    text = text.mask(needs_sign, "-" + text.fillna(""))
    text = text.mask(percent & text.notna(), text.fillna("") + "%")
    return text


def _as_float(value: object) -> float:
    """Best-effort numeric view for range checks. Never raises."""
    if _is_missing(value):
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def _normalized_default(column: ColumnSpec) -> object | None:
    """Keep decimal defaults exact instead of letting an int sneak in."""
    if column.default is None:
        return None
    if column.field_type is FieldType.DECIMAL:
        return Decimal(str(column.default))
    return column.default


def _to_decimal(raw: object) -> Decimal | None:
    """Exact string -> Decimal. Percentages are converted to fractions."""
    if _is_missing(raw):
        return None
    text = str(raw).strip()
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if is_percent:
        value = value / Decimal(100)
    if not value.is_finite():
        return None
    return value


def _coerce_string(series: pd.Series, spec: ColumnSpec) -> tuple[pd.Series, pd.Series]:
    text = series.astype("string").str.strip()
    text = text.replace({"": pd.NA})
    if spec.max_length:
        text = text.str.slice(0, spec.max_length)
    # Strings never fail coercion; only "required but blank" can fail.
    return text, pd.Series(False, index=series.index)


def _coerce_integer(series: pd.Series, spec: ColumnSpec) -> tuple[pd.Series, pd.Series]:
    cleaned = series.astype("string").str.strip().str.replace(",", "", regex=False)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    present = cleaned.notna() & (cleaned.str.len() > 0)
    failed = present & numeric.isna()

    # A value like "3.5" units is not an integer quantity; flag rather than round.
    fractional = numeric.notna() & (numeric % 1 != 0)
    failed = failed | fractional

    result = numeric.where(~fractional).astype("Float64").round().astype("Int64")
    return result, failed


def _coerce_decimal(series: pd.Series, spec: ColumnSpec) -> tuple[pd.Series, pd.Series]:
    cleaned = _clean_numeric_text(series)
    values = cleaned.map(_to_decimal)
    present = series.astype("string").str.strip().replace({"": pd.NA}).notna()
    failed = present & values.isna()
    return values.astype(object), failed


def _coerce_date(series: pd.Series, spec: ColumnSpec) -> tuple[pd.Series, pd.Series]:
    text = series.astype("string").str.strip().replace({"": pd.NA})
    parsed = _parse_datetimes(text)
    present = text.notna()
    failed = present & parsed.isna()
    return parsed.dt.date, failed


def _parse_datetimes(text: pd.Series) -> pd.Series:
    """Parse a date column, tolerating files that mix formats.

    ``format="mixed"`` handles the messy real-world case; the plain call is the
    fallback for the pathological inputs it refuses.
    """
    try:
        return pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=False)
    except (ValueError, TypeError):
        try:
            return pd.to_datetime(text, errors="coerce", dayfirst=False)
        except (ValueError, TypeError):
            return pd.Series(pd.NaT, index=text.index)


def _coerce_boolean(series: pd.Series, spec: ColumnSpec) -> tuple[pd.Series, pd.Series]:
    text = series.astype("string").str.strip().str.lower().replace({"": pd.NA})
    result = pd.Series(pd.NA, index=series.index, dtype="boolean")
    result = result.mask(text.isin(_TRUTHY), True)
    result = result.mask(text.isin(_FALSY), False)
    present = text.notna()
    failed = present & result.isna()
    return result, failed


_COERCERS = {
    FieldType.STRING: _coerce_string,
    FieldType.INTEGER: _coerce_integer,
    FieldType.DECIMAL: _coerce_decimal,
    FieldType.DATE: _coerce_date,
    FieldType.BOOLEAN: _coerce_boolean,
}


# ---------------------------------------------------------------------------
# Validation pipeline
# ---------------------------------------------------------------------------
def validate_frame(frame: pd.DataFrame, spec: EntitySpec) -> ValidationOutcome:
    """Run the full validation pipeline for one entity file."""
    collector = ErrorCollector()
    warnings: list[str] = []
    rows_total = len(frame)

    mapping, unexpected = spec.resolve_headers([str(c) for c in frame.columns])
    working = frame.rename(columns=mapping)
    canonical_present = set(mapping.values())

    missing_required = [c for c in spec.required_columns if c not in canonical_present]
    if missing_required:
        return ValidationOutcome(
            frame=working.iloc[0:0],
            rows_total=rows_total,
            rows_accepted=0,
            rows_rejected=rows_total,
            duplicates_dropped=0,
            missing_required_columns=missing_required,
            unexpected_columns=unexpected,
            critical_error=(
                "Required column(s) missing: " + ", ".join(missing_required) + ". "
                "No rows were imported."
            ),
        )

    if unexpected:
        warnings.append(
            f"{len(unexpected)} column(s) were not recognised and were ignored: "
            + ", ".join(unexpected[:10])
            + ("..." if len(unexpected) > 10 else "")
        )

    working = working.reset_index(drop=True)
    row_numbers = pd.Series(np.arange(1, len(working) + 1), index=working.index)
    valid = pd.Series(True, index=working.index)
    column_reports: list[ColumnReport] = []
    output: dict[str, pd.Series] = {}

    for column in spec.columns:
        default = _normalized_default(column)
        present = column.name in working.columns
        if not present:
            output[column.name] = pd.Series(
                [default] * len(working), index=working.index, dtype=object
            )
            column_reports.append(
                ColumnReport(
                    name=column.name,
                    present=False,
                    required=column.required,
                    inferred_type=column.field_type.value,
                    null_count=len(working),
                )
            )
            continue

        raw = working[column.name]
        coerced, failed = _COERCERS[column.field_type](raw, column)

        for index in working.index[failed]:
            collector.add(
                row_number=int(row_numbers[index]),
                column=column.name,
                error_type=f"invalid_{column.field_type.value}",
                message=f"Could not read '{column.name}' as {column.field_type.value}.",
                value=raw[index],
            )

        blank = coerced.isna()
        if column.required:
            required_missing = blank & ~failed
            for index in working.index[required_missing]:
                collector.add(
                    row_number=int(row_numbers[index]),
                    column=column.name,
                    error_type="missing_required_value",
                    message=f"Required column '{column.name}' is empty.",
                )
            failed = failed | required_missing
        elif default is not None:
            coerced = coerced.fillna(default)

        failed = failed | _check_range(
            coerced, column, working.index, row_numbers, collector
        )
        if column.field_type is FieldType.DATE:
            failed = failed | _check_date_window(
                coerced, column, working.index, row_numbers, collector
            )

        valid &= ~failed
        output[column.name] = coerced
        column_reports.append(
            ColumnReport(
                name=column.name,
                present=True,
                required=column.required,
                inferred_type=column.field_type.value,
                null_count=int(coerced.isna().sum()),
                error_count=int(failed.sum()),
            )
        )

    result = pd.DataFrame(output, index=working.index)
    result[ROW_NUMBER] = row_numbers

    # Cross-field rule: ship date cannot precede order date.
    if {"order_date", "ship_date"}.issubset(result.columns):
        reversed_dates = pd.Series(
            [
                _is_real_date(order_on) and _is_real_date(ship_on) and ship_on < order_on
                for order_on, ship_on in zip(
                    result["order_date"], result["ship_date"], strict=True
                )
            ],
            index=result.index,
        )
        for index in result.index[reversed_dates]:
            collector.add(
                row_number=int(row_numbers[index]),
                column="ship_date",
                error_type="ship_before_order",
                message="Ship date is earlier than the order date.",
                value=result.at[index, "ship_date"],
            )
        valid &= ~reversed_dates

    accepted = result[valid].copy()

    duplicates_dropped = 0
    if spec.primary_key and all(k in accepted.columns for k in spec.primary_key):
        key_columns = list(spec.primary_key)
        has_key = accepted[key_columns].notna().all(axis=1)
        duplicated = has_key & accepted.duplicated(subset=key_columns, keep="first")
        for index in accepted.index[duplicated]:
            collector.add(
                row_number=int(accepted.at[index, ROW_NUMBER]),
                column=",".join(key_columns),
                error_type="duplicate_key",
                message=(
                    "Duplicate of an earlier row with the same "
                    f"{', '.join(key_columns)}; the first occurrence was kept."
                ),
                severity=ErrorSeverity.WARNING,
            )
        duplicates_dropped = int(duplicated.sum())
        accepted = accepted[~duplicated]

    rows_accepted = len(accepted)
    rows_rejected = rows_total - rows_accepted

    outcome = ValidationOutcome(
        frame=accepted,
        rows_total=rows_total,
        rows_accepted=rows_accepted,
        rows_rejected=rows_rejected,
        duplicates_dropped=duplicates_dropped,
        errors=collector.errors,
        error_counts=collector.counts,
        errors_truncated=collector.truncated,
        warnings=warnings,
        columns=column_reports,
        missing_required_columns=[],
        unexpected_columns=unexpected,
    )

    if rows_accepted == 0:
        outcome.critical_error = (
            "Every row failed validation, so nothing was imported. "
            "Check that the file matches the selected entity type."
        )
    elif rows_total and (rows_rejected / rows_total) > MAX_REJECT_FRACTION:
        outcome.critical_error = (
            f"{rows_rejected} of {rows_total} rows failed validation "
            f"({rows_rejected / rows_total:.0%}), which is above the "
            f"{MAX_REJECT_FRACTION:.0%} threshold. The batch was rejected "
            "atomically; no rows were imported."
        )

    return outcome


def _check_range(
    values: pd.Series,
    column: ColumnSpec,
    index: pd.Index,
    row_numbers: pd.Series,
    collector: ErrorCollector,
) -> pd.Series:
    if column.min_value is None and column.max_value is None:
        return pd.Series(False, index=index)

    numeric = pd.Series([_as_float(v) for v in values], index=index, dtype="float64")
    out_of_range = pd.Series(False, index=index)
    if column.min_value is not None:
        out_of_range |= numeric.notna() & (numeric < column.min_value)
    if column.max_value is not None:
        out_of_range |= numeric.notna() & (numeric > column.max_value)

    for position in index[out_of_range]:
        collector.add(
            row_number=int(row_numbers[position]),
            column=column.name,
            error_type="out_of_range",
            message=(
                f"'{column.name}' must be between "
                f"{column.min_value if column.min_value is not None else '-inf'} and "
                f"{column.max_value if column.max_value is not None else 'inf'}."
            ),
            value=values[position],
        )
    return out_of_range


def _check_date_window(
    values: pd.Series,
    column: ColumnSpec,
    index: pd.Index,
    row_numbers: pd.Series,
    collector: ErrorCollector,
) -> pd.Series:
    upper = datetime.now().date() + _FUTURE_SLACK
    implausible = pd.Series(
        [
            _is_real_date(value) and (value < MIN_PLAUSIBLE_DATE or value > upper)
            for value in values
        ],
        index=index,
    )
    for position in index[implausible]:
        collector.add(
            row_number=int(row_numbers[position]),
            column=column.name,
            error_type="implausible_date",
            message=(
                f"'{column.name}' must be between {MIN_PLAUSIBLE_DATE.isoformat()} "
                f"and {upper.isoformat()}."
            ),
            value=values[position],
        )
    return implausible


def check_references(
    frame: pd.DataFrame,
    column: str,
    known: set[str],
    *,
    error_type: str,
    message: str,
    collector: ErrorCollector,
) -> pd.Series:
    """Flag rows whose foreign key is not present in ``known``.

    Returns a boolean mask of *offending* rows so the caller decides whether to
    drop them or auto-create the missing parent.
    """
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)

    values = frame[column]
    unknown = values.notna() & ~values.isin(known)
    for index in frame.index[unknown]:
        collector.add(
            row_number=int(frame.at[index, ROW_NUMBER]),
            column=column,
            error_type=error_type,
            message=message,
            value=values[index],
        )
    return unknown


__all__ = [
    "MAX_REJECT_FRACTION",
    "MIN_PLAUSIBLE_DATE",
    "ROW_NUMBER",
    "ErrorCollector",
    "ValidationOutcome",
    "check_references",
    "validate_frame",
]
