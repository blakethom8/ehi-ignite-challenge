"""Guest temporary harmonization API."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from api.core import guest_harmonization
from api.models import (
    GuestHarmonizationContextRequest,
    GuestHarmonizationDeleteResponse,
    GuestHarmonizationRunResponse,
)
from scripts.export_workspace_package import build_package_from_input


router = APIRouter(prefix="/guest-harmonization", tags=["guest-harmonization"])


def _response(manifest: dict) -> GuestHarmonizationRunResponse:
    return GuestHarmonizationRunResponse(
        **manifest,
        disclosure=guest_harmonization.DISCLOSURE,
    )


def _cookie_state(request: Request) -> guest_harmonization.GuestCookieState:
    return guest_harmonization.parse_cookie(
        request.cookies.get(guest_harmonization.GUEST_COOKIE_NAME)
    )


def _set_guest_cookie(
    response: Response,
    state: guest_harmonization.GuestCookieState,
) -> None:
    response.set_cookie(
        key=guest_harmonization.GUEST_COOKIE_NAME,
        value=guest_harmonization.sign_cookie(state),
        httponly=True,
        secure=guest_harmonization.GUEST_COOKIE_SECURE,
        samesite="lax",
        max_age=guest_harmonization.GUEST_TTL_HOURS * 60 * 60,
        path="/",
    )


def _require_guest_run(request: Request, run_id: str) -> None:
    try:
        guest_harmonization.authorize_run(_cookie_state(request), run_id)
    except guest_harmonization.GuestRunUnauthorized as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


def _map_run_error(exc: Exception) -> HTTPException:
    if isinstance(exc, guest_harmonization.GuestRunExpired):
        return HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc))
    if isinstance(exc, guest_harmonization.GuestRunNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, OverflowError):
        return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/runs", response_model=GuestHarmonizationRunResponse, status_code=201)
def create_guest_run(request: Request, response: Response) -> GuestHarmonizationRunResponse:
    manifest = guest_harmonization.create_run()
    state = guest_harmonization.with_authorized_run(_cookie_state(request), manifest["run_id"])
    _set_guest_cookie(response, state)
    return _response(manifest)


@router.get("/runs/{run_id}", response_model=GuestHarmonizationRunResponse)
def get_guest_run(run_id: str, request: Request) -> GuestHarmonizationRunResponse:
    _require_guest_run(request, run_id)
    try:
        return _response(guest_harmonization.get_run(run_id))
    except Exception as exc:
        raise _map_run_error(exc) from exc


@router.post("/runs/{run_id}/uploads", response_model=GuestHarmonizationRunResponse)
async def upload_guest_file(
    run_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> GuestHarmonizationRunResponse:
    _require_guest_run(request, run_id)
    try:
        manifest = guest_harmonization.add_upload(
            run_id,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            source=file.file,
        )
    except Exception as exc:
        raise _map_run_error(exc) from exc
    return _response(manifest)


@router.post("/runs/{run_id}/process", response_model=GuestHarmonizationRunResponse)
def process_guest_run(run_id: str, request: Request) -> GuestHarmonizationRunResponse:
    """Kick off the extraction pipeline on a background thread.

    Returns immediately with ``status: "processing"`` so the frontend can
    poll ``GET /runs/{run_id}`` every ~1.5s to watch the ``progress``
    block tick through file_started / file_completed events. Matches the
    authenticated ``/api/harmonize/{id}/extract`` job pattern.
    """
    _require_guest_run(request, run_id)
    try:
        return _response(guest_harmonization.start_processing(run_id))
    except Exception as exc:
        raise _map_run_error(exc) from exc


@router.post("/runs/{run_id}/context", response_model=GuestHarmonizationRunResponse)
def set_guest_context(
    run_id: str,
    request: Request,
    payload: GuestHarmonizationContextRequest,
) -> GuestHarmonizationRunResponse:
    """Record patient_voice and/or audience for this run.

    Fields are folded into the patient-summary packet (patient_voice) and
    used to mark the primary packet (audience) at export time.
    """
    _require_guest_run(request, run_id)
    try:
        manifest = guest_harmonization.set_context(
            run_id,
            patient_voice=payload.patient_voice,
            audience=payload.audience or None,
        )
    except Exception as exc:
        raise _map_run_error(exc) from exc
    return _response(manifest)


@router.get("/runs/{run_id}/output")
def get_guest_output(run_id: str, request: Request) -> dict:
    _require_guest_run(request, run_id)
    try:
        return guest_harmonization.output_payload(run_id)
    except Exception as exc:
        raise _map_run_error(exc) from exc


@router.get("/runs/{run_id}/export-workspace")
def export_guest_workspace(run_id: str, request: Request) -> FileResponse:
    """Download a portable EHI Atlas workspace ZIP for a guest run.

    Mirrors the authenticated ``/api/harmonize/{collection}/export-workspace``
    surface but is gated by the guest cookie instead of a logged-in session.
    The ZIP layout is identical to the authenticated path; both build through
    ``build_package_from_input()``.
    """
    _require_guest_run(request, run_id)
    try:
        workspace_input = guest_harmonization.build_workspace_input(run_id)
    except Exception as exc:
        raise _map_run_error(exc) from exc

    out_dir = Path("data/guest-harmonization") / run_id / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{workspace_input.workspace_id}.zip"
    try:
        build_package_from_input(workspace_input, out, include_originals=True)
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(
        path=out,
        media_type="application/zip",
        filename=out.name,
    )


@router.delete("/runs/{run_id}", response_model=GuestHarmonizationDeleteResponse)
def delete_guest_run(
    run_id: str,
    request: Request,
    response: Response,
) -> GuestHarmonizationDeleteResponse:
    _require_guest_run(request, run_id)
    try:
        payload = guest_harmonization.delete_run(run_id)
    except Exception as exc:
        raise _map_run_error(exc) from exc
    state = guest_harmonization.without_authorized_run(_cookie_state(request), run_id)
    _set_guest_cookie(response, state)
    return GuestHarmonizationDeleteResponse(**payload)
