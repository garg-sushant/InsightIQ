"""AnalysisRun repository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from app.models.analysis_run import AnalysisRun, AnalysisStatus
from app.repositories.base import OrgScopedRepository


class AnalysisRunRepository(OrgScopedRepository[AnalysisRun]):
    model = AnalysisRun

    async def latest_completed(self) -> AnalysisRun | None:
        stmt = (
            self.scoped_select()
            .where(AnalysisRun.status == AnalysisStatus.COMPLETED)
            .order_by(AnalysisRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().unique().first()

    async def find_fresh_by_fingerprint(
        self, fingerprint: str, *, max_age_seconds: int
    ) -> AnalysisRun | None:
        """Reuse a recent identical run instead of recomputing on every page load."""
        cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
        stmt = (
            self.scoped_select()
            .where(
                sa.and_(
                    AnalysisRun.filter_fingerprint == fingerprint,
                    AnalysisRun.status == AnalysisStatus.COMPLETED,
                    AnalysisRun.created_at >= cutoff,
                )
            )
            .order_by(AnalysisRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().unique().first()

    async def list_recent(self, *, limit: int = 20, offset: int = 0) -> list[AnalysisRun]:
        return await self.list(
            limit=limit, offset=offset, order_by=AnalysisRun.created_at.desc()
        )


__all__ = ["AnalysisRunRepository"]
