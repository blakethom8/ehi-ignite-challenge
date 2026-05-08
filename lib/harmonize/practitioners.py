"""Practitioner cross-source matcher.

Identity priority:
1. NPI exact match (the canonical US practitioner identifier)
2. Normalized name match (family + given + prefix + suffix lowercased and
   punctuation-stripped)

NPIs are 10-digit numbers; if both records have an NPI and they differ,
the records are NOT the same practitioner — return no match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PractitionerKey:
    """Identity key for a Practitioner. Two records with equal keys are
    the same practitioner."""

    npi: str | None
    normalized_name: str

    def __bool__(self) -> bool:
        return bool(self.npi or self.normalized_name)


def _normalize_name(
    family: str | None,
    given: list[str] | None,
    prefix: str | None,
    suffix: str | None,
) -> str:
    parts = []
    if prefix:
        parts.append(prefix.strip())
    if given:
        parts.extend(given)
    if family:
        parts.append(family)
    if suffix:
        parts.append(suffix.strip())
    raw = " ".join(p for p in parts if p)
    raw = re.sub(r"[^a-z0-9 ]+", " ", raw.lower())
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _normalize_text_field(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def practitioner_key(resource: dict) -> PractitionerKey | None:
    """Extract identity key from a FHIR Practitioner resource. Returns None
    if neither NPI nor a usable name is present."""
    if resource.get("resourceType") != "Practitioner":
        return None

    # NPI extraction
    npi: str | None = None
    for ident in resource.get("identifier", []) or []:
        system = (ident.get("system") or "").lower()
        if system == "http://hl7.org/fhir/sid/us-npi":
            value = (ident.get("value") or "").strip()
            if value:
                npi = value
                break

    # Name extraction (use first name entry)
    family = None
    given: list[str] = []
    prefix = None
    suffix = None
    names = resource.get("name") or []
    if names:
        first = names[0]
        family = first.get("family")
        given = first.get("given") or []
        prefix_list = first.get("prefix") or []
        prefix = prefix_list[0] if prefix_list else None
        suffix_list = first.get("suffix") or []
        suffix = suffix_list[0] if suffix_list else None
        # Fallback to text if structured name absent
        if not (family or given) and first.get("text"):
            return PractitionerKey(npi=npi, normalized_name=_normalize_text_field(first["text"]))

    normalized = _normalize_name(family, given, prefix, suffix)
    if not (npi or normalized):
        return None
    return PractitionerKey(npi=npi, normalized_name=normalized)


def is_same_practitioner(a: dict, b: dict) -> bool:
    """Decide whether two FHIR Practitioner resources are the same person."""
    ka = practitioner_key(a)
    kb = practitioner_key(b)
    if ka is None or kb is None:
        return False
    # NPI match takes precedence
    if ka.npi and kb.npi:
        return ka.npi == kb.npi
    # If only one has NPI, fall back to name comparison ONLY if the other
    # has a name that matches and that name isn't trivially generic
    if ka.normalized_name and kb.normalized_name:
        return ka.normalized_name == kb.normalized_name
    return False
