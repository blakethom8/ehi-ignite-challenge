"""
tests.extract.test_to_fhir
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the extraction-to-FHIR converters (to_fhir.py).

These tests verify that:
 - lab_result_to_observation emits all required FHIR meta fields
 - LOINC code is included in the coding array when provided
 - LOINC coding is omitted (not fabricated) when loinc_code is None
 - condition_to_fhir preserves source_text as Condition.note[0].text
"""

from __future__ import annotations

import pytest

from ehi_atlas.extract.schemas import BBox, ExtractedCondition, ExtractedLabResult
from ehi_atlas.extract.to_fhir import condition_to_fhir, lab_result_to_observation

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

_EXT_BASE = "https://ehi-atlas.example/fhir/StructureDefinition"
_PATIENT_ID = "Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61"
_SOURCE_ID = "quest-2025-09-12"
_MODEL = "claude-opus-4-7"
_CONFIDENCE = 0.97
_PROMPT_VER = "v0.1.0"


def _creatinine_result(loinc: str | None = "2160-0") -> ExtractedLabResult:
    return ExtractedLabResult(
        test_name="Creatinine",
        loinc_code=loinc,
        value_quantity=1.4,
        unit="mg/dL",
        reference_range_low=0.6,
        reference_range_high=1.3,
        flag="H",
        effective_date="2025-09-12",
        bbox=BBox(page=2, x1=72, y1=574, x2=540, y2=590),
    )


def _chest_tightness_condition(bbox: BBox | None = None) -> ExtractedCondition:
    return ExtractedCondition(
        label="Chest tightness on exertion",
        snomed_ct_code="23924001",
        onset_date="2025-11-01",
        source_text=(
            "occasional chest tightness on exertion since "
            "approximately November of last year"
        ),
        bbox=bbox,
    )


def _call_lab(**kwargs):
    defaults = dict(
        result=_creatinine_result(),
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=_CONFIDENCE,
        prompt_version=_PROMPT_VER,
    )
    defaults.update(kwargs)
    return lab_result_to_observation(**defaults)


def _call_condition(**kwargs):
    defaults = dict(
        extracted=_chest_tightness_condition(),
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=_CONFIDENCE,
        prompt_version=_PROMPT_VER,
    )
    defaults.update(kwargs)
    return condition_to_fhir(**defaults)


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------


def _ext_value(obs: dict, url_suffix: str) -> object:
    """Retrieve the first value from a meta.extension entry by URL suffix."""
    for ext in obs["meta"]["extension"]:
        if ext["url"].endswith(url_suffix):
            for k, v in ext.items():
                if k != "url":
                    return v
    raise KeyError(f"Extension not found: {url_suffix}")


# ---------------------------------------------------------------------------
# Tests: lab_result_to_observation
# ---------------------------------------------------------------------------


def test_lab_result_to_observation_emits_required_meta_fields():
    """Observation must have meta.profile, meta.source, meta.tag (both codes),
    and all four extraction extension URLs."""
    obs = _call_lab()

    # resourceType
    assert obs["resourceType"] == "Observation"

    # meta.profile
    assert (
        "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"
        in obs["meta"]["profile"]
    )

    # meta.source
    assert "extracted://" in obs["meta"]["source"]
    assert _SOURCE_ID in obs["meta"]["source"]

    # meta.tag: source-tag + lifecycle = extracted
    tags = {
        t["system"]: t["code"] for t in obs["meta"]["tag"]
    }
    assert "https://ehi-atlas.example/fhir/CodeSystem/source-tag" in tags
    assert tags["https://ehi-atlas.example/fhir/CodeSystem/lifecycle"] == "extracted"

    # meta.extension: all four extraction URLs present
    ext_urls = {e["url"] for e in obs["meta"]["extension"]}
    for suffix in (
        "extraction-model",
        "extraction-confidence",
        "extraction-prompt-version",
        "source-attachment",
    ):
        assert f"{_EXT_BASE}/{suffix}" in ext_urls, (
            f"Missing extension: {suffix}"
        )

    # source-locator present (bbox was supplied)
    assert f"{_EXT_BASE}/source-locator" in ext_urls


def test_lab_result_to_observation_extraction_extension_values():
    """Extraction extension values match inputs."""
    obs = _call_lab()

    model_val = _ext_value(obs, "extraction-model")
    assert isinstance(model_val, dict)
    assert model_val["code"] == _MODEL

    conf_val = _ext_value(obs, "extraction-confidence")
    assert conf_val == _CONFIDENCE

    ver_val = _ext_value(obs, "extraction-prompt-version")
    assert ver_val == _PROMPT_VER

    att_val = _ext_value(obs, "source-attachment")
    assert att_val == {"reference": f"Binary/{_SOURCE_ID}"}

    loc_val = _ext_value(obs, "source-locator")
    assert loc_val == "page=2;bbox=72,574,540,590"


def test_lab_result_uses_loinc_when_provided():
    """When loinc_code is set, the observation includes a LOINC coding entry."""
    obs = _call_lab(result=_creatinine_result(loinc="2160-0"))

    coding = obs["code"].get("coding", [])
    assert len(coding) >= 1
    loinc_entries = [c for c in coding if c.get("system") == "http://loinc.org"]
    assert len(loinc_entries) == 1
    assert loinc_entries[0]["code"] == "2160-0"


def test_lab_result_omits_coding_when_loinc_unknown():
    """When loinc_code is None, there must be no coding key (or an empty list),
    never a fabricated code like '0000-0'."""
    obs = _call_lab(result=_creatinine_result(loinc=None))

    code_block = obs["code"]
    # text is always preserved
    assert code_block["text"] == "Creatinine"

    # no coding key, or empty list — no fabricated LOINC
    coding = code_block.get("coding", [])
    assert coding == [], (
        f"Expected no coding entries when loinc_code=None, got {coding}"
    )


