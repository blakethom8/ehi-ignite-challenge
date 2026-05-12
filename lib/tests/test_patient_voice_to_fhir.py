"""Tests for ``lib.patient_voice.to_fhir`` (T1 of the Phase 1 plan).

Acceptance criteria from
``docs/architecture/LLM-CONTEXT-AUGMENTATION-PLAN.md`` §T1:

1. A "stopped lisinopril 3 weeks ago" turn produces a MedicationStatement
   with status=stopped and effectivePeriod.end ≤ 25 days before today.
2. Every emitted resource carries the §3.1 provenance shape
   (meta.source + meta.extension with source-label + source-locator).
3. The output is a valid FHIR Bundle (resourceType=Bundle, entry list).
4. Tests run without live LLM calls (use FakeTurnClassifier).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lib.patient_voice import (
    FakeTurnClassifier,
    TurnClassification,
    session_to_fhir_bundle,
)
from lib.patient_voice.to_fhir import (
    PATIENT_VOICE_CODE_SYSTEM,
    SOURCE_LABEL_URL,
    SOURCE_LOCATOR_URL,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _session(turns: list[dict], *, gap_cards: list[dict] | None = None) -> dict:
    return {
        "session_id": "sess_a91c",
        "patient_id": "demo",
        "patient_label": "Demo Patient",
        "source_mode": "selected_patient",
        "source_posture": "Selected-patient mode.",
        "gap_cards": gap_cards or [],
        "turns": turns,
        "facts": [],
        "export_status": {"generated": False, "files": [], "generated_at": None},
    }


def _patient_turn(turn_id: str, content: str, *, gap: str | None = None, when: datetime | None = None) -> dict:
    return {
        "id": turn_id,
        "role": "patient",
        "content": content,
        "created_at": (when or datetime(2026, 5, 11, 14, 23, 0, tzinfo=timezone.utc)).isoformat(),
        "linked_gap_id": gap,
    }


def _assistant_turn(turn_id: str, content: str) -> dict:
    return {
        "id": turn_id,
        "role": "assistant",
        "content": content,
        "created_at": "2026-05-11T14:23:30+00:00",
        "linked_gap_id": None,
    }


def _gap_card(id_: str, title: str, prompt: str) -> dict:
    return {
        "id": id_,
        "category": "medication_reality",
        "title": title,
        "prompt": prompt,
        "why_it_matters": "demo",
        "status": "answered",
        "priority": 5,
        "evidence": [],
    }


# ---------------------------------------------------------------------------
# Headline case: stopped lisinopril 3 weeks ago
# ---------------------------------------------------------------------------


def test_med_stopped_emits_medication_statement_with_effective_end():
    """Acceptance §T1 item 1."""
    classifier = FakeTurnClassifier(
        by_turn_id={
            "t_4f2c9b": TurnClassification(
                kind="med_statement",
                status="stopped",
                drug_text="lisinopril",
                effective_end_iso="2026-04-20",
            )
        }
    )
    session = _session(
        turns=[_patient_turn("t_4f2c9b", "I stopped lisinopril about 3 weeks ago — was making me cough.", gap="medication-reality")],
        gap_cards=[_gap_card("medication-reality", "Check meds", "Anything different?")],
    )

    bundle = session_to_fhir_bundle(session, classifier=classifier, today_iso="2026-05-11")

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) == 1
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == "MedicationStatement"
    assert res["id"] == "pv-sess_a91c-t_4f2c9b-0"
    assert res["status"] == "stopped"
    assert res["medicationCodeableConcept"]["text"] == "lisinopril"
    assert res["subject"]["reference"] == "Patient/demo"
    assert res["informationSource"]["reference"] == "Patient/demo"
    assert res["effectivePeriod"]["end"] == "2026-04-20"

    # ≤25 days before today (today_iso = 2026-05-11). 2026-04-20 is 21 days before. OK.
    delta = datetime(2026, 5, 11) - datetime(2026, 4, 20)
    assert delta <= timedelta(days=25)


def test_med_active_emits_medication_statement_no_effective_end():
    classifier = FakeTurnClassifier(
        by_turn_id={
            "t_fish": TurnClassification(
                kind="med_statement",
                status="active",
                drug_text="fish oil",
            )
        }
    )
    session = _session(
        turns=[_patient_turn("t_fish", "Also taking fish oil every morning, my cardiologist suggested it.")],
    )
    bundle = session_to_fhir_bundle(session, classifier=classifier, today_iso="2026-05-11")
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == "MedicationStatement"
    assert res["status"] == "active"
    assert "effectivePeriod" not in res
    assert res["medicationCodeableConcept"]["text"] == "fish oil"


# ---------------------------------------------------------------------------
# Other kinds
# ---------------------------------------------------------------------------


def test_condition_emits_condition_with_unconfirmed_status_and_onset_period():
    classifier = FakeTurnClassifier(
        by_turn_id={
            "t_stone": TurnClassification(
                kind="condition",
                condition_text="kidney stone",
                onset_period=("2022-06-01", "2022-08-31"),
            )
        }
    )
    session = _session(turns=[_patient_turn("t_stone", "I had a kidney stone in summer 2022.")])
    bundle = session_to_fhir_bundle(session, classifier=classifier, today_iso="2026-05-11")
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == "Condition"
    assert res["verificationStatus"]["coding"][0]["code"] == "unconfirmed"
    assert res["code"]["text"] == "kidney stone"
    assert res["recorder"]["reference"] == "Patient/demo"
    assert res["onsetPeriod"] == {"start": "2022-06-01", "end": "2022-08-31"}


def test_goal_emits_goal_resource():
    classifier = FakeTurnClassifier(
        by_turn_id={
            "t_goal": TurnClassification(kind="goal", goal_text="Avoid another stroke.")
        }
    )
    session = _session(turns=[_patient_turn("t_goal", "My main goal is to avoid another stroke.")])
    bundle = session_to_fhir_bundle(session, classifier=classifier, today_iso="2026-05-11")
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == "Goal"
    assert res["lifecycleStatus"] == "active"
    assert res["description"]["text"] == "Avoid another stroke."
    assert res["expressedBy"]["reference"] == "Patient/demo"


def test_generic_emits_observation_with_value_string():
    classifier = FakeTurnClassifier(default=TurnClassification(kind="generic"))
    session = _session(turns=[_patient_turn("t_worry", "I've been worried about my memory lately.")])
    bundle = session_to_fhir_bundle(session, classifier=classifier, today_iso="2026-05-11")
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == "Observation"
    assert res["status"] == "final"
    assert res["code"]["coding"][0]["system"] == PATIENT_VOICE_CODE_SYSTEM
    assert res["code"]["coding"][0]["code"] == "patient-claim"
    assert res["category"][0]["coding"][0]["code"] == "survey"
    assert res["valueString"] == "I've been worried about my memory lately."


# ---------------------------------------------------------------------------
# Provenance shape on every resource (acceptance §T1 item 2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "classification,kind_name",
    [
        (TurnClassification(kind="med_statement", status="active", drug_text="aspirin"), "MedicationStatement"),
        (TurnClassification(kind="condition", condition_text="migraine"), "Condition"),
        (TurnClassification(kind="goal", goal_text="walk more"), "Goal"),
        (TurnClassification(kind="generic"), "Observation"),
    ],
)
def test_every_emitted_resource_carries_atlas_provenance_shape(classification, kind_name):
    classifier = FakeTurnClassifier(by_turn_id={"t_x": classification})
    session = _session(turns=[_patient_turn("t_x", "demo content", gap="medication-reality")])

    bundle = session_to_fhir_bundle(session, classifier=classifier)
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == kind_name

    assert res["meta"]["source"] == "patient-context://sess_a91c"
    ext_by_url = {e["url"]: e["valueString"] for e in res["meta"]["extension"]}
    assert ext_by_url[SOURCE_LABEL_URL] == "Patient (self-reported)"
    locator = ext_by_url[SOURCE_LOCATOR_URL]
    assert "session=sess_a91c" in locator
    assert "turn=t_x" in locator
    assert "gap=medication-reality" in locator


# ---------------------------------------------------------------------------
# Bundle envelope + edge cases
# ---------------------------------------------------------------------------


def test_bundle_is_valid_fhir_collection_envelope():
    """Acceptance §T1 item 3."""
    classifier = FakeTurnClassifier(default=TurnClassification(kind="generic"))
    session = _session(turns=[_patient_turn("t_a", "demo")])
    bundle = session_to_fhir_bundle(session, classifier=classifier)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["meta"]["source"] == "patient-context://sess_a91c"
    assert isinstance(bundle["entry"], list)


def test_assistant_turns_are_filtered_out():
    classifier = FakeTurnClassifier(default=TurnClassification(kind="generic"))
    session = _session(
        turns=[
            _patient_turn("t_a", "patient says hi"),
            _assistant_turn("t_b", "assistant replies"),
            _patient_turn("t_c", "patient says more"),
        ]
    )
    bundle = session_to_fhir_bundle(session, classifier=classifier)
    assert len(bundle["entry"]) == 2
    ids = [e["resource"]["id"] for e in bundle["entry"]]
    assert "pv-sess_a91c-t_a-0" in ids
    assert "pv-sess_a91c-t_c-0" in ids


def test_empty_session_yields_empty_bundle():
    bundle = session_to_fhir_bundle(_session(turns=[]))
    assert bundle["resourceType"] == "Bundle"
    assert bundle["entry"] == []


def test_med_classification_missing_required_field_falls_back_to_observation():
    """A med_statement classification without drug_text or status mustn't drop the turn.

    Per the §T1 failure mode: classifier mis-fires don't lose data — we
    emit a generic observation so the patient's words survive into the
    Bundle.
    """
    classifier = FakeTurnClassifier(
        by_turn_id={
            "t_partial": TurnClassification(kind="med_statement", status="active", drug_text=None)
        }
    )
    session = _session(turns=[_patient_turn("t_partial", "Some medication thing.")])
    bundle = session_to_fhir_bundle(session, classifier=classifier)
    res = bundle["entry"][0]["resource"]
    assert res["resourceType"] == "Observation"
    assert res["valueString"] == "Some medication thing."
