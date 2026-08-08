"""Returns, recorded at order granularity (the Superstore convention).

A return marks a whole ``order_ref`` as returned; the return rate is therefore
returned orders / total orders, not returned lines / total lines.
"""

from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Return(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "returns"
    __table_args__ = (
        sa.UniqueConstraint("organization_id", "order_ref", name="uq_returns_org_order_ref"),
        sa.Index("ix_returns_org_return_date", "organization_id", "return_date"),
    )

    #: References Order.order_ref within the same organization. Kept as a
    #: business key rather than an FK because returns files routinely arrive
    #: before (or without) the matching orders file; referential integrity is
    #: enforced by the ingestion validator, which reports orphans as row errors.
    order_ref: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    returned: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    return_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    reason: Mapped[str | None] = mapped_column(sa.String(240), nullable=True)

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


__all__ = ["Return"]
