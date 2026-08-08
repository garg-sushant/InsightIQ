"""Order-line repository — the analytics data access path.

The analytics engine gets its rows from exactly one method here,
:meth:`OrderRepository.fetch_fact_rows`. Filtering and tenant scoping happen in
SQL; the shaping, aggregation and statistics happen in Pandas/NumPy on top of
that projection. One query, one code path, so a filter can never be applied to
the KPI cards but forgotten on the charts.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any, NamedTuple

import sqlalchemy as sa

from app.models.order import Order
from app.repositories.base import OrgScopedRepository

#: Columns pulled for analytics. Deliberately narrow — no free-text, no PII.
FACT_COLUMNS = (
    "order_date",
    "order_ref",
    "customer_id",
    "product_id",
    "region",
    "state",
    "segment",
    "category",
    "sub_category",
    "ship_mode",
    "quantity",
    "unit_price",
    "discount",
    "sales",
    "profit",
)


class DateBounds(NamedTuple):
    earliest: date | None
    latest: date | None


class OrderRepository(OrgScopedRepository[Order]):
    model = Order

    # -- analytics ----------------------------------------------------------
    def _filter_conditions(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        regions: Sequence[str] = (),
        categories: Sequence[str] = (),
        sub_categories: Sequence[str] = (),
        segments: Sequence[str] = (),
    ) -> list[Any]:
        conditions: list[Any] = []
        if date_from is not None:
            conditions.append(Order.order_date >= date_from)
        if date_to is not None:
            conditions.append(Order.order_date <= date_to)
        if regions:
            conditions.append(Order.region.in_(list(regions)))
        if categories:
            conditions.append(Order.category.in_(list(categories)))
        if sub_categories:
            conditions.append(Order.sub_category.in_(list(sub_categories)))
        if segments:
            conditions.append(Order.segment.in_(list(segments)))
        return conditions

    async def fetch_fact_rows(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        regions: Sequence[str] = (),
        categories: Sequence[str] = (),
        sub_categories: Sequence[str] = (),
        segments: Sequence[str] = (),
    ) -> list[dict[str, Any]]:
        """Return the filtered, tenant-scoped fact projection as plain dicts.

        Money stays as ``Decimal`` here; the analytics engine decides where
        exactness matters (KPI sums) and where float is fine (statistics, ML).
        """
        stmt = (
            sa.select(*(getattr(Order, name) for name in FACT_COLUMNS))
            .where(Order.organization_id == self.organization_id)
            .order_by(Order.order_date.asc())
        )
        conditions = self._filter_conditions(
            date_from=date_from,
            date_to=date_to,
            regions=regions,
            categories=categories,
            sub_categories=sub_categories,
            segments=segments,
        )
        if conditions:
            stmt = stmt.where(*conditions)

        result = await self.session.execute(stmt)
        return [dict(row._mapping) for row in result]

    async def date_bounds(self) -> DateBounds:
        stmt = sa.select(
            sa.func.min(Order.order_date), sa.func.max(Order.order_date)
        ).where(Order.organization_id == self.organization_id)
        result = await self.session.execute(stmt)
        earliest, latest = result.one()
        return DateBounds(earliest=earliest, latest=latest)

    async def distinct_values(self, column_name: str) -> list[str]:
        """Distinct values of a whitelisted dimension column, for filter menus."""
        allowed = {"region", "category", "sub_category", "segment", "state", "ship_mode"}
        if column_name not in allowed:
            raise ValueError(f"{column_name!r} is not a filterable dimension.")
        column = getattr(Order, column_name)
        stmt = (
            sa.select(column)
            .where(
                sa.and_(Order.organization_id == self.organization_id, column.is_not(None))
            )
            .distinct()
            .order_by(column)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result if row[0]]

    # -- ingestion support --------------------------------------------------
    async def existing_line_refs(self, refs: Sequence[str]) -> set[str]:
        if not refs:
            return set()
        stmt = sa.select(Order.line_ref).where(
            sa.and_(
                Order.organization_id == self.organization_id,
                Order.line_ref.in_(list(refs)),
            )
        )
        result = await self.session.execute(stmt)
        return {row[0] for row in result}

    async def existing_order_refs(self, refs: Sequence[str] | None = None) -> set[str]:
        """Used to validate that returns reference real orders."""
        stmt = sa.select(Order.order_ref).where(
            Order.organization_id == self.organization_id
        ).distinct()
        if refs is not None:
            if not refs:
                return set()
            stmt = stmt.where(Order.order_ref.in_(list(refs)))
        result = await self.session.execute(stmt)
        return {row[0] for row in result}

    async def customer_first_order_dates(self) -> dict[uuid.UUID, date]:
        """Each customer's first-ever order date across the tenant's whole history.

        Deliberately unfiltered: "new customer" is a fact about the customer,
        not about the dashboard's current date range. Filtering this by the
        selected window would label every returning customer as new.
        """
        stmt = (
            sa.select(Order.customer_id, sa.func.min(Order.order_date).label("first_order"))
            .where(Order.organization_id == self.organization_id)
            .group_by(Order.customer_id)
        )
        result = await self.session.execute(stmt)
        return {row.customer_id: row.first_order for row in result}

    async def customer_ids_in_use(self) -> set[uuid.UUID]:
        stmt = sa.select(Order.customer_id).where(
            Order.organization_id == self.organization_id
        ).distinct()
        result = await self.session.execute(stmt)
        return {row[0] for row in result}

    # -- summary ------------------------------------------------------------
    async def totals(self) -> dict[str, Decimal | int]:
        """Cheap org-wide totals for the data-inventory panel."""
        stmt = sa.select(
            sa.func.count().label("lines"),
            sa.func.count(sa.distinct(Order.order_ref)).label("orders"),
            sa.func.coalesce(sa.func.sum(Order.sales), 0).label("revenue"),
            sa.func.coalesce(sa.func.sum(Order.profit), 0).label("profit"),
        ).where(Order.organization_id == self.organization_id)
        result = await self.session.execute(stmt)
        row = result.one()
        return {
            "lines": int(row.lines),
            "orders": int(row.orders),
            "revenue": Decimal(str(row.revenue)),
            "profit": Decimal(str(row.profit)),
        }


__all__ = ["FACT_COLUMNS", "DateBounds", "OrderRepository"]
