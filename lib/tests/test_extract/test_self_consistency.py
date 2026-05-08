"""Tests for GOLD-T02: self-consistency wrapper (run_count field + intersection).

Covers:
1. test_extraction_pass_default_run_count_one       — backward compat: ExtractionPass() defaults to run_count=1
2. test_extraction_pass_run_count_two_sets_field    — explicit run_count=2 succeeds
3. test_intersect_pass_outputs_single_run_pass_through — list of one output → returned unchanged
4. test_intersect_observations_keeps_only_common_facts — two runs with overlap → only overlap survives
5. test_intersect_conditions_normalized_display_match  — same condition, different case/punctuation → matched
6. test_intersect_practitioners_match_by_npi           — same NPI → matched even if names differ
7. test_intersect_returns_correct_extraction_type      — output preserves the Pydantic wrapper type
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Test 1 — backward compat: default run_count = 1
# ---------------------------------------------------------------------------


def test_extraction_pass_default_run_count_one() -> None:
    """ExtractionPass() with no run_count argument defaults to run_count=1.

    This guarantees that every existing pipeline that constructs ExtractionPass
    without a run_count is unaffected by GOLD-T02.
    """
    from lib.extract.pipelines.multipass_fhir import ExtractionPass, ConditionExtraction

    p = ExtractionPass(
        name="conditions",
        schema=ConditionExtraction,
        system_prompt="test prompt",
    )
    assert p.run_count == 1, (
        f"Expected run_count=1, got {p.run_count}"
    )


# ---------------------------------------------------------------------------
# Test 2 — explicit run_count=2 is stored
# ---------------------------------------------------------------------------


def test_extraction_pass_run_count_two_sets_field() -> None:
    """ExtractionPass(run_count=2) stores run_count=2 correctly."""
    from lib.extract.pipelines.multipass_fhir import ExtractionPass, LabObservationExtraction

    p = ExtractionPass(
        name="lab_observations",
        schema=LabObservationExtraction,
        system_prompt="lab prompt",
        run_count=2,
    )
    assert p.run_count == 2, (
        f"Expected run_count=2, got {p.run_count}"
    )


# ---------------------------------------------------------------------------
# Test 3 — single-run pass-through
# ---------------------------------------------------------------------------


def test_intersect_pass_outputs_single_run_pass_through() -> None:
    """When only one output is supplied, _intersect_pass_outputs returns it unchanged."""
    from lib.extract.pipelines.multipass_fhir import (
        _intersect_pass_outputs,
        LabObservationExtraction,
        LabObservationEntry,
    )

    entry = LabObservationEntry(test_name="Creatinine", value_quantity=1.2)
    single = LabObservationExtraction(observations=[entry])
    result = _intersect_pass_outputs("lab_observations", [single])

    assert result is single, (
        "_intersect_pass_outputs with a single output must return that exact object"
    )


# ---------------------------------------------------------------------------
# Test 4 — observations: only the intersection survives
# ---------------------------------------------------------------------------


def test_intersect_observations_keeps_only_common_facts() -> None:
    """Two LabObservationExtraction outputs with overlapping + unique facts.

    Run A: Creatinine 1.2, Glucose 95
    Run B: Creatinine 1.2, HbA1c 6.1

    Expected intersection: Creatinine 1.2 only.
    """
    from lib.extract.pipelines.multipass_fhir import (
        _intersect_pass_outputs,
        LabObservationExtraction,
        LabObservationEntry,
    )

    creatinine = LabObservationEntry(test_name="Creatinine", value_quantity=1.2)
    glucose = LabObservationEntry(test_name="Glucose", value_quantity=95.0)
    hba1c = LabObservationEntry(test_name="HbA1c", value_quantity=6.1)

    run_a = LabObservationExtraction(observations=[creatinine, glucose])
    run_b = LabObservationExtraction(observations=[creatinine, hba1c])

    result = _intersect_pass_outputs("lab_observations", [run_a, run_b])

    assert isinstance(result, LabObservationExtraction)
    names = [e.test_name for e in result.observations]
    assert "Creatinine" in names, "Creatinine (in both runs) must survive"
    assert "Glucose" not in names, "Glucose (only in run A) must be filtered out"
    assert "HbA1c" not in names, "HbA1c (only in run B) must be filtered out"
    assert len(result.observations) == 1, (
        f"Expected 1 observation after intersection, got {len(result.observations)}"
    )


# ---------------------------------------------------------------------------
# Test 5 — conditions: normalized display match (case + punctuation)
# ---------------------------------------------------------------------------


def test_intersect_conditions_normalized_display_match() -> None:
    """Same condition with slightly different display text in two runs
    (different casing, trailing punctuation) should be matched as the same
    fact.

    The match key uses _normalize_text() which lowercases and strips
    non-word chars, so 'Allergic Rhinitis.' and 'allergic rhinitis' both
    normalize to 'allergic rhinitis'.
    """
    from lib.extract.pipelines.multipass_fhir import (
        _intersect_pass_outputs,
        ConditionExtraction,
        ConditionEntry,
    )

    # Run A: condition with trailing period and title case
    cond_a = ConditionEntry(display="Allergic Rhinitis.", icd_10_cm_code=None)
    # Run B: same condition, lowercase, no punctuation
    cond_b = ConditionEntry(display="allergic rhinitis", icd_10_cm_code=None)

    run_a = ConditionExtraction(conditions=[cond_a])
    run_b = ConditionExtraction(conditions=[cond_b])

    result = _intersect_pass_outputs("conditions", [run_a, run_b])

    assert isinstance(result, ConditionExtraction)
    assert len(result.conditions) == 1, (
        f"Normalized display match failed: expected 1 condition, got "
        f"{len(result.conditions)}: {[c.display for c in result.conditions]}"
    )


# ---------------------------------------------------------------------------
# Test 6 — practitioners: match by NPI
# ---------------------------------------------------------------------------


def test_intersect_practitioners_match_by_npi() -> None:
    """Two runs each containing a practitioner with the same NPI but slightly
    different display names should be matched as the same practitioner.

    Run A: NPI=1234567890, display_name="Steven Krems MD"
    Run B: NPI=1234567890, display_name="S. Krems, MD"

    → Intersection: one practitioner (from run A).
    """
    from lib.extract.pipelines.multipass_fhir import (
        _intersect_pass_outputs,
        PractitionerExtraction,
        PractitionerEntry,
    )

    prac_a = PractitionerEntry(npi="1234567890", display_name="Steven Krems MD")
    prac_b = PractitionerEntry(npi="1234567890", display_name="S. Krems, MD")

    run_a = PractitionerExtraction(practitioners=[prac_a])
    run_b = PractitionerExtraction(practitioners=[prac_b])

    result = _intersect_pass_outputs("practitioner", [run_a, run_b])

    assert isinstance(result, PractitionerExtraction)
    assert len(result.practitioners) == 1, (
        f"Expected 1 practitioner after NPI-keyed intersection, got "
        f"{len(result.practitioners)}"
    )
    assert result.practitioners[0].npi == "1234567890"


# ---------------------------------------------------------------------------
# Test 7 — output preserves the correct Pydantic wrapper type
# ---------------------------------------------------------------------------


def test_intersect_returns_correct_extraction_type() -> None:
    """Input is LabObservationExtraction → output is also LabObservationExtraction.

    The intersection helper must reconstruct the correct wrapper type, not a
    generic BaseModel or the wrong extraction class.
    """
    from lib.extract.pipelines.multipass_fhir import (
        _intersect_pass_outputs,
        LabObservationExtraction,
        LabObservationEntry,
    )

    entry = LabObservationEntry(test_name="Sodium", value_quantity=140.0)
    run_a = LabObservationExtraction(observations=[entry])
    run_b = LabObservationExtraction(observations=[entry])

    result = _intersect_pass_outputs("lab_observations", [run_a, run_b])

    assert type(result) is LabObservationExtraction, (
        f"Expected LabObservationExtraction, got {type(result).__name__}"
    )
