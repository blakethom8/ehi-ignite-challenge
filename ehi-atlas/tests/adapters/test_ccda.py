"""Tests for the CCDA Layer 1 adapter.

Uses the real Cerner Transition_of_Care_Referral_Summary.xml fixture (92 KB)
for the integration tests and a synthetic minimal-fixture + bad-XML snippet
for the edge/failure cases.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ehi_atlas.adapters.ccda import ACQUISITION_TS, CCDAAdapter, _probe_fhir_converter

# ---------------------------------------------------------------------------
# Paths to the real corpus fixture
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_CCDA_SRC = (
    _REPO_ROOT
    / "corpus"
    / "_sources"
    / "josh-ccdas"
    / "raw"
    / "Cerner Samples"
    / "Transition_of_Care_Referral_Summary.xml"
)

# Minimal valid CDA R2 document (namespace-qualified root).
_MINIMAL_CCDA_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<ClinicalDocument xmlns="urn:hl7-org:v3">
  <realmCode code="US"/>
  <typeId root="2.16.840.1.113883.1.3" extension="POCD_HD000040"/>
  <recordTarget>
    <patientRole>
      <id root="2.16.840.1.113883.19.5.99999.1" extension="999-999-9999"/>
    </patientRole>
  </recordTarget>
</ClinicalDocument>
"""

_BAD_XML = "<?xml version='1.0'?><unclosed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter(
    tmp_path: Path,
    patient_id: str = "test-patient",
    xml_content: str = _MINIMAL_CCDA_XML,
    rel_path: str = "TestVendor/test.xml",
) -> CCDAAdapter:
    """Create a CCDAAdapter wired to a tmp corpus with synthetic XML."""
    source_root = tmp_path / "_sources" / "josh-ccdas" / "raw"
    bronze_root = tmp_path / "bronze" / "ccda"

    xml_file = source_root / rel_path
    xml_file.parent.mkdir(parents=True, exist_ok=True)
    xml_file.write_text(xml_content, encoding="utf-8")
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = CCDAAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {patient_id: rel_path}
    return adapter


def _make_real_adapter(tmp_path: Path) -> CCDAAdapter:
    """Create a CCDAAdapter pointing at the real Cerner fixture."""
    source_root = _REAL_CCDA_SRC.parent.parent  # raw/
    bronze_root = tmp_path / "bronze" / "ccda"
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = CCDAAdapter(source_root=source_root, bronze_root=bronze_root)
    # Override map to use the actual relative path from raw/
    adapter.PATIENT_FILE_MAP = {
        "rhett759": "Cerner Samples/Transition_of_Care_Referral_Summary.xml"
    }
    return adapter


# ---------------------------------------------------------------------------
# Test 1: list_patients returns known patients
# ---------------------------------------------------------------------------


def test_list_patients_returns_known_patients(tmp_path: Path) -> None:
    """list_patients() returns patient IDs whose CCDA files are on disk."""
    adapter = _make_adapter(tmp_path)
    patients = adapter.list_patients()
    assert patients == ["test-patient"], f"Expected ['test-patient'], got {patients}"


def test_list_patients_excludes_missing_files(tmp_path: Path) -> None:
    """list_patients() omits patients whose files don't exist on disk."""
    source_root = tmp_path / "_sources" / "josh-ccdas" / "raw"
    bronze_root = tmp_path / "bronze" / "ccda"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = CCDAAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {"ghost": "GhostVendor/ghost.xml"}

    assert adapter.list_patients() == []


# ---------------------------------------------------------------------------
# Test 2: ingest writes byte-identical XML on repeated runs (idempotency)
# ---------------------------------------------------------------------------


def test_ingest_writes_bronze_xml_idempotent(tmp_path: Path) -> None:
    """Running ingest() twice produces byte-identical data.xml."""
    adapter = _make_adapter(tmp_path)

    meta1 = adapter.ingest("test-patient")
    hash1 = meta1.sha256

    meta2 = adapter.ingest("test-patient")
    hash2 = meta2.sha256

    assert hash1 == hash2, f"SHA-256 changed between runs: {hash1} != {hash2}"

    # Direct file read as additional byte-level confirmation
    data_bytes = (adapter.bronze_dir("test-patient") / "data.xml").read_bytes()
    direct_hash = hashlib.sha256(data_bytes).hexdigest()
    assert direct_hash == hash2


# ---------------------------------------------------------------------------
# Test 3: ingest metadata has correct fields
# ---------------------------------------------------------------------------


def test_ingest_metadata_has_correct_fields(tmp_path: Path) -> None:
    """ingest() produces SourceMetadata with the correct document_type, license, consent."""
    adapter = _make_adapter(tmp_path)
    meta = adapter.ingest("test-patient")

    assert meta.source == "ccda"
    assert meta.patient_id == "test-patient"
    assert meta.fetched_at == ACQUISITION_TS
    assert meta.document_type == "ccda-r2-transition-of-care"
    assert meta.license == "CC BY 4.0"
    assert meta.consent == "open"
    assert len(meta.sha256) == 64, "sha256 must be 64-char hex"

    # metadata.json on disk must round-trip correctly
    meta_path = adapter.bronze_dir("test-patient") / "metadata.json"
    raw_meta = json.loads(meta_path.read_text())
    assert raw_meta["license"] == "CC BY 4.0"
    assert raw_meta["consent"] == "open"
    assert raw_meta["document_type"] == "ccda-r2-transition-of-care"
    assert raw_meta["sha256"] == meta.sha256


