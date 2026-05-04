"""Cross-source MedicationRequest matcher.

Same architecture as ``observations.py`` and ``conditions.py``. Identity
strategies (in priority order):

1. **RxNorm code match** — both sources share at least one RxNorm code.
   Cedars FHIR pulls typically attach 5–20 RxNorm codes per medication
   (one per generic/strength/formulation variant); we union the sets and
   match if any code overlaps.
2. **Drug-name canonicalization** — strip brand-name parentheticals
   ("fluticasone propionate (FLONASE) 50 mcg/actuation nasal spray" →
   "fluticasone propionate"), drop dose/formulation tail, and key on the
   normalized generic name.
3. **Normalized full-text passthrough** — last-resort match on the
   lowercased full display text.

FHIR ``MedicationRequest`` resources reference a separate ``Medication``
resource via ``medicationReference``; the matcher resolves the reference
when that's where the codes actually live (Cedars-style). PDF-extracted
MedicationRequests use ``medicationCodeableConcept.text`` directly.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import MergedMedication, MedicationSource, ProvenanceEdge
from .observations import SourceBundle


_RXNORM_SYSTEMS = (
    "rxnorm",
    "rxnav.nlm.nih.gov/rxnorm",
    "http://www.nlm.nih.gov/research/umls/rxnorm",
)


def _is_rxnorm_system(system: str) -> bool:
    s = system.lower()
    return any(frag in s for frag in _RXNORM_SYSTEMS)


def _resolve_medication_codes(
    mr: dict[str, Any], medications_by_id: dict[str, dict[str, Any]]
) -> tuple[set[str], str, list[dict[str, Any]]]:
    """Return ``(rxnorm_codes, display_text, all_codings)`` for one MedicationRequest.

    Pulls from inline ``medicationCodeableConcept`` first, then resolves
    ``medicationReference`` against the bundle's ``Medication`` resources.
    """
    rxnorm: set[str] = set()
    display = ""
    codings: list[dict[str, Any]] = []

    inline = mr.get("medicationCodeableConcept") or {}
    if inline:
        display = inline.get("text") or display
        for c in inline.get("coding", []):
            codings.append(c)
            if _is_rxnorm_system(c.get("system", "")) and c.get("code"):
                rxnorm.add(c["code"])

    ref = mr.get("medicationReference") or {}
    if ref:
        # Reference shape: ``Medication/<id>``. Bundles may also use a
        # full URL or a urn:uuid; strip down to the id segment.
        raw_ref = ref.get("reference", "")
        if "/" in raw_ref:
            med_id = raw_ref.rsplit("/", 1)[-1]
        else:
            med_id = raw_ref
        med = medications_by_id.get(med_id)
        if med:
            code = med.get("code") or {}
            display = display or code.get("text") or ""
            for c in code.get("coding", []):
                codings.append(c)
                if _is_rxnorm_system(c.get("system", "")) and c.get("code"):
                    rxnorm.add(c["code"])
        # Fall back to the reference display when neither inline nor
        # contained Medication had text.
        if not display:
            display = ref.get("display", "")
    return rxnorm, display, codings


_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_FIRST_DIGIT_RE = re.compile(r"\d")


def canonical_drug_name(raw: str) -> str:
    """Extract a generic-name match key from a free-text medication string.

    "fluticasone propionate (FLONASE) 50 mcg/actuation nasal spray"
        → "fluticasone propionate"
    "cetirizine (ZyrTEC) 10 mg tablet" → "cetirizine"
    "Vitamin D3 1000 IU oral capsule" → "vitamin d3"

    Strategy: lowercase → strip parentheticals → cut at first digit
    → strip trailing whitespace and punctuation. Empty result when
    ``raw`` doesn't contain a plausible drug name.
    """
    if not raw:
        return ""
    s = raw.lower()
    s = _PAREN_RE.sub("", s)
    m = _FIRST_DIGIT_RE.search(s)
    if m:
        s = s[: m.start()]
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_status(mr: dict[str, Any]) -> str | None:
    return mr.get("status")


def _extract_authored_on(mr: dict[str, Any]) -> datetime | None:
    raw = mr.get("authoredOn")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _mr_ref(mr: dict[str, Any], source_label: str, idx: int) -> str:
    if rid := mr.get("id"):
        return f"MedicationRequest/{rid}"
    slug = source_label.lower().replace(" ", "-")
    return f"MedicationRequest/{slug}-{idx}"


def merge_medications(sources: Iterable[SourceBundle]) -> list[MergedMedication]:
    """Merge MedicationRequests across sources.

    The matcher reads ``MedicationRequest`` resources from each
    ``SourceBundle.observations`` list (the field name is reused across
    resource types — see the comment in ``conditions.merge_conditions``).
    It also pulls in any ``Medication`` resources from the bundle to
    resolve ``medicationReference`` codings, but the harmonize_service
    layer is responsible for stitching those together: when calling this
    function, include all relevant ``Medication`` resources alongside the
    ``MedicationRequest`` resources in the same SourceBundle.
    """
    by_key: dict[str, MergedMedication] = {}
    name_to_key: dict[str, str] = {}
    # Any RxNorm code in the union of any source's set can be used to
    # find an existing merged record. The lookup index keeps this O(1)
    # without depending on which code we picked as the primary key.
    rxnorm_to_key: dict[str, str] = {}
    now = datetime.now()

    for bundle in sources:
        # Build per-bundle Medication-id index (for medicationReference resolution).
        meds_by_id: dict[str, dict[str, Any]] = {}
        for r in bundle.observations:
            if r.get("resourceType") == "Medication":
                rid = r.get("id")
                if rid:
                    meds_by_id[rid] = r

        for idx, mr in enumerate(bundle.observations):
            if mr.get("resourceType") != "MedicationRequest":
                continue
            rxnorm, display, codings = _resolve_medication_codes(mr, meds_by_id)
            canon = canonical_drug_name(display)

            # Identity priority: any RxNorm code (try each as a candidate
            # key, taking the first that already exists in the registry;
            # otherwise pick the smallest as primary), then drug-name
            # canonical form, then full-text passthrough.
            existing_key: str | None = None
            for code in rxnorm:
                if code in rxnorm_to_key:
                    existing_key = rxnorm_to_key[code]
                    break
            if existing_key:
                key = existing_key
                activity = "rxnorm-match"
            elif rxnorm:
                key = f"rxnorm:{sorted(rxnorm)[0]}"
                activity = "rxnorm-match"
            elif canon and canon in name_to_key:
                key = name_to_key[canon]
                activity = "drug-name-bridge"
            elif canon:
                key = f"drug:{canon}"
                activity = "drug-name-match"
            else:
                norm = display.lower().strip()
                if not norm:
                    continue
                key = f"name:{norm}"
                activity = "passthrough"

            ref = _mr_ref(mr, bundle.label, idx)
            source = MedicationSource(
                source_label=bundle.label,
                source_request_ref=ref,
                display=display,
                rxnorm_codes=tuple(sorted(rxnorm)),
                status=_extract_status(mr),
                authored_on=_extract_authored_on(mr),
                document_reference=bundle.document_reference,
            )

            # Register canonical-name → key mapping so later text-only
            # sources can attach onto coded records.
            if canon and canon not in name_to_key:
                name_to_key[canon] = key

            merged = by_key.get(key)
            if merged is None:
                target_ref = (
                    f"MedicationRequest/merged-rxnorm-{key.split(':', 1)[1]}"
                    if key.startswith("rxnorm:")
                    else f"MedicationRequest/merged-{key.split(':', 1)[1].replace(' ', '-')}"
                )
                merged = MergedMedication(
                    canonical_name=canon or display,
                    rxnorm_codes=tuple(sorted(rxnorm)),
                )
                merged._merged_ref = target_ref  # type: ignore[attr-defined]
                by_key[key] = merged
            else:
                if rxnorm:
                    union = set(merged.rxnorm_codes) | rxnorm
                    merged.rxnorm_codes = tuple(sorted(union))

            # Register every RxNorm code in this source against the merged
            # record's key, so a future source whose set overlaps via any
            # of these codes (not just the primary) finds this record.
            for code in rxnorm:
                rxnorm_to_key.setdefault(code, key)

            merged.sources.append(source)
            merged.provenance.append(
                ProvenanceEdge(
                    target_ref=getattr(merged, "_merged_ref"),
                    source_ref=ref,
                    source_label=bundle.label,
                    activity=activity,
                    recorded=now,
                )
            )

    # Chronological: oldest first by authored_on.
    def _sort_key(s: MedicationSource) -> float:
        d = s.authored_on
        if d is None:
            return float("-inf")
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()

    for m in by_key.values():
        m.sources.sort(key=_sort_key)
    return sorted(by_key.values(), key=lambda m: m.canonical_name.lower())
