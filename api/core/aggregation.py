"""Data Aggregator workflow service.

The service presents the end-state aggregation workflow while grounding the
current proof of concept in real local inputs: Synthea FHIR bundles, optional
private proof-of-life data, uploaded local files, and Patient Context outputs.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from api.core.loader import load_patient, patient_display_name, path_from_patient_id
from api.core.patient_context import private_cedars_available
from api.models import (
    AggregationCleaningIssue,
    AggregationDeleteResponse,
    AggregationCleaningQueueResponse,
    AggregationEnvironmentResponse,
    AggregationReadinessItem,
    AggregationReadinessResponse,
    AggregationSourceCard,
    AggregationUploadedFile,
    AggregationUploadResponse,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STORE_ROOT = Path(os.getenv("AGGREGATION_UPLOAD_STORE_PATH", REPO_ROOT / "data" / "aggregation-uploads"))
MAX_UPLOAD_BYTES = int(os.getenv("AGGREGATION_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:120] or "patient"


def _patient_label(patient_id: str) -> str:
    path = path_from_patient_id(patient_id)
    if path:
        return patient_display_name(path)
    return patient_id


def _patient_root(patient_id: str) -> Path:
    return STORE_ROOT / _safe_id(patient_id)


def _upload_metadata_path(patient_id: str, file_id: str) -> Path:
    return _patient_root(patient_id) / f"{file_id}.metadata.json"


def _upload_file_path(patient_id: str, upload: AggregationUploadedFile) -> Path:
    if upload.storage_path:
        return Path(upload.storage_path)
    return _patient_root(patient_id) / f"{upload.file_id}-{upload.file_name}"


def _infer_confidence(upload: AggregationUploadedFile) -> str:
    name = upload.file_name.lower()
    if upload.content_type in {"application/json", "text/csv"} or name.endswith((".json", ".ndjson", ".csv")):
        return "high"
    if upload.content_type == "application/pdf" or name.endswith(".pdf"):
        return "medium"
    if name.endswith((".jpg", ".jpeg", ".png", ".heic")):
        return "low"
    return "unknown"


def _source_card_for_upload(upload: AggregationUploadedFile) -> AggregationSourceCard:
    return AggregationSourceCard(
        id=f"upload-{upload.file_id}",
        name=upload.file_name,
        category="file_upload",
        mode="uploaded",
        status_label="Uploaded locally",
        record_count=1,
        last_updated=upload.uploaded_at,
        confidence="medium",
        posture="Local file staging. Contents are not merged into the chart until extraction and review exist.",
        next_action="Add description and document context, then queue this file for extraction review.",
        help_title="Uploaded files",
        help_body=(
            "This file is now part of the local aggregation workspace. In V1, it is tracked as source material; "
            "future extraction should convert supported content into candidate facts with provenance."
        ),
        evidence=[
            f"Data type: {upload.data_type}",
            f"Contains: {', '.join(upload.contains) if upload.contains else 'Not specified'}",
            f"Extraction confidence: {upload.extraction_confidence}",
            f"Size: {upload.size_bytes} bytes",
        ],
    )


def _load_uploaded_files(patient_id: str) -> list[AggregationUploadedFile]:
    root = _patient_root(patient_id)
    if not root.exists():
        return []
    files: list[AggregationUploadedFile] = []
    for path in sorted(root.glob("*.metadata.json")):
        try:
            files.append(AggregationUploadedFile.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    return files


def _resource_counts(patient_id: str) -> dict[str, int]:
    loaded = load_patient(patient_id)
    if loaded is None:
        return {}
    record, _stats = loaded
    return {
        "conditions": len(record.conditions),
        "medications": len(record.medications),
        "encounters": len(record.encounters),
        "observations": len(record.observations),
        "diagnostic_reports": len(record.diagnostic_reports),
        "procedures": len(record.procedures),
        "immunizations": len(record.immunizations),
        "allergies": len(record.allergies),
        "claims": len(record.claims),
        "parse_warnings": len(record.parse_warnings),
    }


def _latest_encounter(patient_id: str) -> datetime | None:
    loaded = load_patient(patient_id)
    if loaded is None:
        return None
    record, _stats = loaded
    starts = [enc.period.start for enc in record.encounters if enc.period.start]
    return max(starts) if starts else None


def source_inventory(patient_id: str) -> AggregationEnvironmentResponse:
    counts = _resource_counts(patient_id)
    uploads = _load_uploaded_files(patient_id)
    private_available = private_cedars_available()
    total_records = sum(value for key, value in counts.items() if key != "parse_warnings")

    cards: list[AggregationSourceCard] = [
        AggregationSourceCard(
            id="synthea-fhir",
            name="Synthea FHIR patient bundle",
            category="synthetic_fhir",
            mode="available" if counts else "missing",
            status_label="Loaded" if counts else "No bundle selected",
            record_count=total_records,
            last_updated=_latest_encounter(patient_id),
            confidence="high" if counts else "not_started",
            posture="Synthetic public-safe FHIR data. Useful for complete workflow demos without private data exposure.",
            next_action="Use this as the baseline chart surface for source coverage, cleaning, and readiness checks.",
            help_title="Synthetic FHIR environment",
            help_body="Synthea lets us demonstrate the end-to-end aggregation workflow while avoiding private patient data in public demos.",
            evidence=[f"{label.replace('_', ' ').title()}: {count}" for label, count in counts.items() if count],
        ),
        AggregationSourceCard(
            id="private-blake-cedars",
            name="Private Cedars proof-of-life export",
            category="private_ehi",
            mode="private" if private_available else "missing",
            status_label="Available locally" if private_available else "Not detected",
            record_count=0,
            confidence="medium" if private_available else "not_started",
            posture="Private local-only data. Raw data and generated artifacts must stay ignored and unstaged.",
            next_action="Use only for local proof-of-life review; keep synthetic mode as the public fallback.",
            help_title="Private proof-of-life mode",
            help_body="This mode proves we can recognize local real-world exports without committing private Blake/Cedars data.",
            evidence=["Local private source path detected."] if private_available else ["No configured local source found."],
        ),
        AggregationSourceCard(
            id="patient-portals",
            name="Health system portals",
            category="portal",
            mode="planned",
            status_label="Target adapter",
            confidence="not_started",
            posture="End-state support for SMART/FHIR, MyChart-style exports, and manual portal downloads.",
            next_action="Ask the patient which portals and health systems are missing.",
            help_title="Portal source planning",
            help_body="Portal inventory should capture where data may live before we try to automate or guide collection.",
            evidence=["Epic/MyChart, hospital portals, specialist clinics, and direct FHIR exports."],
        ),
        AggregationSourceCard(
            id="labs-diagnostics",
            name="Labs and diagnostics",
            category="lab",
            mode="planned",
            status_label="Target adapter",
            confidence="not_started",
            posture="End-state support for commercial labs, imaging reports, and PDF diagnostic packets.",
            next_action="Collect lab portals, PDF reports, and any uploaded diagnostic files.",
            help_title="Lab source planning",
            help_body="Labs often contain the highest-yield missing evidence for longitudinal clinical review.",
            evidence=["Function Health, Quest, Labcorp, imaging reports, scanned PDFs."],
        ),
        AggregationSourceCard(
            id="pharmacy-payer",
            name="Pharmacy and payer records",
            category="pharmacy",
            mode="planned",
            status_label="Target adapter",
            confidence="not_started",
            posture="End-state support for fill history, claims, prior authorization, and coverage context.",
            next_action="Use medication reality checks to identify missing fill or access history.",
            help_title="Medication source planning",
            help_body="Pharmacy and payer records help distinguish prescribed medications from what was actually filled or covered.",
            evidence=["Retail pharmacy exports, PBM records, payer claims, prior authorization history."],
        ),
        AggregationSourceCard(
            id="wearables",
            name="Wearables and patient-generated data",
            category="wearable",
            mode="planned",
            status_label="Target adapter",
            confidence="not_started",
            posture="End-state support for Apple Health, Whoop, home devices, and functional status signals.",
            next_action="Capture which devices and metrics could add clinically useful context.",
            help_title="Wearable source planning",
            help_body="Patient-generated data should be labeled separately and used for context, trends, and follow-up questions.",
            evidence=["Apple Health, Whoop, BP cuffs, glucose monitors, sleep and activity exports."],
        ),
    ]

    cards.extend(_source_card_for_upload(upload) for upload in uploads)

    return AggregationEnvironmentResponse(
        patient_id=patient_id,
        patient_label=_patient_label(patient_id),
        environment_label="Proof-of-concept aggregation workspace",
        source_posture=(
            "Synthetic FHIR powers the public demo. Private and uploaded sources are local-only staging inputs until extraction "
            "and review workflows promote candidate facts."
        ),
        private_blake_cedars_available=private_available,
        synthetic_resource_counts=counts,
        uploaded_files=uploads,
        source_cards=cards,
        guidance=[
            "Use synthetic FHIR to show end-to-end behavior safely.",
            "Use private proof-of-life only when local data exists and privacy posture is visible.",
            "Treat uploads as source material, not chart truth, until extraction and review are complete.",
        ],
    )


def _duplicate_medications(patient_id: str) -> list[str]:
    loaded = load_patient(patient_id)
    if loaded is None:
        return []
    record, _stats = loaded
    counts = Counter(med.display.strip().lower() for med in record.medications if med.display.strip())
    return [name for name, count in counts.items() if count > 1][:5]


def _active_med_count(patient_id: str) -> int:
    loaded = load_patient(patient_id)
    if loaded is None:
        return 0
    record, _stats = loaded
    return sum(1 for med in record.medications if med.status == "active")


def cleaning_queue(patient_id: str) -> AggregationCleaningQueueResponse:
    inventory = source_inventory(patient_id)
    counts = inventory.synthetic_resource_counts
    uploads = inventory.uploaded_files
    duplicate_meds = _duplicate_medications(patient_id)
    active_meds = _active_med_count(patient_id)

    issues: list[AggregationCleaningIssue] = [
        AggregationCleaningIssue(
            id="source-coverage-gap",
            category="source_gap",
            severity="high",
            title="Confirm missing source systems",
            body="The current workspace has synthetic FHIR and local staging signals, but portal, pharmacy, payer, lab, and wearable sources are not yet confirmed for this patient.",
            recommended_action="Open Patient Context and ask which portals, labs, pharmacies, payers, PDFs, and devices should be added.",
            source_ids=["patient-portals", "labs-diagnostics", "pharmacy-payer", "wearables"],
            evidence=[f"{len(inventory.source_cards)} source categories tracked."],
            help_title="Why source gaps matter",
            help_body="A clean chart can still be incomplete. Source gaps explain what evidence may be missing before clinical interpretation.",
        ),
        AggregationCleaningIssue(
            id="medication-reality-check",
            category="medication_reality",
            severity="high" if active_meds else "medium",
            title="Medication list needs patient reality check",
            body="Structured medication records show what was prescribed, but they do not always prove what the patient is currently taking.",
            recommended_action="Ask the patient about current meds, recent stops, supplements, pharmacy fills, and access barriers.",
            source_ids=["synthea-fhir", "pharmacy-payer"],
            evidence=[f"{active_meds} active medication records in the current chart."],
            help_title="Medication reality",
            help_body="Medication reconciliation is a high-yield use case because chart status often lags real patient behavior.",
        ),
        AggregationCleaningIssue(
            id="timeline-transition-gap",
            category="timeline_gap",
            severity="medium",
            title="Care transitions need qualitative explanation",
            body="Encounter and report counts can show activity, but they rarely explain why care moved between sites or why gaps occurred.",
            recommended_action="Use guided Patient Context questions to capture hospitalizations, outside visits, specialist changes, and missed records.",
            source_ids=["synthea-fhir", "patient-portals"],
            evidence=[
                f"{counts.get('encounters', 0)} encounters and {counts.get('diagnostic_reports', 0)} diagnostic reports found."
            ],
            help_title="Timeline gaps",
            help_body="The semantic layer should represent both dated events and patient explanations of unclear transitions.",
        ),
    ]

    if duplicate_meds:
        issues.append(
            AggregationCleaningIssue(
                id="duplicate-medication-candidates",
                category="duplicate_candidate",
                severity="medium",
                title="Possible duplicate medication records",
                body="Some medication names appear more than once and may represent repeat prescriptions, renewals, or duplicates.",
                recommended_action="Group medication episodes before downstream clinical review.",
                source_ids=["synthea-fhir"],
                evidence=[f"Duplicate candidate: {name}" for name in duplicate_meds],
                help_title="Duplicate candidates",
                help_body="Duplicate detection should produce review candidates, not silent merges, because repeat orders can also be clinically meaningful.",
            )
        )

    if uploads:
        issues.append(
            AggregationCleaningIssue(
                id="uploaded-file-extraction",
                category="uncoded_file",
                severity="medium",
                title="Uploaded files need extraction and provenance review",
                body="Local uploads are tracked as source material, but their content has not been parsed into candidate facts yet.",
                recommended_action="Run PDF/FHIR/C-CDA extraction and preserve file-level provenance before publishing.",
                source_ids=[f"upload-{upload.file_id}" for upload in uploads],
                evidence=[f"{upload.file_name} ({upload.content_type})" for upload in uploads[:5]],
                help_title="Uploaded file staging",
                help_body="This keeps upload capability honest: the file is in the workspace, but not automatically promoted into chart truth.",
            )
        )

    issues.append(
        AggregationCleaningIssue(
            id="patient-context-needed",
            category="patient_context",
            severity="medium",
            title="Patient context packet not guaranteed complete",
            body="The record can show structured facts, but it cannot reliably capture patient goals, functional status, preferences, or questions for clinicians.",
            recommended_action="Complete or review the Patient Context guided intake before publishing a chart packet.",
            source_ids=["patient-context"],
            evidence=["Patient-reported context is tracked separately from verified chart facts."],
            help_title="Patient context boundary",
            help_body="Patient Context should travel with the chart while remaining clearly labeled as patient-reported.",
        )
    )

    issue_counts = Counter(issue.severity for issue in issues)
    issue_counts.update({"total": len(issues)})
    return AggregationCleaningQueueResponse(
        patient_id=patient_id,
        patient_label=_patient_label(patient_id),
        issue_counts=dict(issue_counts),
        issues=issues,
        guidance=[
            "Resolve source gaps before claiming chart completeness.",
            "Use Patient Context to clarify patient-reported facts and qualitative history.",
            "Keep candidate facts in review until provenance and confidence are explicit.",
        ],
    )


def readiness(patient_id: str) -> AggregationReadinessResponse:
    inventory = source_inventory(patient_id)
    queue = cleaning_queue(patient_id)
    has_chart = bool(inventory.synthetic_resource_counts)
    has_uploads = bool(inventory.uploaded_files)
    private_available = inventory.private_blake_cedars_available
    high_issues = queue.issue_counts.get("high", 0)

    checklist = [
        AggregationReadinessItem(
            id="chart-baseline",
            label="Baseline chart loaded",
            status="ready" if has_chart else "missing",
            score=100 if has_chart else 0,
            body="A structured FHIR baseline is available for the selected patient." if has_chart else "No structured baseline was found for this patient.",
            next_action="Use this as the safe public demo baseline." if has_chart else "Select a Synthea patient with a local FHIR bundle.",
        ),
        AggregationReadinessItem(
            id="source-coverage",
            label="Source coverage reviewed",
            status="needs_review",
            score=55,
            body="The workspace identifies likely missing portals, labs, pharmacy, payer, and wearable sources.",
            next_action="Complete Source Inventory and Patient Context source questions.",
        ),
        AggregationReadinessItem(
            id="cleaning-queue",
            label="Cleaning queue triaged",
            status="needs_review" if high_issues else "ready",
            score=65 if high_issues else 85,
            body=f"{queue.issue_counts.get('total', 0)} reconciliation issues are currently visible.",
            next_action="Review high-priority issues before presenting the packet as clinically ready.",
        ),
        AggregationReadinessItem(
            id="patient-context",
            label="Patient context captured",
            status="needs_review",
            score=60,
            body="Patient-reported context is available as a separate layer once the guided intake is completed.",
            next_action="Run the Patient Context guided intake and export the Markdown bundle.",
        ),
        AggregationReadinessItem(
            id="uploads",
            label="Uploaded files staged",
            status="ready" if has_uploads else "planned",
            score=80 if has_uploads else 35,
            body="Local uploads are tracked in the source inventory." if has_uploads else "The UI supports local upload staging; extraction remains a next-stage backend workflow.",
            next_action="Upload PDFs, FHIR files, C-CDA documents, or CSVs for local staging.",
        ),
        AggregationReadinessItem(
            id="private-proof",
            label="Private proof-of-life available",
            status="ready" if private_available else "planned",
            score=85 if private_available else 40,
            body="A private local source is detected for proof-of-life review." if private_available else "Private proof-of-life data is optional and should never be required for public demos.",
            next_action="Use private mode only for local review; keep public demos synthetic.",
        ),
    ]
    readiness_score = round(sum(item.score for item in checklist) / len(checklist))
    blockers = [item.label for item in checklist if item.status in {"missing", "needs_review"}]

    return AggregationReadinessResponse(
        patient_id=patient_id,
        patient_label=inventory.patient_label,
        readiness_score=readiness_score,
        posture="Proof-of-concept ready, production ingestion still expanding.",
        checklist=checklist,
        blockers=blockers,
        export_targets=[
            "FHIR Chart surface",
            "Patient Context Markdown bundle",
            "Source and provenance inventory",
            "Cleaning queue review packet",
            "Future agent-readable patient packet",
        ],
    )


def save_upload(
    patient_id: str,
    file_name: str,
    content_type: str | None,
    file_obj: BinaryIO,
    *,
    data_type: str = "Not classified",
    source_name: str = "",
    date_range: str = "",
    contains: list[str] | None = None,
    description: str = "",
    context_notes: str = "",
) -> AggregationUploadResponse:
    root = _patient_root(patient_id)
    root.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file_name).name or "upload.bin"
    file_id = uuid.uuid4().hex[:12]
    target = root / f"{file_id}-{safe_name}"

    size = 0
    with target.open("wb") as out:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                target.unlink(missing_ok=True)
                raise ValueError(f"Upload exceeds {MAX_UPLOAD_BYTES} byte limit.")
            out.write(chunk)

    upload = AggregationUploadedFile(
        file_id=file_id,
        file_name=safe_name,
        content_type=content_type or "application/octet-stream",
        size_bytes=size,
        uploaded_at=_now(),
        status="uploaded" if data_type != "Not classified" or description else "needs_processing",
        data_type=data_type.strip() or "Not classified",
        source_name=source_name.strip(),
        date_range=date_range.strip(),
        contains=contains or [],
        description=description.strip(),
        context_notes=context_notes.strip(),
        storage_path=str(target),
    )
    upload.extraction_confidence = _infer_confidence(upload)  # type: ignore[assignment]
    _upload_metadata_path(patient_id, file_id).write_text(
        upload.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return AggregationUploadResponse(
        file=upload,
        storage_posture="Stored locally under ignored data/aggregation-uploads/. Not merged into chart facts.",
        source_card=_source_card_for_upload(upload),
    )


def delete_upload(patient_id: str, file_id: str) -> AggregationDeleteResponse:
    metadata = _upload_metadata_path(patient_id, file_id)
    if not metadata.exists():
        raise FileNotFoundError(f"Uploaded file not found: {file_id}")
    upload = AggregationUploadedFile.model_validate(json.loads(metadata.read_text(encoding="utf-8")))
    file_path = _upload_file_path(patient_id, upload)
    file_path.unlink(missing_ok=True)
    metadata.unlink(missing_ok=True)
    return AggregationDeleteResponse(deleted=True, file_id=file_id)