# ---------------------------------------------------------------------------
# Test 4: validate passes with the real Cerner CCDA fixture
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _REAL_CCDA_SRC.exists(),
    reason="Real Cerner fixture not present (corpus not staged)",
)
def test_validate_passes_with_real_ccda_fixture(tmp_path: Path) -> None:
    """validate() returns only warnings (not hard errors) on the real Cerner fixture."""
    adapter = _make_real_adapter(tmp_path)
    adapter.ingest("rhett759")

    errors = adapter.validate("rhett759")

    # Filter to hard errors only (warnings are informational)
    hard_errors = [e for e in errors if not e.startswith("warning:")]
    assert hard_errors == [], (
        f"Expected no hard errors for real fixture, got: {hard_errors}"
    )


@pytest.mark.skipif(
    not _REAL_CCDA_SRC.exists(),
    reason="Real Cerner fixture not present (corpus not staged)",
)
def test_ingest_bronze_hash_matches_source_hash(tmp_path: Path) -> None:
    """Bronze data.xml SHA-256 must equal source file SHA-256 (passthrough check)."""
    source_sha = hashlib.sha256(_REAL_CCDA_SRC.read_bytes()).hexdigest()
    adapter = _make_real_adapter(tmp_path)
    meta = adapter.ingest("rhett759")
    assert meta.sha256 == source_sha, (
        f"Bronze hash {meta.sha256} != source hash {source_sha}"
    )


# ---------------------------------------------------------------------------
# Test 5: validate returns descriptive error on bad XML
# ---------------------------------------------------------------------------


def test_validate_returns_xml_parse_error_on_bad_input(tmp_path: Path) -> None:
    """validate() returns a descriptive error when data.xml is malformed XML."""
    adapter = _make_adapter(tmp_path, xml_content=_MINIMAL_CCDA_XML)
    adapter.ingest("test-patient")

    # Overwrite bronze data.xml with malformed XML
    bad_path = adapter.bronze_dir("test-patient") / "data.xml"
    bad_path.write_text(_BAD_XML, encoding="utf-8")

    errors = adapter.validate("test-patient")
    hard_errors = [e for e in errors if not e.startswith("warning:")]

    assert any("not valid XML" in e or "XML" in e for e in hard_errors), (
        f"Expected XML parse error, got: {errors}"
    )


def test_validate_returns_error_on_wrong_root_element(tmp_path: Path) -> None:
    """validate() errors if root element is not <ClinicalDocument>."""
    wrong_root_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Bundle xmlns="http://hl7.org/fhir"><id value="test"/></Bundle>'
    )
    adapter = _make_adapter(tmp_path, xml_content=_MINIMAL_CCDA_XML)
    adapter.ingest("test-patient")

    # Overwrite with wrong root
    (adapter.bronze_dir("test-patient") / "data.xml").write_text(
        wrong_root_xml, encoding="utf-8"
    )

    errors = adapter.validate("test-patient")
    hard_errors = [e for e in errors if not e.startswith("warning:")]
    assert any("ClinicalDocument" in e for e in hard_errors), (
        f"Expected ClinicalDocument root error, got: {errors}"
    )


def test_validate_missing_data_xml(tmp_path: Path) -> None:
    """validate() errors immediately if data.xml is absent."""
    source_root = tmp_path / "_sources" / "josh-ccdas" / "raw"
    bronze_root = tmp_path / "bronze" / "ccda"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = CCDAAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {"nobody": "Vendor/nobody.xml"}

    errors = adapter.validate("nobody")
    assert any("data.xml" in e for e in errors), (
        f"Expected 'data.xml missing' error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Test 6: FHIR-Converter probe does not crash even when tool is absent
# ---------------------------------------------------------------------------


def test_probe_fhir_converter_does_not_crash() -> None:
    """_probe_fhir_converter() always returns (bool, str) — never raises."""
    # Clear LRU cache so this test gets a fresh result
    _probe_fhir_converter.cache_clear()

    result = _probe_fhir_converter()

    assert isinstance(result, tuple), "Expected a tuple"
    assert len(result) == 2, "Expected (available: bool, message: str)"
    available, message = result
    assert isinstance(available, bool), f"available must be bool, got {type(available)}"
    assert isinstance(message, str) and message, "message must be a non-empty string"


def test_probe_fhir_converter_returns_consistent_cached_result() -> None:
    """Calling _probe_fhir_converter() twice returns the same cached result."""
    _probe_fhir_converter.cache_clear()

    result1 = _probe_fhir_converter()
    result2 = _probe_fhir_converter()

    assert result1 == result2, "LRU cache should return identical results on repeat calls"
