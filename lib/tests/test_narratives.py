"""Tests for ``lib.narratives`` (T5 of the Phase 1 plan).

Acceptance criteria from LLM-CONTEXT-AUGMENTATION-PLAN.md §T5:

1. ``generate_episode_narrative`` produces a FHIR Composition with all
   required sections present and ``status='final'``.
2. Every ``[[ref:Resource/id]]`` and ``[[ref:turn-...]]`` marker in the
   output sections resolves to an id in the allowed cite list.
3. Re-running ``write_current_narrative`` moves the prior ``current.json``
   into ``history/<its-date>.json`` and the new Composition carries
   ``relatesTo[0].code='replaces'`` pointing at the prior id.
4. Invalid markers from the LLM are stripped on retry; surrounding
   prose survives.
5. The cite index correctly surfaces patient-voice turn ids alongside
   merged FHIR resource ids.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.narratives import (
    FakeNarrativeGenerator,
    generate_episode_narrative,
    load_current_narrative,
    write_current_narrative,
)
from lib.narratives.generator import (
    _Sections,
    _allowed_id_set,
    _build_cite_index,
    _invalid_refs,
    _strip_invalid_refs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _episode_cardio() -> dict:
    return {
        "resourceType": "EpisodeOfCare",
        "id": "episode-cardiometabolic",
        "status": "active",
        "patient": {"reference": "Patient/demo"},
        "period": {"start": "1980-08-18"},
        "type": [
            {
                "coding": [
                    {
                        "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/episode-type",
                        "code": "chronic-condition-management",
                        "display": "Cardiometabolic management",
                    }
                ],
                "text": "Cardiometabolic management",
            }
        ],
        "diagnosis": [{"condition": {"reference": "Condition/cond-diabetes"}, "rank": 1}],
    }


def _harmonized_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": "cond-diabetes",
                    "code": {"text": "Diabetes"},
                    "subject": {"reference": "Patient/demo"},
                    "onsetDateTime": "1984-08-27",
                    "clinicalStatus": {"coding": [{"code": "active"}]},
                }
            },
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": "merged-rxnorm-29046",
                    "status": "stopped",
                    "medicationCodeableConcept": {"text": "Lisinopril 10mg"},
                    "authoredOn": "2019-08-01",
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-hba1c-latest",
                    "code": {"text": "HbA1c"},
                    "effectiveDateTime": "2026-01-15",
                    "valueString": "7.1",
                }
            },
        ],
    }


def _patient_voice_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"source": "patient-context://sess_a91c"},
        "entry": [
            {
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": "pv-sess_a91c-t_4f2c9b-0",
                    "status": "stopped",
                    "medicationCodeableConcept": {"text": "lisinopril"},
                    "subject": {"reference": "Patient/demo"},
                    "note": [
                        {"text": "I stopped lisinopril about 3 weeks ago — was making me cough."}
                    ],
                    "meta": {
                        "source": "patient-context://sess_a91c",
                        "extension": [
                            {
                                "url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator",
                                "valueString": "session=sess_a91c;turn=t_4f2c9b;gap=medication-reality",
                            }
                        ],
                    },
                }
            }
        ],
    }


def _fake_with_sections(**overrides) -> FakeNarrativeGenerator:
    defaults = dict(
        summary="Lorenzo's cardiometabolic story.",
        timeline=(
            "- Diabetes onset 1984-08 [[ref:Condition/cond-diabetes]]\n"
            "- Lisinopril started [[ref:MedicationRequest/merged-rxnorm-29046]]\n"
        ),
        key_facts=(
            "Active diabetes managed with lifestyle + RAAS therapy "
            "[[ref:MedicationRequest/merged-rxnorm-29046]]. Latest HbA1c 7.1 "
            "[[ref:Observation/obs-hba1c-latest]]."
        ),
        patient_words=(
            '[[ref:turn-t_4f2c9b]] "I stopped lisinopril about 3 weeks ago — '
            'was making me cough."'
        ),
        open_questions="- Confirm why lisinopril was stopped.",
    )
    defaults.update(overrides)
    return FakeNarrativeGenerator(default=_Sections(**defaults))


# ---------------------------------------------------------------------------
# Cite-index + allowed-id semantics
# ---------------------------------------------------------------------------


def test_cite_index_surfaces_resources_and_turn_ids():
    index = _build_cite_index(
        harmonized_record=_harmonized_bundle(),
        patient_voice_bundle=_patient_voice_bundle(),
    )
    assert "cond-diabetes" in index["Condition"]
    assert "merged-rxnorm-29046" in index["MedicationRequest"]
    assert "obs-hba1c-latest" in index["Observation"]
    assert "turn-t_4f2c9b" in index["turn"]


def test_allowed_id_set_prefixes_resources_with_type():
    index = {
        "Condition": {"cond-a"},
        "MedicationRequest": {"med-b"},
        "Observation": set(),
        "Encounter": set(),
        "turn": {"turn-x"},
    }
    allowed = _allowed_id_set(index)
    assert "Condition/cond-a" in allowed
    assert "MedicationRequest/med-b" in allowed
    assert "turn-x" in allowed
    assert "cond-a" not in allowed  # must carry type prefix


def test_invalid_refs_detected_and_stripped():
    text = (
        "Real [[ref:Condition/cond-diabetes]] and "
        "bogus [[ref:Condition/does-not-exist]]."
    )
    allowed = {"Condition/cond-diabetes"}
    bad = _invalid_refs(text, allowed)
    assert bad == {"Condition/does-not-exist"}
    sections = _Sections(
        summary=text, timeline="", key_facts="", patient_words="", open_questions=""
    )
    cleaned = _strip_invalid_refs(sections, allowed)
    assert "[[ref:Condition/cond-diabetes]]" in cleaned.summary
    assert "[[ref:Condition/does-not-exist]]" not in cleaned.summary
    assert "Real" in cleaned.summary  # surrounding prose preserved


# ---------------------------------------------------------------------------
# generate_episode_narrative — happy path
# ---------------------------------------------------------------------------


def test_generate_episode_narrative_produces_valid_composition():
    composition = generate_episode_narrative(
        patient_id="demo",
        episode=_episode_cardio(),
        harmonized_record=_harmonized_bundle(),
        patient_voice_bundle=_patient_voice_bundle(),
        generator=_fake_with_sections(),
    )
    assert composition["resourceType"] == "Composition"
    assert composition["status"] == "final"
    assert composition["subject"] == {"reference": "Patient/demo"}
    assert composition["type"]["coding"][0]["code"] == "episode-narrative"
    titles = [s["title"] for s in composition["section"]]
    assert titles == ["Summary", "Timeline", "Key facts", "Patient's own words", "Open questions"]
    # episode-ref extension points at the EpisodeOfCare we passed in
    ext_urls = {e["url"] for e in composition["extension"]}
    assert any(u.endswith("/episode-ref") for u in ext_urls)
    ext_target = next(e for e in composition["extension"] if e["url"].endswith("/episode-ref"))
    assert ext_target["valueReference"]["reference"] == "EpisodeOfCare/episode-cardiometabolic"


def test_composition_id_uses_episode_slug_minus_prefix():
    composition = generate_episode_narrative(
        patient_id="demo",
        episode=_episode_cardio(),
        harmonized_record=_harmonized_bundle(),
        generator=_fake_with_sections(),
    )
    # id format: narrative-<slug>-<timestamp>
    assert composition["id"].startswith("narrative-cardiometabolic-")


# ---------------------------------------------------------------------------
# Storage + versioning
# ---------------------------------------------------------------------------


def test_write_current_narrative_archives_prior_with_replaces_link(tmp_path: Path):
    # Generate twice: first writes current.json with no relatesTo.
    composition_v1 = generate_episode_narrative(
        patient_id="demo",
        episode=_episode_cardio(),
        harmonized_record=_harmonized_bundle(),
        generator=_fake_with_sections(summary="version one"),
    )
    write_current_narrative(patient_id="demo", composition=composition_v1, root=tmp_path)

    # Sanity: current.json exists, prior version not yet in history.
    current = load_current_narrative("demo", "cardiometabolic", root=tmp_path)
    assert current is not None
    assert current["id"].startswith("narrative-cardiometabolic-")

    composition_v2 = generate_episode_narrative(
        patient_id="demo",
        episode=_episode_cardio(),
        harmonized_record=_harmonized_bundle(),
        generator=_fake_with_sections(summary="version two"),
    )
    write_current_narrative(patient_id="demo", composition=composition_v2, root=tmp_path)

    # current.json is now v2, with relatesTo pointing at v1.
    current2 = load_current_narrative("demo", "cardiometabolic", root=tmp_path)
    assert current2 is not None
    relates = current2.get("relatesTo") or []
    assert relates and relates[0]["code"] == "replaces"
    assert relates[0]["targetReference"]["reference"] == f"Composition/{composition_v1['id']}"

    # v1 is archived in history/ with status=superseded.
    history_dir = tmp_path / "demo" / "cardiometabolic" / "history"
    archived = list(history_dir.glob("*.json"))
    assert len(archived) == 1
    archived_payload = json.loads(archived[0].read_text(encoding="utf-8"))
    assert archived_payload["id"] == composition_v1["id"]
    assert archived_payload["status"] == "superseded"


def test_load_current_narrative_returns_none_when_missing(tmp_path: Path):
    assert load_current_narrative("nobody", "no-such-episode", root=tmp_path) is None
