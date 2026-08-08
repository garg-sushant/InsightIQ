"""Authentication endpoints.

Routes here do three things only: bind validated input, call a service, and
shape a response. No DB session use, no business rules, no query building.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request, status

from app.core.deps import CurrentAuth, DbSession, client_ip, user_agent
from app.core.security import permissions_for_role
from app.schemas.auth import (
    AuthResponse,
    CurrentUserOut,
    LoginRequest,
    OrganizationOut,
    PasswordChangeRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)
from app.schemas.common import Message
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(service: AuthService, user: object) -> TokenPair:
    access, refresh, expires_in = service.issue_tokens(user)  # type: ignore[arg-type]
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace and its first owner",
)
async def signup(
    payload: SignupRequest, session: DbSession, request: Request
) -> AuthResponse:
    service = AuthService(session)
    user, organization = await service.signup(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        organization_name=payload.organization_name,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    return AuthResponse(
        tokens=_tokens(service, user),
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(organization),
    )


@router.post("/login", response_model=AuthResponse, summary="Exchange credentials for tokens")
async def login(
    payload: LoginRequest, session: DbSession, request: Request
) -> AuthResponse:
    service = AuthService(session)
    user, organization = await service.authenticate(
        email=payload.email,
        password=payload.password,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )
    return AuthResponse(
        tokens=_tokens(service, user),
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(organization),
    )


@router.post("/refresh", response_model=TokenPair, summary="Rotate an access token")
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenPair:
    service = AuthService(session)
    user, _ = await service.refresh(payload.refresh_token)
    return _tokens(service, user)


@router.get("/me", response_model=CurrentUserOut, summary="The authenticated user")
async def me(auth: CurrentAuth) -> CurrentUserOut:
    return CurrentUserOut(
        user=UserOut.model_validate(auth.user),
        organization=OrganizationOut.model_validate(auth.organization),
        permissions=permissions_for_role(auth.role),
    )


@router.post("/password", response_model=Message, summary="Change your own password")
async def change_password(
    payload: Annotated[PasswordChangeRequest, ...],
    auth: CurrentAuth,
    session: DbSession,
) -> Message:
    service = AuthService(session)
    await service.change_password(
        user=auth.user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return Message(message="Password updated.")
