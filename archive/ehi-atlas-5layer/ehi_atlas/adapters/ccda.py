"""CCDA (HL7 CDA R2) passthrough adapter (Layer 1).

Reads a C-CDA XML document from `_sources/josh-ccdas/raw/` and writes to
`bronze/ccda/<patient>/data.xml` with metadata.

Layer 2 (standardize) is responsible for converting CCDA → FHIR R4 via the
Microsoft FHIR-Converter subprocess. This adapter stays at Layer 1: raw → bronze.

The validate() method probes Microsoft FHIR-Converter availability so any
Layer 2 toolchain deficit is caught early, without blocking the Layer 1 copy.
A missing converter is reported as a "warning:" (non-fatal) — Layer 2 will
hard-fail if the conversion is attempted and the tool is absent.

Privacy posture: `open` — Josh Mandel's CCDA fixtures are CC BY 4.0.
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from .base import Adapter, SourceMetadata

# Frozen acquisition timestamp for determinism across all Phase 1 adapters.
# Matches stage-bronze.py and other adapters.
ACQUISITION_TS = "2000-01-01T00:00:00+00:00"

# HL7 CDA R2 namespace declared on the root <ClinicalDocument> element.
_HL7_V3_NS = "urn:hl7-org:v3"


# ---------------------------------------------------------------------------
# FHIR-Converter probe (cached for process lifetime)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _probe_fhir_converter() -> tuple[bool, str]:
    """Check whether Microsoft FHIR-Converter is callable as a subprocess.

    Returns (available: bool, version_or_error: str).

    Tries (in order):
    1. `fhir-converter --version`   (standalone global CLI)
    2. `npx @microsoft/fhir-converter --version`  (via npm/npx)
    3. Falls back with an explanatory message.

    The result is cached so repeated validate() calls don't fork repeatedly.
    Uses stdlib `subprocess` only — no new dependencies.
    """
    candidates = [
        ["fhir-converter", "--version"],
        ["npx", "--yes", "@microsoft/fhir-converter", "--version"],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                version_str = (result.stdout or result.stderr).strip().splitlines()[0]
                return True, version_str
            # Non-zero exit — try next candidate
        except FileNotFoundError:
            # Executable not found on PATH
            continue
        except subprocess.TimeoutExpired:
            continue
        except Exception as exc:  # noqa: BLE001
            continue

    return (
        False,
        (
            "Microsoft FHIR-Converter not found. "
            "Install via: npm install -g @microsoft/fhir-converter  "
            "(requires Node.js 18+). "
            "See docs/FHIR-CONVERTER-SETUP.md for details."
        ),
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class CCDAAdapter(Adapter):
    """Layer 1 adapter for HL7 CDA R2 (C-CDA) documents.

    Reads CCDA XML from `_sources/josh-ccdas/raw/` and writes to
    `bronze/ccda/<patient>/data.xml`. Source bytes are copied verbatim —
    no transformation at Layer 1.

    Layer 2 (standardize) will convert CCDA → FHIR R4 via Microsoft
    FHIR-Converter. The adapter's validate() probes converter availability
    so any Layer 2 deficit is caught early, but conversion output is NOT
    stored here.

    Privacy posture: `open` — CC BY 4.0.

    Note on source directory naming: The registry key is "ccda" but the actual
    `_sources/` subdirectory is `josh-ccdas` (the cloned Mandel repo). The CLI
    constructs `source_root = _sources/ccda/raw` by convention; the adapter
    detects this mismatch and reroutes to `_sources/josh-ccdas/raw` so
    `ehi-atlas ingest --source ccda` works without any CLI changes.
    """

    name = "ccda"

    # The _sources/ subdirectory that holds the raw CCDA fixtures.
    # Differs from `name` because the directory is the cloned Mandel repo.
    _SOURCE_SUBDIR = "josh-ccdas"

    # Map: patient_id → path relative to source_root (i.e. relative to raw/).
    # Extend as new CCDA fixtures are added.
    PATIENT_FILE_MAP: dict[str, str] = {
        "rhett759": "Cerner Samples/Transition_of_Care_Referral_Summary.xml",
    }

    def __init__(self, source_root: Path, bronze_root: Path) -> None:
        """Initialise with automatic source-root rerouting.

        If the CLI passes `_sources/ccda/raw` (the default convention) but
        `_sources/josh-ccdas/raw` exists, transparently use the latter. This
        lets `ehi-atlas ingest --source ccda` work without CLI changes.
        """
        super().__init__(source_root, bronze_root)
        # Reroute: if source_root ends in ccda/raw but josh-ccdas/raw exists,
        # use josh-ccdas. Keeps tests that pass an explicit path unaffected.
        candidate_name = Path(source_root).parent.name  # e.g. "ccda" or "josh-ccdas"
        if candidate_name == self.name:
            # CLI-constructed path — try the real subdir
            real_root = Path(source_root).parent.parent / self._SOURCE_SUBDIR / "raw"
            if real_root.exists():
                self.source_root = real_root

    def list_patients(self) -> list[str]:
        """Return patient IDs for which a CCDA file exists on disk."""
        patients: list[str] = []
        for patient_id, rel_path in self.PATIENT_FILE_MAP.items():
            if (self.source_root / rel_path).exists():
                patients.append(patient_id)
        return sorted(patients)

    def ingest(self, patient_id: str) -> SourceMetadata:
        """Read CCDA XML, write bronze record + metadata. Idempotent.

        The source file is copied byte-for-byte. Running ingest() twice
        on the same patient produces a byte-identical data.xml because the
        source is immutable and we use a frozen timestamp (ACQUISITION_TS).
        """
        rel_path = self.PATIENT_FILE_MAP.get(patient_id)
        if rel_path is None:
            raise ValueError(
                f"Unknown patient_id {patient_id!r}. "
                f"Add it to CCDAAdapter.PATIENT_FILE_MAP."
            )

        src = self.source_root / rel_path
        if not src.exists():
            raise FileNotFoundError(
                f"CCDA source not found: {src}. "
                f"Ensure corpus/_sources/josh-ccdas/raw/ is populated "
                f"(see corpus/_sources/josh-ccdas/README.md)."
            )

        dst_dir = self.bronze_dir(patient_id)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "data.xml"

        # Byte-identical copy — preserves encoding declaration and all whitespace.
        shutil.copyfile(src, dst)

        metadata = SourceMetadata(
            source=self.name,
            patient_id=patient_id,
            fetched_at=ACQUISITION_TS,
            document_type="ccda-r2-transition-of-care",
            license="CC BY 4.0",
            consent="open",
            sha256=self.hash_file(dst),
            notes=(
                "Cerner-vendor CCDA R2 Transition of Care; selected via task 1.7. "
                "Used as the cross-vendor referral document for the showcase patient."
            ),
        )
        self.write_metadata(patient_id, metadata)
        return metadata

    def validate(self, patient_id: str) -> list[str]:
        """Check structural validity of the bronze CCDA record.

        Checks performed:
        1. data.xml exists in the bronze directory.
        2. data.xml parses as valid XML (not just well-formed — root element check).
        3. Root element is <ClinicalDocument> in the HL7 v3 namespace.
        4. metadata.json exists and has all required fields.
        5. FHIR-Converter probe — non-fatal warning if not installed.

        Returns empty list on success; list of error strings otherwise.
        "warning:" prefix indicates non-fatal informational issues.
        """
        errors: list[str] = []

        dst_dir = self.bronze_dir(patient_id)
        data_path = dst_dir / "data.xml"
        metadata_path = dst_dir / "metadata.json"

        # 1. data.xml exists
        if not data_path.exists():
            errors.append(f"data.xml missing at {data_path}")
            return errors  # can't continue without the file

        # 2. data.xml parses as XML
        try:
            tree = ET.parse(data_path)  # noqa: S314 — local corpus file
            root = tree.getroot()
        except ET.ParseError as exc:
            errors.append(f"data.xml is not valid XML: {exc}")
            return errors

        # 3. Root element must be <ClinicalDocument> (HL7 v3 ns or bare)
        local_tag = root.tag
        # ElementTree uses Clark notation: {namespace}localname
        expected_ns = f"{{{_HL7_V3_NS}}}ClinicalDocument"
        bare = "ClinicalDocument"
        if local_tag not in (expected_ns, bare):
            errors.append(
                f"Expected root element <ClinicalDocument> "
                f"(HL7 v3 ns or bare), got {local_tag!r}"
            )

        # 4. metadata.json exists and has required fields
        if not metadata_path.exists():
            errors.append(f"metadata.json missing at {metadata_path}")
        else:
            import json  # local import to keep top-level clean

            try:
                raw_meta = json.loads(metadata_path.read_text())
            except json.JSONDecodeError as exc:
                errors.append(f"metadata.json is not valid JSON: {exc}")
                raw_meta = {}

            required_fields = {"source", "patient_id", "fetched_at", "license", "consent", "sha256"}
            missing = required_fields - set(raw_meta.keys())
            if missing:
                errors.append(f"metadata.json missing fields: {sorted(missing)}")

        # 5. Probe FHIR-Converter — non-fatal warning if absent
        available, version_or_msg = _probe_fhir_converter()
        if not available:
            errors.append(
                f"warning: FHIR-Converter unavailable (Layer 2 conversion will fail). "
                f"{version_or_msg}"
            )

        return errors
