"""Tests for the coverage extraction pass in MultiPassFHIRPipeline.

Verifies schema validation, FHIR shape, identifier emission, period,
class[], relationship, subscriberId, and stable ID determinism.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    CoverageEntry,
    CoverageExtraction,
    DocumentContext,
    MultiPassFHIRPipeline,
    _stable_coverage_id,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    p = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    p._patient_id = "test-patient"
    return p


def _common_meta() -> dict:
    return {"source": "extracted://clinical-note/test", "extension": []}


def _doc_context() -> DocumentContext:
    return DocumentContext(document_type="patient-summary")


# ---------------------------------------------------------------------------
# 1. Valid status values
# ---------------------------------------------------------------------------


def test_coverage_entry_validates_status() -> None:
    """CoverageEntry accepts all four valid status literals."""
    for status in ("active", "cancelled", "draft", "entered-in-error"):
        entry = CoverageEntry(status=status)
        assert entry.status == status


# ---------------------------------------------------------------------------
# 2. Invalid status rejected
# ---------------------------------------------------------------------------


def test_coverage_entry_rejects_invalid_status() -> None:
    """status='suspended' is not a valid literal → ValidationError."""
    with pytest.raises(ValidationError):
        CoverageEntry(status="suspended")


# ---------------------------------------------------------------------------
# 3. Minimum resource shape — only payor_name
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_minimum() -> None:
    """Only payor_name → resource has resourceType=Coverage, id, status='active',
    beneficiary, and payor[0].display == payor_name."""
    pipeline = _new_pipeline()
    entry = CoverageEntry(payor_name="Blue Cross")
    resource = pipeline._coverage_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert resource["resourceType"] == "Coverage"
    assert "id" in resource
    assert resource["status"] == "active"
    assert resource["beneficiary"]["reference"] == "Patient/test-patient"
    assert resource["payor"][0]["display"] == "Blue Cross"


# ---------------------------------------------------------------------------
# 4. member_id + group_id → 2 identifier entries
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_emits_member_and_group_identifiers() -> None:
    """member_id + group_id → resource.identifier has 2 entries."""
    pipeline = _new_pipeline()
    entry = CoverageEntry(
        payor_name="Aetna",
        member_id="DVN914W1859710",
        group_id="57ANCA",
    )
    resource = pipeline._coverage_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "identifier" in resource
    assert len(resource["identifier"]) == 2
    types = {ident["type"]["text"] for ident in resource["identifier"]}
    assert "Member ID" in types
    assert "Group ID" in types


# ---------------------------------------------------------------------------
# 5. subscriber_id separate when different from member_id
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_subscriber_id_separate_when_different() -> None:
    """member_id='M1' + subscriber_id='S1' → identifier has both (3 entries
    with group would be more, but here just member + subscriber).
    member_id == subscriber_id → only one entry (no duplicate Subscriber ID)."""
    pipeline = _new_pipeline()

    # Different IDs → member + subscriber entries
    entry_diff = CoverageEntry(member_id="M1", subscriber_id="S1")
    resource_diff = pipeline._coverage_to_fhir(entry_diff, _common_meta(), layout=None, doc_context=_doc_context())
    id_types = {ident["type"]["text"] for ident in resource_diff["identifier"]}
    assert "Member ID" in id_types
    assert "Subscriber ID" in id_types

    # Same IDs → no duplicate Subscriber ID entry
    entry_same = CoverageEntry(member_id="M1", subscriber_id="M1")
    resource_same = pipeline._coverage_to_fhir(entry_same, _common_meta(), layout=None, doc_context=_doc_context())
    id_types_same = {ident["type"]["text"] for ident in resource_same["identifier"]}
    assert "Member ID" in id_types_same
    assert "Subscriber ID" not in id_types_same


# ---------------------------------------------------------------------------
# 6. subscriberId convenience field
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_emits_subscriberId_field() -> None:
    """subscriber_id set → resource.subscriberId populated."""
    pipeline = _new_pipeline()
    entry = CoverageEntry(subscriber_id="SUB-001")
    resource = pipeline._coverage_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert resource.get("subscriberId") == "SUB-001"


# ---------------------------------------------------------------------------
# 7. period emission
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_emits_period() -> None:
    """effective_period_start + effective_period_end → resource.period populated."""
    pipeline = _new_pipeline()
    entry = CoverageEntry(
        payor_name="Humana",
        effective_period_start="2026-01-01",
        effective_period_end="2026-12-31",
    )
    resource = pipeline._coverage_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "period" in resource
    assert resource["period"]["start"] == "2026-01-01"
    assert resource["period"]["end"] == "2026-12-31"


# ---------------------------------------------------------------------------
# 8. class[] for plan name and group
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_emits_class_with_plan_and_group() -> None:
    """plan_name + group_id → resource.class has 2 entries (plan + group)."""
    pipeline = _new_pipeline()
    entry = CoverageEntry(
        payor_name="Blue Cross",
        plan_name="BLUE CROSS EMP VIVITY HMO CSPN",
        group_id="57ANCA",
    )
    resource = pipeline._coverage_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "class" in resource
    classes = resource["class"]
    assert len(classes) == 2
    codes = {
        cls["type"]["coding"][0]["code"]
        for cls in classes
    }
    assert "plan" in codes
    assert "group" in codes


# ---------------------------------------------------------------------------
# 9. relationship coding
# ---------------------------------------------------------------------------


def test_coverage_to_fhir_emits_relationship() -> None:
    """relationship_to_subscriber='self' → resource.relationship.coding[0].code=='self'."""
    pipeline = _new_pipeline()
    entry = CoverageEntry(
        payor_name="Medicare",
        relationship_to_subscriber="self",
    )
    resource = pipeline._coverage_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "relationship" in resource
    assert resource["relationship"]["coding"][0]["code"] == "self"
    assert resource["relationship"]["coding"][0]["system"] == (
        "http://terminology.hl7.org/CodeSystem/subscriber-relationship"
    )


# ---------------------------------------------------------------------------
# 10. Stable ID is deterministic
# ---------------------------------------------------------------------------


def test_stable_coverage_id_is_deterministic() -> None:
    """Same payor_name + member_id + plan_name → same stable ID across calls."""
    entry_a = CoverageEntry(
        payor_name="Blue Cross",
        member_id="DVN914W1859710",
        plan_name="BLUE CROSS EMP VIVITY HMO CSPN",
    )
    entry_b = CoverageEntry(
        payor_name="Blue Cross",
        member_id="DVN914W1859710",
        plan_name="BLUE CROSS EMP VIVITY HMO CSPN",
    )
    id_a = _stable_coverage_id(entry_a)
    id_b = _stable_coverage_id(entry_b)
    assert id_a == id_b
    assert id_a.startswith("cov-")
    # suffix is 12-char hex
    suffix = id_a[len("cov-"):]
    assert len(suffix) == 12
    assert all(c in "0123456789abcdef" for c in suffix)
