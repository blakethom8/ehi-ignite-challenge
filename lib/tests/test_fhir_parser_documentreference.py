"""
Tests for DocumentReferenceRecord dataclass and extractor.

Covers:
  - extract_document_references from synthetic bundles
  - base64 text/* decoding
  - author / encounter-ref extraction
  - non-text content types kept as-is (content_text remains None)
  - skipping unrelated resource types
  - empty bundle
  - PatientRecord.document_references populated via parse_bundle
"""

from __future__ import annotations

import base64
import json
import os
import tempfile

import pytest

from lib.fhir_parser.extractors import extract_document_references
from lib.fhir_parser.models import DocumentReferenceRecord
from lib.fhir_parser.bundle_parser import parse_bundle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bundle(*resources: dict) -> dict:
    """Wrap raw resource dicts into a minimal FHIR Bundle dict."""
    return {
        "resourceType": "Bundle",
        "entry": [{"resource": r} for r in resources],
    }


def _doc_ref(
    *,
    doc_id: str = "doc-1",
    status: str = "current",
    type_text: str | None = None,
    type_coding: list[dict] | None = None,
    date: str | None = None,
    authors: list[dict] | None = None,
    context_encounters: list[dict] | None = None,
    content: list[dict] | None = None,
) -> dict:
    resource: dict = {"resourceType": "DocumentReference", "id": doc_id, "status": status}
    if type_text or type_coding:
        resource["type"] = {}
        if type_text:
            resource["type"]["text"] = type_text
        if type_coding:
            resource["type"]["coding"] = type_coding
    if date:
        resource["date"] = date
    if authors:
        resource["author"] = authors
    if context_encounters:
        resource["context"] = {"encounter": context_encounters}
    if content:
        resource["content"] = content
    return resource


# ---------------------------------------------------------------------------
# Test 1 — minimal bundle with type + content
# ---------------------------------------------------------------------------

def test_extract_document_references_from_minimal_bundle() -> None:
    bundle = _make_bundle(
        _doc_ref(
            type_coding=[{"system": "http://loinc.org", "code": "11506-3", "display": "Progress note"}],
            content=[{"attachment": {"contentType": "text/plain", "title": "Note"}}],
        )
    )
    records = extract_document_references(bundle)
    assert len(records) == 1
    rec = records[0]
    assert rec.type_code == "11506-3"
    assert rec.type_system == "http://loinc.org"
    assert rec.type_display == "Progress note"
    assert rec.document_id == "doc-1"
    assert rec.status == "current"


# ---------------------------------------------------------------------------
# Test 2 — base64 text/plain attachment decoded to content_text
# ---------------------------------------------------------------------------

def test_extract_document_references_decodes_base64_text_attachment() -> None:
    raw_text = "Hello world"
    encoded = base64.b64encode(raw_text.encode()).decode()
    bundle = _make_bundle(
        _doc_ref(
            content=[{"attachment": {"contentType": "text/plain", "data": encoded}}],
        )
    )
    records = extract_document_references(bundle)
    assert len(records) == 1
    assert records[0].content_text == "Hello world"


# ---------------------------------------------------------------------------
# Test 3 — author display names extracted
# ---------------------------------------------------------------------------

def test_extract_document_references_extracts_authors() -> None:
    bundle = _make_bundle(
        _doc_ref(
            authors=[
                {"display": "Ani Shirvanian, NP"},
                {"display": "Steven Krems, MD"},
            ]
        )
    )
    records = extract_document_references(bundle)
    assert len(records) == 1
    assert records[0].author_displays == ["Ani Shirvanian, NP", "Steven Krems, MD"]


# ---------------------------------------------------------------------------
# Test 4 — encounter references extracted from context
# ---------------------------------------------------------------------------

def test_extract_document_references_extracts_encounter_refs() -> None:
    bundle = _make_bundle(
        _doc_ref(context_encounters=[{"reference": "Encounter/abc"}])
    )
    records = extract_document_references(bundle)
    assert len(records) == 1
    assert records[0].encounter_references == ["Encounter/abc"]


# ---------------------------------------------------------------------------
# Test 5 — skips non-DocumentReference resource types
# ---------------------------------------------------------------------------

def test_extract_document_references_skips_other_resource_types() -> None:
    bundle = _make_bundle(
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Encounter", "id": "e1"},
        _doc_ref(doc_id="doc-only"),
    )
    records = extract_document_references(bundle)
    assert len(records) == 1
    assert records[0].document_id == "doc-only"


# ---------------------------------------------------------------------------
# Test 6 — empty bundle returns empty list
# ---------------------------------------------------------------------------

def test_extract_document_references_handles_empty_bundle() -> None:
    records = extract_document_references({"resourceType": "Bundle", "entry": []})
    assert records == []

    records_no_entry = extract_document_references({"resourceType": "Bundle"})
    assert records_no_entry == []


# ---------------------------------------------------------------------------
# Test 7 — non-text content type: content_text stays None
# ---------------------------------------------------------------------------

def test_extract_document_references_handles_non_text_content_type() -> None:
    encoded = base64.b64encode(b"%PDF-stub").decode()
    bundle = _make_bundle(
        _doc_ref(
            content=[{"attachment": {"contentType": "application/pdf", "data": encoded}}],
        )
    )
    records = extract_document_references(bundle)
    assert len(records) == 1
    rec = records[0]
    assert rec.content_type == "application/pdf"
    assert rec.content_text is None  # should NOT attempt to decode non-text


# ---------------------------------------------------------------------------
# Test 8 — parse_bundle populates PatientRecord.document_references
# ---------------------------------------------------------------------------

def test_patient_record_has_document_references_field() -> None:
    """parse_bundle on a bundle containing DocumentReferences populates the field."""
    raw_text = "Surgical note content"
    encoded = base64.b64encode(raw_text.encode()).decode()

    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "patient-1",
                    "name": [{"family": "Smith", "given": ["Jane"]}],
                    "gender": "female",
                    "birthDate": "1980-01-01",
                }
            },
            {
                "resource": _doc_ref(
                    doc_id="doc-test-1",
                    type_coding=[{"system": "http://loinc.org", "code": "11506-3", "display": "Progress note"}],
                    date="2024-03-15T10:00:00Z",
                    authors=[{"display": "Dr. House"}],
                    content=[{"attachment": {"contentType": "text/plain", "data": encoded}}],
                )
            },
        ],
    }

    # Write to a temp file for parse_bundle (which reads from disk)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(bundle, tmp)
        tmp_path = tmp.name

    try:
        record = parse_bundle(tmp_path)
    finally:
        os.unlink(tmp_path)

    assert hasattr(record, "document_references"), "PatientRecord missing document_references field"
    assert len(record.document_references) == 1

    doc = record.document_references[0]
    assert doc.document_id == "doc-test-1"
    assert doc.type_code == "11506-3"
    assert doc.date == "2024-03-15T10:00:00Z"
    assert doc.author_displays == ["Dr. House"]
    assert doc.content_text == "Surgical note content"
