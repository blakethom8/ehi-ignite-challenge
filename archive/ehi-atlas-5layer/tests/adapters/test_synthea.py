"""Tests for the Synthea FHIR R4 passthrough adapter.

Uses a minimal synthetic Bundle fixture (inline) — no need to copy the 9.3 MB
Rhett759 bundle into the test suite. The fixture exercises the full adapter
contract: list_patients → ingest → validate.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ehi_atlas.adapters.synthea import SyntheaAdapter, ACQUISITION_TS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Minimal FHIR R4 Bundle with one Patient resource.
MINIMAL_BUNDLE: dict = {
    "resourceType": "Bundle",
    "id": "test-bundle-001",
    "type": "collection",
    "entry": [
        {
            "fullUrl": "Patient/test-patient-001",
            "resource": {
                "resourceType": "Patient",
                "id": "test-patient-001",
                "name": [{"family": "Test", "given": ["Alice"]}],
                "gender": "female",
                "birthDate": "1980-01-01",
            },
        },
        {
            "fullUrl": "Condition/test-condition-001",
            "resource": {
                "resourceType": "Condition",
                "id": "test-condition-001",
                "subject": {"reference": "Patient/test-patient-001"},
                "code": {
                    "coding": [
                        {"system": "http://snomed.info/sct", "code": "44054006", "display": "Diabetes"}
                    ]
                },
            },
        },
    ],
}

# Bundle WITHOUT a Patient resource — used in the negative test.
BUNDLE_NO_PATIENT: dict = {
    "resourceType": "Bundle",
    "id": "test-bundle-no-patient",
    "type": "collection",
    "entry": [
        {
            "fullUrl": "Condition/test-condition-002",
            "resource": {
                "resourceType": "Condition",
                "id": "test-condition-002",
                "subject": {"reference": "Patient/unknown"},
            },
        }
    ],
}


@pytest.fixture()
def corpus_root(tmp_path: Path) -> Path:
    """Return a tmp_path structured like the real corpus layout."""
    return tmp_path


def make_adapter(
    corpus_root: Path,
    patient_id: str = "alice",
    bundle: dict = MINIMAL_BUNDLE,
    filename: str = "Alice_Test_00000000-0000-0000-0000-000000000001.json",
) -> tuple[SyntheaAdapter, Path]:
    """Create a SyntheaAdapter backed by a temp corpus with one patient bundle."""
    source_root = corpus_root / "_sources" / "synthea" / "raw"
    bronze_root = corpus_root / "bronze" / "synthea"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    # Write the bundle file to the fake raw/ dir
    bundle_path = source_root / filename
    bundle_path.write_text(json.dumps(bundle, indent=2))

    # Build adapter with a custom PATIENT_FILE_MAP for the test patient
    adapter = SyntheaAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {patient_id: filename}

    return adapter, source_root


# ---------------------------------------------------------------------------
# Test 1: list_patients returns known patients
# ---------------------------------------------------------------------------


def test_list_patients_returns_known_patients(tmp_path: Path) -> None:
    """list_patients() returns patient IDs whose files are present on disk."""
    adapter, _ = make_adapter(tmp_path)
    patients = adapter.list_patients()
    assert patients == ["alice"], f"Expected ['alice'], got {patients}"


def test_list_patients_excludes_missing_files(tmp_path: Path) -> None:
    """list_patients() omits patients whose bundle files don't exist."""
    source_root = tmp_path / "_sources" / "synthea" / "raw"
    bronze_root = tmp_path / "bronze" / "synthea"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = SyntheaAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {
        "alice": "Alice_Test.json",       # file does NOT exist
        "bob": "Bob_Test.json",           # file does NOT exist
    }

    assert adapter.list_patients() == []


# ---------------------------------------------------------------------------
# Test 2: ingest writes bronze record with correct shape
# ---------------------------------------------------------------------------


def test_ingest_writes_bronze_record(tmp_path: Path) -> None:
    """ingest() produces data.json + metadata.json with correct shape."""
    adapter, _ = make_adapter(tmp_path)
    metadata = adapter.ingest("alice")

    bronze_dir = adapter.bronze_dir("alice")
    data_path = bronze_dir / "data.json"
    meta_path = bronze_dir / "metadata.json"

    # Files exist
    assert data_path.exists(), "data.json not written"
    assert meta_path.exists(), "metadata.json not written"

    # data.json is valid JSON
    data = json.loads(data_path.read_text())
    assert data["resourceType"] == "Bundle"

    # metadata fields
    assert metadata.source == "synthea"
    assert metadata.patient_id == "alice"
    assert metadata.fetched_at == ACQUISITION_TS
    assert metadata.document_type == "fhir-bundle"
    assert metadata.license == "Apache-2.0"
    assert metadata.consent == "open"
    assert len(metadata.sha256) == 64, "sha256 should be a 64-char hex string"

    # metadata.json on disk matches returned model
    raw_meta = json.loads(meta_path.read_text())
    assert raw_meta["sha256"] == metadata.sha256
    assert raw_meta["patient_id"] == "alice"


# ---------------------------------------------------------------------------
# Test 3: ingest is idempotent (byte-identical on second run)
# ---------------------------------------------------------------------------


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    """Running ingest() twice produces byte-identical bronze data.json."""
    adapter, _ = make_adapter(tmp_path)

    meta1 = adapter.ingest("alice")
    meta2 = adapter.ingest("alice")

    assert meta1.sha256 == meta2.sha256, (
        f"Hash changed between runs: {meta1.sha256} != {meta2.sha256}"
    )

    # Byte-level check too
    data_path = adapter.bronze_dir("alice") / "data.json"
    content = data_path.read_bytes()
    # Re-read sha256 directly
    import hashlib
    direct_hash = hashlib.sha256(content).hexdigest()
    assert direct_hash == meta2.sha256


# ---------------------------------------------------------------------------
# Test 4: validate returns [] for a valid bronze record
# ---------------------------------------------------------------------------


def test_validate_returns_empty_for_valid_record(tmp_path: Path) -> None:
    """After ingest(), validate() returns an empty list."""
    adapter, _ = make_adapter(tmp_path)
    adapter.ingest("alice")

    errors = adapter.validate("alice")
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Test 5: validate catches bundle with no Patient resource
# ---------------------------------------------------------------------------


def test_validate_catches_missing_patient(tmp_path: Path) -> None:
    """validate() returns an error when the Bundle contains no Patient resource."""
    adapter, _ = make_adapter(tmp_path, bundle=BUNDLE_NO_PATIENT)
    adapter.ingest("alice")

    errors = adapter.validate("alice")
    assert any("Patient" in e for e in errors), (
        f"Expected a 'no Patient resource' error, got: {errors}"
    )


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_ingest_raises_for_unknown_patient(tmp_path: Path) -> None:
    """ingest() raises ValueError for a patient_id not in PATIENT_FILE_MAP."""
    source_root = tmp_path / "_sources" / "synthea" / "raw"
    bronze_root = tmp_path / "bronze" / "synthea"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = SyntheaAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {}  # empty map

    with pytest.raises(ValueError, match="Unknown patient_id"):
        adapter.ingest("nobody")


def test_validate_reports_missing_data_file(tmp_path: Path) -> None:
    """validate() errors if data.json is absent (ingest never ran)."""
    source_root = tmp_path / "_sources" / "synthea" / "raw"
    bronze_root = tmp_path / "bronze" / "synthea"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = SyntheaAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {"alice": "Alice_Test.json"}

    errors = adapter.validate("alice")
    assert any("data.json" in e for e in errors), (
        f"Expected a 'data.json missing' error, got: {errors}"
    )
