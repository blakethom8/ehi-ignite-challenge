"""Patient identity resolution for Layer 3 harmonization.

Cross-source linkage using Fellegi-Sunter probabilistic record linkage.
Inputs: silver-tier Patient resources from N sources.
Output: a canonical Patient resource per logical person, with all source
MRNs preserved as identifiers; plus a PatientIdentityIndex mapping each
source's local Patient.id → canonical patient_id.

Phase 1 simplification: the showcase patient is constructed to be
identifiable across sources (same name, same DOB). Fellegi-Sunter still
runs end-to-end for architectural correctness. Phase 2 expansion: PPRL,
provider identity (3.2), and the cross-organizational hard cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientFingerprint:
    """The Fellegi-Sunter input — what we know about a patient at one source."""

    source: str
    local_patient_id: str  # the Patient.id at that source
    family_name: str | None
    given_names: tuple[str, ...]  # tuple for hashability
    birth_date: str | None  # ISO 8601 YYYY-MM-DD
    gender: str | None  # FHIR AdministrativeGender
    address_zip: str | None
    mrn_value: str | None  # primary identifier value at the source
    mrn_system: str | None  # primary identifier system


def fingerprint_from_patient_resource(source: str, patient: dict) -> PatientFingerprint:
    """Extract a fingerprint from a FHIR Patient resource.

    Naming: take Patient.name[0] if present, with given joined as tuple, family as str.
    Birth: use Patient.birthDate (YYYY-MM-DD).
    Gender: Patient.gender.
    Address: take address[0].postalCode if present.
    MRN: walk identifier[] for the first one with use=usual or with system containing
         "mrn" or matching common Epic/Cerner patterns; fallback to identifier[0].
    """
    # --- Name -----------------------------------------------------------
    names = patient.get("name") or []
    family_name: str | None = None
    given_names: tuple[str, ...] = ()
    if names:
        name0 = names[0]
        family_name = name0.get("family") or None
        given_raw = name0.get("given") or []
        given_names = tuple(g for g in given_raw if g)

    # --- Birth date + gender -------------------------------------------
    birth_date: str | None = patient.get("birthDate") or None
    gender: str | None = patient.get("gender") or None

    # --- Address zip ----------------------------------------------------
    addresses = patient.get("address") or []
    address_zip: str | None = None
    if addresses:
        address_zip = addresses[0].get("postalCode") or None

    # --- MRN identifier ------------------------------------------------
    identifiers = patient.get("identifier") or []

    def _is_mrn(ident: dict) -> bool:
        if ident.get("use") == "usual":
            return True
        sys = (ident.get("system") or "").lower()
        type_codings = (ident.get("type") or {}).get("coding") or []
        for c in type_codings:
            code = (c.get("code") or "").upper()
            if code == "MR":
                return True
        if "mrn" in sys or "medical-record" in sys or "smarthealthit" in sys:
            return True
        return False

    mrn_ident: dict | None = None
    for ident in identifiers:
        if _is_mrn(ident):
            mrn_ident = ident
            break
    if mrn_ident is None and identifiers:
        mrn_ident = identifiers[0]

    mrn_value: str | None = None
    mrn_system: str | None = None
    if mrn_ident:
        mrn_value = mrn_ident.get("value") or None
        mrn_system = mrn_ident.get("system") or None

    return PatientFingerprint(
        source=source,
        local_patient_id=patient.get("id") or "",
        family_name=family_name,
        given_names=given_names,
        birth_date=birth_date,
        gender=gender,
        address_zip=address_zip,
        mrn_value=mrn_value,
        mrn_system=mrn_system,
    )


# ---------------------------------------------------------------------------
# Jaro-Winkler (inline, no external deps)
# ---------------------------------------------------------------------------


def _jaro(s1: str, s2: str) -> float:
    """Jaro similarity in [0.0, 1.0]."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    match_dist = max(len1, len2) // 2 - 1
    if match_dist < 0:
        match_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        lo = max(0, i - match_dist)
        hi = min(i + match_dist + 1, len2)
        for j in range(lo, hi):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3


