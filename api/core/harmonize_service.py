"""Harmonization service — wraps `lib.harmonize` for the API layer.

The service knows how to load source bundles for a *collection* (a named
group of source documents the user is harmonizing together) and run the
matchers, returning shaped response objects the router can hand to the
React app.

Collections are deliberately decoupled from "patient" — a collection is
"these documents the user uploaded / pulled," and harmonization runs over
that bag. The current registry includes one well-known demo collection
(``blake-real``) backed by the corpus drop in
``ehi-atlas/corpus/bronze/clinical-portfolios/blake_records/``; future
collections will be registered the same way once the upload-flow side
materializes them under ``data/aggregation-uploads/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from lib.harmonize import (
    SourceBundle,
    merge_conditions,
    merge_observations,
    mint_provenance,
)
from lib.harmonize.models import MergedCondition, MergedObservation


REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Collection registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CollectionDefinition:
    """One harmonizable collection of source documents.

    A collection is the user-visible unit: "these documents I'm
    harmonizing together." The harmonize layer doesn't care whether a
    collection is one patient's record or a research cohort or an
    arbitrary upload session — it just merges whatever it's given.
    """

    id: str
    """Stable collection identifier used in URLs."""

    name: str
    """Human-readable name shown in the UI."""

    description: str
    """One-line description of what's in the collection."""

    sources: tuple["SourceDefinition", ...]
    """Concrete source documents that feed the harmonizer."""


@dataclass(frozen=True)
class SourceDefinition:
    """One source document inside a collection.

    The ``kind`` field drives loading: native FHIR pulls return the FHIR
    dict directly, while extracted PDFs return a Bundle that we flatten
    by resourceType.
    """

    id: str
    label: str
    kind: str  # "fhir-pull" | "extracted-pdf"
    path: Path
    document_reference: str | None = None


_BLAKE_DIR = (
    REPO_ROOT
    / "ehi-atlas"
    / "corpus"
    / "bronze"
    / "clinical-portfolios"
    / "blake_records"
)


_COLLECTIONS: dict[str, CollectionDefinition] = {
    "blake-real": CollectionDefinition(
        id="blake-real",
        name="Blake Thomson — real EHI exports",
        description=(
            "Cross-source aggregation of Blake's actual records: the Cedars-Sinai "
            "Health-Skillz FHIR pull, the Cedars-Sinai HealthSummary PDF, and three "
            "Function Health Quest lab PDFs."
        ),
        sources=(
            SourceDefinition(
                id="cedars-fhir",
                label="Cedars-Sinai (FHIR)",
                kind="fhir-pull",
                path=_BLAKE_DIR / "cedars-healthskillz-download" / "health-records.json",
                document_reference="DocumentReference/cedars-healthskillz-2025-11-07",
            ),
            SourceDefinition(
                id="cedars-pdf",
                label="Cedars-Sinai (PDF)",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "HealthSummary_May_03_2026"
                / "extracted-cedars-healthsummary.json",
                document_reference="DocumentReference/cedars-health-summary-pdf",
            ),
            SourceDefinition(
                id="function-health-2024-07-26",
                label="Function Health · 2024-07-26",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "blake_function_pdfs"
                / "extracted-2024-07-26.json",
                document_reference="DocumentReference/function-health-2024-07-26",
            ),
            SourceDefinition(
                id="function-health-2024-07-29",
                label="Function Health · 2024-07-29",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "blake_function_pdfs"
                / "extracted-2024-07-29.json",
                document_reference="DocumentReference/function-health-2024-07-29",
            ),
            SourceDefinition(
                id="function-health-2025-11-29",
                label="Function Health · 2025-11-29",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "blake_function_pdfs"
                / "extracted-2025-11-29.json",
                document_reference="DocumentReference/function-health-2025-11-29",
            ),
        ),
    ),
}


def list_collections() -> list[CollectionDefinition]:
    return list(_COLLECTIONS.values())


def get_collection(collection_id: str) -> CollectionDefinition | None:
    return _COLLECTIONS.get(collection_id)


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------


def _load_resources_by_type(source: SourceDefinition) -> dict[str, list[dict]]:
    """Return ``{resourceType: [resource, ...]}`` for one source."""
    if not source.path.exists():
        return {}
    raw = json.loads(source.path.read_text())
    out: dict[str, list[dict]] = {}
    if source.kind == "fhir-pull":
        # Health-Skillz envelope: list[{provider, fhir: {ResourceType: [...]}}]
        if isinstance(raw, list) and raw and isinstance(raw[0].get("fhir"), dict):
            for rtype, resources in raw[0]["fhir"].items():
                if isinstance(resources, list):
                    out[rtype] = list(resources)
            return out
        # Plain FHIR Bundle fallback
        for entry in raw.get("entry", []):
            r = entry.get("resource", {})
            rt = r.get("resourceType")
            if rt:
                out.setdefault(rt, []).append(r)
        return out
    # extracted-pdf — multipass-fhir always emits a Bundle
    for entry in raw.get("entry", []):
        r = entry.get("resource", {})
        rt = r.get("resourceType")
        if rt:
            out.setdefault(rt, []).append(r)
    return out


