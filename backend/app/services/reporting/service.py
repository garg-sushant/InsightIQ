"""Report orchestration.

Reports never depend on the AI layer being up: if narrative is unavailable, the
deterministic report is produced without it and the caller is told why.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.audit_log import AuditLogRepository
from app.schemas.report import ReportFormat, ReportRequest
from app.services.ai.service import AIService
from app.services.analytics.service import AnalyticsService
from app.services.reporting.charts import build_chart_set
from app.services.reporting.pdf import build_pdf
from app.services.reporting.pptx import build_pptx

logger = get_logger(__name__)

_CONTENT_TYPES = {
    ReportFormat.PDF: "application/pdf",
    ReportFormat.PPTX: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
}

_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class GeneratedReport:
    content: bytes
    filename: str
    content_type: str
    report_format: ReportFormat


class ReportService:
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id
        self.analytics = AnalyticsService(session, organization_id)
        self.ai = AIService(session, organization_id)
        self.audit = AuditLogRepository(session, organization_id)

    async def generate(
        self,
        request: ReportRequest,
        *,
        organization_name: str,
        user_id: uuid.UUID | None = None,
        actor_email: str | None = None,
    ) -> GeneratedReport:
        run, result = await self.analytics.get_run(request.analysis_run_id)

        insights = None
        if request.include_ai_narrative:
            # Reuse persisted narrative when present; never block the export on
            # a live generation call.
            insights = await self.ai.get_bundle(request.analysis_run_id)
            if insights is None:
                logger.info(
                    "report_without_narrative",
                    extra={"run_id": str(request.analysis_run_id)},
                )

        charts = build_chart_set(result) if request.include_charts else {}

        builder = build_pdf if request.format is ReportFormat.PDF else build_pptx
        content = builder(
            result=result,
            charts=charts,
            insights=insights,
            organization_name=organization_name,
            title=request.title,
            include_charts=request.include_charts,
        )

        filename = self._filename(
            organization_name, result.period.start.isoformat(),
            result.period.end.isoformat(), request.format,
        )

        await self.audit.record(
            action="report.export",
            resource_type="analysis_run",
            resource_id=str(run.id),
            user_id=user_id,
            actor_email=actor_email,
            context={"format": request.format.value, "size_bytes": len(content)},
        )
        await self.session.commit()

        return GeneratedReport(
            content=content,
            filename=filename,
            content_type=_CONTENT_TYPES[request.format],
            report_format=request.format,
        )

    @staticmethod
    def _filename(
        organization_name: str, start: str, end: str, report_format: ReportFormat
    ) -> str:
        slug = _UNSAFE_FILENAME.sub("-", organization_name).strip("-").lower()[:40]
        return f"insightiq-{slug or 'report'}-{start}-to-{end}.{report_format.value}"


__all__ = ["GeneratedReport", "ReportService"]