def _jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    """Jaro-Winkler similarity in [0.0, 1.0].

    p is the scaling factor for common prefix (standard value 0.1).
    """
    jaro = _jaro(s1, s2)
    # Common prefix length capped at 4
    prefix = 0
    for c1, c2 in zip(s1[:4], s2[:4]):
        if c1 == c2:
            prefix += 1
        else:
            break
    return jaro + prefix * p * (1 - jaro)


def _normalize_name(s: str) -> str:
    """Uppercase, strip whitespace."""
    return s.strip().upper()


# ---------------------------------------------------------------------------
# Fellegi-Sunter scorers
# ---------------------------------------------------------------------------


def name_similarity(a: PatientFingerprint, b: PatientFingerprint) -> float:
    """Combined family + given name similarity in [0.0, 1.0].

    Family name: Jaro-Winkler.
    Given names: best-pair Jaro-Winkler over all (a.given × b.given) pairs.
    Weights: family 0.6, given 0.4.
    Either side completely missing → 0.5 (uninformative).
    """
    # --- Family name ---
    if a.family_name and b.family_name:
        family_score = _jaro_winkler(
            _normalize_name(a.family_name),
            _normalize_name(b.family_name),
        )
    elif a.family_name is None and b.family_name is None:
        family_score = 0.5
    else:
        family_score = 0.0

    # --- Given names ---
    if a.given_names and b.given_names:
        best = 0.0
        for ga in a.given_names:
            for gb in b.given_names:
                sim = _jaro_winkler(_normalize_name(ga), _normalize_name(gb))
                if sim > best:
                    best = sim
        given_score = best
    elif not a.given_names and not b.given_names:
        given_score = 0.5
    else:
        # one side has given names, the other doesn't → slightly uninformative
        given_score = 0.4

    return 0.6 * family_score + 0.4 * given_score


def dob_match(a: PatientFingerprint, b: PatientFingerprint) -> float:
    """1.0 if exact match, 0.7 if same year+month, 0.3 if same year, 0.0 otherwise.
    Either side missing → 0.5 (uninformative).
    """
    if a.birth_date is None or b.birth_date is None:
        return 0.5

    # Parse YYYY-MM-DD (be permissive with partial dates)
    da = a.birth_date.strip()
    db = b.birth_date.strip()

    if da == db:
        return 1.0

    parts_a = da.split("-")
    parts_b = db.split("-")

    year_a = parts_a[0] if parts_a else None
    year_b = parts_b[0] if parts_b else None
    month_a = parts_a[1] if len(parts_a) > 1 else None
    month_b = parts_b[1] if len(parts_b) > 1 else None

    if year_a != year_b:
        return 0.0
    # same year
    if month_a is None or month_b is None:
        return 0.3
    if month_a == month_b:
        return 0.7
    return 0.3


def address_match(a: PatientFingerprint, b: PatientFingerprint) -> float:
    """1.0 if both ZIPs present and equal, 0.5 if missing on either side, 0.0 if differ."""
    if a.address_zip is None or b.address_zip is None:
        return 0.5
    return 1.0 if a.address_zip.strip() == b.address_zip.strip() else 0.0


def gender_match(a: PatientFingerprint, b: PatientFingerprint) -> float:
    """1.0 exact, 0.5 if either missing, 0.0 if differ."""
    if a.gender is None or b.gender is None:
        return 0.5
    return 1.0 if a.gender.lower() == b.gender.lower() else 0.0


# ---------------------------------------------------------------------------
# Aggregate match score
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchScore:
    name: float
    dob: float
    address: float
    gender: float
    aggregate: float
    decision: Literal["match", "possible-match", "non-match"]


