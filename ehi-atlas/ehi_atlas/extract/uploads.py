"""Upload management for the PDF Lab.

The Streamlit PDF Lab and the Jupyter notebook both let you point at an
arbitrary PDF — uploaded via browser, dropped into a local path, or pulled
from somewhere outside the corpus. This module gives them one consistent
place to land those files and one manifest to track what's there.

Layout
------
Uploads live under::

    ehi-atlas/corpus/_sources/uploads/<sha256-prefix>/
    ├── data.pdf            ← the original bytes, byte-identical
    └── upload_meta.json    ← per-upload sidecar (filename, label, uploaded_at, sha256)

The directory name is the **first 12 hex chars of the SHA-256** of the PDF
bytes — short enough to be readable, long enough that collisions don't
practically happen for the volumes we'll see.

A top-level manifest at ``corpus/_sources/uploads/manifest.json`` lists all
uploads in chronological order. The Streamlit page reads this to populate
its "previous uploads" selector.

Privacy
-------
All paths under ``corpus/_sources/uploads/`` are **gitignored**. Treat
anything that lands here as potentially PHI even if the original source
wasn't — uploads from real portal PDFs, scanned letters, etc. are exactly
the kind of content we don't want in git history.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ehi_atlas.extract.cache import hash_file

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Resolved relative to this module: ehi-atlas/ehi_atlas/extract/uploads.py
# parents[2] is ehi-atlas/.
_EHI_ATLAS_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = _EHI_ATLAS_ROOT / "corpus" / "_sources" / "uploads"
MANIFEST_PATH = UPLOADS_ROOT / "manifest.json"

_HASH_PREFIX_LEN = 12


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UploadRecord:
    """One entry in the uploads manifest."""

    hash_prefix: str          # first 12 hex chars of SHA-256
    sha256: str               # full hex digest
    original_filename: str    # what the user uploaded ("Quest_2025-09-12.pdf")
    label: str                # human-readable label (defaults to filename)
    uploaded_at: str          # ISO 8601 with timezone
    size_bytes: int

    @property
    def directory(self) -> Path:
        """Where this upload's files live."""
        return UPLOADS_ROOT / self.hash_prefix

    @property
    def pdf_path(self) -> Path:
        """The stored PDF path."""
        return self.directory / "data.pdf"

    @property
    def meta_path(self) -> Path:
        """The per-upload sidecar metadata path."""
        return self.directory / "upload_meta.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def store_upload(
    pdf_bytes: bytes,
    *,
    original_filename: str,
    label: str | None = None,
) -> UploadRecord:
    """Persist *pdf_bytes* into the uploads directory and update the manifest.

    Idempotent: re-uploading identical bytes returns the existing record
    without rewriting the file. The manifest is updated only on the first
    upload of a given hash.

    Args:
        pdf_bytes: The raw PDF bytes (e.g. from ``st.file_uploader().getvalue()``).
        original_filename: The name as the user uploaded it (e.g.
            ``"Quest_lab_2025-09-12.pdf"``). Stored in the sidecar so the
            UI can show a friendlier label than the hash prefix.
        label: Optional display label. Defaults to ``original_filename``.

    Returns:
        :class:`UploadRecord` describing the stored upload.
    """
    import hashlib

    sha = hashlib.sha256(pdf_bytes).hexdigest()
    hash_prefix = sha[:_HASH_PREFIX_LEN]
    directory = UPLOADS_ROOT / hash_prefix
    pdf_path = directory / "data.pdf"
    meta_path = directory / "upload_meta.json"

    if pdf_path.exists():
        # Idempotent — return the existing record.
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
        return UploadRecord(**existing)

    directory.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)

    record = UploadRecord(
        hash_prefix=hash_prefix,
        sha256=sha,
        original_filename=original_filename,
        label=label or original_filename,
        uploaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        size_bytes=len(pdf_bytes),
    )

    meta_path.write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _append_to_manifest(record)
    return record


def store_upload_from_path(
    pdf_path: Path,
    *,
    label: str | None = None,
) -> UploadRecord:
    """Like :func:`store_upload` but takes a path to an existing PDF file.

    Convenience for the notebook path where you already have a PDF on disk
    (e.g. the rhett759 bronze fixture).
    """
    pdf_path = Path(pdf_path)
    return store_upload(
        pdf_path.read_bytes(),
        original_filename=pdf_path.name,
        label=label,
    )


def list_uploads() -> list[UploadRecord]:
    """Return all uploads in the order they were stored (newest last)."""
    if not MANIFEST_PATH.exists():
        return []
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = raw.get("uploads", [])
    return [UploadRecord(**e) for e in entries]


def get_upload(hash_prefix: str) -> UploadRecord | None:
    """Look up an upload by its hash prefix. Returns ``None`` if missing."""
    for record in list_uploads():
        if record.hash_prefix == hash_prefix:
            return record
    return None


def remove_upload(hash_prefix: str) -> bool:
    """Delete the upload directory + remove the manifest entry.

    Returns ``True`` if something was removed, ``False`` if the prefix
    was not found.
    """
    directory = UPLOADS_ROOT / hash_prefix
    found = directory.exists()
    if found:
        shutil.rmtree(directory)

    uploads = [u for u in list_uploads() if u.hash_prefix != hash_prefix]
    _write_manifest(uploads)
    return found


# ---------------------------------------------------------------------------
# Internal manifest helpers
# ---------------------------------------------------------------------------


def _append_to_manifest(record: UploadRecord) -> None:
    """Append *record* to the manifest, creating it if missing."""
    existing = list_uploads()
    # Idempotent: don't double-append the same hash prefix
    if any(u.hash_prefix == record.hash_prefix for u in existing):
        return
    existing.append(record)
    _write_manifest(existing)


def _write_manifest(records: list[UploadRecord]) -> None:
    """Write the full manifest atomically."""
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    body: dict[str, Any] = {
        "uploads": [asdict(r) for r in records],
    }
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(MANIFEST_PATH)
