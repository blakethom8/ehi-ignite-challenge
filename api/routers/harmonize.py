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
    HarmonizeCollection,
    HarmonizeCollectionsResponse,
    HarmonizeConditionsResponse,
    HarmonizeMergedCondition,
    HarmonizeMergedObservation,
    HarmonizeObservationsResponse,
    HarmonizeProvenanceResponse,
    HarmonizeSource,
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