# Cache by mtime tuple so re-extracting any source PDF naturally invalidates.
def _mtime_key(collection: CollectionDefinition) -> tuple:
    return tuple(
        (s.id, s.path.stat().st_mtime if s.path.exists() else 0.0) for s in collection.sources
    )


@lru_cache(maxsize=8)
def _cached_load(collection_id: str, mtime_signature: tuple) -> dict[str, dict[str, list[dict]]]:
    """Loads every source for a collection, returning ``{source_id: {rtype: [resource]}}``."""
    coll = get_collection(collection_id)
    if not coll:
        return {}
    return {s.id: _load_resources_by_type(s) for s in coll.sources}


def load_collection_resources(collection_id: str) -> dict[str, dict[str, list[dict]]]:
    coll = get_collection(collection_id)
    if not coll:
        return {}
    return _cached_load(collection_id, _mtime_key(coll))


# ---------------------------------------------------------------------------
# Source manifest
# ---------------------------------------------------------------------------


def collection_source_manifest(collection_id: str) -> list[dict[str, Any]] | None:
    coll = get_collection(collection_id)
    if not coll:
        return None
    resources = load_collection_resources(collection_id)
    out = []
    for s in coll.sources:
        rs = resources.get(s.id, {})
        out.append(
            {
                "id": s.id,
                "label": s.label,
                "kind": s.kind,
                "available": s.path.exists(),
                "document_reference": s.document_reference,
                "resource_counts": {rt: len(v) for rt, v in rs.items()},
                "total_resources": sum(len(v) for v in rs.values()),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Merge orchestration
# ---------------------------------------------------------------------------


def _bundles_for(collection_id: str, resource_type: str) -> list[SourceBundle]:
    coll = get_collection(collection_id)
    if not coll:
        return []
    resources = load_collection_resources(collection_id)
    bundles = []
    for s in coll.sources:
        items = resources.get(s.id, {}).get(resource_type, [])
        if items:
            bundles.append(
                SourceBundle(
                    label=s.label,
                    observations=items,
                    document_reference=s.document_reference,
                )
            )
    return bundles


def merged_observations(collection_id: str) -> list[MergedObservation]:
    return merge_observations(_bundles_for(collection_id, "Observation"))


def merged_conditions(collection_id: str) -> list[MergedCondition]:
    return merge_conditions(_bundles_for(collection_id, "Condition"))


# ---------------------------------------------------------------------------
# Serialization helpers (lib.harmonize.models → JSON-friendly dicts)
# ---------------------------------------------------------------------------


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def serialize_observation(m: MergedObservation) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "loinc_code": m.loinc_code,
        "canonical_unit": m.canonical_unit,
        "source_count": len({s.source_label for s in m.sources}),
        "measurement_count": len(m.sources),
        "has_conflict": m.has_conflict,
        "latest": (
            {
                "value": m.latest.value,
                "unit": m.latest.unit,
                "source_label": m.latest.source_label,
                "effective_date": _iso(m.latest.effective_date),
            }
            if m.latest
            else None
        ),
        "sources": [
            {
                "source_label": s.source_label,
                "source_observation_ref": s.source_observation_ref,
                "value": s.value,
                "unit": s.unit,
                "raw_value": s.raw_value,
                "raw_unit": s.raw_unit,
                "effective_date": _iso(s.effective_date),
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def serialize_condition(m: MergedCondition) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "snomed": m.snomed,
        "icd10": m.icd10,
        "icd9": m.icd9,
        "is_active": m.is_active,
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_condition_ref": s.source_condition_ref,
                "display": s.display,
                "snomed": s.snomed,
                "icd10": s.icd10,
                "icd9": s.icd9,
                "clinical_status": s.clinical_status,
                "onset_date": _iso(s.onset_date),
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def find_merged_record(collection_id: str, merged_ref: str):
    """Look up a merged record by its synthetic ref ID across both resource types."""
    if "merged-loinc" in merged_ref or merged_ref.startswith("Observation/merged-"):
        for m in merged_observations(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if "merged-snomed" in merged_ref or "merged-icd" in merged_ref or merged_ref.startswith("Condition/merged-"):
        for m in merged_conditions(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    return None


def provenance_for_ref(collection_id: str, merged_ref: str) -> dict[str, Any] | None:
    record = find_merged_record(collection_id, merged_ref)
    if record is None:
        return None
    return mint_provenance(record)
