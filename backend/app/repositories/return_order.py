"""Returns repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa

from app.models.return_order import Return
from app.repositories.base import OrgScopedRepository


class ReturnRepository(OrgScopedRepository[Return]):
    model = Return

    async def returned_order_refs(self) -> set[str]:
        """All order refs flagged as returned for this tenant.

        Returned as a set so the analytics engine can intersect it with whatever
        order refs survived the dashboard filters — the return rate then always
        matches the filtered order population exactly.
        """
        stmt = sa.select(Return.order_ref).where(
            sa.and_(
                Return.organization_id == self.organization_id,
                Return.returned.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result}

    async def returned_refs_with_dates(self) -> dict[str, date | None]:
        stmt = sa.select(Return.order_ref, Return.return_date).where(
            sa.and_(
                Return.organization_id == self.organization_id,
                Return.returned.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return {row.order_ref: row.return_date for row in result}

    async def existing_order_refs(self, refs: Sequence[str]) -> set[str]:
        if not refs:
            return set()
        stmt = sa.select(Return.order_ref).where(
            sa.and_(
                Return.organization_id == self.organization_id,
                Return.order_ref.in_(list(refs)),
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result}


__all__ = ["ReturnRepository"]
