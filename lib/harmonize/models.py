"""Data models for the harmonization layer.

These dataclasses are the "merged" shape that the layer produces — distinct
from raw FHIR Observation resources because a merged fact may be backed by
multiple source observations across sources, dates, and code systems.

The corresponding FHIR Provenance resources are produced by
``lib.harmonize.provenance.mint_provenance`` and reference the canonical
Atlas Extension URLs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ObservationSource:
    """One source observation backing a merged fact.

    A merged Observation typically has 1..N sources — one per ingestion path
    where the fact was found. The same patient lab on two different dates
    becomes two ``ObservationSource`` entries on one merged record (we treat
    repeated measurements as the same canonical fact, longitudinal).
    """

    source_label: str
    """Human-readable source name, e.g. ``"Cedars-Sinai"`` or ``"Function Health"``."""

    source_observation_ref: str
    """FHIR reference back to the originating Observation, e.g.
    ``"Observation/abc-123"`` (Cedars) or
    ``"Observation/extracted://lab-report/.../obs-7"`` (PDF extraction)."""

    value: float | None
    """Numeric value, normalized to the canonical unit. ``None`` for
    qualitative observations (e.g. urine appearance)."""

    unit: str | None
    """Unit string after normalization (e.g. ``"mg/dL"``)."""

    raw_value: float | None
    """Original numeric value as it appeared in the source, before any
    unit conversion. Useful when surfacing the source data verbatim."""

    raw_unit: str | None
    """Original unit string as it appeared in the source."""

    effective_date: datetime | None
    """When the observation was made. Pulled from
    ``Observation.effectiveDateTime`` or ``effectiveInstant`` or ``issued``."""

    document_reference: str | None = None
    """If the source is a document (PDF), the FHIR DocumentReference
    pointing at the source document. Used by the Provenance graph."""


@dataclass(frozen=True)
class ProvenanceEdge:
    """One edge in the Provenance graph: which fact came from which source.

    A merged Observation produces one ``ProvenanceEdge`` per source. The
    full graph for a patient is the union of all edges across all merged
    facts. Materialized as FHIR Provenance resources by
    ``lib.harmonize.provenance.mint_provenance``.
    """

    target_ref: str
    """FHIR reference of the merged fact (e.g. ``"Observation/merged-loinc-13457-7"``)."""

    source_ref: str
    """FHIR reference of the source observation."""

    source_label: str
    """Human-readable source name."""

    activity: str
    """What harmonization step produced this edge:
    ``"loinc-match"`` | ``"name-match"`` | ``"unit-normalize"`` | ``"passthrough"``."""

    recorded: datetime
    """When the edge was minted."""


@dataclass(frozen=True)
class ConditionSource:
    """One source Condition backing a merged condition.

    Conditions don't carry numeric values, so the merged shape differs
    slightly from Observations: the source-level fields are coding +
    clinical status + onset date.
    """

    source_label: str
    """Human-readable source name."""

    source_condition_ref: str
    """FHIR reference to the originating Condition."""

    display: str
    """The free-text label as it appeared in the source."""

    snomed: str | None
    icd10: str | None
    icd9: str | None
    """Codes the source attached. None for any code system the source omitted."""

    clinical_status: str | None
    """``active`` / ``recurrence`` / ``relapse`` / ``inactive`` / ``remission`` /
    ``resolved`` per FHIR. None when the source didn't record one."""

    onset_date: datetime | None
    """When the condition was first noted, from ``onsetDateTime`` or
    ``recordedDate``. None for conditions without a date stamp."""

    document_reference: str | None = None


@dataclass
class MergedCondition:
    """A canonical condition, optionally backed by multiple sources.

    Identity is keyed on SNOMED → ICD-10 → ICD-9 → normalized name (in
    that priority). Sources contribute coding incrementally — a
    SNOMED-only source plus an ICD-10-only source produces a merged
    record with both codes filled in.
    """

    canonical_name: str
    """The display name we surface — the source's text, or a code if no
    text was present."""

    snomed: str | None
    icd10: str | None
    icd9: str | None

    sources: list[ConditionSource] = field(default_factory=list)
    provenance: list[ProvenanceEdge] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """Whether any source still considers the condition active.

        Conservative: returns True if any source has clinical_status of
        active/recurrence/relapse, OR if no source recorded a status
        (most PDF-extracted conditions lack clinical_status).
        """
        seen_any_status = False
        for s in self.sources:
            if not s.clinical_status:
                continue
            seen_any_status = True
            if s.clinical_status in ("active", "recurrence", "relapse"):
                return True
        return not seen_any_status


