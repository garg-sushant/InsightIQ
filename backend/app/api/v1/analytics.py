"""Analytics endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentAuth, DbSession, require
from app.core.security import Permission
from app.schemas.analytics import (
    AnalysisRunDetailOut,
    AnalysisRunOut,
    AnalyticsFilters,
    AnalyticsResult,
    ComparisonMode,
    FilterOptionsOut,
    Granularity,
)
from app.schemas.common import Page, PageMeta
from app.services.analytics.service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/filter-options",
    response_model=FilterOptionsOut,
    dependencies=[require(Permission.ANALYTICS_READ)],
    summary="Distinct dimension values for filter menus",
)
async def filter_options(auth: CurrentAuth, session: DbSession) -> FilterOptionsOut:
    service = AnalyticsService(session, auth.organization_id)
    return await service.filter_options()


@router.post(
    "/run",
    response_model=AnalysisRunDetailOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require(Permission.ANALYTICS_RUN)],
    summary="Compute (or reuse) an analysis for the given filters",
)
async def run_analysis(
    filters: AnalyticsFilters, auth: CurrentAuth, session: DbSession
) -> AnalysisRunDetailOut:
    service = AnalyticsService(session, auth.organization_id)
    run, result = await service.run(filters, user_id=auth.user.id)
    return AnalysisRunDetailOut(
        id=run.id,
        organization_id=run.organization_id,
        status=run.status,
        period_start=run.period_start,
        period_end=run.period_end,
        comparison_start=run.comparison_start,
        comparison_end=run.comparison_end,
        source_row_count=run.source_row_count,
        duration_ms=run.duration_ms,
        created_at=run.created_at,
        created_by_user_id=run.created_by_user_id,
        error_message=run.error_message,
        result=result,
    )


@router.get(
    "/runs",
    response_model=Page[AnalysisRunOut],
    dependencies=[require(Permission.ANALYTICS_READ)],
    summary="Recent analysis runs",
)
async def list_runs(
    auth: CurrentAuth,
    session: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> Page[AnalysisRunOut]:
    service = AnalyticsService(session, auth.organization_id)
    runs = await service.runs.list_recent(limit=limit, offset=offset)
    total = await service.runs.count()
    return Page[AnalysisRunOut](
        items=[AnalysisRunOut.model_validate(run) for run in runs],
        meta=PageMeta(total=total, limit=limit, offset=offset, has_more=offset + len(runs) < total),
    )


@router.get(
    "/runs/{run_id}",
    response_model=AnalysisRunDetailOut,
    dependencies=[require(Permission.ANALYTICS_READ)],
    summary="A stored analysis run with its full result",
)
async def get_run(
    run_id: uuid.UUID, auth: CurrentAuth, session: DbSession
) -> AnalysisRunDetailOut:
    service = AnalyticsService(session, auth.organization_id)
    run, result = await service.get_run(run_id)
    return AnalysisRunDetailOut(
        id=run.id,
        organization_id=run.organization_id,
        status=run.status,
        period_start=run.period_start,
        period_end=run.period_end,
        comparison_start=run.comparison_start,
        comparison_end=run.comparison_end,
        source_row_count=run.source_row_count,
        duration_ms=run.duration_ms,
        created_at=run.created_at,
        created_by_user_id=run.created_by_user_id,
        error_message=run.error_message,
        result=result,
    )


# Re-exported so the frontend / OpenAPI schema documents the enums directly
# on this router's module without an extra import hop.
__all__ = ["router", "ComparisonMode", "Granularity", "AnalyticsResult"]
