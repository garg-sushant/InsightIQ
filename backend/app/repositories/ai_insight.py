"""AIInsight repository."""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from app.models.ai_insight import AIInsight, InsightType
from app.repositories.base import OrgScopedRepository


class AIInsightRepository(OrgScopedRepository[AIInsight]):
    model = AIInsight

    async def list_for_run(self, analysis_run_id: uuid.UUID) -> list[AIInsight]:
        stmt = (
            self.scoped_select()
            .where(AIInsight.analysis_run_id == analysis_run_id)
            .order_by(AIInsight.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_for_run(
        self, analysis_run_id: uuid.UUID, insight_type: InsightType
    ) -> AIInsight | None:
        stmt = self.scoped_select().where(
            sa.and_(
                AIInsight.analysis_run_id == analysis_run_id,
                AIInsight.insight_type == insight_type,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().unique().one_or_none()

    async def delete_for_run(self, analysis_run_id: uuid.UUID) -> int:
        """Clears cached insights so a refresh regenerates them."""
        return await self.delete_where(AIInsight.analysis_run_id == analysis_run_id)


__all__ = ["AIInsightRepository"]
