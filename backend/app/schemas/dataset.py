"""Ingestion payloads: the structured validation report and dataset records."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.models.dataset import DatasetStatus, EntityType
from app.schemas.common import APIModel

#: Per-row errors are capped in the persisted report so one catastrophically
#: malformed 500k-row upload cannot bloat the database or the UI response.
MAX_REPORTED_ROW_ERRORS = 500


class ErrorSeverity(StrEnum):
    #: The row is dropped; the rest of the batch still commits.
    ROW = "row"
    #: The whole batch is rejected atomically (e.g. a required column missing).
    CRITICAL = "critical"
    #: Accepted, but worth surfacing (e.g. a value was coerced).
    WARNING = "warning"


class RowError(APIModel):
    row_number: int = Field(description="1-based row number in the source file, header excluded.")
    column: str | None = None
    error_type: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ROW
    value: str | None = Field(
        default=None,
        description="The offending value, truncated. Present so users can find the cell.",
    )


class ColumnReport(APIModel):
    name: str
    present: bool
    required: bool
    inferred_type: str | None = None
    null_count: int = 0
    error_count: int = 0


class ValidationReport(APIModel):
    """Everything the UI needs to explain what happened to an upload."""

    entity_type: EntityType
    is_valid: bool = Field(description="False when the batch was rejected atomically.")
    rows_total: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    duplicate_keys_dropped: int = 0

    missing_required_columns: list[str] = Field(default_factory=list)
    unexpected_columns: list[str] = Field(default_factory=list)
    columns: list[ColumnReport] = Field(default_factory=list)

    errors: list[RowError] = Field(
        default_factory=list,
        description=f"Capped at {MAX_REPORTED_ROW_ERRORS} entries; see error_counts for totals.",
    )
    error_counts: dict[str, int] = Field(
        default_factory=dict, description="Error type -> number of affected rows."
    )
    errors_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)

    #: Foreign-key style checks, e.g. returns referencing unknown orders.
    referential_issues: dict[str, int] = Field(default_factory=dict)


class DatasetOut(APIModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    entity_type: EntityType
    status: DatasetStatus
    original_filename: str
    file_size_bytes: int
    rows_total: int
    rows_accepted: int
    rows_rejected: int
    error_message: str | None = None
    uploaded_by_user_id: uuid.UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None


class DatasetDetailOut(DatasetOut):
    validation_report: dict[str, Any] | None = None


class UploadResponse(APIModel):
    dataset: DatasetOut
    report: ValidationReport


class EntitySchemaColumn(APIModel):
    name: str
    required: bool
    data_type: str
    description: str
    aliases: list[str] = Field(default_factory=list)


class EntitySchemaOut(APIModel):
    """Documents the expected upload shape so the UI can render a template guide."""

    entity_type: EntityType
    columns: list[EntitySchemaColumn]
    primary_key: list[str]


class DataInventoryOut(APIModel):
    """Row counts per entity — drives the dashboard's empty state."""

    orders: int
    customers: int
    products: int
    returns: int
    earliest_order_date: str | None = None
    latest_order_date: str | None = None
    has_data: bool


__all__ = [
    "MAX_REPORTED_ROW_ERRORS",
    "ColumnReport",
    "DataInventoryOut",
    "DatasetDetailOut",
    "DatasetOut",
    "EntitySchemaColumn",
    "EntitySchemaOut",
    "ErrorSeverity",
    "RowError",
    "UploadResponse",
    "ValidationReport",
]
