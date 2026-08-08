"""Proves org A cannot read org B's data through the repository layer or any
HTTP endpoint. This is the enforcement test for the multi-tenant isolation
guarantee described in app.repositories.base.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, hash_password
from app.models.customer import Customer
from app.models.order import Order
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User
from app.repositories.customer import CustomerRepository
from app.repositories.dataset import DatasetRepository
from app.repositories.order import OrderRepository


async def _create_org_with_data(session: AsyncSession, name: str, slug: str):
    organization = Organization(name=name, slug=slug)
    session.add(organization)
    await session.flush()

    user = User(
        organization_id=organization.id,
        email=f"owner@{slug}.example.com",
        full_name="Owner",
        hashed_password=hash_password("Password123!"),
        role=Role.OWNER,
        is_active=True,
    )
    customer = Customer(
        organization_id=organization.id, customer_ref="C1", name="Secret Customer",
        segment="Consumer", region="East",
    )
    product = Product(
        organization_id=organization.id, product_ref="P1", name="Secret Product",
        category="Office Supplies", unit_price=Decimal("10.00"),
    )
    session.add_all([user, customer, product])
    await session.flush()

    order = Order(
        organization_id=organization.id, line_ref=f"{slug}-line-1", order_ref=f"{slug}-order-1",
        order_date=date(2024, 1, 10), customer_id=customer.id, product_id=product.id,
        region="East", segment="Consumer", category="Office Supplies",
        quantity=2, unit_price=Decimal("10.00"), discount=Decimal("0"),
        sales=Decimal("20.00"), profit=Decimal("5.00"),
    )
    session.add(order)
    await session.commit()
    return organization, user, customer, product, order


@pytest.mark.asyncio
async def test_repository_get_returns_none_across_tenants(db_session: AsyncSession) -> None:
    org_a, _, customer_a, _, order_a = await _create_org_with_data(db_session, "Org A", "org-a")
    org_b, _, _, _, _ = await _create_org_with_data(db_session, "Org B", "org-b")

    repo_b = CustomerRepository(db_session, org_b.id)
    # Fetching org A's customer id while scoped to org B must return None, not
    # the record and not an error that would leak existence.
    result = await repo_b.get(customer_a.id)
    assert result is None

    order_repo_b = OrderRepository(db_session, org_b.id)
    rows = await order_repo_b.fetch_fact_rows()
    assert all(row["order_ref"] != order_a.order_ref for row in rows)
    assert len(rows) == 1  # only org B's own order


@pytest.mark.asyncio
async def test_repository_list_never_crosses_tenants(db_session: AsyncSession) -> None:
    org_a, _, _, _, _ = await _create_org_with_data(db_session, "Org A", "org-a2")
    org_b, _, _, _, _ = await _create_org_with_data(db_session, "Org B", "org-b2")

    datasets_a = DatasetRepository(db_session, org_a.id)
    datasets_b = DatasetRepository(db_session, org_b.id)

    all_a = await datasets_a.list()
    all_b = await datasets_b.list()
    assert all(d.organization_id == org_a.id for d in all_a)
    assert all(d.organization_id == org_b.id for d in all_b)


@pytest.mark.asyncio
async def test_bulk_insert_stamps_correct_tenant(db_session: AsyncSession) -> None:
    org_a, _, _, _, _ = await _create_org_with_data(db_session, "Org A", "org-a3")
    org_b, _, _, _, _ = await _create_org_with_data(db_session, "Org B", "org-b3")

    repo_a = CustomerRepository(db_session, org_a.id)
    await repo_a.bulk_insert_mappings([{"customer_ref": "NEW1", "name": "New Customer"}])
    await db_session.commit()

    repo_b = CustomerRepository(db_session, org_b.id)
    found_in_b = await repo_b.get_by_ref("NEW1")
    assert found_in_b is None

    found_in_a = await repo_a.get_by_ref("NEW1")
    assert found_in_a is not None
    assert found_in_a.organization_id == org_a.id


@pytest.mark.asyncio
async def test_http_endpoints_cannot_cross_tenant_boundary(client: AsyncClient) -> None:
    """End-to-end: sign up two orgs, upload data to org A, verify org B's
    authenticated session sees zero rows and a 404 on org A's dataset id."""
    signup_a = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "owner@tenanta.example.com", "password": "Password123!",
            "full_name": "Owner A", "organization_name": "Tenant A",
        },
    )
    assert signup_a.status_code == 201
    token_a = signup_a.json()["tokens"]["access_token"]

    signup_b = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "owner@tenantb.example.com", "password": "Password123!",
            "full_name": "Owner B", "organization_name": "Tenant B",
        },
    )
    assert signup_b.status_code == 201
    token_b = signup_b.json()["tokens"]["access_token"]

    csv_content = (
        b"Order ID,Order Date,Customer ID,Customer Name,Product ID,Product Name,"
        b"Category,Sales,Quantity,Discount,Profit\n"
        b"ORD-1,1/5/2024,CUST-1,Test Customer,PROD-1,Test Product,"
        b"Office Supplies,100.00,2,0,20.00\n"
    )
    upload = await client.post(
        "/api/v1/datasets/upload/orders",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("orders.csv", csv_content, "text/csv")},
    )
    assert upload.status_code == 201
    dataset_id = upload.json()["dataset"]["id"]

    # Org B must see zero datasets of its own.
    list_b = await client.get(
        "/api/v1/datasets", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert list_b.status_code == 200
    assert list_b.json()["meta"]["total"] == 0

    # Org B must get 404, not org A's data, when requesting org A's dataset id.
    get_b = await client.get(
        f"/api/v1/datasets/{dataset_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert get_b.status_code == 404

    # Org A can see its own dataset.
    get_a = await client.get(
        f"/api/v1/datasets/{dataset_id}", headers={"Authorization": f"Bearer {token_a}"}
    )
    assert get_a.status_code == 200

    # Org B's inventory must show zero orders despite org A's upload.
    inventory_b = await client.get(
        "/api/v1/datasets/inventory", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert inventory_b.status_code == 200
    assert inventory_b.json()["orders"] == 0
