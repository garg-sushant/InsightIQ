"""Report export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.deps import CurrentAuth, DbSession, require
from app.core.security import Permission
from app.schemas.report import ReportRequest
from app.services.reporting.service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post(
    "/export",
    dependencies=[require(Permission.REPORT_EXPORT)],
    summary="Export an analysis run as PDF or PPTX",
    response_class=Response,
)
async def export_report(
    payload: ReportRequest, auth: CurrentAuth, session: DbSession
) -> Response:
    service = ReportService(session, auth.organization_id)
    report = await service.generate(
        payload,
        organization_name=auth.organization.name,
        user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    return Response(
        content=report.content,
        media_type=report.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{report.filename}"',
            "Content-Length": str(len(report.content)),
        },
    )
