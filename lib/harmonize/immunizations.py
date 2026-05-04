"""Cross-source Immunization matcher.

Different identity model than the other resource types: an Immunization
is an *event* (a specific shot administered on a specific date), not a
chronic state. So the match key is **(vaccine_code, occurrence_date)**,
not just vaccine_code. The same flu shot recorded by two sources (same
CVX, same date) collapses onto one merged record. Two flu shots in
different years (same CVX, different dates) stay as two separate
merged records — and that's the right clinical model.

Identity priority:
1. **(CVX, date)** — both sources share a CDC vaccine code and
   occurrence date.
2. **(canonical_name, date)** — text-only sources, normalized name.
3. **(name, date)** passthrough — last resort, raw text + date.

Date is bucketed at YYYY-MM-DD precision (different times same day
still collapse — clinical reality is rarely that precise).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import ImmunizationSource, MergedImmunization, ProvenanceEdge
from .observations import SourceBundle


_CVX_FRAGS = ("cdc.gov/cvx", "/cvx", "hl7.org/fhir/sid/cvx")
_NDC_FRAGS = ("hl7.org/fhir/sid/ndc",)


def _extract_codes(im: dict[str, Any]) -> tuple[str | None, str | None]:
    cvx = ndc = None
    for c in im.get("vaccineCode", {}).get("coding", []):
        sys_ = c.get("system", "").lower()
        code = c.get("code")
        if not code:
            continue
        if any(f in sys_ for f in _CVX_FRAGS) or sys_.endswith("cvx"):
            cvx = cvx or code
        elif any(f in sys_ for f in _NDC_FRAGS):
            ndc = ndc or code
    return cvx, ndc


def _extract_name(im: dict[str, Any]) -> str:
    code = im.get("vaccineCode", {})
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


def _extract_date(im: dict[str, Any]) -> datetime | None:
    raw = im.get("occurrenceDateTime") or im.get("occurrenceString")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _date_bucket(d: datetime | None) -> str:
    return d.date().isoformat() if d else "unknown-date"


def _im_ref(im: dict[str, Any], source_label: str, idx: int) -> str:
    if rid := im.get("id"):
        return f"Immunization/{rid}"
    slug = source_label.lower().replace(" ", "-")
    return f"Immunization/{slug}-{idx}"


def merge_immunizations(sources: Iterable[SourceBundle]) -> list[MergedImmunization]:
    by_key: dict[str, MergedImmunization] = {}
    # name@date → primary key, so a text-only source can attach to an
    # existing CVX-keyed record when the display text matches.
    name_date_to_key: dict[str, str] = {}
    now = datetime.now()

    for bundle in sources:
        for idx, im in enumerate(bundle.observations):
            if im.get("resourceType") != "Immunization":
                continue
            cvx, ndc = _extract_codes(im)
            name = _extract_name(im)
            date_dt = _extract_date(im)
            date_bucket = _date_bucket(date_dt)
            norm = _normalize_name(name)
            name_date_index = f"{norm}@{date_bucket}"

            if cvx:
                key = f"cvx:{cvx}@{date_bucket}"
                activity = "cvx-match"
            elif norm and name_date_index in name_date_to_key:
                key = name_date_to_key[name_date_index]
                activity = "name-bridge"
            elif norm:
                key = f"name:{norm}@{date_bucket}"
                activity = "name-match"
            else:
                continue

            # Register name@date → key so future text-only sources with
            # a matching display + date can bridge onto this record.
            if norm and name_date_index not in name_date_to_key:
                name_date_to_key[name_date_index] = key

            ref = _im_ref(im, bundle.label, idx)
            source = ImmunizationSource(
                source_label=bundle.label,
                source_immunization_ref=ref,
                display=name,
                cvx=cvx,
                ndc=ndc,
                occurrence_date=date_dt,
                status=im.get("status"),
                document_reference=bundle.document_reference,
            )

            merged = by_key.get(key)
            if merged is None:
                target_ref = (
                    f"Immunization/merged-cvx-{cvx}-{date_bucket}"
                    if cvx
                    else f"Immunization/merged-{norm.replace(' ', '-')}-{date_bucket}"
                )
                merged = MergedImmunization(
                    canonical_name=name,
                    cvx=cvx,
                    ndc=ndc,
                    occurrence_date=date_dt,
                )
                merged._merged_ref = target_ref  # type: ignore[attr-defined]
                by_key[key] = merged
            else:
                if cvx and not merged.cvx:
                    merged.cvx = cvx
                if ndc and not merged.ndc:
                    merged.ndc = ndc

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

    # Chronological by occurrence_date, oldest first.
    def _sort_key(m: MergedImmunization) -> float:
        d = m.occurrence_date
        if d is None:
            return float("-inf")
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()

    return sorted(by_key.values(), key=_sort_key)
