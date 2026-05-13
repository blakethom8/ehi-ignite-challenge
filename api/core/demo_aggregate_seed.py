"""Ensure the multi-source demo personas have their synthetic source documents
staged into the aggregation-uploads store, so that the data-aggregation
feature shows them as already-uploaded sources without any user action.

Source of truth: ``data/demo-profiles/<persona>/documents/``
Destination:     ``data/aggregation-uploads/<resolved-patient-id>/``

IMPORTANT: the aggregation endpoint resolves the demo alias to the actual
Patient.id via ``authorize_patient_access`` BEFORE looking up uploads, so
this seeder must stage under the resolved Patient.id (the
``actual_patient_id`` on each ``DemoPatientConfig``), not under the alias.

The seeder is idempotent — if the destination metadata file for an upload
already exists, it leaves both the file and the metadata untouched (so any
user edits to source-card descriptions via the UI survive a restart). Missing
documents get staged with carefully-chosen metadata that matches the source's
real-world provenance (hospital discharge summary, outside-provider C-CDA,
device telemetry FHIR feed, etc.).

This module is called from ``api.main`` at startup. It silently no-ops if
the data/demo-profiles/ tree isn't present (e.g. in tests with a tmpdir).
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from api.models import AggregationUploadedFile

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PROFILES_ROOT = REPO_ROOT / "data" / "demo-profiles"
UPLOAD_ROOT = REPO_ROOT / "data" / "aggregation-uploads"


@dataclass(frozen=True)
class DemoSourceDoc:
    """A single synthetic source document to stage as a pre-uploaded upload.

    ``filename`` is the basename under the persona's ``documents/`` directory.
    The remaining fields populate the ``AggregationUploadedFile`` metadata
    JSON so the source intake page shows a polished card per source.
    """

    filename: str
    source_name: str
    data_type: str
    description: str
    contains: tuple[str, ...]
    date_range: str = ""
    context_notes: str = ""
    extraction_confidence: Literal["high", "medium", "low", "unknown"] = "medium"


# Each demo-aggregate alias maps to a persona directory + an ordered list of
# documents to surface. Order here is the order they appear in the source
# intake list.
DEMO_AGGREGATE_PERSONAS: dict[str, tuple[str, tuple[DemoSourceDoc, ...]]] = {
    "demo-aggregate-icu": (
        "icu-mimic",
        (
            DemoSourceDoc(
                filename="discharge_summary_icu.pdf",
                source_name="BIDMC Medical ICU",
                data_type="Hospital discharge summary",
                description="Most recent ICU admission (3-day stay). Narrative hospital course, reconciled discharge meds, pending studies, follow-up plan.",
                contains=("Hospital course", "Discharge meds", "Pending studies", "Follow-up"),
                date_range="July 2148",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="anticoag_clinic_letter.pdf",
                source_name="BIDMC Anticoagulation Clinic",
                data_type="Outpatient clinic letter",
                description="6-month apixaban management summary to PCP. Dose history, peri-procedural hold instructions, bleeding history.",
                contains=("Apixaban dosing", "INR / DOAC history", "Bleeding history"),
                date_range="Last 6 months",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="pacemaker_interrogation.pdf",
                source_name="BIDMC EP Lab · Medtronic CareLink",
                data_type="Device interrogation report",
                description="In-office dual-chamber pacemaker interrogation. Battery, lead measurements, % pacing, mode-switch episodes.",
                contains=("Pacemaker model", "Lead impedance", "% pacing", "Battery"),
                date_range="In-office interrogation",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="sleep_study_polysomnography.pdf",
                source_name="BIDMC Sleep Disorders Center",
                data_type="Diagnostic procedure report",
                description="Polysomnography demonstrating severe OSA. AHI, oxygen desaturation index, periodic limb movements, CPAP titration recommendation.",
                contains=("AHI", "OSA severity", "CPAP recommendation"),
                date_range="~2 years prior to ICU admission",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="preop_anesthesia_questionnaire.pdf",
                source_name="BIDMC Pre-Admission Testing · Patient self-report",
                data_type="Patient-completed questionnaire",
                description="Pre-op intake form filled in by the patient. Self-reported meds, allergies, family anesthesia history. Includes a self-reported anticoagulation hold that conflicts with the clinic record.",
                contains=("Self-reported meds", "Allergies", "Family hx"),
                date_range="Pre-admission intake",
                context_notes="Patient self-report — confidence is intentionally lower than clinical sources.",
                extraction_confidence="low",
            ),
            DemoSourceDoc(
                filename="outside_oncology_records_ccda.xml",
                source_name="Dana-Farber Cancer Institute (outside)",
                data_type="C-CDA continuity of care",
                description="Outside hematology/oncology continuity-of-care document covering CLL. Problem list, oncology medications, recent CBC.",
                contains=("CLL", "Oncology meds", "CBC trend"),
                date_range="Past 18 months",
                extraction_confidence="medium",
            ),
            DemoSourceDoc(
                filename="outside_oncology_fhir_feed.json",
                source_name="Dana-Farber Cancer Institute · FHIR R4 API",
                data_type="Outside FHIR feed",
                description="Structured FHIR Bundle from Dana-Farber's outpatient hematology system. Includes an active ibrutinib MedicationStatement that does not appear in the in-house chart.",
                contains=("Outside-provider FHIR", "Ibrutinib", "Serial CBC"),
                date_range="Past 18 months",
                extraction_confidence="high",
            ),
        ),
    ),
    "demo-aggregate-oncology": (
        "oncology-breast-mcode",
        (
            DemoSourceDoc(
                filename="mammography_report.pdf",
                source_name="Outpatient Breast Imaging",
                data_type="Imaging report",
                description="Screening mammogram with tomosynthesis. Identifies a BI-RADS 4C spiculated mass and recommends image-guided core needle biopsy.",
                contains=("BI-RADS finding", "Mass localization", "Biopsy recommendation"),
                date_range="February 2024",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="pathology_report.pdf",
                source_name="Hospital Department of Pathology",
                data_type="Surgical pathology report",
                description="Core needle biopsy result confirming invasive ductal carcinoma. ER/PR/HER2 biomarker profile and Ki-67.",
                contains=("IDC diagnosis", "ER/PR/HER2", "Ki-67"),
                date_range="Within 2 weeks of imaging",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="tumor_board_summary.pdf",
                source_name="Breast Multidisciplinary Tumor Board",
                data_type="Multidisciplinary review",
                description="Tumor board consensus recommendation: lumpectomy + sentinel lymph node biopsy with adjuvant decision pending Oncotype DX.",
                contains=("MDR consensus", "Treatment plan", "Oncotype DX gating"),
                date_range="~2 weeks after pathology",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="genetic_counseling_letter.pdf",
                source_name="Cancer Genetics Program",
                data_type="Specialty consult letter",
                description="Genetic counseling visit summary recommending multi-gene panel testing. Family history narration disagrees with the structured FamilyMemberHistory in the FHIR record.",
                contains=("Family history", "BRCA panel recommendation", "Risk assessment"),
                date_range="After tumor board",
                context_notes="Narrative family history disagrees with structured FamilyMemberHistory.",
                extraction_confidence="medium",
            ),
            DemoSourceDoc(
                filename="outside_records_ccda.xml",
                source_name="Prior community gynecologist (outside)",
                data_type="C-CDA continuity of care",
                description="Prior community gyn records — historical fibrocystic findings, OCP history, allergies, prior screening Pap and mammograms.",
                contains=("Prior screenings", "Allergies", "Gyn history"),
                date_range="2018-2023",
                extraction_confidence="medium",
            ),
            DemoSourceDoc(
                filename="patient_app_symptom_tracker_fhir.json",
                source_name="OncoLife symptom-tracker app",
                data_type="Patient-generated FHIR",
                description="8 weeks of patient-reported nausea, fatigue, pain, and step counts. Implies active chemotherapy that does not yet appear in the in-house chart.",
                contains=("Self-reported symptoms", "Step count", "Chemo cycle signal"),
                date_range="8-week window",
                context_notes="Patient app uses different identifier system + name spelling — exercises fuzzy patient matching.",
                extraction_confidence="medium",
            ),
        ),
    ),
    "demo-aggregate-cardiac": (
        "cardiac-coherent",
        (
            DemoSourceDoc(
                filename="cardiology_post_arrest_consult.pdf",
                source_name="Inpatient Cardiology",
                data_type="Specialist consult note",
                description="Cardiology consult after the patient's cardiac arrest. ROSC details, EKG, echo (EF 30%), cath findings, post-arrest plan.",
                contains=("Cardiac arrest workup", "Echo EF", "Cath findings"),
                date_range="Post-arrest hospitalization",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="stroke_discharge_summary.pdf",
                source_name="Stroke Service / Neurology",
                data_type="Hospital discharge summary",
                description="Discharge summary from a prior acute ischemic stroke admission. IV alteplase given, MRI showed acute infarct + silent microhemorrhages.",
                contains=("Acute stroke care", "tPA administration", "MRI findings"),
                date_range="~1 year prior to cardiac arrest",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="prostate_pathology_report.pdf",
                source_name="Hospital Department of Pathology",
                data_type="Surgical pathology report",
                description="Transrectal prostate biopsy result. Gleason 3+4=7, 3 of 12 cores positive, ~15% involvement.",
                contains=("Gleason score", "Core breakdown", "Prostate cancer diagnosis"),
                date_range="Initial diagnosis",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="oncology_chemo_plan.pdf",
                source_name="Medical Oncology / GU",
                data_type="Treatment plan letter",
                description="Oncology treatment plan letter outlining combined ADT (leuprolide) + docetaxel for metastatic castration-sensitive prostate cancer.",
                contains=("Chemo regimen", "Schedule + cycles", "Cardiac considerations"),
                date_range="At treatment initiation",
                context_notes="Schedule narrated as every 3 weeks; structured MedicationRequest coded every 4 weeks.",
                extraction_confidence="medium",
            ),
            DemoSourceDoc(
                filename="cardiac_mri_report.pdf",
                source_name="Cardiothoracic Radiology",
                data_type="Imaging report",
                description="Human-readable cardiac MRI read. Companion to the raw DICOM file in this persona's imaging/ directory.",
                contains=("LVEF", "LGE pattern", "Imaging findings"),
                date_range="Post-arrest assessment",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="pacemaker_telemetry_fhir.json",
                source_name="Medtronic CareLink remote monitoring",
                data_type="Device telemetry FHIR feed",
                description="6 months of device-generated FHIR Observations — AT/AF burden, % pacing, lead impedance, battery voltage.",
                contains=("AT/AF burden", "% pacing trend", "Lead impedance"),
                date_range="Past 6 months",
                context_notes="AF burden trends 5% → 22%; latest RV pacing 38% — conflicts with the in-office interrogation reading.",
                extraction_confidence="high",
            ),
        ),
    ),
    "demo-aggregate-polypharmacy": (
        "polypharmacy-synthea",
        (
            DemoSourceDoc(
                filename="discharge_summary_recent.pdf",
                source_name="Hospital Internal Medicine",
                data_type="Hospital discharge summary",
                description="Most recent observation stay (fall + UTI). Full med reconciliation list, goals-of-care discussion, follow-up.",
                contains=("Med reconciliation", "Goals of care", "Discharge plan"),
                date_range="Most recent admission",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="anticoag_clinic_letter.pdf",
                source_name="Outpatient Coumadin Clinic",
                data_type="Outpatient clinic letter",
                description="6-month warfarin INR monitoring summary. Dose adjustments, held doses during FOLFOX cycles, bleeding/bruising history.",
                contains=("Warfarin INR trail", "Dose history", "Bleeding events"),
                date_range="Past 6 months",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="neurology_dementia_consult.pdf",
                source_name="Neurology · Memory Disorders Clinic",
                data_type="Specialist consult note",
                description="Cognitive assessment establishing Alzheimer's disease. MMSE, clock-draw, MRI atrophy, galantamine initiation.",
                contains=("Cognitive testing", "MRI findings", "Galantamine plan"),
                date_range="Initial dementia evaluation",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="colonoscopy_pathology.pdf",
                source_name="GI / Endoscopy + Pathology",
                data_type="Procedure + pathology report",
                description="Colonoscopy with polyp removal and rectal-mass biopsy. Combined procedure note + pathology in one document.",
                contains=("Polyps", "Adenocarcinoma diagnosis", "Staging recommendation"),
                date_range="Initial colorectal workup",
                extraction_confidence="high",
            ),
            DemoSourceDoc(
                filename="outside_pcp_ccda.xml",
                source_name="Community primary care (referring PCP)",
                data_type="C-CDA continuity of care",
                description="Outside PCP records sent when the patient established at the specialist office. STALE — lists aspirin instead of warfarin, predates anticoagulation.",
                contains=("Problem list", "Med list (stale)", "Recent labs"),
                date_range="Pre-warfarin era",
                context_notes="Outside med list is stale — aspirin listed where chart now has warfarin.",
                extraction_confidence="low",
            ),
            DemoSourceDoc(
                filename="home_monitoring_fhir_feed.json",
                source_name="Lively Care home monitoring (BP cuff + glucometer)",
                data_type="Patient-collected FHIR",
                description="60 days of home-monitoring FHIR. Connected BP cuff, glucometer, and weight scale. Shows uncontrolled HTN and glucose despite the chart's qualitative coding.",
                contains=("Home BP", "Home glucose", "Weight"),
                date_range="60-day window",
                context_notes="Quantitative home data contradicts qualitative diagnoses in the chart.",
                extraction_confidence="high",
            ),
        ),
    ),
}


def _safe_id_dir(value: str) -> Path:
    """Mirrors aggregation._safe_id but kept local to avoid a circular import.

    The aggregation backend keys upload directories by the result of
    ``_safe_id(resolved_patient_id)`` — the SAME function applied to the
    SAME id we use here — so following its rules verbatim is the contract.
    """
    import re

    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return UPLOAD_ROOT / (safe[:120] or "patient")


def _stable_file_id(scope: str, filename: str) -> str:
    """Deterministic id derived from a scope + filename so reruns don't re-stage."""
    digest = hashlib.sha1(f"{scope}:{filename}".encode("utf-8")).hexdigest()
    return f"seed-{digest[:16]}"


