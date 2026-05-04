"""Synthea-payer adapter — splits payer-side resources into a logically distinct source (Layer 1).

Synthea simulates a complete healthcare system end-to-end, generating both clinical
resources (Conditions, Observations, Procedures, etc.) and payer-side resources
(Claim, ExplanationOfBenefit, Coverage). This adapter reads the same raw Bundle as
SyntheaAdapter but emits a Bundle containing ONLY the payer-side resource types
plus the Patient resource (for downstream identity resolution).

Decision D10 in BUILD-TRACKER.md: Synthea-payer split for Source C (claims) in Phase 1.
See docs/mapping-decisions.md — "Source C (claims) — Synthea-payer split".

Privacy posture: `open` — Synthea is fully synthetic data (Apache-2.0).
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import Adapter, SourceMetadata

# Frozen acquisition timestamp for determinism — matches SyntheaAdapter and stage-bronze.py.
ACQUISITION_TS = "2000-01-01T00:00:00+00:00"


class SyntheaPayerAdapter(Adapter):
    """Adapter that splits Synthea's payer-side resources (Claim, EoB, Coverage)
    out of the clinical Bundle into a logically distinct 'synthea-payer' source.

    Reads from `_sources/synthea/raw/` (same input as SyntheaAdapter), but emits
    a Bundle containing only Claim, ExplanationOfBenefit, and Coverage resources
    plus the Patient resource (for cross-source patient identity resolution).

    This implements decision D10 (Synthea-payer split for Source C). The original
    clinical Bundle is left untouched; only the filtered view is written to bronze.

    NOTE: The clinical SyntheaAdapter still emits ALL resource types (including
    Claim/EoB/Coverage). Deduplication at Layer 3 (harmonization) is where the
    two views are reconciled. A follow-up task can add a clinical-only filter to
    SyntheaAdapter if desired (flagged per task 2.2 instructions).
    """

    name = "synthea-payer"

    # The raw source lives in the sibling _sources/synthea/raw/ directory, not
    # _sources/synthea-payer/raw/ (there is no separate physical source for payer
    # data — both adapters read the same Synthea bundle). The CLI constructs
    # source_root as _sources/<adapter-name>/raw/; we remap it here to the
    # canonical synthea raw dir, which is always two levels up ("raw/" → "synthea-payer/" →
    # "_sources/") and then down to "synthea/raw/".
    #
    # In tests, callers can pass the synthea raw dir directly (which is the natural
    # thing to do) — if source_root already ends in "synthea/raw" the remap is a no-op.
    _SYNTHEA_RAW_DIRNAME = "synthea"

    # Resource types that belong to the payer view.
    PAYER_RESOURCE_TYPES: tuple[str, ...] = ("Claim", "ExplanationOfBenefit", "Coverage")

    # Patient resource is always included for downstream identity resolution.
    _KEEP_TYPES: tuple[str, ...] = ("Claim", "ExplanationOfBenefit", "Coverage", "Patient")

    # Map: patient_id (human-readable handle) → raw bundle filename.
    # Points at _sources/synthea/raw/ — shared with SyntheaAdapter.
    PATIENT_FILE_MAP: dict[str, str] = {
        "rhett759": "Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61.json",
    }

    def __init__(self, source_root: Path, bronze_root: Path) -> None:
        """Remap source_root to _sources/synthea/raw/ if needed.

        When invoked from the CLI, source_root = _sources/synthea-payer/raw/.
        We transparently redirect to _sources/synthea/raw/ since both adapters
        read the same physical Synthea bundle (logical split, not physical).
        """
        source_root = Path(source_root)
        # Remap: .../synthea-payer/raw → .../synthea/raw
        if source_root.parent.name != self._SYNTHEA_RAW_DIRNAME:
            source_root = source_root.parent.parent / self._SYNTHEA_RAW_DIRNAME / "raw"
        super().__init__(source_root=source_root, bronze_root=bronze_root)

    def list_patients(self) -> list[str]:
        """Return patient IDs for which we have bundle files in source_root.

        Returns the human-readable keys from PATIENT_FILE_MAP that have a
        corresponding file on disk.
        """
        patients: list[str] = []
        for patient_id, filename in self.PATIENT_FILE_MAP.items():
            if (self.source_root / filename).exists():
                patients.append(patient_id)
        return sorted(patients)

    def ingest(self, patient_id: str) -> SourceMetadata:
        """Read source bundle, extract payer-side resources, write bronze record.

        Builds a new Bundle containing only Claim, ExplanationOfBenefit, Coverage,
        and Patient resources. Entries are sorted by (resourceType, id) for
        determinism so re-runs produce byte-identical output.

        The output Bundle has:
        - id = "synthea-payer-<patient_id>"
        - type = "collection"
        - entry[] filtered to PAYER_RESOURCE_TYPES + ("Patient",)
        """
        filename = self.PATIENT_FILE_MAP.get(patient_id)
        if filename is None:
            raise ValueError(
                f"Unknown patient_id {patient_id!r}. "
                f"Add it to SyntheaPayerAdapter.PATIENT_FILE_MAP."
            )

        src = self.source_root / filename
        if not src.exists():
            raise FileNotFoundError(
                f"Synthea bundle not found: {src}. "
                f"Run corpus acquisition first (see corpus/_sources/synthea/README.md)."
            )

        # Parse source Bundle
        source_bundle = json.loads(src.read_text(encoding="utf-8"))

        # Filter entries to payer resource types + Patient
        keep = set(self._KEEP_TYPES)
        filtered_entries = [
            entry
            for entry in source_bundle.get("entry", [])
            if isinstance(entry, dict)
            and isinstance(entry.get("resource"), dict)
            and entry["resource"].get("resourceType") in keep
        ]

        # Sort for determinism: (resourceType, resource.id)
        filtered_entries.sort(
            key=lambda e: (
                e["resource"].get("resourceType", ""),
                e["resource"].get("id", ""),
            )
        )

        payer_bundle: dict = {
            "resourceType": "Bundle",
            "id": f"synthea-payer-{patient_id}",
            "type": "collection",
            "entry": filtered_entries,
        }

        dst_dir = self.bronze_dir(patient_id)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "data.json"
        dst.write_text(json.dumps(payer_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        metadata = SourceMetadata(
            source=self.name,
            patient_id=patient_id,
            fetched_at=ACQUISITION_TS,
            document_type="fhir-bundle-payer-subset",
            license="Apache-2.0",
            consent="open",
            sha256=self.hash_file(dst),
            notes=(
                "Synthea-payer split per decision D10: payer-only view of Rhett759's "
                "clinical Bundle. Contains Claim, ExplanationOfBenefit, Coverage, and "
                "Patient resources only. Clinical resources (Conditions, Observations, "
                "Procedures, etc.) are left in bronze/synthea/. Both views share the "
                "same raw source at _sources/synthea/raw/. "
                "See docs/mapping-decisions.md for rationale."
            ),
        )
        self.write_metadata(patient_id, metadata)
        return metadata

    def validate(self, patient_id: str) -> list[str]:
        """Check that the payer bronze record is structurally valid.

        Returns an empty list if everything is in order; otherwise a list of
        human-readable error strings.
        """
        errors: list[str] = []

        dst_dir = self.bronze_dir(patient_id)
        data_path = dst_dir / "data.json"
        metadata_path = dst_dir / "metadata.json"

        # 1. data.json exists
        if not data_path.exists():
            errors.append(f"data.json missing at {data_path}")
            return errors

        # 2. data.json parses as JSON
        try:
            bundle = json.loads(data_path.read_text(encoding="utf-8"))
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
            e
            for e in entries
            if isinstance(e, dict)
            and isinstance(e.get("resource"), dict)
            and e["resource"].get("resourceType") == "Patient"
        ]
        if not patient_resources:
            errors.append("Bundle contains no Patient resource")

        # 5. all non-Patient resources are payer types
        non_patient = [
            e["resource"]["resourceType"]
            for e in entries
            if isinstance(e, dict)
            and isinstance(e.get("resource"), dict)
            and e["resource"].get("resourceType") != "Patient"
        ]
        unexpected = sorted(set(non_patient) - set(self.PAYER_RESOURCE_TYPES))
        if unexpected:
            errors.append(
                f"Bundle contains non-payer resource types: {unexpected}. "
                f"Expected only {sorted(self.PAYER_RESOURCE_TYPES)} + Patient."
            )

        # 6. metadata.json exists and has required fields
        if not metadata_path.exists():
            errors.append(f"metadata.json missing at {metadata_path}")
        else:
            try:
                raw_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"metadata.json is not valid JSON: {exc}")
                raw_meta = {}

            required_fields = {"source", "patient_id", "fetched_at", "license", "consent", "sha256"}
            missing = required_fields - set(raw_meta.keys())
            if missing:
                errors.append(f"metadata.json missing fields: {sorted(missing)}")

        return errors
