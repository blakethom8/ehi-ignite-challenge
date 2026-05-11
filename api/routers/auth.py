"""Auth/session HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from api.auth_models import (
    AuthDemoRequest,
    AuthLoginRequest,
    AuthPatientSelectionRequest,
    AuthSessionResponse,
)
from api.core.auth import (
    begin_demo_session,
    clear_session_cookie,
    current_session,
    login_user,
    optional_session_response,
    require_access_session,
    revoke_session,
    select_patient,
    set_session_cookie,
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
