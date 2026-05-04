"""Harmonization service — wraps `lib.harmonize` for the API layer.

The service knows how to load source bundles for a *collection* (a named
group of source documents the user is harmonizing together) and run the
matchers, returning shaped response objects the router can hand to the
React app.

Collections are deliberately decoupled from "patient" — a collection is
"these documents the user uploaded / pulled," and harmonization runs over
that bag. The registry has two halves:

1. **Static registry** — one well-known demo collection (``blake-real``)
   backed by the corpus drop in
   ``ehi-atlas/corpus/bronze/clinical-portfolios/blake_records/``.
2. **Upload-derived collections** — one per subdirectory under
   ``data/aggregation-uploads/<upload_session>/``. Each ``.json`` upload
   becomes a fhir-pull source; each ``.pdf`` upload becomes an
   extracted-pdf source whose extraction lives at
   ``<file>.extracted.json`` next to it (produced by the manual
   extract endpoint or pre-staged out-of-band).

This makes the application document-agnostic: any user can upload any
documents and the harmonizer surfaces a per-upload-session merged record
without code changes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from lib.harmonize import (
    SourceBundle,
    merge_allergies,
    merge_conditions,
    merge_immunizations,
    merge_medications,
    merge_observations,
    mint_provenance,
)
from lib.harmonize.models import (
    MergedAllergy,
    MergedCondition,
    MergedImmunization,
    MergedMedication,
    MergedObservation,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = Path(
    os.getenv("AGGREGATION_UPLOAD_STORE_PATH", REPO_ROOT / "data" / "aggregation-uploads")
)


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


# ---------------------------------------------------------------------------
# Upload-derived collection discovery
# ---------------------------------------------------------------------------
#
# Each subdirectory under ``data/aggregation-uploads/<upload_session>/``
# becomes one collection. A subdirectory's source list is built from the
# files inside it:
#
#   foo.pdf                 → extracted-pdf source (extraction at
#                             foo.extracted.json if cached)
#   bar.json                → fhir-pull source (if FHIR-shaped)
#
# The collection ID is ``upload-<session>``. The ``session`` segment is
# whatever the upload flow chose to key on (currently the patient_id, but
# the harmonizer doesn't care).


def _looks_like_fhir(path: Path) -> bool:
    """Cheap structural check: does this JSON look like FHIR?"""
    if path.suffix.lower() != ".json":
        return False
    try:
        with path.open() as fh:
            head = fh.read(4096)
        # Accept both the Health-Skillz envelope and plain Bundles.
        return (
            '"resourceType"' in head
            or '"fhir"' in head
            or '"providers"' in head
        )
    except OSError:
        return False


def _upload_session_to_collection(session_dir: Path) -> CollectionDefinition | None:
    """Synthesize a CollectionDefinition from one upload-session directory."""
    if not session_dir.is_dir():
        return None
    sources: list[SourceDefinition] = []
    for entry in sorted(session_dir.iterdir()):
        if not entry.is_file():
            continue
        # Skip metadata sidecars and extraction-cache files.
        if entry.name.endswith((".metadata.json", ".extracted.json")):
            continue
        suffix = entry.suffix.lower()
        if suffix == ".pdf":
            sources.append(
                SourceDefinition(
                    id=f"pdf-{entry.stem}",
                    label=entry.name,
                    kind="extracted-pdf",
                    # The extracted JSON is conventionally written next to
                    # the PDF as ``<basename>.extracted.json``. The loader
                    # will return an empty dict if the extraction hasn't
                    # been run yet — the manifest reflects that.
                    path=entry.with_suffix(entry.suffix + ".extracted.json"),
                    document_reference=f"DocumentReference/upload-{entry.stem}",
                )
            )
        elif suffix == ".json" and _looks_like_fhir(entry):
            sources.append(
                SourceDefinition(
                    id=f"fhir-{entry.stem}",
                    label=entry.name,
                    kind="fhir-pull",
                    path=entry,
                    document_reference=f"DocumentReference/upload-{entry.stem}",
                )
            )
    if not sources:
        return None
    return CollectionDefinition(
        id=f"upload-{session_dir.name}",
        name=f"Uploaded session · {session_dir.name}",
        description=(
            f"Documents uploaded under session ``{session_dir.name}``: "
            f"{sum(1 for s in sources if s.kind == 'extracted-pdf')} PDF(s), "
            f"{sum(1 for s in sources if s.kind == 'fhir-pull')} FHIR file(s)."
        ),
        sources=tuple(sources),
    )


def _discover_upload_collections() -> dict[str, CollectionDefinition]:
    if not UPLOADS_ROOT.exists():
        return {}
    out: dict[str, CollectionDefinition] = {}
    for sub in sorted(UPLOADS_ROOT.iterdir()):
        coll = _upload_session_to_collection(sub)
        if coll is not None:
            out[coll.id] = coll
    return out


def list_collections() -> list[CollectionDefinition]:
    """Static registry first, then any upload-derived collections."""
    out: list[CollectionDefinition] = list(_COLLECTIONS.values())
    out.extend(_discover_upload_collections().values())
    return out


def get_collection(collection_id: str) -> CollectionDefinition | None:
    if collection_id in _COLLECTIONS:
        return _COLLECTIONS[collection_id]
    return _discover_upload_collections().get(collection_id)


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


def merged_allergies(collection_id: str) -> list[MergedAllergy]:
    return merge_allergies(_bundles_for(collection_id, "AllergyIntolerance"))


def merged_immunizations(collection_id: str) -> list[MergedImmunization]:
    return merge_immunizations(_bundles_for(collection_id, "Immunization"))


def merged_medications(collection_id: str) -> list[MergedMedication]:
    """Merge MedicationRequests across sources.

    The matcher needs both ``MedicationRequest`` (the orders) and
    ``Medication`` (the contained resources holding RxNorm codes), so
    we hand both resource types into each ``SourceBundle``.
    """
    coll = get_collection(collection_id)
    if not coll:
        return []
    resources = load_collection_resources(collection_id)
    bundles: list[SourceBundle] = []
    for s in coll.sources:
        rs = resources.get(s.id, {})
        pool: list[dict] = list(rs.get("MedicationRequest", [])) + list(rs.get("Medication", []))
        if pool:
            bundles.append(
                SourceBundle(
                    label=s.label,
                    observations=pool,
                    document_reference=s.document_reference,
                )
            )
    return merge_medications(bundles)


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


def serialize_allergy(m: MergedAllergy) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "snomed": m.snomed,
        "rxnorm": m.rxnorm,
        "is_active": m.is_active,
        "highest_criticality": m.highest_criticality,
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_allergy_ref": s.source_allergy_ref,
                "display": s.display,
                "snomed": s.snomed,
                "rxnorm": s.rxnorm,
                "criticality": s.criticality,
                "clinical_status": s.clinical_status,
                "recorded_date": _iso(s.recorded_date),
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def serialize_immunization(m: MergedImmunization) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "cvx": m.cvx,
        "ndc": m.ndc,
        "occurrence_date": _iso(m.occurrence_date),
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_immunization_ref": s.source_immunization_ref,
                "display": s.display,
                "cvx": s.cvx,
                "ndc": s.ndc,
                "occurrence_date": _iso(s.occurrence_date),
                "status": s.status,
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def serialize_medication(m: MergedMedication) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "rxnorm_codes": list(m.rxnorm_codes),
        "is_active": m.is_active,
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_request_ref": s.source_request_ref,
                "display": s.display,
                "rxnorm_codes": list(s.rxnorm_codes),
                "status": s.status,
                "authored_on": _iso(s.authored_on),
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


# ---------------------------------------------------------------------------
# Manual extraction trigger (PDFs in upload-derived collections)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractResult:
    source_id: str
    label: str
    extracted_path: str
    cache_hit: bool
    entry_count: int
    elapsed_seconds: float


def extract_pending_pdfs(collection_id: str) -> list[ExtractResult] | None:
    """Run the multipass-fhir pipeline on every uploaded PDF in this collection
    that doesn't yet have a cached extraction next to it.

    Returns one ``ExtractResult`` per PDF processed (empty list if all PDFs
    already had cached extractions). Returns ``None`` when the collection
    doesn't exist or doesn't support extraction (the static demo collections
    are read-only).
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None
    # Only upload-derived collections support extraction. The static demo
    # registry's ``path`` fields point at pre-staged extractions.
    if not collection_id.startswith("upload-"):
        return None

    # Lazy import — keeps the api/ surface free of the heavy
    # extraction stack at module-load time.
    import time

    from ehi_atlas.extract.pipelines import get as get_pipeline

    PipelineCls = get_pipeline("multipass-fhir")
    pipeline = PipelineCls()

    session = collection_id.removeprefix("upload-")
    session_dir = UPLOADS_ROOT / session

    results: list[ExtractResult] = []
    for src in coll.sources:
        if src.kind != "extracted-pdf":
            continue
        # ``src.path`` is the *extracted* JSON path (which may not exist yet).
        # The actual PDF is in the upload directory; find it by stripping
        # the ``.extracted.json`` suffix off the filename and looking under
        # ``session_dir``.
        extracted_json = src.path
        pdf_name = extracted_json.name.removesuffix(".extracted.json")
        pdf_path = session_dir / pdf_name
        if not pdf_path.exists():
            continue
        if extracted_json.exists():
            results.append(
                ExtractResult(
                    source_id=src.id,
                    label=src.label,
                    extracted_path=str(extracted_json),
                    cache_hit=True,
                    entry_count=len(json.loads(extracted_json.read_text()).get("entry", [])),
                    elapsed_seconds=0.0,
                )
            )
            continue
        t0 = time.time()
        bundle = pipeline.extract(pdf_path)
        elapsed = time.time() - t0
        extracted_json.write_text(json.dumps(bundle, indent=2))
        results.append(
            ExtractResult(
                source_id=src.id,
                label=src.label,
                extracted_path=str(extracted_json),
                cache_hit=False,
                entry_count=len(bundle.get("entry", [])),
                elapsed_seconds=elapsed,
            )
        )
    # Bust the resource-loading cache so the next manifest/observations call
    # picks up the freshly-extracted JSON.
    _cached_load.cache_clear()
    return results


