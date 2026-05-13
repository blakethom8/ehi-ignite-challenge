"""Auth/session HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api.auth_models import (
    AccountPasswordChangeRequest,
    AccountSessionSummary,
    AccountUpdateRequest,
    AdminActionResponse,
    AuthDemoRequest,
    AuthLoginRequest,
    AuthPatientSelectionRequest,
    AuthSessionResponse,
    AuthSignupRequest,
)
from api.core.access_policy import Capabilities, capabilities_for
from api.core import guest_harmonization
from api.core.auth import (
    begin_demo_session,
    change_own_password,
    clear_session_cookie,
    current_session,
    current_session_including_guest,
    delete_own_account,
    login_user,
    optional_session_response,
    require_access_session,
    require_authenticated_session,
    list_own_sessions,
    revoke_session,
    revoke_other_sessions,
    revoke_own_session,
    select_patient,
    set_session_cookie,
    signup_user,
    update_own_display_name,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _clear_guest_cookie(response: Response) -> None:
    response.delete_cookie(key=guest_harmonization.GUEST_COOKIE_NAME, path="/")


@router.get("/capabilities", response_model=Capabilities)
def get_capabilities(request: Request) -> Capabilities:
    """Return the capability surface for the current session.

    Always 200 — anonymous callers get the anonymous capability shape so the
    frontend can render the landing page without an auth round-trip.
    """
    return capabilities_for(current_session_including_guest(request))


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
    _clear_guest_cookie(response)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/signup", response_model=AuthSessionResponse)
def signup(payload: AuthSignupRequest, request: Request, response: Response) -> AuthSessionResponse:
    existing = current_session(request)
    if existing is not None:
        revoke_session(existing)
    session = signup_user(payload.email, payload.password, payload.display_name, request)
    _clear_guest_cookie(response)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/logout", response_model=AuthSessionResponse)
def logout(request: Request, response: Response) -> AuthSessionResponse:
    revoke_session(current_session(request))
    _clear_guest_cookie(response)
    clear_session_cookie(response)
    return optional_session_response(request)


@router.post("/demo", response_model=AuthSessionResponse)
def start_demo(payload: AuthDemoRequest, request: Request, response: Response) -> AuthSessionResponse:
    existing = current_session(request)
    if existing is not None:
        revoke_session(existing)
    session = begin_demo_session(payload.patient_id, request)
    _clear_guest_cookie(response)
    set_session_cookie(response, session.session_id)
    return session.to_response()


@router.post("/demo/exit", response_model=AuthSessionResponse)
def exit_demo(request: Request, response: Response) -> AuthSessionResponse:
    revoke_session(current_session(request))
    _clear_guest_cookie(response)
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


@router.get("/sessions", response_model=list[AccountSessionSummary])
def get_own_sessions(request: Request) -> list[AccountSessionSummary]:
    principal = require_authenticated_session(request)
    assert principal.user_id is not None
    return list_own_sessions(principal.user_id, current_session_id=principal.session_id)


@router.delete("/sessions/{session_id}", response_model=AdminActionResponse)
def delete_own_session(session_id: str, request: Request) -> AdminActionResponse:
    principal = require_authenticated_session(request)
    assert principal.user_id is not None
    revoke_own_session(principal.user_id, session_id, current_session_id=principal.session_id)
    return AdminActionResponse(ok=True)


@router.post("/sessions/revoke-others", response_model=AdminActionResponse)
def delete_other_sessions(request: Request) -> AdminActionResponse:
    principal = require_authenticated_session(request)
    assert principal.user_id is not None
    revoke_other_sessions(principal.user_id, keep_session_id=principal.session_id)
    return AdminActionResponse(ok=True)


@router.delete("/me", response_model=AuthSessionResponse)
def delete_my_account(request: Request, response: Response) -> AuthSessionResponse:
    principal = require_authenticated_session(request)
    delete_own_account(principal)
    _clear_guest_cookie(response)
    clear_session_cookie(response)
    return optional_session_response(request)
