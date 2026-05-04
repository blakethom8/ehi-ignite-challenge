"""Tests for the SyntheaPayerAdapter (D10: Synthea-payer split).

Uses a minimal inline Bundle fixture — no need to load the 9.3 MB Rhett759
bundle in tests. The fixture exercises the full adapter contract:
    list_patients → ingest → validate

Five required cases:
    1. list_patients returns known patients
    2. ingest writes a Bundle with only payer resource types
    3. ingest preserves Patient resource for identity resolution
    4. ingest is idempotent (byte-identical re-run)
    5. validate returns [] for a valid record
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ehi_atlas.adapters.synthea_payer import SyntheaPayerAdapter, ACQUISITION_TS


# ---------------------------------------------------------------------------
# Shared fixture bundles
# ---------------------------------------------------------------------------

PAYER_BUNDLE: dict = {
    "resourceType": "Bundle",
    "id": "test-payer-bundle-001",
    "type": "collection",
    "entry": [
        {
            "fullUrl": "Patient/pt-001",
            "resource": {
                "resourceType": "Patient",
                "id": "pt-001",
                "name": [{"family": "Synthetic", "given": ["Payer"]}],
                "gender": "male",
                "birthDate": "1960-06-15",
            },
        },
        {
            "fullUrl": "Claim/claim-001",
            "resource": {
                "resourceType": "Claim",
                "id": "claim-001",
                "status": "active",
                "patient": {"reference": "Patient/pt-001"},
            },
        },
        {
            "fullUrl": "Claim/claim-002",
            "resource": {
                "resourceType": "Claim",
                "id": "claim-002",
                "status": "active",
                "patient": {"reference": "Patient/pt-001"},
            },
        },
        {
            "fullUrl": "ExplanationOfBenefit/eob-001",
            "resource": {
                "resourceType": "ExplanationOfBenefit",
                "id": "eob-001",
                "status": "active",
                "patient": {"reference": "Patient/pt-001"},
            },
        },
        {
            "fullUrl": "Coverage/cov-001",
            "resource": {
                "resourceType": "Coverage",
                "id": "cov-001",
                "status": "active",
                "beneficiary": {"reference": "Patient/pt-001"},
            },
        },
        # Clinical resources — should NOT appear in payer output
        {
            "fullUrl": "Condition/cond-001",
            "resource": {
                "resourceType": "Condition",
                "id": "cond-001",
                "subject": {"reference": "Patient/pt-001"},
            },
        },
        {
            "fullUrl": "Observation/obs-001",
            "resource": {
                "resourceType": "Observation",
                "id": "obs-001",
                "status": "final",
                "subject": {"reference": "Patient/pt-001"},
            },
        },
        {
            "fullUrl": "Procedure/proc-001",
            "resource": {
                "resourceType": "Procedure",
                "id": "proc-001",
                "status": "completed",
                "subject": {"reference": "Patient/pt-001"},
            },
        },
    ],
}

# Bundle with NO Patient resource — for negative testing
BUNDLE_NO_PATIENT: dict = {
    "resourceType": "Bundle",
    "id": "test-no-patient-bundle",
    "type": "collection",
    "entry": [
        {
            "fullUrl": "Claim/claim-solo",
            "resource": {
                "resourceType": "Claim",
                "id": "claim-solo",
                "status": "active",
            },
        }
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_adapter(
    corpus_root: Path,
    patient_id: str = "testpayer",
    bundle: dict = PAYER_BUNDLE,
    filename: str = "TestPayer_Test_00000000-0000-0000-0000-000000000001.json",
) -> SyntheaPayerAdapter:
    """Create a SyntheaPayerAdapter backed by a temporary corpus layout."""
    # synthea-payer reads from _sources/synthea/raw/ (same physical location as SyntheaAdapter)
    source_root = corpus_root / "_sources" / "synthea" / "raw"
    bronze_root = corpus_root / "bronze" / "synthea-payer"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    bundle_path = source_root / filename
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")

    adapter = SyntheaPayerAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {patient_id: filename}
    return adapter


# ---------------------------------------------------------------------------
# Test 1: list_patients returns known patients
# ---------------------------------------------------------------------------


def test_list_patients_returns_known_patients(tmp_path: Path) -> None:
    """list_patients() returns patient IDs whose bundle files are on disk."""
    adapter = make_adapter(tmp_path)
    patients = adapter.list_patients()
    assert patients == ["testpayer"], f"Expected ['testpayer'], got {patients}"


def test_list_patients_excludes_missing_files(tmp_path: Path) -> None:
    """list_patients() omits patients whose bundle files don't exist."""
    source_root = tmp_path / "_sources" / "synthea" / "raw"
    bronze_root = tmp_path / "bronze" / "synthea-payer"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = SyntheaPayerAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {
        "alice": "Alice_Missing.json",  # file does NOT exist
    }
    assert adapter.list_patients() == []


# ---------------------------------------------------------------------------
# Test 2: ingest writes Bundle with ONLY payer resource types (+ Patient)
# ---------------------------------------------------------------------------


