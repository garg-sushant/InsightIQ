"""Order lines — the central fact table, on the Superstore retail shape.

One row is one *line* of an order (an order with three products is three rows,
all sharing ``order_ref``). Region / segment / category / sub_category are
denormalised onto the fact deliberately: they are the dimensions every
dashboard filter and breakdown touches, and keeping them here makes the whole
analytics engine a single-table scan with no joins on the hot path. Dimension
drift over time is a non-issue for a sales history that is loaded, not edited.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    Rate,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Order(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        # Idempotent re-uploads: the same source line never lands twice.
        sa.UniqueConstraint("organization_id", "line_ref", name="uq_orders_org_line_ref"),
        # The primary analytics access path.
        sa.Index("ix_orders_org_order_date", "organization_id", "order_date"),
        sa.Index("ix_orders_org_order_ref", "organization_id", "order_ref"),
        sa.Index("ix_orders_org_region", "organization_id", "region"),
        sa.Index("ix_orders_org_segment", "organization_id", "segment"),
        sa.Index("ix_orders_org_category", "organization_id", "category"),
        sa.Index("ix_orders_org_subcategory", "organization_id", "sub_category"),
        sa.Index("ix_orders_org_customer", "organization_id", "customer_id"),
        sa.Index("ix_orders_org_product", "organization_id", "product_id"),
        sa.CheckConstraint("quantity >= 0", name="ck_orders_quantity_non_negative"),
        sa.CheckConstraint("discount >= 0 AND discount <= 1", name="ck_orders_discount_range"),
    )

    #: Stable per-line business key from the source file (Superstore "Row ID").
    line_ref: Mapped[str] = mapped_column(sa.String(96), nullable=False)
    #: Groups lines into an order (Superstore "Order ID"). Not unique.
    order_ref: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    order_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    ship_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    ship_mode: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # --- Denormalised dimensions (see module docstring) --------------------
    region: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(sa.String(80), nullable=True)
    city: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    segment: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    sub_category: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)

    # --- Measures (exact numerics only) ------------------------------------
    quantity: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    unit_price: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    discount: Mapped[Decimal] = mapped_column(Rate, nullable=False, default=Decimal("0"))
    sales: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))
    profit: Mapped[Decimal] = mapped_column(nullable=False, default=Decimal("0"))

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


__all__ = ["Order"]
