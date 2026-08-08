"""User repository.

Two access paths, deliberately separated:

* :meth:`get_by_email_global` is used *only* by login, which by definition has
  no tenant context yet.
* Everything else goes through the org-scoped methods, so member management can
  never touch another workspace's users.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role
from app.models.user import User
from app.repositories.base import OrgScopedRepository


class UserRepository(OrgScopedRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = self.scoped_select().where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def list_members(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[User]:
        return await self.list(limit=limit, offset=offset, order_by=User.created_at.asc())

    async def count_by_role(self, role: Role) -> int:
        return await self.count([User.role == role])


class UserAuthRepository:
    """Tenant-less lookups needed before a tenant is known.

    Kept as a separate class so an un-scoped ``select(User)`` cannot be reached
    by accident from ordinary member-management code.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email_global(self, email: str) -> User | None:
        stmt = sa.select(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def get_by_id_global(self, user_id: uuid.UUID) -> User | None:
        """Used by token verification, which carries the user id in ``sub``."""
        stmt = sa.select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def email_exists(self, email: str) -> bool:
        stmt = sa.select(sa.func.count()).select_from(User).where(User.email == email.lower())
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) > 0


__all__ = ["UserAuthRepository", "UserRepository"]
