"""Reference bundle review API.

Draft review state is stored outside immutable pipeline run artifacts at:

    data/pdf-lab/reviews/<run-id>/review.json

Publishing uses lib.extract.lab.ground_truth.save_ground_truth() to create a
new reviewed reference bundle version under data/pdf-lab/ground-truth/.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import io
import json
from pathlib import Path
import threading
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from api.core.pdf_fact_locator import FactLocatorInput, PdfTextMatch, find_pdf_matches, locate_fact_in_pdf as locate_pdf_fact
from lib.extract.lab.ground_truth import list_ground_truth_versions, load_ground_truth_version, save_ground_truth
from lib.extract.lab.recorder import REPO_ROOT
from lib.extract.lab.review import render_resource_summary

router = APIRouter(prefix="/ground-truth-review", tags=["ground-truth-review"])

LAB_ROOT = REPO_ROOT / "data" / "pdf-lab"
RUNS_DIR = LAB_ROOT / "runs"
REVIEWS_DIR = LAB_ROOT / "reviews"
PDF_RENDER_SCALE = 2.0
_PDF_RENDER_LOCK = threading.Lock()

ReviewStatus = Literal["draft", "published"]
FactStatus = Literal[
    "accepted",
    "rejected",
    "edited",
    "missing",
    "uncertain",
    "needs_follow_up",
    "duplicate",
    "unsupported",
]
ReasonCode = Literal[
    "wrong_value",
    "wrong_code",
    "wrong_date",
    "wrong_unit",
    "wrong_status",
    "wrong_linkage",
    "unsupported_by_pdf",
    "missing_from_output",
]
AnnotationType = Literal[
    "supports_fact",
    "contradicts_fact",
    "missing_fact",
    "extraction_error",
    "uncertain",
]


class BBox(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class PdfAnnotation(BaseModel):
    annotation_id: str
    page_number: int = Field(ge=1)
    bbox: BBox
    annotation_type: AnnotationType
    linked_resource_ref: str | None = None
    note: str = ""
    created_at: str
    updated_at: str


class FactDecision(BaseModel):
    decision_id: str
    resource_ref: str
    resource_type: str
    resource_id: str | None = None
    status: FactStatus
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    original_resource: dict[str, Any] | None = None
    edited_resource: dict[str, Any] | None = None
    reviewer_note: str = ""
    linked_annotation_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ReviewSession(BaseModel):
    review_id: str
    run_id: str
    pdf_sha256: str
    source_pdf_path: str
    candidate_bundle_path: str
    reviewer: str = "Blake"
    status: ReviewStatus = "draft"
    created_at: str
    updated_at: str
    published_ground_truth_version: int | None = None
    decisions: list[FactDecision] = Field(default_factory=list)
    annotations: list[PdfAnnotation] = Field(default_factory=list)
    notes: str = ""


class ReviewProgress(BaseModel):
    total_facts: int
    reviewed_facts: int
    accepted_facts: int
    rejected_facts: int
    edited_facts: int
    uncertain_facts: int
    missing_facts: int
    needs_review: int


class ReviewRunSummary(BaseModel):
    run_id: str
    pipeline_name: str
    status: str
    pdf_label: str
    pdf_sha256: str
    started_at: str | None = None
    finished_at: str | None = None
    total_entries: int
    resource_counts: dict[str, int] = Field(default_factory=dict)
    has_source_pdf: bool
    has_bundle: bool
    review_status: ReviewStatus | Literal["not_started"] = "not_started"
    reviewed_facts: int = 0
    published_ground_truth_version: int | None = None
    existing_ground_truth_versions: list[int] = Field(default_factory=list)


class FactSummary(BaseModel):
    resource_ref: str
    resource_type: str
    resource_id: str | None = None
    display: str
    codes: list[str] = Field(default_factory=list)
    value: str | None = None
    date: str | None = None
    status: str | None = None
    patient_ref: str | None = None
    encounter_ref: str | None = None
    source_locator: str | None = None
    original_resource: dict[str, Any]


class ReviewRunDetail(BaseModel):
    run: ReviewRunSummary
    manifest: dict[str, Any]
    facts: list[FactSummary]
    facts_by_type: dict[str, list[FactSummary]]
    review: ReviewSession
    progress: ReviewProgress
    artifact_urls: dict[str, str]


class PublishRequest(BaseModel):
    reviewer: str | None = None
    notes: str | None = None


class PublishResponse(BaseModel):
    run_id: str
    pdf_sha256: str
    version: int
    ground_truth_path: str
    kept_resource_count: int
    rejected_resource_count: int
    missing_fact_count: int
    review: ReviewSession


class GroundTruthVersionSummary(BaseModel):
    version: int
    created_at: str | None = None
    reviewer: str | None = None
    source_run_id: str | None = None
    notes: str = ""
    total_entries: int
    resource_counts: dict[str, int] = Field(default_factory=dict)
    ground_truth_path: str


class PdfPageSummary(BaseModel):
    page_number: int
    width: int
    height: int
    image_url: str


class PdfPagesResponse(BaseModel):
    run_id: str
    page_count: int
    scale: float
    pages: list[PdfPageSummary]


class FactLocationResponse(BaseModel):
    run_id: str
    resource_ref: str
    query: str
    locator_version: str
    matches: list[PdfTextMatch]


@router.get("/runs", response_model=list[ReviewRunSummary])
def list_reviewable_runs() -> list[ReviewRunSummary]:
    """List pipeline runs that have a source PDF and candidate bundle."""
    if not RUNS_DIR.exists():
        return []
    runs = [_run_summary(path.parent) for path in RUNS_DIR.glob("*/manifest.json")]
    reviewable = [run for run in runs if run.has_source_pdf and run.has_bundle]
    return sorted(reviewable, key=lambda run: run.finished_at or run.started_at or "", reverse=True)


@router.get("/runs/{run_id}", response_model=ReviewRunDetail)
def get_review_run(run_id: str) -> ReviewRunDetail:
    run_dir = _run_dir(run_id)
    manifest = _load_manifest(run_dir)
    bundle = _load_bundle(run_dir)
    review = _load_or_create_review(run_dir, manifest)
    facts = _summarize_bundle(bundle)
    facts_by_type: dict[str, list[FactSummary]] = {}
    for fact in facts:
        facts_by_type.setdefault(fact.resource_type, []).append(fact)
    return ReviewRunDetail(
        run=_run_summary(run_dir),
        manifest=manifest,
        facts=facts,
        facts_by_type=facts_by_type,
        review=review,
        progress=_progress(review, len(facts)),
        artifact_urls={
            "pdf": f"/api/ground-truth-review/runs/{run_id}/pdf",
            "bundle": f"/api/ground-truth-review/runs/{run_id}/bundle",
            "review": f"/api/ground-truth-review/runs/{run_id}/review",
        },
    )


@router.get("/runs/{run_id}/pdf")
def get_run_pdf(run_id: str) -> FileResponse:
    path = _run_dir(run_id) / "source.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="source.pdf not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{run_id}.pdf")


@router.get("/runs/{run_id}/pdf/pages", response_model=PdfPagesResponse)
def get_run_pdf_pages(run_id: str) -> PdfPagesResponse:
    """Return page dimensions and image URLs for the rendered PDF viewer."""
    pdf_path = _run_dir(run_id) / "source.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="source.pdf not found")
    page_sizes = _pdf_page_sizes(pdf_path)
    return PdfPagesResponse(
        run_id=run_id,
        page_count=len(page_sizes),
        scale=PDF_RENDER_SCALE,
        pages=[
            PdfPageSummary(
                page_number=index + 1,
                width=round(width * PDF_RENDER_SCALE),
                height=round(height * PDF_RENDER_SCALE),
                image_url=f"/api/ground-truth-review/runs/{run_id}/pdf/pages/{index + 1}.png",
            )
            for index, (width, height) in enumerate(page_sizes)
        ],
    )


@router.get("/runs/{run_id}/pdf/pages/{page_number}.png", response_model=None)
def get_run_pdf_page_image(run_id: str, page_number: int):
    """Render one PDF page to a PNG image.

    Images are cached under data/pdf-lab/reviews/<run-id>/pdf-pages so page
    rendering is stable and the frontend can treat the PDF as inspectable page
    pixels for future annotation overlays.
    """
    if page_number < 1:
        raise HTTPException(status_code=404, detail="PDF page not found")
    pdf_path = _run_dir(run_id) / "source.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="source.pdf not found")
    cache_path = _pdf_page_cache_path(run_id, page_number)
    if cache_path.exists():
        return FileResponse(cache_path, media_type="image/png")
    try:
        png = _render_pdf_page(pdf_path, page_number)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail="PDF page not found") from exc
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(png)
    return Response(content=png, media_type="image/png")


@router.get("/runs/{run_id}/pdf/search", response_model=list[PdfTextMatch])
def search_run_pdf(
    run_id: str,
    q: str = Query(..., min_length=2),
    limit: int = Query(default=12, ge=1, le=50),
) -> list[PdfTextMatch]:
    pdf_path = _run_dir(run_id) / "source.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="source.pdf not found")
    return find_pdf_matches(pdf_path, q, limit=limit)


@router.get("/runs/{run_id}/locate-fact", response_model=FactLocationResponse)
def locate_fact_in_pdf(
    run_id: str,
    resource_ref: str = Query(...),
    limit: int = 8,
) -> FactLocationResponse:
    run_dir = _run_dir(run_id)
    pdf_path = run_dir / "source.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="source.pdf not found")
    facts = _summarize_bundle(_load_bundle(run_dir))
    fact = next((item for item in facts if item.resource_ref == resource_ref), None)
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    location = locate_pdf_fact(pdf_path=pdf_path, fact=_locator_input(fact), limit=limit)
    return FactLocationResponse(
        run_id=run_id,
        resource_ref=resource_ref,
        query=location.query,
        locator_version=location.locator_version,
        matches=location.matches,
    )


@router.get("/runs/{run_id}/bundle")
def get_run_bundle(run_id: str) -> dict[str, Any]:
    return _load_bundle(_run_dir(run_id))


@router.get("/runs/{run_id}/review", response_model=ReviewSession)
def get_review(run_id: str) -> ReviewSession:
    run_dir = _run_dir(run_id)
    return _load_or_create_review(run_dir, _load_manifest(run_dir))


@router.put("/runs/{run_id}/review", response_model=ReviewSession)
def save_review(run_id: str, review: ReviewSession) -> ReviewSession:
    run_dir = _run_dir(run_id)
    manifest = _load_manifest(run_dir)
    if review.run_id != run_id:
        raise HTTPException(status_code=400, detail="Review run_id does not match URL")
    if review.pdf_sha256 != manifest.get("pdf_sha256"):
        raise HTTPException(status_code=400, detail="Review pdf_sha256 does not match run manifest")
    now = _now_iso()
    if not review.created_at:
        review.created_at = now
    review.updated_at = now
    if review.status == "published":
        review.status = "draft"
    _write_review(run_id, review)
    return review


@router.post("/runs/{run_id}/publish", response_model=PublishResponse)
def publish_review(run_id: str, request: PublishRequest | None = None) -> PublishResponse:
    run_dir = _run_dir(run_id)
    manifest = _load_manifest(run_dir)
    bundle = _load_bundle(run_dir)
    review = _load_or_create_review(run_dir, manifest)
    final_bundle, kept, rejected = _bundle_from_review(bundle, review)
    missing_count = sum(1 for decision in review.decisions if decision.status == "missing")
    reviewer = (request.reviewer if request and request.reviewer else review.reviewer) or "unknown"
    notes = (request.notes if request and request.notes is not None else review.notes) or ""
    gtv = save_ground_truth(
        pdf_sha256=review.pdf_sha256,
        pdf_path=review.source_pdf_path,
        bundle=final_bundle,
        decisions=[decision.model_dump(mode="json") for decision in review.decisions],
        reviewer=reviewer,
        source_run_id=run_id,
        notes=notes,
        lab_root=LAB_ROOT,
    )
    review.reviewer = reviewer
    review.notes = notes
    review.status = "published"
    review.published_ground_truth_version = gtv.version
    review.updated_at = _now_iso()
    _write_review(run_id, review)
    gt_path = LAB_ROOT / "ground-truth" / review.pdf_sha256[:8] / f"v{gtv.version}.json"
    return PublishResponse(
        run_id=run_id,
        pdf_sha256=review.pdf_sha256,
        version=gtv.version,
        ground_truth_path=_rel(gt_path),
        kept_resource_count=kept,
        rejected_resource_count=rejected,
        missing_fact_count=missing_count,
        review=review,
    )


@router.get("/ground-truth/{pdf_sha}", response_model=list[GroundTruthVersionSummary])
def list_reviewed_reference_versions(pdf_sha: str) -> list[GroundTruthVersionSummary]:
    versions: list[GroundTruthVersionSummary] = []
    for version in list_ground_truth_versions(pdf_sha, lab_root=LAB_ROOT):
        gtv = load_ground_truth_version(pdf_sha, version, lab_root=LAB_ROOT)
        if gtv is None:
            continue
        path = LAB_ROOT / "ground-truth" / pdf_sha[:8] / f"v{version}.json"
        versions.append(
            GroundTruthVersionSummary(
                version=version,
                created_at=gtv.created_at,
                reviewer=gtv.reviewer,
                source_run_id=gtv.source_run_id,
                notes=gtv.notes,
                total_entries=_bundle_entry_count(gtv.bundle),
                resource_counts=_resource_counts(gtv.bundle),
                ground_truth_path=_rel(path),
            )
        )
    return versions


def _run_dir(run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid run id")
    path = (RUNS_DIR / run_id).resolve()
    runs_root = RUNS_DIR.resolve()
    if path.parent != runs_root or not path.exists():
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return path


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="manifest.json not found")
    return _read_json(path)


def _load_bundle(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "bundle.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="bundle.json not found")
    data = _read_json(path)
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="bundle.json is not a JSON object")
    return data


def _run_summary(run_dir: Path) -> ReviewRunSummary:
    manifest = _read_json(run_dir / "manifest.json")
    bundle = _read_json(run_dir / "bundle.json")
    shape = _read_json(run_dir / "bundle_shape.json")
    pdf_sha = str(manifest.get("pdf_sha256") or "")
    review = _read_review(run_dir.name)
    decision_count = len(review.decisions) if review else 0
    return ReviewRunSummary(
        run_id=str(manifest.get("run_id") or run_dir.name),
        pipeline_name=str(manifest.get("pipeline_name") or "unknown"),
        status=str(manifest.get("status") or "unknown"),
        pdf_label=Path(str(manifest.get("pdf_path") or "")).name or "unknown",
        pdf_sha256=pdf_sha or None,
        started_at=manifest.get("started_at"),
        finished_at=manifest.get("finished_at"),
        total_entries=int(shape.get("total_entries") or _bundle_entry_count(bundle)),
        resource_counts=_resource_counts(bundle),
        has_source_pdf=(run_dir / "source.pdf").exists(),
        has_bundle=(run_dir / "bundle.json").exists(),
        review_status=review.status if review else "not_started",
        reviewed_facts=decision_count,
        published_ground_truth_version=review.published_ground_truth_version if review else None,
        existing_ground_truth_versions=list_ground_truth_versions(pdf_sha, lab_root=LAB_ROOT) if pdf_sha else [],
    )


def _load_or_create_review(run_dir: Path, manifest: dict[str, Any]) -> ReviewSession:
    existing = _read_review(run_dir.name)
    if existing is not None:
        return existing
    now = _now_iso()
    return ReviewSession(
        review_id=f"review-{uuid4().hex}",
        run_id=run_dir.name,
        pdf_sha256=str(manifest.get("pdf_sha256") or ""),
        source_pdf_path=str(manifest.get("pdf_path") or run_dir / "source.pdf"),
        candidate_bundle_path=_rel(run_dir / "bundle.json"),
        reviewer="Blake",
        status="draft",
        created_at=now,
        updated_at=now,
        decisions=[],
        annotations=[],
        notes="",
    )


def _read_review(run_id: str) -> ReviewSession | None:
    path = _review_path(run_id)
    if not path.exists():
        return None
    try:
        return ReviewSession.model_validate_json(path.read_text())
    except Exception:
        return None


def _write_review(run_id: str, review: ReviewSession) -> None:
    path = _review_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2))


def _review_path(run_id: str) -> Path:
    return REVIEWS_DIR / run_id / "review.json"


def _bundle_from_review(bundle: dict[str, Any], review: ReviewSession) -> tuple[dict[str, Any], int, int]:
    decisions_by_ref = {decision.resource_ref: decision for decision in review.decisions}
    entries = bundle.get("entry") if isinstance(bundle.get("entry"), list) else []
    final_entries: list[dict[str, Any]] = []
    rejected = 0
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        resource_ref = _resource_ref(resource, entry, index)
        decision = decisions_by_ref.get(resource_ref)
        if decision and decision.status in {"rejected", "duplicate", "unsupported"}:
            rejected += 1
            continue
        next_entry = dict(entry)
        if decision and decision.status == "edited" and isinstance(decision.edited_resource, dict):
            next_entry["resource"] = decision.edited_resource
        final_entries.append(next_entry)
    final_bundle = {**bundle, "entry": final_entries}
    return final_bundle, len(final_entries), rejected


def _summarize_bundle(bundle: dict[str, Any]) -> list[FactSummary]:
    facts: list[FactSummary] = []
    entries = bundle.get("entry") if isinstance(bundle.get("entry"), list) else []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        facts.append(
            FactSummary(
                resource_ref=_resource_ref(resource, entry, index),
                resource_type=str(resource.get("resourceType") or "Unknown"),
                resource_id=resource.get("id") if isinstance(resource.get("id"), str) else None,
                display=render_resource_summary(resource),
                codes=_codes(resource),
                value=_value(resource),
                date=_date(resource),
                status=_status(resource),
                patient_ref=_reference(resource, ("subject", "patient", "beneficiary")),
                encounter_ref=_reference(resource, ("encounter", "context")),
                source_locator=_source_locator(resource),
                original_resource=resource,
            )
        )
    return facts


def _resource_ref(resource: dict[str, Any], entry: dict[str, Any], index: int) -> str:
    resource_type = str(resource.get("resourceType") or "Unknown")
    resource_id = resource.get("id")
    if isinstance(resource_id, str) and resource_id:
        return f"{resource_type}/{resource_id}"
    full_url = entry.get("fullUrl")
    if isinstance(full_url, str) and full_url:
        return full_url
    return f"entry/{index}"


def _codes(resource: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for codeable in _codeable_concepts(resource):
        text = codeable.get("text")
        if isinstance(text, str) and text:
            out.append(text)
        for coding in codeable.get("coding") or []:
            if not isinstance(coding, dict):
                continue
            system = str(coding.get("system") or "").rsplit("/", 1)[-1]
            code = coding.get("code")
            display = coding.get("display")
            if code and display:
                out.append(f"{system}:{code} {display}".strip(": "))
            elif code:
                out.append(f"{system}:{code}".strip(":"))
            elif display:
                out.append(str(display))
    return list(dict.fromkeys(out))[:6]


def _codeable_concepts(resource: dict[str, Any]) -> list[dict[str, Any]]:
    concepts: list[dict[str, Any]] = []
    for key in ("code", "medicationCodeableConcept", "vaccineCode", "type"):
        value = resource.get(key)
        if isinstance(value, dict):
            concepts.append(value)
        elif isinstance(value, list):
            concepts.extend(item for item in value if isinstance(item, dict))
    return concepts


def _value(resource: dict[str, Any]) -> str | None:
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict):
        raw = quantity.get("value")
        unit = quantity.get("unit") or quantity.get("code")
        return " ".join(str(part) for part in (raw, unit) if part not in (None, ""))
    for key in ("valueString", "valueCodeableConcept", "valueBoolean", "valueInteger"):
        value = resource.get(key)
        if isinstance(value, dict):
            return str(value.get("text") or value.get("display") or value)
        if value is not None:
            return str(value)
    return None


def _date(resource: dict[str, Any]) -> str | None:
    for key in ("effectiveDateTime", "authoredOn", "onsetDateTime", "recordedDate", "occurrenceDateTime", "date"):
        value = resource.get(key)
        if isinstance(value, str):
            return value
    period = resource.get("effectivePeriod") or resource.get("period")
    if isinstance(period, dict):
        return str(period.get("start") or period.get("end") or "") or None
    return None


def _status(resource: dict[str, Any]) -> str | None:
    status = resource.get("status") or resource.get("clinicalStatus")
    if isinstance(status, str):
        return status
    if isinstance(status, dict):
        return status.get("text") or _codes({"code": status})[0] if _codes({"code": status}) else None
    return None


def _reference(resource: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = resource.get(key)
        if isinstance(value, dict) and isinstance(value.get("reference"), str):
            return value["reference"]
    return None


def _source_locator(resource: dict[str, Any]) -> str | None:
    meta = resource.get("meta")
    if isinstance(meta, dict):
        source = meta.get("source")
        if isinstance(source, str):
            return source
    extension = resource.get("extension")
    if isinstance(extension, list):
        for item in extension:
            if isinstance(item, dict) and "source" in str(item.get("url", "")).lower():
                for key in ("valueString", "valueUri", "valueUrl"):
                    value = item.get(key)
                    if isinstance(value, str):
                        return value
    return None


def _progress(review: ReviewSession, total_facts: int) -> ReviewProgress:
    counts = Counter(decision.status for decision in review.decisions)
    reviewed = sum(
        count
        for status, count in counts.items()
        if status not in {"missing"}
    )
    return ReviewProgress(
        total_facts=total_facts,
        reviewed_facts=reviewed,
        accepted_facts=counts["accepted"],
        rejected_facts=counts["rejected"] + counts["duplicate"] + counts["unsupported"],
        edited_facts=counts["edited"],
        uncertain_facts=counts["uncertain"] + counts["needs_follow_up"],
        missing_facts=counts["missing"],
        needs_review=max(total_facts - reviewed, 0),
    )


def _pdf_page_sizes(pdf_path: Path) -> list[tuple[float, float]]:
    import pypdfium2 as pdfium

    with _PDF_RENDER_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            sizes: list[tuple[float, float]] = []
            for page_index in range(len(doc)):
                page = doc[page_index]
                try:
                    width, height = page.get_size()
                    sizes.append((float(width), float(height)))
                finally:
                    page.close()
            return sizes
        finally:
            doc.close()


def _render_pdf_page(pdf_path: Path, page_number: int) -> bytes:
    import pypdfium2 as pdfium

    with _PDF_RENDER_LOCK:
        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            page_index = page_number - 1
            if page_index >= len(doc):
                raise IndexError(page_number)
            page = doc[page_index]
            try:
                image = page.render(scale=PDF_RENDER_SCALE).to_pil()
                out = io.BytesIO()
                image.save(out, format="PNG")
                return out.getvalue()
            finally:
                page.close()
        finally:
            doc.close()


def _pdf_page_cache_path(run_id: str, page_number: int) -> Path:
    return REVIEWS_DIR / run_id / "pdf-pages" / f"page-{page_number:03d}-scale-{PDF_RENDER_SCALE:g}.png"


def _locator_input(fact: FactSummary) -> FactLocatorInput:
    return FactLocatorInput(
        resource_ref=fact.resource_ref,
        resource_type=fact.resource_type,
        display=fact.display,
        codes=fact.codes,
        value=fact.value,
        date=fact.date,
        status=fact.status,
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _bundle_entry_count(bundle: Any) -> int:
    if not isinstance(bundle, dict):
        return 0
    entries = bundle.get("entry")
    return len(entries) if isinstance(entries, list) else 0


def _resource_counts(bundle: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not isinstance(bundle, dict):
        return counts
    entries = bundle.get("entry")
    if not isinstance(entries, list):
        return counts
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        resource_type = str(resource.get("resourceType") or "Unknown")
        counts[resource_type] = counts.get(resource_type, 0) + 1
    return counts


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