def test_lab_result_interpretation_flag_mapped():
    """Flag 'H' produces the correct HL7 interpretation coding."""
    obs = _call_lab()

    interp = obs.get("interpretation", [])
    assert len(interp) == 1
    coding = interp[0]["coding"]
    assert any(c["code"] == "H" for c in coding)
    assert any("High" in c.get("display", "") for c in coding)


def test_lab_result_reference_range_emitted():
    """reference_range_low / high are serialized into referenceRange."""
    obs = _call_lab()

    rr = obs.get("referenceRange", [])
    assert len(rr) == 1
    assert rr[0]["low"]["value"] == 0.6
    assert rr[0]["high"]["value"] == 1.3


def test_lab_result_no_reference_range_when_absent():
    """referenceRange key is absent when both bounds are None."""
    result = ExtractedLabResult(
        test_name="Unknown Test",
        value_quantity=5.0,
        unit="U/L",
        bbox=BBox(page=1, x1=0, y1=0, x2=100, y2=20),
    )
    obs = lab_result_to_observation(
        result=result,
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=0.5,
        prompt_version=_PROMPT_VER,
    )
    assert "referenceRange" not in obs


def test_lab_result_value_string_path():
    """value_string is serialized when value_quantity is absent."""
    result = ExtractedLabResult(
        test_name="HIV Screen",
        value_string="Negative",
        bbox=BBox(page=1, x1=0, y1=0, x2=100, y2=20),
    )
    obs = lab_result_to_observation(
        result=result,
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=0.9,
        prompt_version=_PROMPT_VER,
    )
    assert obs.get("valueString") == "Negative"
    assert "valueQuantity" not in obs


def test_lab_result_subject_reference():
    """subject.reference is set to Patient/<patient_id>."""
    obs = _call_lab()
    assert obs["subject"]["reference"] == f"Patient/{_PATIENT_ID}"


# ---------------------------------------------------------------------------
# Tests: condition_to_fhir
# ---------------------------------------------------------------------------


def test_condition_to_fhir_includes_source_text_in_note():
    """The exact source_text phrase is preserved as Condition.note[0].text."""
    cond = _call_condition()

    notes = cond.get("note", [])
    assert len(notes) >= 1
    assert "chest tightness on exertion" in notes[0]["text"]


def test_condition_to_fhir_emits_required_meta_fields():
    """Condition must have meta.profile, meta.source, meta.tag, and extensions."""
    cond = _call_condition()

    assert cond["resourceType"] == "Condition"
    assert (
        "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition"
        in cond["meta"]["profile"]
    )
    assert "extracted://clinical-note/" in cond["meta"]["source"]

    tags = {t["system"]: t["code"] for t in cond["meta"]["tag"]}
    assert tags["https://ehi-atlas.example/fhir/CodeSystem/lifecycle"] == "extracted"

    ext_urls = {e["url"] for e in cond["meta"]["extension"]}
    assert f"{_EXT_BASE}/extraction-model" in ext_urls
    assert f"{_EXT_BASE}/extraction-confidence" in ext_urls
    assert f"{_EXT_BASE}/extraction-prompt-version" in ext_urls
    assert f"{_EXT_BASE}/source-attachment" in ext_urls


def test_condition_to_fhir_snomed_coding():
    """SNOMED CT code from extracted condition appears in code.coding."""
    cond = _call_condition()

    code_block = cond["code"]
    codings = code_block.get("coding", [])
    snomed = [c for c in codings if "snomed" in c.get("system", "")]
    assert len(snomed) == 1
    assert snomed[0]["code"] == "23924001"


def test_condition_to_fhir_no_fabricated_coding_when_codes_absent():
    """When both snomed_ct_code and icd_10_cm_code are None, coding list is empty or absent."""
    extracted = ExtractedCondition(
        label="Fatigue",
        source_text="patient reports fatigue",
    )
    cond = condition_to_fhir(
        extracted=extracted,
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=0.7,
        prompt_version=_PROMPT_VER,
    )
    codings = cond["code"].get("coding", [])
    assert codings == []


def test_condition_onset_date():
    """onset_date from the extracted condition becomes onsetDateTime."""
    cond = _call_condition()
    assert cond.get("onsetDateTime") == "2025-11-01"


def test_condition_source_locator_absent_when_no_bbox():
    """source-locator extension is omitted when bbox is None."""
    extracted = ExtractedCondition(
        label="Fatigue",
        source_text="patient reports fatigue",
        bbox=None,
    )
    cond = condition_to_fhir(
        extracted=extracted,
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=0.7,
        prompt_version=_PROMPT_VER,
    )
    ext_urls = {e["url"] for e in cond["meta"]["extension"]}
    assert f"{_EXT_BASE}/source-locator" not in ext_urls


def test_condition_source_locator_present_when_bbox_given():
    """source-locator extension is present when bbox is supplied."""
    bbox = BBox(page=1, x1=0, y1=0, x2=100, y2=20)
    extracted = _chest_tightness_condition(bbox=bbox)
    cond = condition_to_fhir(
        extracted=extracted,
        patient_id=_PATIENT_ID,
        source_attachment_id=_SOURCE_ID,
        model=_MODEL,
        confidence=0.9,
        prompt_version=_PROMPT_VER,
    )
    ext_urls = {e["url"] for e in cond["meta"]["extension"]}
    assert f"{_EXT_BASE}/source-locator" in ext_urls