# Tunable thresholds (Phase 1 — adjust if showcase merges fail)
MATCH_THRESHOLD = 0.85
POSSIBLE_MATCH_THRESHOLD = 0.6


def score(a: PatientFingerprint, b: PatientFingerprint) -> MatchScore:
    """Fellegi-Sunter weighted aggregate.

    Weights: name 0.5, dob 0.3, address 0.1, gender 0.1.
    """
    n = name_similarity(a, b)
    d = dob_match(a, b)
    addr = address_match(a, b)
    g = gender_match(a, b)
    agg = 0.5 * n + 0.3 * d + 0.1 * addr + 0.1 * g

    if agg >= MATCH_THRESHOLD:
        decision: Literal["match", "possible-match", "non-match"] = "match"
    elif agg >= POSSIBLE_MATCH_THRESHOLD:
        decision = "possible-match"
    else:
        decision = "non-match"

    return MatchScore(name=n, dob=d, address=addr, gender=g, aggregate=agg, decision=decision)


# ---------------------------------------------------------------------------
# Identity index
# ---------------------------------------------------------------------------


@dataclass
class CanonicalPatient:
    """The merged identity. Carries all source identifiers."""

    canonical_id: str  # human-readable handle (e.g. "rhett759")
    fingerprints: list[PatientFingerprint]  # one per contributing source
    fhir_resource: dict  # the merged FHIR Patient resource (with all identifiers)


@dataclass
class PatientIdentityIndex:
    """Maps source-local Patient.ids to canonical patient_ids.

    The canonical patient_id is human-readable (e.g. "rhett759"). The index
    is built once from a list of fingerprints and then queried.
    """

    canonical_patients: dict[str, CanonicalPatient]  # canonical_id → record
    source_to_canonical: dict[tuple[str, str], str]  # (source, local_id) → canonical_id

    def resolve(self, source: str, local_patient_id: str) -> str | None:
        """Return the canonical_id for this (source, local_patient_id) pair, or None."""
        return self.source_to_canonical.get((source, local_patient_id))


def _canonical_id_from_fingerprint(fp: PatientFingerprint) -> str:
    """Derive a human-readable canonical ID from a fingerprint."""
    name_part = (fp.family_name or "patient").lower().replace(" ", "-")
    # Strip any numeric suffixes Synthea appends (e.g. "Rohan584" → "rohan")
    import re

    name_part = re.sub(r"\d+$", "", name_part) or "patient"
    dob_part = ""
    if fp.birth_date:
        parts = fp.birth_date.split("-")
        if len(parts) >= 3:
            dob_part = parts[2]  # day
        elif len(parts) == 2:
            dob_part = parts[1]
    if dob_part:
        return f"{name_part}{dob_part}"
    return name_part


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


