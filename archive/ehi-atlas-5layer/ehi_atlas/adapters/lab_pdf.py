"""Lab PDF Layer-1 adapter.

Reads PDF lab reports from `_sources/synthesized-lab-pdf/raw/` and writes
bronze records with the original PDF plus per-page rasterizations and bbox
text JSON. The Layer-2-B vision extractor (ehi_atlas.extract.pdf) consumes
those bronze artifacts.

Privacy posture: `constructed` — fully synthetic Quest-style CMP PDF.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import Adapter, SourceMetadata
from ehi_atlas.extract.layout import prepare_pdf_for_extraction

# Frozen acquisition timestamp for determinism across all Phase 1 adapters.
ACQUISITION_TS = "2000-01-01T00:00:00+00:00"


class LabPDFAdapter(Adapter):
    """Layer-1 adapter for lab-report PDFs.

    Bronze record contains:
      - data.pdf: byte-identical copy of the source PDF
      - pages/NNN.png + pages/NNN.text.json: rasterizations + layout per page
      - metadata.json: SourceMetadata

    This adapter handles the raw→bronze promotion only. Vision extraction
    (PDF pages → FHIR Observations) is task 4.3's responsibility.

    Source path note: the PDF lives at `_sources/synthesized-lab-pdf/raw/`, not
    `_sources/lab-pdf/raw/` (the CLI convention). The adapter remaps automatically:
    if the CLI-supplied source_root ends with "lab-pdf/raw", it is redirected to
    the actual synthesized-lab-pdf directory two levels up, matching the pattern
    used by SyntheaPayerAdapter.
    """

    name = "lab-pdf"

    # Map: patient_id → PDF filename in source_root.
    # source_root is corpus/_sources/synthesized-lab-pdf/raw/
    PATIENT_FILE_MAP: dict[str, str] = {
        "rhett759": "lab-report-2025-09-12-quest.pdf",
    }

    DEFAULT_DPI = 200

    def __init__(self, source_root: Path, bronze_root: Path) -> None:
        super().__init__(source_root, bronze_root)
        # Remap CLI-supplied _sources/lab-pdf/raw/ → _sources/synthesized-lab-pdf/raw/.
        # The physical source directory was named "synthesized-lab-pdf" (task 1.9).
        # Only remap when the path actually ends in "lab-pdf/raw" (i.e. came from the CLI),
        # not when a test or stage-bronze.py has already passed the correct path.
        resolved = self.source_root
        if resolved.parts[-2:] == ("lab-pdf", "raw"):
            # Navigate up past lab-pdf/ and raw/, then down into synthesized-lab-pdf/raw/
            self.source_root = resolved.parent.parent / "synthesized-lab-pdf" / "raw"

    def list_patients(self) -> list[str]:
        """Return patient IDs for which the source PDF exists in source_root."""
        patients: list[str] = []
        for patient_id, filename in self.PATIENT_FILE_MAP.items():
            if (self.source_root / filename).exists():
                patients.append(patient_id)
        return sorted(patients)

    def ingest(self, patient_id: str) -> SourceMetadata:
        """Read source PDF, write bronze record + pages/ + metadata. Idempotent.

        Steps:
        1. Resolve source PDF path from PATIENT_FILE_MAP.
        2. Copy byte-identically to bronze/<patient>/data.pdf.
        3. Call prepare_pdf_for_extraction() to populate bronze/<patient>/pages/.
        4. Write metadata.json with SourceMetadata (sha256 over data.pdf).
        """
        filename = self.PATIENT_FILE_MAP.get(patient_id)
        if filename is None:
            raise ValueError(
                f"Unknown patient_id {patient_id!r}. "
                f"Add it to LabPDFAdapter.PATIENT_FILE_MAP."
            )

        src = self.source_root / filename
        if not src.exists():
            raise FileNotFoundError(
                f"Lab PDF not found: {src}. "
                f"Run corpus acquisition first "
                f"(see corpus/_sources/synthesized-lab-pdf/README.md)."
            )

        # 1. Prepare bronze directory
        dst_dir = self.bronze_dir(patient_id)
        dst_dir.mkdir(parents=True, exist_ok=True)

        # 2. Copy PDF byte-identically
        dst_pdf = dst_dir / "data.pdf"
        shutil.copyfile(src, dst_pdf)

        # 3. Rasterize pages + extract bbox text → pages/
        pages_dir = dst_dir / "pages"
        prepare_pdf_for_extraction(
            pdf_path=dst_pdf,
            output_dir=pages_dir,
            dpi=self.DEFAULT_DPI,
        )

        # 4. Write metadata (sha256 over the bronze data.pdf)
        metadata = SourceMetadata(
            source=self.name,
            patient_id=patient_id,
            fetched_at=ACQUISITION_TS,
            document_type="lab-report-pdf",
            license="MIT",
            consent="constructed",
            sha256=self.hash_file(dst_pdf),
            notes=(
                "Synthesized Quest-style 3-page CMP. "
                "Creatinine row at page=2;bbox=72,574,540,590. "
                "Generator: corpus/_sources/synthesized-lab-pdf/generator.py. "
                "pages/ subdirectory contains rasterized PNGs + bbox text JSON "
                "per page for Layer-2-B vision extraction."
            ),
        )
        self.write_metadata(patient_id, metadata)
        return metadata

    def validate(self, patient_id: str) -> list[str]:
        """Check bronze record structural validity.

        Returns an empty list when everything is in order; otherwise a list of
        human-readable error strings describing what is wrong.
        """
        import json

        errors: list[str] = []
        dst_dir = self.bronze_dir(patient_id)
        data_path = dst_dir / "data.pdf"
        pages_dir = dst_dir / "pages"
        metadata_path = dst_dir / "metadata.json"

        # 1. data.pdf exists and is non-empty
        if not data_path.exists():
            errors.append(f"data.pdf missing at {data_path}")
            return errors  # can't continue without primary data file
        if data_path.stat().st_size == 0:
            errors.append(f"data.pdf is empty at {data_path}")

        # 2. pages/ directory exists and has at minimum 001.png + 001.text.json
        if not pages_dir.exists():
            errors.append(f"pages/ directory missing at {pages_dir}")
        else:
            first_png = pages_dir / "001.png"
            first_json = pages_dir / "001.text.json"
            if not first_png.exists():
                errors.append(f"pages/001.png missing in {pages_dir}")
            if not first_json.exists():
                errors.append(f"pages/001.text.json missing in {pages_dir}")

        # 3. metadata.json exists and parses as SourceMetadata
        if not metadata_path.exists():
            errors.append(f"metadata.json missing at {metadata_path}")
        else:
            try:
                raw_meta = json.loads(metadata_path.read_text())
                # Attempt to construct SourceMetadata to validate all required fields
                SourceMetadata(**raw_meta)
            except json.JSONDecodeError as exc:
                errors.append(f"metadata.json is not valid JSON: {exc}")
            except Exception as exc:
                errors.append(f"metadata.json fails SourceMetadata validation: {exc}")

        return errors
