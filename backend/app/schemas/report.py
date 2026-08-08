"""Report export payloads."""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import Field

from app.schemas.common import APIModel


class ReportFormat(StrEnum):
    PDF = "pdf"
    PPTX = "pptx"


class ReportRequest(APIModel):
    analysis_run_id: uuid.UUID
    format: ReportFormat = ReportFormat.PDF
    title: str | None = Field(default=None, max_length=160)
    #: Include the AI narrative sections. Off => a purely deterministic report,
    #: which is also what you get automatically when the AI layer is degraded.
    include_ai_narrative: bool = True
    include_charts: bool = True


class ReportMetaOut(APIModel):
    filename: str
    content_type: str
    size_bytes: int
    format: ReportFormat


__all__ = ["ReportFormat", "ReportMetaOut", "ReportRequest"]
