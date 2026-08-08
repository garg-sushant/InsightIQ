"""Append-only record of security- and data-relevant actions."""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class AuditLog(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        sa.Index("ix_audit_logs_org_created", "organization_id", "created_at"),
        sa.Index("ix_audit_logs_org_action", "organization_id", "action"),
    )

    #: Dotted verb, e.g. "dataset.upload", "auth.login", "member.role_assign".
    action: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #: Denormalised so the trail survives user deletion.
    actor_email: Mapped[str | None] = mapped_column(sa.String(320), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(sa.String(400), nullable=True)
    #: Never store request bodies here — only non-sensitive context.
    context: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)


__all__ = ["AuditLog"]
