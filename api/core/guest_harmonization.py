"""Temporary guest harmonization runs.

Guest harmonization is deliberately separate from durable account workspaces:
each run lives under ``data/guest-harmonization/<run_id>`` and is authorized by
a signed HTTP-only cookie that records which run ids this browser created.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO


REPO_ROOT = Path(__file__).resolve().parents[2]
GUEST_ROOT = Path(
    os.getenv("GUEST_HARMONIZATION_ROOT", REPO_ROOT / "data" / "guest-harmonization")
)
GUEST_SECRET_PATH = Path(
    os.getenv("GUEST_HARMONIZATION_SECRET_PATH", REPO_ROOT / "data" / "atlas-guest-harmonization.key")
)
GUEST_COOKIE_NAME = "atlas_guest_harmonization"
GUEST_COOKIE_SECURE = os.getenv("ENVIRONMENT", "development").strip().lower() in {"prod", "production"}
GUEST_TTL_HOURS = max(1, int(os.getenv("GUEST_HARMONIZATION_TTL_HOURS", "24")))
GUEST_MAX_FILE_BYTES = max(
    1024,
    int(os.getenv("GUEST_HARMONIZATION_MAX_FILE_BYTES", str(10 * 1024 * 1024))),
)
ALLOWED_EXTENSIONS = {".json", ".pdf", ".xml", ".txt"}
GUEST_MAX_PDF_PAGES = max(
    1, int(os.getenv("GUEST_HARMONIZATION_MAX_PDF_PAGES", "60"))
)
GUEST_MAX_PAGES_PER_PDF = max(
    1, int(os.getenv("GUEST_HARMONIZATION_MAX_PAGES_PER_PDF", "40"))
)
GUEST_GLOBAL_DAILY_PAGE_BUDGET = max(
    0, int(os.getenv("GUEST_HARMONIZATION_GLOBAL_DAILY_PAGE_BUDGET", "5000"))
)
GUEST_PDF_PIPELINE_NAME = (
    os.getenv("GUEST_HARMONIZATION_PDF_PIPELINE", "multipass-fhir").strip()
    or "multipass-fhir"
)
GUEST_PDF_FALLBACK_PIPELINE_NAME = "pdfplumber-lab-text"
GUEST_CCDA_PIPELINE_NAME = "ccda-fallback-v1"
GUEST_PROGRESS_EVENT_CAP = max(20, int(os.getenv("GUEST_HARMONIZATION_EVENT_CAP", "200")))

# Background-thread plumbing. Guest processing runs as a daemon so the
# frontend can poll for granular page-by-page progress instead of blocking
# on a 30-90s HTTP request. Mirrors api/core/harmonize_service.py:start_extract_job.
_PROCESSING_THREADS: dict[str, threading.Thread] = {}
_PROCESSING_LOCK = threading.Lock()
DISCLOSURE = (
    "Guest uploads are processed in a temporary workspace and automatically deleted. "
    "Download your output or create an account to save your workspace."
)
ALLOWED_AUDIENCES = {
    "patient-summary",
    "clinician-handoff",
    "second-opinion",
    "preop-review",
}
PATIENT_VOICE_MAX_CHARS = 4000


class GuestRunNotFound(FileNotFoundError):
    """The guest run directory or manifest does not exist."""


class GuestRunExpired(RuntimeError):
    """The guest run exists but is past its expiration time."""


class GuestRunUnauthorized(PermissionError):
    """The current browser is not authorized for this guest run."""


@dataclass(frozen=True)
class GuestCookieState:
    run_ids: tuple[str, ...]


def utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() in {"prod", "production"}


def _guest_secret() -> bytes:
    override = (os.getenv("GUEST_HARMONIZATION_SECRET") or "").strip()
    if override:
        return override.encode("utf-8")
    if _is_production():
        raise RuntimeError(
            "GUEST_HARMONIZATION_SECRET env var is required when ENVIRONMENT=production. "
            "Refusing to fall back to data/atlas-guest-harmonization.key — guest "
            "session signing secrets must not live as a plaintext file on disk in "
            "production."
        )
    _ensure_parent(GUEST_SECRET_PATH)
    if GUEST_SECRET_PATH.exists():
        return GUEST_SECRET_PATH.read_bytes()
    secret = secrets.token_bytes(32)
    GUEST_SECRET_PATH.write_bytes(secret)
    return secret


def _b64_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64_json(raw: str) -> dict[str, Any] | None:
    try:
        padding = "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode((raw + padding).encode("ascii"))
        payload = json.loads(decoded)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def sign_cookie(state: GuestCookieState) -> str:
    payload = _b64_json({"run_ids": list(state.run_ids)})
    signature = hmac.new(_guest_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def parse_cookie(raw: str | None) -> GuestCookieState:
    if not raw or "." not in raw:
        return GuestCookieState(run_ids=())
    payload, signature = raw.rsplit(".", 1)
    expected = hmac.new(_guest_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return GuestCookieState(run_ids=())
    data = _unb64_json(payload)
    raw_ids = data.get("run_ids") if data else None
    if not isinstance(raw_ids, list):
        return GuestCookieState(run_ids=())
    run_ids = tuple(
        item for item in (str(raw).strip() for raw in raw_ids) if item.startswith("guest_")
    )
    return GuestCookieState(run_ids=run_ids)


def with_authorized_run(state: GuestCookieState, run_id: str) -> GuestCookieState:
    run_ids = [item for item in state.run_ids if item != run_id]
    run_ids.append(run_id)
    return GuestCookieState(run_ids=tuple(run_ids[-20:]))


def without_authorized_run(state: GuestCookieState, run_id: str) -> GuestCookieState:
    return GuestCookieState(run_ids=tuple(item for item in state.run_ids if item != run_id))


def authorize_run(state: GuestCookieState, run_id: str) -> None:
    if run_id not in state.run_ids:
        raise GuestRunUnauthorized("Guest run is not available in this browser session.")


def _safe_filename(raw: str) -> str:
    name = Path(raw or "upload.bin").name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "upload.bin"


def _run_dir(run_id: str) -> Path:
    return GUEST_ROOT / run_id


def _manifest_path(run_id: str) -> Path:
    return _run_dir(run_id) / "manifest.json"


def _read_manifest(run_id: str) -> dict[str, Any]:
    path = _manifest_path(run_id)
    if not path.exists():
        raise GuestRunNotFound(f"Guest run not found: {run_id}")
    manifest = json.loads(path.read_text())
    expires_at = _parse_dt(str(manifest["expires_at"]))
    if expires_at <= utc_now():
        if manifest.get("status") != "expired":
            manifest["status"] = "expired"
            _write_manifest(run_id, manifest)
        raise GuestRunExpired(f"Guest run expired: {run_id}")
    return manifest


def _write_manifest(run_id: str, manifest: dict[str, Any]) -> None:
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    _manifest_path(run_id).write_text(json.dumps(manifest, indent=2, sort_keys=True))


def _per_source_bundle_path(run_id: str, file_id: str) -> Path:
    """Path where ``_extract_pdf_facts`` / ``_extract_ccda_facts`` persist
    the raw FHIR Bundle returned by their underlying pipeline.

    ``build_workspace_input`` reads these back so the bundle exporter can
    splice the extracted resources into ``evidence/canonical-facts.json``
    via the shared ``build_evidence()`` code path. Without this sidecar,
    PDF-extracted facts only live inside ``outputs/harmonized-record.json``
    and never reach the workspace ZIP.
    """
    return _run_dir(run_id) / "outputs" / "per-source" / f"{file_id}.fhir.json"


def _write_per_source_bundle(run_id: str, file_id: str, bundle: dict[str, Any]) -> None:
    path = _per_source_bundle_path(run_id, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True))


def _daily_budget_path(day: str | None = None) -> Path:
    """Sidecar file tracking total pages processed by all Guest runs today.

    Used as a soft circuit breaker so a single misconfigured Guest tier
    can't burn an unbounded vision-API budget overnight. Keyed by UTC day.
    """
    today = day or utc_now().strftime("%Y-%m-%d")
    return GUEST_ROOT / ".daily-page-budget" / f"{today}.json"


def _read_daily_page_count(day: str | None = None) -> int:
    path = _daily_budget_path(day)
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return 0
    return int(payload.get("pages", 0) or 0)


def _record_daily_page_use(pages: int, day: str | None = None) -> int:
    path = _daily_budget_path(day)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = _read_daily_page_count(day)
    new_total = current + max(0, int(pages))
    path.write_text(json.dumps({"pages": new_total}, indent=2))
    return new_total


# ---------------------------------------------------------------------------
# Progress block — mirrors ExtractJob shape from harmonize_service so the
# frontend can render the same components on Guest and authenticated views.
# ---------------------------------------------------------------------------


def _initial_progress(total_files: int) -> dict[str, Any]:
    return {
        "status": "pending",
        "stage": "Queued",
        "total_files": total_files,
        "processed_files": 0,
        "total_pages": 0,
        "processed_pages": 0,
        "estimated_processed_pages": 0,
        "current_source_label": None,
        "progress_mode": "lifecycle",
        "progress_percent": 0,
        "started_at": _iso(utc_now()),
        "completed_at": None,
        "events": [],
    }


def _progress_percent(processed_pages: int, total_pages: int, processed_files: int, total_files: int) -> int:
    if total_pages > 0:
        return max(0, min(100, int(round(processed_pages / total_pages * 100))))
    if total_files > 0:
        return max(0, min(100, int(round(processed_files / total_files * 100))))
    return 0


def _set_progress(manifest: dict[str, Any], **fields: Any) -> None:
    progress = manifest.setdefault("progress", _initial_progress(len(manifest.get("uploaded_files") or [])))
    for key, value in fields.items():
        if value is not None:
            progress[key] = value
    progress["progress_percent"] = _progress_percent(
        int(progress.get("processed_pages", 0) or 0),
        int(progress.get("total_pages", 0) or 0),
        int(progress.get("processed_files", 0) or 0),
        int(progress.get("total_files", 0) or 0),
    )


def _append_progress_event(
    manifest: dict[str, Any],
    *,
    event_type: str,
    message: str,
    stage: str | None = None,
    source_id: str | None = None,
    source_label: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    page_count: int | None = None,
    progress_basis: str = "lifecycle",
    is_estimate: bool = False,
) -> None:
    progress = manifest.setdefault("progress", _initial_progress(len(manifest.get("uploaded_files") or [])))
    events: list[dict[str, Any]] = progress.setdefault("events", [])
    events.append(
        {
            "event_id": secrets.token_urlsafe(8),
            "event_type": event_type,
            "created_at": _iso(utc_now()),
            "stage": stage or progress.get("stage"),
            "message": message,
            "source_id": source_id,
            "source_label": source_label,
            "page_start": page_start,
            "page_end": page_end,
            "page_count": page_count,
            "processed_pages": int(progress.get("processed_pages", 0) or 0),
            "total_pages": int(progress.get("total_pages", 0) or 0),
            "processed_files": int(progress.get("processed_files", 0) or 0),
            "total_files": int(progress.get("total_files", 0) or 0),
            "progress_basis": progress_basis,
            "is_estimate": is_estimate,
        }
    )
    if len(events) > GUEST_PROGRESS_EVENT_CAP:
        progress["events"] = events[-GUEST_PROGRESS_EVENT_CAP:]


def _safe_pdf_page_count(path: Path) -> int:
    """Best-effort page count via pypdfium2 — never raises.

    Used to seed ``progress.total_pages`` so the progress map shows the
    real document size before extraction starts (rather than jumping
    from 0 to N at completion).
    """
    try:
        import pypdfium2 as pdfium  # type: ignore[import-not-found]

        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return 0


def cleanup_expired_runs(now: datetime | None = None) -> int:
    current = now or utc_now()
    if not GUEST_ROOT.exists():
        return 0
    deleted = 0
    for manifest_path in GUEST_ROOT.glob("guest_*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text())
            expires_at = _parse_dt(str(manifest["expires_at"]))
        except Exception:
            continue
        if expires_at <= current:
            shutil.rmtree(manifest_path.parent, ignore_errors=True)
            deleted += 1
    return deleted


def create_run() -> dict[str, Any]:
    cleanup_expired_runs()
    now = utc_now()
    run_id = f"guest_{secrets.token_urlsafe(24)}"
    manifest = {
        "run_id": run_id,
        "mode": "guest",
        "created_at": _iso(now),
        "expires_at": _iso(now + timedelta(hours=GUEST_TTL_HOURS)),
        "uploaded_files": [],
        "outputs": [],
        "status": "ready",
    }
    run_dir = _run_dir(run_id)
    (run_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (run_dir / "derived").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    _write_manifest(run_id, manifest)
    return manifest


def get_run(run_id: str) -> dict[str, Any]:
    return _read_manifest(run_id)


def add_upload(
    run_id: str,
    *,
    filename: str,
    content_type: str | None,
    source: BinaryIO,
) -> dict[str, Any]:
    manifest = _read_manifest(run_id)
    safe_name = _safe_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Guest uploads support JSON, PDF, XML, and TXT files for this MVP.")

    data = source.read()
    if len(data) > GUEST_MAX_FILE_BYTES:
        raise OverflowError(f"Guest uploads are limited to {GUEST_MAX_FILE_BYTES} bytes per file.")

    file_id = f"file_{secrets.token_urlsafe(10)}"
    relative_path = Path("uploads") / f"{file_id}-{safe_name}"
    path = _run_dir(run_id) / relative_path
    path.write_bytes(data)

    uploaded = {
        "file_id": file_id,
        "file_name": safe_name,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": len(data),
        "uploaded_at": _iso(utc_now()),
        "storage_path": str(relative_path),
        "status": "uploaded",
    }
    manifest["uploaded_files"].append(uploaded)
    manifest["status"] = "ready"
    _write_manifest(run_id, manifest)
    return manifest


def delete_run(run_id: str) -> dict[str, Any]:
    path = _run_dir(run_id)
    if not path.exists():
        raise GuestRunNotFound(f"Guest run not found: {run_id}")
    shutil.rmtree(path)
    return {"deleted": True, "run_id": run_id}


def set_context(
    run_id: str,
    *,
    patient_voice: str | None = None,
    audience: str | None = None,
) -> dict[str, Any]:
    """Record patient-supplied context on the run manifest.

    ``patient_voice`` is free text the user writes about their own
    history/concerns — folded into the patient-summary packet at export
    time. ``audience`` selects which packet purpose the user wants the
    bundle emphasized for; downstream packagers use it to mark a
    primary packet.
    """
    manifest = _read_manifest(run_id)
    if patient_voice is not None:
        cleaned = patient_voice.strip()
        if len(cleaned) > PATIENT_VOICE_MAX_CHARS:
            raise ValueError(
                f"Patient voice is limited to {PATIENT_VOICE_MAX_CHARS} characters."
            )
        manifest["patient_voice"] = cleaned
    if audience is not None:
        audience_clean = audience.strip()
        if audience_clean and audience_clean not in ALLOWED_AUDIENCES:
            raise ValueError(
                f"Audience must be one of {sorted(ALLOWED_AUDIENCES)} or empty."
            )
        manifest["audience"] = audience_clean
    _write_manifest(run_id, manifest)
    return manifest


def process_run(run_id: str) -> dict[str, Any]:
    """Synchronous extraction pipeline. Used by tests + the daemon thread.

    The HTTP route should call :func:`start_processing` instead, which wraps
    this in a background thread and returns immediately so the frontend can
    poll for progress events.
    """
    manifest = _read_manifest(run_id)
    uploaded_files = manifest.get("uploaded_files") or []
    total_files = len(uploaded_files)

    # Seed the progress block so the very first poll has something to render.
    estimated_total_pages = 0
    for uploaded in uploaded_files:
        rel = Path(str(uploaded.get("storage_path", "")))
        path = _run_dir(run_id) / rel
        if path.suffix.lower() == ".pdf" and path.exists():
            estimated_total_pages += _safe_pdf_page_count(path)

    manifest["status"] = "processing"
    manifest["progress"] = _initial_progress(total_files)
    _set_progress(
        manifest,
        status="running",
        stage="Reading uploads",
        total_pages=estimated_total_pages,
    )
    _append_progress_event(
        manifest,
        event_type="job_started",
        message=(
            f"Processing {total_files} file{'s' if total_files != 1 else ''}"
            + (f" ({estimated_total_pages} PDF page{'s' if estimated_total_pages != 1 else ''} detected)" if estimated_total_pages else "")
        ),
        stage="Reading uploads",
        progress_basis="lifecycle",
    )
    _write_manifest(run_id, manifest)

    source_files = []
    facts: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    quality_issues: list[dict[str, Any]] = []
    patient: dict[str, Any] = {}

    for uploaded in uploaded_files:
        source_files.append(
            {
                "file_id": uploaded["file_id"],
                "file_name": uploaded["file_name"],
                "content_type": uploaded["content_type"],
                "size_bytes": uploaded["size_bytes"],
            }
        )
        rel = Path(str(uploaded["storage_path"]))
        path = _run_dir(run_id) / rel
        suffix = path.suffix.lower()
        stage_label = f"Extracting {uploaded['file_name']}"
        _set_progress(
            manifest,
            stage=stage_label,
            current_source_label=uploaded["file_name"],
        )
        _append_progress_event(
            manifest,
            event_type="file_started",
            message=f"Started {uploaded['file_name']}",
            stage=stage_label,
            source_id=uploaded["file_id"],
            source_label=uploaded["file_name"],
            progress_basis="lifecycle",
        )
        _write_manifest(run_id, manifest)

        before_pages = int((manifest.get("progress") or {}).get("processed_pages", 0) or 0)
        before_total = int((manifest.get("progress") or {}).get("total_pages", 0) or 0)

        if suffix == ".json":
            _extract_json_facts(
                path=path,
                uploaded=uploaded,
                patient=patient,
                facts=facts,
                provenance=provenance,
                quality_issues=quality_issues,
            )
        elif suffix == ".pdf":
            _extract_pdf_facts(
                path=path,
                uploaded=uploaded,
                patient=patient,
                facts=facts,
                provenance=provenance,
                quality_issues=quality_issues,
                manifest=manifest,
            )
        elif suffix == ".xml":
            _extract_ccda_facts(
                path=path,
                uploaded=uploaded,
                patient=patient,
                facts=facts,
                provenance=provenance,
                quality_issues=quality_issues,
                manifest=manifest,
            )
        else:
            quality_issues.append(
                {
                    "severity": "medium",
                    "code": "format_not_deeply_parsed",
                    "message": (
                        f"{uploaded['file_name']} is stored in the temporary workspace, "
                        "but plain-text files are not parsed for structured facts."
                    ),
                    "source_file_id": uploaded["file_id"],
                }
            )

        processed_files = int((manifest.get("progress") or {}).get("processed_files", 0) or 0) + 1
        after_pages = int((manifest.get("progress") or {}).get("processed_pages", 0) or 0)
        after_total = int((manifest.get("progress") or {}).get("total_pages", 0) or 0)
        delta_pages = max(0, after_pages - before_pages)
        page_start = before_pages + 1 if delta_pages else None
        page_end = after_pages if delta_pages else None
        _set_progress(manifest, processed_files=processed_files)
        _append_progress_event(
            manifest,
            event_type="file_completed",
            message=f"Finished {uploaded['file_name']}",
            stage=stage_label,
            source_id=uploaded["file_id"],
            source_label=uploaded["file_name"],
            page_start=page_start,
            page_end=page_end,
            page_count=after_total - before_total or delta_pages or None,
            progress_basis="reported" if delta_pages else "lifecycle",
        )
        _write_manifest(run_id, manifest)

    _set_progress(manifest, stage="Writing outputs", current_source_label=None)
    output = {
        "schema_version": "atlas.harmonized_record.v1",
        "created_at": _iso(utc_now()),
        "source_files": source_files,
        "patient": patient,
        "facts": facts,
        "provenance": provenance,
        "quality_issues": quality_issues,
    }

    out_path = _run_dir(run_id) / "outputs" / "harmonized-record.json"
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True))
    output_meta = {
        "output_id": "harmonized-record",
        "file_name": out_path.name,
        "content_type": "application/json",
        "size_bytes": out_path.stat().st_size,
        "created_at": output["created_at"],
        "storage_path": "outputs/harmonized-record.json",
    }
    manifest["outputs"] = [output_meta]
    manifest["status"] = "completed"
    manifest["processed_at"] = output["created_at"]
    _set_progress(
        manifest,
        status="complete",
        stage="Completed",
        completed_at=output["created_at"],
    )
    _append_progress_event(
        manifest,
        event_type="job_completed",
        message=(
            f"Generated {len(facts)} fact{'s' if len(facts) != 1 else ''} "
            f"from {total_files} source{'s' if total_files != 1 else ''}"
        ),
        stage="Completed",
        progress_basis="lifecycle",
    )
    _write_manifest(run_id, manifest)
    return manifest


def start_processing(run_id: str) -> dict[str, Any]:
    """Spawn ``process_run`` on a daemon thread and return immediately.

    Idempotent on a run that's already processing: a second call returns
    the current manifest without spawning another thread. The frontend
    polls ``GET /guest-harmonization/runs/{run_id}`` to watch ``progress``
    update event-by-event.
    """
    with _PROCESSING_LOCK:
        existing = _PROCESSING_THREADS.get(run_id)
        if existing is not None and existing.is_alive():
            return _read_manifest(run_id)

        # Mark processing + seed progress synchronously so the immediate response
        # carries a coherent state even if the thread hasn't started yet.
        manifest = _read_manifest(run_id)
        total_files = len(manifest.get("uploaded_files") or [])
        manifest["status"] = "processing"
        manifest["progress"] = _initial_progress(total_files)
        _set_progress(manifest, status="pending", stage="Queued")
        _write_manifest(run_id, manifest)

        def _runner() -> None:
            try:
                process_run(run_id)
            except Exception as exc:  # pragma: no cover — defensive
                # The frontend should still see *something* if the daemon
                # blows up. Stamp the failure on the manifest so the UI
                # can render an error state rather than hanging forever.
                try:
                    manifest_now = _read_manifest(run_id)
                    manifest_now["status"] = "failed"
                    _set_progress(
                        manifest_now,
                        status="failed",
                        stage="Failed",
                    )
                    _append_progress_event(
                        manifest_now,
                        event_type="job_failed",
                        message=f"{type(exc).__name__}: {str(exc)[:200]}",
                        stage="Failed",
                        progress_basis="lifecycle",
                    )
                    _write_manifest(run_id, manifest_now)
                except Exception:
                    pass
                traceback.print_exc()

        thread = threading.Thread(target=_runner, name=f"guest-process-{run_id}", daemon=True)
        _PROCESSING_THREADS[run_id] = thread
        thread.start()
        return manifest


def wait_for_processing(run_id: str, *, timeout: float = 60.0) -> dict[str, Any]:
    """Block until the background processing thread for ``run_id`` completes.

    Provided primarily for tests + the rare caller that wants synchronous
    semantics. The HTTP route never calls this — frontends should poll
    ``GET /guest-harmonization/runs/{run_id}`` and observe ``progress``
    tick toward ``status == "complete"`` instead.
    """
    with _PROCESSING_LOCK:
        thread = _PROCESSING_THREADS.get(run_id)
    if thread is not None:
        thread.join(timeout=timeout)
    return get_run(run_id)


def output_payload(run_id: str) -> dict[str, Any]:
    _read_manifest(run_id)
    path = _run_dir(run_id) / "outputs" / "harmonized-record.json"
    if not path.exists():
        raise GuestRunNotFound(f"Guest run output not found: {run_id}")
    return json.loads(path.read_text())


def build_workspace_input(run_id: str):
    """Adapter: convert a guest run into a WorkspaceInput for the packager.

    Each uploaded file becomes a ``source`` record in the shape that
    ``discover_sources()`` produces for authenticated collections. JSON files
    have their FHIR resources pre-parsed and attached as ``resources`` so
    ``build_evidence()`` can rebuild canonical facts using the same code path
    as the authenticated workspace export.
    """
    from scripts.export_workspace_package import WorkspaceInput, source_kind_for_path

    manifest = _read_manifest(run_id)
    sources: list[dict[str, Any]] = []
    for uploaded in manifest.get("uploaded_files", []):
        rel = Path(str(uploaded.get("storage_path", "")))
        path = _run_dir(run_id) / rel
        if not path.exists():
            continue

        resources: list[dict[str, Any]] = []
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                payload = None
            if payload is not None:
                resources = _resources_from_payload(payload)
        elif suffix in {".pdf", ".xml"}:
            # PDFs and CCDA XML were extracted to FHIR bundles in process_run()
            # and persisted next to outputs/harmonized-record.json. Read them
            # back so the shared build_evidence() path can splice their
            # resources into evidence/canonical-facts.json.
            bundle_path = _per_source_bundle_path(run_id, uploaded["file_id"])
            if bundle_path.exists():
                try:
                    bundle = json.loads(bundle_path.read_text())
                except (OSError, json.JSONDecodeError):
                    bundle = None
                if isinstance(bundle, dict):
                    resources = _resources_from_bundle(bundle)

        kind = source_kind_for_path(path)
        sources.append(
            {
                "source_id": uploaded["file_id"],
                "label": uploaded.get("file_name") or uploaded["file_id"],
                "kind": kind,
                "path": path,
                "original_path": path if path.suffix.lower() != ".json" else None,
                "resources": resources,
                "demo_source": False,
            }
        )

    workspace_id = f"guest-{run_id[len('guest_'):][:12]}" if run_id.startswith("guest_") else run_id
    extraction = _extraction_stanza(manifest)
    return WorkspaceInput(
        workspace_id=workspace_id,
        sources=sources,
        harmonization=None,
        package_id_override=f"ehi-atlas-workspace-{workspace_id}-{utc_now().strftime('%Y%m%d')}",
        patient_voice=manifest.get("patient_voice") or None,
        audience=manifest.get("audience") or None,
        extraction=extraction,
    )


def _extraction_stanza(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build the ``extraction`` block stamped onto MANIFEST.json.

    Records which pipelines ran (PDF + CCDA) plus the page count, so a
    downstream consumer can tell whether a packet came from the vision
    multipass tier, the labs-only fallback, or both.
    """
    pdf_pipelines = list(manifest.get("pdf_pipelines_used") or [])
    has_ccda = any(
        str(uploaded.get("storage_path", "")).lower().endswith(".xml")
        for uploaded in manifest.get("uploaded_files") or []
    )
    stanza: dict[str, Any] = {
        "tier": "guest",
        "pdf_pipeline": pdf_pipelines[0] if len(pdf_pipelines) == 1 else None,
        "pdf_pipelines_used": pdf_pipelines,
        "pdf_pages_processed": int(manifest.get("pdf_pages_processed", 0) or 0),
        "ccda_pipeline": GUEST_CCDA_PIPELINE_NAME if has_ccda else None,
        "ran_at": manifest.get("processed_at") or manifest.get("created_at"),
    }
    return stanza


