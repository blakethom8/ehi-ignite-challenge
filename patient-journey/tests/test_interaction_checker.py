"""Tests for the drug interaction checker."""

import sys
from pathlib import Path

# Add paths for imports
_REPO_ROOT = str(Path(__file__).parent.parent.parent)
_APP_DIR = str(Path(__file__).parent.parent)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _APP_DIR)

from lib.fhir_parser.models import MedicationRecord
from lib.clinical.interaction_checker import check_interactions, DrugInteraction
from lib.clinical.drug_classifier import DrugClassifier


def _make_med(display: str, status: str = "active", rxnorm: str = "") -> MedicationRecord:
    return MedicationRecord(
        display=display,
        status=status,
        rxnorm_code=rxnorm,
    )


def test_no_interactions_with_single_class():
    """A patient on only anticoagulants should have no interactions."""
    meds = [_make_med("Warfarin 5mg")]
    report = check_interactions(meds)
    assert report.total_count == 0


def test_anticoagulant_nsaid_critical_interaction():
    """Warfarin + Ibuprofen should trigger a critical interaction."""
    meds = [
        _make_med("Warfarin 5mg"),
        _make_med("Ibuprofen 400mg"),
    ]
    report = check_interactions(meds)
    assert report.has_critical
    assert report.critical_count >= 1
    # Find the specific interaction
    found = [i for i in report.interactions
             if {i.class_a, i.class_b} == {"anticoagulants", "nsaids"}]
    assert len(found) == 1
    assert found[0].severity == "critical"


def test_anticoagulant_antiplatelet_critical():
    """Warfarin + Aspirin should trigger critical bleeding risk."""
    meds = [
        _make_med("Warfarin 5mg"),
        _make_med("Aspirin 81mg"),
    ]
    report = check_interactions(meds)
    assert report.has_critical


def test_active_only_filter():
    """Historical medications should be excluded when active_only=True."""
    meds = [
        _make_med("Warfarin 5mg", status="active"),
        _make_med("Ibuprofen 400mg", status="stopped"),
    ]
    # Active only — no interaction (ibuprofen is stopped)
    report_active = check_interactions(meds, active_only=True)
    critical_active = [i for i in report_active.interactions
                       if {i.class_a, i.class_b} == {"anticoagulants", "nsaids"}]
    assert len(critical_active) == 0

    # All medications — interaction found
    report_all = check_interactions(meds, active_only=False)
    critical_all = [i for i in report_all.interactions
                    if {i.class_a, i.class_b} == {"anticoagulants", "nsaids"}]
    assert len(critical_all) == 1


def test_no_meds_no_interactions():
    """Empty medication list should produce no interactions."""
    report = check_interactions([])
    assert report.total_count == 0
    assert not report.has_critical


def test_multiple_interactions():
    """Patient on warfarin + aspirin + ibuprofen should have multiple interactions."""
    meds = [
        _make_med("Warfarin 5mg"),
        _make_med("Aspirin 81mg"),
        _make_med("Ibuprofen 400mg"),
    ]
    report = check_interactions(meds)
    # Should have: anticoagulant-antiplatelet, anticoagulant-nsaid, antiplatelet-nsaid
    assert report.total_count >= 3


def test_opioid_psych_warning():
    """Opioid + SSRI should trigger a warning."""
    meds = [
        _make_med("Oxycodone 5mg"),
        _make_med("Sertraline 100mg"),
    ]
    report = check_interactions(meds)
    found = [i for i in report.interactions
             if {i.class_a, i.class_b} == {"opioids", "psych_medications"}]
    assert len(found) == 1
    assert found[0].severity == "warning"
