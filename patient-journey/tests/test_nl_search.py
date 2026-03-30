"""Tests for the natural language search engine."""

import sys
from pathlib import Path
from datetime import datetime

_REPO_ROOT = str(Path(__file__).parent.parent.parent)
_APP_DIR = str(Path(__file__).parent.parent)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _APP_DIR)

from fhir_explorer.parser.models import (
    PatientRecord,
    PatientSummary,
    MedicationRecord,
    ConditionRecord,
    EncounterRecord,
    ProcedureRecord,
    CodeableConcept,
    Period,
)
from views.nl_search import search_patient, _parse_time_filter


def _make_record(
    medications=None,
    conditions=None,
    encounters=None,
    procedures=None,
) -> PatientRecord:
    return PatientRecord(
        summary=PatientSummary(name="Test Patient"),
        medications=medications or [],
        conditions=conditions or [],
        encounters=encounters or [],
        procedures=procedures or [],
    )


def test_blood_thinner_search():
    """Searching 'blood thinners' should find anticoagulants."""
    record = _make_record(medications=[
        MedicationRecord(display="Warfarin 5mg", status="active",
                         authored_on=datetime(2022, 1, 1)),
        MedicationRecord(display="Lisinopril 10mg", status="active",
                         authored_on=datetime(2020, 6, 1)),
    ])
    results = search_patient(record, "blood thinners")
    assert len(results) >= 1
    assert any("Warfarin" in r.title for r in results)
    # Lisinopril is NOT a blood thinner
    assert not any("Lisinopril" in r.title for r in results)


def test_condition_search():
    """Searching a condition name should find matching conditions."""
    record = _make_record(conditions=[
        ConditionRecord(
            code=CodeableConcept(display="Type 2 Diabetes Mellitus"),
            clinical_status="active",
            onset_dt=datetime(2015, 3, 1),
        ),
    ])
    results = search_patient(record, "diabetes")
    assert len(results) >= 1
    assert any("Diabetes" in r.title for r in results)


def test_empty_query_returns_nothing():
    """Empty query should return no results."""
    record = _make_record(medications=[
        MedicationRecord(display="Warfarin 5mg", status="active"),
    ])
    results = search_patient(record, "")
    assert len(results) == 0


def test_time_filter_parsing():
    """Time filter phrases should be extracted from queries."""
    cleaned, cutoff = _parse_time_filter("blood thinners in the last 5 years")
    assert cutoff is not None
    assert "blood thinner" in cleaned
    assert "last 5 years" not in cleaned


def test_time_filter_no_phrase():
    """Queries without time phrases should have no cutoff."""
    cleaned, cutoff = _parse_time_filter("warfarin")
    assert cutoff is None
    assert cleaned == "warfarin"


def test_surgery_search():
    """Searching 'surgeries' should find procedures."""
    record = _make_record(procedures=[
        ProcedureRecord(
            code=CodeableConcept(display="Appendectomy"),
            status="completed",
            performed_period=Period(start=datetime(2020, 6, 15)),
        ),
    ])
    results = search_patient(record, "surgeries")
    assert len(results) >= 1
    assert any("Appendectomy" in r.title for r in results)
