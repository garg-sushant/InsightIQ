"""Auth, user and organization payloads."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES, Permission, Role
from app.schemas.common import APIModel

PASSWORD_MIN_LENGTH = 10
_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")


def _validate_password_strength(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(value.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes when UTF-8 encoded."
        )
    if not _HAS_LETTER.search(value) or not _HAS_DIGIT.search(value):
        raise ValueError("Password must contain at least one letter and one digit.")
    return value


class SignupRequest(APIModel):
    """Creates an organization and its first (owner) user in one step."""

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(min_length=2, max_length=200)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(APIModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(APIModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class OrganizationOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    industry: str | None = None
    is_active: bool
    created_at: datetime


class UserOut(APIModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    organization_id: uuid.UUID
    last_login_at: datetime | None = None
    created_at: datetime


class CurrentUserOut(APIModel):
    """``/auth/me`` — the user plus everything the UI needs to gate features."""

    user: UserOut
    organization: OrganizationOut
    permissions: list[Permission]


class AuthResponse(APIModel):
    tokens: TokenPair
    user: UserOut
    organization: OrganizationOut


class InviteUserRequest(APIModel):
    """Creates a member directly.

    A real deployment would email a signed invitation link; that needs an SMTP
    provider, which this build deliberately does not require. Instead the API
    returns a one-time temporary password for the admin to hand over. This is
    documented as a known limitation in the README.
    """

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: Role = Role.VIEWER


class InviteUserResponse(APIModel):
    user: UserOut
    temporary_password: str = Field(
        description="Share out-of-band. The member should change it after first login."
    )


class RoleAssignRequest(APIModel):
    role: Role


class PasswordChangeRequest(APIModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class OrganizationUpdateRequest(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    industry: str | None = Field(default=None, max_length=120)


__all__ = [
    "PASSWORD_MIN_LENGTH",
    "AuthResponse",
    "CurrentUserOut",
    "InviteUserRequest",
    "InviteUserResponse",
    "LoginRequest",
    "OrganizationOut",
    "OrganizationUpdateRequest",
    "PasswordChangeRequest",
    "RefreshRequest",
    "RoleAssignRequest",
    "SignupRequest",
    "TokenPair",
    "UserOut",
]
