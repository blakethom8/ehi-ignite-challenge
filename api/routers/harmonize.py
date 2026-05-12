"""/api/harmonize — cross-source merge with FHIR Provenance.

Surfaces the harmonization layer (`lib.harmonize`) as JSON endpoints
the React app can consume. The endpoints are *collection-scoped* —
a collection is a named bag of source documents being harmonized
together. The current registry holds one demo collection
(``blake-real``); future collections will be created when the upload
flow materializes new source bundles.

Endpoint surface:

- ``GET /api/harmonize/collections`` — list registered collections.
- ``GET /api/harmonize/{collection_id}/sources`` — manifest of the
  source documents that feed this collection.
- ``GET /api/harmonize/{collection_id}/observations`` — merged
  Observations with longitudinal source detail.
- ``GET /api/harmonize/{collection_id}/conditions`` — merged
  Conditions with coding + clinical-status detail.
- ``GET /api/harmonize/{collection_id}/provenance/{merged_ref}`` —
  FHIR Provenance resource for one merged record, walking back to all
  source observations / conditions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from api.core import harmonization_runs, harmonize_service, published_charts
from api.core.auth import require_authenticated_session
from scripts.export_workspace_package import build_package
from api.models import (
    HarmonizeAllergiesResponse,
    HarmonizeCollection,
    HarmonizeCollectionsResponse,
    HarmonizeClinicalNote,
    HarmonizeClinicalArtifact,
    HarmonizeConditionsResponse,
    HarmonizeContributionsResponse,
    HarmonizeContributionTotals,
    HarmonizeExtractItem,
    HarmonizeExtractJobResponse,
    HarmonizeExtractResponse,
    HarmonizeImmunizationsResponse,
    HarmonizeMedicationsResponse,
    HarmonizeMergedAllergy,
    HarmonizeMergedCondition,
    HarmonizeMergedImmunization,
    HarmonizeMergedMedication,
    HarmonizeMergedObservation,
    HarmonizeObservationsResponse,
    HarmonizeProvenanceResponse,
    HarmonizeReviewDecisionRequest,
    HarmonizeRunResponse,
    HarmonizeRunStateResponse,
    HarmonizeSource,
    HarmonizeSourceDiffResponse,
    HarmonizeSourceDiffSource,
    HarmonizeSourceDiffSourceTotals,
    HarmonizeSourceDiffUniqueFacts,
    HarmonizeSourceManifestResponse,
    PublishedChartStateResponse,
)


router = APIRouter(prefix="/harmonize", tags=["harmonize"])


@router.get("/collections", response_model=HarmonizeCollectionsResponse)
def get_collections(request: Request) -> HarmonizeCollectionsResponse:
    require_authenticated_session(request)
    return HarmonizeCollectionsResponse(
        collections=[
            HarmonizeCollection(
                id=c.id,
                name=c.name,
                description=c.description,
                source_count=len(c.sources),
            )
            for c in harmonize_service.list_collections()
        ]
    )


@router.get("/workspaces/{patient_id}", response_model=HarmonizeCollection)
def get_patient_workspace(request: Request, patient_id: str) -> HarmonizeCollection:
    require_authenticated_session(request)
    collection = harmonize_service.patient_workspace_collection(patient_id)
    if collection is None:
        raise HTTPException(status_code=404, detail=f"Patient workspace not found: {patient_id}")
    return HarmonizeCollection(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        source_count=len(collection.sources),
    )


@router.get("/{collection_id}/sources", response_model=HarmonizeSourceManifestResponse)
def get_sources(request: Request, collection_id: str) -> HarmonizeSourceManifestResponse:
    require_authenticated_session(request)
    manifest = harmonize_service.collection_source_manifest(collection_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    return HarmonizeSourceManifestResponse(
        collection_id=collection_id,
        sources=[HarmonizeSource(**s) for s in manifest],
    )


@router.get(
    "/{collection_id}/observations",
    response_model=HarmonizeObservationsResponse,
)
def get_observations(request: Request,
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeObservationsResponse:
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    merged = harmonize_service.merged_observations(collection_id)
    cross = [m for m in merged if len({s.source_label for s in m.sources}) > 1]
    visible = cross if cross_source_only else merged
    return HarmonizeObservationsResponse(
        collection_id=collection_id,
        total=len(merged),
        cross_source=len(cross),
        merged=[
            HarmonizeMergedObservation(**harmonize_service.serialize_observation(m))
            for m in visible
        ],
    )


@router.get(
    "/{collection_id}/conditions",
    response_model=HarmonizeConditionsResponse,
)
def get_conditions(request: Request,
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeConditionsResponse:
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    merged = harmonize_service.merged_conditions(collection_id)
    cross = [m for m in merged if len({s.source_label for s in m.sources}) > 1]
    visible = cross if cross_source_only else merged
    return HarmonizeConditionsResponse(
        collection_id=collection_id,
        total=len(merged),
        cross_source=len(cross),
        merged=[
            HarmonizeMergedCondition(**harmonize_service.serialize_condition(m))
            for m in visible
        ],
    )


@router.get(
    "/{collection_id}/medications",
    response_model=HarmonizeMedicationsResponse,
)
def get_medications(request: Request,
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeMedicationsResponse:
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    merged = harmonize_service.merged_medications(collection_id)
    cross = [m for m in merged if len({s.source_label for s in m.sources}) > 1]
    visible = cross if cross_source_only else merged
    return HarmonizeMedicationsResponse(
        collection_id=collection_id,
        total=len(merged),
        cross_source=len(cross),
        merged=[
            HarmonizeMergedMedication(**harmonize_service.serialize_medication(m))
            for m in visible
        ],
    )


@router.get(
    "/{collection_id}/allergies",
    response_model=HarmonizeAllergiesResponse,
)
def get_allergies(request: Request,
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeAllergiesResponse:
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    merged = harmonize_service.merged_allergies(collection_id)
    cross = [m for m in merged if len({s.source_label for s in m.sources}) > 1]
    visible = cross if cross_source_only else merged
    return HarmonizeAllergiesResponse(
        collection_id=collection_id,
        total=len(merged),
        cross_source=len(cross),
        merged=[
            HarmonizeMergedAllergy(**harmonize_service.serialize_allergy(m))
            for m in visible
        ],
    )


@router.get(
    "/{collection_id}/immunizations",
    response_model=HarmonizeImmunizationsResponse,
)
def get_immunizations(request: Request,
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeImmunizationsResponse:
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    merged = harmonize_service.merged_immunizations(collection_id)
    cross = [m for m in merged if len({s.source_label for s in m.sources}) > 1]
    visible = cross if cross_source_only else merged
    return HarmonizeImmunizationsResponse(
        collection_id=collection_id,
        total=len(merged),
        cross_source=len(cross),
        merged=[
            HarmonizeMergedImmunization(**harmonize_service.serialize_immunization(m))
            for m in visible
        ],
    )


@router.post(
    "/{collection_id}/extract",
    response_model=HarmonizeExtractJobResponse,
    status_code=202,
)
def extract_collection(request: Request, collection_id: str) -> HarmonizeExtractJobResponse:
    """Enqueue an extraction job over every uploaded PDF in this collection
    that lacks a cached extraction.

    Returns immediately with HTTP 202 + a job_id. PDFs typically take 30-90s
    each; the React page should poll
    ``GET /api/harmonize/extract-jobs/{job_id}`` for completion. Static demo
    collections are read-only and return 400.
    """
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    job = harmonize_service.start_extract_job(collection_id)
    if job is None:
        raise HTTPException(
            status_code=400,
            detail=f"Collection {collection_id} doesn't support extraction (static demo).",
        )
    return _job_to_response(job)


@router.get(
    "/extract-jobs/{job_id}",
    response_model=HarmonizeExtractJobResponse,
)
def get_extract_job(request: Request, job_id: str) -> HarmonizeExtractJobResponse:
    """Poll a previously-enqueued extraction job. 404s for unknown jobs."""
    require_authenticated_session(request)
    job = harmonize_service.get_extract_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Extract job not found: {job_id}")
    return _job_to_response(job)


@router.get(
    "/{collection_id}/extract-job",
    response_model=HarmonizeExtractJobResponse,
)
def get_latest_extract_job(request: Request, collection_id: str) -> HarmonizeExtractJobResponse:
    """Return the most recent extraction job for a collection.

    This lets the UI recover in-flight progress after navigation or reloads.
    """
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    job = harmonize_service.get_latest_extract_job(collection_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No extract job found for: {collection_id}")
    return _job_to_response(job)


@router.post(
    "/{collection_id}/runs",
    response_model=HarmonizeRunResponse,
    status_code=201,
)
def run_harmonization(request: Request, collection_id: str) -> HarmonizeRunResponse:
    """Create a durable scripted harmonization run for this collection."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    try:
        payload = harmonization_runs.run_harmonization(collection_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}") from None
    return HarmonizeRunResponse(**payload)


