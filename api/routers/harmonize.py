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

from fastapi import APIRouter, HTTPException

from api.core import harmonize_service
from api.models import (
    HarmonizeAllergiesResponse,
    HarmonizeCollection,
    HarmonizeCollectionsResponse,
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
    HarmonizeSource,
    HarmonizeSourceDiffResponse,
    HarmonizeSourceDiffSource,
    HarmonizeSourceDiffSourceTotals,
    HarmonizeSourceDiffUniqueFacts,
    HarmonizeSourceManifestResponse,
)


router = APIRouter(prefix="/harmonize", tags=["harmonize"])


@router.get("/collections", response_model=HarmonizeCollectionsResponse)
def get_collections() -> HarmonizeCollectionsResponse:
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


@router.get("/{collection_id}/sources", response_model=HarmonizeSourceManifestResponse)
def get_sources(collection_id: str) -> HarmonizeSourceManifestResponse:
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
def get_observations(
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeObservationsResponse:
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
def get_conditions(
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeConditionsResponse:
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
def get_medications(
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeMedicationsResponse:
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
def get_allergies(
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeAllergiesResponse:
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
def get_immunizations(
    collection_id: str,
    cross_source_only: bool = False,
) -> HarmonizeImmunizationsResponse:
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
def extract_collection(collection_id: str) -> HarmonizeExtractJobResponse:
    """Enqueue an extraction job over every uploaded PDF in this collection
    that lacks a cached extraction.

    Returns immediately with HTTP 202 + a job_id. PDFs typically take 30-90s
    each; the React page should poll
    ``GET /api/harmonize/extract-jobs/{job_id}`` for completion. Static demo
    collections are read-only and return 400.
    """
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
def get_extract_job(job_id: str) -> HarmonizeExtractJobResponse:
    """Poll a previously-enqueued extraction job. 404s for unknown jobs."""
    job = harmonize_service.get_extract_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Extract job not found: {job_id}")
    return _job_to_response(job)


def _job_to_response(job: harmonize_service.ExtractJob) -> HarmonizeExtractJobResponse:
    return HarmonizeExtractJobResponse(
        job_id=job.job_id,
        collection_id=job.collection_id,
        status=job.status,  # type: ignore[arg-type]
        results=[HarmonizeExtractItem(**vars(r)) for r in job.results],
        error=job.error,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{collection_id}/source-diff",
    response_model=HarmonizeSourceDiffResponse,
)
def get_source_diff(collection_id: str) -> HarmonizeSourceDiffResponse:
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


@router.get(
    "/{collection_id}/contributions/{document_reference:path}",
    response_model=HarmonizeContributionsResponse,
)
def get_contributions(
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
        totals=HarmonizeContributionTotals(**payload["totals"]),
    )


@router.get(
    "/{collection_id}/provenance/{merged_ref:path}",
    response_model=HarmonizeProvenanceResponse,
)
def get_provenance(collection_id: str, merged_ref: str) -> HarmonizeProvenanceResponse:
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
    )
