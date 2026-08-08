"""Shared pytest fixtures.

Tests run against in-memory SQLite via aiosqlite. The application models are
dialect-agnostic (see ``app.models.base.enum_column`` and the Numeric/JSON
type mapping), so this exercises the real ORM layer without requiring Docker.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

# Must be set before app.core.config is imported anywhere.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault(
    "SECRET_KEY", "test-only-secret-key-not-for-production-use-1234567890"
)
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.deps import get_db
from app.core.security import Role, hash_password
from app.db.base import target_metadata
from app.main import app
from app.models.customer import Customer
from app.models.order import Order
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(target_metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    # get_db calls get_session() directly rather than declaring it via Depends,
    # so FastAPI's override mechanism must target get_db itself — overriding
    # get_session here would silently have no effect.
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_org(db_session: AsyncSession):
    """One organization with an owner user, for tests that need a tenant."""
    organization = Organization(name="Acme Retail", slug="acme-retail")
    db_session.add(organization)
    await db_session.flush()

    user = User(
        organization_id=organization.id,
        email="owner@acme.example.com",
        full_name="Ada Owner",
        hashed_password=hash_password("Password123!"),
        role=Role.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return organization, user


async def make_order_fixture(
    session: AsyncSession,
    organization_id: uuid.UUID,
    *,
    n_customers: int = 5,
    n_products: int = 5,
) -> tuple[list[Customer], list[Product]]:
    customers = [
        Customer(
            organization_id=organization_id,
            customer_ref=f"C{i}",
            name=f"Customer {i}",
            segment="Consumer",
            region="East",
        )
        for i in range(n_customers)
    ]
    products = [
        Product(
            organization_id=organization_id,
            product_ref=f"P{i}",
            name=f"Product {i}",
            category="Office Supplies",
            sub_category="Binders",
            unit_price=Decimal("25.00"),
        )
        for i in range(n_products)
    ]
    session.add_all(customers)
    session.add_all(products)
    await session.flush()
    return customers, products


@pytest.fixture
def known_kpi_dataset():
    """A tiny, fully hand-computed dataset for deterministic KPI assertions.

    4 orders, 2 customers, 2 products, spanning two months:

    Jan: order A (2 lines): sales 100 + 200 = 300, profit 20 + 40 = 60
         order B (1 line):  sales 150, profit -10 (loss-making)
    Feb: order C (1 line):  sales 500, profit 100

    Expected (whole period, no filters):
      revenue = 300 + 150 + 500 = 950
      profit  = 60 - 10 + 100 = 150
      margin  = 150 / 950 * 100 = 15.789473...%
      orders  = 3 (A, B, C)
      units   = sum of quantities
      aov     = 950 / 3 = 316.666...
    """
    return {
        "expected_revenue": Decimal("950"),
        "expected_profit": Decimal("150"),
        "expected_orders": 3,
    }
