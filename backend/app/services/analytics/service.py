"""Analytics orchestration.

One entry point, :meth:`AnalyticsService.run`, which:

1. resolves the reporting window and its comparison window,
2. pulls a single tenant-scoped, filtered projection from the database,
3. computes every metric deterministically from that one projection,
4. persists the result as an :class:`AnalysisRun` so reports and AI narrative
   can be tied back to exactly these numbers.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientDataError, NotFoundError
from app.core.logging import get_logger
from app.models.analysis_run import AnalysisRun, AnalysisStatus
from app.repositories.analysis_run import AnalysisRunRepository
from app.repositories.customer import CustomerRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.return_order import ReturnRepository
from app.schemas.analytics import (
    AnalyticsFilters,
    AnalyticsResult,
    Breakdown,
    ComparisonMode,
    FilterOptionsOut,
    Granularity,
    PeriodInfo,
    ReturnsView,
    TimeSeries,
)
from app.schemas.dataset import DataInventoryOut
from app.services.analytics.anomalies import detect_anomalies
from app.services.analytics.breakdowns import (
    build_all_breakdowns,
    build_breakdown,
    build_product_performance,
)
from app.services.analytics.frame import build_frame, slice_period
from app.services.analytics.kpis import build_kpi_set, compute_core_metrics
from app.services.analytics.numeric import ZERO, decimal_sum, money, rate, ratio_pct
from app.services.analytics.risk import build_business_health, build_risk_indicators
from app.services.analytics.segmentation import segment_customers
from app.services.analytics.timeseries import (
    build_timeseries,
    choose_anomaly_granularity,
)

logger = get_logger(__name__)

#: A completed run with the same fingerprint younger than this is reused rather
#: than recomputed, so flipping between dashboard tabs is instant.
RUN_CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class ResolvedPeriod:
    start: date
    end: date
    comparison_start: date | None
    comparison_end: date | None
    mode: ComparisonMode

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


class AnalyticsService:
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id
        self.orders = OrderRepository(session, organization_id)
        self.returns = ReturnRepository(session, organization_id)
        self.products = ProductRepository(session, organization_id)
        self.customers = CustomerRepository(session, organization_id)
        self.runs = AnalysisRunRepository(session, organization_id)

    # -- public API ---------------------------------------------------------
    async def run(
        self,
        filters: AnalyticsFilters,
        *,
        user_id: uuid.UUID | None = None,
        use_cache: bool = True,
    ) -> tuple[AnalysisRun, AnalyticsResult]:
        """Compute (or reuse) an analysis for the given filters."""
        fingerprint = self.fingerprint(filters)

        if use_cache:
            cached = await self.runs.find_fresh_by_fingerprint(
                fingerprint, max_age_seconds=RUN_CACHE_TTL_SECONDS
            )
            if cached is not None and cached.result is not None:
                logger.info("analysis_cache_hit", extra={"run_id": str(cached.id)})
                return cached, AnalyticsResult.model_validate(cached.result)

        started = time.perf_counter()
        result = await self.compute(filters)

        run = AnalysisRun(
            status=AnalysisStatus.COMPLETED,
            period_start=result.period.start,
            period_end=result.period.end,
            comparison_start=result.period.comparison_start,
            comparison_end=result.period.comparison_end,
            filters=filters.model_dump(mode="json"),
            filter_fingerprint=fingerprint,
            kpis=result.kpis.model_dump(mode="json"),
            result=result.model_dump(mode="json"),
            source_row_count=result.row_count,
            duration_ms=int((time.perf_counter() - started) * 1000),
            created_by_user_id=user_id,
        )
        await self.runs.add(run)
        await self.session.commit()
        logger.info(
            "analysis_complete",
            extra={"run_id": str(run.id), "rows": result.row_count,
                   "duration_ms": run.duration_ms},
        )
        return run, result

    async def get_run(self, run_id: uuid.UUID) -> tuple[AnalysisRun, AnalyticsResult]:
        run = await self.runs.get(run_id)
        if run is None:
            raise NotFoundError("Analysis run not found.")
        if run.result is None:
            raise NotFoundError("This analysis run has no stored result.")
        return run, AnalyticsResult.model_validate(run.result)

    async def compute(self, filters: AnalyticsFilters) -> AnalyticsResult:
        """The deterministic pipeline. No persistence, no AI, no HTTP."""
        period = await self._resolve_period(filters)

        # One query covering the reporting window *and* its comparison window;
        # the two frames are then sliced from the same projection.
        fetch_start = period.comparison_start or period.start
        rows = await self.orders.fetch_fact_rows(
            date_from=fetch_start,
            date_to=period.end,
            regions=filters.regions,
            categories=filters.categories,
            sub_categories=filters.sub_categories,
            segments=filters.segments,
        )
        full_frame = build_frame(rows)
        current_frame = slice_period(full_frame, period.start, period.end)

        comparison_frame: pd.DataFrame | None = None
        if period.comparison_start and period.comparison_end:
            comparison_frame = slice_period(
                full_frame, period.comparison_start, period.comparison_end
            )
            if comparison_frame.empty:
                comparison_frame = None

        returned_refs = await self.returns.returned_order_refs()
        first_order_dates = await self.orders.customer_first_order_dates()
        product_meta = await self.products.id_to_meta_map()

        current_metrics = compute_core_metrics(
            current_frame,
            returned_order_refs=returned_refs,
            customer_first_order=first_order_dates,
            period_start=period.start,
        )
        previous_metrics = (
            compute_core_metrics(
                comparison_frame,
                returned_order_refs=returned_refs,
                customer_first_order=first_order_dates,
                period_start=period.comparison_start or period.start,
            )
            if comparison_frame is not None
            else None
        )

        timeseries = build_timeseries(current_frame, filters.granularity)
        breakdowns = build_all_breakdowns(
            current_frame, comparison_frame=comparison_frame, top_n=filters.top_n
        )
        top_products, bottom_products = build_product_performance(
            current_frame, product_meta, top_n=filters.top_n
        )
        anomalies = detect_anomalies(
            current_frame, choose_anomaly_granularity(period.days)
        )
        rfm = segment_customers(current_frame, period.end)
        returns_view = self._build_returns_view(
            current_frame, returned_refs, filters.granularity
        )
        indicators = build_risk_indicators(
            frame=current_frame,
            current=current_metrics,
            previous=previous_metrics,
            timeseries=timeseries,
        )

        return AnalyticsResult(
            period=PeriodInfo(
                start=period.start,
                end=period.end,
                days=period.days,
                comparison_start=period.comparison_start,
                comparison_end=period.comparison_end,
                comparison_mode=period.mode,
            ),
            filters=filters,
            row_count=len(current_frame),
            kpis=build_kpi_set(current_metrics, previous_metrics),
            timeseries=timeseries,
            breakdowns=breakdowns,
            top_products=top_products,
            bottom_products=bottom_products,
            anomalies=anomalies,
            rfm=rfm,
            returns=returns_view,
            health=build_business_health(indicators),
            computed_at=datetime.now(UTC),
        )

    async def filter_options(self) -> FilterOptionsOut:
        bounds = await self.orders.date_bounds()
        return FilterOptionsOut(
            regions=await self.orders.distinct_values("region"),
            categories=await self.orders.distinct_values("category"),
            sub_categories=await self.orders.distinct_values("sub_category"),
            segments=await self.orders.distinct_values("segment"),
            date_min=bounds.earliest,
            date_max=bounds.latest,
        )

    async def inventory(self) -> DataInventoryOut:
        bounds = await self.orders.date_bounds()
        orders_count = await self.orders.count()
        return DataInventoryOut(
            orders=orders_count,
            customers=await self.customers.count(),
            products=await self.products.count(),
            returns=await self.returns.count(),
            earliest_order_date=bounds.earliest.isoformat() if bounds.earliest else None,
            latest_order_date=bounds.latest.isoformat() if bounds.latest else None,
            has_data=orders_count > 0,
        )

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def fingerprint(filters: AnalyticsFilters) -> str:
        """Stable hash of a filter set, used for run reuse."""
        payload = json.dumps(filters.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _resolve_period(self, filters: AnalyticsFilters) -> ResolvedPeriod:
        bounds = await self.orders.date_bounds()
        if bounds.earliest is None or bounds.latest is None:
            raise InsufficientDataError(
                "No orders have been uploaded yet. Upload an orders file to see analytics."
            )

        start = filters.date_from or bounds.earliest
        end = filters.date_to or bounds.latest
        if start > end:
            start, end = end, start
        # Clamp to the data we actually have, so an over-wide range does not
        # produce a trend line padded with meaningless empty periods.
        start = max(start, bounds.earliest)
        end = min(end, bounds.latest)

        comparison_start: date | None = None
        comparison_end: date | None = None
        span = (end - start).days + 1

        if filters.comparison is ComparisonMode.PREVIOUS_PERIOD:
            comparison_end = start - timedelta(days=1)
            comparison_start = comparison_end - timedelta(days=span - 1)
        elif filters.comparison is ComparisonMode.PREVIOUS_YEAR:
            comparison_start = _shift_year(start)
            comparison_end = _shift_year(end)

        # A comparison window entirely before the first order is not a
        # comparison, it is a fabricated zero. Drop it instead.
        if comparison_end is not None and comparison_end < bounds.earliest:
            comparison_start = comparison_end = None

        return ResolvedPeriod(
            start=start,
            end=end,
            comparison_start=comparison_start,
            comparison_end=comparison_end,
            mode=filters.comparison
            if comparison_start is not None
            else ComparisonMode.NONE,
        )

    @staticmethod
    def _build_returns_view(
        frame: pd.DataFrame,
        returned_refs: set[str],
        granularity: Granularity,
    ) -> ReturnsView:
        if frame.empty:
            return ReturnsView(
                returned_orders=0,
                total_orders=0,
                return_rate_pct=0.0,
                revenue_at_risk=0.0,
            )

        order_refs = set(frame["order_ref"].astype(str))
        returned_in_period = order_refs & returned_refs
        returned_mask = frame["order_ref"].astype(str).isin(returned_in_period)
        returned_frame = frame[returned_mask]

        by_category: Breakdown = build_breakdown(returned_frame, "category")
        by_region: Breakdown = build_breakdown(returned_frame, "region")
        trend: TimeSeries = build_timeseries(returned_frame, granularity)

        return ReturnsView(
            returned_orders=len(returned_in_period),
            total_orders=len(order_refs),
            return_rate_pct=rate(
                ratio_pct(Decimal(len(returned_in_period)), Decimal(len(order_refs))) or ZERO
            ),
            revenue_at_risk=money(decimal_sum(returned_frame["sales"])),
            by_category=by_category.items,
            by_region=by_region.items,
            trend=trend.points,
        )


def _shift_year(value: date) -> date:
    """Same calendar date one year earlier, tolerating 29 February."""
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


__all__ = ["RUN_CACHE_TTL_SECONDS", "AnalyticsService", "ResolvedPeriod"]
