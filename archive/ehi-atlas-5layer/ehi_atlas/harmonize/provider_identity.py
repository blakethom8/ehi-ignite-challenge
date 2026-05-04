"""Provider identity resolution for Layer 3 harmonization.

Cross-source Practitioner linkage. Phase 1: NPI exact match (primary) + name
similarity fallback (secondary). Phase 2: NPPES API enrichment.

Mirrors the shape of patient identity (`ehi_atlas.harmonize.identity`) but
anchored on NPI rather than name+DOB+address.

NPI (National Provider Identifier) is the universal 10-digit identifier issued
by CMS to every provider in the US. When both sides have an NPI:
- equal NPIs → same person (decision = "match")
- different NPIs → different people (decision = "non-match")

When NPI is absent from one or both sides (common in older C-CDA, free-text
extracted notes), we fall back to Jaro-Winkler name similarity + Jaccard
specialty overlap.

Phase 2 (not implemented here): NPPES API enrichment to canonicalize name,
gender, taxonomy code, and primary practice address for each resolved provider.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Literal

# Re-use Jaro-Winkler from patient identity (no duplication)
from ehi_atlas.harmonize.identity import _jaro_winkler


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# NPPES NPI system URI — the canonical identifier for US providers
NPI_SYSTEM = "http://hl7.org/fhir/sid/us-npi"

# Pattern for a bare 10-digit NPI (all digits, length 10)
_NPI_PATTERN = re.compile(r"^\d{10}$")


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderFingerprint:
    """What we know about a provider at one source."""

    source: str
    local_practitioner_id: str        # Practitioner.id at the source
    npi: str | None                   # if Practitioner.identifier with NPI_SYSTEM is present
    family_name: str | None
    given_names: tuple[str, ...]
    specialty_codes: tuple[str, ...]  # taxonomy / SNOMED specialty codings
    organization: str | None          # primary affiliation (Phase 1: from extension only)


def fingerprint_from_practitioner_resource(
    source: str, practitioner: dict
) -> ProviderFingerprint:
    """Extract a fingerprint from a FHIR Practitioner resource.

    NPI: walk identifier[] for system==NPI_SYSTEM (preferred), then any system
         containing "us-npi", then any value matching the 10-digit NPI pattern.
    Names: Practitioner.name[0]; given as tuple, family as str.
    Specialty codes: Practitioner.qualification[].code.coding[*].code.
    Organization: not on Practitioner directly — usually on PractitionerRole or
                  derived from affiliated Encounter.serviceProvider. For Phase 1
                  pull from Practitioner.extension if present, otherwise None.
    """
    # --- NPI ---------------------------------------------------------------
    identifiers = practitioner.get("identifier") or []
    npi: str | None = None

    for ident in identifiers:
        sys = ident.get("system") or ""
        val = ident.get("value") or ""
        if sys == NPI_SYSTEM:
            npi = val.strip() or None
            break

    if npi is None:
        for ident in identifiers:
            sys = (ident.get("system") or "").lower()
            val = ident.get("value") or ""
            if "us-npi" in sys:
                npi = val.strip() or None
                break

    if npi is None:
        for ident in identifiers:
            val = (ident.get("value") or "").strip()
            if _NPI_PATTERN.match(val):
                npi = val
                break

    # --- Name --------------------------------------------------------------
    names = practitioner.get("name") or []
    family_name: str | None = None
    given_names: tuple[str, ...] = ()
    if names:
        name0 = names[0]
        family_name = name0.get("family") or None
        given_raw = name0.get("given") or []
        given_names = tuple(g for g in given_raw if g)

    # --- Specialty codes from qualification --------------------------------
    qualifications = practitioner.get("qualification") or []
    codes: list[str] = []
    for qual in qualifications:
        for coding in (qual.get("code") or {}).get("coding") or []:
            code = coding.get("code") or ""
            if code:
                codes.append(code)
    specialty_codes = tuple(codes)

    # --- Organization: Phase 1 pulls from extension only ------------------
    organization: str | None = None
    for ext in practitioner.get("extension") or []:
        url = ext.get("url") or ""
        if "organization" in url.lower() or "affiliation" in url.lower():
            organization = (
                ext.get("valueString")
                or (ext.get("valueReference") or {}).get("display")
                or None
            )
            if organization:
                break

    return ProviderFingerprint(
        source=source,
        local_practitioner_id=practitioner.get("id") or "",
        npi=npi,
        family_name=family_name,
        given_names=given_names,
        specialty_codes=specialty_codes,
        organization=organization,
    )


# ---------------------------------------------------------------------------
# Match scoring
# ---------------------------------------------------------------------------


def _full_name(fp: ProviderFingerprint) -> str:
    """Produce a single normalized full-name string for Jaro-Winkler comparison."""
    parts = list(fp.given_names) + ([fp.family_name] if fp.family_name else [])
    return " ".join(p.strip().upper() for p in parts if p)


def _jaccard_specialty(a: ProviderFingerprint, b: ProviderFingerprint) -> float:
    """Jaccard similarity of specialty code sets.

    Both empty → 0.0 (no useful signal either way; treat as non-overlapping).
    One empty → 0.0.
    """
    sa = set(a.specialty_codes)
    sb = set(b.specialty_codes)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


@dataclass(frozen=True)
class ProviderMatchScore:
    npi_match: bool                # True only when both have NPIs and they're equal
    name_similarity: float         # 0..1 Jaro-Winkler on full name
    specialty_overlap: float       # 0..1 Jaccard on specialty codes
    decision: Literal["match", "possible-match", "non-match"]


# Decision thresholds
NAME_THRESHOLD = 0.90   # high bar for fallback matching


def score_providers(a: ProviderFingerprint, b: ProviderFingerprint) -> ProviderMatchScore:
    """Score two fingerprints.

    Logic:
    - If both NPIs present and equal → npi_match=True, decision="match" (always)
    - If NPIs present but DIFFERENT → decision="non-match" (different people, period)
    - If neither has NPI (or one missing): rely on name + specialty:
        - name_similarity ≥ NAME_THRESHOLD AND specialty_overlap > 0 → "match"
        - name_similarity ≥ 0.75 → "possible-match"
        - else → "non-match"
    """
    # Compute name and specialty scores regardless (for the score object)
    name_a = _full_name(a)
    name_b = _full_name(b)
    if name_a and name_b:
        name_sim = _jaro_winkler(name_a, name_b)
    elif not name_a and not name_b:
        name_sim = 0.5  # both unknown — uninformative
    else:
        name_sim = 0.0

    spec_overlap = _jaccard_specialty(a, b)

    # NPI decision branch
    if a.npi is not None and b.npi is not None:
        if a.npi == b.npi:
            return ProviderMatchScore(
                npi_match=True,
                name_similarity=name_sim,
                specialty_overlap=spec_overlap,
                decision="match",
            )
        else:
            return ProviderMatchScore(
                npi_match=False,
                name_similarity=name_sim,
                specialty_overlap=spec_overlap,
                decision="non-match",
            )

    # Fallback: name + specialty
    npi_match = False
    if name_sim >= NAME_THRESHOLD and spec_overlap > 0:
        decision: Literal["match", "possible-match", "non-match"] = "match"
    elif name_sim >= 0.75:
        decision = "possible-match"
    else:
        decision = "non-match"

    return ProviderMatchScore(
        npi_match=npi_match,
        name_similarity=name_sim,
        specialty_overlap=spec_overlap,
        decision=decision,
    )


# ---------------------------------------------------------------------------
# Connected components (reused shape from identity.py)
# ---------------------------------------------------------------------------


def _connected_components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Union-Find connected components over node indices 0..n-1."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for u, v in edges:
        union(u, v)

    from collections import defaultdict

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Identity index
# ---------------------------------------------------------------------------


@dataclass
class CanonicalProvider:
    canonical_id: str
    fingerprints: list[ProviderFingerprint]
    fhir_resource: dict          # the merged Practitioner resource


@dataclass
class ProviderIdentityIndex:
    """Maps source-local Practitioner.ids to canonical provider_ids."""

    canonical_providers: dict[str, CanonicalProvider]
    source_to_canonical: dict[tuple[str, str], str]  # (source, local_id) → canonical_id

    def resolve(self, source: str, local_practitioner_id: str) -> str | None:
        """Return the canonical_id for (source, local_practitioner_id), or None."""
        return self.source_to_canonical.get((source, local_practitioner_id))


def _canonical_id_from_fingerprints(fps: list[ProviderFingerprint]) -> str:
    """Derive a canonical ID from a cluster of fingerprints.

    Strategy:
    1. If any fingerprint has an NPI: family-name-slug + last-3-of-NPI
    2. Else: family-name-slug from the most-complete fingerprint
    3. Fallback: "provider-<hash-of-local-ids>"
    """
    # Find a fingerprint with NPI
    npi_fp = next((fp for fp in fps if fp.npi), None)
    if npi_fp and npi_fp.family_name:
        slug = re.sub(r"\d+$", "", npi_fp.family_name.lower().replace(" ", "-")) or "provider"
        npi_tail = npi_fp.npi[-3:]  # type: ignore[index]
        return f"{slug}-{npi_tail}"
    if npi_fp and npi_fp.npi:
        return f"provider-npi{npi_fp.npi[-3:]}"

    # Best name from most-complete fingerprint
    def _completeness(fp: ProviderFingerprint) -> int:
        score = 0
        if fp.family_name:
            score += 2
        if fp.given_names:
            score += 2
        if fp.npi:
            score += 3
        if fp.specialty_codes:
            score += 1
        return score

    base = max(fps, key=_completeness)
    if base.family_name:
        slug = re.sub(r"\d+$", "", base.family_name.lower().replace(" ", "-")) or "provider"
        return slug

    # Final fallback
    h = hashlib.md5(
        "".join(fp.local_practitioner_id for fp in fps).encode()
    ).hexdigest()[:8]
    return f"provider-{h}"


def build_provider_identity_index(
    fingerprints: list[ProviderFingerprint],
    *,
    canonical_id_for: dict[str, str] | None = None,
) -> ProviderIdentityIndex:
    """Cluster fingerprints into canonical providers.

    Algorithm (mirrors patient identity):
    1. Compute score for every pair
    2. Connected components on (match | possible-match) edges
    3. Each component → one canonical provider
    4. canonical_id naming:
       - canonical_id_for[fingerprint.local_id] if provided
       - else family-name + last-3-of-NPI (if NPI present)
       - fallback: "provider-<hash-of-cluster>"
    5. Merged Practitioner: most-complete fingerprint as base + all NPIs/source-ids
       preserved as Practitioner.identifier[]
    """
    n = len(fingerprints)
    if n == 0:
        return ProviderIdentityIndex(canonical_providers={}, source_to_canonical={})

    # Step 1 + 2: score all pairs, collect match edges
    edges: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            s = score_providers(fingerprints[i], fingerprints[j])
            if s.decision in ("match", "possible-match"):
                edges.append((i, j))

    # Step 3: connected components
    components = _connected_components(n, edges)

    canonical_providers: dict[str, CanonicalProvider] = {}
    source_to_canonical: dict[tuple[str, str], str] = {}

    id_for = canonical_id_for or {}

    for component in components:
        fps = [fingerprints[i] for i in component]

        # Step 4: determine canonical_id
        canonical_id: str | None = None
        for fp in fps:
            if fp.local_practitioner_id in id_for:
                canonical_id = id_for[fp.local_practitioner_id]
                break

        if canonical_id is None:
            canonical_id = _canonical_id_from_fingerprints(fps)

        # Step 5: build merged resource (placeholder; filled immediately after)
        cp = CanonicalProvider(
            canonical_id=canonical_id,
            fingerprints=fps,
            fhir_resource={},
        )
        cp.fhir_resource = merged_practitioner_resource(cp)

        canonical_providers[canonical_id] = cp

        for fp in fps:
            source_to_canonical[(fp.source, fp.local_practitioner_id)] = canonical_id

    return ProviderIdentityIndex(
        canonical_providers=canonical_providers,
        source_to_canonical=source_to_canonical,
    )


def merged_practitioner_resource(canonical: CanonicalProvider) -> dict:
    """Emit gold-tier merged Practitioner.

    All source identifiers preserved, name[] union (deduplicated), qualification
    aggregated. meta.profile includes us-core-practitioner. meta.tag includes
    one source-tag per source + lifecycle=harmonized.
    """
    fps = canonical.fingerprints

    # Choose the "most complete" fingerprint as the base for demographics
    def _completeness(fp: ProviderFingerprint) -> int:
        s = 0
        if fp.family_name:
            s += 2
        if fp.given_names:
            s += 2
        if fp.npi:
            s += 3
        if fp.specialty_codes:
            s += 1
        if fp.organization:
            s += 1
        return s

    base = max(fps, key=_completeness)

    # Build identifier list — one NPI entry per unique NPI, plus one source-id
    # entry per source fingerprint so no provenance is lost.
    identifiers: list[dict] = []
    seen_npis: set[str] = set()

    for fp in fps:
        # NPI identifier (deduplicated by value)
        if fp.npi and fp.npi not in seen_npis:
            seen_npis.add(fp.npi)
            identifiers.append(
                {
                    "system": NPI_SYSTEM,
                    "value": fp.npi,
                    "use": "official",
                    "extension": [
                        {
                            "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-tag",
                            "valueString": fp.source,
                        }
                    ],
                }
            )

    # Source-local identifiers (always preserved, even if NPI was present)
    seen_local: set[tuple[str, str]] = set()
    for fp in fps:
        key = (fp.source, fp.local_practitioner_id)
        if key not in seen_local and fp.local_practitioner_id:
            seen_local.add(key)
            identifiers.append(
                {
                    "system": f"https://ehi-atlas.example/fhir/source/{fp.source}/Practitioner",
                    "value": fp.local_practitioner_id,
                    "use": "secondary",
                    "extension": [
                        {
                            "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-tag",
                            "valueString": fp.source,
                        }
                    ],
                }
            )

    # Name — deduplicated union from all fingerprints
    seen_names: set[tuple[str | None, tuple[str, ...]]] = set()
    name_list: list[dict] = []
    for fp in fps:
        name_key = (fp.family_name, fp.given_names)
        if name_key in seen_names:
            continue
        if not fp.family_name and not fp.given_names:
            continue
        seen_names.add(name_key)
        name_block: dict = {"use": "official"}
        if fp.family_name:
            name_block["family"] = fp.family_name
        if fp.given_names:
            name_block["given"] = list(fp.given_names)
        name_list.append(name_block)

    # Qualification — aggregate unique specialty codes
    seen_codes: set[str] = set()
    qualifications: list[dict] = []
    for fp in fps:
        for code in fp.specialty_codes:
            if code not in seen_codes:
                seen_codes.add(code)
                qualifications.append(
                    {
                        "code": {
                            "coding": [{"code": code}],
                        }
                    }
                )

    # Tags — one per contributing source + lifecycle=harmonized
    source_tags = [
        {
            "system": "https://ehi-atlas.example/fhir/CodeSystem/source-tag",
            "code": fp.source,
        }
        for fp in fps
    ]
    lifecycle_tag = {
        "system": "https://ehi-atlas.example/fhir/CodeSystem/lifecycle",
        "code": "harmonized",
    }

    resource: dict = {
        "resourceType": "Practitioner",
        "id": canonical.canonical_id,
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/core/StructureDefinition/us-core-practitioner"
            ],
            "source": "harmonizer://provider-identity-resolution",
            "tag": source_tags + [lifecycle_tag],
        },
        "identifier": identifiers,
        "name": name_list,
    }

    if qualifications:
        resource["qualification"] = qualifications

    if base.organization:
        resource["extension"] = [
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/primary-organization",
                "valueString": base.organization,
            }
        ]

    return resource
