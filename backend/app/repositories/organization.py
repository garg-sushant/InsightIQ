"""Organization repository — the one table that is not itself tenant-scoped."""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def get(self, organization_id: uuid.UUID) -> Organization | None:
        stmt = sa.select(Organization).where(Organization.id == organization_id)
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = sa.select(Organization).where(Organization.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        stmt = sa.select(sa.func.count()).select_from(Organization).where(
            Organization.slug == slug
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) > 0


__all__ = ["OrganizationRepository"]
