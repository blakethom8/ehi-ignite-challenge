"""Internal playground for C-CDA/PDF to FHIR conversion pipelines."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.core.ccda import convert_ccda_to_fhir_bundle, is_ccda_xml
from lib.extract.lab.bundle_shape import score_bundle_shape
from lib.extract.pipelines import get as get_pdf_pipeline
from lib.extract.pipelines import list_pipelines

router = APIRouter(prefix="/internal/ccda-lab", tags=["internal-ccda-lab"])

MAX_UPLOAD_BYTES = int(os.getenv("CCDA_LAB_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))


class ConverterOption(BaseModel):
    id: str
    label: str
    input_kinds: list[Literal["ccda", "pdf"]]
    backend: str
    available: bool = True
    description: str = ""


class ConverterOptionsResponse(BaseModel):
    options: list[ConverterOption]
    microsoft_configured: bool
    microsoft_status: "MicrosoftConverterStatus"
    upload_limit_bytes: int


class MicrosoftConverterStatus(BaseModel):
    configured: bool
    reachable: bool
    mode: Literal["api", "cli", "none"]
    endpoint: str | None = None
    detail: str = ""


class SourceSectionSummary(BaseModel):
    title: str
    code: str | None = None
    entry_count: int
    expected_resource_types: list[str] = Field(default_factory=list)
    emitted_matching_resources: int = 0


class SourceSummary(BaseModel):
    document_title: str = ""
    patient_display: str = ""
    section_count: int = 0
    entry_count: int = 0
    sections: list[SourceSectionSummary] = Field(default_factory=list)


class CoverageSummary(BaseModel):
    source_section_count: int = 0
    source_entry_count: int = 0
    mappable_section_count: int = 0
    mapped_section_count: int = 0
    emitted_resource_count: int = 0
    emitted_clinical_resource_count: int = 0


class ResourceSample(BaseModel):
    resource_type: str
    id: str | None = None
    display: str = ""
    status: str = ""
    date: str = ""
    value: str = ""


class ConversionResponse(BaseModel):
    filename: str
    content_type: str | None = None
    input_kind: Literal["ccda", "pdf"]
    processor_id: str
    processor_label: str
    backend_used: Literal["microsoft", "fallback", "pdf-pipeline"]
    latency_ms: int
    total_entries: int
    resource_counts: dict[str, int]
    coverage: CoverageSummary
    source_summary: SourceSummary | None = None
    bundle_shape: dict[str, Any]
    samples: list[ResourceSample] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    bundle: dict[str, Any]


CLINICAL_RESOURCE_TYPES = {
    "AllergyIntolerance",
    "Condition",
    "DiagnosticReport",
    "Immunization",
    "MedicationRequest",
    "MedicationStatement",
    "Observation",
    "Procedure",
}


def _microsoft_status() -> MicrosoftConverterStatus:
    base_url = (os.getenv("FHIR_CONVERTER_URL") or "").rstrip("/")
    if base_url:
        parsed = urllib.parse.urlparse(base_url)
        endpoint = parsed.netloc or parsed.path or base_url
        try:
            with urllib.request.urlopen(f"{base_url}/health/check", timeout=2) as response:
                reachable = 200 <= int(response.status) < 500
            return MicrosoftConverterStatus(
                configured=True,
                reachable=reachable,
                mode="api",
                endpoint=endpoint,
                detail="Health endpoint responded." if reachable else "Health endpoint returned an unexpected status.",
            )
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            return MicrosoftConverterStatus(
                configured=True,
                reachable=False,
                mode="api",
                endpoint=endpoint,
                detail=f"Configured but health check failed: {type(exc).__name__}.",
            )
    converter_bin = os.getenv("FHIR_CONVERTER_BIN")
    template_dir = os.getenv("FHIR_CONVERTER_TEMPLATE_DIR")
    if converter_bin and template_dir:
        return MicrosoftConverterStatus(
            configured=True,
            reachable=True,
            mode="cli",
            endpoint=Path(converter_bin).name,
            detail="CLI converter and template directory are configured.",
        )
    return MicrosoftConverterStatus(
        configured=False,
        reachable=False,
        mode="none",
        detail="Set FHIR_CONVERTER_URL or FHIR_CONVERTER_BIN/FHIR_CONVERTER_TEMPLATE_DIR.",
    )


def _processor_options() -> list[ConverterOption]:
    status = _microsoft_status()
    options = [
        ConverterOption(
            id="ccda-auto",
            label="C-CDA auto",
            input_kinds=["ccda"],
            backend="microsoft-or-fallback",
            available=True,
            description="Use Microsoft when configured, otherwise the local fallback parser.",
        ),
        ConverterOption(
            id="ccda-microsoft",
            label="Microsoft FHIR Converter",
            input_kinds=["ccda"],
            backend="microsoft",
            available=status.reachable,
            description="Call the configured Microsoft FHIR Converter service/container.",
        ),
        ConverterOption(
            id="ccda-fallback",
            label="Local fallback parser",
            input_kinds=["ccda"],
            backend="local",
            available=True,
            description="Limited deterministic parser for Patient, DocumentReference, Problems, and Medications.",
        ),
    ]
    for meta in list_pipelines():
        options.append(
            ConverterOption(
                id=meta.name,
                label=meta.name,
                input_kinds=["pdf"],
                backend=", ".join(meta.primary_backends),
                available=True,
                description=meta.description,
            )
        )
    return options


@router.get("/processors")
def list_converter_options() -> ConverterOptionsResponse:
    status = _microsoft_status()
    return ConverterOptionsResponse(
        options=_processor_options(),
        microsoft_configured=status.configured,
        microsoft_status=status,
        upload_limit_bytes=MAX_UPLOAD_BYTES,
    )


@router.post("/convert")
async def convert_document(
    file: UploadFile = File(...),
    processor_id: str = Form("ccda-auto"),
    skip_cache: bool = Form(False),
) -> ConversionResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Upload is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_BYTES} bytes.")

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in {".xml", ".ccda", ".cda", ".pdf"}:
        raise HTTPException(status_code=400, detail="Upload must be a C-CDA XML document or a PDF.")

    input_kind: Literal["ccda", "pdf"] = "pdf" if suffix == ".pdf" else "ccda"
    with tempfile.TemporaryDirectory(prefix="ccda-lab-") as tmp:
        path = Path(tmp) / (Path(file.filename or f"upload{suffix}").name or f"upload{suffix}")
        path.write_bytes(content)
        started = time.perf_counter()
        source_summary = _ccda_source_summary(path) if input_kind == "ccda" else None
        if input_kind == "ccda":
            bundle, label, backend_used, warnings = _convert_ccda(path, processor_id)
        else:
            bundle, label, warnings = _convert_pdf(path, processor_id, skip_cache=skip_cache)
            backend_used = "pdf-pipeline"
        latency_ms = int((time.perf_counter() - started) * 1000)

    shape = asdict(score_bundle_shape(bundle))
    counts = _resource_counts(bundle)
    if source_summary:
        source_summary = _attach_section_match_counts(source_summary, counts)
    return ConversionResponse(
        filename=file.filename or path.name,
        content_type=file.content_type,
        input_kind=input_kind,
        processor_id=processor_id,
        processor_label=label,
        backend_used=backend_used,
        latency_ms=latency_ms,
        total_entries=sum(counts.values()),
        resource_counts=counts,
        coverage=_coverage_summary(source_summary, counts),
        source_summary=source_summary,
        bundle_shape=shape,
        samples=_resource_samples(bundle, limit=80),
        warnings=warnings,
        bundle=bundle,
    )


def _convert_ccda(path: Path, processor_id: str) -> tuple[dict[str, Any], str, Literal["microsoft", "fallback"], list[str]]:
    if not is_ccda_xml(path):
        raise HTTPException(status_code=400, detail="XML upload is not a CDA ClinicalDocument.")
    status = _microsoft_status()
    if processor_id == "ccda-auto":
        if status.reachable:
            bundle = convert_ccda_to_fhir_bundle(str(path), "ccda-lab", mode="microsoft")
            label = "C-CDA auto (Microsoft)"
            backend_used: Literal["microsoft", "fallback"] = "microsoft"
        else:
            bundle = convert_ccda_to_fhir_bundle(str(path), "ccda-lab", mode="fallback")
            label = "C-CDA auto (fallback)"
            backend_used = "fallback"
    elif processor_id == "ccda-microsoft":
        if not status.reachable:
            raise HTTPException(status_code=503, detail=f"Microsoft FHIR Converter is not reachable. {status.detail}")
        bundle = convert_ccda_to_fhir_bundle(str(path), "ccda-lab", mode="microsoft")
        label = "Microsoft FHIR Converter"
        backend_used = "microsoft"
    elif processor_id == "ccda-fallback":
        bundle = convert_ccda_to_fhir_bundle(str(path), "ccda-lab", mode="fallback")
        label = "Local fallback parser"
        backend_used = "fallback"
    else:
        raise HTTPException(status_code=400, detail=f"Processor {processor_id!r} does not accept C-CDA input.")
    warnings = _bundle_warnings(bundle)
    if backend_used == "fallback":
        warnings.append("Using the local fallback parser; C-CDA section coverage is intentionally limited.")
    return bundle, label, backend_used, warnings


def _convert_pdf(path: Path, processor_id: str, *, skip_cache: bool) -> tuple[dict[str, Any], str, list[str]]:
    if processor_id.startswith("ccda-"):
        raise HTTPException(status_code=400, detail=f"Processor {processor_id!r} does not accept PDF input.")
    try:
        pipeline_cls = get_pdf_pipeline(processor_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown PDF pipeline: {processor_id}") from exc
    pipeline = pipeline_cls()
    try:
        bundle = pipeline.extract(path, skip_cache=skip_cache)  # type: ignore[call-arg]
    except TypeError:
        bundle = pipeline.extract(path)  # type: ignore[call-arg]
    if not isinstance(bundle, dict) or bundle.get("resourceType") != "Bundle":
        raise HTTPException(status_code=502, detail=f"Pipeline {processor_id!r} did not return a FHIR Bundle.")
    return bundle, processor_id, _bundle_warnings(bundle)


def _resource_counts(bundle: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in bundle.get("entry", []) or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict) and resource.get("resourceType"):
            counts[str(resource["resourceType"])] += 1
    return dict(sorted(counts.items()))


def _resource_samples(bundle: dict[str, Any], *, limit: int = 12) -> list[ResourceSample]:
    samples: list[ResourceSample] = []
    for entry in bundle.get("entry", []) or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        samples.append(
            ResourceSample(
                resource_type=str(resource.get("resourceType") or "Resource"),
                id=str(resource.get("id")) if resource.get("id") else None,
                display=_resource_display(resource),
                status=_resource_status(resource),
                date=_resource_date(resource),
                value=_resource_value(resource),
            )
        )
        if len(samples) >= limit:
            break
    return samples


def _ccda_source_summary(path: Path) -> SourceSummary:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return SourceSummary()
    sections: list[SourceSectionSummary] = []
    for section in (element for element in root.iter() if _local_name(element.tag) == "section"):
        title = _text(_child(section, "title")) or "Untitled section"
        code_el = _child(section, "code")
        code = code_el.attrib.get("code") if code_el is not None else None
        entry_count = sum(1 for element in section.iter() if _local_name(element.tag) == "entry")
        sections.append(
            SourceSectionSummary(
                title=title,
                code=code,
                entry_count=entry_count,
                expected_resource_types=_expected_resource_types_for_section(title, code),
            )
        )
    return SourceSummary(
        document_title=_text(_child(root, "title")),
        patient_display=_patient_display_from_ccda(root),
        section_count=len(sections),
        entry_count=sum(section.entry_count for section in sections),
        sections=sections,
    )


def _attach_section_match_counts(summary: SourceSummary, counts: dict[str, int]) -> SourceSummary:
    sections: list[SourceSectionSummary] = []
    consumed: Counter[str] = Counter()
    for section in summary.sections:
        matching = 0
        for resource_type in section.expected_resource_types:
            remaining = max(counts.get(resource_type, 0) - consumed[resource_type], 0)
            if remaining > 0:
                matching += remaining
                consumed[resource_type] += remaining
        sections.append(section.model_copy(update={"emitted_matching_resources": matching}))
    return summary.model_copy(update={"sections": sections})


def _coverage_summary(summary: SourceSummary | None, counts: dict[str, int]) -> CoverageSummary:
    clinical_count = sum(count for resource_type, count in counts.items() if resource_type in CLINICAL_RESOURCE_TYPES)
    if summary is None:
        return CoverageSummary(
            emitted_resource_count=sum(counts.values()),
            emitted_clinical_resource_count=clinical_count,
        )
    mappable_sections = [section for section in summary.sections if section.expected_resource_types and section.entry_count > 0]
    mapped_sections = [section for section in mappable_sections if section.emitted_matching_resources > 0]
    return CoverageSummary(
        source_section_count=summary.section_count,
        source_entry_count=summary.entry_count,
        mappable_section_count=len(mappable_sections),
        mapped_section_count=len(mapped_sections),
        emitted_resource_count=sum(counts.values()),
        emitted_clinical_resource_count=clinical_count,
    )


def _expected_resource_types_for_section(title: str, code: str | None) -> list[str]:
    normalized = f"{code or ''} {title}".lower()
    mappings = [
        (("11450-4", "problem", "diagnos"), ["Condition"]),
        (("10160-0", "medication"), ["MedicationRequest", "MedicationStatement"]),
        (("48765-2", "allerg"), ["AllergyIntolerance"]),
        (("30954-2", "result", "lab"), ["Observation", "DiagnosticReport"]),
        (("8716-3", "vital"), ["Observation"]),
        (("11369-6", "immunization", "vaccine"), ["Immunization"]),
        (("47519-4", "procedure", "surgery"), ["Procedure"]),
        (("46240-8", "encounter", "visit"), ["Encounter"]),
    ]
    for needles, resource_types in mappings:
        if any(needle in normalized for needle in needles):
            return resource_types
    return []


def _patient_display_from_ccda(root: ET.Element) -> str:
    patient = next((element for element in root.iter() if _local_name(element.tag) == "patient"), None)
    if patient is None:
        return ""
    name = _child(patient, "name")
    if name is None:
        return ""
    family = _text(_child(name, "family"))
    given = " ".join(_text(child) for child in name if _local_name(child.tag) == "given")
    return " ".join(part for part in [given, family] if part).strip()


def _child(element: ET.Element, local_name: str) -> ET.Element | None:
    for child in element:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(" ".join(element.itertext()).split())


def _resource_date(resource: dict[str, Any]) -> str:
    for key in ("effectiveDateTime", "authoredOn", "recordedDate", "performedDateTime", "date", "onsetDateTime"):
        value = resource.get(key)
        if isinstance(value, str) and value:
            return value[:10]
    for key in ("effectivePeriod", "performedPeriod"):
        value = resource.get(key)
        if isinstance(value, dict):
            date_value = value.get("start") or value.get("end")
            if isinstance(date_value, str) and date_value:
                return date_value[:10]
    return ""


def _resource_value(resource: dict[str, Any]) -> str:
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict):
        value = quantity.get("value")
        unit = quantity.get("unit") or quantity.get("code") or ""
        return " ".join(str(part) for part in [value, unit] if part)
    concept = resource.get("valueCodeableConcept")
    if isinstance(concept, dict):
        return str(concept.get("text") or "")
    if isinstance(resource.get("valueString"), str):
        return str(resource["valueString"])
    return ""


def _resource_status(resource: dict[str, Any]) -> str:
    status = resource.get("status")
    if isinstance(status, str):
        return status
    clinical_status = resource.get("clinicalStatus")
    if isinstance(clinical_status, dict):
        text = clinical_status.get("text")
        if isinstance(text, str):
            return text
        coding = clinical_status.get("coding")
        if isinstance(coding, list) and coding and isinstance(coding[0], dict):
            return str(coding[0].get("display") or coding[0].get("code") or "")
    return ""


def _resource_display(resource: dict[str, Any]) -> str:
    rt = resource.get("resourceType")
    if rt == "Patient":
        names = resource.get("name") if isinstance(resource.get("name"), list) else []
        first = names[0] if names and isinstance(names[0], dict) else {}
        given = " ".join(str(v) for v in first.get("given", []) if v) if isinstance(first.get("given"), list) else ""
        return " ".join(part for part in [given, str(first.get("family") or "")] if part).strip()
    for field in ("code", "medicationCodeableConcept", "vaccineCode", "type"):
        value = resource.get(field)
        if isinstance(value, dict):
            text = value.get("text")
            if text:
                return str(text)
            coding = value.get("coding")
            if isinstance(coding, list) and coding and isinstance(coding[0], dict):
                return str(coding[0].get("display") or coding[0].get("code") or "")
    if isinstance(resource.get("valueString"), str):
        return resource["valueString"]
    return str(resource.get("status") or "")


def _bundle_warnings(bundle: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    counts = _resource_counts(bundle)
    if counts.get("Patient", 0) == 0:
        warnings.append("No Patient resource was emitted.")
    if counts.get("Patient", 0) > 1:
        warnings.append("Multiple Patient resources were emitted.")
    clinical_count = sum(counts.get(rt, 0) for rt in ("Condition", "MedicationRequest", "Observation", "AllergyIntolerance", "Procedure", "Immunization"))
    if clinical_count == 0:
        warnings.append("No clinical fact resources were emitted beyond document/patient scaffolding.")
    return warnings