def test_ingest_writes_bronze_bundle_with_only_payer_resources(tmp_path: Path) -> None:
    """ingest() emits a Bundle containing only Claim/EoB/Coverage/Patient entries."""
    adapter = make_adapter(tmp_path)
    metadata = adapter.ingest("testpayer")

    data_path = adapter.bronze_dir("testpayer") / "data.json"
    assert data_path.exists(), "data.json not written"

    bundle = json.loads(data_path.read_text())
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["id"] == "synthea-payer-testpayer"

    allowed_types = {"Claim", "ExplanationOfBenefit", "Coverage", "Patient"}
    actual_types = {
        entry["resource"]["resourceType"]
        for entry in bundle["entry"]
        if isinstance(entry.get("resource"), dict)
    }

    # No clinical resource types should be present
    unexpected = actual_types - allowed_types
    assert unexpected == set(), (
        f"Found unexpected resource types in payer bundle: {unexpected}"
    )

    # Payer types present in our fixture should be there
    assert "Claim" in actual_types, "Expected Claim resources in payer bundle"
    assert "ExplanationOfBenefit" in actual_types, "Expected EoB resources in payer bundle"
    assert "Coverage" in actual_types, "Expected Coverage resources in payer bundle"

    # Clinical types should be excluded
    clinical_types = {"Condition", "Observation", "Procedure"}
    assert actual_types.isdisjoint(clinical_types), (
        f"Clinical resource types leaked into payer bundle: "
        f"{actual_types & clinical_types}"
    )

    # Metadata fields
    assert metadata.source == "synthea-payer"
    assert metadata.patient_id == "testpayer"
    assert metadata.fetched_at == ACQUISITION_TS
    assert metadata.document_type == "fhir-bundle-payer-subset"
    assert metadata.license == "Apache-2.0"
    assert metadata.consent == "open"
    assert len(metadata.sha256) == 64, "sha256 should be 64-char hex"


# ---------------------------------------------------------------------------
# Test 3: Patient resource is preserved for identity resolution
# ---------------------------------------------------------------------------


def test_ingest_preserves_patient_resource(tmp_path: Path) -> None:
    """ingest() includes the Patient resource for downstream identity resolution."""
    adapter = make_adapter(tmp_path)
    adapter.ingest("testpayer")

    data_path = adapter.bronze_dir("testpayer") / "data.json"
    bundle = json.loads(data_path.read_text())

    patient_entries = [
        e for e in bundle["entry"]
        if isinstance(e.get("resource"), dict)
        and e["resource"].get("resourceType") == "Patient"
    ]
    assert len(patient_entries) == 1, (
        f"Expected exactly 1 Patient entry for identity resolution, "
        f"got {len(patient_entries)}"
    )
    assert patient_entries[0]["resource"]["id"] == "pt-001"


# ---------------------------------------------------------------------------
# Test 4: ingest is idempotent (byte-identical re-run)
# ---------------------------------------------------------------------------


def test_ingest_is_idempotent(tmp_path: Path) -> None:
    """Running ingest() twice produces byte-identical bronze data.json."""
    adapter = make_adapter(tmp_path)

    meta1 = adapter.ingest("testpayer")
    meta2 = adapter.ingest("testpayer")

    assert meta1.sha256 == meta2.sha256, (
        f"sha256 changed between runs: {meta1.sha256} != {meta2.sha256}"
    )

    # Direct byte-level check
    data_path = adapter.bronze_dir("testpayer") / "data.json"
    content = data_path.read_bytes()
    direct_hash = hashlib.sha256(content).hexdigest()
    assert direct_hash == meta2.sha256, "sha256 in metadata does not match file contents"


# ---------------------------------------------------------------------------
# Test 5: validate returns [] for a valid record
# ---------------------------------------------------------------------------


def test_validate_returns_empty_for_valid_record(tmp_path: Path) -> None:
    """After ingest(), validate() returns an empty error list."""
    adapter = make_adapter(tmp_path)
    adapter.ingest("testpayer")

    errors = adapter.validate("testpayer")
    assert errors == [], f"Expected no validation errors, got: {errors}"


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_validate_catches_missing_patient(tmp_path: Path) -> None:
    """validate() errors when the bronze Bundle contains no Patient resource."""
    adapter = make_adapter(tmp_path, bundle=BUNDLE_NO_PATIENT)
    adapter.ingest("testpayer")

    errors = adapter.validate("testpayer")
    assert any("Patient" in e for e in errors), (
        f"Expected a 'no Patient resource' error, got: {errors}"
    )


def test_ingest_raises_for_unknown_patient(tmp_path: Path) -> None:
    """ingest() raises ValueError for a patient_id not in PATIENT_FILE_MAP."""
    source_root = tmp_path / "_sources" / "synthea" / "raw"
    bronze_root = tmp_path / "bronze" / "synthea-payer"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    adapter = SyntheaPayerAdapter(source_root=source_root, bronze_root=bronze_root)
    adapter.PATIENT_FILE_MAP = {}

    with pytest.raises(ValueError, match="Unknown patient_id"):
        adapter.ingest("nobody")


def test_adapter_name_is_synthea_payer() -> None:
    """The adapter's canonical name is 'synthea-payer' (matches D10 + REGISTRY key)."""
    assert SyntheaPayerAdapter.name == "synthea-payer"


def test_registry_contains_synthea_payer() -> None:
    """REGISTRY maps 'synthea-payer' to SyntheaPayerAdapter."""
    from ehi_atlas.adapters import REGISTRY
    assert "synthea-payer" in REGISTRY
    assert REGISTRY["synthea-payer"] is SyntheaPayerAdapter
