import pytest

from api.trust.redactions import PRESETS, apply_preset


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        apply_preset("nope", {})


def test_de_id_v1_strips_direct_identifiers():
    out = apply_preset(
        "de-id-v1",
        {
            "name": "M. Hollister",
            "mrn": "8.4127.881",
            "dob": "1957-08-04",
            "diagnoses": [{"code": "C92.10", "display": "CML"}],
        },
    )
    assert "name" not in out and "mrn" not in out and "dob" not in out
    assert out["diagnoses"][0]["code"] == "C92.10"


def test_de_id_v2_buckets_age():
    out = apply_preset(
        "de-id-v2",
        {"demographics": {"age": 68, "sex": "F"}},
    )
    assert out["demographics"]["age-band"] == "65-69"
    assert "age" not in out["demographics"]


def test_de_id_v3_truncates_zip():
    out = apply_preset(
        "de-id-v3",
        {"demographics": {"age": 68, "sex": "F", "geography": {"zip": "94110", "city": "SF"}}},
    )
    assert out["demographics"]["geography"]["zip3"] == "941**"
    assert "city" not in out["demographics"]["geography"]


def test_research_grade_drops_notes():
    out = apply_preset(
        "research-grade",
        {"diagnoses": [{"code": "C92.10", "note": "free text PHI"}]},
    )
    assert "note" not in out["diagnoses"][0]


def test_minimal_passthrough_keeps_identifiers():
    src = {"name": "M. Hollister", "mrn": "8.4127.881"}
    assert apply_preset("minimal", src) == src


def test_all_presets_registered():
    assert set(PRESETS) >= {"de-id-v1", "de-id-v2", "de-id-v3", "research-grade", "minimal"}
