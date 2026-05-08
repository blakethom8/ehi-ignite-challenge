"""Organization cross-source matcher.

Identity priority:
1. Identifier match (when both have a system+value pair that matches)
2. Normalized (name, city, state) tuple match — names are lowercased,
   punctuation-stripped, and common suffixes ("Inc", "LLC", "MD",
   "Health System") are kept (they're often signal, not noise — "Cedars-
   Sinai Health System" vs "Cedars-Sinai Hospital" should NOT collide).

Conservative: when name matches but city/state differ, treat as
different organizations (a chain may have many locations with the same
name).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class OrganizationKey:
    identifier_system: str | None
    identifier_value: str | None
    normalized_name: str
    city: str | None
    state: str | None

    def __bool__(self) -> bool:
        return bool(self.identifier_value or self.normalized_name)


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    n = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _normalize_locality(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().upper()


def organization_key(resource: dict) -> OrganizationKey | None:
    if resource.get("resourceType") != "Organization":
        return None
    name = resource.get("name")
    if not name:
        return None
    normalized = _normalize_name(name)
    if not normalized:
        return None

    # First identifier with a system+value pair
    ident_system: str | None = None
    ident_value: str | None = None
    for ident in resource.get("identifier", []) or []:
        v = ident.get("value")
        if v:
            ident_value = v
            ident_system = ident.get("system")
            break

    addresses = resource.get("address") or []
    city = state = None
    if addresses:
        first = addresses[0]
        city = _normalize_locality(first.get("city"))
        state = _normalize_locality(first.get("state"))

    return OrganizationKey(
        identifier_system=ident_system,
        identifier_value=ident_value,
        normalized_name=normalized,
        city=city,
        state=state,
    )


def is_same_organization(a: dict, b: dict) -> bool:
    ka = organization_key(a)
    kb = organization_key(b)
    if ka is None or kb is None:
        return False
    # Identifier match takes precedence
    if ka.identifier_value and kb.identifier_value:
        if ka.identifier_value == kb.identifier_value and (
            ka.identifier_system == kb.identifier_system or not (ka.identifier_system and kb.identifier_system)
        ):
            return True
        # If both have identifiers but they differ, no match
        return False
    # Name + city + state match (all three must align if we have them)
    if ka.normalized_name != kb.normalized_name:
        return False
    # Same name. If either lacks city/state info, accept the name match.
    if ka.city is None or kb.city is None:
        return True
    if ka.city != kb.city:
        return False
    if ka.state is None or kb.state is None:
        return True
    return ka.state == kb.state
