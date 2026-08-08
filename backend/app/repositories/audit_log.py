"""Audit log repository (append-only in practice — no update method exists)."""

from __future__ import annotations

import uuid
from typing import Any

from app.models.audit_log import AuditLog
from app.repositories.base import OrgScopedRepository


class AuditLogRepository(OrgScopedRepository[AuditLog]):
    model = AuditLog

    async def record(
        self,
        *,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        user_id: uuid.UUID | None = None,
        actor_email: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actor_email=actor_email,
            ip_address=ip_address,
            user_agent=(user_agent or "")[:400] or None,
            context=context,
        )
        return await self.add(entry)

    async def list_recent(self, *, limit: int = 100, offset: int = 0) -> list[AuditLog]:
        return await self.list(limit=limit, offset=offset, order_by=AuditLog.created_at.desc())


__all__ = ["AuditLogRepository"]
