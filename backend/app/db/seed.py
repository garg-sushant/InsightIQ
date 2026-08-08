"""Seed script: one demo organization with ~2 years of realistic Superstore-style
retail data. Run with: python -m app.db.seed (inside the backend container/venv).

Idempotent: re-running clears and regenerates the demo org only.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, hash_password
from app.db.session import SessionFactory, dispose_engine
from app.models.customer import Customer
from app.models.order import Order
from app.models.organization import Organization
from app.models.product import Product
from app.models.return_order import Return
from app.models.user import User

DEMO_SLUG = "demo-retail"
DEMO_EMAIL = "demo@insightiq.io"
DEMO_PASSWORD = "DemoPass123!"

REGIONS = ["East", "West", "Central", "South"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
CATEGORIES = {
    "Furniture": ["Bookcases", "Chairs", "Tables", "Furnishings"],
    "Office Supplies": ["Binders", "Paper", "Labels", "Storage", "Art"],
    "Technology": ["Phones", "Accessories", "Machines", "Copiers"],
}
SHIP_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]
STATES = ["California", "New York", "Texas", "Illinois", "Washington", "Ohio", "Florida"]

random.seed(20260807)

START_DATE = date.today() - timedelta(days=730)
END_DATE = date.today()


async def _clear_demo_org(session: AsyncSession, organization_id: uuid.UUID) -> None:
    for model in (Return, Order, Customer, Product, User):
        await session.execute(delete(model).where(model.organization_id == organization_id))
    await session.commit()


async def seed() -> None:
    async with SessionFactory() as session:
        result = await session.execute(select(Organization).where(Organization.slug == DEMO_SLUG))
        organization = result.scalar_one_or_none()
        if organization is None:
            organization = Organization(name="Demo Retail Co.", slug=DEMO_SLUG, industry="Retail")
            session.add(organization)
            await session.flush()
        else:
            await _clear_demo_org(session, organization.id)

        owner = User(
            organization_id=organization.id,
            email=DEMO_EMAIL,
            full_name="Demo Owner",
            hashed_password=hash_password(DEMO_PASSWORD),
            role=Role.OWNER,
            is_active=True,
        )
        session.add(owner)
        await session.flush()

        print(f"Seeding demo data for organization {organization.id} ({organization.slug})...")

        customers = [
            Customer(
                organization_id=organization.id,
                customer_ref=f"CUST-{i:04d}",
                name=f"Demo Customer {i}",
                segment=random.choice(SEGMENTS),
                country="United States",
                region=random.choice(REGIONS),
                state=random.choice(STATES),
                city="Springfield",
                postal_code=f"{random.randint(10000, 99999)}",
            )
            for i in range(1, 251)
        ]
        session.add_all(customers)
        await session.flush()

        products: list[Product] = []
        product_id = 1
        for category, sub_categories in CATEGORIES.items():
            for sub_category in sub_categories:
                for _ in range(random.randint(8, 14)):
                    price = Decimal(str(round(random.uniform(5, 2000), 2)))
                    products.append(
                        Product(
                            organization_id=organization.id,
                            product_ref=f"PROD-{product_id:04d}",
                            name=f"{sub_category} Item {product_id}",
                            category=category,
                            sub_category=sub_category,
                            unit_price=price,
                        )
                    )
                    product_id += 1
        session.add_all(products)
        await session.flush()

        # Deliberately biased demo economics: a slow margin decline over the
        # back half of the window and one clear revenue anomaly, so anomaly
        # detection and the AI narrative have something real to describe.
        anomaly_week_start = START_DATE + timedelta(days=int(730 * 0.7))
        anomaly_week_end = anomaly_week_start + timedelta(days=6)

        orders: list[Order] = []
        returns: list[Return] = []
        line_counter = 1
        order_counter = 1
        current_date = START_DATE

        while current_date <= END_DATE:
            progress = (current_date - START_DATE).days / 730
            # Gentle seasonal + growth trend so the trend chart is not a flat line.
            base_orders_today = 3 + int(2 * progress) + (3 if current_date.month in (11, 12) else 0)
            is_anomaly_week = anomaly_week_start <= current_date <= anomaly_week_end
            daily_orders = base_orders_today * (3 if is_anomaly_week else 1)

            for _ in range(daily_orders):
                order_ref = f"ORD-{order_counter:06d}"
                order_counter += 1
                customer = random.choice(customers)
                ship_mode = random.choice(SHIP_MODES)
                ship_date = current_date + timedelta(days=random.randint(1, 6))
                n_lines = random.randint(1, 4)

                margin_bias = -0.15 * max(0, progress - 0.5) * 2  # erodes after the halfway point

                for _ in range(n_lines):
                    product = random.choice(products)
                    quantity = random.randint(1, 8)
                    discount = Decimal(str(random.choice([0, 0, 0, 0.1, 0.15, 0.2, 0.3, 0.5])))
                    unit_price = product.unit_price or Decimal("50.00")
                    sales = (unit_price * quantity * (1 - discount)).quantize(Decimal("0.0001"))

                    base_margin = random.uniform(0.05, 0.35) + margin_bias
                    profit = (sales * Decimal(str(round(base_margin, 4)))).quantize(Decimal("0.0001"))

                    orders.append(
                        Order(
                            organization_id=organization.id,
                            line_ref=f"LINE-{line_counter:07d}",
                            order_ref=order_ref,
                            order_date=current_date,
                            ship_date=ship_date,
                            ship_mode=ship_mode,
                            customer_id=customer.id,
                            product_id=product.id,
                            region=customer.region,
                            country="United States",
                            state=customer.state,
                            city=customer.city,
                            segment=customer.segment,
                            category=product.category,
                            sub_category=product.sub_category,
                            quantity=quantity,
                            unit_price=unit_price.quantize(Decimal("0.0001")),
                            discount=discount,
                            sales=sales,
                            profit=profit,
                        )
                    )
                    line_counter += 1

                if random.random() < 0.045:
                    returns.append(
                        Return(
                            organization_id=organization.id,
                            order_ref=order_ref,
                            returned=True,
                            return_date=ship_date + timedelta(days=random.randint(1, 14)),
                            reason=random.choice(
                                ["Damaged in transit", "Wrong item", "No longer needed", "Defective"]
                            ),
                        )
                    )

            current_date += timedelta(days=1)

            if len(orders) >= 4000:
                session.add_all(orders)
                await session.flush()
                orders = []

        if orders:
            session.add_all(orders)
            await session.flush()
        if returns:
            session.add_all(returns)
            await session.flush()

        await session.commit()
        print(f"Seeded {order_counter - 1} orders, {line_counter - 1} order lines, {len(returns)} returns.")
        print(f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
