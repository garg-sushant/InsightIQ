"""Customer repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from app.models.customer import Customer
from app.repositories.base import OrgScopedRepository


class CustomerRepository(OrgScopedRepository[Customer]):
    model = Customer

    async def ref_to_id_map(self, refs: Sequence[str] | None = None) -> dict[str, uuid.UUID]:
        """Business key -> surrogate id, for ingestion FK resolution."""
        stmt = sa.select(Customer.customer_ref, Customer.id).where(
            Customer.organization_id == self.organization_id
        )
        if refs is not None:
            if not refs:
                return {}
            stmt = stmt.where(Customer.customer_ref.in_(list(refs)))
        result = await self.session.execute(stmt)
        return {row.customer_ref: row.id for row in result}

    async def get_by_ref(self, customer_ref: str) -> Customer | None:
        stmt = self.scoped_select().where(Customer.customer_ref == customer_ref)
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def existing_refs(self, refs: Sequence[str]) -> set[str]:
        if not refs:
            return set()
        stmt = sa.select(Customer.customer_ref).where(
            sa.and_(
                Customer.organization_id == self.organization_id,
                Customer.customer_ref.in_(list(refs)),
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result}

    async def distinct_segments(self) -> list[str]:
        stmt = (
            sa.select(Customer.segment)
            .where(
                sa.and_(
                    Customer.organization_id == self.organization_id,
                    Customer.segment.is_not(None),
                )
            )
            .distinct()
            .order_by(Customer.segment)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result if row[0]]


__all__ = ["CustomerRepository"]
