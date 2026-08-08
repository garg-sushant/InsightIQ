"""Async engine + session factory.

Routes never touch this module directly; they depend on ``app.core.deps.get_db``,
which yields a session that the service layer receives.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _engine_kwargs(url: str) -> dict[str, Any]:
    # SQLite (used by the test suite) rejects pool sizing arguments.
    if url.startswith("sqlite"):
        return {"echo": settings.db_echo, "future": True}
    return {
        "echo": settings.db_echo,
        "future": True,
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }


engine: AsyncEngine = create_async_engine(
    settings.database_url, **_engine_kwargs(settings.database_url)
)

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a session, rolling back on any exception escaping the request."""
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()


__all__ = ["SessionFactory", "dispose_engine", "engine", "get_session"]