# ---------------------------------------------------------------------------
# Bidirectional Provenance walk — "what did this source document contribute?"
# ---------------------------------------------------------------------------


def facts_for_document_reference(
    collection_id: str, document_reference: str
) -> dict[str, Any] | None:
    """Reverse-walk the Provenance graph: list every merged fact whose
    sources include the given DocumentReference.

    Returns a dict shaped:

        {
          "document_reference": "DocumentReference/...",
          "label": "Cedars-Sinai (FHIR)",
          "kind": "fhir-pull",
          "observations": [serialized MergedObservation, ...],
          "conditions":   [serialized MergedCondition,   ...],
          "medications":  [serialized MergedMedication,  ...],
          "allergies":    [serialized MergedAllergy,     ...],
          "immunizations":[serialized MergedImmunization,...],
          "totals": {"observations": N, ...},
        }

    Each merged record appears in the list of resources of the right
    type if at least one of its sources points at this DocumentReference.
    Returns ``None`` for unknown collections.
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None

    # Find the matching SourceDefinition (label + kind) for the doc ref.
    matching_label: str | None = None
    matching_kind: str | None = None
    for s in coll.sources:
        if s.document_reference == document_reference:
            matching_label = s.label
            matching_kind = s.kind
            break

    def _has_doc_ref(sources: list, attr: str = "document_reference") -> bool:
        return any(getattr(s, attr, None) == document_reference for s in sources)

    obs_hits = [m for m in merged_observations(collection_id) if _has_doc_ref(m.sources)]
    cond_hits = [m for m in merged_conditions(collection_id) if _has_doc_ref(m.sources)]
    med_hits = [m for m in merged_medications(collection_id) if _has_doc_ref(m.sources)]
    allergy_hits = [m for m in merged_allergies(collection_id) if _has_doc_ref(m.sources)]
    im_hits = [m for m in merged_immunizations(collection_id) if _has_doc_ref(m.sources)]

    return {
        "document_reference": document_reference,
        "label": matching_label,
        "kind": matching_kind,
        "observations": [serialize_observation(m) for m in obs_hits],
        "conditions": [serialize_condition(m) for m in cond_hits],
        "medications": [serialize_medication(m) for m in med_hits],
        "allergies": [serialize_allergy(m) for m in allergy_hits],
        "immunizations": [serialize_immunization(m) for m in im_hits],
        "totals": {
            "observations": len(obs_hits),
            "conditions": len(cond_hits),
            "medications": len(med_hits),
            "allergies": len(allergy_hits),
            "immunizations": len(im_hits),
            "all": (
                len(obs_hits)
                + len(cond_hits)
                + len(med_hits)
                + len(allergy_hits)
                + len(im_hits)
            ),
        },
    }


# ---------------------------------------------------------------------------
# Multi-source contribution diff — "what did each source uniquely add?"
# ---------------------------------------------------------------------------


def source_contribution_diff(collection_id: str) -> dict[str, Any] | None:
    """Per-source unique vs shared fact counts and unique-fact listings.

    For each source bundle in the collection, compute:

      * **unique**: merged records where this source is the only contributor
        (i.e. ``len({s.source_label for s in record.sources}) == 1`` and
        the record's source label matches this source).
      * **shared**: merged records where this source contributed alongside
        at least one other source.

    Unique facts are the high-signal "if I removed this source, here's
    what I'd lose" set — and on the demo data they correspond to:

      * **vision wins** (PDF-only): clinical findings present in the
        narrative-PDF that the structured FHIR pull never coded
        (e.g. "Bilateral inferior turbinate hypertrophy" — see
        Move H in PIPELINE-LOG.md).
      * **FHIR-only**: structured facts only the API surfaces, like
        the COVID-19 Pfizer 2021 doses in the immunization history.

    Returns ``None`` for unknown collections.
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None

    obs = merged_observations(collection_id)
    cond = merged_conditions(collection_id)
    med = merged_medications(collection_id)
    allergy = merged_allergies(collection_id)
    im = merged_immunizations(collection_id)

    def _is_unique_to(record: Any, source_label: str) -> bool:
        labels = {s.source_label for s in record.sources}
        return len(labels) == 1 and source_label in labels

    def _is_shared_with(record: Any, source_label: str) -> bool:
        labels = {s.source_label for s in record.sources}
        return len(labels) > 1 and source_label in labels

    sources_out: list[dict[str, Any]] = []
    for s in coll.sources:
        unique_obs = [m for m in obs if _is_unique_to(m, s.label)]
        unique_cond = [m for m in cond if _is_unique_to(m, s.label)]
        unique_med = [m for m in med if _is_unique_to(m, s.label)]
        unique_allergy = [m for m in allergy if _is_unique_to(m, s.label)]
        unique_im = [m for m in im if _is_unique_to(m, s.label)]
        shared_obs = sum(1 for m in obs if _is_shared_with(m, s.label))
        shared_cond = sum(1 for m in cond if _is_shared_with(m, s.label))
        shared_med = sum(1 for m in med if _is_shared_with(m, s.label))
        shared_allergy = sum(1 for m in allergy if _is_shared_with(m, s.label))
        shared_im = sum(1 for m in im if _is_shared_with(m, s.label))

        unique_total = (
            len(unique_obs)
            + len(unique_cond)
            + len(unique_med)
            + len(unique_allergy)
            + len(unique_im)
        )
        shared_total = (
            shared_obs + shared_cond + shared_med + shared_allergy + shared_im
        )

        sources_out.append(
            {
                "id": s.id,
                "label": s.label,
                "kind": s.kind,
                "document_reference": s.document_reference,
                "totals": {
                    "unique": {
                        "observations": len(unique_obs),
                        "conditions": len(unique_cond),
                        "medications": len(unique_med),
                        "allergies": len(unique_allergy),
                        "immunizations": len(unique_im),
                        "all": unique_total,
                    },
                    "shared": {
                        "observations": shared_obs,
                        "conditions": shared_cond,
                        "medications": shared_med,
                        "allergies": shared_allergy,
                        "immunizations": shared_im,
                        "all": shared_total,
                    },
                },
                "unique_facts": {
                    "observations": [serialize_observation(m) for m in unique_obs],
                    "conditions": [serialize_condition(m) for m in unique_cond],
                    "medications": [serialize_medication(m) for m in unique_med],
                    "allergies": [serialize_allergy(m) for m in unique_allergy],
                    "immunizations": [serialize_immunization(m) for m in unique_im],
                },
            }
        )

    return {
        "collection_id": collection_id,
        "sources": sources_out,
    }


def find_merged_record(collection_id: str, merged_ref: str):
    """Look up a merged record by its synthetic ref ID across all resource types."""
    if merged_ref.startswith("Observation/"):
        for m in merged_observations(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("Condition/"):
        for m in merged_conditions(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("MedicationRequest/"):
        for m in merged_medications(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("AllergyIntolerance/"):
        for m in merged_allergies(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("Immunization/"):
        for m in merged_immunizations(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    return None


def provenance_for_ref(collection_id: str, merged_ref: str) -> dict[str, Any] | None:
    record = find_merged_record(collection_id, merged_ref)
    if record is None:
        return None
    return mint_provenance(record)
