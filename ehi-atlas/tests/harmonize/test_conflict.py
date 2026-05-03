"""Tests for ehi_atlas.harmonize.conflict (task 3.8).

Covers:
  - detect_observation_conflicts (near-match, exact-match, different-dates, same-source)
  - detect_medication_class_conflicts (CrossClassFlag → ConflictPair)
  - apply_conflict_pairs (extension attach, idempotency, empty input)
  - emit_conflict_provenance (one record per pair, DERIVE activity, two entities)
  - ConflictPair label and summary properties

CrossClassFlag is defined as a local dataclass matching the protocol shape
expected from 3.6's medication.py (which may be in_progress). Tests use the
local definition; once 3.6 lands the import can be switched to
``from ehi_atlas.harmonize.medication import CrossClassFlag``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from ehi_atlas.harmonize.conflict import (
    ConflictPair,
    apply_conflict_pairs,
    detect_medication_class_conflicts,
    detect_observation_conflicts,
    emit_conflict_provenance,
)
from ehi_atlas.harmonize.provenance import (
    ACTIVITY_SYS,
    EXT_CONFLICT_PAIR,
    ProvenanceWriter,
)


# ---------------------------------------------------------------------------
# Local CrossClassFlag stub (mirrors protocol from medication.py task 3.6)
# ---------------------------------------------------------------------------


@dataclass
class CrossClassFlag:
    """Local stub matching the CrossClassFlag protocol from 3.6."""

    ingredient_a: str
    ingredient_b: str
    class_label: str
    source_a: str
    source_b: str
    resource_a_reference: str
    resource_b_reference: str


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

LOINC_CREATININE = "2160-0"
DATE_SEPT_12 = "2025-09-12"


def _make_obs(
    obs_id: str,
    loinc: str,
    date: str,
    value: float,
    unit: str = "mg/dl",
    source_tag: str = "synthea",
) -> dict:
    """Minimal FHIR Observation fixture for dedup/conflict testing."""
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "meta": {
            "tag": [
                {"system": "https://ehi-atlas.example/fhir/CodeSystem/source-tag", "code": source_tag}
            ]
        },
        "status": "final",
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc, "display": "Creatinine"}]
        },
        "effectiveDateTime": date,
        "valueQuantity": {"value": value, "unit": unit, "code": unit},
    }


def _make_flag(
    ingredient_a: str = "simvastatin",
    ingredient_b: str = "atorvastatin",
    class_label: str = "statin",
    source_a: str = "synthea",
    source_b: str = "epic-ehi",
    ref_a: str = "MedicationRequest/synth-simva-001",
    ref_b: str = "MedicationRequest/epic-atorva-042",
) -> CrossClassFlag:
    return CrossClassFlag(
        ingredient_a=ingredient_a,
        ingredient_b=ingredient_b,
        class_label=class_label,
        source_a=source_a,
        source_b=source_b,
        resource_a_reference=ref_a,
        resource_b_reference=ref_b,
    )


# ---------------------------------------------------------------------------
# 1. Observation near-match: creatinine 1.4 vs 1.5 on same date → ConflictPair
# ---------------------------------------------------------------------------


def test_detect_observation_conflicts_near_match_creatinine():
    synthea_obs = _make_obs("synthea-creat-001", LOINC_CREATININE, DATE_SEPT_12, 1.4, source_tag="synthea")
    lab_obs = _make_obs("labpdf-creat-001", LOINC_CREATININE, DATE_SEPT_12, 1.5, source_tag="lab-pdf")

    obs_by_source = {
        "synthea": [synthea_obs],
        "lab-pdf": [lab_obs],
    }
    pairs = detect_observation_conflicts(obs_by_source)

    assert len(pairs) == 1, f"Expected 1 conflict pair, got {len(pairs)}"
    pair = pairs[0]
    assert pair.kind == "observation-value-disagreement"
    assert pair.sources == ("synthea", "lab-pdf") or pair.sources == ("lab-pdf", "synthea")


# ---------------------------------------------------------------------------
# 2. Exact-match observations → no conflict (those are deduplicated by 3.7)
# ---------------------------------------------------------------------------


def test_detect_observation_conflicts_exact_match_returns_none():
    obs_a = _make_obs("synth-001", LOINC_CREATININE, DATE_SEPT_12, 1.4, source_tag="synthea")
    obs_b = _make_obs("labpdf-001", LOINC_CREATININE, DATE_SEPT_12, 1.4, source_tag="lab-pdf")

    pairs = detect_observation_conflicts({"synthea": [obs_a], "lab-pdf": [obs_b]})

    assert pairs == [], "Exact-value match must NOT produce a conflict pair"


# ---------------------------------------------------------------------------
# 3. Different dates → no conflict
# ---------------------------------------------------------------------------


def test_detect_observation_conflicts_different_dates_returns_none():
    obs_a = _make_obs("synth-001", LOINC_CREATININE, "2025-09-12", 1.4, source_tag="synthea")
    obs_b = _make_obs("labpdf-001", LOINC_CREATININE, "2025-09-15", 1.5, source_tag="lab-pdf")

    pairs = detect_observation_conflicts({"synthea": [obs_a], "lab-pdf": [obs_b]})

    assert pairs == [], "Different clinical dates must NOT produce a conflict pair"


# ---------------------------------------------------------------------------
# 4. Same-source pairs skipped even with different values
# ---------------------------------------------------------------------------


def test_detect_observation_conflicts_same_source_pairs_skipped():
    obs_a = _make_obs("synth-001", LOINC_CREATININE, DATE_SEPT_12, 1.4, source_tag="synthea")
    obs_b = _make_obs("synth-002", LOINC_CREATININE, DATE_SEPT_12, 1.5, source_tag="synthea")

    pairs = detect_observation_conflicts({"synthea": [obs_a, obs_b]})

    assert pairs == [], "Same-source observations must NOT be flagged as cross-source conflicts"


# ---------------------------------------------------------------------------
# 5. Medication cross-class: simvastatin ↔ atorvastatin → ConflictPair
# ---------------------------------------------------------------------------


def test_detect_medication_class_conflicts_emits_pair_for_simvastatin_atorvastatin():
    flag = _make_flag()
    pairs = detect_medication_class_conflicts([flag])

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.kind == "medication-cross-class"
    assert pair.resource_a_reference == "MedicationRequest/synth-simva-001"
    assert pair.resource_b_reference == "MedicationRequest/epic-atorva-042"
    assert pair.sources == ("synthea", "epic-ehi")


# ---------------------------------------------------------------------------
# 6. Medication cross-class summary mentions both ingredient names
# ---------------------------------------------------------------------------


def test_detect_medication_class_conflicts_summary_mentions_both_ingredients():
    flag = _make_flag(ingredient_a="simvastatin", ingredient_b="atorvastatin")
    pairs = detect_medication_class_conflicts([flag])

    summary = pairs[0].summary
    assert "simvastatin" in summary, f"Summary should mention simvastatin; got: {summary!r}"
    assert "atorvastatin" in summary, f"Summary should mention atorvastatin; got: {summary!r}"


# ---------------------------------------------------------------------------
# 7. apply_conflict_pairs attaches EXT_CONFLICT_PAIR to both resources
# ---------------------------------------------------------------------------


def test_apply_conflict_pairs_attaches_extension_to_both_resources():
    obs_a: dict = {"resourceType": "Observation", "id": "obs-a"}
    obs_b: dict = {"resourceType": "Observation", "id": "obs-b"}

    pair = ConflictPair(
        kind="observation-value-disagreement",
        label="value disagreement",
        summary="Source 'synthea' reported 1.4 mg/dl; Source 'lab-pdf' reported 1.5 mg/dl.",
        resource_a_reference="Observation/obs-a",
        resource_b_reference="Observation/obs-b",
        sources=("synthea", "lab-pdf"),
    )

    resources_by_id = {
        "Observation/obs-a": obs_a,
        "Observation/obs-b": obs_b,
    }
    apply_conflict_pairs([pair], resources_by_id)

    # obs-a should point at obs-b
    exts_a = obs_a.get("extension", [])
    conflict_exts_a = [e for e in exts_a if e.get("url") == EXT_CONFLICT_PAIR]
    assert len(conflict_exts_a) == 1
    assert conflict_exts_a[0]["valueReference"]["reference"] == "Observation/obs-b"

    # obs-b should point at obs-a
    exts_b = obs_b.get("extension", [])
    conflict_exts_b = [e for e in exts_b if e.get("url") == EXT_CONFLICT_PAIR]
    assert len(conflict_exts_b) == 1
    assert conflict_exts_b[0]["valueReference"]["reference"] == "Observation/obs-a"


# ---------------------------------------------------------------------------
# 8. apply_conflict_pairs is idempotent
# ---------------------------------------------------------------------------


def test_apply_conflict_pairs_is_idempotent():
    obs_a: dict = {"resourceType": "Observation", "id": "obs-a"}
    obs_b: dict = {"resourceType": "Observation", "id": "obs-b"}

    pair = ConflictPair(
        kind="observation-value-disagreement",
        label="value disagreement",
        summary="Repeated application must not duplicate extensions.",
        resource_a_reference="Observation/obs-a",
        resource_b_reference="Observation/obs-b",
        sources=("synthea", "lab-pdf"),
    )

    resources_by_id = {"Observation/obs-a": obs_a, "Observation/obs-b": obs_b}

    apply_conflict_pairs([pair], resources_by_id)
    apply_conflict_pairs([pair], resources_by_id)  # second call

    # Each resource should still have exactly ONE conflict-pair extension
    exts_a = [e for e in obs_a.get("extension", []) if e.get("url") == EXT_CONFLICT_PAIR]
    exts_b = [e for e in obs_b.get("extension", []) if e.get("url") == EXT_CONFLICT_PAIR]
    assert len(exts_a) == 1, "Idempotency violated: obs-a has multiple conflict-pair extensions"
    assert len(exts_b) == 1, "Idempotency violated: obs-b has multiple conflict-pair extensions"


# ---------------------------------------------------------------------------
# 9. emit_conflict_provenance writes one record per pair with two entities
# ---------------------------------------------------------------------------


def test_emit_conflict_provenance_writes_one_record_per_pair_with_two_entities(tmp_path):
    pair_a = ConflictPair(
        kind="observation-value-disagreement",
        label="value disagreement",
        summary="Source 'synthea' reported 1.4 mg/dl; Source 'lab-pdf' reported 1.5 mg/dl.",
        resource_a_reference="Observation/obs-001",
        resource_b_reference="Observation/obs-002",
        sources=("synthea", "lab-pdf"),
    )
    pair_b = ConflictPair(
        kind="medication-cross-class",
        label="drug-class switch",
        summary="Statin substitution: 'synthea' has simvastatin; 'epic-ehi' has atorvastatin.",
        resource_a_reference="MedicationRequest/synth-001",
        resource_b_reference="MedicationRequest/epic-001",
        sources=("synthea", "epic-ehi"),
    )

    writer = ProvenanceWriter(tmp_path, patient_id="rhett759")
    emit_conflict_provenance([pair_a, pair_b], writer)
    out_path = writer.flush()

    lines = out_path.read_text().splitlines()
    assert len(lines) == 2, f"Expected 2 provenance records, got {len(lines)}"

    for line in lines:
        prov = json.loads(line)
        assert prov["resourceType"] == "Provenance"
        entities = prov.get("entity", [])
        assert len(entities) == 2, f"Expected 2 entities per conflict Provenance, got {len(entities)}"


# ---------------------------------------------------------------------------
# 10. emit_conflict_provenance uses DERIVE activity
# ---------------------------------------------------------------------------


def test_emit_conflict_provenance_uses_derive_activity(tmp_path):
    pair = ConflictPair(
        kind="observation-value-disagreement",
        label="value disagreement",
        summary="Source 'synthea' reported 1.4 mg/dl; Source 'lab-pdf' reported 1.5 mg/dl.",
        resource_a_reference="Observation/obs-001",
        resource_b_reference="Observation/obs-002",
        sources=("synthea", "lab-pdf"),
    )

    writer = ProvenanceWriter(tmp_path, patient_id="rhett759")
    emit_conflict_provenance([pair], writer)
    out_path = writer.flush()

    prov = json.loads(out_path.read_text().strip())
    activity_codings = prov.get("activity", {}).get("coding", [])
    assert any(c.get("code") == "DERIVE" for c in activity_codings), (
        f"Expected DERIVE activity; got {activity_codings}"
    )
    assert any(c.get("system") == ACTIVITY_SYS for c in activity_codings)


# ---------------------------------------------------------------------------
# 11. ConflictPair label is short and human-readable (< 40 chars)
# ---------------------------------------------------------------------------


def test_conflict_pair_label_is_short_and_human_readable():
    obs_a = _make_obs("s-001", LOINC_CREATININE, DATE_SEPT_12, 1.4, source_tag="synthea")
    obs_b = _make_obs("l-001", LOINC_CREATININE, DATE_SEPT_12, 1.5, source_tag="lab-pdf")
    obs_pairs = detect_observation_conflicts({"synthea": [obs_a], "lab-pdf": [obs_b]})

    flag = _make_flag()
    med_pairs = detect_medication_class_conflicts([flag])

    all_pairs = obs_pairs + med_pairs
    assert all_pairs, "Need at least one pair to test labels"

    for pair in all_pairs:
        assert len(pair.label) < 40, (
            f"Label too long ({len(pair.label)} chars): {pair.label!r}"
        )
        # Label must not be empty
        assert pair.label.strip(), f"Label must not be empty for kind={pair.kind}"


# ---------------------------------------------------------------------------
# 12. ConflictPair summary explains the disagreement (contains actual values / names)
# ---------------------------------------------------------------------------


def test_conflict_pair_summary_explains_the_disagreement():
    # Observation: summary should contain the actual values
    obs_a = _make_obs("s-001", LOINC_CREATININE, DATE_SEPT_12, 1.4, source_tag="synthea")
    obs_b = _make_obs("l-001", LOINC_CREATININE, DATE_SEPT_12, 1.5, source_tag="lab-pdf")
    obs_pairs = detect_observation_conflicts({"synthea": [obs_a], "lab-pdf": [obs_b]})
    assert obs_pairs
    obs_summary = obs_pairs[0].summary
    assert "1.4" in obs_summary, f"Observation summary should contain value 1.4; got: {obs_summary!r}"
    assert "1.5" in obs_summary, f"Observation summary should contain value 1.5; got: {obs_summary!r}"

    # Medication: summary should contain the ingredient names
    flag = _make_flag(ingredient_a="simvastatin", ingredient_b="atorvastatin", class_label="statin")
    med_pairs = detect_medication_class_conflicts([flag])
    assert med_pairs
    med_summary = med_pairs[0].summary
    assert "simvastatin" in med_summary
    assert "atorvastatin" in med_summary


# ---------------------------------------------------------------------------
# 13. apply_conflict_pairs handles empty input without error
# ---------------------------------------------------------------------------


def test_apply_conflict_pairs_handles_empty_input():
    resources_by_id: dict[str, dict] = {}
    # Must not raise
    apply_conflict_pairs([], resources_by_id)

    # Also handles non-empty resources but empty pairs
    obs: dict = {"resourceType": "Observation", "id": "obs-x"}
    apply_conflict_pairs([], {"Observation/obs-x": obs})
    assert "extension" not in obs, "No extension should be attached when pairs list is empty"