def _guess_content_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime
    suffix = path.suffix.lower()
    if suffix == ".xml":
        return "application/xml"
    if suffix == ".json":
        return "application/json"
    if suffix == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _parse_status_for(content_type: str) -> str:
    """Pre-staged JSON / XML are already structured; PDFs need extraction.

    Aligns with the existing AggregationUploadedFile.parse_status values.
    """
    if content_type == "application/json":
        return "structured"
    if content_type == "application/xml":
        return "ready_to_extract"
    return "ready_to_extract"


def _next_step_for(content_type: str) -> str:
    if content_type == "application/json":
        return "Already structured — ready to harmonize."
    if content_type == "application/xml":
        return "Parse C-CDA into FHIR resources."
    return "Run multipass PDF extraction."


def _seed_one_persona(alias: str, persona_dir: str, docs: tuple[DemoSourceDoc, ...]) -> int:
    """Stage every document in ``docs`` into the persona's aggregation-uploads
    directory if it isn't already there. The directory is keyed by the demo
    config's ``actual_patient_id`` because the aggregation endpoint resolves
    aliases to that id BEFORE looking up uploads.

    Returns the number of files newly staged.
    """

    # Imported lazily to avoid an import cycle at module load (auth.py imports
    # from api.core.aggregation, which can re-enter this module's parent).
    from api.core.auth import DEMO_PATIENT_BY_ALIAS

    config = DEMO_PATIENT_BY_ALIAS.get(alias)
    if config is None:
        logger.warning("demo-aggregate seed: alias %s missing from DEMO_PATIENT_BY_ALIAS", alias)
        return 0

    source_root = DEMO_PROFILES_ROOT / persona_dir / "documents"
    if not source_root.exists():
        logger.debug("demo-aggregate seed: no source docs at %s — skipping %s", source_root, alias)
        return 0

    # IMPORTANT: stage under the resolved Patient.id, NOT the alias. The
    # aggregation endpoint translates demo aliases to actual_patient_id via
    # authorize_patient_access before looking up uploads — if we keyed by
    # alias, the source intake page would silently show no pre-staged docs.
    dest_root = _safe_id_dir(config.actual_patient_id)
    dest_root.mkdir(parents=True, exist_ok=True)

    newly_staged = 0
    for doc in docs:
        src = source_root / doc.filename
        if not src.exists():
            logger.warning("demo-aggregate seed: missing source doc %s", src)
            continue

        # Scope the file id by the resolved Patient.id so any future alias
        # rename doesn't change the staged file ids.
        file_id = _stable_file_id(config.actual_patient_id, doc.filename)
        metadata_path = dest_root / f"{file_id}.metadata.json"
        if metadata_path.exists():
            # Either the seeder already ran or the user edited this card via
            # the UI. Either way, do not clobber.
            continue

        # Copy the actual file alongside the metadata.
        dest_file = dest_root / f"{file_id}{src.suffix}"
        if not dest_file.exists():
            shutil.copyfile(src, dest_file)

        content_type = _guess_content_type(src)
        size_bytes = dest_file.stat().st_size

        upload = AggregationUploadedFile(
            file_id=file_id,
            file_name=doc.filename,
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_at=datetime.now(timezone.utc),
            status="uploaded",
            data_type=doc.data_type,
            source_name=doc.source_name,
            date_range=doc.date_range,
            contains=list(doc.contains),
            description=doc.description,
            context_notes=doc.context_notes,
            extraction_confidence=doc.extraction_confidence,
            storage_path=str(dest_file.relative_to(REPO_ROOT)),
            parse_status=_parse_status_for(content_type),  # type: ignore[arg-type]
            next_step=_next_step_for(content_type),
        )
        metadata_path.write_text(upload.model_dump_json(indent=2), encoding="utf-8")
        newly_staged += 1

    return newly_staged


def seed_demo_aggregate_uploads() -> dict[str, int]:
    """Idempotently stage demo-aggregate persona documents into the
    aggregation-uploads store. Returns a per-alias count of files newly
    staged. Safe to call on every startup."""

    if not DEMO_PROFILES_ROOT.exists():
        return {}

    out: dict[str, int] = {}
    for alias, (persona_dir, docs) in DEMO_AGGREGATE_PERSONAS.items():
        try:
            out[alias] = _seed_one_persona(alias, persona_dir, docs)
        except Exception:  # noqa: BLE001
            logger.exception("demo-aggregate seed: failed for alias=%s", alias)
            out[alias] = 0
    return out
