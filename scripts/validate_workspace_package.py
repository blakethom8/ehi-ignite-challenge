#!/usr/bin/env python3
"""Validate an EHI Atlas portable workspace package."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

REQUIRED = [
    "README.md",
    "MANIFEST.json",
    "AGENT-INSTRUCTIONS.md",
    "PATIENT-SUMMARY.md",
    "sources/sources.json",
    "evidence/canonical-facts.json",
    "evidence/provenance.json",
    "evidence/source-contributions.json",
    "evidence/conflicts.json",
    "evidence/missing-information.json",
    "packets/second-opinion.context.json",
    "exports/clinician-handoff.md",
    "cli/atlas_workspace.py",
]


def load_json(path: Path):
    return json.loads(path.read_text())


def find_root(tmp: Path) -> Path:
    children = [p for p in tmp.iterdir() if p.is_dir()]
    if len(children) != 1:
        raise SystemExit(f"Expected one package root in zip, found {len(children)}")
    return children[0]


def validate(package: Path) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="atlas-validate-") as d:
        tmp = Path(d)
        if package.suffix == ".zip":
            with zipfile.ZipFile(package) as zf:
                zf.extractall(tmp)
            root = find_root(tmp)
        else:
            root = package

        for rel in REQUIRED:
            if not (root / rel).exists():
                errors.append(f"missing required file: {rel}")

        if errors:
            return errors

        manifest = load_json(root / "MANIFEST.json")
        if manifest.get("package_version") != "atlas-workspace.v1":
            errors.append("unexpected package_version")
        if not manifest.get("workspace_id"):
            errors.append("missing workspace_id")
        if "privacy" not in manifest:
            errors.append("missing privacy block")
        else:
            privacy = manifest["privacy"]
            if "contains_phi" not in privacy or "demo_data" not in privacy:
                errors.append("privacy block missing contains_phi/demo_data flags")

        for f in manifest.get("files", []):
            rel = f.get("path") if isinstance(f, dict) else None
            if not rel:
                errors.append("manifest file entry missing path")
                continue
            if rel.startswith("/") or ".." in Path(rel).parts:
                errors.append(f"unsafe manifest path: {rel}")
            if not (root / rel).exists():
                errors.append(f"manifest references missing file: {rel}")

        facts = load_json(root / "evidence" / "canonical-facts.json").get("facts", [])
        sources = load_json(root / "sources" / "sources.json").get("sources", [])
        packet = load_json(root / "packets" / "second-opinion.context.json")
        if not isinstance(facts, list) or len(facts) == 0:
            errors.append("canonical-facts.json has no facts")
        if not isinstance(sources, list) or len(sources) == 0:
            errors.append("sources.json has no sources")
        if not packet.get("instructions"):
            errors.append("agent packet missing instructions")

        # No absolute local filesystem leaks in JSON/text outputs.
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".json", ".md", ".csv", ".py", ".sh"}:
                text = path.read_text(errors="ignore")
                if "/Users/blake/" in text or str(Path.home()) in text:
                    errors.append(f"local absolute path leaked in {path.relative_to(root)}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate an EHI Atlas workspace package")
    ap.add_argument("package", type=Path)
    args = ap.parse_args()
    errors = validate(args.package)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        raise SystemExit(1)
    print(f"OK: {args.package}")


if __name__ == "__main__":
    main()