@dataclass(frozen=True)
class MedicationSource:
    """One source MedicationRequest backing a merged medication.

    Multiple source requests for the same canonical medication collapse
    onto one ``MergedMedication`` (e.g. one prescription record from the
    EHR FHIR pull plus one extracted from a discharge summary PDF).
    Refills and dose changes appear as additional sources on the same
    merged record.
    """

    source_label: str
    source_request_ref: str
    display: str
    rxnorm_codes: tuple[str, ...]
    status: str | None
    """``active`` / ``completed`` / ``stopped`` / ``on-hold`` / etc.
    Per FHIR MedicationRequest.status."""

    authored_on: datetime | None
    document_reference: str | None = None


@dataclass
class MergedMedication:
    """A canonical medication, optionally backed by multiple sources.

    Identity priority: any RxNorm code overlap → drug-name canonical
    form (generic name with brand parenthetical and dose stripped) →
    normalized full-text passthrough. Sources contribute RxNorm codes
    incrementally — the merged record's ``rxnorm_codes`` is the union
    across all contributing sources.
    """

    canonical_name: str
    rxnorm_codes: tuple[str, ...]

    sources: list[MedicationSource] = field(default_factory=list)
    provenance: list[ProvenanceEdge] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """True if any source still considers the medication active.

        Mirrors ``MergedCondition.is_active`` semantics: PDF-extracted
        MedicationRequests often lack a status, so missing-status defaults
        to active rather than inactive.
        """
        seen_any_status = False
        for s in self.sources:
            if not s.status:
                continue
            seen_any_status = True
            if s.status in ("active", "on-hold"):
                return True
        return not seen_any_status


@dataclass
class MergedObservation:
    """A canonical fact, optionally backed by multiple sources.

    The merged fact has a stable identity — typically a LOINC code — that
    survives across ingestion paths. ``sources`` is the longitudinal list
    of every source observation that contributed.
    """

    canonical_name: str
    """Human-readable canonical name, e.g. ``"Hemoglobin A1c"``."""

    loinc_code: str | None
    """LOINC code if known. ``None`` for facts where neither source had
    LOINC and the bridge couldn't resolve a name."""

    canonical_unit: str | None
    """The unit we normalized values to. ``None`` for qualitative facts."""

    sources: list[ObservationSource] = field(default_factory=list)
    """Every source observation that backs this merged fact, in
    chronological order (oldest first)."""

    provenance: list[ProvenanceEdge] = field(default_factory=list)
    """The Provenance edges this merge produced — one per source."""

    @property
    def latest(self) -> ObservationSource | None:
        """Most recent source observation."""
        dated = [s for s in self.sources if s.effective_date is not None]
        if not dated:
            return self.sources[-1] if self.sources else None

        def _ts(s: ObservationSource) -> float:
            d = s.effective_date
            assert d is not None
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.timestamp()

        return max(dated, key=_ts)

    @property
    def has_conflict(self) -> bool:
        """Whether sources disagree by more than 10% on the same date.

        Conservative: only flags two values on the *same* effective date with
        |Δ| / mean > 0.10. Same-day disagreement across sources is the
        canonical conflict case (e.g. two providers measure the same blood
        draw differently). Longitudinal change isn't a conflict.
        """
        from collections import defaultdict

        by_date: dict[str, list[float]] = defaultdict(list)
        for s in self.sources:
            if s.value is None or s.effective_date is None:
                continue
            by_date[s.effective_date.date().isoformat()].append(s.value)
        for vals in by_date.values():
            if len(vals) < 2:
                continue
            mean = sum(vals) / len(vals)
            if mean == 0:
                continue
            spread = (max(vals) - min(vals)) / abs(mean)
            if spread > 0.10:
                return True
        return False
