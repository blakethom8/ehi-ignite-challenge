"""Code mapping for Layer 3 harmonization.

Bridges code systems via the UMLS CUI in our hand-curated crosswalk
(corpus/reference/handcrafted-crosswalk/showcase.json). Two codes from
different systems are "equivalent" if they map to the same UMLS CUI in
the crosswalk.

Phase 1 only handles the showcase patient's codes. Phase 2 = full UMLS load.

Supported code systems (FHIR-canonical URIs):
  - http://snomed.info/sct        (SNOMED CT)
  - http://hl7.org/fhir/sid/icd-10-cm  (ICD-10-CM)
  - http://www.nlm.nih.gov/research/umls/rxnorm  (RxNorm)
  - http://loinc.org              (LOINC — crosswalk does not contain LOINC
                                   entries in Phase 1; lookups will return
                                   found_in_crosswalk=False)

Supported FHIR resource types for annotate_resource_codings():
  - Condition         → resource["code"]
  - Observation       → resource["code"]
  - MedicationRequest → resource["medicationCodeableConcept"] (when present)
  Non-listed resource types are returned unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from ehi_atlas.harmonize.provenance import EXT_UMLS_CUI
from ehi_atlas.terminology import lookup_cross

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Code system URIs (FHIR-canonical form)
# ---------------------------------------------------------------------------

SYS_SNOMED = "http://snomed.info/sct"
SYS_ICD10_CM = "http://hl7.org/fhir/sid/icd-10-cm"
SYS_RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SYS_LOINC = "http://loinc.org"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodingRef:
    """A FHIR Coding's identifying fields, normalized.

    Attributes:
        system: FHIR-canonical code system URI (e.g. SYS_SNOMED).
        code:   The code value (e.g. "38341003").
        display: Optional human-readable display string.
    """

    system: str
    code: str
    display: str | None = None


@dataclass(frozen=True)
class ConceptResolution:
    """Result of resolving a coding via the crosswalk.

    Attributes:
        coding:             The original CodingRef that was looked up.
        umls_cui:           The UMLS CUI if found in the crosswalk, else None.
        crosswalk_label:    The concept_label from the crosswalk entry, else None.
        found_in_crosswalk: True only when the crosswalk has an entry for this
                            (system, code) pair.
    """

    coding: CodingRef
    umls_cui: str | None
    crosswalk_label: str | None
    found_in_crosswalk: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _coding_ref_from_dict(coding: dict) -> CodingRef:
    """Convert a FHIR Coding dict to a CodingRef."""
    return CodingRef(
        system=coding.get("system", ""),
        code=coding.get("code", ""),
        display=coding.get("display"),
    )


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def resolve_coding(coding: dict | CodingRef) -> ConceptResolution:
    """Look up a single Coding in the crosswalk; return its UMLS CUI if known.

    Args:
        coding: Either a :class:`CodingRef` or a FHIR Coding dict with
                at minimum ``system`` and ``code`` keys.

    Returns:
        A :class:`ConceptResolution`. ``found_in_crosswalk`` is False when
        the (system, code) pair is not in the Phase 1 crosswalk.
    """
    if isinstance(coding, dict):
        ref = _coding_ref_from_dict(coding)
    else:
        ref = coding

    entry = lookup_cross(ref.system, ref.code)
    if entry is None:
        return ConceptResolution(
            coding=ref,
            umls_cui=None,
            crosswalk_label=None,
            found_in_crosswalk=False,
        )
    return ConceptResolution(
        coding=ref,
        umls_cui=entry.get("umls_cui"),
        crosswalk_label=entry.get("concept_label"),
        found_in_crosswalk=True,
    )


def codings_equivalent(a: dict | CodingRef, b: dict | CodingRef) -> bool:
    """True if both codings resolve to the same non-None UMLS CUI in the crosswalk.

    If either coding is unmappable (not in the crosswalk), returns False.
    We never guess — unknown codes do not "match" anything.

    Args:
        a: First coding (CodingRef or FHIR Coding dict).
        b: Second coding (CodingRef or FHIR Coding dict).
    """
    res_a = resolve_coding(a)
    res_b = resolve_coding(b)
    if not res_a.found_in_crosswalk or not res_b.found_in_crosswalk:
        return False
    if res_a.umls_cui is None or res_b.umls_cui is None:
        return False
    return res_a.umls_cui == res_b.umls_cui


def codeable_concepts_equivalent(a: dict, b: dict) -> bool:
    """True if any coding in a shares a UMLS CUI with any coding in b.

    Handles FHIR CodeableConcept dicts (``{"coding": [...], "text": "..."}``)
    by trying every (a.coding[i], b.coding[j]) pair.

    Args:
        a: First FHIR CodeableConcept dict.
        b: Second FHIR CodeableConcept dict.

    Returns:
        True as soon as any cross-system CUI match is found. False if no
        pair resolves to the same CUI, or if either concept has no codings.
    """
    codings_a: list[dict] = a.get("coding", [])
    codings_b: list[dict] = b.get("coding", [])

    for ca in codings_a:
        for cb in codings_b:
            if codings_equivalent(ca, cb):
                return True
    return False


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------


def annotate_codeable_concept_with_cui(concept: dict) -> dict:
    """For each coding in a CodeableConcept, attach the UMLS CUI extension if known.

    Walks ``concept["coding"]`` (a list of FHIR Coding dicts). For each entry
    that has a crosswalk hit, appends:

        {"url": EXT_UMLS_CUI, "valueString": "<CUI>"}

    to that coding's ``extension`` list.

    Idempotent: if the extension URL is already present for a coding, the
    value is updated in place rather than duplicated.

    Mutates and returns the concept dict.

    Args:
        concept: A FHIR CodeableConcept dict (must have a "coding" list).
    """
    for coding_dict in concept.get("coding", []):
        res = resolve_coding(coding_dict)
        if not res.found_in_crosswalk or res.umls_cui is None:
            continue

        # Ensure extension list exists on this coding
        if "extension" not in coding_dict:
            coding_dict["extension"] = []

        # Idempotent: update existing entry if already present
        for ext in coding_dict["extension"]:
            if ext.get("url") == EXT_UMLS_CUI:
                ext["valueString"] = res.umls_cui
                break
        else:
            coding_dict["extension"].append(
                {"url": EXT_UMLS_CUI, "valueString": res.umls_cui}
            )

    return concept


def annotate_resource_codings(resource: dict) -> dict:
    """Walk a FHIR resource and annotate CodeableConcepts with UMLS CUIs.

    Handles the following resource types and their primary CodeableConcept
    locations:

    - **Condition**          → ``resource["code"]``
    - **Observation**        → ``resource["code"]``
    - **MedicationRequest**  → ``resource["medicationCodeableConcept"]``
                               (only when ``medicationCodeableConcept`` is
                               present; ``medicationReference`` cases are
                               silently skipped)

    Non-listed resource types are returned unchanged. The function is
    idempotent: calling it twice on the same resource does not duplicate
    extensions.

    Args:
        resource: A mutable FHIR resource dict with a ``resourceType`` key.

    Returns:
        The same dict, mutated in place.
    """
    rtype = resource.get("resourceType", "")

    if rtype in ("Condition", "Observation"):
        code_cc = resource.get("code")
        if isinstance(code_cc, dict):
            annotate_codeable_concept_with_cui(code_cc)

    elif rtype == "MedicationRequest":
        med_cc = resource.get("medicationCodeableConcept")
        if isinstance(med_cc, dict):
            annotate_codeable_concept_with_cui(med_cc)

    else:
        logger.debug(
            "annotate_resource_codings: skipping unsupported resourceType %r", rtype
        )

    return resource


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------


def collect_concept_groups(
    resources: Iterable[dict], path: str = "code"
) -> dict[str, list[dict]]:
    """Group resources by their primary code's UMLS CUI.

    Resolves each resource's primary CodeableConcept (found at the field
    named ``path``) against the crosswalk. Resources that match a CUI are
    collected under that CUI key.

    Resources with no crosswalk hit are excluded — callers may use exact-code
    fallback for those ungrouped resources.

    Args:
        resources: Iterable of FHIR resource dicts (any resourceType).
        path:      The field name on each resource holding the primary
                   CodeableConcept. Defaults to ``"code"``, which is correct
                   for Condition, Observation, and most clinical resources.
                   For MedicationRequest with ``medicationCodeableConcept``,
                   pass ``path="medicationCodeableConcept"``.

    Returns:
        A dict mapping UMLS CUI → list of resource dicts that resolved to
        that CUI. Order within each group matches input order.

    Example::

        groups = collect_concept_groups([cond_htn_snomed, cond_htn_icd10, cond_t2dm])
        # → {"C0020538": [cond_htn_snomed, cond_htn_icd10], "C0011860": [cond_t2dm]}
    """
    groups: dict[str, list[dict]] = {}

    for resource in resources:
        concept = resource.get(path)
        if not isinstance(concept, dict):
            continue

        # Try each coding in the CodeableConcept until we get a CUI hit
        cui: str | None = None
        for coding_dict in concept.get("coding", []):
            res = resolve_coding(coding_dict)
            if res.found_in_crosswalk and res.umls_cui:
                cui = res.umls_cui
                break

        if cui is not None:
            groups.setdefault(cui, []).append(resource)

    return groups
