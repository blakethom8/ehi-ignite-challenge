"""Conflict detection for Layer 3 harmonization.

Conflicts are cross-source disagreements the harmonizer SURFACES rather than
silently resolving. Both records are preserved; the conflict-pair extension
on each links them together; a narrator-friendly label/summary is attached
for the Sources-panel UI.

Phase 1 detectors:
  1. Observation near-match (same LOINC + date, different value/unit)
  2. Medication cross-class divergence (different ingredients, same class)
  3. (stub) Condition status divergence (one source: active, other: resolved)

The LLM judge for ambiguous cases is build-time: a static labelling pre-frozen
into a dictionary, applied at runtime. For Phase 1 the labelling is rule-based;
the LLM hook is reserved for Phase 2.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from ehi_atlas.harmonize.observation import observations_near_match, extract_observation_key
from ehi_atlas.harmonize.provenance import (
    attach_conflict_pair,
    ProvenanceWriter,
    SourceRef,
    ProvenanceRecord,
    ACTIVITY_SYS,
    DEFAULT_RECORDED,
)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ConflictKind = Literal[
    "observation-value-disagreement",
    "medication-cross-class",
    "medication-status-disagreement",
    "condition-status-disagreement",
]


@dataclass(frozen=True)
class ConflictPair:
    """A pair of resources flagged as conflicting across sources."""

    kind: ConflictKind
    label: str          # short human label (e.g. "drug-class switch"), < 40 chars
    summary: str        # one-sentence explanation for the UI
    resource_a_reference: str   # silver-tier reference, e.g. "Observation/synthea-obs-creat-001"
    resource_b_reference: str
    sources: tuple[str, str]    # (source-a-name, source-b-name)


# ---------------------------------------------------------------------------
# CrossClassFlag protocol — matches medication.py (task 3.6) without importing it.
# If 3.6 has landed, tests can also import CrossClassFlag directly.
# ---------------------------------------------------------------------------


@runtime_checkable
class CrossClassFlagProtocol(Protocol):
    """Structural protocol matching the expected CrossClassFlag from 3.6."""

    ingredient_a: str       # ingredient name in source A (e.g. "simvastatin")
    ingredient_b: str       # ingredient name in source B (e.g. "atorvastatin")
    class_label: str        # shared drug class (e.g. "statin")
    source_a: str           # source name for record A (e.g. "synthea")
    source_b: str           # source name for record B (e.g. "epic-ehi")
    resource_a_reference: str   # silver-tier reference for the A-side resource
    resource_b_reference: str   # silver-tier reference for the B-side resource


# ---------------------------------------------------------------------------
# Label / summary formatters
# ---------------------------------------------------------------------------


def _observation_label(key_a_value: float | str | None, key_b_value: float | str | None) -> str:
    """Short label for an observation value conflict (< 40 chars)."""
    return "value disagreement"


def _observation_summary(
    loinc: str | None,
    date: str | None,
    value_a: float | str | None,
    unit_a: str | None,
    source_a: str,
    value_b: float | str | None,
    unit_b: str | None,
    source_b: str,
) -> str:
    """One-sentence explanation of an observation value conflict for the UI."""
    loinc_str = loinc or "unknown LOINC"
    date_str = date or "unknown date"
    val_a_str = f"{value_a} {unit_a}".strip() if value_a is not None else "unknown"
    val_b_str = f"{value_b} {unit_b}".strip() if value_b is not None else "unknown"
    return (
        f"LOINC {loinc_str} on {date_str}: "
        f"Source {source_a!r} reported {val_a_str}; "
        f"Source {source_b!r} reported {val_b_str}."
    )


def _medication_class_label(ingredient_a: str, ingredient_b: str) -> str:
    """Short label for a medication cross-class conflict (< 40 chars)."""
    return "drug-class switch"


def _medication_class_summary(
    ingredient_a: str,
    ingredient_b: str,
    class_label: str,
    source_a: str,
    source_b: str,
) -> str:
    """One-sentence explanation of a medication cross-class conflict."""
    return (
        f"{class_label.capitalize()} substitution: "
        f"Source {source_a!r} has {ingredient_a}; "
        f"Source {source_b!r} has {ingredient_b}."
    )


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def detect_observation_conflicts(
    observations_by_source: dict[str, list[dict]],
) -> list[ConflictPair]:
    """Walk pairs of (resource, source) where the SAME LOINC + clinical-date
    appear across sources but the value differs. Emits a ConflictPair per
    near-match.

    Uses ``observations_near_match`` from 3.7 + ``extract_observation_key`` to
    group candidates first (avoid O(N²) brute force).

    Args:
        observations_by_source: ``{source_name: [Observation resource dicts]}``

    Returns:
        List of :class:`ConflictPair`, one per cross-source near-match pair.
        Same-source pairs and exact-match pairs are both excluded.
    """
    # Build index: (loinc, date) → list[(source_name, obs_resource)]
    # We only index observations with a complete key (loinc + date non-None).
    index: dict[tuple[str | None, str | None], list[tuple[str, dict]]] = {}

    for source_name, obs_list in observations_by_source.items():
        for obs in obs_list:
            key = extract_observation_key(obs)
            # Index on (loinc, date) — the shared dimensions for near-match
            bucket_key = (key.loinc_code, key.clinical_date)
            if key.loinc_code is None or key.clinical_date is None:
                # Skip observations without enough identity to conflict
                continue
            index.setdefault(bucket_key, []).append((source_name, obs))

    pairs: list[ConflictPair] = []
    seen_pairs: set[frozenset[str]] = set()  # avoid bidirectional duplicates

    for (loinc, date), candidates in index.items():
        # Pairwise check — O(k²) where k = #candidates per bucket (typically ≤ 5)
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                source_a, obs_a = candidates[i]
                source_b, obs_b = candidates[j]

                # Skip same-source pairs
                if source_a == source_b:
                    continue

                ref_a = _obs_ref(obs_a)
                ref_b = _obs_ref(obs_b)

                # Dedup: each (ref_a, ref_b) pair reported once
                pair_key: frozenset[str] = frozenset({ref_a, ref_b})
                if pair_key in seen_pairs:
                    continue

                if observations_near_match(obs_a, obs_b):
                    key_a = extract_observation_key(obs_a)
                    key_b = extract_observation_key(obs_b)
                    seen_pairs.add(pair_key)
                    pairs.append(
                        ConflictPair(
                            kind="observation-value-disagreement",
                            label=_observation_label(key_a.value, key_b.value),
                            summary=_observation_summary(
                                loinc=loinc,
                                date=date,
                                value_a=key_a.value,
                                unit_a=key_a.unit,
                                source_a=source_a,
                                value_b=key_b.value,
                                unit_b=key_b.unit,
                                source_b=source_b,
                            ),
                            resource_a_reference=ref_a,
                            resource_b_reference=ref_b,
                            sources=(source_a, source_b),
                        )
                    )

    return pairs


def detect_medication_class_conflicts(
    cross_class_flags,  # list[CrossClassFlag] from 3.6 (or protocol-compatible objects)
) -> list[ConflictPair]:
    """Convert each CrossClassFlag from 3.6 into a ConflictPair with a
    descriptive label (e.g. 'statin substitution: simvastatin → atorvastatin')
    and one-sentence summary suitable for the Sources panel.

    Args:
        cross_class_flags: Iterable of objects conforming to
            :class:`CrossClassFlagProtocol` (i.e. the CrossClassFlag dataclass
            from ``ehi_atlas.harmonize.medication`` — or a mock with the same
            fields for testing).

    Returns:
        One :class:`ConflictPair` per flag.
    """
    pairs: list[ConflictPair] = []
    for flag in cross_class_flags:
        pairs.append(
            ConflictPair(
                kind="medication-cross-class",
                label=_medication_class_label(flag.ingredient_a, flag.ingredient_b),
                summary=_medication_class_summary(
                    ingredient_a=flag.ingredient_a,
                    ingredient_b=flag.ingredient_b,
                    class_label=flag.class_label,
                    source_a=flag.source_a,
                    source_b=flag.source_b,
                ),
                resource_a_reference=flag.resource_a_reference,
                resource_b_reference=flag.resource_b_reference,
                sources=(flag.source_a, flag.source_b),
            )
        )
    return pairs


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def apply_conflict_pairs(
    pairs: list[ConflictPair],
    resources_by_id: dict[str, dict],
) -> None:
    """For each ConflictPair, attach EXT_CONFLICT_PAIR to both resources
    (each pointing at the other), so the UI can render them side-by-side.

    Looks up resources by their FHIR relative reference (e.g.
    ``"Observation/abc"``). Resources not found in ``resources_by_id`` are
    silently skipped.

    Mutates resources in place via ``attach_conflict_pair`` from provenance.py
    (idempotent upsert).

    Args:
        pairs: List of detected :class:`ConflictPair` objects.
        resources_by_id: ``{"Observation/abc": resource_dict, ...}``
    """
    for pair in pairs:
        res_a = resources_by_id.get(pair.resource_a_reference)
        res_b = resources_by_id.get(pair.resource_b_reference)

        if res_a is not None:
            attach_conflict_pair(res_a, pair.resource_b_reference)
        if res_b is not None:
            attach_conflict_pair(res_b, pair.resource_a_reference)


def emit_conflict_provenance(
    pairs: list[ConflictPair],
    writer: ProvenanceWriter,
) -> None:
    """For each ConflictPair, write a Provenance record (activity=DERIVE,
    rationale=label+summary) to the ndjson via the writer.

    The Provenance.target is the GOLD-tier conflict-pair record using a
    deterministic id ``conflict-{kind}-{counter}`` (counter starts at 0).
    ``entity[]`` points at both silver-tier source resources.

    Args:
        pairs: List of detected :class:`ConflictPair` objects.
        writer: An open :class:`ProvenanceWriter` instance.
    """
    for counter, pair in enumerate(pairs):
        gold_id = f"conflict-{pair.kind}-{counter}"
        gold_reference = f"Provenance/{gold_id}"

        rationale = f"{pair.label}: {pair.summary}"

        prov = ProvenanceRecord(
            target_reference=gold_reference,
            activity="DERIVE",
            sources=[
                SourceRef(reference=pair.resource_a_reference, role="source"),
                SourceRef(reference=pair.resource_b_reference, role="source"),
            ],
            rationale=rationale,
        )
        writer.add(prov)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _obs_ref(obs: dict) -> str:
    """Build a FHIR reference string for an Observation, e.g. 'Observation/abc'."""
    rid = obs.get("id", "unknown")
    return f"Observation/{rid}"
