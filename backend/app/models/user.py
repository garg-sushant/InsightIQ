"""Users belong to exactly one organization.

Trade-off noted in the README: a single-org membership keeps login (email ->
user -> org) and every authorization check trivially simple. Supporting one
human across several workspaces would mean a join table and an explicit
"active workspace" in the token; that is deliberately out of scope.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import Role
from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
)

if TYPE_CHECKING:
    from app.models.organization import Organization


class User(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.Index("ix_users_org_role", "organization_id", "role"),
    )

    email: Mapped[str] = mapped_column(sa.String(320), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    role: Mapped[Role] = mapped_column(
        enum_column(Role, "user_role"), nullable=False, default=Role.VIEWER
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(back_populates="users", lazy="joined")


__all__ = ["User"]
