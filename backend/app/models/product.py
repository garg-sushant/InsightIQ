"""Product master data, keyed on the tenant's own product reference."""

from __future__ import annotations

import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Product(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        sa.UniqueConstraint("organization_id", "product_ref", name="uq_products_org_ref"),
        sa.Index("ix_products_org_category", "organization_id", "category"),
        sa.Index("ix_products_org_subcategory", "organization_id", "sub_category"),
    )

    product_ref: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(400), nullable=False)
    category: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    sub_category: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    #: List price. Order lines carry their own realised unit price, because
    #: historical lines must not move when the catalogue is re-priced.
    unit_price: Mapped[Decimal | None] = mapped_column(nullable=True)

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


__all__ = ["Product"]
