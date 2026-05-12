"""Tests for ``lib.patient_voice.ingest`` (T3 of the Phase 1 plan).

Acceptance criteria from LLM-CONTEXT-AUGMENTATION-PLAN.md §T3:

- Patient-voice bundles on disk are discovered and yielded as
  SourceBundle instances.
- MedicationStatement entries are converted to MedicationRequest
  shape so the existing harmonizer can consume them.
- Resources for the wrong patient are filtered out (defence in depth).
- An end-to-end merge of (Cedars MedicationRequest + patient-voice
  MedicationStatement) produces a merged lisinopril row with
  ``status=stopped`` and provenance carrying the override rule.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lib.harmonize.medications import merge_medications
from lib.harmonize.observations import SourceBundle
from lib.harmonize.provenance import RESOLUTION_RULE_URL, mint_provenance
from lib.patient_voice.ingest import (
    PATIENT_VOICE_LABEL,
    patient_voice_source_bundles,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_bundle(store_root: Path, patient_id: str, session_id: str, *resources: dict) -> Path:
    fhir_dir = store_root / patient_id / "fhir"
    fhir_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"source": f"patient-context://{session_id}"},
        "entry": [{"resource": r} for r in resources],
    }
    path = fhir_dir / f"{session_id}.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path


def _med_statement_stopped_lisinopril(*, patient_id: str, session_id: str) -> dict:
    return {
        "resourceType": "MedicationStatement",
        "id": f"pv-{session_id}-t1-0",
        "status": "stopped",
        "medicationCodeableConcept": {
            "text": "lisinopril",
            "coding": [
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "29046"}
            ],
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "informationSource": {"reference": f"Patient/{patient_id}"},
        "dateAsserted": "2026-05-11T14:23:00+00:00",
        "effectivePeriod": {"end": "2026-04-20"},
        "note": [{"text": "I stopped lisinopril about 3 weeks ago — was making me cough."}],
        "meta": {"source": f"patient-context://{session_id}"},
    }


def _med_request_active_lisinopril(*, request_id: str) -> dict:
    return {
        "resourceType": "MedicationRequest",
        "id": request_id,
        "status": "active",
        "authoredOn": "2025-09-01T00:00:00+00:00",
        "medicationCodeableConcept": {
            "text": "Lisinopril 10 MG Oral Tablet",
            "coding": [
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "29046"}
            ],
        },
    }


# ---------------------------------------------------------------------------
# Ingest discovery
# ---------------------------------------------------------------------------


def test_patient_voice_source_bundles_no_directory(tmp_path: Path):
    """Returns [] cleanly when no patient-voice FHIR exists on disk."""
    assert patient_voice_source_bundles("demo", resource_type="MedicationRequest", store_root=tmp_path) == []


def test_patient_voice_bundles_medication_statement_converted_to_request(tmp_path: Path):
    _write_bundle(
        tmp_path,
        "demo",
        "sess_a91c",
        _med_statement_stopped_lisinopril(patient_id="demo", session_id="sess_a91c"),
    )
    bundles = patient_voice_source_bundles("demo", resource_type="MedicationRequest", store_root=tmp_path)
    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.label == PATIENT_VOICE_LABEL
    assert len(bundle.observations) == 1
    mr = bundle.observations[0]
    assert mr["resourceType"] == "MedicationRequest"
    assert mr["status"] == "stopped"
    assert mr["medicationCodeableConcept"]["text"] == "lisinopril"
    assert mr["authoredOn"] == "2026-05-11T14:23:00+00:00"
    assert mr["meta"]["source"] == "patient-context://sess_a91c"


def test_patient_voice_bundles_filters_subject_mismatch(tmp_path: Path):
    """Resources for a different patient are filtered out at entry level."""
    other = _med_statement_stopped_lisinopril(patient_id="someone-else", session_id="sess_a91c")
    correct = _med_statement_stopped_lisinopril(patient_id="demo", session_id="sess_a91c")
    correct["id"] = "pv-sess_a91c-t2-0"
    _write_bundle(tmp_path, "demo", "sess_a91c", other, correct)
    bundles = patient_voice_source_bundles("demo", resource_type="MedicationRequest", store_root=tmp_path)
    assert len(bundles) == 1
    assert len(bundles[0].observations) == 1
    assert bundles[0].observations[0]["id"] == "pv-sess_a91c-t2-0"


def test_patient_voice_bundles_unknown_resource_type_returns_empty(tmp_path: Path):
    _write_bundle(
        tmp_path, "demo", "sess_a91c",
        _med_statement_stopped_lisinopril(patient_id="demo", session_id="sess_a91c"),
    )
    assert patient_voice_source_bundles("demo", resource_type="Encounter", store_root=tmp_path) == []


def test_patient_voice_bundles_pass_through_conditions(tmp_path: Path):
    """Condition resources flow through without shape conversion."""
    cond = {
        "resourceType": "Condition",
        "id": "pv-sess-x-t1-0",
        "code": {"text": "kidney stone"},
        "subject": {"reference": "Patient/demo"},
        "verificationStatus": {
            "coding": [
                {"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                 "code": "unconfirmed"}
            ]
        },
        "meta": {"source": "patient-context://sess-x"},
    }
    _write_bundle(tmp_path, "demo", "sess-x", cond)
    bundles = patient_voice_source_bundles("demo", resource_type="Condition", store_root=tmp_path)
    assert len(bundles) == 1
    assert bundles[0].observations[0]["code"]["text"] == "kidney stone"


# ---------------------------------------------------------------------------
# End-to-end: discovery + merge + provenance
# ---------------------------------------------------------------------------


def test_end_to_end_patient_voice_overrides_ehr_in_merged_record(tmp_path: Path):
    """Headline §T3 acceptance: drop a patient-voice bundle + a Cedars-style
    MedicationRequest into the merger and verify the merged lisinopril row
    shows status=stopped with the override rule code on its provenance.
    """
    # Cedars source — active flag, recorded 2025-09-01
    cedars = SourceBundle(label="Cedars-Sinai", observations=[_med_request_active_lisinopril(request_id="mr-cedars-1")])

    # Patient-voice — stopped, asserted 2026-05-11
    _write_bundle(
        tmp_path,
        "demo",
        "sess_a91c",
        _med_statement_stopped_lisinopril(patient_id="demo", session_id="sess_a91c"),
    )
    patient_bundles = patient_voice_source_bundles(
        "demo", resource_type="MedicationRequest", store_root=tmp_path
    )

    merged_list = merge_medications([cedars, *patient_bundles])
    assert len(merged_list) == 1
    merged = merged_list[0]
    assert merged.canonical_status == "stopped"
    assert merged.is_active is False
    labels = {s.source_label for s in merged.sources}
    assert {"Cedars-Sinai", PATIENT_VOICE_LABEL} <= labels

    # Provenance carries the override rule on the patient-voice entity.
    provenance = mint_provenance(merged)
    patient_entity = next(
        e for e in provenance["entity"]
        if e["what"]["reference"].endswith("pv-sess_a91c-t1-0")
    )
    cedars_entity = next(
        e for e in provenance["entity"]
        if e["what"]["reference"].endswith("mr-cedars-1")
    )
    patient_urls = {e["url"] for e in patient_entity["extension"]}
    cedars_urls = {e["url"] for e in cedars_entity["extension"]}
    assert RESOLUTION_RULE_URL in patient_urls
    assert RESOLUTION_RULE_URL not in cedars_urls


def test_multiple_sessions_yield_multiple_bundles(tmp_path: Path):
    """Two patient-context sessions on disk produce two separate SourceBundles."""
    _write_bundle(
        tmp_path, "demo", "sess-one",
        _med_statement_stopped_lisinopril(patient_id="demo", session_id="sess-one"),
    )
    _write_bundle(
        tmp_path, "demo", "sess-two",
        {
            "resourceType": "MedicationStatement",
            "id": "pv-sess-two-t1-0",
            "status": "active",
            "medicationCodeableConcept": {"text": "fish oil"},
            "subject": {"reference": "Patient/demo"},
            "dateAsserted": "2026-05-11T14:23:00+00:00",
            "meta": {"source": "patient-context://sess-two"},
        },
    )
    bundles = patient_voice_source_bundles(
        "demo", resource_type="MedicationRequest", store_root=tmp_path
    )
    assert len(bundles) == 2
