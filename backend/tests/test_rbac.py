"""RBAC enforcement: role permission matrix and privilege-escalation guards."""

from __future__ import annotations

import pytest

from app.core.security import Permission, Role, role_has_permission


def test_viewer_cannot_write_or_run_analytics() -> None:
    assert role_has_permission(Role.VIEWER, Permission.DATASET_READ)
    assert not role_has_permission(Role.VIEWER, Permission.DATASET_WRITE)
    assert not role_has_permission(Role.VIEWER, Permission.ANALYTICS_RUN)
    assert not role_has_permission(Role.VIEWER, Permission.AI_GENERATE)


def test_analyst_can_write_and_run_but_not_administer() -> None:
    assert role_has_permission(Role.ANALYST, Permission.DATASET_WRITE)
    assert role_has_permission(Role.ANALYST, Permission.ANALYTICS_RUN)
    assert role_has_permission(Role.ANALYST, Permission.AI_GENERATE)
    assert not role_has_permission(Role.ANALYST, Permission.MEMBER_INVITE)
    assert not role_has_permission(Role.ANALYST, Permission.ORG_DELETE)


def test_admin_can_administer_but_not_delete_org() -> None:
    assert role_has_permission(Role.ADMIN, Permission.MEMBER_INVITE)
    assert role_has_permission(Role.ADMIN, Permission.MEMBER_ROLE_ASSIGN)
    assert role_has_permission(Role.ADMIN, Permission.DATASET_DELETE)
    assert not role_has_permission(Role.ADMIN, Permission.ORG_DELETE)


def test_owner_has_full_permissions() -> None:
    assert role_has_permission(Role.OWNER, Permission.ORG_DELETE)
    assert role_has_permission(Role.OWNER, Permission.MEMBER_REMOVE)


@pytest.mark.asyncio
async def test_admin_cannot_escalate_self_to_owner(client, db_session) -> None:
    from app.services.auth_service import AuthService

    service = AuthService(db_session)
    user, organization = await service.signup(
        email="owner@escalation.example.com", password="Password123!",
        full_name="Owner", organization_name="Escalation Test",
    )

    from app.services.auth_service import MemberService
    from app.core.exceptions import PermissionDeniedError

    members = MemberService(db_session, organization.id)
    admin, _ = await members.invite(
        actor=user, email="admin@escalation.example.com", full_name="Admin", role=Role.ADMIN,
    )

    # Re-fetch admin as an ORM object with the ADMIN role for the actor check.
    with pytest.raises(PermissionDeniedError):
        await members.assign_role(actor=admin, member_id=user.id, role=Role.OWNER)


@pytest.mark.asyncio
async def test_viewer_upload_returns_403(client) -> None:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "owner@rbactest.example.com", "password": "Password123!",
            "full_name": "Owner", "organization_name": "RBAC Test",
        },
    )
    owner_token = signup.json()["tokens"]["access_token"]

    invite = await client.post(
        "/api/v1/orgs/members",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": "viewer@rbactest.example.com", "full_name": "Viewer", "role": "viewer"},
    )
    assert invite.status_code == 201
    temp_password = invite.json()["temporary_password"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@rbactest.example.com", "password": temp_password},
    )
    viewer_token = login.json()["tokens"]["access_token"]

    upload = await client.post(
        "/api/v1/datasets/upload/orders",
        headers={"Authorization": f"Bearer {viewer_token}"},
        files={"file": ("orders.csv", b"Order ID,Order Date\nX,1/1/2024\n", "text/csv")},
    )
    assert upload.status_code == 403
    assert upload.json()["error"]["code"] == "permission_denied"
