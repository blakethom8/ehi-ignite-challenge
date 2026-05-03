"""Synthea FHIR R4 passthrough adapter (Layer 1).

Synthea outputs standard FHIR R4 Bundles — no format conversion required.
This adapter is a near-passthrough: read the Bundle JSON from
`_sources/synthea/raw/`, copy to `bronze/synthea/<patient>/data.json`,
and emit `SourceMetadata`.

Privacy posture: `open` — Synthea is fully synthetic data (Apache-2.0).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .base import Adapter, SourceMetadata

# Frozen acquisition timestamp for determinism across all Phase 1 adapters.
# Matches the value used by scripts/stage-bronze.py.
ACQUISITION_TS = "2000-01-01T00:00:00+00:00"


class SyntheaAdapter(Adapter):
    """Layer 1 adapter for Synthea FHIR R4 Bundle JSON files.

    Maps human-readable patient handles (e.g. "rhett759") to their bundle
    filenames. The PATIENT_FILE_MAP can be extended as new showcase patients
    are added. For unknown filenames (future use), the adapter falls back to
    using the UUID portion of the filename as the patient_id.
    """

    name = "synthea"

    # Map: patient_id (human-readable handle) → raw bundle filename.
    # Extend this map as new showcase patients are added to _sources/synthea/raw/.
    PATIENT_FILE_MAP: dict[str, str] = {
        "rhett759": "Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61.json",
    }

    def list_patients(self) -> list[str]:
        """Return patient IDs for which we have bundle files in source_root.

        Returns the human-readable keys from PATIENT_FILE_MAP that have a
        corresponding file on disk. Unknown files (not in the map) are ignored
        — they can be added to PATIENT_FILE_MAP when needed.
        """
        patients: list[str] = []
        for patient_id, filename in self.PATIENT_FILE_MAP.items():
            if (self.source_root / filename).exists():
                patients.append(patient_id)
        return sorted(patients)

    def ingest(self, patient_id: str) -> SourceMetadata:
        """Read source bundle, write bronze record + metadata. Idempotent.

        Running ingest() twice on the same patient produces byte-identical
        bronze output — the source file is immutable and we use a fixed
        timestamp (ACQUISITION_TS) rather than utc_now_iso().
        """
        filename = self.PATIENT_FILE_MAP.get(patient_id)
        if filename is None:
            raise ValueError(
                f"Unknown patient_id {patient_id!r}. "
                f"Add it to SyntheaAdapter.PATIENT_FILE_MAP."
            )

        src = self.source_root / filename
        if not src.exists():
            raise FileNotFoundError(
                f"Synthea bundle not found: {src}. "
                f"Run corpus acquisition first (see corpus/_sources/synthea/README.md)."
            )

        dst_dir = self.bronze_dir(patient_id)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "data.json"

        shutil.copyfile(src, dst)

        metadata = SourceMetadata(
            source=self.name,
            patient_id=patient_id,
            fetched_at=ACQUISITION_TS,
            document_type="fhir-bundle",
            license="Apache-2.0",
            consent="open",
            sha256=self.hash_file(dst),
            notes="Synthea-generated FHIR R4 Bundle; ground-truth showcase patient.",
        )
        self.write_metadata(patient_id, metadata)
        return metadata

    def validate(self, patient_id: str) -> list[str]:
        """Check that the bronze record is structurally valid.

        Returns an empty list if everything is in order; otherwise a list of
        human-readable error strings describing what is wrong.
        """
        errors: list[str] = []

        dst_dir = self.bronze_dir(patient_id)
        data_path = dst_dir / "data.json"
        metadata_path = dst_dir / "metadata.json"

        # 1. data.json exists
        if not data_path.exists():
            errors.append(f"data.json missing at {data_path}")
            return errors  # can't continue without the file

        # 2. data.json parses as JSON
        try:
            bundle = json.loads(data_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"data.json is not valid JSON: {exc}")
            return errors

        # 3. top-level resourceType == "Bundle"
        if bundle.get("resourceType") != "Bundle":
            errors.append(
                f"Expected resourceType='Bundle', got {bundle.get('resourceType')!r}"
            )

        # 4. contains at least one Patient resource
        entries = bundle.get("entry", [])
        patient_resources = [
            e for e in entries
            if isinstance(e, dict)
            and isinstance(e.get("resource"), dict)
            and e["resource"].get("resourceType") == "Patient"
        ]
        if not patient_resources:
            errors.append("Bundle contains no Patient resource")

        # 5. metadata.json exists and has required fields
        if not metadata_path.exists():
            errors.append(f"metadata.json missing at {metadata_path}")
        else:
            try:
                raw_meta = json.loads(metadata_path.read_text())
            except json.JSONDecodeError as exc:
                errors.append(f"metadata.json is not valid JSON: {exc}")
                raw_meta = {}

            required_fields = {"source", "patient_id", "fetched_at", "license", "consent", "sha256"}
            missing = required_fields - set(raw_meta.keys())
            if missing:
                errors.append(f"metadata.json missing fields: {sorted(missing)}")

        return errors
