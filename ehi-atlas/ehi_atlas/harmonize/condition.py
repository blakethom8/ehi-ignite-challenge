"""Condition merging for Layer 3 harmonization.

Clusters Conditions across silver Bundles by shared UMLS CUI (via the
hand-curated crosswalk), merges each cluster into a canonical Condition with
all source codings preserved, picks authoritative status/onset by quality
score, and emits Provenance edges.

Artifact 1 anchor: HTN in Synthea (SNOMED 38341003) and Epic projection
(ICD-10 I10) both map to UMLS CUI C0020538 via the crosswalk. This module
merges them into ONE canonical Condition with both source codings preserved
in Condition.code.coding[] and Provenance edges back to both silver records.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from ehi_atlas.harmonize.code_map import (
    annotate_codeable_concept_with_cui,
    collect_concept_groups,
    resolve_coding,
)
from ehi_atlas.harmonize.quality import quality_score
from ehi_atlas.harmonize.provenance import (
    merge_provenance,
    attach_quality_score,
    attach_merge_rationale,
    SYS_SOURCE_TAG,
    SYS_LIFECYCLE,
    EXT_QUALITY_SCORE,
    ProvenanceRecord,
)
from ehi_atlas.harmonize.temporal import clinical_time

# US Core Condition profile URL
US_CORE_CONDITION_PROFILE = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition"
)

# Sentinel key for conditions that didn't resolve to any UMLS CUI
_UNMAPPED_KEY = "_unmapped"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ConditionMergeResult:
    """The result of merging N Conditions sharing a UMLS CUI.

    Attributes:
        merged:     The canonical gold-tier Condition resource.
        sources:    Silver-tier resource references that contributed
                    (e.g. ``["Condition/synthea-htn-001", "Condition/epic-htn-row42"]``).
        rationale:  One-line merge explanation (includes the UMLS CUI).
        provenance: The Provenance edge to emit alongside the merged Condition.
    """

    merged: dict
    sources: list[str]
    rationale: str
    provenance: ProvenanceRecord


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cond_ref(condition: dict) -> str:
    """Build a FHIR relative reference for a Condition, e.g. 'Condition/abc'."""
    rid = condition.get("id", "unknown")
    return f"Condition/{rid}"


def _get_quality_score_from_meta(resource: dict) -> float | None:
    """Extract the EXT_QUALITY_SCORE from resource.meta.extension, or None."""
    for ext in resource.get("meta", {}).get("extension", []):
        if isinstance(ext, dict) and ext.get("url") == EXT_QUALITY_SCORE:
            val = ext.get("valueDecimal")
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    return None


def _effective_quality_score(condition: dict) -> float:
    """Return the quality score already attached to this condition (via meta extension),
    or compute it fresh via quality_score() if not already attached.
    """
    pre_scored = _get_quality_score_from_meta(condition)
    if pre_scored is not None:
        return pre_scored
    return quality_score(condition)


def _get_cui_for_condition(condition: dict) -> str | None:
    """Return the first UMLS CUI found for any coding in Condition.code, or None."""
    code_cc = condition.get("code")
    if not isinstance(code_cc, dict):
        return None
    for coding_dict in code_cc.get("coding", []):
        res = resolve_coding(coding_dict)
        if res.found_in_crosswalk and res.umls_cui:
            return res.umls_cui
    return None


def _earliest_onset(conditions: list[dict]) -> str | None:
    """Return the ISO 8601 onsetDateTime string of the earliest-onset condition.

    Walks each condition via clinical_time(); returns the raw string value from
    the condition dict (not the normalised datetime) to preserve the original
    format.  Returns None if no condition has a recoverable onset.
    """
    best_ts = None
    best_raw: str | None = None

    for cond in conditions:
        ct = clinical_time(cond)
        if ct.timestamp is None:
            continue
        if best_ts is None or ct.timestamp < best_ts:
            best_ts = ct.timestamp
            # Prefer onsetDateTime, fall back to onsetPeriod.start, recordedDate
            for key in ("onsetDateTime", "recordedDate"):
                raw = cond.get(key)
                if raw and isinstance(raw, str):
                    best_raw = raw
                    break
            else:
                # Try onsetPeriod.start
                onset_period = cond.get("onsetPeriod", {})
                ps = onset_period.get("start") if isinstance(onset_period, dict) else None
                if ps and isinstance(ps, str):
                    best_raw = ps

    return best_raw


def _merge_codings(conditions: list[dict]) -> list[dict]:
    """Union of all codings across conditions, deduplicated by (system, code).

    Returns a list of coding dicts. Order: codings from the first condition
    appear first, then novel codings from subsequent conditions.
    """
    seen: dict[tuple[str, str], dict] = {}
    result: list[dict] = []

    for cond in conditions:
        code_cc = cond.get("code")
        if not isinstance(code_cc, dict):
            continue
        for coding_dict in code_cc.get("coding", []):
            if not isinstance(coding_dict, dict):
                continue
            sys = coding_dict.get("system", "")
            code = coding_dict.get("code", "")
            key = (sys, code)
            if key not in seen:
                seen[key] = dict(coding_dict)  # shallow copy
                result.append(seen[key])

    return result


# ---------------------------------------------------------------------------
# Core merge
# ---------------------------------------------------------------------------


def merge_conditions(conditions: list[dict], canonical_id: str) -> ConditionMergeResult:
    """Merge N Conditions sharing a UMLS CUI into one canonical Condition.

    Inputs must be cross-source equivalent (caller groups them via UMLS CUI).
    Returns the merged Condition + the Provenance to emit.

    Merge rules:
    - id = canonical_id
    - meta.profile = ['us-core-condition']
    - meta.tag includes one source-tag per contributing source + lifecycle=harmonized
    - meta.extension carries EXT_QUALITY_SCORE = max(quality_score per input)
    - identifier[] = union of all input identifiers (each tagged with source system)
    - code.coding[] = union of all input codings (deduplicated by (system, code))
    - code.coding[*] gets EXT_UMLS_CUI via annotate_codeable_concept_with_cui
    - clinicalStatus / verificationStatus = picked from highest quality input
    - onsetDateTime = earliest non-null clinical onset across inputs (temporal envelope)
    - subject = highest-quality input's subject (references the canonical Patient)
    - merge-rationale extension: "UMLS CUI <cui> matched across <N> sources"
    """
    if not conditions:
        raise ValueError("merge_conditions requires at least one condition")

    # --- Determine quality score for each input ---
    scores = [_effective_quality_score(c) for c in conditions]
    best_idx = max(range(len(conditions)), key=lambda i: scores[i])
    best = conditions[best_idx]
    max_score = max(scores)

    # --- Determine the shared UMLS CUI (from any condition in the cluster) ---
    cui: str | None = None
    for cond in conditions:
        cui = _get_cui_for_condition(cond)
        if cui:
            break

    # --- Collect all source-tags (stable unique order) ---
    merged_tags: list[dict] = []
    seen_source_codes: set[str] = set()
    for cond in conditions:
        for tag in cond.get("meta", {}).get("tag", []):
            if not isinstance(tag, dict):
                continue
            if tag.get("system") == SYS_SOURCE_TAG:
                code = tag.get("code", "")
                if code and code not in seen_source_codes:
                    seen_source_codes.add(code)
                    merged_tags.append({"system": SYS_SOURCE_TAG, "code": code})

    merged_tags.append({"system": SYS_LIFECYCLE, "code": "harmonized"})

    # --- Build merged identifiers ---
    # Each source condition's id becomes an identifier entry, system derived from
    # the source-tag code so it can be round-tripped back.
    identifiers: list[dict] = []
    for cond in conditions:
        cond_id = cond.get("id", "")
        source_tags = [
            t.get("code", "")
            for t in cond.get("meta", {}).get("tag", [])
            if isinstance(t, dict) and t.get("system") == SYS_SOURCE_TAG
        ]
        id_system = (
            f"{source_tags[0]}://Condition"
            if source_tags
            else "ehi-atlas://Condition"
        )
        # Also include pre-existing identifiers from the source condition
        for existing_id in cond.get("identifier", []):
            if isinstance(existing_id, dict):
                identifiers.append(existing_id)
        # Always add the resource-id as an identifier keyed to the source
        if cond_id:
            identifiers.append({"system": id_system, "value": cond_id})

    # Deduplicate identifiers by (system, value)
    seen_ids: set[tuple[str, str]] = set()
    deduped_identifiers: list[dict] = []
    for ident in identifiers:
        key = (ident.get("system", ""), ident.get("value", ""))
        if key not in seen_ids:
            seen_ids.add(key)
            deduped_identifiers.append(ident)

    # --- Build merged code: union of all codings with UMLS CUI annotation ---
    merged_codings = _merge_codings(conditions)
    merged_code: dict = {"coding": merged_codings}
    # Carry forward text from best condition if available
    best_text = best.get("code", {}).get("text") if isinstance(best.get("code"), dict) else None
    if best_text:
        merged_code["text"] = best_text
    # Annotate each coding with UMLS CUI extension
    annotate_codeable_concept_with_cui(merged_code)

    # --- Temporal envelope: earliest onset wins ---
    earliest_onset = _earliest_onset(conditions)

    # --- Assemble merged meta ---
    merged_meta: dict = {
        "profile": [US_CORE_CONDITION_PROFILE],
        "tag": merged_tags,
        "extension": [],
    }

    # --- Assemble merged Condition ---
    merged: dict = {
        "resourceType": "Condition",
        "id": canonical_id,
        "meta": merged_meta,
        "identifier": deduped_identifiers,
        "clinicalStatus": best.get("clinicalStatus"),
        "verificationStatus": best.get("verificationStatus"),
        "category": best.get("category"),
        "code": merged_code,
        "subject": best.get("subject"),
    }

    # Attach onset — prefer merged earliest, fall back to best's onset
    if earliest_onset is not None:
        merged["onsetDateTime"] = earliest_onset
    elif best.get("onsetDateTime"):
        merged["onsetDateTime"] = best.get("onsetDateTime")

    # Carry forward recordedDate from best if no onset available
    if not merged.get("onsetDateTime") and best.get("recordedDate"):
        merged["recordedDate"] = best.get("recordedDate")

    # Remove None-valued fields to keep the dict clean
    merged = {k: v for k, v in merged.items() if v is not None}

    # --- Attach quality score (max across inputs) ---
    attach_quality_score(merged, max_score)

    # --- Compose and attach rationale ---
    source_refs = [_cond_ref(c) for c in conditions]
    n_sources = len(conditions)
    cui_label = cui if cui else "unknown"
    rationale = (
        f"UMLS CUI {cui_label} matched across {n_sources} source"
        + ("s" if n_sources != 1 else "")
        + ": "
        + ", ".join(source_refs)
    )
    attach_merge_rationale(merged, rationale)

    # --- Build Provenance record ---
    prov = merge_provenance(
        target=f"Condition/{canonical_id}",
        sources=source_refs,
        rationale=rationale,
    )

    return ConditionMergeResult(
        merged=merged,
        sources=source_refs,
        rationale=rationale,
        provenance=prov,
    )


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


def cluster_conditions_by_cui(conditions: list[dict]) -> dict[str, list[dict]]:
    """Group Conditions by their primary code's UMLS CUI.

    Uses collect_concept_groups (from code_map) under the hood. Conditions
    with no CUI hit (unmapped codes) end up in the special ``"_unmapped"``
    group.

    Args:
        conditions: List of FHIR Condition resource dicts.

    Returns:
        ``{cui: [conditions...]}`` where unmapped conditions are under
        the key ``"_unmapped"``.
    """
    # collect_concept_groups returns only mapped codes
    groups = collect_concept_groups(conditions, path="code")

    # Find unmapped conditions: those not present in any CUI group
    mapped_ids: set[str] = {
        cond.get("id", "")
        for cond_list in groups.values()
        for cond in cond_list
    }
    unmapped = [c for c in conditions if c.get("id", "") not in mapped_ids]

    if unmapped:
        groups[_UNMAPPED_KEY] = unmapped

    return groups


# ---------------------------------------------------------------------------
# Bulk merge
# ---------------------------------------------------------------------------


def merge_all_conditions(
    conditions_by_source: dict[str, list[dict]],
    *,
    canonical_id_fn=None,
) -> tuple[list[dict], list[ConditionMergeResult]]:
    """Bulk merge: cluster Conditions across sources by UMLS CUI, merge each cluster.

    Args:
        conditions_by_source: ``{source_name: [Condition resources from that source's silver]}``
        canonical_id_fn: Callable ``(cui, sources) -> str``; defaults to
                         ``"merged-cond-<cui>"``.

    Returns:
        ``(deduplicated_conditions, list_of_merge_results)``.

        - **Singletons** (one-source clusters) flow through unchanged — no
          merge result is emitted.
        - **Unmapped** Conditions (``_unmapped`` group) flow through unchanged
          and are NOT merged.
        - **Multi-source clusters** are merged; one :class:`ConditionMergeResult`
          is emitted per cluster.
    """
    if canonical_id_fn is None:
        def canonical_id_fn(cui: str, sources: list[str]) -> str:  # type: ignore[misc]
            return f"merged-cond-{cui}"

    # Flatten all conditions into one list, preserving source attribution
    all_conditions: list[dict] = []
    for source_conditions in conditions_by_source.values():
        all_conditions.extend(source_conditions)

    if not all_conditions:
        return [], []

    # Cluster by UMLS CUI
    clusters = cluster_conditions_by_cui(all_conditions)

    result_conditions: list[dict] = []
    merge_results: list[ConditionMergeResult] = []

    for cui, cluster in clusters.items():
        if cui == _UNMAPPED_KEY:
            # Unmapped conditions pass through unchanged
            result_conditions.extend(cluster)
            continue

        if len(cluster) == 1:
            # Singleton — pass through unchanged, no merge result
            result_conditions.append(cluster[0])
            continue

        # Multi-source cluster → merge
        source_refs = [_cond_ref(c) for c in cluster]
        canonical_id = canonical_id_fn(cui, source_refs)
        merge_result = merge_conditions(cluster, canonical_id)
        result_conditions.append(merge_result.merged)
        merge_results.append(merge_result)

    return result_conditions, merge_results