@router.get(
    "/{collection_id}/runs/latest",
    response_model=HarmonizeRunStateResponse,
)
def get_latest_harmonization_run(request: Request, collection_id: str) -> HarmonizeRunStateResponse:
    """Return the latest persisted harmonization run, if one exists."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    latest = harmonization_runs.latest_run(collection_id)
    return HarmonizeRunStateResponse(
        collection_id=collection_id,
        latest_run=HarmonizeRunResponse(**latest) if latest else None,
    )


@router.get(
    "/{collection_id}/runs/{run_id}",
    response_model=HarmonizeRunResponse,
)
def get_harmonization_run(request: Request, collection_id: str, run_id: str) -> HarmonizeRunResponse:
    """Fetch one persisted harmonization run artifact by id."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    payload = harmonization_runs.get_run(collection_id, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Harmonization run not found: {run_id}")
    return HarmonizeRunResponse(**payload)


@router.post(
    "/{collection_id}/runs/{run_id}/review-items/resolve",
    response_model=HarmonizeRunResponse,
)
def resolve_harmonization_review_item(request: Request,
    collection_id: str,
    run_id: str,
    decision: HarmonizeReviewDecisionRequest,
) -> HarmonizeRunResponse:
    """Record a reviewer decision for one persisted harmonization run item."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    try:
        payload = harmonization_runs.resolve_review_item(
            collection_id=collection_id,
            run_id=run_id,
            item_id=decision.item_id,
            decision=decision.decision,
            notes=decision.notes,
            selected_source_ref=decision.selected_source_ref,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Harmonization run not found: {run_id}") from None
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Review item not found: {decision.item_id}") from None
    return HarmonizeRunResponse(**payload)


@router.get(
    "/{collection_id}/published",
    response_model=PublishedChartStateResponse,
)
def get_published_chart(request: Request, collection_id: str) -> PublishedChartStateResponse:
    """Return published chart snapshots for this harmonize collection."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    return PublishedChartStateResponse(**published_charts.state(collection_id))


