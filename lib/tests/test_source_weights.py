"""Tests for source-weighted medication status resolution (T2).

Acceptance criteria from LLM-CONTEXT-AUGMENTATION-PLAN.md §T2:

- Patient asserts ``stopped``, EHR asserts ``active`` → merged status
  is ``stopped`` and provenance carries
  ``patient-voice-status-override`` on the patient-voice entity.
- Patient says nothing about dose; EHR asserts a dose → merged dose
  reflects the EHR (the patient doesn't override fields they didn't
  claim).
- Two non-patient sources disagree on status → existing behavior
  (most-recent wins by authored_on tiebreak; both votes weight 1.0).
- Patient asserts ``active``; EHR asserts ``stopped`` 6 months ago →
  patient wins (patient assertion is the newer, higher-weighted
  signal).

The plan also requires that the weight table live in exactly one
place — see ``test_weight_table_single_source_of_truth``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lib.harmonize.medications import merge_medications
from lib.harmonize.observations import SourceBundle
from lib.harmonize.provenance import (
    RESOLUTION_RULE_URL,
    SOURCE_LABEL_URL,
    mint_provenance,
)
from lib.harmonize.source_weights import (
    MEDICATION_STATUS_WEIGHTS,
    PATIENT_VOICE_SOURCE_PREFIX,
    is_patient_voice,
    weight_for_source,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _med_request(
    *,
    request_id: str,
    rxnorm: str,
    display: str,
    status: str,
    authored: datetime,
    meta_source: str | None = None,
) -> dict:
    res: dict = {
        "resourceType": "MedicationRequest",
        "id": request_id,
        "status": status,
        "authoredOn": authored.isoformat(),
        "medicationCodeableConcept": {
            "text": display,
            "coding": [
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rxnorm}
            ],
        },
    }
    if meta_source:
        res["meta"] = {"source": meta_source}
    return res


def _bundle(label: str, *resources: dict) -> SourceBundle:
    return SourceBundle(label=label, observations=list(resources))


# ---------------------------------------------------------------------------
# Weight table unit tests
# ---------------------------------------------------------------------------


def test_weight_for_patient_voice_status_is_five():
    assert weight_for_source("patient-context://sess_a91c", "medication.status") == 5.0


def test_weight_for_ehr_status_is_one():
    assert weight_for_source("DocumentReference/cedars-pdf", "medication.status") == 1.0


def test_weight_for_unknown_field_defaults_to_one():
    """Phase 1 only weights medication.status; everything else is 1.0."""
    assert weight_for_source(PATIENT_VOICE_SOURCE_PREFIX + "x", "medication.dose") == 1.0


def test_weight_for_no_meta_source_defaults_to_one():
    assert weight_for_source(None, "medication.status") == 1.0


def test_is_patient_voice_helper():
    assert is_patient_voice("patient-context://sess_a91c") is True
    assert is_patient_voice("DocumentReference/cedars") is False
    assert is_patient_voice(None) is False
    assert is_patient_voice("") is False


def test_weight_table_single_source_of_truth():
    """The plan requires the weight constants live in exactly one place.

    This is a soft check: the weight values are imported from
    ``lib.harmonize.source_weights`` and any change should land there.
    """
    assert MEDICATION_STATUS_WEIGHTS[PATIENT_VOICE_SOURCE_PREFIX] == 5.0
    assert MEDICATION_STATUS_WEIGHTS["*"] == 1.0


# ---------------------------------------------------------------------------
# Status resolution via merge_medications
# ---------------------------------------------------------------------------


def test_patient_stopped_overrides_ehr_active():
    """Headline demo case: Cedars + FH say active, patient says stopped."""
    cedars = _bundle(
        "Cedars-Sinai",
        _med_request(
            request_id="mr-cedars-lisinopril",
            rxnorm="29046",
            display="Lisinopril 10 MG Oral Tablet",
            status="active",
            authored=datetime(2025, 9, 1, tzinfo=timezone.utc),
        ),
    )
    fh = _bundle(
        "Function Health",
        _med_request(
            request_id="mr-fh-lisinopril",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="active",
            authored=datetime(2025, 11, 1, tzinfo=timezone.utc),
        ),
    )
    patient = _bundle(
        "Patient (self-reported)",
        _med_request(
            request_id="mr-pv-lisinopril",
            rxnorm="29046",
            display="lisinopril",
            status="stopped",
            authored=datetime(2026, 5, 11, tzinfo=timezone.utc),
            meta_source="patient-context://sess_a91c",
        ),
    )

    merged_list = merge_medications([cedars, fh, patient])
    assert len(merged_list) == 1
    merged = merged_list[0]
    assert merged.canonical_status == "stopped"
    assert merged.is_active is False


def test_patient_active_overrides_ehr_stopped_six_months_ago():
    """Patient assertion wins over a stale EHR stopped flag."""
    cedars = _bundle(
        "Cedars",
        _med_request(
            request_id="mr-cedars",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="stopped",
            authored=datetime(2025, 11, 1, tzinfo=timezone.utc),
        ),
    )
    patient = _bundle(
        "Patient",
        _med_request(
            request_id="mr-pv",
            rxnorm="29046",
            display="lisinopril",
            status="active",
            authored=datetime(2026, 5, 11, tzinfo=timezone.utc),
            meta_source="patient-context://sess_a91c",
        ),
    )

    merged_list = merge_medications([cedars, patient])
    assert merged_list[0].canonical_status == "active"
    assert merged_list[0].is_active is True


def test_two_ehr_sources_disagree_most_recent_wins():
    """No patient voice → existing tiebreak behavior (highest authored_on among tied weights)."""
    cedars = _bundle(
        "Cedars",
        _med_request(
            request_id="mr-cedars",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="active",
            authored=datetime(2025, 6, 1, tzinfo=timezone.utc),
        ),
    )
    fh = _bundle(
        "Function Health",
        _med_request(
            request_id="mr-fh",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="stopped",
            authored=datetime(2025, 11, 1, tzinfo=timezone.utc),
        ),
    )
    merged = merge_medications([cedars, fh])[0]
    assert merged.canonical_status == "stopped"  # FH is the more recent vote


def test_all_sources_agree_active():
    cedars = _bundle(
        "Cedars",
        _med_request(
            request_id="mr-c",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="active",
            authored=datetime(2025, 9, 1, tzinfo=timezone.utc),
        ),
    )
    fh = _bundle(
        "Function Health",
        _med_request(
            request_id="mr-f",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="active",
            authored=datetime(2025, 11, 1, tzinfo=timezone.utc),
        ),
    )
    merged = merge_medications([cedars, fh])[0]
    assert merged.canonical_status == "active"


def test_no_source_records_status_defaults_to_active():
    """When no source carries a status (PDFs often don't), is_active stays True."""
    pdf = _bundle(
        "Cedars-PDF",
        {
            "resourceType": "MedicationRequest",
            "id": "mr-pdf",
            "medicationCodeableConcept": {
                "text": "lisinopril",
                "coding": [
                    {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "29046"}
                ],
            },
            "authoredOn": datetime(2025, 11, 1, tzinfo=timezone.utc).isoformat(),
        },
    )
    merged = merge_medications([pdf])[0]
    assert merged.canonical_status is None
    assert merged.is_active is True  # default-active when no status seen


# ---------------------------------------------------------------------------
# Provenance — resolution-rule extension fires on override
# ---------------------------------------------------------------------------


def test_provenance_attaches_resolution_rule_to_patient_voice_entity():
    """Acceptance §T2: provenance carries the rule code on the patient entity."""
    cedars = _bundle(
        "Cedars",
        _med_request(
            request_id="mr-cedars",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="active",
            authored=datetime(2025, 9, 1, tzinfo=timezone.utc),
        ),
    )
    patient = _bundle(
        "Patient",
        _med_request(
            request_id="mr-pv",
            rxnorm="29046",
            display="lisinopril",
            status="stopped",
            authored=datetime(2026, 5, 11, tzinfo=timezone.utc),
            meta_source="patient-context://sess_a91c",
        ),
    )
    merged = merge_medications([cedars, patient])[0]
    provenance = mint_provenance(merged)

    # Find the entity whose source_ref matches the patient MR.
    patient_entity = next(
        e for e in provenance["entity"] if e["what"]["reference"].endswith("mr-pv")
    )
    cedars_entity = next(
        e for e in provenance["entity"] if e["what"]["reference"].endswith("mr-cedars")
    )

    ext_urls_patient = {e["url"] for e in patient_entity["extension"]}
    ext_urls_cedars = {e["url"] for e in cedars_entity["extension"]}

    assert RESOLUTION_RULE_URL in ext_urls_patient
    assert RESOLUTION_RULE_URL not in ext_urls_cedars

    rule_ext = next(
        e for e in patient_entity["extension"] if e["url"] == RESOLUTION_RULE_URL
    )
    assert rule_ext["valueString"] == "patient-voice-status-override"
    # Source-label preserved.
    label_ext = next(e for e in patient_entity["extension"] if e["url"] == SOURCE_LABEL_URL)
    assert label_ext["valueString"] == "Patient"


def test_provenance_omits_rule_when_sources_agree():
    """When everyone agrees, the resolution-rule extension is absent."""
    cedars = _bundle(
        "Cedars",
        _med_request(
            request_id="mr-c",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="stopped",
            authored=datetime(2025, 9, 1, tzinfo=timezone.utc),
        ),
    )
    patient = _bundle(
        "Patient",
        _med_request(
            request_id="mr-p",
            rxnorm="29046",
            display="lisinopril",
            status="stopped",
            authored=datetime(2026, 5, 11, tzinfo=timezone.utc),
            meta_source="patient-context://sess_a91c",
        ),
    )
    merged = merge_medications([cedars, patient])[0]
    provenance = mint_provenance(merged)
    for entity in provenance["entity"]:
        assert all(
            e["url"] != RESOLUTION_RULE_URL for e in entity["extension"]
        ), "no entity should carry the override when sources agree"


def test_provenance_omits_rule_when_no_patient_voice():
    """Two EHR sources disagreeing must NOT mint the patient-voice extension."""
    cedars = _bundle(
        "Cedars",
        _med_request(
            request_id="mr-c",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="active",
            authored=datetime(2025, 6, 1, tzinfo=timezone.utc),
        ),
    )
    fh = _bundle(
        "FH",
        _med_request(
            request_id="mr-f",
            rxnorm="29046",
            display="Lisinopril 10mg",
            status="stopped",
            authored=datetime(2025, 11, 1, tzinfo=timezone.utc),
        ),
    )
    merged = merge_medications([cedars, fh])[0]
    provenance = mint_provenance(merged)
    for entity in provenance["entity"]:
        assert all(
            e["url"] != RESOLUTION_RULE_URL for e in entity["extension"]
        ), "rule should only fire when patient-voice disagrees with another source"
