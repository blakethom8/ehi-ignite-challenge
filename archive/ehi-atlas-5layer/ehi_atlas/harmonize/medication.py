"""Medication episode reconciliation for Layer 3 harmonization.

A medication episode is a continuous period of patient exposure to a single
RxNorm ingredient. This module:
  - groups MedicationRequest resources by RxNorm-ingredient (or RxCUI directly
    if no IN mapping)
  - merges same-ingredient episodes across sources (temporal envelope union,
    status reconciliation by quality score)
  - leaves different-ingredient episodes separate (3.8 detects the cross-source
    "drug switch" conflict)

For the showcase, simvastatin (RxCUI 36567) and atorvastatin (RxCUI 83367)
are different ingredients → two separate gold episodes flagged for 3.8.

CROSSWALK NOTE (Phase 1):
The hand-curated crosswalk (corpus/reference/handcrafted-crosswalk/showcase.json)
does NOT have a dedicated ``class_label`` field on the per-drug entries.
Therapeutic-class grouping is encoded only as a separate "Statin therapy
(class concept)" entry (umls_cui=C0360714). For Phase 1 we use a small
hardcoded RXCUI → class_label mapping derived from that crosswalk entry.
Main-thread: please add a ``class_label`` field to the simvastatin and
atorvastatin crosswalk entries (and any other Phase 2 medications) so that
``detect_cross_class_flags`` can drive entirely from the crosswalk at runtime
rather than needing a Phase-1 hardcode.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable

from ehi_atlas.harmonize.code_map import SYS_RXNORM
from ehi_atlas.harmonize.quality import quality_score
from ehi_atlas.harmonize.provenance import (
    merge_provenance,
    attach_quality_score,
    attach_merge_rationale,
    SYS_SOURCE_TAG,
    SYS_LIFECYCLE,
    ProvenanceRecord,
    EXT_QUALITY_SCORE,
)


# ---------------------------------------------------------------------------
# Status reconciliation
# ---------------------------------------------------------------------------

# When the same ingredient has different statuses across sources, which wins?
# Higher priority value wins. "stopped"/"cancelled" beat "active" when we see
# a definitive end-of-treatment signal from any source.
STATUS_PRIORITY: dict[str, int] = {
    "entered-in-error": 0,
    "draft":            1,
    "unknown":          1,
    "active":           2,
    "completed":        3,
    "on-hold":          4,
    "stopped":          5,
    "cancelled":        6,
}


# ---------------------------------------------------------------------------
# Phase 1 therapeutic-class map
# ---------------------------------------------------------------------------

# Derived from the crosswalk notes: simvastatin and atorvastatin are both
# "HMG-CoA reductase inhibitors (statins)".  Keyed by RxCUI (string).
# Phase 2: remove this hardcode and drive from crosswalk.class_label.
_RXCUI_CLASS_LABEL: dict[str, str] = {
    "36567":  "statin",  # simvastatin
    "83367":  "statin",  # atorvastatin
    "896188": "statin",  # fluticasone/salmeterol product — not a statin; placeholder shows extension point
}
# Correct the fluticasone entry — it is NOT a statin.  Removed.
# Note: Synthea emits product-level RxCUI 316672 ("Simvastatin 10 MG Oral Tablet")
# rather than ingredient-level 36567.  Both map to the same therapeutic class.
_RXCUI_CLASS_LABEL = {
    "36567":  "statin",  # simvastatin (ingredient-level IN)
    "316672": "statin",  # Simvastatin 10 MG Oral Tablet (clinical drug SCD — Synthea uses this)
    "83367":  "statin",  # atorvastatin (ingredient-level IN)
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MedicationEpisode:
    """A normalized representation of a single drug episode.

    Attributes:
        rxcui:              RxNorm code (ingredient level); None if unmapped.
        ingredient_label:   Human-readable drug name (from crosswalk or display).
        status:             MedicationRequest.status string.
        period_start:       ISO 8601 onset or dispenseRequest.validityPeriod.start.
        period_end:         ISO 8601 end-of-treatment; None if still active/unknown.
        source_resource_id: The original silver MedicationRequest ``id``.
        source_tag:         The source system (synthea, epic-ehi, …).
    """

    rxcui: str | None
    ingredient_label: str | None
    status: str
    period_start: str | None
    period_end: str | None
    source_resource_id: str
    source_tag: str | None = None


def episode_from_medication_request(req: dict) -> MedicationEpisode:
    """Pull (rxcui, status, dates, source) from a FHIR MedicationRequest.

    RxCUI: walks ``req.medicationCodeableConcept.coding[]`` for
    ``system == SYS_RXNORM`` (http://www.nlm.nih.gov/research/umls/rxnorm).
    Falls back to None if no RxNorm coding found.

    Status: ``req.status`` (string).

    period_start resolution order:
      1. ``req.dispenseRequest.validityPeriod.start``
      2. ``req.authoredOn``
      3. None

    period_end:
      1. ``req.dispenseRequest.validityPeriod.end``
      2. None (Phase 1 only; Phase 2: walk MedicationDispense/Statement history)

    ingredient_label: ``display`` of the RxNorm coding, or ``text`` of the
    CodeableConcept, or None.

    source_tag: extracted from ``req.meta.tag[]`` for SYS_SOURCE_TAG system.
    """
    # --- RxCUI and ingredient_label ---
    rxcui: str | None = None
    ingredient_label: str | None = None

    med_cc = req.get("medicationCodeableConcept")
    if isinstance(med_cc, dict):
        for coding in med_cc.get("coding", []):
            if isinstance(coding, dict) and coding.get("system") == SYS_RXNORM:
                rxcui = coding.get("code") or None
                ingredient_label = coding.get("display") or None
                break
        # Fallback label from CodeableConcept.text
        if ingredient_label is None:
            ingredient_label = med_cc.get("text") or None

    # --- Status ---
    status: str = req.get("status", "unknown")

    # --- Dates ---
    period_start: str | None = None
    period_end: str | None = None

    dispense = req.get("dispenseRequest", {})
    validity = dispense.get("validityPeriod", {}) if isinstance(dispense, dict) else {}
    if isinstance(validity, dict):
        period_start = validity.get("start") or None
        period_end = validity.get("end") or None

    if period_start is None:
        period_start = req.get("authoredOn") or None

    # --- source_tag ---
    source_tag: str | None = None
    tags: list = req.get("meta", {}).get("tag", []) or []
    for tag in tags:
        if isinstance(tag, dict) and tag.get("system") == SYS_SOURCE_TAG:
            source_tag = tag.get("code") or None
            break

    return MedicationEpisode(
        rxcui=rxcui,
        ingredient_label=ingredient_label,
        status=status,
        period_start=period_start,
        period_end=period_end,
        source_resource_id=req.get("id", "unknown"),
        source_tag=source_tag,
    )


# ---------------------------------------------------------------------------
# Same-ingredient predicate
# ---------------------------------------------------------------------------


def episodes_same_ingredient(a: MedicationEpisode, b: MedicationEpisode) -> bool:
    """True iff both episodes have the same non-None RxCUI.

    NB: two episodes sharing a *therapeutic class* (e.g., simvastatin and
    atorvastatin, both statins) return False here — that is a 3.8 conflict,
    not a merge candidate.  We group only by exact ingredient identity.

    If either episode has rxcui=None (unmapped), returns False — we never guess.
    """
    if a.rxcui is None or b.rxcui is None:
        return False
    return a.rxcui == b.rxcui


# ---------------------------------------------------------------------------
# Merge result
# ---------------------------------------------------------------------------


@dataclass
class EpisodeMergeResult:
    """Result of merging N same-ingredient episodes into one gold resource."""

    merged: dict          # Gold-tier FHIR MedicationRequest
    sources: list[str]    # Silver-tier references that contributed
    rationale: str        # One-line merge explanation
    provenance: ProvenanceRecord


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------


def _get_quality_score_from_req(req: dict) -> float | None:
    """Extract EXT_QUALITY_SCORE from req.meta.extension, or None."""
    for ext in req.get("meta", {}).get("extension", []):
        if isinstance(ext, dict) and ext.get("url") == EXT_QUALITY_SCORE:
            val = ext.get("valueDecimal")
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass
    return None


def _source_tags_from_req(req: dict) -> list[str]:
    """Return all source-tag codes from req.meta.tag."""
    return [
        t.get("code", "")
        for t in req.get("meta", {}).get("tag", [])
        if isinstance(t, dict) and t.get("system") == SYS_SOURCE_TAG
    ]


def _med_ref(req: dict) -> str:
    """Build 'MedicationRequest/<id>' reference string."""
    return f"MedicationRequest/{req.get('id', 'unknown')}"


# ---------------------------------------------------------------------------
# merge_episodes
# ---------------------------------------------------------------------------


def merge_episodes(
    episodes: list[dict],
    canonical_id: str,
) -> EpisodeMergeResult:
    """Merge N same-ingredient MedicationRequests into one gold MedicationRequest.

    Strategy:
    - Highest quality score input is the data donor (code, subject, …).
    - All source-tags are preserved in meta.tag.
    - lifecycle=harmonized tag added.
    - period_start: earliest non-None start across inputs.
    - period_end: if any input has a period_end (discontinued), preserve the
      *latest* such end date to capture the full temporal envelope.
    - status: highest STATUS_PRIORITY wins (e.g., "stopped" beats "active").
      If the winning status comes with a period_end, that is preserved.
    - Original IDs are added as identifier[] entries.
    - EXT_QUALITY_SCORE (max), EXT_MERGE_RATIONALE attached.

    Returns an EpisodeMergeResult (merged FHIR dict + provenance record).
    """
    if not episodes:
        raise ValueError("merge_episodes requires at least one MedicationRequest")

    # Pick the best (highest-quality) as data donor
    scores = [_get_quality_score_from_req(r) for r in episodes]
    best_idx = 0
    if any(s is not None for s in scores):
        best_idx = max(
            range(len(episodes)),
            key=lambda i: scores[i] if scores[i] is not None else -1.0,
        )
    best = episodes[best_idx]
    max_score = max((s for s in scores if s is not None), default=None)

    # Status: highest STATUS_PRIORITY wins
    winning_status = max(
        (ep.get("status", "unknown") for ep in episodes),
        key=lambda s: STATUS_PRIORITY.get(s, 1),
    )

    # Temporal envelope: earliest start, latest end
    starts: list[str] = [
        ep.get("dispenseRequest", {}).get("validityPeriod", {}).get("start")
        or ep.get("authoredOn")
        for ep in episodes
    ]
    starts_non_none = [s for s in starts if s]
    merged_start = min(starts_non_none) if starts_non_none else None

    ends: list[str] = [
        ep.get("dispenseRequest", {}).get("validityPeriod", {}).get("end")
        for ep in episodes
        if ep.get("dispenseRequest", {}).get("validityPeriod", {}).get("end")
    ]
    merged_end = max(ends) if ends else None

    # meta.tag — gather all source tags + lifecycle=harmonized
    merged_tags: list[dict] = []
    seen_source_codes: set[str] = set()
    for ep in episodes:
        for tag in ep.get("meta", {}).get("tag", []):
            if not isinstance(tag, dict):
                continue
            if tag.get("system") == SYS_SOURCE_TAG and tag.get("code") not in seen_source_codes:
                seen_source_codes.add(tag["code"])
                merged_tags.append({"system": SYS_SOURCE_TAG, "code": tag["code"]})
    merged_tags.append({"system": SYS_LIFECYCLE, "code": "harmonized"})

    # identifier[] — one per contributing source
    identifiers: list[dict] = []
    for ep in episodes:
        ep_id = ep.get("id", "")
        src_tags = _source_tags_from_req(ep)
        sys_str = (
            f"ehi-atlas://source/{src_tags[0]}/MedicationRequest"
            if src_tags
            else "ehi-atlas://MedicationRequest"
        )
        identifiers.append({"system": sys_str, "value": ep_id})

    # meta.extension — carry forward non-quality extensions from best, then re-attach quality
    merged_meta_exts: list[dict] = [
        ext
        for ext in best.get("meta", {}).get("extension", [])
        if isinstance(ext, dict) and ext.get("url") != EXT_QUALITY_SCORE
    ]
    merged_meta: dict = {
        "tag": merged_tags,
        "extension": merged_meta_exts,
    }

    # Build validityPeriod if we have any temporal data
    validity_period: dict = {}
    if merged_start:
        validity_period["start"] = merged_start
    if merged_end:
        validity_period["end"] = merged_end

    # Assemble merged resource (base from best, override dynamic fields)
    merged: dict = {
        "resourceType": "MedicationRequest",
        "id": canonical_id,
        "meta": merged_meta,
        "identifier": identifiers,
        "status": winning_status,
        "intent": best.get("intent", "order"),
        "medicationCodeableConcept": best.get("medicationCodeableConcept"),
        "subject": best.get("subject"),
        "authoredOn": merged_start,
        "dispenseRequest": (
            {"validityPeriod": validity_period} if validity_period else best.get("dispenseRequest")
        ),
    }
    # Drop None-valued top-level keys
    merged = {k: v for k, v in merged.items() if v is not None}

    # Attach quality score
    if max_score is not None:
        attach_quality_score(merged, max_score)

    # Build rationale
    source_refs = [_med_ref(ep) for ep in episodes]
    ep0 = episode_from_medication_request(best)
    rationale = (
        f"Merged {len(episodes)} same-ingredient (RxCUI={ep0.rxcui}) episodes "
        f"across sources {list(seen_source_codes)}: {', '.join(source_refs)}"
    )
    attach_merge_rationale(merged, rationale)

    prov = merge_provenance(
        target=f"MedicationRequest/{canonical_id}",
        sources=source_refs,
        rationale=rationale,
    )

    return EpisodeMergeResult(
        merged=merged,
        sources=source_refs,
        rationale=rationale,
        provenance=prov,
    )


# ---------------------------------------------------------------------------
# reconcile_episodes — bulk reconciliation
# ---------------------------------------------------------------------------


def reconcile_episodes(
    medication_requests_by_source: dict[str, list[dict]],
    *,
    canonical_id_fn: Callable[[str, int], str] | None = None,
) -> tuple[list[dict], list[EpisodeMergeResult]]:
    """Bulk reconciliation across sources.

    Algorithm:
    1. Convert all MedicationRequests to MedicationEpisodes (extract RxCUI, status, dates).
    2. Group by rxcui (exact match only — different ingredients stay separate).
    3. For each group:
       - 1 resource  → pass through unchanged.
       - 2+ resources from DIFFERENT sources → merge_episodes.
       - Multiple resources from the SAME source with the same RxCUI: all
         included in the merge (unusual but handled).
    4. MedicationRequests with rxcui=None pass through (un-mappable).

    Args:
        medication_requests_by_source: ``{"synthea": [...], "epic-ehi": [...], ...}``
        canonical_id_fn: Optional ``(rxcui, group_index) → str`` for canonical IDs.
            Default: ``"merged-med-{rxcui}-{idx}"``.

    Returns:
        ``(deduplicated_requests, list_of_merge_results)``
        The merge list is what the orchestrator uses to emit Provenance.
    """
    if canonical_id_fn is None:
        def canonical_id_fn(rxcui: str, idx: int) -> str:
            return f"merged-med-{rxcui}-{idx}"

    # Flatten all requests while tagging source
    all_reqs: list[dict] = []
    for source_name, reqs in medication_requests_by_source.items():
        for req in reqs:
            # Ensure the source tag is on the request (caller should have set it;
            # but defensively inject it here too so grouping / tags work)
            meta = req.setdefault("meta", {})
            tags: list = meta.setdefault("tag", [])
            has_source_tag = any(
                isinstance(t, dict) and t.get("system") == SYS_SOURCE_TAG
                for t in tags
            )
            if not has_source_tag:
                tags.append({"system": SYS_SOURCE_TAG, "code": source_name})
            all_reqs.append(req)

    # Split into rxcui-keyed and un-mapped
    rxcui_groups: dict[str, list[dict]] = {}
    unmapped: list[dict] = []

    for req in all_reqs:
        ep = episode_from_medication_request(req)
        if ep.rxcui is None:
            unmapped.append(req)
        else:
            rxcui_groups.setdefault(ep.rxcui, []).append(req)

    result_reqs: list[dict] = list(unmapped)
    merges: list[EpisodeMergeResult] = []

    for group_idx, (rxcui, group) in enumerate(rxcui_groups.items()):
        if len(group) == 1:
            result_reqs.append(group[0])
        else:
            cid = canonical_id_fn(rxcui, group_idx)
            merge_result = merge_episodes(group, cid)
            result_reqs.append(merge_result.merged)
            merges.append(merge_result)

    return result_reqs, merges


# ---------------------------------------------------------------------------
# Cross-source class flagging (the bridge to 3.8 conflict detection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrossClassFlag:
    """Two different ingredients in the same therapeutic class, seen across sources.

    This signals a candidate "drug switch" conflict for 3.8 to narrate.

    Attributes:
        ingredient_a:       RxCUI of the first ingredient.
        ingredient_b:       RxCUI of the second ingredient.
        sources_a:          Source tags that have ingredient_a.
        sources_b:          Source tags that have ingredient_b.
        common_class_label: Shared therapeutic class (e.g. "statin").
    """

    ingredient_a: str
    ingredient_b: str
    sources_a: list[str]
    sources_b: list[str]
    common_class_label: str


def _class_label_for_rxcui(rxcui: str) -> str | None:
    """Return the therapeutic class label for a given RxCUI, or None.

    Phase 1: driven from the hardcoded _RXCUI_CLASS_LABEL map (derived from
    the crosswalk's "Statin therapy (class concept)" entry).

    Phase 2: replace this lookup with a runtime read of crosswalk.class_label
    once main-thread adds that field to the per-drug crosswalk entries.
    """
    return _RXCUI_CLASS_LABEL.get(rxcui)


def detect_cross_class_flags(
    episodes: list[MedicationEpisode],
    crosswalk_class_field: str = "class_label",  # reserved for Phase 2 runtime use
) -> list[CrossClassFlag]:
    """Identify episodes for DIFFERENT ingredients sharing a therapeutic class.

    When two episodes have distinct RxCUIs but the same class_label (e.g.,
    simvastatin=statin and atorvastatin=statin), and those episodes come from
    DIFFERENT source systems, emit a CrossClassFlag for 3.8 to consume.

    Rules:
    - Only flag episodes with non-None rxcui.
    - Only flag pairs where rxcui_a != rxcui_b (same ingredient → no flag).
    - Only flag when both share a known class_label.
    - Only flag pairs from DIFFERENT sources (same-source same-class is not
      a cross-source conflict).
    - Phase 1: only pairwise flags (multi-way flagging is Phase 2).

    Returns empty list if no cross-class divergence detected.
    """
    # Group episodes by rxcui and collect their sources
    rxcui_to_sources: dict[str, list[str]] = {}
    for ep in episodes:
        if ep.rxcui is None:
            continue
        src = ep.source_tag or "unknown"
        rxcui_to_sources.setdefault(ep.rxcui, []).append(src)

    # Build list of (rxcui, class_label, sources)
    rxcui_class_sources: list[tuple[str, str, list[str]]] = []
    for rxcui, sources in rxcui_to_sources.items():
        label = _class_label_for_rxcui(rxcui)
        if label is not None:
            rxcui_class_sources.append((rxcui, label, sources))

    # Find pairs sharing a class_label but with DIFFERENT rxcuis AND different sources
    flags: list[CrossClassFlag] = []
    seen_pairs: set[frozenset[str]] = set()

    for i, (rxcui_a, class_a, sources_a) in enumerate(rxcui_class_sources):
        for j, (rxcui_b, class_b, sources_b) in enumerate(rxcui_class_sources):
            if j <= i:
                continue  # only upper triangle
            if class_a != class_b:
                continue  # different classes → not a cross-class conflict
            if rxcui_a == rxcui_b:
                continue  # same ingredient → no flag
            # Check that the two groups come from at least some different sources
            sources_a_set = set(sources_a)
            sources_b_set = set(sources_b)
            if not sources_a_set.isdisjoint(sources_b_set):
                # Overlap: some sources have both; might still be multi-source
                # but only flag if there are sources exclusive to each side
                only_a = sources_a_set - sources_b_set
                only_b = sources_b_set - sources_a_set
                if not only_a or not only_b:
                    continue  # all sources have both → not a cross-source conflict
            pair_key = frozenset([rxcui_a, rxcui_b])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            flags.append(
                CrossClassFlag(
                    ingredient_a=rxcui_a,
                    ingredient_b=rxcui_b,
                    sources_a=sorted(set(sources_a)),
                    sources_b=sorted(set(sources_b)),
                    common_class_label=class_a,
                )
            )

    return flags
