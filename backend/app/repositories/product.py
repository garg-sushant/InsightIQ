"""Product repository."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from app.models.product import Product
from app.repositories.base import OrgScopedRepository


class ProductRepository(OrgScopedRepository[Product]):
    model = Product

    async def ref_to_id_map(self, refs: Sequence[str] | None = None) -> dict[str, uuid.UUID]:
        stmt = sa.select(Product.product_ref, Product.id).where(
            Product.organization_id == self.organization_id
        )
        if refs is not None:
            if not refs:
                return {}
            stmt = stmt.where(Product.product_ref.in_(list(refs)))
        result = await self.session.execute(stmt)
        return {row.product_ref: row.id for row in result}

    async def get_by_ref(self, product_ref: str) -> Product | None:
        stmt = self.scoped_select().where(Product.product_ref == product_ref)
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def existing_refs(self, refs: Sequence[str]) -> set[str]:
        if not refs:
            return set()
        stmt = sa.select(Product.product_ref).where(
            sa.and_(
                Product.organization_id == self.organization_id,
                Product.product_ref.in_(list(refs)),
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result}

    async def id_to_meta_map(self) -> dict[uuid.UUID, dict[str, str | None]]:
        """Product id -> display metadata, used to label top/bottom product tables."""
        stmt = sa.select(
            Product.id, Product.product_ref, Product.name, Product.category, Product.sub_category
        ).where(Product.organization_id == self.organization_id)
        result = await self.session.execute(stmt)
        return {
            row.id: {
                "product_ref": row.product_ref,
                "name": row.name,
                "category": row.category,
                "sub_category": row.sub_category,
            }
            for row in result
        }

    async def distinct_categories(self) -> list[str]:
        stmt = (
            sa.select(Product.category)
            .where(
                sa.and_(
                    Product.organization_id == self.organization_id,
                    Product.category.is_not(None),
                )
            )
            .distinct()
            .order_by(Product.category)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result if row[0]]


__all__ = ["ProductRepository"]
