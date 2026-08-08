"""Audit trail payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import APIModel


class AuditLogOut(APIModel):
    id: uuid.UUID
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    user_id: uuid.UUID | None = None
    actor_email: str | None = None
    ip_address: str | None = None
    context: dict[str, Any] | None = None
    created_at: datetime


__all__ = ["AuditLogOut"]
