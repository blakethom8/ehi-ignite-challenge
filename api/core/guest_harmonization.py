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
    1, int(os.getenv("GUEST_HARMONIZATION_MAX_PDF_PAGES", "20"))
)
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
    manifest = _read_manifest(run_id)
    manifest["status"] = "processing"
    _write_manifest(run_id, manifest)

    source_files = []
    facts: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    quality_issues: list[dict[str, Any]] = []
    patient: dict[str, Any] = {}

    for uploaded in manifest["uploaded_files"]:
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
    _write_manifest(run_id, manifest)
    return manifest


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
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                payload = None
            if payload is not None:
                resources = _resources_from_payload(payload)

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
    return WorkspaceInput(
        workspace_id=workspace_id,
        sources=sources,
        harmonization=None,
        package_id_override=f"ehi-atlas-workspace-{workspace_id}-{utc_now().strftime('%Y%m%d')}",
        patient_voice=manifest.get("patient_voice") or None,
        audience=manifest.get("audience") or None,
    )


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
    """Extract FHIR facts from a PDF using the deterministic text-first pipeline.

    Anonymous Guest tier: ``PdfPlumberLabTextPipeline`` (no LLM, free, ~100ms).
    Surfaces lab Observations only. Rate-limited by total PDF pages per run
    (``GUEST_HARMONIZATION_MAX_PDF_PAGES``, default 20) to bound Guest cost.
    """
    pages_consumed_already = int(manifest.get("pdf_pages_processed", 0) or 0)
    try:
        from lib.extract.pipelines.text_first import (
            PdfPlumberLabTextPipeline,
            extract_pdf_text_pages,
        )
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

    if pages_consumed_already + len(pages) > GUEST_MAX_PDF_PAGES:
        quality_issues.append(
            {
                "severity": "medium",
                "code": "pdf_page_limit_exceeded",
                "message": (
                    f"PDF has {len(pages)} pages but only {GUEST_MAX_PDF_PAGES - pages_consumed_already} "
                    f"pages remain in this Guest workspace's quota. Create an account for the full pipeline."
                ),
                "source_file_id": uploaded["file_id"],
            }
        )
        return

    pipeline = PdfPlumberLabTextPipeline(patient_id=f"guest_{uploaded['file_id'][:8]}")
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

    manifest["pdf_pages_processed"] = pages_consumed_already + len(pages)
    resources = _resources_from_bundle(bundle)
    added = _extract_facts_from_resources(
        resources,
        uploaded=uploaded,
        patient=patient,
        facts=facts,
        provenance=provenance,
        method="guest_pdf_text_first_v1",
    )
    if added == 0:
        quality_issues.append(
            {
                "severity": "low",
                "code": "pdf_low_yield",
                "message": (
                    f"{uploaded['file_name']} parsed but no structured lab rows were "
                    "recognized. Scanned PDFs or non-tabular reports need the authenticated "
                    "vision pipeline."
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
