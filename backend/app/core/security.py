"""Password hashing, JWT issuance/verification, and the RBAC permission matrix."""

from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError

TokenType = Literal["access", "refresh"]

# bcrypt silently ignores bytes past 72; rejecting instead of truncating avoids
# the classic "two different long passwords both work" surprise.
BCRYPT_MAX_PASSWORD_BYTES = 72


class Role(StrEnum):
    """Workspace roles, ordered from most to least privileged."""

    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(StrEnum):
    """Discrete capabilities checked at the endpoint boundary."""

    # Data
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    DATASET_DELETE = "dataset:delete"
    # Analytics & AI
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_RUN = "analytics:run"
    AI_GENERATE = "ai:generate"
    # Reports
    REPORT_EXPORT = "report:export"
    # Administration
    MEMBER_READ = "member:read"
    MEMBER_INVITE = "member:invite"
    MEMBER_ROLE_ASSIGN = "member:role_assign"
    MEMBER_REMOVE = "member:remove"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"
    AUDIT_READ = "audit:read"


_VIEWER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.DATASET_READ,
        Permission.ANALYTICS_READ,
        Permission.REPORT_EXPORT,
        Permission.MEMBER_READ,
    }
)

_ANALYST_PERMISSIONS: frozenset[Permission] = _VIEWER_PERMISSIONS | {
    Permission.DATASET_WRITE,
    Permission.ANALYTICS_RUN,
    Permission.AI_GENERATE,
}

_ADMIN_PERMISSIONS: frozenset[Permission] = _ANALYST_PERMISSIONS | {
    Permission.DATASET_DELETE,
    Permission.MEMBER_INVITE,
    Permission.MEMBER_ROLE_ASSIGN,
    Permission.MEMBER_REMOVE,
    Permission.ORG_UPDATE,
    Permission.AUDIT_READ,
}

_OWNER_PERMISSIONS: frozenset[Permission] = _ADMIN_PERMISSIONS | {Permission.ORG_DELETE}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER_PERMISSIONS,
    Role.ANALYST: _ANALYST_PERMISSIONS,
    Role.ADMIN: _ADMIN_PERMISSIONS,
    Role.OWNER: _OWNER_PERMISSIONS,
}

# Used to stop an admin from promoting anyone above their own level.
ROLE_RANK: dict[Role, int] = {Role.VIEWER: 0, Role.ANALYST: 1, Role.ADMIN: 2, Role.OWNER: 3}


def role_has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def permissions_for_role(role: Role) -> list[Permission]:
    return sorted(ROLE_PERMISSIONS.get(role, frozenset()), key=lambda p: p.value)


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
        )
    return bcrypt.hashpw(encoded, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash in the DB — treat as a failed login, never a 500.
        return False


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------
def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
        "iss": "insightiq",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(
    subject: str,
    *,
    organization_id: str | None = None,
    role: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Access tokens carry org + role so route guards need no extra DB round-trip.

    The values are still re-checked against the database on every request (see
    ``app.core.deps``) — the claims are a convenience, not the source of truth.
    """
    extra: dict[str, Any] = {}
    if organization_id:
        extra["org"] = organization_id
    if role:
        extra["role"] = role
    return _create_token(
        subject,
        "access",
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes),
        extra,
    )


def create_refresh_token(subject: str, *, expires_delta: timedelta | None = None) -> str:
    return _create_token(
        subject,
        "refresh",
        expires_delta or timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Decode and validate a JWT, raising :class:`AuthenticationError` on any problem."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            issuer="insightiq",
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Token is invalid.", code="token_invalid") from exc

    if expected_type is not None and not hmac.compare_digest(
        str(payload.get("type", "")), expected_type
    ):
        raise AuthenticationError(
            f"Expected a {expected_type} token.", code="token_wrong_type"
        )
    return payload


__all__ = [
    "BCRYPT_MAX_PASSWORD_BYTES",
    "ROLE_PERMISSIONS",
    "ROLE_RANK",
    "Permission",
    "Role",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "permissions_for_role",
    "role_has_permission",
    "verify_password",
]
