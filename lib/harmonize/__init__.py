"""Atlas harmonization layer — cross-source merge with FHIR-native Provenance.

Public API:

    from lib.harmonize import merge_observations, MergedObservation

The harmonization layer takes per-source FHIR Observation lists (from
heterogeneous ingestion paths — Cedars FHIR pull, Function Health PDF
extraction, etc.) and produces:

1. A canonical merged longitudinal view, identity-resolved by LOINC code
   (with text-based fallback when one source uses LOINC and the other
   doesn't).
2. FHIR Provenance resources that record where each fact came from,
   conforming to the Atlas Provenance Extension URLs.

Scope (v1): Observations only. Conditions, Medications, Allergies,
Immunizations follow the same shape but are not yet implemented.
"""

from __future__ import annotations

from .models import (
    MergedObservation,
    ObservationSource,
    ProvenanceEdge,
)
from .observations import SourceBundle, merge_observations
from .provenance import mint_provenance, mint_provenance_bundle

__all__ = [
    "merge_observations",
    "mint_provenance",
    "mint_provenance_bundle",
    "MergedObservation",
    "ObservationSource",
    "ProvenanceEdge",
    "SourceBundle",
]
