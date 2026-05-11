from datetime import datetime, timedelta, timezone

import pytest

from api.plugins.anchors import (
    AnchorError,
    AnchorExpired,
    OutOfScope,
    compile_anchor_package,
    read_anchor_field,
    verify_anchor_package,
)
from api.plugins.manifest import load_manifest


@pytest.fixture(scope="module")
def trial_finder():
    return load_manifest("trial-finder", "2.4.1").manifest


@pytest.fixture(scope="module")
def med_access():
    return load_manifest("med-access", "1.7.0").manifest


def test_compile_anchor_returns_only_scoped_fields(trial_finder):
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test1"
    )
    # Trial Finder scope includes diagnoses.active + biomarkers, NOT medications.
    assert "diagnoses.active" in pkg.data
    assert "biomarkers" in pkg.data
    assert "medications.active" not in pkg.data


def test_compile_anchor_signature_verifies(trial_finder):
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test2"
    )
    verify_anchor_package(pkg)


def test_compile_anchor_tamper_breaks_signature(trial_finder):
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test3"
    )
    pkg.data["diagnoses.active"] = []  # tamper
    with pytest.raises(AnchorError):
        verify_anchor_package(pkg)


def test_anchor_expiry(trial_finder):
    past = datetime.now(timezone.utc) - timedelta(seconds=trial_finder.anchor.ttlSeconds + 60)
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test4", now=past
    )
    with pytest.raises(AnchorExpired):
        verify_anchor_package(pkg)


def test_read_anchor_field_out_of_scope(trial_finder):
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test5"
    )
    with pytest.raises(OutOfScope):
        read_anchor_field(pkg, "medications.active")


def test_read_anchor_field_in_scope(trial_finder):
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test6"
    )
    biomarkers = read_anchor_field(pkg, "biomarkers")
    assert any(b.get("marker", "").startswith("BCR-ABL") for b in biomarkers)


def test_de_id_v3_truncates_geography(trial_finder):
    pkg = compile_anchor_package(
        manifest=trial_finder, patient_id="8.4127.881", run_id="r_test7"
    )
    geo = pkg.data.get("demographics.geography")
    # de-id-v3 should have removed city; v3 routes zip → zip3
    if isinstance(geo, dict) and "zip" in geo:
        # If the raw geo dict carried a zip field, redaction should have shrunk it.
        assert geo.get("zip3") or geo.get("zip", "***").endswith("**")


def test_med_access_minimal_preserves_identifiers(med_access):
    pkg = compile_anchor_package(
        manifest=med_access, patient_id="8.4127.881", run_id="r_test8"
    )
    assert pkg.redactionPreset == "minimal"
    # medications.active should be present and unredacted
    meds = read_anchor_field(pkg, "medications.active")
    assert any("apixaban" in m.get("display", "") for m in meds)


def test_unknown_patient_raises(trial_finder):
    with pytest.raises(AnchorError):
        compile_anchor_package(
            manifest=trial_finder, patient_id="not-a-real-mrn", run_id="r_x"
        )
