"""Authentication and member management.

Owns its transactions and raises domain errors. Knows nothing about HTTP —
no ``Request``, no ``HTTPException``, no status codes.
"""

from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import (
    ROLE_RANK,
    Role,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.organization import Organization
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserAuthRepository, UserRepository

logger = get_logger(__name__)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class AuthContext:
    """Everything downstream needs to know about the caller."""

    user: User
    organization: Organization

    @property
    def organization_id(self) -> uuid.UUID:
        return self.organization.id

    @property
    def role(self) -> Role:
        return self.user.role


def slugify(value: str) -> str:
    slug = _SLUG_STRIP.sub("-", value.lower()).strip("-")
    return slug[:60] or "workspace"


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.orgs = OrganizationRepository(session)
        self.user_auth = UserAuthRepository(session)

    # -- registration -------------------------------------------------------
    async def signup(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        organization_name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, Organization]:
        """Create a workspace and its owner atomically."""
        email = email.lower().strip()
        if await self.user_auth.email_exists(email):
            # Same message either way — do not confirm which emails are registered.
            raise ConflictError("An account with these details could not be created.")

        organization = Organization(
            name=organization_name.strip(),
            slug=await self._unique_slug(slugify(organization_name)),
        )
        await self.orgs.add(organization)

        user = User(
            organization_id=organization.id,
            email=email,
            full_name=full_name.strip(),
            hashed_password=hash_password(password),
            role=Role.OWNER,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()

        audit = AuditLogRepository(self.session, organization.id)
        await audit.record(
            action="auth.signup",
            resource_type="organization",
            resource_id=str(organization.id),
            user_id=user.id,
            actor_email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.session.commit()
        logger.info("signup", extra={"organization_id": str(organization.id)})
        return user, organization

    async def _unique_slug(self, base: str) -> str:
        slug = base
        for attempt in range(50):
            if not await self.orgs.slug_exists(slug):
                return slug
            slug = f"{base}-{attempt + 2}"
        return f"{base}-{secrets.token_hex(4)}"

    # -- login --------------------------------------------------------------
    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, Organization]:
        user = await self.user_auth.get_by_email_global(email.lower().strip())

        # Constant-ish work on the miss path so response timing does not reveal
        # whether the email exists.
        if user is None:
            hash_password("timing-equalisation-placeholder-value")
            raise AuthenticationError("Incorrect email or password.")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        organization = await self.orgs.get(user.organization_id)
        if organization is None or not organization.is_active:
            raise AuthenticationError("This workspace is not available.")

        user.last_login_at = datetime.now(UTC)
        audit = AuditLogRepository(self.session, organization.id)
        await audit.record(
            action="auth.login",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            actor_email=user.email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.session.commit()
        return user, organization

    def issue_tokens(self, user: User) -> tuple[str, str, int]:
        access = create_access_token(
            str(user.id),
            organization_id=str(user.organization_id),
            role=user.role.value,
        )
        refresh = create_refresh_token(str(user.id))
        return access, refresh, settings.access_token_expire_minutes * 60

    async def refresh(self, refresh_token: str) -> tuple[User, Organization]:
        payload = decode_token(refresh_token, expected_type="refresh")
        try:
            user_id = uuid.UUID(str(payload["sub"]))
        except (ValueError, KeyError) as exc:
            raise AuthenticationError("Token is invalid.", code="token_invalid") from exc

        user = await self.user_auth.get_by_id_global(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Token is no longer valid.", code="token_revoked")

        organization = await self.orgs.get(user.organization_id)
        if organization is None or not organization.is_active:
            raise AuthenticationError("This workspace is not available.")
        return user, organization

    # -- session verification (used by request dependencies) ----------------
    async def resolve_access_token(self, token: str) -> AuthContext:
        """Validate an access token *and* re-check the user against the database.

        The org/role claims in the token are a convenience for clients; they are
        never trusted for authorization. A user deactivated or demoted after
        their token was issued loses access on their very next request.
        """
        payload = decode_token(token, expected_type="access")
        try:
            user_id = uuid.UUID(str(payload["sub"]))
        except (ValueError, KeyError) as exc:
            raise AuthenticationError("Token is invalid.", code="token_invalid") from exc

        user = await self.user_auth.get_by_id_global(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account is no longer active.", code="account_inactive")

        organization = await self.orgs.get(user.organization_id)
        if organization is None or not organization.is_active:
            raise AuthenticationError("This workspace is not available.")
        return AuthContext(user=user, organization=organization)

    # -- password -----------------------------------------------------------
    async def change_password(
        self, *, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect.")
        user.hashed_password = hash_password(new_password)
        audit = AuditLogRepository(self.session, user.organization_id)
        await audit.record(
            action="auth.password_change",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            actor_email=user.email,
        )
        await self.session.commit()


class MemberService:
    """Workspace membership: invite, list, re-role, deactivate."""

    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id
        self.users = UserRepository(session, organization_id)
        self.user_auth = UserAuthRepository(session)
        self.audit = AuditLogRepository(session, organization_id)

    async def list_members(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return await self.users.list_members(limit=limit, offset=offset)

    async def count_members(self) -> int:
        return await self.users.count()

    async def invite(
        self,
        *,
        actor: User,
        email: str,
        full_name: str,
        role: Role,
    ) -> tuple[User, str]:
        """Create a member and return a generated temporary password.

        No email is sent — that would require an SMTP account this build
        intentionally avoids. The admin hands the password over out-of-band.
        Documented as a known limitation in the README.
        """
        self._assert_can_grant(actor.role, role)

        email = email.lower().strip()
        if await self.user_auth.email_exists(email):
            raise ConflictError("A user with that email address already exists.")

        # 24 hex chars: comfortably strong, and short enough to read aloud.
        temporary_password = f"IIQ-{secrets.token_hex(12)}"
        member = User(
            organization_id=self.organization_id,
            email=email,
            full_name=full_name.strip(),
            hashed_password=hash_password(temporary_password),
            role=role,
            is_active=True,
        )
        await self.users.add(member)
        await self.audit.record(
            action="member.invite",
            resource_type="user",
            resource_id=str(member.id),
            user_id=actor.id,
            actor_email=actor.email,
            context={"role": role.value},
        )
        await self.session.commit()
        return member, temporary_password

    async def assign_role(self, *, actor: User, member_id: uuid.UUID, role: Role) -> User:
        member = await self.users.get(member_id)
        if member is None:
            raise NotFoundError("Member not found.")
        if member.id == actor.id:
            raise ValidationError("You cannot change your own role.")

        self._assert_can_grant(actor.role, role)
        # An admin must not be able to demote or re-role someone above them.
        self._assert_can_grant(actor.role, member.role)

        if member.role == Role.OWNER and role != Role.OWNER:
            owners = await self.users.count_by_role(Role.OWNER)
            if owners <= 1:
                raise ValidationError("A workspace must always have at least one owner.")

        previous = member.role
        member.role = role
        await self.audit.record(
            action="member.role_assign",
            resource_type="user",
            resource_id=str(member.id),
            user_id=actor.id,
            actor_email=actor.email,
            context={"from": previous.value, "to": role.value},
        )
        await self.session.commit()
        return member

    async def set_active(self, *, actor: User, member_id: uuid.UUID, is_active: bool) -> User:
        member = await self.users.get(member_id)
        if member is None:
            raise NotFoundError("Member not found.")
        if member.id == actor.id:
            raise ValidationError("You cannot deactivate your own account.")
        self._assert_can_grant(actor.role, member.role)

        if member.role == Role.OWNER and not is_active:
            owners = await self.users.count_by_role(Role.OWNER)
            if owners <= 1:
                raise ValidationError("A workspace must always have at least one active owner.")

        member.is_active = is_active
        await self.audit.record(
            action="member.deactivate" if not is_active else "member.activate",
            resource_type="user",
            resource_id=str(member.id),
            user_id=actor.id,
            actor_email=actor.email,
        )
        await self.session.commit()
        return member

    @staticmethod
    def _assert_can_grant(actor_role: Role, target_role: Role) -> None:
        """Nobody may act on a role at or above their own rank.

        Without this, an admin could promote themselves to owner by proxy — the
        classic privilege-escalation hole in role-based member management.
        """
        if ROLE_RANK[target_role] >= ROLE_RANK[actor_role]:
            raise PermissionDeniedError(
                "You cannot assign or modify a role at or above your own level."
            )


class OrganizationService:
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id
        self.orgs = OrganizationRepository(session)
        self.audit = AuditLogRepository(session, organization_id)

    async def get(self) -> Organization:
        organization = await self.orgs.get(self.organization_id)
        if organization is None:
            raise NotFoundError("Workspace not found.")
        return organization

    async def update(
        self, *, actor: User, name: str | None = None, industry: str | None = None
    ) -> Organization:
        organization = await self.get()
        if name is not None:
            organization.name = name.strip()
        if industry is not None:
            organization.industry = industry.strip() or None
        await self.audit.record(
            action="org.update",
            resource_type="organization",
            resource_id=str(organization.id),
            user_id=actor.id,
            actor_email=actor.email,
        )
        await self.session.commit()
        return organization


__all__ = ["AuthContext", "AuthService", "MemberService", "OrganizationService", "slugify"]
