"""Declarative base, shared column types, and reusable mixins."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB where available (indexable, typed), plain JSON on SQLite for tests.
JSONColumn = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

# Money and other exact quantities. Never float — 0.1 + 0.2 problems in a
# financial dashboard are indistinguishable from bugs in the analytics engine.
MONEY_PRECISION = 16
MONEY_SCALE = 4
Money = sa.Numeric(MONEY_PRECISION, MONEY_SCALE)
Rate = sa.Numeric(9, 6)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Root declarative class.

    ``type_annotation_map`` means a bare ``Mapped[Decimal]`` gets exact numeric
    storage and ``Mapped[dict]`` gets JSONB, without repeating the type on every
    column.
    """

    type_annotation_map = {
        Decimal: Money,
        dict[str, Any]: JSONColumn,
        list[dict[str, Any]]: JSONColumn,
        datetime: sa.DateTime(timezone=True),
        uuid.UUID: sa.Uuid(as_uuid=True),
    }

    def __repr__(self) -> str:  # pragma: no cover - debugging affordance
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


class UUIDPrimaryKeyMixin:
    """Opaque, non-enumerable primary keys.

    Sequential integer ids leak volume and invite IDOR probing; every public
    identifier in InsightIQ is a UUID.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.func.now(),
    )


class OrganizationScopedMixin:
    """Marks a table as tenant-owned.

    Presence of this mixin is what ``OrgScopedRepository`` keys off; every model
    that carries business data must use it so no table can quietly escape
    tenant filtering.
    """

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


def enum_column(
    values: type[Any],
    name: str,
    **kwargs: Any,
) -> sa.Enum:
    """A VARCHAR + CHECK constraint enum.

    ``native_enum=False`` keeps migrations simple (no ``ALTER TYPE`` dance) and
    lets the same models run on SQLite in the test suite.
    """
    return sa.Enum(
        values,
        name=name,
        native_enum=False,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
        validate_strings=True,
        **kwargs,
    )


__all__ = [
    "Base",
    "JSONColumn",
    "Money",
    "OrganizationScopedMixin",
    "Rate",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "enum_column",
    "utcnow",
]
