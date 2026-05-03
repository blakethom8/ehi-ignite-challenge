"""Observation deduplication for Layer 3 harmonization.

Two silver-tier Observations refer to the same logical fact if they share:
  - The same LOINC (or UMLS-equivalent) code
  - The same clinical date (per ehi_atlas.harmonize.temporal)
  - The same numeric value (within ε tolerance)
  - The same UCUM unit (byte-equal after light normalization)

Near-matches are NOT silently merged — both records are preserved with a
conflict-pair extension. Only exact matches dedup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ehi_atlas.harmonize.temporal import clinical_time
from ehi_atlas.harmonize.provenance import (
    merge_provenance,
    attach_quality_score,
    attach_merge_rationale,
    EXT_QUALITY_SCORE,
    SYS_SOURCE_TAG,
    SYS_LIFECYCLE,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOINC_SYSTEM = "http://loinc.org"
US_CORE_OBS_LAB_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"
)

# Tunable: numeric value match tolerance as a fraction of the value.
# 0.001 → 1.40 == 1.4 == 1.401 but 1.45 is a near-match (not equivalent).
VALUE_TOLERANCE = 0.001


# ---------------------------------------------------------------------------
# ObservationKey
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObservationKey:
    """The dedup key extracted from an Observation."""

    loinc_code: str | None
    clinical_date: str | None  # ISO 8601 date or datetime; from temporal module
    value: float | str | None  # numeric value or string code
    unit: str | None  # normalized UCUM


# ---------------------------------------------------------------------------
# Unit normalization
# ---------------------------------------------------------------------------


def normalize_unit(unit: str | None) -> str | None:
    """Light normalization: lowercase, strip, common synonyms.

    'mg/dL' → 'mg/dl', 'MG/DL' → 'mg/dl', '  mg/dL ' → 'mg/dl'. No real
    unit conversion — that's Phase 2.
    """
    if unit is None:
        return None
    normalized = unit.strip().lower()
    return normalized if normalized else None


# ---------------------------------------------------------------------------
# Key extraction
# ---------------------------------------------------------------------------


def extract_observation_key(
    obs: dict, encounter_lookup: dict | None = None
) -> ObservationKey:
    """Pull (loinc, date, value, unit) from a FHIR R4 Observation.

    LOINC: walks ``obs.code.coding[]`` for a coding with system
    http://loinc.org.
    Date: uses ``clinical_time(obs)`` from temporal module → ISO date string
    (date portion only, so two Observations on the same day compare equal even
    if one has a time component).
    Value: ``obs.valueQuantity.value`` (numeric) or ``obs.valueString``
    (string).
    Unit: ``obs.valueQuantity.code`` (UCUM) preferred over
    ``valueQuantity.unit``.
    """
    # --- LOINC code ---
    loinc_code: str | None = None
    code_block = obs.get("code", {})
    for coding in code_block.get("coding", []):
        if isinstance(coding, dict) and coding.get("system") == LOINC_SYSTEM:
            loinc_code = coding.get("code") or None
            break

    # --- Clinical date (date portion only) ---
    clinical_date: str | None = None
    ct = clinical_time(obs, encounter_lookup or {})
    if ct.timestamp is not None:
        # Keep only the date portion for day-level comparison
        clinical_date = ct.timestamp.strftime("%Y-%m-%d")

    # --- Value ---
    value: float | str | None = None
    vq = obs.get("valueQuantity")
    if isinstance(vq, dict) and "value" in vq:
        raw_val = vq["value"]
        try:
            value = float(raw_val)
        except (TypeError, ValueError):
            value = str(raw_val)
    elif "valueString" in obs:
        value = obs["valueString"]

    # --- Unit (UCUM code preferred over display unit) ---
    unit: str | None = None
    if isinstance(vq, dict):
        raw_unit = vq.get("code") or vq.get("unit")
        unit = normalize_unit(raw_unit)

    return ObservationKey(
        loinc_code=loinc_code,
        clinical_date=clinical_date,
        value=value,
        unit=unit,
    )


# ---------------------------------------------------------------------------
# Equivalence + near-match
# ---------------------------------------------------------------------------


def _key_complete(key: ObservationKey) -> bool:
    """Return True iff all four key fields are non-None."""
    return (
        key.loinc_code is not None
        and key.clinical_date is not None
        and key.value is not None
        and key.unit is not None
    )


def _values_equal(a_val: float | str | None, b_val: float | str | None) -> bool:
    """Compare two observation values with tolerance for floats."""
    if a_val is None or b_val is None:
        return False
    if isinstance(a_val, float) and isinstance(b_val, float):
        # Relative tolerance: |a - b| / max(|a|, |b|, ε) ≤ VALUE_TOLERANCE
        denom = max(abs(a_val), abs(b_val), 1e-12)
        return abs(a_val - b_val) / denom <= VALUE_TOLERANCE
    # String or mixed comparison: exact match only
    return a_val == b_val


def observations_equivalent(a: dict, b: dict) -> bool:
    """True iff (loinc, date, value, unit) keys are byte-equal up to tolerance.

    None on either key field → not equivalent (we don't guess).
    """
    ka = extract_observation_key(a)
    kb = extract_observation_key(b)

    if not (_key_complete(ka) and _key_complete(kb)):
        return False

    return (
        ka.loinc_code == kb.loinc_code
        and ka.clinical_date == kb.clinical_date
        and _values_equal(ka.value, kb.value)
        and ka.unit == kb.unit
    )


def observations_near_match(a: dict, b: dict) -> bool:
    """True iff same loinc + same date but value or unit differs.

    Used for conflict detection; returns False if exact match (use
    observations_equivalent for that).
    """
    ka = extract_observation_key(a)
    kb = extract_observation_key(b)

    if not (_key_complete(ka) and _key_complete(kb)):
        return False

    # Must share loinc + date
    if ka.loinc_code != kb.loinc_code or ka.clinical_date != kb.clinical_date:
        return False

    # If they are equivalent, this is NOT a near-match — it's an exact match
    if _values_equal(ka.value, kb.value) and ka.unit == kb.unit:
        return False

    return True


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


@dataclass
class ObservationMergeResult:
    """The result of merging N observations that share a key."""

    merged: dict  # the gold-tier Observation
    sources: list[str]  # the silver-tier resource references that contributed
    rationale: str  # one-line merge explanation


def _get_quality_score(obs: dict) -> float | None:
    """Extract the EXT_QUALITY_SCORE from obs.meta.extension, or None."""
    meta = obs.get("meta", {})
    for ext in meta.get("extension", []):
        if isinstance(ext, dict) and ext.get("url") == EXT_QUALITY_SCORE:
            val = ext.get("valueDecimal")
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    return None


def _obs_ref(obs: dict) -> str:
    """Build a FHIR reference string for an Observation, e.g. 'Observation/abc'."""
    rid = obs.get("id", "unknown")
    return f"Observation/{rid}"


def merge_observations(
    observations: list[dict], canonical_id: str
) -> ObservationMergeResult:
    """Merge N observations sharing the same key into one canonical Observation.

    Inputs must be observations_equivalent pairwise; this function does NOT
    re-check equivalence — that's the caller's job (typically the orchestrator).

    The merged resource:
    - id = ``canonical_id``
    - meta.profile includes us-core-observation-lab
    - meta.tag includes a source-tag entry for EVERY contributing source
    - meta.tag includes lifecycle=harmonized
    - identifier[] includes one entry per source (system+value)
    - code, value, unit, effectiveDateTime taken from the highest-quality input
      (use existing meta extension EXT_QUALITY_SCORE if present; otherwise the
      first input)
    - meta.extension gets EXT_QUALITY_SCORE (max across inputs) and
      EXT_MERGE_RATIONALE
    """
    if not observations:
        raise ValueError("merge_observations requires at least one observation")

    # --- Pick the "best" observation as the data donor ---
    scores = [_get_quality_score(obs) for obs in observations]
    best_idx = 0
    if any(s is not None for s in scores):
        # Pick the one with the highest quality score; None scores lose
        best_idx = max(
            range(len(observations)),
            key=lambda i: scores[i] if scores[i] is not None else -1.0,
        )
    best = observations[best_idx]
    max_score = max((s for s in scores if s is not None), default=None)

    # --- Build merged meta.tag ---
    # Collect all source tags from all inputs (unique, stable order)
    merged_tags: list[dict] = []
    seen_source_tags: set[str] = set()
    for obs in observations:
        meta = obs.get("meta", {})
        for tag in meta.get("tag", []):
            if not isinstance(tag, dict):
                continue
            sys = tag.get("system", "")
            code = tag.get("code", "")
            if sys == SYS_SOURCE_TAG and code not in seen_source_tags:
                seen_source_tags.add(code)
                merged_tags.append({"system": sys, "code": code})

    # Add lifecycle=harmonized tag
    merged_tags.append({"system": SYS_LIFECYCLE, "code": "harmonized"})

    # --- Build merged identifiers ---
    # One per contributing observation; use source tag as system when available
    identifiers: list[dict] = []
    for obs in observations:
        obs_id = obs.get("id", "")
        # Try to find a good system from existing identifiers or meta
        meta = obs.get("meta", {})
        source_tags = [
            t.get("code", "")
            for t in meta.get("tag", [])
            if isinstance(t, dict) and t.get("system") == SYS_SOURCE_TAG
        ]
        id_system = (
            f"ehi-atlas://source/{source_tags[0]}/Observation"
            if source_tags
            else "ehi-atlas://Observation"
        )
        identifiers.append({"system": id_system, "value": obs_id})

    # --- Build merged meta ---
    merged_meta: dict = {
        "profile": [US_CORE_OBS_LAB_PROFILE],
        "tag": merged_tags,
        "extension": [],
    }

    # Carry forward any meta.extension from the best observation that aren't
    # quality-score (we'll re-attach that ourselves) or lifecycle tags
    for ext in best.get("meta", {}).get("extension", []):
        if isinstance(ext, dict) and ext.get("url") != EXT_QUALITY_SCORE:
            merged_meta["extension"].append(ext)

    # --- Assemble merged Observation ---
    merged: dict = {
        "resourceType": "Observation",
        "id": canonical_id,
        "meta": merged_meta,
        "identifier": identifiers,
        "status": best.get("status", "final"),
        "category": best.get("category"),
        "code": best.get("code"),
        "subject": best.get("subject"),
        "effectiveDateTime": best.get("effectiveDateTime"),
        "issued": best.get("issued"),
        "valueQuantity": best.get("valueQuantity"),
    }
    # Remove None fields to keep the dict clean
    merged = {k: v for k, v in merged.items() if v is not None}

    # --- Attach quality score (max) ---
    if max_score is not None:
        attach_quality_score(merged, max_score)

    # --- Compose rationale ---
    source_refs = [_obs_ref(obs) for obs in observations]
    rationale = (
        f"Dedup merge of {len(observations)} observations sharing "
        f"(LOINC={extract_observation_key(best).loinc_code}, "
        f"date={extract_observation_key(best).clinical_date}, "
        f"value={extract_observation_key(best).value}, "
        f"unit={extract_observation_key(best).unit}): "
        + ", ".join(source_refs)
    )

    # Attach merge rationale to merged resource (top-level extension)
    attach_merge_rationale(merged, rationale)

    return ObservationMergeResult(
        merged=merged,
        sources=source_refs,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Bulk dedup
# ---------------------------------------------------------------------------


def dedup_observations(
    observations: Iterable[dict],
    canonical_id_prefix: str = "merged-obs",
) -> tuple[list[dict], list[ObservationMergeResult]]:
    """Bulk dedup pass.

    Group observations by ObservationKey (only resources with all key fields).
    For each group:
      - if group size == 1, pass through (no merge needed; resource stays as-is)
      - if group size > 1, merge into one canonical observation
    Resources without a complete key fall through unchanged.

    Returns ``(deduplicated_observations, list_of_merges)``.
    The merges list is what the orchestrator uses to emit Provenance.
    """
    obs_list = list(observations)

    # Separate into keyed (eligible for dedup) and unkeyed (pass-through)
    keyed: list[tuple[ObservationKey, dict]] = []
    unkeyed: list[dict] = []

    for obs in obs_list:
        key = extract_observation_key(obs)
        if _key_complete(key):
            keyed.append((key, obs))
        else:
            unkeyed.append(obs)

    # Group keyed observations by their key
    groups: dict[ObservationKey, list[dict]] = {}
    for key, obs in keyed:
        groups.setdefault(key, []).append(obs)

    result_obs: list[dict] = list(unkeyed)
    merges: list[ObservationMergeResult] = []

    for idx, (key, group) in enumerate(groups.items()):
        if len(group) == 1:
            # No duplicate — pass through unchanged
            result_obs.append(group[0])
        else:
            # Multiple observations share the same key → merge
            canonical_id = f"{canonical_id_prefix}-{idx}"
            merge_result = merge_observations(group, canonical_id)
            result_obs.append(merge_result.merged)
            merges.append(merge_result)

    return result_obs, merges