def build_identity_index(
    fingerprints: list[PatientFingerprint],
    *,
    canonical_id_for: dict[str, str] | None = None,
) -> PatientIdentityIndex:
    """Run Fellegi-Sunter pairwise across fingerprints, cluster into canonical patients.

    Algorithm:
    1. Score every pair of fingerprints.
    2. Connected components: any pair with score.decision in {"match", "possible-match"}
       is connected; "non-match" pairs are not.
    3. Each connected component → one canonical patient.
    4. canonical_id naming:
       - if `canonical_id_for[fingerprint.local_patient_id]` is set, use that
       - else use the first fingerprint's family_name.lower() + last 3 of birth_date
       - fallback: "patient-<hash>"
    5. Build the merged FHIR Patient resource: take the most-complete fingerprint as
       the base, then merge all source identifiers as Patient.identifier[].
    """
    n = len(fingerprints)
    if n == 0:
        return PatientIdentityIndex(canonical_patients={}, source_to_canonical={})

    # Step 1 + 2: score all pairs, collect match edges
    edges: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            s = score(fingerprints[i], fingerprints[j])
            if s.decision in ("match", "possible-match"):
                edges.append((i, j))

    # Step 3: connected components
    components = _connected_components(n, edges)

    canonical_patients: dict[str, CanonicalPatient] = {}
    source_to_canonical: dict[tuple[str, str], str] = {}

    # Build a lookup: local_patient_id → canonical_id (from explicit overrides)
    id_for = canonical_id_for or {}

    for component in components:
        fps = [fingerprints[i] for i in component]

        # Step 4: determine canonical_id
        canonical_id: str | None = None
        for fp in fps:
            if fp.local_patient_id in id_for:
                canonical_id = id_for[fp.local_patient_id]
                break

        if canonical_id is None:
            # Use first fingerprint's name+dob
            canonical_id = _canonical_id_from_fingerprint(fps[0])
            if not canonical_id or canonical_id == "patient":
                import hashlib

                h = hashlib.md5(
                    "".join(fp.local_patient_id for fp in fps).encode()
                ).hexdigest()[:8]
                canonical_id = f"patient-{h}"

        # Step 5: build merged resource
        fhir = merged_patient_resource(
            CanonicalPatient(
                canonical_id=canonical_id,
                fingerprints=fps,
                fhir_resource={},  # placeholder; filled below
            )
        )

        cp = CanonicalPatient(
            canonical_id=canonical_id,
            fingerprints=fps,
            fhir_resource=fhir,
        )
        canonical_patients[canonical_id] = cp

        for fp in fps:
            source_to_canonical[(fp.source, fp.local_patient_id)] = canonical_id

    return PatientIdentityIndex(
        canonical_patients=canonical_patients,
        source_to_canonical=source_to_canonical,
    )


def merged_patient_resource(canonical: CanonicalPatient) -> dict:
    """Emit the gold-tier merged FHIR Patient.

    All source MRNs preserved as Patient.identifier[]; one canonical name + DOB
    chosen by completeness. meta.profile = us-core-patient.
    """
    fps = canonical.fingerprints

    # Choose the "most complete" fingerprint as the base for demographics
    def _completeness(fp: PatientFingerprint) -> int:
        score = 0
        if fp.family_name:
            score += 2
        if fp.given_names:
            score += 2
        if fp.birth_date:
            score += 2
        if fp.gender:
            score += 1
        if fp.address_zip:
            score += 1
        if fp.mrn_value:
            score += 1
        return score

    base = max(fps, key=_completeness)

    # Build identifier list — one entry per source fingerprint that has an MRN
    identifiers: list[dict] = []
    seen: set[tuple[str | None, str | None]] = set()
    for fp in fps:
        key = (fp.mrn_system, fp.mrn_value)
        if key in seen or (fp.mrn_value is None):
            continue
        seen.add(key)
        ident: dict = {
            "use": "usual",
            "type": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                        "code": "MR",
                        "display": "Medical Record Number",
                    }
                ],
                "text": "Medical Record Number",
            },
            "value": fp.mrn_value,
        }
        if fp.mrn_system:
            ident["system"] = fp.mrn_system
        # Tag which source this came from
        ident["extension"] = [
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-tag",
                "valueString": fp.source,
            }
        ]
        identifiers.append(ident)

    # Name
    name_block: dict = {}
    if base.family_name:
        name_block["family"] = base.family_name
    if base.given_names:
        name_block["given"] = list(base.given_names)
    name_block["use"] = "official"

    # Tags — one per contributing source
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
        "resourceType": "Patient",
        "id": canonical.canonical_id,
        "meta": {
            "profile": [
                "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
            ],
            "source": "harmonizer://identity-resolution",
            "tag": source_tags + [lifecycle_tag],
        },
        "identifier": identifiers,
        "name": [name_block] if (name_block.get("family") or name_block.get("given")) else [],
    }

    if base.birth_date:
        resource["birthDate"] = base.birth_date
    if base.gender:
        resource["gender"] = base.gender

    return resource
