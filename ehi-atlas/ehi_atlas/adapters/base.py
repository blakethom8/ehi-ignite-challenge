"""Adapter ABC + bronze-tier metadata model.

Every Layer 1 source adapter conforms to this contract. See
docs/ADAPTER-CONTRACT.md for the full specification.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ConsentPosture = Literal["open", "personal", "constructed", "claim-only"]


class SourceMetadata(BaseModel):
    """Per-bronze-record metadata, written alongside the source artifact."""

    source: str = Field(..., description="canonical source name, matches _sources/ subdir")
    patient_id: str = Field(..., description="the patient this record is for")
    fetched_at: str = Field(..., description="ISO 8601 UTC timestamp")
    document_type: str | None = Field(
        None, description="e.g. 'lab-report', 'ccda', 'fhir-bundle'"
    )
    license: str = Field(..., description="license string for redistribution")
    consent: ConsentPosture = Field(..., description="privacy posture")
    sha256: str = Field(..., description="content hash of the primary data file")
    notes: str | None = None


class Adapter(ABC):
    """Layer 1 source adapter.

    Reads from `_sources/<name>/raw/` (or `raw-redacted/` for personal sources)
    and writes to `bronze/<name>/<patient>/`.

    Adapters MUST be idempotent: running ingest() twice on the same patient
    produces byte-identical bronze output.
    """

    name: str  # canonical source name; subclasses override

    def __init__(self, source_root: Path, bronze_root: Path):
        self.source_root = Path(source_root)
        self.bronze_root = Path(bronze_root)

    @abstractmethod
    def list_patients(self) -> list[str]:
        """Patient IDs available from this source."""

    @abstractmethod
    def ingest(self, patient_id: str) -> SourceMetadata:
        """Read source, write canonical bronze record. Idempotent."""

    @abstractmethod
    def validate(self, patient_id: str) -> list[str]:
        """Return list of validation errors; empty list = valid."""

    # ---- Helpers shared by adapters ----------------------------------------

    def bronze_dir(self, patient_id: str) -> Path:
        """Canonical bronze output directory for a given patient."""
        return self.bronze_root / patient_id

    @staticmethod
    def hash_file(path: Path) -> str:
        """SHA-256 of a file's contents."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def utc_now_iso() -> str:
        """Current UTC time in ISO 8601, second-precision (no fractional)."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def write_metadata(self, patient_id: str, metadata: SourceMetadata) -> None:
        """Write metadata.json alongside the bronze data file."""
        out = self.bronze_dir(patient_id) / "metadata.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(metadata.model_dump(), indent=2, sort_keys=True) + "\n")