@router.post(
    "/{collection_id}/runs/{run_id}/publish",
    response_model=PublishedChartStateResponse,
    status_code=201,
)
def publish_harmonization_run(request: Request, collection_id: str, run_id: str) -> PublishedChartStateResponse:
    """Pin a completed harmonization run as the active downstream chart."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    try:
        response = PublishedChartStateResponse(**published_charts.publish_run(collection_id, run_id))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Harmonization run not found: {run_id}") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # T6 (LLM-CONTEXT-AUGMENTATION-PLAN §T6): regenerate per-episode
    # narratives so the freshly published snapshot has up-to-date
    # Compositions. Synchronous in Phase 1 (small patient counts);
    # async-with-jobs is Phase 2 (§P8). Per-episode failures are
    # tolerated so one bad narrative doesn't block the publish.
    patient_id = harmonize_service._patient_id_from_workspace_collection(collection_id)
    if patient_id:
        try:
            from api.core.narrative_service import regenerate_all_episodes

            regenerate_all_episodes(patient_id, collection_id=collection_id)
        except Exception as exc:  # noqa: BLE001 — never block publish
            import logging

            logging.getLogger(__name__).warning(
                "narrative regen after publish failed for %s: %s", patient_id, exc
            )

    return response


@router.post(
    "/{collection_id}/published/{snapshot_id}/activate",
    response_model=PublishedChartStateResponse,
)
def activate_published_snapshot(request: Request, collection_id: str, snapshot_id: str) -> PublishedChartStateResponse:
    """Switch downstream modules back to a prior published snapshot."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    try:
        return PublishedChartStateResponse(**published_charts.activate_snapshot(collection_id, snapshot_id))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Published snapshot not found: {snapshot_id}") from None


@router.delete(
    "/{collection_id}/published/active",
    response_model=PublishedChartStateResponse,
)
def unpublish_active_snapshot(request: Request, collection_id: str) -> PublishedChartStateResponse:
    """Remove active downstream access while keeping snapshot history."""
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    return PublishedChartStateResponse(**published_charts.unpublish(collection_id))


def _job_progress(job: harmonize_service.ExtractJob) -> int:
    if job.status == "complete":
        return 100
    if job.status == "failed":
        return min(95, max(5, _job_progress_from_work(job)))
    if job.status == "pending":
        return 5
    return min(95, max(10, _job_progress_from_work(job)))


