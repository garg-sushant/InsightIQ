"""AI narrative, always tied to the AnalysisRun whose numbers it describes."""

from __future__ import annotations

import uuid
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


class InsightType(StrEnum):
    EXECUTIVE_SUMMARY = "executive_summary"
    ROOT_CAUSE = "root_cause"
    RECOMMENDATIONS = "recommendations"
    RISKS = "risks"


class AIInsight(UUIDPrimaryKeyMixin, OrganizationScopedMixin, TimestampMixin, Base):
    __tablename__ = "ai_insights"
    __table_args__ = (
        sa.UniqueConstraint(
            "analysis_run_id", "insight_type", name="uq_ai_insights_run_type"
        ),
        sa.Index("ix_ai_insights_org_created", "organization_id", "created_at"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight_type: Mapped[InsightType] = mapped_column(
        enum_column(InsightType, "ai_insight_type"), nullable=False
    )

    #: Rendered markdown/plain text for direct display.
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    #: Structured form when the insight has one (e.g. a list of recommendations
    #: with priority/impact/effort). Null for free-text insight types.
    structured: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)

    provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    model: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    #: True when this came from MockProvider or a degraded fallback rather than
    #: a live model. The UI labels these explicitly.
    is_fallback: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)

    tokens_prompt: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    tokens_completion: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)


__all__ = ["AIInsight", "InsightType"]
