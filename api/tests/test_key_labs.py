"""Tests for key-lab interpretation helpers."""

from __future__ import annotations

from api.routers.patients import _interpret_lab_value


def test_key_lab_alternate_loinc_codes_use_review_thresholds() -> None:
    """Panel LOINCs should not show unknown range when thresholds exist."""
    hematocrit = _interpret_lab_value("20570-8", 62.0)
    inr = _interpret_lab_value("34714-6", 5.4)

    assert hematocrit == ("high", "critical", 24.0, 52.0, "%", "24-52 %")
    assert inr == ("high", "critical", None, 3.0, "", "<= 3")


def test_key_lab_panel_codes_include_basic_reference_ranges() -> None:
    wbc = _interpret_lab_value("6690-2", 5.1)
    bun = _interpret_lab_value("3094-0", 16.0)

    assert wbc == ("normal", None, 4.0, 11.0, "10*3/uL", "4-11 10*3/uL")
    assert bun == ("normal", None, 7.0, 20.0, "mg/dL", "7-20 mg/dL")


def test_key_lab_source_reference_range_overrides_review_threshold_range() -> None:
    creatinine = _interpret_lab_value("2160-0", 1.3, 0.4, 1.2, "mg/dL")

    assert creatinine == ("high", None, 0.4, 1.2, "mg/dL", "0.4-1.2 mg/dL")


def test_key_lab_source_reference_range_can_interpret_unconfigured_loinc() -> None:
    ferritin = _interpret_lab_value("2276-4", 12.0, 20.0, 300.0, "ng/mL")

    assert ferritin == ("low", None, 20.0, 300.0, "ng/mL", "20-300 ng/mL")
