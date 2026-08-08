"""Dataset (upload batch) repository."""

from __future__ import annotations

import sqlalchemy as sa

from app.models.dataset import Dataset, DatasetStatus, EntityType
from app.repositories.base import OrgScopedRepository


class DatasetRepository(OrgScopedRepository[Dataset]):
    model = Dataset

    async def list_for_org(
        self,
        *,
        entity_type: EntityType | None = None,
        status: DatasetStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Dataset]:
        conditions = []
        if entity_type is not None:
            conditions.append(Dataset.entity_type == entity_type)
        if status is not None:
            conditions.append(Dataset.status == status)
        return await self.list(
            limit=limit,
            offset=offset,
            order_by=Dataset.created_at.desc(),
            conditions=conditions,
        )

    async def count_for_org(
        self,
        *,
        entity_type: EntityType | None = None,
        status: DatasetStatus | None = None,
    ) -> int:
        conditions = []
        if entity_type is not None:
            conditions.append(Dataset.entity_type == entity_type)
        if status is not None:
            conditions.append(Dataset.status == status)
        return await self.count(conditions)

    async def find_by_checksum(
        self, checksum: str, entity_type: EntityType
    ) -> Dataset | None:
        """Detects a byte-identical re-upload so the UI can warn about it."""
        stmt = self.scoped_select().where(
            sa.and_(
                Dataset.checksum_sha256 == checksum,
                Dataset.entity_type == entity_type,
                Dataset.status.in_([DatasetStatus.INGESTED, DatasetStatus.PARTIAL]),
            )
        ).order_by(Dataset.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().unique().first()


__all__ = ["DatasetRepository"]