def _extract_json_facts(
    *,
    path: Path,
    uploaded: dict[str, Any],
    patient: dict[str, Any],
    facts: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    quality_issues: list[dict[str, Any]],
) -> None:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        quality_issues.append(
            {
                "severity": "high",
                "code": "invalid_json",
                "message": f"{uploaded['file_name']} is not valid JSON: {exc.msg}.",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    resources = _resources_from_payload(payload)
    if not resources:
        quality_issues.append(
            {
                "severity": "medium",
                "code": "no_fhir_resources",
                "message": f"{uploaded['file_name']} did not contain FHIR resources.",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    for resource in resources:
        if resource.get("resourceType") == "Patient" and not patient:
            patient.update(_patient_summary(resource))
            continue
        fact = _fact_from_resource(resource, uploaded["file_id"])
        if fact is None:
            continue
        facts.append(fact)
        provenance.append(
            {
                "target_fact_id": fact["fact_id"],
                "source_file_id": uploaded["file_id"],
                "source_resource_type": resource.get("resourceType"),
                "source_resource_id": resource.get("id"),
                "method": "guest_fhir_json_mvp",
            }
        )


def _resources_from_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull resource dicts out of a FHIR Bundle (or a single resource)."""
    if not isinstance(bundle, dict):
        return []
    if bundle.get("resourceType") == "Bundle":
        resources = []
        for entry in bundle.get("entry") or []:
            if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
                resources.append(entry["resource"])
        return resources
    if isinstance(bundle.get("resourceType"), str):
        return [bundle]
    return []


def _extract_facts_from_resources(
    resources: list[dict[str, Any]],
    *,
    uploaded: dict[str, Any],
    patient: dict[str, Any],
    facts: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    method: str,
) -> int:
    """Walk a list of FHIR resources, appending fact + provenance entries.

    Returns the number of fact rows added so callers can flag low-yield
    extractions.
    """
    added = 0
    for resource in resources:
        if resource.get("resourceType") == "Patient" and not patient:
            patient.update(_patient_summary(resource))
            continue
        fact = _fact_from_resource(resource, uploaded["file_id"])
        if fact is None:
            continue
        facts.append(fact)
        provenance.append(
            {
                "target_fact_id": fact["fact_id"],
                "source_file_id": uploaded["file_id"],
                "source_resource_type": resource.get("resourceType"),
                "source_resource_id": resource.get("id"),
                "method": method,
            }
        )
        added += 1
    return added


def _extract_pdf_facts(
    *,
    path: Path,
    uploaded: dict[str, Any],
    patient: dict[str, Any],
    facts: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    quality_issues: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    """Extract FHIR facts from a PDF using the production multipass pipeline.

    Default: ``multipass-fhir`` (vision, 5-pass) — same code path the
    authenticated tier uses. Falls back to ``pdfplumber-lab-text`` (no-LLM
    labs-only baseline) when ANTHROPIC_API_KEY is missing or the global
    daily page budget is exhausted, so a Guest run still completes with
    whatever signal we can pull from text.

    Rate limits (all env-configurable):
      - ``GUEST_HARMONIZATION_MAX_PDF_PAGES`` (default 60) — per-run total.
      - ``GUEST_HARMONIZATION_MAX_PAGES_PER_PDF`` (default 40) — per-file.
      - ``GUEST_HARMONIZATION_GLOBAL_DAILY_PAGE_BUDGET`` (default 5000) —
        circuit-breaker across all Guest runs in one UTC day.
    """
    run_id = str(manifest.get("run_id") or "")
    pages_consumed_already = int(manifest.get("pdf_pages_processed", 0) or 0)
    try:
        from lib.extract.pipelines.text_first import extract_pdf_text_pages
        from lib.extract.pipelines import get as get_pipeline
    except Exception as exc:  # pragma: no cover — defensive against missing extras
        quality_issues.append(
            {
                "severity": "high",
                "code": "pdf_pipeline_unavailable",
                "message": f"PDF extraction not available in this environment: {exc}",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    try:
        pages = extract_pdf_text_pages(path)
    except Exception as exc:
        quality_issues.append(
            {
                "severity": "high",
                "code": "pdf_unreadable",
                "message": f"Could not read PDF text layer: {exc}",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    page_count = len(pages)
    if page_count > GUEST_MAX_PAGES_PER_PDF:
        quality_issues.append(
            {
                "severity": "medium",
                "code": "pdf_page_limit_per_file_exceeded",
                "message": (
                    f"{uploaded['file_name']} has {page_count} pages; the Guest per-file "
                    f"cap is {GUEST_MAX_PAGES_PER_PDF}. Create an account to process longer documents."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    if pages_consumed_already + page_count > GUEST_MAX_PDF_PAGES:
        quality_issues.append(
            {
                "severity": "medium",
                "code": "pdf_page_limit_exceeded",
                "message": (
                    f"PDF has {page_count} pages but only "
                    f"{max(0, GUEST_MAX_PDF_PAGES - pages_consumed_already)} pages remain in "
                    f"this Guest workspace's quota. Create an account for the full pipeline."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    pipeline_name = GUEST_PDF_PIPELINE_NAME
    daily_pages = _read_daily_page_count()
    if (
        GUEST_GLOBAL_DAILY_PAGE_BUDGET > 0
        and pipeline_name != GUEST_PDF_FALLBACK_PIPELINE_NAME
        and daily_pages + page_count > GUEST_GLOBAL_DAILY_PAGE_BUDGET
    ):
        quality_issues.append(
            {
                "severity": "medium",
                "code": "daily_budget_exhausted",
                "message": (
                    f"Guest vision-pipeline daily budget exhausted "
                    f"({daily_pages}/{GUEST_GLOBAL_DAILY_PAGE_BUDGET} pages). Falling back to "
                    f"the labs-only baseline for this PDF."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )
        pipeline_name = GUEST_PDF_FALLBACK_PIPELINE_NAME

    if pipeline_name == "multipass-fhir" and not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
        quality_issues.append(
            {
                "severity": "high",
                "code": "pipeline_unconfigured",
                "message": (
                    "Vision PDF pipeline requires ANTHROPIC_API_KEY in this environment; "
                    "falling back to the labs-only baseline."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )
        pipeline_name = GUEST_PDF_FALLBACK_PIPELINE_NAME

    try:
        PipelineCls = get_pipeline(pipeline_name)
        pipeline = PipelineCls(patient_id=f"guest_{uploaded['file_id'][:8]}")
    except Exception as exc:
        quality_issues.append(
            {
                "severity": "high",
                "code": "pdf_pipeline_unavailable",
                "message": f"PDF pipeline {pipeline_name!r} unavailable: {exc}",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    try:
        bundle = pipeline.extract(path)
    except Exception as exc:
        quality_issues.append(
            {
                "severity": "high",
                "code": "pdf_extraction_failed",
                "message": f"PDF extraction failed: {str(exc)[:280]}",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    manifest["pdf_pages_processed"] = pages_consumed_already + page_count
    pipelines_used = list(manifest.get("pdf_pipelines_used") or [])
    if pipeline_name not in pipelines_used:
        pipelines_used.append(pipeline_name)
    manifest["pdf_pipelines_used"] = pipelines_used
    _record_daily_page_use(page_count)

    # Reconcile progress-block page counters with the just-completed file so
    # the polling UI sees a real page-by-page checkpoint (mirrors the
    # authenticated extract-job emission).
    progress = manifest.setdefault("progress", _initial_progress(len(manifest.get("uploaded_files") or [])))
    current_total = int(progress.get("total_pages", 0) or 0)
    current_processed = int(progress.get("processed_pages", 0) or 0)
    new_total = max(current_total, current_processed + page_count)
    _set_progress(
        manifest,
        processed_pages=current_processed + page_count,
        total_pages=new_total,
        progress_mode="reported",
    )

    if run_id and isinstance(bundle, dict):
        try:
            _write_per_source_bundle(run_id, uploaded["file_id"], bundle)
        except OSError:
            # Persistence failure is non-fatal — the in-process facts still
            # land in outputs/harmonized-record.json. Worst case: the
            # workspace exporter sees no resources for this source.
            pass

    method = (
        "guest_pdf_multipass_v1"
        if pipeline_name == "multipass-fhir"
        else "guest_pdf_text_first_v1"
    )
    resources = _resources_from_bundle(bundle)
    added = _extract_facts_from_resources(
        resources,
        uploaded=uploaded,
        patient=patient,
        facts=facts,
        provenance=provenance,
        method=method,
    )
    if added == 0:
        quality_issues.append(
            {
                "severity": "low",
                "code": "pdf_low_yield",
                "message": (
                    f"{uploaded['file_name']} parsed but the {pipeline_name} pipeline returned "
                    f"no clinical resources. Scanned PDFs or unusual layouts may need the "
                    f"authenticated vision pipeline."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )


def _extract_ccda_facts(
    *,
    path: Path,
    uploaded: dict[str, Any],
    patient: dict[str, Any],
    facts: list[dict[str, Any]],
    provenance: list[dict[str, Any]],
    quality_issues: list[dict[str, Any]],
    manifest: dict[str, Any] | None = None,
) -> None:
    """Extract FHIR facts from a C-CDA XML using the deterministic fallback parser.

    The Microsoft FHIR Converter path is not used for Guests; only the
    no-dependency fallback in ``api.core.ccda``. Today this fallback covers
    Patient + Conditions + Medications.
    """
    try:
        from api.core.ccda import convert_ccda_to_fhir_bundle, is_ccda_xml
    except Exception as exc:  # pragma: no cover
        quality_issues.append(
            {
                "severity": "high",
                "code": "ccda_pipeline_unavailable",
                "message": f"C-CDA parser not available in this environment: {exc}",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    if not is_ccda_xml(path):
        quality_issues.append(
            {
                "severity": "medium",
                "code": "xml_not_ccda",
                "message": (
                    f"{uploaded['file_name']} is XML but does not look like a C-CDA "
                    "ClinicalDocument; no facts extracted."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    try:
        bundle = convert_ccda_to_fhir_bundle(str(path), uploaded["file_id"], mode="fallback")
    except Exception as exc:
        quality_issues.append(
            {
                "severity": "high",
                "code": "ccda_extraction_failed",
                "message": f"C-CDA parse failed: {str(exc)[:280]}",
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    run_id = str(manifest.get("run_id") or "") if isinstance(manifest, dict) else ""
    if run_id and isinstance(bundle, dict):
        try:
            _write_per_source_bundle(run_id, uploaded["file_id"], bundle)
        except OSError:
            pass

    resources = _resources_from_bundle(bundle)
    added = _extract_facts_from_resources(
        resources,
        uploaded=uploaded,
        patient=patient,
        facts=facts,
        provenance=provenance,
        method="guest_ccda_fallback_v1",
    )
    if added == 0:
        quality_issues.append(
            {
                "severity": "low",
                "code": "ccda_low_yield",
                "message": (
                    f"{uploaded['file_name']} parsed but no Conditions or Medications were "
                    "recognized by the fallback parser."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )


def _resources_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    if payload.get("resourceType") == "Bundle":
        resources = []
        for entry in payload.get("entry", []):
            if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
                resources.append(entry["resource"])
        return resources
    if isinstance(payload.get("resourceType"), str):
        return [payload]
    return []


def _patient_summary(resource: dict[str, Any]) -> dict[str, Any]:
    name = resource.get("name")
    display_name = ""
    if isinstance(name, list) and name:
        first = name[0] if isinstance(name[0], dict) else {}
        given = " ".join(str(item) for item in first.get("given", []) if item)
        family = str(first.get("family") or "")
        display_name = f"{given} {family}".strip()
    return {
        "id": resource.get("id"),
        "name": display_name,
        "gender": resource.get("gender"),
        "birth_date": resource.get("birthDate"),
    }


def _fact_from_resource(resource: dict[str, Any], source_file_id: str) -> dict[str, Any] | None:
    resource_type = str(resource.get("resourceType") or "")
    if resource_type not in {
        "Observation",
        "Condition",
        "MedicationRequest",
        "MedicationStatement",
        "AllergyIntolerance",
        "Immunization",
    }:
        return None
    resource_id = str(resource.get("id") or secrets.token_urlsafe(8))
    label = _resource_label(resource)
    return {
        "fact_id": f"{source_file_id}:{resource_type}:{resource_id}",
        "resource_type": resource_type,
        "source_resource_id": resource_id,
        "label": label,
        "value": _resource_value(resource),
        "date": _resource_date(resource),
        "status": _resource_status(resource),
        "source_file_ids": [source_file_id],
    }


def _resource_label(resource: dict[str, Any]) -> str:
    for key in ("code", "medicationCodeableConcept", "vaccineCode"):
        label = _codeable_label(resource.get(key))
        if label:
            return label
    if resource.get("resourceType") == "AllergyIntolerance":
        label = _codeable_label(resource.get("code"))
        return label or "Allergy"
    return str(resource.get("resourceType") or "Clinical fact")


def _codeable_label(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("text"), str) and value["text"].strip():
        return value["text"].strip()
    coding = value.get("coding")
    if isinstance(coding, list):
        for item in coding:
            if isinstance(item, dict) and isinstance(item.get("display"), str):
                return item["display"].strip()
    return ""


def _resource_value(resource: dict[str, Any]) -> str:
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict):
        raw_value = quantity.get("value")
        unit = quantity.get("unit") or quantity.get("code") or ""
        return f"{raw_value} {unit}".strip()
    concept = _codeable_label(resource.get("valueCodeableConcept"))
    if concept:
        return concept
    return ""


def _resource_date(resource: dict[str, Any]) -> str:
    for key in ("effectiveDateTime", "onsetDateTime", "authoredOn", "occurrenceDateTime", "recordedDate"):
        value = resource.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _resource_status(resource: dict[str, Any]) -> str:
    value = resource.get("clinicalStatus")
    if isinstance(value, dict):
        label = _codeable_label(value)
        if label:
            return label
    for key in ("status", "verificationStatus"):
        raw = resource.get(key)
        if isinstance(raw, str):
            return raw
    return ""
