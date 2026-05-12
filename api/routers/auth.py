"""Auth/session HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api.auth_models import (
    AccountPasswordChangeRequest,
    AccountUpdateRequest,
    AdminActionResponse,
    AuthDemoRequest,
    AuthLoginRequest,
    AuthPatientSelectionRequest,
    AuthSessionResponse,
    AuthSignupRequest,
)
from api.core.auth import (
    begin_demo_session,
    change_own_password,
    clear_session_cookie,
    current_session,
    delete_own_account,
    login_user,
    optional_session_response,
    require_access_session,
    require_authenticated_session,
    revoke_session,
    select_patient,
    set_session_cookie,
    signup_user,
    update_own_display_name,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/session", response_model=AuthSessionResponse)
def get_session(request: Request, response: Response) -> AuthSessionResponse:
    session = current_session(request)
    if session is None:
        clear_session_cookie(response)
        return optional_session_response(request)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/login", response_model=AuthSessionResponse)
def login(payload: AuthLoginRequest, request: Request, response: Response) -> AuthSessionResponse:
    existing = current_session(request)
    if existing is not None:
        revoke_session(existing)
    session = login_user(payload.email, payload.password, request)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/signup", response_model=AuthSessionResponse)
def signup(payload: AuthSignupRequest, request: Request, response: Response) -> AuthSessionResponse:
    existing = current_session(request)
    if existing is not None:
        revoke_session(existing)
    session = signup_user(payload.email, payload.password, payload.display_name, request)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/logout", response_model=AuthSessionResponse)
def logout(request: Request, response: Response) -> AuthSessionResponse:
    revoke_session(current_session(request))
    clear_session_cookie(response)
    return optional_session_response(request)


@router.post("/demo", response_model=AuthSessionResponse)
def start_demo(payload: AuthDemoRequest, request: Request, response: Response) -> AuthSessionResponse:
    existing = current_session(request)
    if existing is not None:
        revoke_session(existing)
    session = begin_demo_session(payload.patient_id, request)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/demo/exit", response_model=AuthSessionResponse)
def exit_demo(request: Request, response: Response) -> AuthSessionResponse:
    revoke_session(current_session(request))
    clear_session_cookie(response)
    return optional_session_response(request)


@router.post("/select-patient", response_model=AuthSessionResponse)
def update_selected_patient(
    payload: AuthPatientSelectionRequest,
    request: Request,
    response: Response,
) -> AuthSessionResponse:
    session = select_patient(require_access_session(request), payload.patient_id)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.patch("/me", response_model=AuthSessionResponse)
def update_own_profile(payload: AccountUpdateRequest, request: Request) -> AuthSessionResponse:
    principal = require_authenticated_session(request)
    assert principal.user_id is not None  # require_authenticated_session guarantees this
    update_own_display_name(principal.user_id, payload.display_name)
    # Re-resolve the session so the response carries the fresh display_name.
    refreshed = current_session(request)
    if refreshed is None:
        return optional_session_response(request)
    return refreshed.to_response()


@router.post("/change-password", response_model=AdminActionResponse)
def change_password(payload: AccountPasswordChangeRequest, request: Request) -> AdminActionResponse:
    principal = require_authenticated_session(request)
    assert principal.user_id is not None
    change_own_password(
        principal.user_id,
        payload.current_password,
        payload.new_password,
        keep_session_id=principal.session_id,
    )
    return AdminActionResponse(ok=True)


@router.delete("/me", response_model=AuthSessionResponse)
def delete_my_account(request: Request, response: Response) -> AuthSessionResponse:
    principal = require_authenticated_session(request)
    delete_own_account(principal)
    clear_session_cookie(response)
    return optional_session_response(request)
