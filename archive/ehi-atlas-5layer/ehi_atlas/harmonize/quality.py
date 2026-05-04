"""Quality scoring for Layer 3 harmonization.

Three components combined into a single 0-1 score:
  - Recency: newer data is more reliable (40% weight)
  - Source authority: hospital FHIR > Epic EHI > extracted PDF > extracted text (40%)
  - Completeness: how many expected fields are populated (20%)

Deterministic. Same input -> same output. No ML; this is explicit policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from ehi_atlas.harmonize.temporal import clinical_time
from ehi_atlas.harmonize.provenance import attach_quality_score, SYS_SOURCE_TAG


# Phase 1 reference date for recency calculation. Frozen for determinism;
# Phase 2 swaps for date.today().
REFERENCE_DATE = date(2026, 4, 29)

# Component weights (sum to 1.0)
WEIGHT_RECENCY      = 0.4
WEIGHT_AUTHORITY    = 0.4
WEIGHT_COMPLETENESS = 0.2


# Source-authority lookup, scored 0-1. The score reflects "how much should I
# trust a fact attributed to this source?" -- derived from data lineage, not
# from clinical accuracy of the source.
SOURCE_AUTHORITY_SCORE: dict[str, float] = {
    # FHIR API pulls from a clinical system -- highest authority
    "synthea":       0.85,   # synthetic but generated end-to-end
    "ccda":          0.80,   # vendor-emitted clinical document
    # EHR-native exports
    "epic-ehi":      0.85,   # Epic's official EHI Export shape
    # Payer-side data -- different domain, slightly lower authority for clinical facts
    "synthea-payer": 0.70,
    "blue-button":   0.70,
    # Extracted from unstructured input
    "lab-pdf":       0.65,   # vision-extracted with structured layout
    "synthesized-clinical-note": 0.60,  # text-extracted free-form note
    # Default for unknown sources
    "_default":      0.50,
}


# Completeness expectations per resource type.
# The tuple lists fields whose presence signals a well-formed resource.
COMPLETENESS_FIELDS: dict[str, tuple[str, ...]] = {
    "Observation": ("code", "subject", "valueQuantity", "effectiveDateTime"),
    "Condition": ("code", "subject", "clinicalStatus", "verificationStatus", "onsetDateTime"),
    "MedicationRequest": ("medicationCodeableConcept", "subject", "status", "authoredOn"),
    "Encounter": ("class", "subject", "period"),
    "Procedure": ("code", "subject", "status", "performedDateTime"),
    "AllergyIntolerance": ("code", "patient", "clinicalStatus"),
    "Patient": ("name", "birthDate", "gender"),
    "DocumentReference": ("type", "subject", "content"),
    # Default if not listed: 0.5 floor (see completeness_score)
}


# ---- Component scorers -----------------------------------------------------

def recency_score(resource: dict, *, ref_date: date = REFERENCE_DATE) -> float:
    """Score in [0,1] based on clinical-time recency.

    Within 1y of ref_date -> 1.0
    1-3y                  -> 0.8
    3-5y                  -> 0.5
    5y+                   -> 0.3
    No clinical time      -> 0.5 (neutral)
    """
    ct = clinical_time(resource)
    if ct.timestamp is None:
        return 0.5

    # Convert ref_date to a tz-aware datetime at midnight UTC for comparison
    ref_dt = datetime(ref_date.year, ref_date.month, ref_date.day, tzinfo=timezone.utc)

    # Age in fractional years (365.25 days per year)
    delta_days = (ref_dt - ct.timestamp).total_seconds() / 86400.0
    age_years = delta_days / 365.25

    # Resources with a future clinical time relative to ref_date
    # (e.g. scheduled future appointments) are treated as "within 1y"
    if age_years < 0:
        return 1.0
    elif age_years < 1:
        return 1.0
    elif age_years < 3:
        return 0.8
    elif age_years < 5:
        return 0.5
    else:
        return 0.3


def authority_score(resource: dict) -> float:
    """Score in [0,1] from the resource's source-tag.

    Walks resource.meta.tag[] for the source-tag system; first match wins.
    Falls back to SOURCE_AUTHORITY_SCORE['_default'] if no tag found.
    """
    tags: list = resource.get("meta", {}).get("tag", []) or []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if tag.get("system") == SYS_SOURCE_TAG:
            code = tag.get("code", "")
            return SOURCE_AUTHORITY_SCORE.get(code, SOURCE_AUTHORITY_SCORE["_default"])
    return SOURCE_AUTHORITY_SCORE["_default"]


def completeness_score(resource: dict) -> float:
    """Score in [0,1] from how many expected fields are populated.

    For known resource types, the fraction of COMPLETENESS_FIELDS present
    (where 'present' means truthy, not null/empty).
    For unknown types: 0.5 floor.
    """
    rt = resource.get("resourceType")
    expected_fields = COMPLETENESS_FIELDS.get(rt)
    if expected_fields is None:
        return 0.5

    if len(expected_fields) == 0:
        return 1.0

    present = sum(1 for field in expected_fields if resource.get(field))
    return present / len(expected_fields)


# ---- Aggregate -------------------------------------------------------------

@dataclass(frozen=True)
class QualityComponents:
    """Decomposed quality score; useful for explainability + audit."""
    recency: float
    authority: float
    completeness: float
    aggregate: float


def quality_components(resource: dict, *, ref_date: date = REFERENCE_DATE) -> QualityComponents:
    """Return all three components + the weighted aggregate."""
    r = recency_score(resource, ref_date=ref_date)
    a = authority_score(resource)
    c = completeness_score(resource)
    agg = WEIGHT_RECENCY * r + WEIGHT_AUTHORITY * a + WEIGHT_COMPLETENESS * c
    # Clamp to [0, 1] for safety against floating-point edge cases
    agg = max(0.0, min(1.0, agg))
    return QualityComponents(
        recency=r,
        authority=a,
        completeness=c,
        aggregate=agg,
    )


def quality_score(resource: dict, *, ref_date: date = REFERENCE_DATE) -> float:
    """Convenience wrapper: returns just the aggregate. Always in [0,1]."""
    return quality_components(resource, ref_date=ref_date).aggregate


def annotate_quality(resource: dict, *, ref_date: date = REFERENCE_DATE) -> dict:
    """Compute quality_score(resource) and attach via the provenance helper.

    Mutates and returns the resource. Idempotent.
    """
    score = quality_score(resource, ref_date=ref_date)
    attach_quality_score(resource, score)
    return resource
