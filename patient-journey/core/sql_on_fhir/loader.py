"""Load FHIR bundles from disk and stream their entries as resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator


def iter_bundle_resources(bundle_path: str | Path) -> Iterator[dict]:
    """Yield each resource contained in a FHIR Bundle JSON file."""
    with open(bundle_path) as f:
        bundle = json.load(f)
    if bundle.get("resourceType") != "Bundle":
        # Caller may have passed a single resource — yield it directly
        if bundle.get("resourceType"):
            yield bundle
        return
    for entry in bundle.get("entry", []) or []:
        resource = entry.get("resource")
        if resource:
            yield resource


def iter_bundles(directory: str | Path, limit: int | None = None) -> Iterator[Path]:
    """Yield JSON bundle paths from a directory (optionally capped)."""
    root = Path(directory)
    count = 0
    for path in sorted(root.glob("*.json")):
        yield path
        count += 1
        if limit is not None and count >= limit:
            return


def iter_all_resources(
    directory: str | Path, limit: int | None = None
) -> Iterator[dict]:
    """Stream every resource across every bundle in a directory."""
    for bundle_path in iter_bundles(directory, limit=limit):
        yield from iter_bundle_resources(bundle_path)
