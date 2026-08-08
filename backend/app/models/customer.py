"""Customer master data, keyed on the tenant's own customer reference."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Customer(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        # The tenant's own key is unique *within* the tenant, never globally.
        sa.UniqueConstraint("organization_id", "customer_ref", name="uq_customers_org_ref"),
        sa.Index("ix_customers_org_segment", "organization_id", "segment"),
        sa.Index("ix_customers_org_region", "organization_id", "region"),
    )

    customer_ref: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    segment: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    region: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    state: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


__all__ = ["Customer"]