def _job_progress_from_work(job: harmonize_service.ExtractJob) -> int:
    progress_candidates: list[float] = []
    if job.total_files:
        progress_candidates.append((job.processed_files / job.total_files) * 100)
    if job.total_pages:
        progress_candidates.append((job.processed_pages / job.total_pages) * 100)
    if job.estimated_seconds:
        ended_at = job.completed_at or datetime.now()
        elapsed_seconds = max(0.0, (ended_at - job.started_at).total_seconds())
        progress_candidates.append(min(90.0, (elapsed_seconds / job.estimated_seconds) * 90.0))
    if not progress_candidates:
        return 15 if job.status == "running" else 0
    return round(max(progress_candidates))


def _job_estimated_processed_pages(job: harmonize_service.ExtractJob) -> int:
    """Best-effort page position for UI orientation, not a true parser event.

    The current PDF extraction pipeline runs as one blocking multipass call.
    Until that worker can emit page-level checkpoints, this estimate lets the
    frontend show a gentle "current page" orientation without claiming pages
    have actually completed.
    """
    if not job.total_pages:
        return 0
    if job.status == "complete":
        return job.total_pages
    if job.processed_pages > 0:
        return min(job.processed_pages, job.total_pages)
    if job.status not in {"pending", "running"} or not job.estimated_seconds:
        return 0
    elapsed_seconds = max(0.0, (datetime.now() - job.started_at).total_seconds())
    estimated_pages = int((elapsed_seconds / job.estimated_seconds) * job.total_pages)
    return min(max(0, estimated_pages), max(job.total_pages - 1, 0))


def _job_progress_mode(job: harmonize_service.ExtractJob) -> str:
    if job.processed_pages > 0 or any(event.progress_basis == "reported" for event in job.events):
        return "reported"
    if job.status in {"pending", "running"} and job.estimated_seconds:
        return "estimated"
    return "lifecycle"


def _job_detail(job: harmonize_service.ExtractJob) -> str:
    source = f" Current file: {job.current_source_label}." if job.current_source_label else ""
    if _job_progress_mode(job) == "reported":
        return f"Runs on the server, so you can leave this page and come back later. Reported checkpoints are shown in the event timeline.{source}"
    return f"Runs on the server, so you can leave this page and come back later. Page position remains estimated until the worker reports a checkpoint.{source}"


def _job_to_response(job: harmonize_service.ExtractJob) -> HarmonizeExtractJobResponse:
    return HarmonizeExtractJobResponse(
        job_id=job.job_id,
        collection_id=job.collection_id,
        status=job.status,  # type: ignore[arg-type]
        results=[HarmonizeExtractItem(**vars(r)) for r in job.results],
        error=job.error,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress_percent=_job_progress(job),
        stage=job.stage,
        detail=_job_detail(job),
        total_files=job.total_files,
        processed_files=job.processed_files,
        total_pages=job.total_pages,
        processed_pages=job.processed_pages,
        estimated_processed_pages=_job_estimated_processed_pages(job),
        current_source_label=job.current_source_label,
        estimated_seconds=job.estimated_seconds,
        progress_mode=_job_progress_mode(job),  # type: ignore[arg-type]
        events=[vars(event) for event in job.events],
    )


