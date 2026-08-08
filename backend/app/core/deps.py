"""FastAPI dependencies: DB session, current user, tenant scope, RBAC guards.

This is the only place in the codebase where HTTP concerns and authorization
meet. Routes declare what they need (``CurrentUser``, ``require(Permission.X)``)
and receive it already validated.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import Permission, role_has_permission
from app.db.session import get_session
from app.services.auth_service import AuthContext, AuthService

# auto_error=False so a missing header raises our own envelope, not Starlette's.
_bearer = HTTPBearer(auto_error=False, description="JWT access token")


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: DbSession,
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication required.")
    service = AuthService(session)
    return await service.resolve_access_token(credentials.credentials)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


async def get_organization_id(auth: CurrentAuth) -> uuid.UUID:
    """The tenant scope for the request. Every scoped repository takes this."""
    return auth.organization_id


OrganizationId = Annotated[uuid.UUID, Depends(get_organization_id)]


def require(*permissions: Permission) -> object:
    """Endpoint guard requiring *all* the listed permissions.

    Usage::

        @router.post("/upload", dependencies=[Depends(require(Permission.DATASET_WRITE))])
    """

    async def _guard(auth: CurrentAuth) -> AuthContext:
        missing = [p for p in permissions if not role_has_permission(auth.role, p)]
        if missing:
            raise PermissionDeniedError(
                "Your role does not permit this action.",
                details={
                    "required": [p.value for p in permissions],
                    "missing": [p.value for p in missing],
                    "role": auth.role.value,
                },
            )
        return auth

    return Depends(_guard)


def client_ip(request: Request) -> str | None:
    """Best-effort client IP.

    ``X-Forwarded-For`` is only consulted because both target deploy targets
    (Render, Vercel) terminate TLS at a trusted proxy. It is used for the audit
    trail only — never for an authorization decision.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent", "")[:400] or None


__all__ = [
    "CurrentAuth",
    "DbSession",
    "OrganizationId",
    "client_ip",
    "get_auth_context",
    "get_db",
    "get_organization_id",
    "require",
    "user_agent",
]
