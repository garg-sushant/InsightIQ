"""An upload batch: one file, one entity type, one validation report."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
)


class EntityType(StrEnum):
    ORDERS = "orders"
    CUSTOMERS = "customers"
    PRODUCTS = "products"
    RETURNS = "returns"


class DatasetStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    #: Rows were accepted and written.
    INGESTED = "ingested"
    #: Some rows were rejected but the batch was still committed.
    PARTIAL = "partial"
    #: Nothing was written; the batch failed atomically.
    FAILED = "failed"


class Dataset(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (
        sa.Index("ix_datasets_org_entity_created", "organization_id", "entity_type", "created_at"),
        sa.Index("ix_datasets_org_status", "organization_id", "status"),
    )

    entity_type: Mapped[EntityType] = mapped_column(
        enum_column(EntityType, "dataset_entity_type"), nullable=False
    )
    status: Mapped[DatasetStatus] = mapped_column(
        enum_column(DatasetStatus, "dataset_status"),
        nullable=False,
        default=DatasetStatus.PENDING,
    )
    original_filename: Mapped[str] = mapped_column(sa.String(400), nullable=False)
    content_type: Mapped[str | None] = mapped_column(sa.String(160), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, index=True)

    rows_total: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    rows_accepted: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)

    #: Full structured ValidationReport (see schemas.dataset). Stored verbatim so
    #: the UI can render per-row error reasons long after the upload finished.
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)


__all__ = ["Dataset", "DatasetStatus", "EntityType"]
