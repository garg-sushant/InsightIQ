"""Repository base classes.

``OrgScopedRepository`` is the single chokepoint for multi-tenant isolation.
Every read it performs is filtered by ``organization_id``, and every write it
performs stamps ``organization_id`` onto the entity — a caller cannot forget,
because the caller never gets to supply it.

Rules enforced elsewhere by review and tests:

* Routes never build queries. They call services; services call repositories.
* No module outside ``app/repositories`` may ``select()`` a tenant-owned model.
* ``tests/test_tenant_isolation.py`` proves org A cannot reach org B's data
  through any endpoint.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.base import Base, OrganizationScopedMixin

ModelT = TypeVar("ModelT", bound=Base)
ScopedModelT = TypeVar("ScopedModelT", bound=OrganizationScopedMixin)


class BaseRepository(Generic[ModelT]):
    """Un-scoped repository. Only legal for tables with no tenant (Organization)."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def add_all(self, entities: Sequence[ModelT]) -> None:
        self.session.add_all(list(entities))
        await self.session.flush()

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()


class OrgScopedRepository(Generic[ScopedModelT]):
    """Base for every repository over tenant-owned data."""

    model: type[ScopedModelT]

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        if organization_id is None:  # pragma: no cover - defensive
            raise ValueError("organization_id is required for a tenant-scoped repository.")
        self.session = session
        self.organization_id = organization_id

    # -- query construction -------------------------------------------------
    @property
    def _entity(self) -> Any:
        return self.model

    def scoped_select(self) -> Select[Any]:
        """Start every read here. Never call ``sa.select(Model)`` directly."""
        return sa.select(self._entity).where(
            self._entity.organization_id == self.organization_id
        )

    def _scoped_where(self, *conditions: Any) -> Any:
        return sa.and_(
            self._entity.organization_id == self.organization_id,
            *conditions,
        )

    # -- reads --------------------------------------------------------------
    async def get(self, entity_id: uuid.UUID) -> ScopedModelT | None:
        """Fetch by id *within this tenant*.

        A cross-tenant id returns ``None``, so callers naturally produce a 404
        rather than leaking the existence of another org's record via a 403.
        """
        stmt = self.scoped_select().where(self._entity.id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        order_by: Any | None = None,
        conditions: Sequence[Any] = (),
    ) -> list[ScopedModelT]:
        stmt = self.scoped_select()
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(order_by if order_by is not None else self._entity.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count(self, conditions: Sequence[Any] = ()) -> int:
        stmt = sa.select(sa.func.count()).select_from(self._entity).where(
            self._entity.organization_id == self.organization_id
        )
        if conditions:
            stmt = stmt.where(*conditions)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def exists(self, conditions: Sequence[Any] = ()) -> bool:
        return await self.count(conditions) > 0

    # -- writes -------------------------------------------------------------
    async def add(self, entity: ScopedModelT) -> ScopedModelT:
        """Add an entity, forcing it into this tenant.

        Overwriting rather than validating is deliberate: it makes writing a
        row into the wrong organization structurally impossible from service
        code, instead of merely detectable.
        """
        entity.organization_id = self.organization_id
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def add_all(self, entities: Sequence[ScopedModelT]) -> None:
        for entity in entities:
            entity.organization_id = self.organization_id
        self.session.add_all(list(entities))
        await self.session.flush()

    async def bulk_insert_mappings(self, rows: Sequence[dict[str, Any]]) -> int:
        """Fast path for ingestion. Stamps the tenant on every mapping."""
        if not rows:
            return 0
        payload = [{**row, "organization_id": self.organization_id} for row in rows]
        await self.session.execute(sa.insert(self._entity), payload)
        return len(payload)

    async def delete(self, entity: ScopedModelT) -> None:
        if entity.organization_id != self.organization_id:  # pragma: no cover - defensive
            raise PermissionError("Refusing to delete an entity from another organization.")
        await self.session.delete(entity)
        await self.session.flush()

    async def delete_where(self, *conditions: Any) -> int:
        stmt = sa.delete(self._entity).where(self._scoped_where(*conditions))
        result = await self.session.execute(stmt)
        return int(result.rowcount or 0)

    # -- transaction --------------------------------------------------------
    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


__all__ = ["BaseRepository", "OrgScopedRepository"]
