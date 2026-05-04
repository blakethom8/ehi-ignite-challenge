"""Cross-source AllergyIntolerance matcher.

Mirrors ``conditions.py``: identity strategies in priority order are
SNOMED → RxNorm (for drug allergies) → normalized name → name-bridge
fallback for text-only sources whose display matches an already-merged
coded record.

Allergies are *chronic state* — there's no date-bucketing dimension
like immunizations. The same allergy recorded by two sources collapses
onto one merged record regardless of when it was noted.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import AllergySource, MergedAllergy, ProvenanceEdge
from .observations import SourceBundle


_SNOMED_FRAGS = ("snomed.info/sct",)
_RXNORM_FRAGS = ("rxnorm",)


def _extract_codes(allergy: dict[str, Any]) -> tuple[str | None, str | None]:
    snomed = rxnorm = None
    for c in allergy.get("code", {}).get("coding", []):
        sys_ = c.get("system", "").lower()
        code = c.get("code")
        if not code:
            continue
        if any(f in sys_ for f in _SNOMED_FRAGS):
            snomed = snomed or code
        elif any(f in sys_ for f in _RXNORM_FRAGS):
            rxnorm = rxnorm or code
    return snomed, rxnorm


def _extract_name(allergy: dict[str, Any]) -> str:
    code = allergy.get("code", {})
    if text := code.get("text"):
        return text
    for c in code.get("coding", []):
        if d := c.get("display"):
            return d
    return ""


def _normalize_name(raw: str) -> str:
    s = raw.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_clinical_status(allergy: dict[str, Any]) -> str | None:
    cs = allergy.get("clinicalStatus") or {}
    for c in cs.get("coding", []):
        if code := c.get("code"):
            return code
    return None


def _extract_criticality(allergy: dict[str, Any]) -> str | None:
    """``low`` / ``high`` / ``unable-to-assess`` per FHIR."""
    return allergy.get("criticality")


def _extract_recorded(allergy: dict[str, Any]) -> datetime | None:
    for key in ("recordedDate", "onsetDateTime"):
        v = allergy.get(key)
        if v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def _allergy_ref(allergy: dict[str, Any], source_label: str, idx: int) -> str:
    if rid := allergy.get("id"):
        return f"AllergyIntolerance/{rid}"
    slug = source_label.lower().replace(" ", "-")
    return f"AllergyIntolerance/{slug}-{idx}"


def merge_allergies(sources: Iterable[SourceBundle]) -> list[MergedAllergy]:
    by_key: dict[str, MergedAllergy] = {}
    name_to_key: dict[str, str] = {}
    now = datetime.now()

    for bundle in sources:
        for idx, allergy in enumerate(bundle.observations):
            if allergy.get("resourceType") != "AllergyIntolerance":
                continue
            snomed, rxnorm = _extract_codes(allergy)
            name = _extract_name(allergy)
            norm = _normalize_name(name)

            if snomed:
                key = f"snomed:{snomed}"
                activity = "snomed-match"
            elif rxnorm:
                key = f"rxnorm:{rxnorm}"
                activity = "rxnorm-match"
            else:
                if not norm:
                    continue
                if norm in name_to_key:
                    key = name_to_key[norm]
                    activity = "name-bridge"
                else:
                    key = f"name:{norm}"
                    activity = "name-match"

            if norm and key not in (f"name:{norm}",) and norm not in name_to_key:
                name_to_key[norm] = key

            ref = _allergy_ref(allergy, bundle.label, idx)
            source = AllergySource(
                source_label=bundle.label,
                source_allergy_ref=ref,
                display=name,
                snomed=snomed,
                rxnorm=rxnorm,
                criticality=_extract_criticality(allergy),
                clinical_status=_extract_clinical_status(allergy),
                recorded_date=_extract_recorded(allergy),
                document_reference=bundle.document_reference,
            )

            merged = by_key.get(key)
            if merged is None:
                target_ref = (
                    f"AllergyIntolerance/merged-snomed-{snomed}"
                    if snomed
                    else f"AllergyIntolerance/merged-rxnorm-{rxnorm}"
                    if rxnorm
                    else f"AllergyIntolerance/merged-{_normalize_name(name).replace(' ', '-')}"
                )
                merged = MergedAllergy(
                    canonical_name=name or snomed or rxnorm or "?",
                    snomed=snomed,
                    rxnorm=rxnorm,
                )
                merged._merged_ref = target_ref  # type: ignore[attr-defined]
                by_key[key] = merged
            else:
                if snomed and not merged.snomed:
                    merged.snomed = snomed
                if rxnorm and not merged.rxnorm:
                    merged.rxnorm = rxnorm

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

    def _sort_key(s: AllergySource) -> float:
        d = s.recorded_date
        if d is None:
            return float("-inf")
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()

    for m in by_key.values():
        m.sources.sort(key=_sort_key)
    return sorted(by_key.values(), key=lambda m: m.canonical_name.lower())