@router.get(
    "/{collection_id}/source-diff",
    response_model=HarmonizeSourceDiffResponse,
)
def get_source_diff(request: Request, collection_id: str) -> HarmonizeSourceDiffResponse:
    """Per-source unique vs shared contribution counts + the unique-fact lists.

    For each source bundle in the collection: the merged records that are
    *only* contributed-to by this source ("unique") vs those shared with
    at least one other source ("shared").

    Unique facts are the high-signal "if I removed this source, here's
    what I'd lose" set. On Cedars FHIR + extracted-PDF pairs, the PDF's
    unique set tends to be the *vision wins* (clinical findings the
    structured FHIR pull never coded — see PIPELINE-LOG Move H), and
    the FHIR's unique set tends to be older / non-summary records.
    """
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    payload = harmonize_service.source_contribution_diff(collection_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    return HarmonizeSourceDiffResponse(
        collection_id=payload["collection_id"],
        sources=[
            HarmonizeSourceDiffSource(
                id=s["id"],
                label=s["label"],
                kind=s["kind"],
                document_reference=s["document_reference"],
                totals=HarmonizeSourceDiffSourceTotals(
                    unique=HarmonizeContributionTotals(**s["totals"]["unique"]),
                    shared=HarmonizeContributionTotals(**s["totals"]["shared"]),
                ),
                unique_facts=HarmonizeSourceDiffUniqueFacts(
                    observations=[
                        HarmonizeMergedObservation(**m)
                        for m in s["unique_facts"]["observations"]
                    ],
                    conditions=[
                        HarmonizeMergedCondition(**m)
                        for m in s["unique_facts"]["conditions"]
                    ],
                    medications=[
                        HarmonizeMergedMedication(**m)
                        for m in s["unique_facts"]["medications"]
                    ],
                    allergies=[
                        HarmonizeMergedAllergy(**m)
                        for m in s["unique_facts"]["allergies"]
                    ],
                    immunizations=[
                        HarmonizeMergedImmunization(**m)
                        for m in s["unique_facts"]["immunizations"]
                    ],
                ),
            )
            for s in payload["sources"]
        ],
    )


@router.get("/{collection_id}/export-workspace")
def export_workspace_package(request: Request,
    collection_id: str,
    include_originals: bool = False,
) -> FileResponse:
    """Download a portable patient-owned EHI Atlas workspace package.

    The zip contains source inventory, canonical facts, provenance, source
    contributions, missing-information signals, agent instructions, context
    packets, markdown/CSV exports, and a tiny package-inspection CLI.
    """
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    out_dir = Path("data/workspace-packages")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{collection_id}.zip"
    try:
        build_package(
            collection_id,
            out,
            include_originals=include_originals,
        )
    except SystemExit as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=out,
        media_type="application/zip",
        filename=out.name,
    )


@router.get(
    "/{collection_id}/contributions/{document_reference:path}",
    response_model=HarmonizeContributionsResponse,
)
def get_contributions(request: Request,
    collection_id: str,
    document_reference: str,
) -> HarmonizeContributionsResponse:
    """Reverse Provenance walk — list every merged fact whose sources
    include the given DocumentReference.

    Answers "what did this source document actually contribute?" — the
    other direction of the Provenance graph from the per-fact lineage
    panel. Useful when a clinician wants to understand the relative
    information density of one source vs another, or audit which facts
    came from a specific PDF before removing it.
    """
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    payload = harmonize_service.facts_for_document_reference(
        collection_id, document_reference
    )
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Collection not found: {collection_id}",
        )
    return HarmonizeContributionsResponse(
        collection_id=collection_id,
        document_reference=payload["document_reference"],
        label=payload["label"],
        kind=payload["kind"],
        observations=[HarmonizeMergedObservation(**m) for m in payload["observations"]],
        conditions=[HarmonizeMergedCondition(**m) for m in payload["conditions"]],
        medications=[HarmonizeMergedMedication(**m) for m in payload["medications"]],
        allergies=[HarmonizeMergedAllergy(**m) for m in payload["allergies"]],
        immunizations=[HarmonizeMergedImmunization(**m) for m in payload["immunizations"]],
        encounters=[HarmonizeClinicalArtifact(**m) for m in payload.get("encounters", [])],
        procedures=[HarmonizeClinicalArtifact(**m) for m in payload.get("procedures", [])],
        diagnostic_reports=[
            HarmonizeClinicalArtifact(**m)
            for m in payload.get("diagnostic_reports", [])
        ],
        clinical_notes=[HarmonizeClinicalNote(**m) for m in payload.get("clinical_notes", [])],
        totals=HarmonizeContributionTotals(**payload["totals"]),
    )


@router.get(
    "/{collection_id}/provenance/{merged_ref:path}",
    response_model=HarmonizeProvenanceResponse,
)
def get_provenance(request: Request, collection_id: str, merged_ref: str) -> HarmonizeProvenanceResponse:
    require_authenticated_session(request)
    if harmonize_service.get_collection(collection_id) is None:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")
    prov = harmonize_service.provenance_for_ref(collection_id, merged_ref)
    if prov is None:
        raise HTTPException(
            status_code=404,
            detail=f"Merged record not found: {merged_ref}",
        )
    return HarmonizeProvenanceResponse(
        collection_id=collection_id,
        merged_ref=merged_ref,
        provenance=prov,
        canonical_selection=harmonization_runs.latest_canonical_selection(
            collection_id,
            merged_ref,
        ),
    )
