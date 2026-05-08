"""Tests for reconcile_document_maps() — BIDI-T01.

All tests operate on the pure function; no pipeline instance is needed.
"""

from lib.extract.pipelines.multipass_fhir import (
    DocumentMap,
    MapReconciliation,
    ResourcePresence,
    reconcile_document_maps,
)


def _map(**presence_kwargs: dict) -> DocumentMap:
    """Build a minimal DocumentMap with the given presence entries."""
    return DocumentMap(document_type="other", presence=presence_kwargs)  # type: ignore[arg-type]


def _rp(present: bool, pages: list[int] | None = None, section_hint: str | None = None) -> ResourcePresence:
    return ResourcePresence(present=present, pages=pages or [], section_hint=section_hint)


# ---------------------------------------------------------------------------
# Test 1 — both empty → reconciled has empty presence
# ---------------------------------------------------------------------------


def test_reconcile_both_empty_returns_empty_map() -> None:
    """Two DocumentMaps with no presence entries → reconciled has empty presence."""
    map_a = DocumentMap(document_type="other")
    map_b = DocumentMap(document_type="other")
    result = reconcile_document_maps(map_a, map_b)
    assert isinstance(result, MapReconciliation)
    assert result.reconciled.presence == {}
    assert result.agreement_count == 0
    assert result.disagreement_count == 0


# ---------------------------------------------------------------------------
# Test 2 — union includes either present
# ---------------------------------------------------------------------------


def test_reconcile_union_includes_either_present() -> None:
    """Union: A says vital_signs present, B doesn't → vital_signs in reconciled."""
    map_a = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [2])},
    )
    map_b = DocumentMap(document_type="other")

    result = reconcile_document_maps(map_a, map_b, strategy="union")
    assert "vital_signs" in result.reconciled.presence
    assert result.reconciled.presence["vital_signs"].present is True


# ---------------------------------------------------------------------------
# Test 3 — intersection excludes partial agreement
# ---------------------------------------------------------------------------


def test_reconcile_intersection_excludes_partial_agreement() -> None:
    """Intersection: A says vital_signs present, B doesn't → NOT in reconciled."""
    map_a = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [2])},
    )
    map_b = DocumentMap(document_type="other")

    result = reconcile_document_maps(map_a, map_b, strategy="intersection")
    # Either absent or present=False — the key should not appear in reconciled
    assert "vital_signs" not in result.reconciled.presence


# ---------------------------------------------------------------------------
# Test 4 — union pages are the set-union
# ---------------------------------------------------------------------------


def test_reconcile_union_pages_are_union() -> None:
    """Union strategy: A pages=[2,3], B pages=[3,4] → reconciled pages=[2,3,4]."""
    map_a = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [2, 3])},
    )
    map_b = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [3, 4])},
    )

    result = reconcile_document_maps(map_a, map_b, strategy="union")
    assert result.reconciled.presence["vital_signs"].pages == [2, 3, 4]


# ---------------------------------------------------------------------------
# Test 5 — intersection pages are the set-intersection
# ---------------------------------------------------------------------------


def test_reconcile_intersection_pages_are_intersection() -> None:
    """Intersection strategy: A pages=[2,3], B pages=[3,4] → reconciled pages=[3]."""
    map_a = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [2, 3])},
    )
    map_b = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [3, 4])},
    )

    result = reconcile_document_maps(map_a, map_b, strategy="intersection")
    assert result.reconciled.presence["vital_signs"].pages == [3]


# ---------------------------------------------------------------------------
# Test 6 — disagreement_count
# ---------------------------------------------------------------------------


def test_reconcile_disagreement_count() -> None:
    """3 passes where exactly one scout marks each present → disagreement_count == 3."""
    map_a = DocumentMap(
        document_type="other",
        presence={
            "conditions": _rp(True),
            "medications": _rp(False),
            "allergies": _rp(True),
        },
    )
    map_b = DocumentMap(
        document_type="other",
        presence={
            "conditions": _rp(False),
            "medications": _rp(True),
            "allergies": _rp(False),
        },
    )

    result = reconcile_document_maps(map_a, map_b)
    assert result.disagreement_count == 3


# ---------------------------------------------------------------------------
# Test 7 — only_in_a / only_in_b
# ---------------------------------------------------------------------------


def test_reconcile_only_in_a_lists_correctly() -> None:
    """A has clinical_notes only, B has lab_observations only → lists correct."""
    map_a = DocumentMap(
        document_type="other",
        presence={"clinical_notes": _rp(True)},
    )
    map_b = DocumentMap(
        document_type="other",
        presence={"lab_observations": _rp(True)},
    )

    result = reconcile_document_maps(map_a, map_b)
    assert result.only_in_a == ["clinical_notes"]
    assert result.only_in_b == ["lab_observations"]


# ---------------------------------------------------------------------------
# Test 8 — prefer scout A for identity fields
# ---------------------------------------------------------------------------


def test_reconcile_prefers_scout_a_for_identity_fields() -> None:
    """A.patient_name='Blake', B.patient_name='Robert' → reconciled.patient_name=='Blake'."""
    map_a = DocumentMap(document_type="other", patient_name="Blake")
    map_b = DocumentMap(document_type="other", patient_name="Robert")

    result = reconcile_document_maps(map_a, map_b)
    assert result.reconciled.patient_name == "Blake"


# ---------------------------------------------------------------------------
# Test 9 — fall back to B when A field is None
# ---------------------------------------------------------------------------


def test_reconcile_falls_back_to_b_when_a_field_is_none() -> None:
    """A.patient_dob=None, B.patient_dob='1993-06-16' → reconciled uses B's value."""
    map_a = DocumentMap(document_type="other", patient_dob=None)
    map_b = DocumentMap(document_type="other", patient_dob="1993-06-16")

    result = reconcile_document_maps(map_a, map_b)
    assert result.reconciled.patient_dob == "1993-06-16"


# ---------------------------------------------------------------------------
# Test 10 — section_hint: prefer non-null when one is None
# ---------------------------------------------------------------------------


def test_reconcile_section_hint_preferred_when_one_null() -> None:
    """A has section_hint='Vital Signs', B has section_hint=None → 'Vital Signs' wins."""
    map_a = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [1], section_hint="Vital Signs")},
    )
    map_b = DocumentMap(
        document_type="other",
        presence={"vital_signs": _rp(True, [1], section_hint=None)},
    )

    result = reconcile_document_maps(map_a, map_b, strategy="union")
    assert result.reconciled.presence["vital_signs"].section_hint == "Vital Signs"
