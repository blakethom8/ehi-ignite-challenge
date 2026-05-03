"""Tests for the drug classifier and safety flag generator."""

from lib.fhir_parser.models import MedicationRecord
from lib.clinical.drug_classifier import DrugClassifier


def test_warfarin_classified_as_anticoagulant():
    classifier = DrugClassifier()
    med = MedicationRecord(display="Warfarin 5mg Oral Tablet", rxnorm_code="11289")
    classes = classifier.classify_medication(med)
    assert "anticoagulants" in classes


def test_lisinopril_classified_as_ace_inhibitor():
    classifier = DrugClassifier()
    med = MedicationRecord(display="Lisinopril 10 MG Oral Tablet")
    classes = classifier.classify_medication(med)
    assert "ace_inhibitors" in classes


def test_oxycodone_classified_as_opioid():
    classifier = DrugClassifier()
    med = MedicationRecord(display="Acetaminophen 325 MG / oxyCODONE Hydrochloride 5 MG Oral Tablet")
    classes = classifier.classify_medication(med)
    assert "opioids" in classes


def test_unclassified_med_returns_empty():
    classifier = DrugClassifier()
    med = MedicationRecord(display="Amoxicillin 500 MG Oral Capsule")
    classes = classifier.classify_medication(med)
    assert classes == []


def test_safety_flags_include_all_classes():
    classifier = DrugClassifier()
    flags = classifier.generate_safety_flags([])
    assert len(flags) == len(classifier.class_keys)
    assert all(f.status == "NONE" for f in flags)


def test_active_med_produces_active_flag():
    classifier = DrugClassifier()
    med = MedicationRecord(
        display="Warfarin 5mg Oral Tablet",
        status="active",
    )
    flags = classifier.generate_safety_flags([med])
    anticoag = next(f for f in flags if f.class_key == "anticoagulants")
    assert anticoag.status == "ACTIVE"


def test_stopped_med_produces_historical_flag():
    classifier = DrugClassifier()
    med = MedicationRecord(
        display="Warfarin 5mg Oral Tablet",
        status="stopped",
    )
    flags = classifier.generate_safety_flags([med])
    anticoag = next(f for f in flags if f.class_key == "anticoagulants")
    assert anticoag.status == "HISTORICAL"


if __name__ == "__main__":
    test_warfarin_classified_as_anticoagulant()
    test_lisinopril_classified_as_ace_inhibitor()
    test_oxycodone_classified_as_opioid()
    test_unclassified_med_returns_empty()
    test_safety_flags_include_all_classes()
    test_active_med_produces_active_flag()
    test_stopped_med_produces_historical_flag()
    print("All tests passed!")
