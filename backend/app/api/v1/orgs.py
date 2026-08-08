"""Workspace and membership administration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentAuth, DbSession, require
from app.core.security import Permission
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit import AuditLogOut
from app.schemas.auth import (
    InviteUserRequest,
    InviteUserResponse,
    OrganizationOut,
    OrganizationUpdateRequest,
    RoleAssignRequest,
    UserOut,
)
from app.schemas.common import Page, PageMeta
from app.services.auth_service import MemberService, OrganizationService

router = APIRouter(prefix="/orgs", tags=["organization"])


@router.get("/current", response_model=OrganizationOut, summary="Current workspace")
async def get_current_org(auth: CurrentAuth) -> OrganizationOut:
    return OrganizationOut.model_validate(auth.organization)


@router.patch(
    "/current",
    response_model=OrganizationOut,
    dependencies=[require(Permission.ORG_UPDATE)],
    summary="Update workspace details",
)
async def update_current_org(
    payload: OrganizationUpdateRequest, auth: CurrentAuth, session: DbSession
) -> OrganizationOut:
    service = OrganizationService(session, auth.organization_id)
    organization = await service.update(
        actor=auth.user, name=payload.name, industry=payload.industry
    )
    return OrganizationOut.model_validate(organization)


@router.get(
    "/members",
    response_model=Page[UserOut],
    dependencies=[require(Permission.MEMBER_READ)],
    summary="List workspace members",
)
async def list_members(
    auth: CurrentAuth,
    session: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[UserOut]:
    service = MemberService(session, auth.organization_id)
    members = await service.list_members(limit=limit, offset=offset)
    total = await service.count_members()
    return Page[UserOut](
        items=[UserOut.model_validate(member) for member in members],
        meta=PageMeta(
            total=total, limit=limit, offset=offset, has_more=offset + len(members) < total
        ),
    )


@router.post(
    "/members",
    response_model=InviteUserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require(Permission.MEMBER_INVITE)],
    summary="Add a member to the workspace",
)
async def invite_member(
    payload: InviteUserRequest, auth: CurrentAuth, session: DbSession
) -> InviteUserResponse:
    service = MemberService(session, auth.organization_id)
    member, temporary_password = await service.invite(
        actor=auth.user,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
    )
    return InviteUserResponse(
        user=UserOut.model_validate(member), temporary_password=temporary_password
    )


@router.patch(
    "/members/{member_id}/role",
    response_model=UserOut,
    dependencies=[require(Permission.MEMBER_ROLE_ASSIGN)],
    summary="Assign a role to a member",
)
async def assign_role(
    member_id: uuid.UUID,
    payload: RoleAssignRequest,
    auth: CurrentAuth,
    session: DbSession,
) -> UserOut:
    service = MemberService(session, auth.organization_id)
    member = await service.assign_role(
        actor=auth.user, member_id=member_id, role=payload.role
    )
    return UserOut.model_validate(member)


@router.delete(
    "/members/{member_id}",
    response_model=UserOut,
    dependencies=[require(Permission.MEMBER_REMOVE)],
    summary="Deactivate a member",
)
async def deactivate_member(
    member_id: uuid.UUID, auth: CurrentAuth, session: DbSession
) -> UserOut:
    service = MemberService(session, auth.organization_id)
    member = await service.set_active(
        actor=auth.user, member_id=member_id, is_active=False
    )
    return UserOut.model_validate(member)


@router.get(
    "/audit",
    response_model=Page[AuditLogOut],
    dependencies=[require(Permission.AUDIT_READ)],
    summary="Recent audit-log entries",
)
async def list_audit(
    auth: CurrentAuth,
    session: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[AuditLogOut]:
    repository = AuditLogRepository(session, auth.organization_id)
    entries = await repository.list_recent(limit=limit, offset=offset)
    total = await repository.count()
    return Page[AuditLogOut](
        items=[AuditLogOut.model_validate(entry) for entry in entries],
        meta=PageMeta(
            total=total, limit=limit, offset=offset, has_more=offset + len(entries) < total
        ),
    )
