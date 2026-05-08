"""Tests for the social-history extraction pass in MultiPassFHIRPipeline.

Verifies schema validation, LOINC mapping correctness, FHIR category,
value emission, and doc-context date fallback.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    MultiPassFHIRPipeline,
    SocialHistoryEntry,
    SocialHistoryExtraction,
    _SOCIAL_HISTORY_LOINC_MAP,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    return MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)


# ---------------------------------------------------------------------------
# 1. Schema validation — all 11 topic values pass
# ---------------------------------------------------------------------------


def test_social_history_entry_validates_topic() -> None:
    """Each of the 11 topic literals should pass validation."""
    valid_topics = [
        "tobacco-use",
        "alcohol-use",
        "drug-use",
        "occupation",
        "phq-9",
        "phq-2",
        "depression-screen",
        "sex-assigned-at-birth",
        "legal-sex",
        "gender-identity",
        "sexual-orientation",
    ]
    for topic in valid_topics:
        entry = SocialHistoryEntry(topic=topic)
        assert entry.topic == topic, f"Expected topic={topic!r}, got {entry.topic!r}"


# ---------------------------------------------------------------------------
# 2. Schema validation — invalid topic rejected
# ---------------------------------------------------------------------------


def test_social_history_entry_rejects_invalid_topic() -> None:
    """An unrecognized topic string must raise a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        SocialHistoryEntry(topic="weird")


# ---------------------------------------------------------------------------
# 3. LOINC + category correctness for tobacco-use
# ---------------------------------------------------------------------------


def test_social_history_to_fhir_tobacco_emits_correct_loinc() -> None:
    """topic='tobacco-use' → code 72166-2, category social-history."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    entry = SocialHistoryEntry(topic="tobacco-use", value_string="Never")
    resource = pipeline._social_history_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    # LOINC code
    codings = resource["code"]["coding"]
    loinc_codes = [c["code"] for c in codings if c.get("system") == "http://loinc.org"]
    assert loinc_codes == ["72166-2"], f"Expected [72166-2], got {loinc_codes!r}"

    # Category
    cat_codings = resource["category"][0]["coding"]
    cat_codes = [c["code"] for c in cat_codings]
    assert "social-history" in cat_codes, f"Expected 'social-history' in {cat_codes!r}"


# ---------------------------------------------------------------------------
# 4. PHQ-9 emits survey category and code 44261-6
# ---------------------------------------------------------------------------


def test_social_history_to_fhir_phq9_emits_survey_category() -> None:
    """topic='phq-9' → category='survey', LOINC 44261-6."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    entry = SocialHistoryEntry(topic="phq-9", value_quantity=0)
    resource = pipeline._social_history_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    # Category must be survey
    cat_codings = resource["category"][0]["coding"]
    cat_codes = [c["code"] for c in cat_codings]
    assert "survey" in cat_codes, f"Expected 'survey' in {cat_codes!r}"

    # LOINC code
    codings = resource["code"]["coding"]
    loinc_codes = [c["code"] for c in codings if c.get("system") == "http://loinc.org"]
    assert loinc_codes == ["44261-6"], f"Expected [44261-6], got {loinc_codes!r}"


# ---------------------------------------------------------------------------
# 5. value_string emission — no valueQuantity
# ---------------------------------------------------------------------------


def test_social_history_to_fhir_value_string() -> None:
    """value_string='Never' → resource.valueString=='Never', no valueQuantity."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    entry = SocialHistoryEntry(topic="tobacco-use", value_string="Never")
    resource = pipeline._social_history_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    assert resource.get("valueString") == "Never"
    assert "valueQuantity" not in resource


# ---------------------------------------------------------------------------
# 6. value_quantity emission — no valueString
# ---------------------------------------------------------------------------


def test_social_history_to_fhir_value_quantity() -> None:
    """topic='phq-9' + value_quantity=0 → resource.valueQuantity.value==0, no valueString."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    entry = SocialHistoryEntry(topic="phq-9", value_quantity=0)
    resource = pipeline._social_history_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    assert "valueQuantity" in resource
    assert resource["valueQuantity"]["value"] == 0
    assert "valueString" not in resource


# ---------------------------------------------------------------------------
# 7. Doc-context date fallback
# ---------------------------------------------------------------------------


def test_social_history_to_fhir_effective_date_from_doc_context_fallback() -> None:
    """No effective_date on entry but DocumentContext.encounter_date set →
    resource picks up doc-context date as effectiveDateTime."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary", encounter_date="2025-08-11")

    entry = SocialHistoryEntry(topic="occupation", value_string="MANAGER")
    assert entry.effective_date is None  # no date on the entry

    resource = pipeline._social_history_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    assert resource.get("effectiveDateTime") == "2025-08-11"
