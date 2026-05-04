"""Tests for ehi_atlas.harmonize.provenance — task 3.10.

12 tests covering:
- Builder functions and activity codes
- ProvenanceRecord.to_fhir() shape and defaults
- Resource-meta helper functions
- ProvenanceWriter ndjson output, sort order, and directory creation
- Extension URL constant parity with docs/PROVENANCE-SPEC.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ehi_atlas import __version__
from ehi_atlas.harmonize.provenance import (
    DEFAULT_RECORDED,
    EXT_BASE,
    EXT_CONFLICT_PAIR,
    EXT_EXTRACTION_CONFIDENCE,
    EXT_EXTRACTION_MODEL,
    EXT_EXTRACTION_PROMPT_VER,
    EXT_MERGE_RATIONALE,
    EXT_QUALITY_SCORE,
    EXT_SOURCE_ATTACHMENT,
    EXT_SOURCE_LOCATOR,
    EXT_UMLS_CUI,
    ACTIVITY_SYS,
    ProvenanceRecord,
    ProvenanceWriter,
    SourceRef,
    attach_conflict_pair,
    attach_merge_rationale,
    attach_quality_score,
    attach_umls_cui,
    derive_provenance,
    extract_provenance,
    merge_provenance,
    transform_provenance,
)


# ---------------------------------------------------------------------------
# Test 1 — merge_provenance emits correct activity code
# ---------------------------------------------------------------------------


def test_merge_provenance_emits_correct_activity_code():
    """activity.coding[0].system + .code must match the v3-DataOperation system."""
    prov = merge_provenance(
        target="Condition/harmonized-htn",
        sources=["Condition/synthea-htn", "Condition/epic-htn"],
    )
    fhir = prov.to_fhir()

    coding = fhir["activity"]["coding"][0]
    assert coding["system"] == ACTIVITY_SYS
    assert coding["code"] == "MERGE"


# ---------------------------------------------------------------------------
# Test 2 — merge_provenance with two sources produces two entity entries
# ---------------------------------------------------------------------------


def test_merge_provenance_with_two_sources_has_two_entities():
    """entity[] count must equal the number of sources passed in."""
    prov = merge_provenance(
        target="Condition/harmonized-htn",
        sources=["Condition/src-a", "Condition/src-b"],
    )
    fhir = prov.to_fhir()

    assert len(fhir["entity"]) == 2
    refs = {e["what"]["reference"] for e in fhir["entity"]}
    assert refs == {"Condition/src-a", "Condition/src-b"}


# ---------------------------------------------------------------------------
# Test 3 — extract_provenance uses EXTRACT activity code
# ---------------------------------------------------------------------------


def test_extract_provenance_uses_extract_activity():
    """The EXTRACT builder must emit activity code == 'EXTRACT'."""
    prov = extract_provenance(
        target="Observation/creatinine-extracted",
        source_attachment="Binary/quest-2025-09-12",
    )
    fhir = prov.to_fhir()

    assert fhir["activity"]["coding"][0]["code"] == "EXTRACT"


# ---------------------------------------------------------------------------
# Test 4 — default recorded timestamp when none provided
# ---------------------------------------------------------------------------


def test_provenance_record_to_fhir_uses_default_recorded_when_not_provided():
    """When `recorded` is not passed, to_fhir() must use DEFAULT_RECORDED."""
    rec = ProvenanceRecord(
        target_reference="Condition/test",
        activity="DERIVE",
        sources=[SourceRef(reference="Condition/silver-test")],
    )
    fhir = rec.to_fhir()

    assert fhir["recorded"] == DEFAULT_RECORDED


# ---------------------------------------------------------------------------
# Test 5 — agent.who.display matches ehi-atlas version
# ---------------------------------------------------------------------------


def test_provenance_record_agent_display_uses_ehi_atlas_version():
    """agent[0].who.display must be 'ehi-atlas v<__version__>'."""
    rec = ProvenanceRecord(
        target_reference="Condition/test",
        activity="MERGE",
        sources=[SourceRef(reference="Condition/src")],
    )
    fhir = rec.to_fhir()

    expected = f"ehi-atlas v{__version__}"
    assert fhir["agent"][0]["who"]["display"] == expected
    assert expected == "ehi-atlas v0.1.0"


# ---------------------------------------------------------------------------
# Test 6 — attach_quality_score adds meta extension with correct URL + value
# ---------------------------------------------------------------------------


def test_attach_quality_score_adds_meta_extension():
    """attach_quality_score must add the quality-score Extension to resource.meta."""
    resource: dict = {"resourceType": "Condition"}
    attach_quality_score(resource, 0.92)

    ext_list = resource["meta"]["extension"]
    assert any(
        e["url"] == EXT_QUALITY_SCORE and e["valueDecimal"] == 0.92 for e in ext_list
    ), f"Expected quality-score extension in {ext_list}"


# ---------------------------------------------------------------------------
# Test 7 — attach_quality_score does not clobber existing meta extensions
# ---------------------------------------------------------------------------


def test_attach_quality_score_does_not_clobber_existing_extensions():
    """Pre-existing meta.extension entries must be preserved after attach_quality_score."""
    existing_ext = {"url": "https://example.com/other-ext", "valueString": "preserved"}
    resource: dict = {
        "resourceType": "Condition",
        "meta": {"extension": [existing_ext]},
    }
    attach_quality_score(resource, 0.75)

    ext_list = resource["meta"]["extension"]
    # Both the original extension and the new quality-score extension should be present
    urls = [e["url"] for e in ext_list]
    assert "https://example.com/other-ext" in urls
    assert EXT_QUALITY_SCORE in urls
    assert len(ext_list) == 2

    # Original value must be untouched
    orig = next(e for e in ext_list if e["url"] == "https://example.com/other-ext")
    assert orig["valueString"] == "preserved"


# ---------------------------------------------------------------------------
# Test 8 — attach_conflict_pair lives on the resource (top level), not meta
# ---------------------------------------------------------------------------


def test_attach_conflict_pair_uses_resource_level_extension_not_meta():
    """Per spec, conflict-pair extension is on the resource itself, not resource.meta."""
    resource: dict = {"resourceType": "MedicationRequest"}
    attach_conflict_pair(resource, "MedicationRequest/epic-atorvastatin-row42")

    # Must be in the top-level extension array
    assert "extension" in resource
    top_exts = resource["extension"]
    conflict_exts = [e for e in top_exts if e["url"] == EXT_CONFLICT_PAIR]
    assert len(conflict_exts) == 1
    assert conflict_exts[0]["valueReference"]["reference"] == (
        "MedicationRequest/epic-atorvastatin-row42"
    )

    # Must NOT be in meta
    assert "meta" not in resource or "extension" not in resource.get("meta", {})


# ---------------------------------------------------------------------------
# Test 9 — ProvenanceWriter writes ndjson with one record per line
# ---------------------------------------------------------------------------


def test_provenance_writer_writes_ndjson_one_record_per_line(tmp_path: Path):
    """Each flushed record must occupy exactly one line (valid ndjson)."""
    gold_root = tmp_path / "gold"

    rec1 = merge_provenance(
        target="Condition/htn",
        sources=["Condition/a", "Condition/b"],
    )
    rec2 = extract_provenance(
        target="Observation/creatinine",
        source_attachment="Binary/quest",
    )

    with ProvenanceWriter(gold_root, "rhett759") as pw:
        pw.add(rec1)
        pw.add(rec2)

    out = gold_root / "patients" / "rhett759" / "provenance.ndjson"
    assert out.exists()

    lines = [l for l in out.read_text().splitlines() if l.strip()]
    assert len(lines) == 2

    # Each line must be valid JSON with the right resourceType
    for line in lines:
        parsed = json.loads(line)
        assert parsed["resourceType"] == "Provenance"


# ---------------------------------------------------------------------------
# Test 10 — ProvenanceWriter is byte-identical on re-run
# ---------------------------------------------------------------------------


def test_provenance_writer_is_byte_identical_on_re_run(tmp_path: Path):
    """Two writes with the same inputs must produce byte-identical output."""

    def _write(root: Path) -> bytes:
        with ProvenanceWriter(root, "rhett759") as pw:
            pw.add(merge_provenance(target="Condition/htn", sources=["Condition/a", "Condition/b"]))
            pw.add(extract_provenance(target="Observation/cr", source_attachment="Binary/q"))
            pw.add(derive_provenance(target="MedicationRequest/derived", source="MedicationRequest/src"))
        return (root / "patients" / "rhett759" / "provenance.ndjson").read_bytes()

    run1 = _write(tmp_path / "run1")
    run2 = _write(tmp_path / "run2")

    assert run1 == run2, "ndjson output should be byte-identical across re-runs"


# ---------------------------------------------------------------------------
# Test 11 — ProvenanceWriter creates the directory structure
# ---------------------------------------------------------------------------


def test_provenance_writer_creates_directory_structure(tmp_path: Path):
    """gold_root/patients/<patient>/provenance.ndjson must be created even if dirs are absent."""
    gold_root = tmp_path / "deeply" / "nested" / "gold"
    # Do NOT pre-create gold_root — the writer must create the full tree.

    with ProvenanceWriter(gold_root, "test-patient") as pw:
        pw.add(transform_provenance(
            target="Condition/transformed",
            source="Condition/silver",
        ))

    expected = gold_root / "patients" / "test-patient" / "provenance.ndjson"
    assert expected.exists(), f"Expected ndjson at {expected}"


# ---------------------------------------------------------------------------
# Test 12 — Extension URL constants exactly match docs/PROVENANCE-SPEC.md
# ---------------------------------------------------------------------------


def test_extension_url_constants_match_provenance_spec():
    """Paranoia test: verify the 9 EXT_* constants exactly match the documented URLs.

    Any URL drift here would silently break the app's Sources panel.
    The expected values are copied verbatim from docs/PROVENANCE-SPEC.md.
    """
    base = "https://ehi-atlas.example/fhir/StructureDefinition"

    expected = {
        "EXT_QUALITY_SCORE": f"{base}/quality-score",
        "EXT_CONFLICT_PAIR": f"{base}/conflict-pair",
        "EXT_EXTRACTION_MODEL": f"{base}/extraction-model",
        "EXT_EXTRACTION_CONFIDENCE": f"{base}/extraction-confidence",
        "EXT_EXTRACTION_PROMPT_VER": f"{base}/extraction-prompt-version",
        "EXT_SOURCE_ATTACHMENT": f"{base}/source-attachment",
        "EXT_SOURCE_LOCATOR": f"{base}/source-locator",
        "EXT_MERGE_RATIONALE": f"{base}/merge-rationale",
        "EXT_UMLS_CUI": f"{base}/umls-cui",
    }

    actual = {
        "EXT_QUALITY_SCORE": EXT_QUALITY_SCORE,
        "EXT_CONFLICT_PAIR": EXT_CONFLICT_PAIR,
        "EXT_EXTRACTION_MODEL": EXT_EXTRACTION_MODEL,
        "EXT_EXTRACTION_CONFIDENCE": EXT_EXTRACTION_CONFIDENCE,
        "EXT_EXTRACTION_PROMPT_VER": EXT_EXTRACTION_PROMPT_VER,
        "EXT_SOURCE_ATTACHMENT": EXT_SOURCE_ATTACHMENT,
        "EXT_SOURCE_LOCATOR": EXT_SOURCE_LOCATOR,
        "EXT_MERGE_RATIONALE": EXT_MERGE_RATIONALE,
        "EXT_UMLS_CUI": EXT_UMLS_CUI,
    }

    for name, url in expected.items():
        assert actual[name] == url, (
            f"URL drift detected for {name}: "
            f"expected {url!r}, got {actual[name]!r}"
        )

    # Also verify EXT_BASE itself
    assert EXT_BASE == base
