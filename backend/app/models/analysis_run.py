"""A frozen snapshot of deterministically-computed analytics.

Everything downstream — the dashboard, the AI narrative, the PDF and the PPTX —
reads from a persisted run, so a report can always be reproduced exactly and an
AI insight can always be traced back to the numbers it described.
"""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    OrganizationScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    enum_column,
)


class AnalysisStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRun(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        sa.Index("ix_analysis_runs_org_created", "organization_id", "created_at"),
        sa.Index("ix_analysis_runs_org_fingerprint", "organization_id", "filter_fingerprint"),
    )

    status: Mapped[AnalysisStatus] = mapped_column(
        enum_column(AnalysisStatus, "analysis_status"),
        nullable=False,
        default=AnalysisStatus.RUNNING,
    )

    period_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    period_end: Mapped[date] = mapped_column(sa.Date, nullable=False)
    comparison_start: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    comparison_end: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    #: The exact filter set that produced this run, plus a stable hash of it so
    #: repeated dashboard loads can reuse a recent run instead of recomputing.
    filters: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    filter_fingerprint: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    #: Headline KPI block, kept separate from ``result`` for cheap listing.
    kpis: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    #: The complete AnalyticsResult payload (breakdowns, series, anomalies...).
    result: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    #: Exactly what was handed to the AI layer. Persisted so the privacy
    #: boundary is auditable after the fact, not just at test time.
    ai_payload: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)

    source_row_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


__all__ = ["AnalysisRun", "AnalysisStatus"]
