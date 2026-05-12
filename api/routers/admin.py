"""/api/admin — administrator-only user, session, and activity surface.

Every endpoint here is gated by ``require_role("admin")``. Demo sessions and
non-admin authenticated sessions get HTTP 403 with a generic message.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from api.auth_models import (
    AdminActionResponse,
    AdminAuditEvent,
    AdminAuditListResponse,
    AdminPatchUserRequest,
    AdminSessionSummary,
    AdminUserDetail,
    AdminUserSummary,
    AdminWorkspaceSummary,
)
from api.core.aggregation import (
    _patient_root,
    list_profiles_for_user,
    storage_bytes_for_user,
)
from api.core.auth import (
    SessionPrincipal,
    admin_delete_user,
    admin_get_user,
    admin_list_sessions,
    admin_list_user_activity,
    admin_list_users,
    admin_patch_user,
    admin_revoke_session,
    require_role,
)


router = APIRouter(prefix="/admin", tags=["admin"])

_admin_dep = require_role("admin")


def _workspace_storage_bytes(workspace_id: str) -> int:
    root = _patient_root(workspace_id)
    if not root.exists():
        return 0
    total = 0
    for child in root.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _workspace_source_count(workspace_id: str) -> int:
    root = _patient_root(workspace_id)
    if not root.exists():
        return 0
    return sum(1 for _ in root.glob("*.metadata.json"))


def _user_summary(user, *, include_workspaces: bool = False) -> AdminUserSummary:
    profiles = list_profiles_for_user(user.id)
    storage = storage_bytes_for_user(user.id)
    base = AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        workspace_count=len(profiles),
        storage_bytes=storage,
    )
    if not include_workspaces:
        return base
    workspaces = [
        AdminWorkspaceSummary(
            id=profile.id,
            display_name=profile.display_name,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            source_count=_workspace_source_count(profile.id),
            storage_bytes=_workspace_storage_bytes(profile.id),
        )
        for profile in profiles
    ]
    return AdminUserDetail(**base.model_dump(), workspaces=workspaces)


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(_: SessionPrincipal = Depends(_admin_dep)) -> list[AdminUserSummary]:
    return [_user_summary(user) for user in admin_list_users()]


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(user_id: str, _: SessionPrincipal = Depends(_admin_dep)) -> AdminUserDetail:
    user = admin_get_user(user_id)
    summary = _user_summary(user, include_workspaces=True)
    # _user_summary returns AdminUserDetail when include_workspaces is True.
    assert isinstance(summary, AdminUserDetail)
    return summary


@router.get("/users/{user_id}/activity", response_model=AdminAuditListResponse)
def get_user_activity(
    user_id: str,
    limit: int = 100,
    _: SessionPrincipal = Depends(_admin_dep),
) -> AdminAuditListResponse:
    events = [
        AdminAuditEvent(
            id=event.id,
            created_at=event.created_at,
            session_id=event.session_id,
            user_id=event.user_id,
            mode=event.mode,
            patient_id=event.patient_id,
            event_type=event.event_type,
            payload=event.payload,
        )
        for event in admin_list_user_activity(user_id, limit=limit)
    ]
    return AdminAuditListResponse(events=events)


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
def patch_user(
    user_id: str,
    payload: AdminPatchUserRequest,
    request: Request,
    principal: SessionPrincipal = Depends(_admin_dep),
) -> AdminUserDetail:
    admin_patch_user(
        user_id,
        role=payload.role,
        status_value=payload.status,
        caller_user_id=principal.user_id,
    )
    user = admin_get_user(user_id)
    summary = _user_summary(user, include_workspaces=True)
    assert isinstance(summary, AdminUserDetail)
    return summary


@router.delete("/users/{user_id}", response_model=AdminActionResponse)
def delete_user(
    user_id: str,
    principal: SessionPrincipal = Depends(_admin_dep),
) -> AdminActionResponse:
    admin_delete_user(user_id, caller_user_id=principal.user_id)
    return AdminActionResponse(ok=True)


@router.get("/sessions", response_model=list[AdminSessionSummary])
def list_sessions(_: SessionPrincipal = Depends(_admin_dep)) -> list[AdminSessionSummary]:
    return [
        AdminSessionSummary(
            id=row.id,
            mode=row.mode,
            user_id=row.user_id,
            user_email=row.user_email,
            user_display_name=row.user_display_name,
            active_patient_id=row.active_patient_id,
            active_patient_name=row.active_patient_name,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            user_agent=row.user_agent,
        )
        for row in admin_list_sessions()
    ]


@router.delete("/sessions/{session_id}", response_model=AdminActionResponse)
def revoke_session(
    session_id: str,
    principal: SessionPrincipal = Depends(_admin_dep),
) -> AdminActionResponse:
    admin_revoke_session(session_id, caller_user_id=principal.user_id)
    return AdminActionResponse(ok=True)
