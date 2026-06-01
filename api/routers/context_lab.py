"""Public FHIR context preview lab.

Accepts an uploaded FHIR Bundle and returns the compact Caspian-style context
without persisting the chart as a patient workspace.
"""

from __future__ import annotations

import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.core.context_builder import build_clinical_context_from_bundle_path

router = APIRouter(prefix="/context-lab", tags=["context-lab"])

MAX_UPLOAD_BYTES = 80 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 80 * 1024 * 1024


def _as_bundle(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("resourceType") == "Bundle":
        return payload
    if payload.get("resourceType"):
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [{"resource": payload}],
        }
    return None


def _load_json_bundle(data: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Upload must be valid UTF-8 JSON or a ZIP containing JSON.") from exc
    bundle = _as_bundle(payload)
    if bundle is None:
        raise HTTPException(status_code=422, detail="JSON must be a FHIR Bundle or a FHIR resource.")
    return bundle


def _load_zip_bundle(data: bytes) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    entries: list[dict[str, Any]] = []
    bundle_type = "collection"
    json_members = 0

    try:
        with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
            tmp.write(data)
            tmp.flush()
            with zipfile.ZipFile(tmp.name) as zf:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".json"):
                        continue
                    if info.file_size > MAX_ZIP_MEMBER_BYTES:
                        warnings.append(f"Skipped {info.filename}: file exceeds 80 MB.")
                        continue
                    json_members += 1
                    try:
                        payload = json.loads(zf.read(info).decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        warnings.append(f"Skipped {info.filename}: not valid JSON.")
                        continue
                    bundle = _as_bundle(payload)
                    if bundle is None:
                        warnings.append(f"Skipped {info.filename}: not a FHIR Bundle/resource.")
                        continue
                    if bundle.get("resourceType") == "Bundle":
                        bundle_type = str(bundle.get("type") or bundle_type)
                    entries.extend(bundle.get("entry") or [])
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="ZIP upload could not be opened.") from exc

    if not entries:
        detail = "ZIP did not contain a usable FHIR JSON Bundle or resource."
        if json_members:
            detail += " JSON files were present but none parsed as FHIR."
        raise HTTPException(status_code=422, detail=detail)

    if json_members > 1:
        warnings.append(f"Merged entries from {json_members} JSON files in the ZIP.")
    return {"resourceType": "Bundle", "type": bundle_type, "entry": entries}, warnings


def _resource_counts(bundle: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in bundle.get("entry") or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict):
            counts[str(resource.get("resourceType") or "Unknown")] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _section_rows(context) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    sections = [
        ("Safety flags", context.safety_flags),
        ("Drug interactions", context.interactions),
        ("Active medications", context.active_medications),
        ("Active conditions", context.active_conditions),
        ("Key labs", context.key_labs),
        ("Clinical notes", context.clinical_notes),
        ("Recent encounters", context.recent_encounters),
        ("Procedures", context.procedures_summary),
        ("Historical medications", context.historical_meds),
        ("Resolved conditions", context.resolved_conditions),
        ("Notable absences", context.absences),
    ]
    rows: list[dict[str, Any]] = []
    for label, values in sections:
        text = "\n".join(values)
        rows.append(
            {
                "label": label,
                "count": len(values),
                "token_estimate": len(text) // 4,
                "included": bool(values),
            }
        )
    return rows


@router.post("/preview")
async def preview_context(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Upload was empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds the 80 MB preview limit.")

    filename = file.filename or "upload.json"
    warnings: list[str] = []
    if filename.lower().endswith(".zip"):
        bundle, zip_warnings = _load_zip_bundle(data)
        warnings.extend(zip_warnings)
    else:
        bundle = _load_json_bundle(data)

    if not bundle.get("entry"):
        raise HTTPException(status_code=422, detail="FHIR Bundle has no entries.")

    raw_json = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    raw_token_estimate = len(raw_json) // 4
    resource_counts = _resource_counts(bundle)

    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=True) as tmp:
            tmp.write(raw_json)
            tmp.flush()
            context = build_clinical_context_from_bundle_path(Path(tmp.name))
            markdown = context.to_prompt()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not build clinical context: {exc}") from exc

    context_tokens = context.total_tokens_estimate
    compression_ratio = round(raw_token_estimate / context_tokens, 1) if context_tokens else None
    trace_steps = [
        {
            "label": "Upload received",
            "detail": f"{filename} ({len(data):,} bytes)",
            "status": "complete",
        },
        {
            "label": "FHIR parsed",
            "detail": f"{len(bundle.get('entry') or []):,} bundle entries across {len(resource_counts)} resource types",
            "status": "complete",
        },
        {
            "label": "Clinical facts compressed",
            "detail": f"{context.fact_count:,} facts rendered into {context_tokens:,} estimated context tokens",
            "status": "complete",
        },
        {
            "label": "Prompt-ready context",
            "detail": f"Raw estimate {raw_token_estimate:,} tokens; compression {compression_ratio or 'n/a'}x",
            "status": "complete",
        },
    ]

    return {
        "source_filename": filename,
        "bundle_type": bundle.get("type") or "unknown",
        "entry_count": len(bundle.get("entry") or []),
        "resource_type_counts": resource_counts,
        "raw_bytes": len(raw_json.encode("utf-8")),
        "raw_token_estimate": raw_token_estimate,
        "context_token_estimate": context_tokens,
        "compression_ratio": compression_ratio,
        "fact_count": context.fact_count,
        "patient_summary": context.patient_summary,
        "sections": _section_rows(context),
        "trace_steps": trace_steps,
        "markdown": markdown,
        "warnings": warnings,
    }
