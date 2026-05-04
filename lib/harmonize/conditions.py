"""Cross-source Condition matcher.

Same architecture as ``observations.py`` — takes per-source FHIR Condition
lists and produces ``MergedCondition`` records. Identity resolution
strategies (in priority order):

1. **SNOMED code match** — both sources share a SNOMED CT code.
2. **ICD-10 code match** — both sources share an ICD-10-CM code (or
   ICD-9-CM for legacy data).
3. **Name match (normalized)** — when codes don't overlap or are missing,
   fall back to lowercased / punctuation-stripped display text.

We don't bridge SNOMED ↔ ICD-10 in v1. That's a UMLS-grade undertaking
and the marginal value is low: most US clinical sources emit both codes
side-by-side (Cedars's FHIR pull stamps SNOMED + ICD-9 + ICD-10 on every
Condition), so a SNOMED-only source and an ICD-10-only source merging
is rare in practice. When the gap matters, the name-match fallback
catches the obvious cases ("Allergic rhinitis" stays "Allergic rhinitis"
across coding systems).

Repeated occurrences of the same condition across encounters / sources
collapse onto a single ``MergedCondition`` — the longitudinal source
list captures the timeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import MergedCondition, ConditionSource, ProvenanceEdge
from .observations import SourceBundle  # reuse the source-bundle type


_SNOMED_SYSTEM_FRAGMENTS = ("snomed.info/sct",)
_ICD10_SYSTEM_FRAGMENTS = ("icd-10", "icd10")
_ICD9_SYSTEM_FRAGMENTS = ("icd-9", "icd9")


def _extract_codes(cond: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Pull (snomed, icd10, icd9) codes from a Condition's ``code.coding`` array."""
    snomed = icd10 = icd9 = None
    for c in cond.get("code", {}).get("coding", []):
        sys_ = c.get("system", "").lower()
        code = c.get("code")
        if not code:
            continue
        if any(f in sys_ for f in _SNOMED_SYSTEM_FRAGMENTS):
            snomed = snomed or code
        elif any(f in sys_ for f in _ICD10_SYSTEM_FRAGMENTS):
            icd10 = icd10 or code
        elif any(f in sys_ for f in _ICD9_SYSTEM_FRAGMENTS):
            icd9 = icd9 or code
    return snomed, icd10, icd9


def _extract_name(cond: dict[str, Any]) -> str:
    code = cond.get("code", {})
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


def _extract_clinical_status(cond: dict[str, Any]) -> str | None:
    cs = cond.get("clinicalStatus") or {}
    for c in cs.get("coding", []):
        if code := c.get("code"):
            return code
    return None


def _extract_onset(cond: dict[str, Any]) -> datetime | None:
    for key in ("onsetDateTime", "recordedDate"):
        v = cond.get(key)
        if v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
    period = cond.get("onsetPeriod") or {}
    if start := period.get("start"):
        try:
            return datetime.fromisoformat(start.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def _cond_ref(cond: dict[str, Any], source_label: str, idx: int) -> str:
    if rid := cond.get("id"):
        return f"Condition/{rid}"
    slug = source_label.lower().replace(" ", "-")
    return f"Condition/{slug}-{idx}"


def merge_conditions(sources: Iterable[SourceBundle]) -> list[MergedCondition]:
    """Merge Conditions across sources into canonical ``MergedCondition`` records.

    The ``SourceBundle.observations`` field is reused as the resource list
    (it carries any FHIR resource type — the Condition matcher just expects
    Conditions). Use the same ``SourceBundle`` shape that
    ``merge_observations`` consumes; pass Conditions instead of
    Observations.
    """
    by_key: dict[str, MergedCondition] = {}
    name_to_key: dict[str, str] = {}  # normalized display → primary key
    now = datetime.now()

    for bundle in sources:
        for idx, cond in enumerate(bundle.observations):
            if cond.get("resourceType") != "Condition":
                continue
            snomed, icd10, icd9 = _extract_codes(cond)
            name = _extract_name(cond)
            norm = _normalize_name(name)

            # Pick the strongest identity available for this Condition.
            # When the source has a code (SNOMED/ICD), we key on it.
            # When the source is text-only, we first try to attach to an
            # existing coded record whose display text matches — this is
            # the bridge between LOINC-coded sources (Cedars FHIR) and
            # vision-extracted PDFs (text-only).
            if snomed:
                key = f"snomed:{snomed}"
                activity = "snomed-match"
            elif icd10:
                key = f"icd10:{icd10}"
                activity = "icd10-match"
            elif icd9:
                key = f"icd9:{icd9}"
                activity = "icd9-match"
            else:
                if not norm:
                    continue
                # Try to bind onto an already-merged coded record by display text.
                if norm in name_to_key:
                    key = name_to_key[norm]
                    activity = "name-bridge"
                else:
                    key = f"name:{norm}"
                    activity = "name-match"

            ref = _cond_ref(cond, bundle.label, idx)
            source = ConditionSource(
                source_label=bundle.label,
                source_condition_ref=ref,
                display=name,
                snomed=snomed,
                icd10=icd10,
                icd9=icd9,
                clinical_status=_extract_clinical_status(cond),
                onset_date=_extract_onset(cond),
                document_reference=bundle.document_reference,
            )

            # Register the normalized display text against the primary
            # key so later text-only sources can bind here.
            if norm and key not in (f"name:{norm}",) and norm not in name_to_key:
                name_to_key[norm] = key

            merged = by_key.get(key)
            if merged is None:
                target_ref = (
                    f"Condition/merged-snomed-{snomed}"
                    if snomed
                    else f"Condition/merged-icd10-{icd10}"
                    if icd10
                    else f"Condition/merged-icd9-{icd9}"
                    if icd9
                    else f"Condition/merged-{_normalize_name(name).replace(' ', '-')}"
                )
                merged = MergedCondition(
                    canonical_name=name or snomed or icd10 or icd9 or "?",
                    snomed=snomed,
                    icd10=icd10,
                    icd9=icd9,
                )
                merged._merged_ref = target_ref  # type: ignore[attr-defined]
                by_key[key] = merged
            else:
                # If a later source has a code the merged record doesn't yet,
                # promote it. Helps when one source is SNOMED-only and the
                # other contributes ICD-10.
                if snomed and not merged.snomed:
                    merged.snomed = snomed
                if icd10 and not merged.icd10:
                    merged.icd10 = icd10
                if icd9 and not merged.icd9:
                    merged.icd9 = icd9

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

    # Chronological ordering within each merged record (oldest onset first),
    # naive/aware-safe.
    def _sort_key(s: ConditionSource) -> float:
        d = s.onset_date
        if d is None:
            return float("-inf")
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()

    for m in by_key.values():
        m.sources.sort(key=_sort_key)
    return sorted(by_key.values(), key=lambda m: m.canonical_name.lower())
